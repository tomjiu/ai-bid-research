"""管道编排核心（#601 批次 D 第 16 轮）。

四阶段串联::

    collect  —— 装载源 → 去重 → upsert 入库（新/更新分开计数）
    extract  —— 需要时对「新公告」做 LLM 结构化抽取（可跳过/离线）
    analyze  —— 数据集 → 全分析面 payload
    report   —— 纯数据报告落盘

设计口径：

- **阶段可空转**（source=None 只跑 analyze+report；client=None
  跳过 extract）——``StageResult.status`` 如实记录
  ``ok``/``skipped``/``empty``，绝不静默；
- **新/更新分开计**：``collect`` 阶段对每条记录先查后写，
  truly-new（库中无此 bid_id）与 update（已有，幂等覆盖）分账
  ——这是增量抽取（第 17 轮）与「采集了多少新公告」研究口径的基础；
- 失败不炸管道：collect 坏文件登记 failures；extract 失败进
  pending 面（既有降级链路）；空数据集让 report 渲染缺口节。
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from src.collect import dedupe_records, load_records
from src.extract import (
    REASON_LLM_ERROR,
    AnnouncementExtractor,
    STATUS_STORED,
    apply_extraction,
    park_record_failure,
)
from src.analyze import build_analysis_payload, load_dataset
from src.collect.sources import SourceError
from src.report.generator import ReportGenerator
from src.storage.database import BidDatabase

#: 阶段状态常量。
STAGE_OK = "ok"
STAGE_SKIPPED = "skipped"
STAGE_EMPTY = "empty"


@dataclass
class StageResult:
    """单阶段执行结果。

    Attributes:
        name: 阶段名（collect/extract/analyze/report）。
        status: ``ok`` / ``skipped`` / ``empty``。
        detail: 阶段统计（各阶段自定义键）。
        failures: 阶段内已登记的失败明细（origin/error 对）。
    """

    name: str
    status: str
    detail: Dict[str, Any] = field(default_factory=dict)
    failures: List[Dict[str, str]] = field(default_factory=list)


@dataclass
class PipelineResult:
    """一次管道运行的全结果。

    Attributes:
        stages: 各阶段结果（按执行顺序）。
        report_path: 报告文件路径（report 阶段产出）。
        payload: 分析 payload（analyze 阶段产出——调用方可续用）。
    """

    stages: List[StageResult] = field(default_factory=list)
    report_path: Optional[Path] = None
    payload: Optional[Dict[str, Any]] = None
    run_id: Optional[int] = None  # pipeline_runs 台账行（审计可溯）

    def stage(self, name: str) -> Optional[StageResult]:
        """按阶段名取结果。"""
        for item in self.stages:
            if item.name == name:
                return item
        return None


class ResearchPipeline:
    """研究管道编排器。

    Attributes:
        db_path: 研究工作区数据库路径。
        extractor: 抽取器（``None`` = extract 阶段跳过）。
        output_dir: 报告输出目录。
    """

    def __init__(
        self,
        db_path: Union[str, Path],
        *,
        extractor: Optional[AnnouncementExtractor] = None,
        output_dir: Union[str, Path] = "output/reports",
    ) -> None:
        """初始化管道。

        Args:
            db_path: 数据库路径（不存在自动建库）。
            extractor: 抽取器实例；``None`` 跳过抽取阶段。
            output_dir: 报告输出目录。
        """
        self.db_path = Path(db_path)
        self.extractor = extractor
        self.output_dir = Path(output_dir)

    # ------------------------------------------------------------------
    # 编排入口
    # ------------------------------------------------------------------

    def run(
        self,
        source: Optional[Union[str, Path]] = None,
        *,
        keyword: Optional[str] = None,
        days: Optional[int] = None,
        html: bool = False,
        incremental: bool = False,
    ) -> PipelineResult:
        """运行研究管道（同步编排；extract 内部异步由批次 B 收口）。

        Args:
            source: 公告源（``None`` = 跳过 collect，只分析既有库）。
            keyword: 分析/报告口径关键词。
            days: 分析/报告时间窗口。
            html: 报告落盘后同时导出 HTML。
            incremental: 增量模式——collect 只读 mtime 晚于上次
                成功运行的新文件（水位来自 pipeline_runs 台账）；
                首次运行无水位 = 全量。

        Returns:
            管道结果（stages/payload/report_path）。

        Note:
            抽取面只处理 collect 产出的**新公告**（已入库公告不重复
            消耗 API——补抽走 extract --source / --retry 单命令面）。

        Raises:
            SourceError: source 指定但不可读（collect 阶段硬错——
                管道起步失败没有「继续跑」的语义）。
        """
        import time as _time
        from datetime import datetime

        started_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        watermark = _time.time()  # 亚秒精度——与文件 mtime 同口径
        with BidDatabase(self.db_path) as db:
            run_id = db.pipeline_runs_save(
                started_at, source=str(source) if source else None,
                keyword=keyword, days=days, watermark=watermark,
            )
            last_run = db.pipeline_runs_last(status="done")

        since: Optional[float] = None
        if incremental and last_run is not None:
            value = last_run.get("watermark")
            since = value if isinstance(value, (int, float)) else None
            # 水位缺失/损坏 → 退化为全量（不炸管道）

        try:
            result = self._run_stages(
                source, keyword=keyword, days=days, html=html, since=since
            )
        except Exception:
            with BidDatabase(self.db_path) as db:
                db.pipeline_runs_finish(run_id, status="failed")
            raise

        with BidDatabase(self.db_path) as db:
            db.pipeline_runs_finish(
                run_id,
                stages=[
                    {
                        "name": s.name,
                        "status": s.status,
                        "detail": s.detail,
                        "failures": s.failures,
                    }
                    for s in result.stages
                ],
                report_path=str(result.report_path)
                if result.report_path
                else None,
            )
        result.run_id = run_id
        return result

    def _run_stages(
        self,
        source,
        *,
        keyword,
        days,
        html,
        since: Optional[float],
    ) -> PipelineResult:
        result = PipelineResult()

        new_records: List[Any] = []
        if source is not None:
            new_records, collect_stage = self._stage_collect(source, since=since)
            result.stages.append(collect_stage)
        else:
            result.stages.append(
                StageResult(
                    name="collect",
                    status=STAGE_SKIPPED,
                    detail={"reason": "未指定 --source"},
                )
            )

        if self.extractor is not None and new_records:
            result.stages.append(self._stage_extract(new_records))
        else:
            result.stages.append(
                StageResult(
                    name="extract",
                    status=STAGE_SKIPPED,
                    detail={
                        "reason": (
                            "无新公告" if not new_records
                            else "未配置抽取器（离线模式）"
                        )
                    },
                )
            )

        payload_stage, payload = self._stage_analyze(keyword, days)
        result.stages.append(payload_stage)
        result.payload = payload

        report_stage, report_path = self._stage_report(
            payload, keyword, html=html
        )
        result.stages.append(report_stage)
        result.report_path = report_path
        return result

    # ------------------------------------------------------------------
    # 各阶段
    # ------------------------------------------------------------------

    def _stage_collect(self, source, *, since: Optional[float] = None) -> tuple:
        """collect 阶段：装载（可水位增量）→ 去重 → 新/更新分账 upsert。"""
        loaded = load_records(source, since=since)  # SourceError 直抛
        deduped = dedupe_records(loaded.records)

        new_records: List[Any] = []
        updated_count = 0
        with BidDatabase(self.db_path) as db:
            for record in deduped.unique:
                if db.get_bid(record.bid_id) is None:
                    new_records.append(record)
                    db.save_bid(record.to_bid_row())
                else:
                    db.save_bid(record.to_bid_row())  # 幂等覆盖（可能带新字段）
                    updated_count += 1

        stage = StageResult(
            name="collect",
            status=STAGE_OK,
            detail={
                "files_read": loaded.files_read,
                "loaded": len(loaded.records),
                "deduped": deduped.removed,
                "new": len(new_records),
                "updated": updated_count,
            },
            failures=list(loaded.failures),
        )
        return new_records, stage

    def _stage_extract(self, records) -> StageResult:
        """extract 阶段：对新公告做 LLM 抽取（失败进 pending 降级面）。"""
        batch = asyncio.run(self.extractor.extract_batch(records))
        stored = 0
        parked = 0
        with BidDatabase(self.db_path) as db:
            record_map = {r.bid_id: r for r in records}
            for outcome in batch.outcomes:
                record = record_map.get(outcome.bid_id)
                if record is None:
                    continue
                store_outcome = apply_extraction(
                    db, outcome, record.to_bid_row()
                )
                if store_outcome.status == STATUS_STORED:
                    stored += 1
            for failure in batch.failures:
                record = record_map.get(failure["bid_id"])
                if record is not None:
                    park_record_failure(
                        db,
                        record,
                        REASON_LLM_ERROR,
                        raw_text=(
                            record.extras.get("content")
                            or record.extras.get("公告原文")
                        ),
                        error=failure["error"],
                    )
                    parked += 1
        return StageResult(
            name="extract",
            status=STAGE_OK,
            detail={
                "extracted": len(batch.outcomes),
                "stored": stored,
                "llm_failures": len(batch.failures),
                "parked": parked,
            },
        )

    def _stage_analyze(
        self, keyword: Optional[str], days: Optional[int]
    ) -> tuple:
        """analyze 阶段：数据集 + payload。"""
        dataset = load_dataset(self.db_path, keyword=keyword, days=days)
        payload = build_analysis_payload(dataset, keyword=keyword, days=days)
        stage = StageResult(
            name="analyze",
            status=STAGE_OK if len(dataset) else STAGE_EMPTY,
            detail={
                "records": len(dataset),
                "complete_rate": payload["complete_rate"],
            },
        )
        return stage, payload

    def _stage_report(
        self, payload: Dict[str, Any], keyword: Optional[str], *, html: bool
    ) -> tuple:
        """report 阶段：报告落盘（+可选 HTML）。"""
        generator = ReportGenerator(output_dir=self.output_dir)
        report_path = generator.generate_analysis_report(payload)
        if html:
            html_path = generator.export_html(report_path)
            payload["_html_path"] = str(html_path)  # 内部续用键
        stage = StageResult(
            name="report",
            status=STAGE_OK,
            detail={"path": str(report_path), "html": html},
        )
        return stage, report_path
