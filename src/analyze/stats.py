"""描述性统计（#601 批次 C 第 11 轮）。

产出纯 dict（JSON 可序列化）——批次 C 后续轮次直接喂给
ReportGenerator 的数据块，不引入自定义类型。

分位数口径：**最近邻秩位法**（nearest-rank，索引
``ceil(p*n)-1``）——不插值、结果必是观测值本身，研究面
可核对（「P90 = 480 万」是真实出现过的项目预算）。
"""

from __future__ import annotations

from collections import Counter
from typing import Dict, List, Optional

from src.analyze.dataset import AnalysisDataset

#: 未知区域的归一标签。
UNKNOWN_LABEL = "未知"

#: 预算摘要的分位口径。
_QUANTILES = (0.25, 0.50, 0.75, 0.90)


def _nearest_rank(sorted_values: List[float], q: float) -> Optional[float]:
    """最近邻秩位分位（q∈(0,1]）；空序列返回 None。"""
    if not sorted_values:
        return None
    import math

    rank = max(1, math.ceil(q * len(sorted_values)))
    return sorted_values[rank - 1]


def budget_summary(dataset: AnalysisDataset) -> Dict[str, Optional[float]]:
    """预算分布摘要（万元）。

    Args:
        dataset: 分析数据集。

    Returns:
        ``{"count", "total", "min", "max", "mean", "median",
        "p25", "p50", "p75", "p90"}``——空预算返回全 None
        （count 为 0），不猜数。
    """
    values = sorted(dataset.budgets)
    if not values:
        result: Dict[str, Optional[float]] = {
            "count": 0, "total": None, "min": None, "max": None,
            "mean": None, "median": None,
        }
        for q in _QUANTILES:
            result[f"p{int(q * 100)}"] = None
        return result
    total = sum(values)
    result = {
        "count": len(values),
        "total": total,
        "min": values[0],
        "max": values[-1],
        "mean": total / len(values),
        "median": _nearest_rank(values, 0.50),
    }
    for q in _QUANTILES:
        result[f"p{int(q * 100)}"] = _nearest_rank(values, q)
    return result


def region_distribution(
    dataset: AnalysisDataset, *, top: Optional[int] = None
) -> Dict[str, int]:
    """区域分布（降序计数）。

    Args:
        dataset: 分析数据集。
        top: 只保留前 N 位（其余并计 ``其他``）；``None`` = 全量。

    Returns:
        ``{区域: 条数}``（按条数降序）；无区域记录归 ``未知``。
    """
    counter: Counter = Counter()
    for record in dataset.records:
        region = (record.get("region") or "").strip()
        counter[region or UNKNOWN_LABEL] += 1
    items = sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))
    if top is not None and len(items) > top:
        kept = dict(items[:top])
        # 尾部合并为「其他」（与区域专名撞名属可接受边角，文档口径）
        kept["其他"] = sum(count for _, count in items[top:])
        return kept
    return dict(items)


def monthly_trend(dataset: AnalysisDataset) -> Dict[str, int]:
    """月度发布趋势（YYYY-MM 升序计数）。

    Args:
        dataset: 分析数据集。

    Returns:
        ``{"2026-08": 3, "2026-09": 5, ...}``；无日期返回空 dict。
    """
    counter: Counter = Counter(
        date.strftime("%Y-%m") for date in dataset.publish_dates
    )
    return dict(sorted(counter.items()))


def date_range(dataset: AnalysisDataset) -> Dict[str, Optional[int]]:
    """发布日期跨度。

    Args:
        dataset: 分析数据集。

    Returns:
        ``{"earliest", "latest", "span_days", "count"}``——
        earliest/latest 为 ``YYYY-MM-DD`` 字符串；空为 None。
    """
    dates = dataset.publish_dates
    if not dates:
        return {"earliest": None, "latest": None, "span_days": None, "count": 0}
    earliest, latest = dates[0], dates[-1]
    return {
        "earliest": earliest.strftime("%Y-%m-%d"),
        "latest": latest.strftime("%Y-%m-%d"),
        "span_days": (latest - earliest).days,
        "count": len(dates),
    }
