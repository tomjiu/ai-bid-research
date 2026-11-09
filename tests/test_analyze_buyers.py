"""src/analyze.buyers 采购人画像测试（#601 R35）。

覆盖画像聚合口径（项目数/预算有值样本/类别去重/活跃月/定标数）、
排序确定性、Top 上限、缺失采购人不猜数、payload 接线与报告八节渲染。
"""

from src.analyze import (
    AnalysisDataset,
    build_analysis_payload,
    buyer_profiles,
    render_analysis_markdown,
)


def _rows(*rows):
    """构造 bids 形态记录列表（dict 展开）。"""
    return [dict(r) for r in rows]


class TestBuyerProfiles:
    """画像聚合口径。"""

    def test_aggregation_fields(self):
        ds = AnalysisDataset(
            records=_rows(
                {
                    "purchaser": "某大数据局",
                    "project_name": "A",
                    "budget": 100.0,
                    "category": "信息化",
                    "publish_date": "2026-01-05",
                    "winner": "甲公司",
                },
                {
                    "purchaser": "某大数据局",
                    "project_name": "B",
                    "budget": 300.0,
                    "category": "信息化",
                    "publish_date": "2026-03-10",
                },
                {
                    "purchaser": "某大数据局",
                    "project_name": "C",
                    "budget": None,
                    "category": "咨询",
                    "publish_date": "2026-01-20",
                },
            )
        )
        profiles = buyer_profiles(ds)
        assert len(profiles) == 1
        profile = profiles[0]
        assert profile["purchaser"] == "某大数据局"
        assert profile["project_count"] == 3
        # 预算只计有值样本：(100+300)/2，不把 None 折零
        assert profile["budget_total"] == 400.0
        assert profile["budget_mean"] == 200.0
        assert profile["budget_sample_count"] == 2
        # 类别去重保序 + 活跃月去重升序
        assert profile["categories"] == ["信息化", "咨询"]
        assert profile["active_months"] == ["2026-01", "2026-03"]
        assert profile["awarded_count"] == 1

    def test_all_budgets_missing_is_none(self):
        ds = AnalysisDataset(
            records=_rows({"purchaser": "某局", "project_name": "A"})
        )
        profile = buyer_profiles(ds)[0]
        assert profile["budget_total"] is None
        assert profile["budget_mean"] is None
        assert profile["budget_sample_count"] == 0

    def test_missing_purchaser_excluded(self):
        """缺采购人的记录不参与聚合（不猜数）。"""
        ds = AnalysisDataset(
            records=_rows(
                {"project_name": "无采购人"},
                {"purchaser": "  ", "project_name": "空白采购人"},
                {"purchaser": "某局", "project_name": "A"},
            )
        )
        profiles = buyer_profiles(ds)
        assert [p["purchaser"] for p in profiles] == ["某局"]

    def test_sort_count_desc_then_name(self):
        """项目数降序；并列按名称排序（确定性）。"""
        ds = AnalysisDataset(
            records=_rows(
                {"purchaser": "乙局", "project_name": "1"},
                {"purchaser": "甲局", "project_name": "1"},
                {"purchaser": "丙局", "project_name": "1"},
                {"purchaser": "丙局", "project_name": "2"},
            )
        )
        names = [p["purchaser"] for p in buyer_profiles(ds)]
        assert names == ["丙局", "乙局", "甲局"]

    def test_top_n_cap(self):
        rows = _rows(
            *[
                {"purchaser": f"局{i}", "project_name": str(i)}
                for i in range(10)
            ]
        )
        assert len(buyer_profiles(AnalysisDataset(records=rows), top_n=3)) == 3

    def test_empty_dataset_returns_empty(self):
        assert buyer_profiles(AnalysisDataset(records=[])) == []


class TestPayloadAndRender:
    """payload 接线与报告渲染。"""

    def test_payload_contains_buyer_profiles(self):
        payload = build_analysis_payload(
            AnalysisDataset(
                records=_rows(
                    {"purchaser": "某局", "project_name": "A", "budget": 10.0}
                )
            )
        )
        assert payload["buyer_profiles"][0]["purchaser"] == "某局"

    def test_render_section_eight_present(self):
        payload = build_analysis_payload(
            AnalysisDataset(
                records=_rows(
                    {
                        "purchaser": "某大数据局",
                        "project_name": "智慧城市一期",
                        "budget": 350.0,
                        "publish_date": "2026-01-05",
                        "category": "信息化",
                    }
                )
            )
        )
        markdown = render_analysis_markdown(payload)
        assert "## 八、采购人画像" in markdown
        assert "某大数据局" in markdown

    def test_render_section_skipped_without_purchaser(self):
        """无采购人信号 → 跳节（数据缺口不伪装成画像）。"""
        payload = build_analysis_payload(
            AnalysisDataset(
                records=_rows(
                    {"project_name": "智慧城市一期", "budget": 350.0}
                )
            )
        )
        markdown = render_analysis_markdown(payload)
        assert "八、采购人画像" not in markdown
