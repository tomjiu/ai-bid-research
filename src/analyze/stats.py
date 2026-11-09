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


# ----------------------------------------------------------------------
# 区域分布
# ----------------------------------------------------------------------


def region_distribution(
    ds: BidDataset, *, top_n: int = 10
) -> Dict[str, Any]:
    """区域分布：按项目数降序的 top-N 地区。

    Args:
        ds: 分析数据集。
        top_n: 返回前 N 个地区（默认 10）。

    Returns:
        含 ``regions``（列表，每项 ``name`` / ``count`` / ``budget_total``
        / ``awarded``——预算合计仅计非空样本）/ ``unique_regions``
        / ``unknown_count``（region 为空样本数）。
    """
    groups: Dict[str, Dict[str, Any]] = {}
    unknown = 0
    for record in ds.records:
        region = record.get("region")
        if not region:
            unknown += 1
            continue
        bucket = groups.setdefault(
            region, {"count": 0, "budget_total": 0.0, "awarded": 0}
        )
        bucket["count"] += 1
        if record.get("budget") is not None:
            bucket["budget_total"] += float(record["budget"])
        if record.get("winner"):
            bucket["awarded"] += 1

    ranked = sorted(
        groups.items(), key=lambda kv: (-kv[1]["count"], kv[0])
    )[:top_n]
    return {
        "regions": [
            {
                "name": name,
                "count": data["count"],
                "budget_total": round(data["budget_total"], 2),
                "awarded": data["awarded"],
            }
            for name, data in ranked
        ],
        "unique_regions": len(groups),
        "unknown_count": unknown,
    }


# ----------------------------------------------------------------------
# 月度趋势
# ----------------------------------------------------------------------


def monthly_trend(ds: BidDataset) -> Dict[str, Any]:
    """月度趋势：按发布月聚合项目数与预算额（时间升序）。

    Args:
        ds: 分析数据集。

    Returns:
        含 ``months``（列表，每项 ``month`` (``YYYY-MM``) / ``count`` /
        ``budget_total``）/ ``mom_change``（最近一月项目数环比 %；
        不足两月为 ``None``）/ ``with_date``（有日期样本数）。
    """
    groups: Dict[str, Dict[str, Any]] = {}
    for record in ds.records:
        month = (record.get("publish_date") or "")[:7]
        if len(month) != 7:
            continue  # 无日期样本不进趋势（口径：趋势分母 = with_date）
        bucket = groups.setdefault(
            month, {"count": 0, "budget_total": 0.0}
        )
        bucket["count"] += 1
        if record.get("budget") is not None:
            bucket["budget_total"] += float(record["budget"])

    ordered = sorted(groups.items())
    months = [
        {
            "month": month,
            "count": data["count"],
            "budget_total": round(data["budget_total"], 2),
        }
        for month, data in ordered
    ]
    mom: Optional[float] = None
    if len(months) >= 2:
        prev, curr = months[-2]["count"], months[-1]["count"]
        if prev > 0:
            mom = round((curr - prev) / prev * 100, 1)
    return {"months": months, "mom_change": mom, "with_date": ds.with_date}
