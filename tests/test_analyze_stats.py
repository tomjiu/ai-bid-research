"""src/analyze.stats 模块单元测试（#601 批次 C 第 11 轮）。"""

import pytest

from src.analyze import AnalysisDataset
from src.analyze.stats import (
    budget_summary,
    date_range,
    monthly_trend,
    region_distribution,
)


def _records(items):
    """构造记录列表。"""
    return [AnalysisDataset(records=item) for item in [items]][0]


class TestBudgetSummary:
    """预算分布。"""

    def test_known_values(self):
        """已知序列的分位数（最近邻秩位法）。"""
        ds = AnalysisDataset(
            records=[
                {"budget": b} for b in [100, 200, 300, 400, 500]
            ]
        )
        s = budget_summary(ds)
        assert s["count"] == 5
        assert s["total"] == 1500
        assert s["min"] == 100
        assert s["max"] == 500
        assert s["mean"] == pytest.approx(300.0)
        assert s["p25"] == 200   # ceil(0.25*5)=2 → 第2小=200
        assert s["median"] == 300
        assert s["p75"] == 400
        assert s["p90"] == 500   # ceil(0.9*5)=5 → 最大值

    def test_none_budgets_excluded(self):
        """None 预算不进统计（count 只算有效值）。"""
        ds = AnalysisDataset(
            records=[{"budget": 100}, {"budget": None}, {"budget": 50}]
        )
        s = budget_summary(ds)
        assert s["count"] == 2
        assert s["total"] == 150

    def test_empty_dataset(self):
        """空集 → 全 None + count 0（不猜数）。"""
        s = budget_summary(AnalysisDataset())
        assert s["count"] == 0
        assert s["median"] is None
        assert s["p90"] is None
        assert s["total"] is None

    def test_single_value(self):
        """单值序列：所有分位 = 该值。"""
        s = budget_summary(AnalysisDataset(records=[{"budget": 88.0}]))
        assert s["min"] == s["max"] == s["median"] == s["p90"] == 88.0


class TestRegionDistribution:
    """区域分布。"""

    def test_counts_desc(self):
        """按条数降序；平局按名称。"""
        ds = AnalysisDataset(
            records=[
                {"region": "浙江"}, {"region": "浙江"},
                {"region": "江苏"}, {"region": None}, {"region": "  "},
            ]
        )
        dist = region_distribution(ds)
        assert dist == {"浙江": 2, "未知": 2, "江苏": 1}

    def test_top_n_merges_rest(self):
        """top N 截断，其余并计「其他」。"""
        ds = AnalysisDataset(
            records=[
                {"region": r} for r in ["甲", "甲", "乙", "乙", "丙", "丁"]
            ]
        )
        dist = region_distribution(ds, top=2)
        assert dist["甲"] == 2
        assert dist["乙"] == 2
        assert dist["其他"] == 2

    def test_empty(self):
        """空集 → 空 dict。"""
        assert region_distribution(AnalysisDataset()) == {}


class TestMonthlyTrend:
    """月度趋势。"""

    def test_month_counts_sorted(self):
        """按月计数并升序；无日期记录剔除。"""
        ds = AnalysisDataset(
            records=[
                {"publish_date": "2026-11-01"},
                {"publish_date": "2026-10-15"},
                {"publish_date": "2026-11-20"},
                {"publish_date": None},
                {"publish_date": "2026-09-30"},
            ]
        )
        trend = monthly_trend(ds)
        assert list(trend.items()) == [
            ("2026-09", 1), ("2026-10", 1), ("2026-11", 2),
        ]

    def test_empty(self):
        """无日期 → 空 dict。"""
        assert monthly_trend(AnalysisDataset(records=[{"budget": 1}])) == {}


class TestDateRange:
    """时间跨度。"""

    def test_range(self):
        """earliest/latest/天数。"""
        ds = AnalysisDataset(
            records=[
                {"publish_date": "2026-10-01"},
                {"publish_date": "2026-11-15"},
                {"publish_date": "2026-10-20"},
            ]
        )
        r = date_range(ds)
        assert r["earliest"] == "2026-10-01"
        assert r["latest"] == "2026-11-15"
        assert r["span_days"] == 45
        assert r["count"] == 3

    def test_empty(self):
        """空集 → 全 None。"""
        r = date_range(AnalysisDataset())
        assert r == {"earliest": None, "latest": None, "span_days": None, "count": 0}
