"""src/analyze.keywords 术语演化（月度趋势）测试（#601 R37）。

覆盖月度计数、一词一项只计一次、无日期记录不参与、Top 上限与
排序确定性、first/last_seen、空集、payload 接线与十节渲染。
"""

from src.analyze import (
    AnalysisDataset,
    build_analysis_payload,
    keyword_monthly_trend,
    render_analysis_markdown,
)


def _ds(rows):
    return AnalysisDataset(records=[dict(r) for r in rows])


class TestKeywordMonthlyTrend:
    """趋势聚合口径。"""

    def test_monthly_counts_and_bounds(self):
        ds = _ds(
            [
                {
                    "project_name": "智慧城市一期",
                    "publish_date": "2026-01-05",
                },
                {
                    "project_name": "智慧城市二期",
                    "publish_date": "2026-01-20",
                },
                {
                    "project_name": "智慧城市三期",
                    "publish_date": "2026-03-01",
                },
            ]
        )
        trends = keyword_monthly_trend(ds)
        slot = trends["智慧城市"]
        assert slot["months"] == {"2026-01": 2, "2026-03": 1}
        assert slot["total"] == 3
        assert slot["first_seen"] == "2026-01"
        assert slot["last_seen"] == "2026-03"

    def test_term_counted_once_per_record(self):
        """一词一项只计一次（同 keyword_frequency 口径）。"""
        ds = _ds(
            [
                {
                    "project_name": "智慧城市与智慧交通项目",
                    "publish_date": "2026-02-01",
                }
            ]
        )
        trends = keyword_monthly_trend(ds)
        assert trends["智慧城市"]["total"] == 1
        assert trends["智慧交通"]["total"] == 1

    def test_records_without_date_excluded(self):
        """无发布日期的记录不参与演化面（口径明示）。"""
        ds = _ds(
            [
                {"project_name": "智慧城市一期", "publish_date": "2026-01-05"},
                {"project_name": "智慧城市二期"},  # 无日期
            ]
        )
        trends = keyword_monthly_trend(ds)
        assert trends["智慧城市"]["total"] == 1

    def test_top_n_and_order_by_total(self):
        rows = []
        for i, month in enumerate(("2026-01", "2026-02", "2026-03")):
            rows.append(
                {"project_name": f"智慧水务{i}期", "publish_date": month}
            )
        rows.append({"project_name": "数据中心项目", "publish_date": "2026-02"})
        ds = _ds(rows)
        assert list(keyword_monthly_trend(ds, top_n=1)) == ["智慧水务"]
        # 总数降序：智慧水务 3 > 数据中心 1
        assert list(keyword_monthly_trend(ds)) == ["智慧水务", "数据中心"]

    def test_extra_terms_extension(self):
        ds = _ds(
            [{"project_name": "低空经济平台", "publish_date": "2026-05-01"}]
        )
        trends = keyword_monthly_trend(ds, extra_terms=("低空经济",))
        assert trends["低空经济"]["first_seen"] == "2026-05"

    def test_no_hits_returns_empty(self):
        assert keyword_monthly_trend(_ds([])) == {}
        assert keyword_monthly_trend(
            _ds([{"project_name": "无关项目", "publish_date": "2026-01-01"}])
        ) == {}


class TestPayloadAndRender:
    """payload 接线与十节渲染。"""

    def test_payload_contains_trends(self):
        payload = build_analysis_payload(
            _ds([{"project_name": "智慧城市一期", "publish_date": "2026-01-05"}])
        )
        assert payload["keyword_trends"]["智慧城市"]["total"] == 1

    def test_render_section_ten_present(self):
        payload = build_analysis_payload(
            _ds(
                [
                    {
                        "project_name": "智慧城市一期",
                        "publish_date": "2026-01-05",
                    },
                    {
                        "project_name": "智慧城市二期",
                        "publish_date": "2026-02-01",
                    },
                ]
            )
        )
        markdown = render_analysis_markdown(payload)
        assert "## 十、术语演化" in markdown
        assert "2026-01" in markdown
        assert "首次出现" in markdown

    def test_render_skipped_without_trend_signal(self):
        payload = build_analysis_payload(
            _ds([{"project_name": "无关键词命中", "publish_date": "2026-01-05"}])
        )
        markdown = render_analysis_markdown(payload)
        assert "十、术语演化" not in markdown
