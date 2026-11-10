"""src/analyze.agencies 代理机构画像测试（#601 R96）。

覆盖聚合口径（项目数/预算有值样本/合作采购人去重/类别/活跃月/
定标数）、无代理记录不猜数、排序确定性、Top 上限、十八节渲染。
"""

from src.analyze import AnalysisDataset
from src.analyze.agencies import agency_profiles


def _rows(*rows):
    return [dict(r) for r in rows]


class TestAgencyProfiles:
    def test_aggregation_fields(self):
        ds = AnalysisDataset(
            records=_rows(
                {
                    "agency": "丙代理",
                    "project_name": "A",
                    "budget": 100.0,
                    "category": "信息化",
                    "publish_date": "2026-01-05",
                    "purchaser": "大数据局",
                    "winner": "甲公司",
                },
                {
                    "agency": "丙代理",
                    "project_name": "B",
                    "budget": 300.0,
                    "category": "安防",
                    "publish_date": "2026-03-10",
                    "purchaser": "政务办",
                },
                {
                    "agency": "丙代理",
                    "project_name": "C",
                    "budget": None,
                    "category": "信息化",
                    "publish_date": "2026-01-20",
                    "purchaser": "大数据局",
                },
            )
        )
        profiles = agency_profiles(ds)
        assert len(profiles) == 1
        p = profiles[0]
        assert p["agency"] == "丙代理"
        assert p["project_count"] == 3
        # 预算只计有值样本（100+300；缺预算样本不计、不折零）
        assert p["budget_total"] == 400.0
        assert p["budget_mean"] == 200.0
        assert p["budget_sample_count"] == 2
        # 合作采购人去重（出现序）
        assert p["purchasers"] == ["大数据局", "政务办"]
        assert p["purchaser_count"] == 2
        # 类别去重（出现序）
        assert p["categories"] == ["信息化", "安防"]
        # 活跃月升序
        assert p["active_months"] == ["2026-01", "2026-03"]
        # 已定标数
        assert p["awarded_count"] == 1

    def test_no_agency_records_excluded(self):
        """无代理（采购人自采等）不属于任何代理机构——不猜数。"""
        ds = AnalysisDataset(
            records=_rows(
                {"agency": "", "project_name": "自采A", "budget": 50.0},
                {"agency": None, "project_name": "自采B"},
                {"agency": "  ", "project_name": "空白C"},
                {"agency": "乙代理", "project_name": "D", "budget": 80.0},
            )
        )
        profiles = agency_profiles(ds)
        assert len(profiles) == 1
        assert profiles[0]["agency"] == "乙代理"
        assert profiles[0]["project_count"] == 1

    def test_agency_name_cleaned(self):
        """机构名首尾空白清洗后聚合（同一机构不因空白分裂）。"""
        ds = AnalysisDataset(
            records=_rows(
                {"agency": "  某招标代理  ", "project_name": "A"},
                {"agency": "某招标代理", "project_name": "B"},
            )
        )
        profiles = agency_profiles(ds)
        assert len(profiles) == 1
        assert profiles[0]["agency"] == "某招标代理"
        assert profiles[0]["project_count"] == 2

    def test_sorting_deterministic(self):
        """项目数降序，并列按名称（Unicode 码位）——确定性。"""
        ds = AnalysisDataset(
            records=_rows(
                {"agency": "乙代理", "project_name": "B1"},
                {"agency": "甲代理", "project_name": "A1"},
                {"agency": "甲代理", "project_name": "A2"},
                {"agency": "甲代理", "project_name": "A3"},
            )
        )
        profiles = agency_profiles(ds)
        assert [p["agency"] for p in profiles] == ["甲代理", "乙代理"]
        assert profiles[0]["project_count"] == 3

    def test_tie_breaks_by_name(self):
        """项目数并列时按名排序（丙 U+4E19 < 甲 U+7532）。"""
        ds = AnalysisDataset(
            records=_rows(
                {"agency": "甲代理", "project_name": "A"},
                {"agency": "丙代理", "project_name": "B"},
            )
        )
        profiles = agency_profiles(ds)
        assert [p["agency"] for p in profiles] == ["丙代理", "甲代理"]

    def test_top_n_limit(self):
        ds = AnalysisDataset(
            records=_rows(
                *({"agency": f"代理{i}", "project_name": f"P{i}"} for i in range(8))
            )
        )
        assert len(agency_profiles(ds)) == 5
        assert len(agency_profiles(ds, top_n=3)) == 3

    def test_empty_dataset(self):
        assert agency_profiles(AnalysisDataset(records=[])) == []

    def test_all_missing_budget_no_folding(self):
        """预算全缺：合计/均值为 None（不折零），样本数 0 如实。"""
        ds = AnalysisDataset(
            records=_rows(
                {"agency": "某代理", "project_name": "A", "budget": None},
                {"agency": "某代理", "project_name": "B", "budget": None},
            )
        )
        p = agency_profiles(ds)[0]
        assert p["budget_total"] is None
        assert p["budget_mean"] is None
        assert p["budget_sample_count"] == 0

    def test_json_serializable(self):
        """产物 JSON 可序列化（--json 消费面）。"""
        import json

        ds = AnalysisDataset(
            records=_rows(
                {"agency": "某代理", "project_name": "A", "budget": 10.0}
            )
        )
        text = json.dumps(agency_profiles(ds), ensure_ascii=False)
        assert "某代理" in text


class TestAgencySectionRender:
    """十九节渲染（payload→Markdown 全链）。"""

    def test_section_nineteen_rendered_with_data(self):
        from src.analyze.report_data import (
            build_analysis_payload,
            render_analysis_markdown,
        )

        ds = AnalysisDataset(
            records=_rows(
                {
                    "agency": "某招标代理",
                    "project_name": "智慧水务平台",
                    "budget": 120.0,
                    "region": "江苏",
                    "publish_date": "2026-03-01",
                    "deadline": "2026-03-21",
                    "purchaser": "水务局",
                    "category": "服务",
                },
                {
                    "agency": "某招标代理",
                    "project_name": "安防改造",
                    "budget": 80.0,
                    "region": "浙江",
                    "publish_date": "2026-03-05",
                    "deadline": "2026-04-05",
                    "purchaser": "公安局",
                    "category": "安防",
                },
                {"project_name": "无代理项目", "budget": 60.0},
            )
        )
        md = render_analysis_markdown(build_analysis_payload(ds))
        assert "## 十九、代理机构画像（代理项目数 Top）" in md
        assert "某招标代理" in md
        assert "合作采购人数" in md
        # 注明只计有值样本
        assert "缺失不折零" in md
        # 目录可导航
        assert "[十九、代理机构画像" in md

    def test_section_skipped_without_agency(self):
        """全数据集无代理 → 节跳过（采购人自采是常态，不渲染空壳）。"""
        from src.analyze.report_data import (
            build_analysis_payload,
            render_analysis_markdown,
        )

        ds = AnalysisDataset(
            records=_rows({"project_name": "自采项目", "budget": 50.0})
        )
        md = render_analysis_markdown(build_analysis_payload(ds))
        assert "十九、代理机构画像" not in md
