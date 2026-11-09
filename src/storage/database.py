"""招标信息 SQLite 存储层（非生产链路——仅供研究，见 docs/PYTHON-BOUNDARY.md）。

设计说明：SQLite 为本地文件数据库，读写延迟远低于 LLM 网络调用，
故本模块采用标准库 ``sqlite3`` 的同步实现；上层异步报告生成器
可直接调用本模块而不阻塞事件循环的实际瓶颈。
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

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

-- raw 公告暂存面（#601 批次 B）：LLM 不可用/JSON 损坏时原文不丢，
-- pending 标记等待重试——失败降级不阻塞管道。
CREATE TABLE IF NOT EXISTS raw_announcements (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    source     TEXT NOT NULL,
    content    TEXT NOT NULL,
    content_sha TEXT NOT NULL,
    status     TEXT NOT NULL DEFAULT 'pending',
    error      TEXT,
    bid_id     TEXT,
    attempts   INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);
CREATE INDEX IF NOT EXISTS idx_raw_status ON raw_announcements(status);
CREATE UNIQUE INDEX IF NOT EXISTS idx_raw_content_sha ON raw_announcements(content_sha);
"""

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
        self._conn.executescript(_DB_SCHEMA)
        self._conn.commit()

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

    def iter_all(self, chunk_size: int = 500):
        """全表迭代（#601 批次 C：分析面数据集加载 / 去重水位）。

        Args:
            chunk_size: 分批拉取的行数（游标按 id 升序推进，
                内存占用与全表规模解耦）。

        Yields:
            每行反序列化后的业务字典（``requirements`` 已还原为列表）。
        """
        last_id = 0
        while True:
            cursor = self._conn.execute(
                "SELECT * FROM bids WHERE id > ? ORDER BY id ASC LIMIT ?",
                (last_id, chunk_size),
            )
            rows = cursor.fetchall()
            if not rows:
                return
            for row in rows:
                last_id = row["id"]
                yield self._row_to_dict(row)

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
    # raw 公告暂存面（#601 批次 B）
    # ------------------------------------------------------------------

    def save_raw(
        self, source: str, content: str, *, content_sha: Optional[str] = None
    ) -> int:
        """存入一条公告原文（按内容指纹幂等——同文重复导入不重复占位）。

        Args:
            source: 来源标识（通常是文件名或 ``file.txt``）。
            content: 公告原文全文。
            content_sha: 内容 sha256 指纹；缺省时现算。

        Returns:
            新记录 id；内容已存在时返回既有记录 id（幂等）。
        """
        sha = content_sha or hashlib.sha256(
            content.encode("utf-8")
        ).hexdigest()
        existing = self._conn.execute(
            "SELECT id FROM raw_announcements WHERE content_sha = ?", (sha,)
        ).fetchone()
        if existing:
            return int(existing["id"])
        cursor = self._conn.execute(
            "INSERT INTO raw_announcements (source, content, content_sha)"
            " VALUES (?, ?, ?)",
            (source, content, sha),
        )
        self._conn.commit()
        return int(cursor.lastrowid)

    def has_raw_content(self, content: str) -> bool:
        """判断公告原文是否已在暂存面（内容指纹比对）。

        Args:
            content: 公告原文全文。

        Returns:
            已存在返回 ``True``。
        """
        sha = hashlib.sha256(content.encode("utf-8")).hexdigest()
        row = self._conn.execute(
            "SELECT 1 FROM raw_announcements WHERE content_sha = ?", (sha,)
        ).fetchone()
        return row is not None

    def pending_raws(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """取出待抽取的公告原文（含重试：状态仍为 pending 的失败件）。

        Args:
            limit: 最多返回条数；``None`` 表示全部。

        Returns:
            按 id 升序的记录列表（含 ``id`` / ``source`` / ``content``
            / ``attempts``）。
        """
        query = (
            "SELECT id, source, content, attempts FROM raw_announcements"
            " WHERE status = 'pending' ORDER BY id ASC"
        )
        params: List[Any] = []
        if limit is not None:
            query += " LIMIT ?"
            params.append(limit)
        cursor = self._conn.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]

    def mark_raw_extracted(self, raw_id: int, bid_id: str) -> None:
        """标记公告原文抽取成功。

        Args:
            raw_id: raw_announcements 记录 id。
            bid_id: 抽取得到的招标编号（关联 bids 表）。
        """
        self._conn.execute(
            "UPDATE raw_announcements SET status = 'extracted', bid_id = ?,"
            " error = NULL, attempts = attempts + 1,"
            " updated_at = datetime('now', 'localtime') WHERE id = ?",
            (bid_id, raw_id),
        )
        self._conn.commit()

    def mark_raw_failed(self, raw_id: int, error: str) -> None:
        """标记公告原文抽取失败（状态保持 pending——留待重试）。

        Args:
            raw_id: raw_announcements 记录 id。
            error: 失败原因（逐字保留供人工排查）。
        """
        self._conn.execute(
            "UPDATE raw_announcements SET status = 'pending', error = ?,"
            " attempts = attempts + 1,"
            " updated_at = datetime('now', 'localtime') WHERE id = ?",
            (error, raw_id),
        )
        self._conn.commit()

    def raw_stats(self) -> Dict[str, int]:
        """raw 暂存面状态统计。

        Returns:
            含 ``total`` / ``pending`` / ``extracted`` 的计数字典。
        """
        cursor = self._conn.execute(
            "SELECT status, COUNT(*) AS n FROM raw_announcements"
            " GROUP BY status"
        )
        counts = {row["status"]: int(row["n"]) for row in cursor.fetchall()}
        return {
            "total": sum(counts.values()),
            "pending": counts.get("pending", 0),
            "extracted": counts.get("extracted", 0),
        }

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
