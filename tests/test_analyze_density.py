"""src/analyze.density 模块单元测试（#601 批次 C 第 13 轮）。"""

import pytest

from src.analyze import AnalysisDataset
from src.analyze.density import competition_density


class TestCompetitionDensity:
    """竞争密度各面。"""

    def test_high_density_scenario(self):
        """高密度：单月 10 条 → 高 + monthly_rate=10。"""
        ds = AnalysisDataset(
            records=[
                {"publish_date": "2026-10-05"},
                {"publish_date": "2026-10-06"},
                {"publish_date": "2026-10-07"},
                {"publish_date": "2026-10-08"},
                {"publish_date": "2026-10-09"},
                {"publish_date": "2026-10-10"},
                {"publish_date": "2026-10-11"},
                {"publish_date": "2026-10-12"},
                {"publish_date": "2026-10-13"},
                {"publish_date": "2026-10-14"},
            ]
        )
        d = competition_density(ds)
        assert d["monthly_rate"] == pytest.approx(10.0)
        assert d["density_level"] == "高"
        assert d["span_months"] == 1

    def test_medium_density(self):
        """中密度：3 个月 10 条 ≈ 3.3/月。"""
        ds = AnalysisDataset(
            records=[
                {"publish_date": f"2026-{m:02d}-{day:02d}"}
                for m, day in [(8, 1), (9, 1), (10, 1)] * 3 + [(10, 15)]
            ]
        )
        d = competition_density(ds)
        assert d["monthly_rate"] == pytest.approx(10 / 3)
        assert d["density_level"] == "中"

    def test_low_density(self):
        """低密度：跨 3 月仅 2 条。"""
        ds = AnalysisDataset(
            records=[{"publish_date": "2026-08-01"}, {"publish_date": "2026-10-01"}]
        )
        d = competition_density(ds)
        assert d["density_level"] == "低"

    def test_no_dates_unknown(self):
        """无日期 → 密度未知但不炸。"""
        d = competition_density(
            AnalysisDataset(records=[{"project_name": "x"}, {"budget": 1}])
        )
        assert d["monthly_rate"] is None
        assert d["density_level"].startswith("未知")
        assert d["records"] == 2

    def test_purchaser_concentration(self):
        """采购人集中度：1 家独大 → top3=1.0、HHI=10000。"""
        ds = AnalysisDataset(
            records=[
                {"purchaser": "某局", "publish_date": "2026-10-01"},
                {"purchaser": "某局", "publish_date": "2026-10-02"},
                {"purchaser": "某局", "publish_date": "2026-10-03"},
                {"purchaser": "某委", "publish_date": "2026-10-04"},
            ]
        )
        d = competition_density(ds)
        assert d["purchaser_top3_share"] == pytest.approx(1.0)
        assert d["purchaser_hhi"] == pytest.approx(
            (0.75 ** 2 + 0.25 ** 2) * 10000
        )

    def test_winner_concentration_and_award_rate(self):
        """定标面：中标人 top3 占比 + 定标率。"""
        ds = AnalysisDataset(
            records=[
                {"winner": "甲公司", "publish_date": "2026-10-01"},
                {"winner": "甲公司", "publish_date": "2026-10-02"},
                {"winner": "乙公司", "publish_date": "2026-10-03"},
                {"winner": None, "publish_date": "2026-10-04"},
            ]
        )
        d = competition_density(ds)
        assert d["award_rate"] == pytest.approx(0.75)
        assert d["winner_top3_share"] == pytest.approx(1.0)

    def test_empty_dataset(self):
        """空集 → 全 None + records 0（不猜数）。"""
        d = competition_density(AnalysisDataset())
        assert d["records"] == 0
        assert d["monthly_rate"] is None
        assert d["purchaser_top3_share"] is None
        assert d["award_rate"] is None

    def test_buyer_market_spread(self):
        """分散市场：4 家各 1 单 → HHI=2500、top3=0.75。"""
        ds = AnalysisDataset(
            records=[
                {"purchaser": f"买家{i}", "publish_date": "2026-10-01"}
                for i in range(4)
            ]
        )
        d = competition_density(ds)
        assert d["purchaser_hhi"] == pytest.approx(2500.0)
        assert d["purchaser_top3_share"] == pytest.approx(0.75)
