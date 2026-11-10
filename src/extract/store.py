"""抽取结果入库管道（#601 批次 B 第 7 轮）。

设计说明
--------
把 ``ExtractionOutcome`` 落进 bids 表的两条路：

1. **记录流**（apply_extraction）：源记录 + 抽取结果 →
   ``merge_fields``（补全不覆盖）→ ``validate_fields`` →
   ``save_bid`` upsert。源记录必填字段恒在，校验是防御面
   （合并策略或上游语义变化时的安全网，拒收不静默）。
2. **原文流**（apply_extraction_from_raw）：无结构化源记录，
   LLM 抽取字段即全部——公告没有招标编号时**不合成伪编号**
   （合成会污染 dedup 面的 bid_id 身份锚点），拒收并给出
   缺失清单，由调用方路由到 pending 面（第 8 轮）等人工/重试。

入库走 ``save_bid`` 幂等 upsert（按 bid_id），重复运行管道
不产生重复行——与 collect 面同一纪律。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.extract.extractor import (
    BatchExtractionResult,
    ExtractionOutcome,
    merge_fields,
)
from src.extract.validator import validate_fields
from src.storage.database import BidDatabase

#: 入库状态常量。
STATUS_STORED = "stored"
STATUS_REJECTED = "rejected"


@dataclass
class StoreOutcome:
    """单条入库结果。

    Attributes:
        status: ``stored``（已 upsert）/ ``rejected``（拒收）。
        bid_id: 记录锚点（拒收时可能为 ``None``——原文流缺编号）。
        hit_rate: 合并后字段的命中率（质量面）。
        used_llm: 该条是否发生真实 LLM 调用。
        saved: save_bid 受影响行数（拒收时为 0）。
        missing_required: 拒收时的必填缺失清单（人读原因）。
    """

    status: str
    bid_id: Optional[str] = None
    hit_rate: float = 0.0
    used_llm: bool = False
    saved: int = 0
    missing_required: List[str] = field(default_factory=list)


@dataclass
class BatchStoreResult:
    """一批入库结果汇总。

    Attributes:
        outcomes: 每条的入库结果（与输入顺序一致）。
    """

    outcomes: List[StoreOutcome] = field(default_factory=list)

    @property
    def stored(self) -> int:
        """入库成功条数。"""
        return sum(1 for o in self.outcomes if o.status == STATUS_STORED)

    @property
    def rejected(self) -> int:
        """拒收条数。"""
        return sum(1 for o in self.outcomes if o.status == STATUS_REJECTED)

    @property
    def llm_used(self) -> int:
        """真实 LLM 调用条数。"""
        return sum(1 for o in self.outcomes if o.used_llm)


def _row_from_fields(fields: Dict[str, Any]) -> Dict[str, Any]:
    """构造 save_bid 兼容行（requirements 列表保留——save_bid 序列化）。"""
    row = {
        "bid_id": fields.get("bid_id"),
        "project_name": fields.get("project_name"),
        "region": fields.get("region"),
        "budget": fields.get("budget"),
        "publish_date": fields.get("publish_date"),
        "deadline": fields.get("deadline"),
        "category": fields.get("category"),
        "purchaser": fields.get("purchaser"),
        "agency": fields.get("agency"),
        "winner": fields.get("winner"),
        "source_url": fields.get("source_url"),
        "requirements": fields.get("requirements") or [],
    }
    return row


def apply_extraction(
    db: BidDatabase,
    outcome: ExtractionOutcome,
    record_fields: Dict[str, Any],
) -> StoreOutcome:
    """记录流入库：合并（补全不覆盖）→ 校验 → upsert。

    Args:
        db: 目标数据库。
        outcome: 抽取结果。
        record_fields: 源记录字段（:meth:`AnnouncementRecord.to_bid_row`
            产物）。

    Returns:
        入库结果（stored/rejected + 质量指标）。
    """
    merged = merge_fields(record_fields, outcome.fields)
    validation = validate_fields(merged)
    if not validation.valid:
        return StoreOutcome(
            status=STATUS_REJECTED,
            bid_id=merged.get("bid_id"),
            used_llm=outcome.used_llm,
            missing_required=validation.missing_required,
        )
    saved = db.save_bid(_row_from_fields(merged))
    # R58：抽取完成标记 + 同记录 pending 自动清账（续跑闭环）
    bid_id = merged.get("bid_id")
    db.set_extract_status(bid_id, "extracted")
    db.resolve_pending_by_bid(bid_id)
    return StoreOutcome(
        status=STATUS_STORED,
        bid_id=bid_id,
        hit_rate=validation.hit_rate,
        used_llm=outcome.used_llm,
        saved=saved,
    )


def apply_extraction_from_raw(
    db: BidDatabase,
    outcome: ExtractionOutcome,
) -> StoreOutcome:
    """原文流入库：抽取字段即全部（无结构化源记录）。

    缺招标编号时拒收（不合成伪编号——保护 dedup 身份锚点），
    拒收明细供调用方登记 pending 面。

    Args:
        db: 目标数据库。
        outcome: 抽取结果（fields 为唯一字段来源）。

    Returns:
        入库结果。
    """
    fields = outcome.fields
    validation = validate_fields(fields)
    if not validation.valid:
        return StoreOutcome(
            status=STATUS_REJECTED,
            bid_id=fields.get("bid_id"),
            used_llm=outcome.used_llm,
            missing_required=validation.missing_required,
        )
    saved = db.save_bid(_row_from_fields(fields))
    return StoreOutcome(
        status=STATUS_STORED,
        bid_id=fields.get("bid_id"),
        hit_rate=validation.hit_rate,
        used_llm=outcome.used_llm,
        saved=saved,
    )


def apply_extraction_batch(
    db: BidDatabase,
    batch: BatchExtractionResult,
    records_fields: Optional[List[Dict[str, Any]]] = None,
) -> BatchStoreResult:
    """批量入库：outcome 顺序与 records_fields 一一对应（记录流）。

    Args:
        db: 目标数据库。
        batch: 批量抽取结果。
        records_fields: 每条记录的源字段（记录流）；
            ``None`` 时走原文流（抽取字段即全部）。

    Returns:
        批量入库汇总。

    Raises:
        ValueError: records_fields 长度与 outcomes 不一致时。
    """
    if records_fields is not None and len(records_fields) != len(batch.outcomes):
        raise ValueError(
            f"records_fields 长度 {len(records_fields)} 与 outcomes "
            f"长度 {len(batch.outcomes)} 不一致"
        )
    result = BatchStoreResult()
    for index, outcome in enumerate(batch.outcomes):
        if records_fields is not None:
            store_outcome = apply_extraction(db, outcome, records_fields[index])
        else:
            store_outcome = apply_extraction_from_raw(db, outcome)
        result.outcomes.append(store_outcome)
    return result
