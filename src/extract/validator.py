"""抽取结果校验与完整度度量（#601 批次 B 第 6 轮）。

设计说明
--------
抽取出的字段要回答两个问题：

1. **值得入库吗？**——``bid_id`` + ``project_name`` 是 bids 表
   硬约束（save_bid 的必填面）；缺任一则该条只能进 pending/
   降级面（批次 B 第 8 轮），不能半截进库。
2. **质量如何？**——12 个规范字段的**命中率**
   （:attr:`ValidationResult.hit_rate`）是抽取质量的可量化口径：
   直通模式稀疏记录命中率天然低（正常——源就是稀疏的），
   LLM 模式低命中率则提示原文质量/提示词需要复查。
   该指标在批次 F「抽取质量评估面」直接复用。

「推荐字段」缺失（publish_date/budget 等）**不判无效**——
公告本身可以不写预算（面议），研究管道不该因此拒收。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

#: bids 表硬约束字段（save_bid 必填面）。
REQUIRED_FIELDS = ("bid_id", "project_name")

#: 研究分析强依赖字段（缺失不拒收，仅告警——公告可不写）。
RECOMMENDED_FIELDS = (
    "publish_date",
    "budget",
    "deadline",
    "region",
    "requirements",
)

#: 完整度分母：全部规范业务字段（不含 created_at 等元数据列）。
#: 公共常量（#601 批次 E：字段级质量评估面共用）。
ALL_FIELDS = (
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


def is_filled(value: Any) -> bool:
    """字段「已填」判定：非 None/非空串/非空列表。

    公共谓词（#601 批次 E：字段级质量评估面共用）。
    """
    if value is None:
        return False
    if isinstance(value, str) and not value.strip():
        return False
    if isinstance(value, (list, dict)) and not value:
        return False
    return True


@dataclass
class ValidationResult:
    """字段校验结果。

    Attributes:
        valid: 必填字段是否齐全（能否入库）。
        missing_required: 缺失的必填字段（拒收原因）。
        missing_recommended: 缺失的推荐字段（告警）。
        hit_rate: 12 个规范字段的命中率（0.0-1.0）。
        filled_fields: 已填字段名列表（质量评估面用）。
    """

    valid: bool
    missing_required: List[str] = field(default_factory=list)
    missing_recommended: List[str] = field(default_factory=list)
    hit_rate: float = 0.0
    filled_fields: List[str] = field(default_factory=list)


def validate_fields(fields: Dict[str, Any]) -> ValidationResult:
    """校验抽取/合并后的字段集合。

    Args:
        fields: 字段字典（建议已过归一——直通或 LLM 输出皆可）。

    Returns:
        校验结果（valid / 缺失清单 / 命中率）。
    """
    filled = [name for name in ALL_FIELDS if is_filled(fields.get(name))]
    missing_required = [
        name for name in REQUIRED_FIELDS if not is_filled(fields.get(name))
    ]
    missing_recommended = [
        name
        for name in RECOMMENDED_FIELDS
        if not is_filled(fields.get(name))
    ]
    hit_rate = len(filled) / len(ALL_FIELDS)
    return ValidationResult(
        valid=not missing_required,
        missing_required=missing_required,
        missing_recommended=missing_recommended,
        hit_rate=hit_rate,
        filled_fields=filled,
    )
