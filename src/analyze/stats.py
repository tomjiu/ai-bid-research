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

#: 预算分桶（万元，研究经验口径——左闭右开；末桶无上界，R36）。
BUDGET_BUCKETS = (
    (0.0, 100.0, "0-100万"),
    (100.0, 500.0, "100-500万"),
    (500.0, 1000.0, "500-1000万"),
    (1000.0, 5000.0, "1000-5000万"),
    (5000.0, None, "5000万+"),
)

#: 预算未知桶标签（budget 为 None 的记录——数据缺口如实可见）。
BUDGET_UNKNOWN_LABEL = "预算未知"


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


def budget_bucket_label(budget: Optional[float]) -> str:
    """预算 → 分桶标签（None → 预算未知，R36）。

    Args:
        budget: 预算（万元）。

    Returns:
        桶标签（左闭右开口径；负值理论上被归一面拦截，
        兑底落入首桶）。"""
    if budget is None:
        return BUDGET_UNKNOWN_LABEL
    for low, high, label in BUDGET_BUCKETS:
        if budget >= low and (high is None or budget < high):
            return label
    return BUDGET_BUCKETS[0][2]


def budget_region_crosstab(
    dataset: AnalysisDataset, *, top_regions: int = 8
) -> Dict[str, Dict[str, int]]:
    """预算 × 区域交叉计数（描述性统计，R36）。

    Args:
        dataset: 分析数据集。
        top_regions: 展示区域数上限（计数降序，并列按名称——确定性；
            「未知」区域若有记录且未进前列则末位附加——数据缺口可见）。

    Returns:
        ``{区域: {桶标签: 计数}}``——行=区域、列=预算桶
        （含「预算未知」，稠密矩阵：缺席桶补 0）；
        空集返回 ``{}``（不猜数）。
    """
    matrix: Dict[str, Counter] = {}
    region_counts: Counter = Counter()
    for record in dataset.records:
        region = (record.get("region") or "").strip() or UNKNOWN_LABEL
        region_counts[region] += 1
        bucket = budget_bucket_label(record.get("budget"))
        matrix.setdefault(region, Counter())[bucket] += 1

    if not region_counts:
        return {}

    ordered = [
        name
        for name, _ in sorted(
            region_counts.items(), key=lambda kv: (-kv[1], kv[0])
        )
    ]
    top = ordered[:top_regions]
    if UNKNOWN_LABEL in region_counts and UNKNOWN_LABEL not in top:
        top.append(UNKNOWN_LABEL)

    bucket_labels = [label for _, _, label in BUDGET_BUCKETS] + [
        BUDGET_UNKNOWN_LABEL
    ]
    result: Dict[str, Dict[str, int]] = {}
    for region in top:
        counter = matrix[region]
        result[region] = {
            label: counter.get(label, 0) for label in bucket_labels
        }
    return result
