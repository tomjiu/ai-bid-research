"""招标信息 SQLite 存储层（非生产链路——仅供研究，见 docs/PYTHON-BOUNDARY.md）。

设计说明：SQLite 为本地文件数据库，读写延迟远低于 LLM 网络调用，
故本模块采用标准库 ``sqlite3`` 的同步实现；上层异步报告生成器
可直接调用本模块而不阻塞事件循环的实际瓶颈。
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from src.storage.pragmas import configure_pragmas

_DB_SCHEMA = """
CREATE TABLE IF NOT EXISTS bids (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    bid_id       TEXT UNIQUE NOT NULL,
    project_name TEXT NOT NULL,
    region       TEXT,
    budget       REAL,
    publish_date TEXT,
    deadline     TEXT,
    category     TEXT,
    purchaser    TEXT,
    agency       TEXT,
    winner       TEXT,
    source_url   TEXT,
    requirements TEXT,
    created_at   TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);
CREATE INDEX IF NOT EXISTS idx_bids_publish_date ON bids(publish_date);
CREATE INDEX IF NOT EXISTS idx_bids_bid_id ON bids(bid_id);

-- #601 批次 B：抽取失败/拒收公告的降级面（研究工作区，非生产）。
-- 同件公告（指纹一致）只登记一次；重试成功后置 resolved。
CREATE TABLE IF NOT EXISTS pending_announcements (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    fingerprint  TEXT UNIQUE NOT NULL,
    bid_id       TEXT,
    raw_text     TEXT,
    payload      TEXT,
    reason       TEXT NOT NULL,
    error        TEXT,
    hit_rate     REAL,
    status       TEXT NOT NULL DEFAULT 'pending',
    created_at   TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    updated_at   TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS idx_pending_status ON pending_announcements(status);

-- #601 批次 D：研究管道运行台账（审计面——报告基于哪次运行的数据可追溯）
CREATE TABLE IF NOT EXISTS pipeline_runs (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at   TEXT NOT NULL,
    finished_at  TEXT,
    source       TEXT,
    keyword      TEXT,
    days         INTEGER,
    watermark    REAL,
    stages       TEXT,
    report_path  TEXT,
    status       TEXT NOT NULL DEFAULT 'running'
);
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_started ON pipeline_runs(started_at DESC);
"""

#: 目标版本 → 迁移脚本（R56 迁移框架）。
#: v2 = 当前结构（bids/pending_announcements/pipeline_runs 全量建表
#: 由 _DB_SCHEMA IF NOT EXISTS 幂等覆盖，故 v2 迁移为空跑——
#: 只钉 user_version 标记位）。未来 schema 变更在此追加。
_MIGRATIONS: Dict[int, str] = {
    2: "-- v2：基线标记（结构由 _DB_SCHEMA 幂等保证）",
    # v3（R58 断点续跑）：抽取状态列——collect 置 'raw'，
    # 抽取成功置 'extracted'；NULL = 外部导入/历史行（来源不明，
    # 不参与续跑扫描）。不在 _BID_COLUMNS：导入导出面不泄露内部态。
    3: "ALTER TABLE bids ADD COLUMN extract_status TEXT;",
}

# 允许写入 bids 表的业务字段（requirements 以 JSON 文本存储）
_BID_COLUMNS = (
    "bid_id",
    "project_name",
    "region",
    "budget",
    "publish_date",
    "deadline",
    "category",
    "purchaser",
    "agency",
    "winner",
    "source_url",
    "requirements",
)


class BidDatabase:
    """招标信息数据库封装。

    Attributes:
        db_path: 数据库文件路径（``:memory:`` 表示内存库）。
    """

    def __init__(self, db_path: Union[str, Path] = "data/bids.db") -> None:
        """初始化数据库连接并确保表结构存在。

        Args:
            db_path: SQLite 数据库文件路径；父目录不存在时自动创建。

        Raises:
            sqlite3.DatabaseError: 建表失败时。
        """
        self.db_path = Path(db_path) if str(db_path) != ":memory:" else db_path
        if str(db_path) != ":memory:":
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path))
        self._conn.row_factory = sqlite3.Row
        # R42：平台安全 PRAGMA——WAL 探测-回退（Windows 网络盘/旧 FAT
        # 切不上时保持 delete+FULL，不静默谎报并发能力）
        if str(db_path) != ":memory:":
            self.pragmas = configure_pragmas(self._conn)
        else:
            self.pragmas = {"journal_mode": "memory", "synchronous": "n/a"}
        self._conn.executescript(_DB_SCHEMA)
        self._conn.commit()
        self._apply_migrations()

    # ------------------------------------------------------------------
    # Schema 版本与迁移（R56）
    # ------------------------------------------------------------------

    def _apply_migrations(self) -> None:
        """按序应用迁移至最新版本（PRAGMA user_version 记录当前位）。

        迁移表 :data:`_MIGRATIONS` 以目标版本号 → SQL 脚本映射；
        未来加列/加表时追加条目，旧库自动逐级升级（研究库小，
        全程同步完成）。
        """
        current = self._conn.execute("PRAGMA user_version").fetchone()[0]
        for version in sorted(_MIGRATIONS):
            if version > current:
                self._conn.executescript(_MIGRATIONS[version])
                self._conn.execute(f"PRAGMA user_version = {version}")
                self._conn.commit()

    def schema_info(self) -> dict:
        """库结构状态面（db status 消费）。

        Returns:
            ``{"user_version": n, "tables": {表名: 行数}}``。
        """
        version = self._conn.execute("PRAGMA user_version").fetchone()[0]
        tables: Dict[str, int] = {}
        rows = self._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
            " AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
        for row in rows:
            name = row[0]
            count = self._conn.execute(
                f"SELECT COUNT(*) FROM {name}"  # noqa: S608——表名来自 sqlite_master 白名单
            ).fetchone()[0]
            tables[name] = count
        return {"user_version": version, "tables": tables}

    def set_extract_status(self, bid_id: str, status: str) -> None:
        """设置单条记录的抽取状态（R58）。

        Args:
            bid_id: 记录标识。
            status: ``raw``（采集入库待抽）/ ``extracted``（抽取完成）。
        """
        self._conn.execute(
            "UPDATE bids SET extract_status = ? WHERE bid_id = ?",
            (status, str(bid_id)),
        )
        self._conn.commit()

    def extract_status_of(self, bid_id: str) -> Optional[str]:
        """读取单条记录的抽取状态（缺行/未标记 → None）。"""
        row = self._conn.execute(
            "SELECT extract_status FROM bids WHERE bid_id = ?", (str(bid_id),)
        ).fetchone()
        return row[0] if row else None

    def list_by_extract_status(
        self, status: str, *, limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """按抽取状态列行（续跑扫描面）。"""
        sql = (
            "SELECT bid_id FROM bids WHERE extract_status = ?"
            " ORDER BY bid_id"
        )
        if limit is not None:
            sql += f" LIMIT {int(limit)}"
        rows = self._conn.execute(sql, (status,)).fetchall()
        return [dict(r) for r in rows]

    def resolve_pending_by_bid(self, bid_id: str) -> int:
        """按 bid_id 解决 pending 条目（R58：续跑成功后自动清账）。

        Returns:
            解决的条数（0 = 无该记录的 pending 条目）。
        """
        cursor = self._conn.execute(
            "UPDATE pending_announcements SET status = 'resolved',"
            " updated_at = datetime('now','localtime')"
            " WHERE bid_id = ? AND status = 'pending'",
            (str(bid_id),),
        )
        self._conn.commit()
        return cursor.rowcount

    # ------------------------------------------------------------------
    # 写入
    # ------------------------------------------------------------------

    def save_bid(self, bid: Dict[str, Any]) -> int:
        """保存或更新一条招标项目记录（按 ``bid_id`` 幂等 upsert）。

        Args:
            bid: 项目数据字典，须含 ``bid_id`` 与 ``project_name``；
                ``requirements`` 列表会被序列化为 JSON 文本存储。

        Returns:
            受影响的行数（成功为 1）。

        Raises:
            KeyError: 缺少必填字段时。
        """
        for required in ("bid_id", "project_name"):
            if not bid.get(required):
                raise KeyError(f"招标项目缺少必填字段: {required}")

        row = {key: bid.get(key) for key in _BID_COLUMNS}
        if isinstance(row["requirements"], (list, dict)):
            row["requirements"] = json.dumps(
                row["requirements"], ensure_ascii=False
            )
        row["bid_id"] = str(row["bid_id"])
        row["project_name"] = str(row["project_name"])

        columns = ", ".join(_BID_COLUMNS)
        placeholders = ", ".join("?" for _ in _BID_COLUMNS)
        updates = ", ".join(
            f"{key} = excluded.{key}" for key in _BID_COLUMNS if key != "bid_id"
        )
        cursor = self._conn.execute(
            f"INSERT INTO bids ({columns}) VALUES ({placeholders}) "
            f"ON CONFLICT(bid_id) DO UPDATE SET {updates}",
            [row[key] for key in _BID_COLUMNS],
        )
        self._conn.commit()
        return cursor.rowcount

    def import_bids(self, bids: List[Dict[str, Any]]) -> int:
        """批量导入项目记录。

        Args:
            bids: 项目数据字典列表。

        Returns:
            成功保存的条数。
        """
        saved = 0
        for bid in bids:
            saved += self.save_bid(bid)
        return saved

    # ------------------------------------------------------------------
    # 查询
    # ------------------------------------------------------------------

    def get_bid(self, bid_id: str) -> Optional[Dict[str, Any]]:
        """按招标编号查询单条记录。

        Args:
            bid_id: 招标编号。

        Returns:
            项目数据字典；不存在时返回 ``None``。其中 ``requirements``
            为反序列化后的列表。
        """
        cursor = self._conn.execute(
            "SELECT * FROM bids WHERE bid_id = ?", (str(bid_id),)
        )
        row = cursor.fetchone()
        return self._row_to_dict(row) if row else None

    def query_bids(
        self,
        keyword: Optional[str] = None,
        days: Optional[int] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """按关键词与时间窗口查询项目记录。

        Args:
            keyword: 关键词，对 ``project_name`` 与 ``bid_id`` 做
                模糊匹配；``None`` 表示不过滤。
            days: 回溯天数（基于 ``publish_date``）；``None`` 表示不过滤。
            limit: 最多返回条数。

        Returns:
            按 ``publish_date`` 降序排列的项目列表。
        """
        clauses: List[str] = []
        params: List[Any] = []

        if keyword:
            clauses.append("(project_name LIKE ? OR bid_id LIKE ?)")
            pattern = f"%{keyword}%"
            params.extend([pattern, pattern])

        if days is not None:
            since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
            clauses.append("publish_date IS NOT NULL AND publish_date >= ?")
            params.append(since)

        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)
        cursor = self._conn.execute(
            "SELECT * FROM bids" + where
            + " ORDER BY publish_date DESC, id DESC LIMIT ?",
            params,
        )
        return [self._row_to_dict(row) for row in cursor.fetchall()]

    def count_bids(
        self, keyword: Optional[str] = None, days: Optional[int] = None
    ) -> int:
        """统计满足过滤条件的项目条数。

        Args:
            keyword: 关键词过滤，语义同 :meth:`query_bids`。
            days: 回溯天数过滤，语义同 :meth:`query_bids`。

        Returns:
            符合条件的记录总数。
        """
        clauses: List[str] = []
        params: List[Any] = []
        if keyword:
            clauses.append("(project_name LIKE ? OR bid_id LIKE ?)")
            pattern = f"%{keyword}%"
            params.extend([pattern, pattern])
        if days is not None:
            since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
            clauses.append("publish_date IS NOT NULL AND publish_date >= ?")
            params.append(since)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        cursor = self._conn.execute("SELECT COUNT(*) FROM bids" + where, params)
        return int(cursor.fetchone()[0])

    def stats(self) -> Dict[str, Any]:
        """返回数据库统计概览。

        Returns:
            含 ``total``（总记录数）与 ``awarded``（已含中标人的记录数）
            的字典。
        """
        total = self.count_bids()
        cursor = self._conn.execute(
            "SELECT COUNT(*) FROM bids WHERE winner IS NOT NULL AND winner != ''"
        )
        awarded = int(cursor.fetchone()[0])
        return {"total": total, "awarded": awarded}

    # ------------------------------------------------------------------
    # 降级面：pending_announcements（#601 批次 B）
    # ------------------------------------------------------------------

    def save_pending(
        self,
        fingerprint: str,
        reason: str,
        *,
        bid_id: Optional[str] = None,
        raw_text: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
        hit_rate: Optional[float] = None,
        status: str = "pending",
    ) -> int:
        """保存或更新一条待处理公告（按 fingerprint 幂等 upsert）。

        Args:
            fingerprint: 公告指纹（同件唯一键；原文流用原文 hash）。
            reason: 登记原因（``llm_error`` / ``rejected`` / ``no_text``）。
            bid_id: 招标编号（缺编号场景为 ``None``）。
            raw_text: 公告原文（重试面需要）。
            payload: 可重放的完整载荷（to_bid_row + extras + content）。
            error: 失败详情（人读）。
            hit_rate: 登记时的字段命中率快照。
            status: ``pending`` / ``resolved`` / ``skipped``。

        Returns:
            受影响行数（1 成功）。
        """
        if not fingerprint or not str(fingerprint).strip():
            raise KeyError("待处理公告缺少指纹（fingerprint）")
        cursor = self._conn.execute(
            """
            INSERT INTO pending_announcements
                (fingerprint, bid_id, raw_text, payload, reason, error,
                 hit_rate, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(fingerprint) DO UPDATE SET
                bid_id = excluded.bid_id,
                raw_text = excluded.raw_text,
                payload = excluded.payload,
                reason = excluded.reason,
                error = excluded.error,
                hit_rate = excluded.hit_rate,
                status = excluded.status,
                updated_at = datetime('now', 'localtime')
            """,
            (
                str(fingerprint),
                bid_id,
                raw_text,
                json.dumps(payload, ensure_ascii=False)
                if payload is not None
                else None,
                reason,
                error,
                hit_rate,
                status,
            ),
        )
        self._conn.commit()
        return cursor.rowcount

    def list_pending(
        self,
        status: str = "pending",
        limit: int = 100,
        *,
        order: str = "fifo",
    ) -> List[Dict[str, Any]]:
        """列出待处理公告（status 过滤）。

        Args:
            status: 状态过滤（默认 ``pending``）。
            limit: 返回上限。
            order: 排序口径（R61）——

                - ``fifo``（缺省）：created_at, id——登记序，行为
                  与历史版本一致；
                - ``priority``：重试价值优先——

                  1. ``llm_error``（瞬态故障）先于 ``rejected``
                     （校验拒收偏结构性，重试命中期望低）；
                  2. ``hit_rate`` 降序 NULL 末尾（越接近合格越
                     值得先重试）；
                  3. created_at, id 兜底（同优先级保持稳定序）。

        Returns:
            记录字典列表（payload 已反序列化）。
        """
        order_sql = (
            """
            CASE reason WHEN 'llm_error' THEN 0 ELSE 1 END,
            hit_rate IS NULL, hit_rate DESC,
            created_at, id
            """
            if order == "priority"
            else "created_at, id"
        )
        cursor = self._conn.execute(
            f"""
            SELECT * FROM pending_announcements
            WHERE status = ? ORDER BY {order_sql} LIMIT ?
            """,  # noqa: S608——order_sql 为封闭白名单两值
            (status, limit),
        )
        rows = []
        for row in cursor.fetchall():
            item = dict(row)
            if item.get("payload"):
                try:
                    item["payload"] = json.loads(item["payload"])
                except (json.JSONDecodeError, TypeError):
                    item["payload"] = None  # 损坏载荷不炸查询（#563 兕底口径）
            rows.append(item)
        return rows

    def update_pending_status(
        self, fingerprint: str, status: str, *, error: Optional[str] = None
    ) -> int:
        """更新待处理公告状态（重试成功 resolved / 人工 skipped）。

        Args:
            fingerprint: 公告指纹。
            status: 新状态（``resolved`` / ``skipped`` / ``pending``）。
            error: 可选——覆盖错误详情（重试仍失败时更新）。

        Returns:
            受影响行数（0 = 指纹不存在）。
        """
        cursor = self._conn.execute(
            """
            UPDATE pending_announcements
            SET status = ?, error = COALESCE(?, error),
                updated_at = datetime('now', 'localtime')
            WHERE fingerprint = ?
            """,
            (status, error, str(fingerprint)),
        )
        self._conn.commit()
        return cursor.rowcount

    def pending_stats(self) -> Dict[str, Any]:
        """待处理公告统计（按 status 分组 + reason 分布）。

        Returns:
            ``{"total", "pending", "resolved", "skipped", "by_reason"}``。
        """
        cursor = self._conn.execute(
            """
            SELECT status, COUNT(*) AS c FROM pending_announcements
            GROUP BY status
            """
        )
        counts = {row["status"]: int(row["c"]) for row in cursor.fetchall()}
        cursor = self._conn.execute(
            """
            SELECT reason, COUNT(*) AS c FROM pending_announcements
            WHERE status = 'pending' GROUP BY reason
            """
        )
        by_reason = {row["reason"]: int(row["c"]) for row in cursor.fetchall()}
        return {
            "total": sum(counts.values()),
            "pending": counts.get("pending", 0),
            "resolved": counts.get("resolved", 0),
            "skipped": counts.get("skipped", 0),
            "by_reason": by_reason,
        }

    def pipeline_runs_save(
        self,
        started_at: str,
        *,
        source: Optional[str] = None,
        keyword: Optional[str] = None,
        days: Optional[int] = None,
        watermark: Optional[float] = None,
    ) -> int:
        """登记一次管道运行（running 态）——返回运行 ID。

        Args:
            started_at: 开始时刻（人读 ISO 字符串）。
            source: 本次源路径。
            keyword: 分析关键词。
            days: 时间窗口。
            watermark: 增量水位（epoch 浮点秒——亚秒精度，
                与文件 mtime 同口径比较；人读时刻是秒级，
                直接比对会有同秒竞态）。

        Returns:
            新运行行的 id（供 finish 用）。
        """
        cursor = self._conn.execute(
            """
            INSERT INTO pipeline_runs
                (started_at, source, keyword, days, watermark, status)
            VALUES (?, ?, ?, ?, ?, 'running')
            """,
            (started_at, str(source) if source else None, keyword, days,
             watermark),
        )
        self._conn.commit()
        return int(cursor.lastrowid)

    def pipeline_runs_finish(
        self,
        run_id: int,
        *,
        stages: Optional[List[Dict[str, Any]]] = None,
        report_path: Optional[str] = None,
        status: str = "done",
    ) -> int:
        """收口一次运行（stages JSON + 报告路径 + 状态）。

        Args:
            run_id: :meth:`pipeline_runs_save` 返回的运行 ID。
            stages: 各阶段结果（name/status/detail 序列化面）。
            report_path: 报告文件路径。
            status: ``done`` / ``failed``。

        Returns:
            受影响行数。
        """
        cursor = self._conn.execute(
            """
            UPDATE pipeline_runs
            SET finished_at = datetime('now', 'localtime'),
                stages = ?, report_path = ?, status = ?
            WHERE id = ?
            """,
            (
                json.dumps(stages, ensure_ascii=False, default=str)
                if stages is not None
                else None,
                report_path,
                status,
                run_id,
            ),
        )
        self._conn.commit()
        return cursor.rowcount

    def pipeline_runs_list(
        self, *, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """列出最近 N 次运行（新在前，stages 已反序列化）。"""
        cursor = self._conn.execute(
            "SELECT * FROM pipeline_runs ORDER BY id DESC LIMIT ?",
            (limit,),
        )
        rows = []
        for row in cursor.fetchall():
            item = dict(row)
            if item.get("stages"):
                try:
                    item["stages"] = json.loads(item["stages"])
                except (json.JSONDecodeError, TypeError):
                    item["stages"] = None  # 损坏兜底（#563 口径）
            rows.append(item)
        return rows

    def pipeline_runs_last(self, *, status: str = "done") -> Optional[Dict[str, Any]]:
        """最近一次指定状态的运行（增量水位的时序基础）。"""
        cursor = self._conn.execute(
            "SELECT * FROM pipeline_runs WHERE status = ? "
            "ORDER BY id DESC LIMIT 1",
            (status,),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        item = dict(row)
        if item.get("stages"):
            try:
                item["stages"] = json.loads(item["stages"])
            except (json.JSONDecodeError, TypeError):
                item["stages"] = None
        return item

    # ------------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------------

    def close(self) -> None:
        """关闭数据库连接。"""
        self._conn.close()

    def __enter__(self) -> "BidDatabase":
        """进入上下文管理器。

        Returns:
            数据库实例自身。
        """
        return self

    def __exit__(self, *exc_info: Any) -> None:
        """退出上下文管理器，确保连接关闭。

        Args:
            exc_info: 异常信息三元组（未使用）。
        """
        self.close()

    # ------------------------------------------------------------------
    # 内部工具
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
        """将查询行转换为业务字典。

        Args:
            row: sqlite3 查询行。

        Returns:
            业务字典，``requirements`` 反序列化为列表（失败时置空列表），
            ``created_at``/``id`` 一并透出。
        """
        data = {key: row[key] for key in row.keys()}
        if data.get("requirements"):
            try:
                data["requirements"] = json.loads(data["requirements"])
            except (json.JSONDecodeError, TypeError):
                data["requirements"] = []
        return data
