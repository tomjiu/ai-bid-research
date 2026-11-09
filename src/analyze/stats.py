"""统计面（#601 批次 C）——五维统计 + 汇总装配。

口径声明（研究结论须可复算——每个统计都写清分母与样本规则）：

* **金额分位**：仅计 ``budget`` 非空样本（``with_budget`` 为分母），
  分位数用线性插值（inclusive 口径，与 Excel PERCENTILE.INC 一致）；
* **区域分布**：``region`` 为空的样本归「未知」；按项目数降序，
  top-N 截断（默认 10）；
* **月度趋势**：仅计 ``publish_date`` 非空样本；按 ``YYYY-MM``
  聚合项目数与预算额；含环比（最近一月相对前一月）；
* **关键词频次**：对 ``project_name`` 计领域关键词命中数
  （一个项目可命中多个关键词——类目有重叠是诚实的）；
* **竞争密度**：以 ``awarded``（已定中标人）为分母计
  赢家集中度（CR1/CR3/HHI）；无已定标样本时集中度为 ``None``。

纯标准库，无 LLM/网络依赖。
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

from src.analyze.dataset import (
    DEFAULT_DOMAIN_KEYWORDS,
    BidDataset,
)

# ----------------------------------------------------------------------
# 金额分位
# ----------------------------------------------------------------------


def _percentile(sorted_values: List[float], pct: float) -> Optional[float]:
    """线性插值分位数（inclusive 口径）。

    Args:
        sorted_values: 升序样本。
        pct: 分位百分比（0-100）。

    Returns:
        分位值；空样本为 ``None``。
    """
    if not sorted_values:
        return None
    if len(sorted_values) == 1:
        return float(sorted_values[0])
    rank = (len(sorted_values) - 1) * pct / 100.0
    lower = math.floor(rank)
    upper = math.ceil(rank)
    if lower == upper:
        return float(sorted_values[int(rank)])
    frac = rank - lower
    return float(
        sorted_values[lower] * (1 - frac) + sorted_values[upper] * frac
    )


def budget_percentiles(ds: BidDataset) -> Dict[str, Any]:
    """预算金额分布（万元）。

    Args:
        ds: 分析数据集。

    Returns:
        含 ``count``（样本数）/ ``total`` / ``mean`` / ``min`` /
        ``p25`` / ``median`` / ``p75`` / ``max`` 的字典；
        空样本时各值为 ``None``/0（不伪造）。
    """
    values = sorted(ds.budget_values)
    if not values:
        return {
            "count": 0,
            "total": 0.0,
            "mean": None,
            "min": None,
            "p25": None,
            "median": None,
            "p75": None,
            "max": None,
        }
    return {
        "count": len(values),
        "total": round(sum(values), 2),
        "mean": round(sum(values) / len(values), 2),
        "min": values[0],
        "p25": round(_percentile(values, 25), 2),
        "median": round(_percentile(values, 50), 2),
        "p75": round(_percentile(values, 75), 2),
        "max": values[-1],
    }
