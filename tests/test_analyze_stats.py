"""src/analyze 金额分位测试（#601 批次 C·R11）。"""

from __future__ import annotations

import pytest

from src.analyze.dataset import BidDataset
from src.analyze.stats import _percentile, budget_percentiles


def ds_with_budgets(budgets):
    return BidDataset(
        [
            {
                "bid_id": f"B-{i}",
                "project_name": f"项目{i}",
                "budget": b,
            }
            for i, b in enumerate(budgets)
        ]
    )


class TestPercentileHelper:
    def test_empty(self):
        assert _percentile([], 50) is None

    def test_single(self):
        assert _percentile([42.0], 25) == 42.0

    def test_exact_rank(self):
        # 4 样本 p50：rank = 3 * 0.5 = 1.5 → 插值
        values = [10.0, 20.0, 30.0, 40.0]
        assert _percentile(values, 50) == pytest.approx(25.0)

    def test_interpolated(self):
        values = [10.0, 20.0, 30.0]
        # p25: rank = 2 * 0.25 = 0.5 → 15.0
        assert _percentile(values, 25) == pytest.approx(15.0)
        # p75: rank = 2 * 0.75 = 1.5 → 25.0
        assert _percentile(values, 75) == pytest.approx(25.0)

    def test_extremes(self):
        values = [5.0, 10.0, 15.0]
        assert _percentile(values, 0) == 5.0
        assert _percentile(values, 100) == 15.0


class TestBudgetPercentiles:
    def test_basic_distribution(self):
        stats = budget_percentiles(ds_with_budgets([100, 200, 300, 400, 500]))
        assert stats["count"] == 5
        assert stats["total"] == 1500
        assert stats["mean"] == 300
        assert stats["min"] == 100
        assert stats["max"] == 500
        assert stats["median"] == 300
        assert stats["p25"] == 200
        assert stats["p75"] == 400

    def test_none_budgets_excluded(self):
        """budget=None 的样本不计入分位（分母是 with_budget）。"""
        ds = BidDataset(
            [
                {"bid_id": "1", "project_name": "a", "budget": 100.0},
                {"bid_id": "2", "project_name": "b", "budget": None},
                {"bid_id": "3", "project_name": "c", "budget": 300.0},
            ]
        )
        stats = budget_percentiles(ds)
        assert stats["count"] == 2
        assert stats["total"] == 400
        assert stats["median"] == 200

    def test_empty_dataset_honest_none(self):
        stats = budget_percentiles(BidDataset([]))
        assert stats["count"] == 0
        assert stats["total"] == 0.0
        assert stats["mean"] is None
        assert stats["median"] is None
        assert stats["min"] is None

    def test_all_missing_budget(self):
        ds = BidDataset([{"bid_id": "1", "project_name": "a"}])
        stats = budget_percentiles(ds)
        assert stats["count"] == 0
        assert stats["max"] is None

    def test_single_sample(self):
        stats = budget_percentiles(ds_with_budgets([888.0]))
        assert stats["count"] == 1
        assert stats["median"] == 888.0
        assert stats["p25"] == 888.0
        assert stats["max"] == 888.0

    def test_unsorted_input_normalized(self):
        """乱序输入：先排序再算分位（口径稳定）。"""
        stats = budget_percentiles(ds_with_budgets([500, 100, 300]))
        assert stats["min"] == 100
        assert stats["max"] == 500
        assert stats["median"] == 300
