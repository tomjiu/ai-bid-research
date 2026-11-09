"""竞争密度估算（#601 批次 C 第 13 轮）。

研究问题：「这个领域现在挤不挤？」

口径（全部数据驱动 + 启发式分层，研究工具不冒充事实）：

- **发布密度**：条/月——时间跨度内的平均发布频率；
- **市场集中度**：采购人 top3 占比 + HHI（赫芬达尔指数，
  0-10000）——少数买家主导 vs 多小买家，投标策略完全不同；
- **定标面**：已定标率 + 中标人 top3 占比（谁在持续拿单）。

**密度分层是启发式**（monthly_rate <2 低 / 2-8 中 / >8 高）——
研究速判口径，报告面会明确标注「估算」。
"""

from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List, Optional

from src.analyze.dataset import AnalysisDataset

#: 密度分层阈值（条/月）——研究启发式口径。
_DENSITY_LOW = 2.0
_DENSITY_HIGH = 8.0

#: 未知方归一标签。
UNKNOWN_LABEL = "未知"


def _top_share(counter: Counter, top: int = 3) -> Optional[float]:
    """top-N 占比（总份额基 1.0）；空返回 None。"""
    total = sum(counter.values())
    if total == 0:
        return None
    return sum(count for _, count in counter.most_common(top)) / total


def _hhi(counter: Counter) -> Optional[float]:
    """赫芬达尔指数（0-10000 标度）。

    10000 = 单一主体垄断；<1500 常规视为分散（反垄断口径的研究借用）。
    """
    total = sum(counter.values())
    if total == 0:
        return None
    return sum((count / total) ** 2 for count in counter.values()) * 10000


def _span_months(dataset: AnalysisDataset) -> Optional[float]:
    """时间跨度（月，至少 1——单月也有密度语义）。"""
    dates = dataset.publish_dates
    if not dates:
        return None
    months = (dates[-1].year - dates[0].year) * 12 + (
        dates[-1].month - dates[0].month
    )
    return max(months, 0) + 1


def competition_density(dataset: AnalysisDataset) -> Dict[str, Any]:
    """竞争密度估算（数据面 + 启发式分层）。

    Args:
        dataset: 分析数据集（可先用 db 侧 keyword 过滤切片）。

    Returns:
        含以下键的字典（JSON 可序列化）：

        - ``records``：记录总数；
        - ``span_months``：跨度月数（无日期为 None）；
        - ``monthly_rate``：条/月（无日期为 None）；
        - ``density_level``：``低``/``中``/``高``/``未知``（启发式）；
        - ``purchaser_top3_share``：采购人 top3 占比（0-1）；
        - ``purchaser_hhi``：采购人 HHI（0-10000）；
        - ``award_rate``：定标率；
        - ``winner_top3_share``：中标人 top3 占比（已定标面）。
    """
    purchaser_counter: Counter = Counter()
    winner_counter: Counter = Counter()
    for record in dataset.records:
        purchaser = (record.get("purchaser") or "").strip()
        purchaser_counter[purchaser or UNKNOWN_LABEL] += 1
        winner = (record.get("winner") or "").strip()
        if winner:
            winner_counter[winner] += 1

    span_months = _span_months(dataset)
    monthly_rate = (
        len(dataset) / span_months if span_months is not None else None
    )
    if monthly_rate is None:
        density_level = "未知（无日期，无法估密度）"
    elif monthly_rate < _DENSITY_LOW:
        density_level = "低"
    elif monthly_rate <= _DENSITY_HIGH:
        density_level = "中"
    else:
        density_level = "高"

    return {
        "records": len(dataset),
        "span_months": span_months,
        "monthly_rate": monthly_rate,
        "density_level": density_level,
        "purchaser_top3_share": _top_share(purchaser_counter),
        "purchaser_hhi": _hhi(purchaser_counter),
        "award_rate": dataset.award_rate,
        "winner_top3_share": _top_share(winner_counter),
    }
