"""src/analyze.density 集中度月度趋势测试（#601 R38）。

覆盖逐月 HHI（垄断 10000/分散<1500）、月份升序、无日期排除、
当月定标率、采购人数、空集、payload 接线与十一节渲染（≥2 月才展示）。
"""

from src.analyze import (
    AnalysisDataset,
    build_analysis_payload,
    concentration_trend,
    render_analysis_markdown,
)


def _ds(rows):
    return AnalysisDataset(records=[dict(r) for r in rows])


class TestConcentrationTrend:
    """逐月集中度口径。"""

    def test_monopoly_month_hhi_10000(self):
        """单月单采购人 → HHI 10000（垄断口径）。"""
        ds = _ds(
            [
                {"purchaser": "某局", "publish_date": "2026-01-05"},
                {"purchaser": "某局", "publish_date": "2026-01-20"},
            ]
        )
        trend = concentration_trend(ds)
        assert len(trend["months"]) == 1
        month = trend["months"][0]
        assert month["hhi"] == 10000.0
        assert month["projects"] == 2
        assert month["purchasers"] == 1

    def test_concentration_evolves_between_months(self):
        """1 月单一采购人垄断（HHI=10000）→ 2 月七家均分（≈1429 < 1500 分散口径）。"""
        rows = [
            {"purchaser": "某局", "publish_date": "2026-01-05"},
            {"purchaser": "某局", "publish_date": "2026-01-06"},
        ]
        for i in range(7):
            rows.append({"purchaser": f"局{i}", "publish_date": "2026-02-01"})
        ds = _ds(rows)
        months = concentration_trend(ds)["months"]
        assert [m["month"] for m in months] == ["2026-01", "2026-02"]
        assert months[0]["hhi"] == 10000.0
        assert abs(months[1]["hhi"] - 10000 / 7) < 1  # ≈1428.6
        assert months[0]["hhi"] > months[1]["hhi"]  # 集中度在下降

    def test_award_rate_per_month(self):
        ds = _ds(
            [
                {
                    "purchaser": "某局",
                    "publish_date": "2026-01-05",
                    "winner": "甲公司",
                },
                {"purchaser": "某局", "publish_date": "2026-01-06"},
                {"purchaser": "乙局", "publish_date": "2026-02-01"},
            ]
        )
        months = concentration_trend(ds)["months"]
        assert months[0]["award_rate"] == 0.5
        assert months[1]["award_rate"] == 0.0

    def test_records_without_date_excluded(self):
        ds = _ds(
            [
                {"purchaser": "某局", "publish_date": "2026-01-05"},
                {"purchaser": "他局"},  # 无日期
            ]
        )
        months = concentration_trend(ds)["months"]
        assert len(months) == 1
        assert months[0]["projects"] == 1

    def test_empty_dataset_returns_empty_months(self):
        assert concentration_trend(_ds([])) == {"months": []}


class TestPayloadAndRender:
    """payload 接线与十一节渲染。"""

    def test_payload_contains_trend(self):
        payload = build_analysis_payload(
            _ds([{"purchaser": "某局", "publish_date": "2026-01-05"}])
        )
        assert payload["concentration_trend"]["months"][0]["projects"] == 1

    def test_render_section_eleven_with_two_months(self):
        payload = build_analysis_payload(
            _ds(
                [
                    {"purchaser": "某局", "publish_date": "2026-01-05"},
                    {"purchaser": "乙局", "publish_date": "2026-02-01"},
                ]
            )
        )
        markdown = render_analysis_markdown(payload)
        assert "## 十一、集中度月度趋势" in markdown
        assert "HHI(0-10000)" in markdown

    def test_render_skipped_with_single_month(self):
        """单月无趋势对照 → 不展示（六节已覆盖全局密度）。"""
        payload = build_analysis_payload(
            _ds([{"purchaser": "某局", "publish_date": "2026-01-05"}])
        )
        markdown = render_analysis_markdown(payload)
        assert "十一、集中度月度趋势" not in markdown
