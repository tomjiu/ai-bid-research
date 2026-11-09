"""管道编排器（#601 批次 D·R17/R18）——四阶段串联 + 运行留档。

编排纪律：

* **阶段失败不中断**——collect/extract 失败时 analyze/report 照跑
  （它们只依赖库内数据，不依赖当次阶段产出）；全部阶段跑完后
  ``PipelineRun.all_ok`` 汇总裁决；
* **增量水位**——collect 默认增量（DB 水位三键分类）、extract 天然
  增量（pending 过滤 + 内容指纹），重复运行零副作用；
* **运行留档**——每次 run 写 ``pipeline_runs`` 表（各阶段统计
  JSON 留档，研究面可回溯「哪次跑了什么」）；
* **演练模式**——dry_run 只跑 collect/extract 的演练语义 + analyze
  （只读），report 不落盘、留档不写。
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.analyze import (
    compute_stats,
    format_stats_markdown,
    load_dataset,
    save_analysis_report,
)
from src.pipeline.stages import (
    StageResult,
    run_collect_stage,
    run_extract_stage,
)
from src.report.generator import ReportGenerator
from src.storage.database import BidDatabase

#: pipeline_runs 表（运行留档——阶段状态报告的水位面）。
_PIPELINE_RUNS_SCHEMA = """
CREATE TABLE IF NOT EXISTS pipeline_runs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at  TEXT NOT NULL,
    finished_at TEXT,
    ok          INTEGER,
    stages_json TEXT NOT NULL,
    dry_run     INTEGER NOT NULL DEFAULT 0,
    report_path TEXT
);
"""


# ----------------------------------------------------------------------
# analyze / report 阶段
# ----------------------------------------------------------------------


def run_analyze_stage(
    db: BidDatabase,
    *,
    keyword: Optional[str] = None,
    days: Optional[int] = None,
    region: Optional[str] = None,
) -> StageResult:
    """analyze 阶段：数据集 → 五维统计（只读，不落任何状态）。

    Returns:
        阶段结果——summary 含 ``total``/``awarded``/``with_budget``/
        ``with_date`` 与 ``stats``（五维统计汇总，report 阶段消费）；
        空数据集视为阶段失败（无样本不伪造统计——诚实拒绝）。
    """
    start = time.monotonic()
    ds = load_dataset(db, keyword=keyword, days=days, region=region)
    if ds.total == 0:
        return StageResult(
            name="analyze",
            ok=False,
            duration_ms=int((time.monotonic() - start) * 1000),
            summary={"total": 0},
            error="过滤后数据集为空——无样本可统计",
        )
    stats = compute_stats(ds)
    summary = {
        "total": ds.total,
        "awarded": ds.awarded,
        "with_budget": ds.with_budget,
        "with_date": ds.with_date,
        "stats": stats,
    }
    return StageResult(
        name="analyze",
        ok=True,
        duration_ms=int((time.monotonic() - start) * 1000),
        summary=summary,
    )


def run_report_stage(
    stats: Dict[str, Any],
    output_dir: Path,
    *,
    title: str = "招标数据分析报告",
    html: bool = False,
) -> StageResult:
    """report 阶段：统计 → 确定性 Markdown（可选 HTML）。

    Args:
        stats: ``compute_stats`` 产物（由 analyze 阶段透传）。
        output_dir: 报告输出目录。
        title: 报告标题。
        html: 是否导出 HTML。

    Returns:
        阶段结果——summary 含 ``markdown``/``html`` 路径。
    """
    start = time.monotonic()
    markdown = format_stats_markdown(stats, title=title)
    generator = ReportGenerator(output_dir=output_dir, llm_client=None)
    saved = save_analysis_report(
        generator, markdown, prefix="pipeline", html=html
    )
    return StageResult(
        name="report",
        ok=True,
        duration_ms=int((time.monotonic() - start) * 1000),
        summary={"markdown": saved["markdown"], "html": saved["html"]},
    )


# ----------------------------------------------------------------------
# 运行模型
# ----------------------------------------------------------------------


@dataclass
class PipelineRun:
    """一次管道运行的结果。

    Attributes:
        started_at: 开始时间（ISO 字符串）。
        stages: 各阶段结果（按执行顺序）。
        dry_run: 是否演练模式。
        stats: analyze 阶段的五维统计（report 阶段消费；失败时为 ``None``）。
    """

    started_at: str
    stages: List[StageResult] = field(default_factory=list)
    dry_run: bool = False
    stats: Optional[Dict[str, Any]] = None

    @property
    def all_ok(self) -> bool:
        """全部阶段成功。"""
        return all(stage.ok for stage in self.stages)

    @property
    def duration_ms(self) -> int:
        """各阶段耗时合计（毫秒）。"""
        return sum(stage.duration_ms for stage in self.stages)

    def stage(self, name: str) -> Optional[StageResult]:
        """按名称取阶段结果。"""
        for result in self.stages:
            if result.name == name:
                return result
        return None

    def to_dict(self) -> Dict[str, Any]:
        """序列化形态（留档/打印用）。"""
        return {
            "started_at": self.started_at,
            "dry_run": self.dry_run,
            "all_ok": self.all_ok,
            "duration_ms": self.duration_ms,
            "stages": [stage.to_dict() for stage in self.stages],
        }

    def format_summary(self) -> str:
        """人读运行摘要（CLI 打印用）。"""
        lines = [
            f"管道运行（{'演练' if self.dry_run else '正式'}）"
            f"——{'全部成功' if self.all_ok else '存在失败阶段'}，"
            f"总耗时 {self.duration_ms} ms"
        ]
        for stage in self.stages:
            status = "✓" if stage.ok else "✗"
            error = f"：{stage.error}" if stage.error else ""
            lines.append(f"  {status} {stage.name}（{stage.duration_ms} ms）{error}")
        return "\n".join(lines)


# ----------------------------------------------------------------------
# 编排器
# ----------------------------------------------------------------------


class Pipeline:
    """四阶段管道编排器。

    Attributes:
        db: 研究工作区数据库（bids + raw_announcements + pipeline_runs）。
        output_dir: 报告输出目录。
    """

    def __init__(
        self,
        db: BidDatabase,
        output_dir: Path = Path("output/reports"),
    ) -> None:
        """初始化（建 pipeline_runs 表——幂等）。

        Args:
            db: 已打开的数据库。
            output_dir: 报告输出目录。
        """
        self.db = db
        self.output_dir = Path(output_dir)
        self.db._conn.executescript(_PIPELINE_RUNS_SCHEMA)  # noqa: SLF001
        self.db._conn.commit()  # noqa: SLF001

    def run(
        self,
        *,
        announcements: Optional[Path] = None,
        raw_texts: Optional[Path] = None,
        keyword: Optional[str] = None,
        days: Optional[int] = None,
        region: Optional[str] = None,
        title: str = "招标数据分析报告",
        html: bool = False,
        dry_run: bool = False,
        extract_limit: Optional[int] = None,
    ) -> PipelineRun:
        """执行完整管道：collect → extract → analyze → report。

        Args:
            announcements: 结构化公告源（collect 阶段；``None`` 跳过该阶段）。
            raw_texts: 原文公告源（extract 阶段；``None`` 时 extract
                仅重试库内 pending）。
            keyword/days/region: analyze 数据集过滤。
            title: 报告标题。
            html: 报告是否导出 HTML。
            dry_run: 演练模式——collect/extract 只统计不写库，
                analyze 只读，report 与留档不落盘。
            extract_limit: extract 阶段最多处理条数。

        Returns:
            运行结果（含各阶段统计与 report 产物路径）。
        """
        run = PipelineRun(
            started_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            dry_run=dry_run,
        )

        # ① collect（源给定才跑）
        if announcements is not None:
            if dry_run:
                run.stages.append(
                    self._collect_dry(announcements)
                )
            else:
                run.stages.append(
                    run_collect_stage(self.db, announcements)
                )

        # ② extract（有源或库内有 pending 都跑；空库无源跳过）
        has_pending = bool(self.db.pending_raws(limit=1))
        if raw_texts is not None or has_pending:
            if dry_run:
                run.stages.append(
                    self._extract_dry(raw_texts, extract_limit)
                )
            else:
                run.stages.append(
                    run_extract_stage(
                        self.db, raw_texts, limit=extract_limit
                    )
                )

        # ③ analyze（只读——永远可跑）
        analyze_result = run_analyze_stage(
            self.db, keyword=keyword, days=days, region=region
        )
        run.stages.append(analyze_result)
        run.stats = (
            analyze_result.summary.get("stats") if analyze_result.ok else None
        )

        # ④ report（analyze 失败则跳过——无统计不伪造报告）
        if analyze_result.ok and not dry_run:
            run.stages.append(
                run_report_stage(
                    run.stats, self.output_dir, title=title, html=html
                )
            )
        elif analyze_result.ok and dry_run:
            run.stages.append(
                StageResult(
                    name="report",
                    ok=True,
                    summary={"skipped": "dry-run 不落盘"},
                )
            )

        # ⑤ 留档（正式运行）
        if not dry_run:
            self._archive(run)
        return run

    # ------------------------------------------------------------------
    # 演练模式内部
    # ------------------------------------------------------------------

    def _collect_dry(self, source: Path) -> StageResult:
        """collect 演练：装载 + 水位分类，不写库。"""
        start = time.monotonic()
        try:
            from src.collect import load_records
            from src.pipeline.stages import classify_against_db

            loaded = load_records(source, skip_invalid=True)
            classified = classify_against_db(loaded.records, self.db)
        except Exception as exc:  # noqa: BLE001
            return StageResult(
                "collect", False, int((time.monotonic() - start) * 1000),
                {}, f"源不可读: {exc}",
            )
        return StageResult(
            "collect", True, int((time.monotonic() - start) * 1000),
            {
                "files_read": loaded.files_read,
                "loaded": len(loaded.records),
                "new": len(classified["new"]),
                "update": len(classified["update"]),
                "skip_duplicate": len(classified["skip"]),
                "dry_run": True,
            },
        )

    def _extract_dry(
        self, source: Optional[Path], limit: Optional[int]
    ) -> StageResult:
        """extract 演练：装载统计 + pending 计数，不抽取不改状态。"""
        start = time.monotonic()
        summary: Dict[str, Any] = {"dry_run": True}
        if source is not None:
            try:
                from src.extract.runner import resolve_raw_files

                files = resolve_raw_files(source)
                summary["files_read"] = len(files)
                summary["new"] = sum(
                    1
                    for path in files
                    if not self.db.has_raw_content(
                        path.read_text(encoding="utf-8")
                    )
                )
            except Exception as exc:  # noqa: BLE001
                return StageResult(
                    "extract", False, int((time.monotonic() - start) * 1000),
                    summary, f"原文源不可读: {exc}",
                )
        summary["pending"] = len(self.db.pending_raws(limit=limit or 10**9))
        return StageResult(
            "extract", True, int((time.monotonic() - start) * 1000), summary
        )

    # ------------------------------------------------------------------
    # 留档
    # ------------------------------------------------------------------

    def _archive(self, run: PipelineRun) -> None:
        """把运行结果写入 pipeline_runs 表（阶段状态报告留档）。"""
        report_stage = run.stage("report")
        report_path = (
            report_stage.summary.get("markdown", "")
            if report_stage and report_stage.ok
            else ""
        )
        self.db._conn.execute(  # noqa: SLF001
            "INSERT INTO pipeline_runs"
            " (started_at, finished_at, ok, stages_json, dry_run, report_path)"
            " VALUES (?, ?, ?, ?, 0, ?)",
            (
                run.started_at,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                1 if run.all_ok else 0,
                json.dumps(run.to_dict(), ensure_ascii=False),
                report_path,
            ),
        )
        self.db._conn.commit()  # noqa: SLF001

    def run_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """查询最近 N 次运行留档（含阶段统计 JSON）。"""
        cursor = self.db._conn.execute(  # noqa: SLF001
            "SELECT * FROM pipeline_runs ORDER BY id DESC LIMIT ?",
            (limit,),
        )
        rows = []
        for row in cursor.fetchall():
            data = dict(row)
            try:
                data["stages"] = json.loads(data.pop("stages_json") or "[]")
            except json.JSONDecodeError:
                data["stages"] = []
            rows.append(data)
        return rows
