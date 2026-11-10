"""预算异常值检测（非生产链路——仅供研究，见 docs/PYTHON-BOUNDARY.md）。

R49：IQR（四分位距）围栏法识别预算离群记录——**描述性标记**，
不删除、不修正：

- 只统计有预算样本（缺失不折零），样本 < 5 时无统计意义，
  返回空结果并说明原因（不猜数）；
- 上围栏外（疑似高价）/下围栏外（疑似低价/万元口径嫌疑）分开
  列出，各带预算值与项目名；
- 围栏系数 1.5 为经典口径（Tukey），调用方可调。
"""

from __future__ import annotations

from typing import Any, Dict, List

from src.analyze.dataset import AnalysisDataset


def _percentile(sorted_values: List[float], q: float) -> float:
    """线性插值分位数（与 statistics.quantiles 默认一致）。"""
    if not sorted_values:
        raise ValueError("空样本无分位数")
    if len(sorted_values) == 1:
        return sorted_values[0]
    pos = q * (len(sorted_values) - 1)
    lower = int(pos)
    upper = min(lower + 1, len(sorted_values) - 1)
    frac = pos - lower
    return sorted_values[lower] * (1 - frac) + sorted_values[upper] * frac


def budget_outliers(
    dataset: AnalysisDataset, *, factor: float = 1.5
) -> Dict[str, Any]:
    """IQR 围栏法预算离群检测。

    Args:
        dataset: 分析数据集。
        factor: 围栏系数（1.5 = Tukey 经典；3.0 = 极端离群）。

    Returns:
        JSON 可序列化结果：

        - ``sample_count``：有预算样本数（<5 时检测跳过，
          ``skipped_reason`` 说明）；
        - ``q1`` / ``median`` / ``q3`` / ``iqr``：分布锚点；
        - ``lower_fence`` / ``upper_fence``：围栏值；
        - ``high`` / ``low``：离群记录列表（``bid_id`` /
          ``project_name`` / ``budget``），各按偏离围栏距离降序。
    """
    samples: List[Dict[str, Any]] = [
        {
            "bid_id": str(record.get("bid_id") or ""),
            "project_name": str(record.get("project_name") or "(未命名)"),
            "budget": float(record["budget"]),
        }
        for record in dataset.records
        if record.get("budget") is not None
    ]

    if len(samples) < 5:
        return {
            "sample_count": len(samples),
            "skipped_reason": (
                f"有预算样本 {len(samples)} < 5，无统计意义，不检测（不猜数）"
            ),
            "q1": None,
            "median": None,
            "q3": None,
            "iqr": None,
            "lower_fence": None,
            "upper_fence": None,
            "high": [],
            "low": [],
        }

    values = sorted(s["budget"] for s in samples)
    q1 = _percentile(values, 0.25)
    median = _percentile(values, 0.50)
    q3 = _percentile(values, 0.75)
    iqr = q3 - q1
    lower_fence = q1 - factor * iqr
    upper_fence = q3 + factor * iqr

    high = [
        s
        for s in samples
        if s["budget"] > upper_fence
    ]
    low = [
        s
        for s in samples
        if s["budget"] < max(lower_fence, 0)  # 预算非负，下围栏不越 0
    ]
    high.sort(key=lambda s: -s["budget"])
    low.sort(key=lambda s: s["budget"])

    return {
        "sample_count": len(samples),
        "q1": q1,
        "median": median,
        "q3": q3,
        "iqr": iqr,
        "lower_fence": max(lower_fence, 0.0),
        "upper_fence": upper_fence,
        "high": high,
        "low": low,
    }
