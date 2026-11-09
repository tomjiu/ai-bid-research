"""src/analyze 金额分位测试（#601 批次 C·R11）。"""

from __future__ import annotations

import pytest

from src.analyze.dataset import BidDataset
from src.analyze.stats import (
    _percentile,
    budget_percentiles,
    monthly_trend,
    region_distribution,
)


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


# ----------------------------------------------------------------------
# 区域分布（R12）
# ----------------------------------------------------------------------


class TestRegionDistribution:
    def make_ds(self):
        return BidDataset(
            [
                {"bid_id": "1", "project_name": "a", "region": "浙江省杭州市", "budget": 100.0, "winner": "甲"},
                {"bid_id": "2", "project_name": "b", "region": "浙江省杭州市", "budget": 200.0},
                {"bid_id": "3", "project_name": "c", "region": "北京市", "budget": None},
                {"bid_id": "4", "project_name": "d", "region": None},
                {"bid_id": "5", "project_name": "e", "region": "北京市", "budget": 50.0, "winner": "乙"},
            ]
        )

    def test_group_counts_desc(self):
        result = region_distribution(self.make_ds())
        names = [r["name"] for r in result["regions"]]
        # 杭州与北京并列 2——并列时按名称字典序
        assert names == ["北京市", "浙江省杭州市"]

    def test_budget_and_awarded_per_region(self):
        result = region_distribution(self.make_ds())
        by_name = {r["name"]: r for r in result["regions"]}
        assert by_name["浙江省杭州市"]["count"] == 2
        assert by_name["浙江省杭州市"]["budget_total"] == 300.0
        assert by_name["浙江省杭州市"]["awarded"] == 1
        assert by_name["北京市"]["budget_total"] == 50.0  # None 预算不计

    def test_unknown_count(self):
        result = region_distribution(self.make_ds())
        assert result["unknown_count"] == 1
        assert result["unique_regions"] == 2

    def test_top_n_truncation(self):
        result = region_distribution(self.make_ds(), top_n=1)
        assert len(result["regions"]) == 1
        assert result["unique_regions"] == 2  # 不截断唯一数

    def test_empty(self):
        result = region_distribution(BidDataset([]))
        assert result["regions"] == []
        assert result["unique_regions"] == 0
        assert result["unknown_count"] == 0


# ----------------------------------------------------------------------
# 月度趋势（R12）
# ----------------------------------------------------------------------


class TestMonthlyTrend:
    def make_ds(self):
        return BidDataset(
            [
                {"bid_id": "1", "project_name": "a", "publish_date": "2026-01-05", "budget": 100.0},
                {"bid_id": "2", "project_name": "b", "publish_date": "2026-01-20", "budget": 200.0},
                {"bid_id": "3", "project_name": "c", "publish_date": "2026-02-10", "budget": None},
                {"bid_id": "4", "project_name": "d", "publish_date": None},  # 无日期不进趋势
                {"bid_id": "5", "project_name": "e", "publish_date": "2026-02-15", "budget": 300.0},
            ]
        )

    def test_months_chronological(self):
        result = monthly_trend(self.make_ds())
        assert [m["month"] for m in result["months"]] == ["2026-01", "2026-02"]

    def test_counts_and_budgets(self):
        result = monthly_trend(self.make_ds())
        by_month = {m["month"]: m for m in result["months"]}
        assert by_month["2026-01"]["count"] == 2
        assert by_month["2026-01"]["budget_total"] == 300.0
        assert by_month["2026-02"]["count"] == 2
        assert by_month["2026-02"]["budget_total"] == 300.0  # None 预算不计

    def test_mom_change(self):
        result = monthly_trend(self.make_ds())
        # 2 月 2 个 vs 1 月 2 个 → 0.0%
        assert result["mom_change"] == 0.0

    def test_mom_change_growth(self):
        ds = BidDataset(
            [
                {"bid_id": "1", "project_name": "a", "publish_date": "2026-01-01"},
                {"bid_id": "2", "project_name": "b", "publish_date": "2026-02-01"},
                {"bid_id": "3", "project_name": "c", "publish_date": "2026-02-02"},
                {"bid_id": "4", "project_name": "d", "publish_date": "2026-02-03"},
            ]
        )
        assert monthly_trend(ds)["mom_change"] == 200.0

    def test_single_month_no_mom(self):
        ds = BidDataset([{"bid_id": "1", "project_name": "a", "publish_date": "2026-03-01"}])
        assert monthly_trend(ds)["mom_change"] is None

    def test_with_date_count(self):
        assert monthly_trend(self.make_ds())["with_date"] == 4

    def test_empty(self):
        result = monthly_trend(BidDataset([]))
        assert result["months"] == []
        assert result["mom_change"] is None
        assert result["with_date"] == 0


# ----------------------------------------------------------------------
# 关键词频次 + 竞争密度 + 汇总（R13）
# ----------------------------------------------------------------------

from src.analyze.stats import (
    competition_density,
    compute_stats,
    keyword_frequency,
)


