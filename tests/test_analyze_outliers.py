"""src/analyze.outliers 预算离群检测测试（#601 R49）。"""

from src.analyze import (
    AnalysisDataset,
    build_analysis_payload,
    render_analysis_markdown,
)
from src.analyze.outliers import budget_outliers


def _ds(budgets):
    return AnalysisDataset(
        records=[
            {"project_name": f"P{i}", "budget": b} for i, b in enumerate(budgets)
        ]
    )


class TestIqrOutliers:
    def test_basic_high_low_detection(self):
        ds = _ds([10, 12, 13, 15, 16, 18, 20, 500])  # 500 明显高价
        out = budget_outliers(ds)
        assert out["sample_count"] == 8
        assert [o["budget"] for o in out["high"]] == [500.0]
        assert out["low"] == []
        # 分布锚点在合理区间
        assert out["q1"] <= out["median"] <= out["q3"]

    def test_low_outlier_and_nonnegative_fence(self):
        ds = _ds([100, 110, 115, 120, 125, 130, 0.001])  # 0.001 疑似口径混录
        out = budget_outliers(ds)
        assert [o["budget"] for o in out["low"]] == [0.001]
        assert out["lower_fence"] >= 0  # 预算域非负——下围栏不越 0

    def test_small_sample_skips_honestly(self):
        out = budget_outliers(_ds([1.0, 2.0]))
        assert out["high"] == [] and out["low"] == []
        assert "无统计意义" in out["skipped_reason"]

    def test_missing_budget_not_counted(self):
        ds = AnalysisDataset(
            records=[
                {"project_name": "a", "budget": 10},
                {"project_name": "b"},  # 缺预算
                {"project_name": "c", "budget": None},
            ]
        )
        out = budget_outliers(ds)
        assert out["sample_count"] == 1

    def test_no_outliers_clean_data(self):
        ds = _ds([10, 11, 12, 13, 14, 15, 16, 17])
        out = budget_outliers(ds)
        assert out["high"] == [] and out["low"] == []

    def test_wider_factor_fewer_outliers(self):
        ds = _ds([10, 12, 13, 15, 16, 18, 20, 100])
        tight = budget_outliers(ds, factor=1.5)
        loose = budget_outliers(ds, factor=3.0)
        assert len(tight["high"]) >= len(loose["high"])


class TestReportSectionThirteen:
    def test_payload_and_markdown(self):
        ds = _ds([10, 12, 13, 15, 16, 18, 20, 500])
        payload = build_analysis_payload(ds)
        md = render_analysis_markdown(payload)
        assert "## 十三、预算离群标记（IQR）" in md
        assert "疑似高价" in md
        assert "统计标记" in md  # 免责口径在节内

    def test_section_skipped_for_small_sample(self):
        md = render_analysis_markdown(build_analysis_payload(_ds([1.0, 2.0])))
        assert "十三、预算离群" not in md
