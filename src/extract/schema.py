"""抽取结果 schema 校验（#601 批次 B·R5）。

LLM（或规则基线）输出的结构化载荷在入库前必须过校验：

* **载荷形态**——必须是 JSON 对象（dict）；
* **必填字段**——``bid_id`` / ``project_name``（容忍中文别名，与
  采集面 :meth:`AnnouncementRecord.from_raw` 同一套别名表）；
* **日期**——归一为 ``YYYY-MM-DD``，无法解析置 ``None``（诚实降级，
  记入记录 ``warnings``，不伪造）；
* **金额**——归一为万元口径 float（采集面同款单位归一）。

校验通过 → 返回 :class:`AnnouncementRecord`（直接可
``to_bid_row`` → ``BidDatabase.save_bid`` 幂等回写）；
校验失败 → 抛 :class:`ExtractionSchemaError`（调用方决定降级路径：
原文留在 raw 暂存面 + pending 标记，不阻塞管道）。

设计上**不重复造轮子**：字段别名/清洗/必填校验全部复用采集面的
``AnnouncementRecord.from_raw``——抽取面只是给它包一层
「LLM 载荷语义」的异常类型与诊断信息。
"""

from __future__ import annotations

from typing import Any, Dict

from src.collect.records import (
    AnnouncementRecord,
    RecordValidationError,
)

#: LLM 抽取载荷中允许出现的规范字段（超出部分进 ``extras``，不入库）。
EXPECTED_FIELDS = (
    "bid_id",
    "project_name",
    "budget",
    "publish_date",
    "deadline",
    "region",
    "purchaser",
    "agency",
    "category",
    "requirements",
)


class ExtractionSchemaError(ValueError):
    """抽取载荷未通过 schema 校验。"""

    def __init__(self, reason: str, *, field: str = "") -> None:
        """初始化。

        Args:
            reason: 人读失败原因（含原值摘要）。
            field: 相关字段名（可空——载荷级错误时无单一字段）。
        """
        super().__init__(reason)
        self.reason = reason
        self.field = field


def validate_extraction(payload: Any) -> AnnouncementRecord:
    """校验并规范化一条 LLM 抽取载荷。

    Args:
        payload: 抽取产物（必须是 dict；其他类型直接判 schema 错）。

    Returns:
        规范化记录（含清洗 ``warnings``，调用方可透传到日志）。

    Raises:
        ExtractionSchemaError: 载荷非 dict、缺必填字段、或字段值
            形态非法（来自 :class:`RecordValidationError` 的包装）。
    """
    if not isinstance(payload, dict):
        raise ExtractionSchemaError(
            f"抽取载荷必须是 JSON 对象，实际为 {type(payload).__name__}"
        )
    if not payload:
        raise ExtractionSchemaError("抽取载荷为空对象，无任何字段")

    try:
        record = AnnouncementRecord.from_raw(payload)
    except RecordValidationError as exc:
        raise ExtractionSchemaError(
            f"必填字段校验失败: {exc.field}——{exc.reason}",
            field=exc.field,
        ) from exc
    except TypeError as exc:
        raise ExtractionSchemaError(f"载荷形态非法: {exc}") from exc

    # 记录级诊断：全部必填在、但关键值全空（如 bid_id 仅由空白构成
    # 的情况已由 from_raw 拒绝；这里补「必填字段值为 null」的显式诊断）
    if record.bid_id is None or record.project_name is None:  # pragma: no cover
        raise ExtractionSchemaError("必填字段为 null（不可能路径，防御）")

    return record


def summarize_validation(record: AnnouncementRecord) -> Dict[str, Any]:
    """生成校验摘要（CLI/日志用——一眼看全清洗降级情况）。

    Args:
        record: 已通过校验的记录。

    Returns:
        含 ``ok`` / ``warnings`` / ``filled_fields`` / ``extras`` 的摘要。
    """
    filled = [
        name
        for name in EXPECTED_FIELDS
        if getattr(record, name, None)
        not in (None, "", [])
    ]
    return {
        "ok": True,
        "bid_id": record.bid_id,
        "warnings": list(record.warnings),
        "filled_fields": filled,
        "missing_fields": [
            name for name in EXPECTED_FIELDS if name not in filled
        ],
        "extras": sorted(record.extras.keys()),
    }