class TestKeywordFrequency:
    def make_ds(self):
        return BidDataset(
            [
                {"bid_id": "1", "project_name": "智慧城市一期平台建设"},
                {"bid_id": "2", "project_name": "智慧城市数据中心设备采购"},
                {"bid_id": "3", "project_name": "政务云运维服务"},
                {"bid_id": "4", "project_name": "某某幼儿园装修"},  # 无命中
            ]
        )

    def test_hits_and_share(self):
        result = keyword_frequency(self.make_ds(), ["智慧城市", "数据中心", "运维"])
        by_kw = {k["keyword"]: k for k in result["keywords"]}
        assert by_kw["智慧城市"]["count"] == 2
        assert by_kw["智慧城市"]["share"] == 50.0  # 2/4
        assert by_kw["数据中心"]["count"] == 1
        assert by_kw["运维"]["count"] == 1

    def test_one_project_matches_multiple(self):
        """「智慧城市数据中心…」同时命中两个关键词——诚实计数。"""
        result = keyword_frequency(self.make_ds(), ["智慧城市", "数据中心"])
        assert sum(k["count"] for k in result["keywords"]) == 3  # 2 + 1

    def test_unmatched(self):
        result = keyword_frequency(self.make_ds(), ["智慧城市", "数据中心", "运维"])
        assert result["unmatched"] == 1

    def test_zero_hit_keywords_absent(self):
        result = keyword_frequency(self.make_ds(), ["不存在词"])
        assert result["keywords"] == []
        assert result["unmatched"] == 4

    def test_default_vocab_used_when_none(self):
        result = keyword_frequency(self.make_ds())
        assert any(k["keyword"] == "智慧城市" for k in result["keywords"])

    def test_ranking_desc_then_name(self):
        result = keyword_frequency(
            self.make_ds(), ["运维", "智慧城市", "数据中心"]
        )
        order = [k["keyword"] for k in result["keywords"]]
        assert order == ["智慧城市", "数据中心", "运维"]  # 2 > 1 = 1 字典序


class TestCompetitionDensity:
    def make_ds(self):
        return BidDataset(
            [
                {"bid_id": "1", "project_name": "a", "winner": "甲公司", "budget": 100.0},
                {"bid_id": "2", "project_name": "b", "winner": "甲公司", "budget": 300.0},
                {"bid_id": "3", "project_name": "c", "winner": "乙公司", "budget": 200.0},
                {"bid_id": "4", "project_name": "d", "winner": None, "budget": None},
            ]
        )

    def test_counts(self):
        result = competition_density(self.make_ds())
        assert result["total"] == 4
        assert result["awarded"] == 3
        assert result["award_rate"] == 75.0
        assert result["unique_winners"] == 2

    def test_top_winners_ranked(self):
        result = competition_density(self.make_ds())
        assert result["top_winners"][0]["name"] == "甲公司"
        assert result["top_winners"][0]["count"] == 2
        assert result["top_winners"][0]["share"] == pytest.approx(66.7)

    def test_cr_and_hhi(self):
        result = competition_density(self.make_ds())
        # 甲 2/3、乙 1/3：CR1=66.7、CR3=100、HHI=66.7²+33.3²≈5555.6
        assert result["cr1"] == pytest.approx(66.7)
        assert result["cr3"] == 100.0
        assert result["hhi"] == pytest.approx(5555.6)

    def test_avg_budget_uses_with_budget_denominator(self):
        result = competition_density(self.make_ds())
        assert result["avg_budget"] == 200.0  # (100+300+200)/3

    def test_no_awarded_honest_none(self):
        ds = BidDataset([{"bid_id": "1", "project_name": "a"}])
        result = competition_density(ds)
        assert result["cr1"] is None
        assert result["cr3"] is None
        assert result["hhi"] is None
        assert result["avg_budget"] is None
        assert result["award_rate"] == 0.0  # 0/1——已定标率为 0（非未定义）

    def test_empty(self):
        result = competition_density(BidDataset([]))
        assert result["total"] == 0
        assert result["top_winners"] == []


class TestComputeStats:
    def test_assembly_shape(self):
        ds = BidDataset(
            [
                {
                    "bid_id": "1",
                    "project_name": "智慧城市项目",
                    "region": "北京市",
                    "budget": 500.0,
                    "publish_date": "2026-01-01",
                    "winner": "甲公司",
                }
            ]
        )
        stats = compute_stats(ds)
        for section in (
            "generated_at",
            "overview",
            "budget",
            "regions",
            "trend",
            "keywords",
            "competition",
        ):
            assert section in stats
        assert stats["overview"]["total"] == 1
        assert stats["budget"]["median"] == 500.0
        assert stats["competition"]["cr1"] == 100.0

    def test_empty_dataset_no_crash(self):
        stats = compute_stats(BidDataset([]))
        assert stats["overview"]["total"] == 0
        assert stats["budget"]["count"] == 0
        assert stats["regions"]["regions"] == []
