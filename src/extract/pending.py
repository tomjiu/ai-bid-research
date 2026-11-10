"""抽取降级面：pending 登记与重试（#601 批次 B 第 8 轮）。

设计说明
--------
「失败不能静默、也不能阻塞管道」：

- LLM 调用失败 / 校验拒收的公告进 ``pending_announcements``
  表（同件指纹幂等——反复跑管道不重复登记）；
- payload 存**可重放**的完整形态（``to_bid_row`` + extras +
  原文），重试时 ``AnnouncementRecord.from_raw`` 原样重建——
  不依赖调用方现场传参；
- ``retry_pending``：待处理面逐条重试（可指定重试的 extractor，
  换模型/换提示词后重跑即可），成功置 ``resolved``，失败更新
  error 保持 ``pending``。

原文流（无源记录）的身份锚点是**原文哈希**——公告没抽出
编号时，标题/日期/地区指纹无从计算，只能锚定原文本身。
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.collect.records import AnnouncementRecord
from src.extract.extractor import AnnouncementExtractor
from src.extract.store import (
    STATUS_REJECTED,
    STATUS_STORED,
    apply_extraction,
    apply_extraction_from_raw,
)
from src.storage.database import BidDatabase

#: 登记原因常量。
REASON_LLM_ERROR = "llm_error"
REASON_REJECTED = "rejected"

#: 状态常量（与 storage 层默认值对齐）。
STATUS_PENDING = "pending"
STATUS_RESOLVED = "resolved"
STATUS_SKIPPED = "skipped"


def raw_text_fingerprint(raw_text: str) -> str:
    """原文哈希指纹（原文流的身份锚点）。

    Args:
        raw_text: 公告原文。

    Returns:
        sha256 前 12 位十六进制（与记录指纹同长度口径）。
    """
    return hashlib.sha256(
        raw_text.strip().encode("utf-8")
    ).hexdigest()[:12]


def build_replay_payload(
    record: AnnouncementRecord, raw_text: Optional[str]
) -> Dict[str, Any]:
    """构造可重放载荷：重试时 from_raw 原样重建记录。

    Args:
        record: 规范化记录。
        raw_text: 公告原文（可为 ``None``）。

    Returns:
        载荷字典（规范字段 + extras + content 键）。
    """
    payload: Dict[str, Any] = record.to_bid_row()
    payload.update(record.extras)
    if raw_text:
        payload["content"] = raw_text
    return payload


def park_record_failure(
    db: BidDatabase,
    record: AnnouncementRecord,
    reason: str,
    *,
    raw_text: Optional[str] = None,
    error: Optional[str] = None,
    hit_rate: Optional[float] = None,
) -> int:
    """登记记录流失败（LLM 错误/校验拒收）到 pending 面。

    Args:
        db: 研究工作区数据库。
        record: 规范化记录（身份与载荷来源）。
        reason: 登记原因（``REASON_LLM_ERROR`` / ``REASON_REJECTED``）。
        raw_text: 公告原文（重试面需要）。
        error: 失败详情。
        hit_rate: 登记时命中率快照。

    Returns:
        受影响行数（1 成功登记/更新）。
    """
    return db.save_pending(
        record.fingerprint(),
        reason,
        bid_id=record.bid_id,
        raw_text=raw_text,
        payload=build_replay_payload(record, raw_text),
        error=error,
        hit_rate=hit_rate,
    )


def park_raw_failure(
    db: BidDatabase,
    raw_text: str,
    reason: str,
    *,
    bid_id: Optional[str] = None,
    error: Optional[str] = None,
    extracted_fields: Optional[Dict[str, Any]] = None,
    hit_rate: Optional[float] = None,
) -> int:
    """登记原文流失败（无源记录，身份锚定原文哈希）。

    Args:
        db: 研究工作区数据库。
        raw_text: 公告原文（身份锚点 + 重试面需要）。
        reason: 登记原因。
        bid_id: 已抽出的编号（可为 ``None``——缺编号是常见拒收因）。
        error: 失败详情。
        extracted_fields: 已抽出的部分字段（随载荷保留，不丢失）。

    Returns:
        受影响行数。
    """
    payload: Dict[str, Any] = {"content": raw_text}
    if extracted_fields:
        payload.update(extracted_fields)
    return db.save_pending(
        raw_text_fingerprint(raw_text),
        reason,
        bid_id=bid_id,
        raw_text=raw_text,
        payload=payload,
        error=error,
        hit_rate=hit_rate,
    )


@dataclass
class RetryReport:
    """一次重试的报告。

    Attributes:
        attempted: 实际重试条数。
        resolved: 成功（入库 + 置 resolved）条数。
        still_pending: 仍失败（保持 pending，error 已更新）条数。
        skipped_rebuild: 载荷损坏无法重建而跳过的条数。
    """

    attempted: int = 0
    resolved: int = 0
    still_pending: int = 0
    skipped_rebuild: int = 0
    details: List[Dict[str, str]] = field(default_factory=list)


def retry_pending(
    db: BidDatabase,
    extractor: AnnouncementExtractor,
    *,
    limit: Optional[int] = None,
) -> RetryReport:
    """重试 pending 面的全部待处理公告（同步驱动异步 extract）。

    Args:
        db: 研究工作区数据库。
        extractor: 抽取器（可换模型/提示词后的新实例）。
        limit: 最多重试条数（``None`` = 全部）——**优先序消费**
            （R61）：llm_error 且 hit_rate 高者先重试，有限预算
            先烧最有希望的。

    Returns:
        重试报告（resolved / still_pending / skipped_rebuild）。

    Note:
        逐条 ``asyncio.run`` 驱动——pending 面是降级队列，
        量级小（正常管道 <5%），不值得常驻事件循环。
    """
    import asyncio

    report = RetryReport()
    rows = db.list_pending(
        status=STATUS_PENDING, limit=limit or 1000, order="priority"
    )
    for row in rows:
        fingerprint = row["fingerprint"]
        raw_text = row.get("raw_text")
        payload = row.get("payload")
        is_record_flow = bool(row.get("bid_id"))

        record: Optional[AnnouncementRecord]
        if is_record_flow:
            # 记录流：载荷原样重建（损坏载荷跳过不炸——#563 口径）
            record = None
            if isinstance(payload, dict):
                try:
                    record = AnnouncementRecord.from_raw(payload)
                except (ValueError, TypeError):
                    record = None
            if record is None:
                report.attempted += 1
                report.skipped_rebuild += 1
                db.update_pending_status(
                    fingerprint, STATUS_PENDING, error="载荷损坏，无法重建记录"
                )
                report.details.append(
                    {"fingerprint": fingerprint, "result": "载荷损坏"}
                )
                continue
        else:
            # 原文流：无源记录——伪锚点记录仅承载原文（锚点不入库，
            # apply_extraction_from_raw 以 LLM 抽出的字段为准）
            if not raw_text:
                report.attempted += 1
                report.still_pending += 1
                db.update_pending_status(
                    fingerprint, STATUS_PENDING, error="无原文可重试"
                )
                report.details.append(
                    {"fingerprint": fingerprint, "result": "无原文可重试"}
                )
                continue
            record = AnnouncementRecord.from_raw(
                {
                    "bid_id": f"pending-{fingerprint}",
                    "project_name": "（重试中的待抽取公告）",
                    "content": raw_text,
                }
            )

        try:
            outcome = asyncio.run(extractor.extract(record, raw_text))
        except Exception as exc:  # ExtractionError / 网络——降级面不炸
            report.attempted += 1
            report.still_pending += 1
            db.update_pending_status(
                fingerprint, STATUS_PENDING, error=str(exc)
            )
            report.details.append(
                {"fingerprint": fingerprint, "result": f"重试失败: {exc}"}
            )
            continue

        if is_record_flow:
            store_outcome = apply_extraction(
                db, outcome, record.to_bid_row()
            )
        else:
            store_outcome = apply_extraction_from_raw(db, outcome)

        report.attempted += 1
        if store_outcome.status == STATUS_STORED:
            report.resolved += 1
            db.update_pending_status(fingerprint, STATUS_RESOLVED)
            report.details.append(
                {"fingerprint": fingerprint, "result": "已入库并置 resolved"}
            )
        else:
            report.still_pending += 1
            db.update_pending_status(
                fingerprint,
                STATUS_PENDING,
                error="重试后仍缺必填字段: "
                + ",".join(store_outcome.missing_required),
            )
            report.details.append(
                {"fingerprint": fingerprint, "result": "仍拒收（缺必填）"}
            )
    return report
