"""滑动窗口环比分析（非生产链路——仅供研究，见 docs/PYTHON-BOUNDARY.md）。

R52：最近 N 个月 vs 再前 N 个月的**窗口对照**——单月波动大，
固定窗口对比才能看出趋势方向：

- 指标：项目数、有预算样本均值、定标数（全部描述性）；
- 月份不足 ``2 × window`` 时诚实跳过（``skipped_reason``）；
- 无日期/无预算如实为 ``None``——不折零不猜数；
- 环比差值带方向（``delta`` 正负），变化率在样本为 0 时不可算。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.analyze.dataset import AnalysisDataset


def _month_key(record: Dict[str, Any]) -> Optional[str]:
    date_str = record.get("publish_date")
    if not date_str:
        return None
    return str(date_str)[:7]


def _window_metrics(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    budgets = [
        float(r["budget"]) for r in records if r.get("budget") is not None
    ]
    awarded = sum(1 for r in records if str(r.get("winner") or "").strip())
    return {
        "months": sorted({_month_key(r) for r in records if _month_key(r)}),
        "project_count": len(records),
        "budget_mean": (sum(budgets) / len(budgets)) if budgets else None,
        "budget_sample_count": len(budgets),
        "awarded_count": awarded,
    }


def rolling_comparison(
    dataset: AnalysisDataset, *, window: int = 3
) -> Dict[str, Any]:
    """最近 N 月 vs 再前 N 月窗口对照。

    Args:
        dataset: 分析数据集。
        window: 窗口宽度（月；缺省 3）。

    Returns:
        ``{"current": 指标, "previous": 指标, "delta": 差值,
        "skipped_reason": 跳过说明}``——差值 = 当前 - 前值
        （均值/计数直接相减；None 参与的差值为 None）。
    """
    if window < 1:
        raise ValueError(f"窗口宽度必须 ≥1，收到 {window}")

    dated = [r for r in dataset.records if _month_key(r)]
    months = sorted({_month_key(r) for r in dated})
    if len(months) < 2 * window:
        return {
            "current": None,
            "previous": None,
            "delta": None,
            "skipped_reason": (
                f"有日期月份 {len(months)} < {2 * window}"
                f"（窗口 {window} × 2 期），无对照意义，不计算（不猜数）"
            ),
        }

    current_months = set(months[-window:])
    previous_months = set(months[-2 * window : -window])
    current_records = [r for r in dated if _month_key(r) in current_months]
    previous_records = [r for r in dated if _month_key(r) in previous_months]

    current = _window_metrics(current_records)
    previous = _window_metrics(previous_records)

    def _diff(key: str) -> Optional[float]:
        cur, prev = current[key], previous[key]
        if cur is None or prev is None:
            return None
        return cur - prev

    delta = {
        "project_count": _diff("project_count"),
        "budget_mean": _diff("budget_mean"),
        "awarded_count": _diff("awarded_count"),
    }
    return {
        "current": current,
        "previous": previous,
        "delta": delta,
        "skipped_reason": None,
    }
