"""src/analyze.rolling 滑动窗口对照测试（#601 R52）。"""

from src.analyze import (
    AnalysisDataset,
    build_analysis_payload,
    render_analysis_markdown,
)
from src.analyze.rolling import rolling_comparison


def _rec(month, *, budget=None, winner=None):
    return {
        "project_name": f"P-{month}",
        "publish_date": f"{month}-15",
        "budget": budget,
        "winner": winner,
    }


class TestRollingComparison:
    def test_basic_two_windows(self):
        ds = AnalysisDataset(
            records=[
                # 前 3 个月：3 个项目
                _rec("2025-10", budget=100.0),
                _rec("2025-11", budget=200.0),
                _rec("2025-12", budget=300.0),
                # 近 3 个月：2 个项目（更高均值）
                _rec("2026-01", budget=500.0, winner="甲"),
                _rec("2026-02", budget=None, winner="乙"),
                _rec("2026-03", budget=None, winner=None),
            ]
        )
        out = rolling_comparison(ds, window=3)
        assert out["skipped_reason"] is None
        assert out["previous"]["project_count"] == 3
        assert out["current"]["project_count"] == 3
        assert out["delta"]["project_count"] == 0
        # 均值：当前 (500)/1=500 vs 前值 (100+200+300)/3=200
        assert out["current"]["budget_mean"] == 500.0
        assert out["previous"]["budget_mean"] == 200.0
        assert out["delta"]["budget_mean"] == 300.0
        assert out["current"]["awarded_count"] == 2
        assert out["delta"]["awarded_count"] == 2

    def test_insufficient_months_skips(self):
        ds = AnalysisDataset(records=[_rec("2026-01"), _rec("2026-02")])
        out = rolling_comparison(ds, window=3)
        assert "无对照意义" in out["skipped_reason"]
        assert out["current"] is None

    def test_undated_records_excluded(self):
        ds = AnalysisDataset(
            records=[
                {"project_name": "无日期", "budget": 1.0},
                _rec("2026-01"),
            ]
        )
        out = rolling_comparison(ds, window=1)
        # 有日期月份只 1 个 < 2——跳过
        assert out["skipped_reason"] is not None

    def test_all_missing_budget_none_not_zero(self):
        ds = AnalysisDataset(
            records=[
                _rec("2025-12"),
                _rec("2026-01", budget=None),
                _rec("2026-02"),
            ]
        )
        out = rolling_comparison(ds, window=1)
        assert out["current"]["budget_mean"] is None
        assert out["delta"]["budget_mean"] is None

    def test_invalid_window_raises(self):
        import pytest

        with pytest.raises(ValueError):
            rolling_comparison(AnalysisDataset(records=[]), window=0)


class TestReportTrendAddendum:
    def test_markdown_window_table(self):
        # 报告面走缺省窗口 3 → 需要 6 个月数据
        ds = AnalysisDataset(
            records=[
                _rec("2025-09", budget=100.0),
                _rec("2025-10", budget=100.0),
                _rec("2025-11", budget=100.0),
                _rec("2025-12", budget=100.0),
                _rec("2026-01", budget=400.0),
                _rec("2026-02", budget=400.0),
            ]
        )
        md = render_analysis_markdown(build_analysis_payload(ds))
        assert "### 窗口对照（近 3 个月 vs 再前同宽）" in md
        assert "环比差" in md
        assert "+200" in md  # 均值差 300-100 显式带号

    def test_no_table_when_insufficient(self):
        ds = AnalysisDataset(records=[_rec("2026-01")])
        md = render_analysis_markdown(build_analysis_payload(ds))
        assert "窗口对照" not in md
