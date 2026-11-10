"""src/analyze.categories 品类分布测试（#601 R97）。

覆盖归并口径（清洗后精确匹配、不做词表归一）、填充率三数口径、
预算有值样本、排序确定性、Top 上限与 distinct 不受限、空集不猜数、
二十节渲染。
"""

from src.analyze import AnalysisDataset
from src.analyze.categories import category_distribution


def _rows(*rows):
    return [dict(r) for r in rows]


class TestCategoryDistribution:
    def test_aggregation_and_fill_rate(self):
        ds = AnalysisDataset(
            records=_rows(
                {"project_name": "A", "category": "信息化", "budget": 100.0, "winner": "甲"},
                {"project_name": "B", "category": "信息化", "budget": 300.0},
                {"project_name": "C", "category": "安防", "budget": 50.0},
                {"project_name": "D", "category": None},
                {"project_name": "E", "category": "  "},
            )
        )
        result = category_distribution(ds)
        assert result["filled_count"] == 3
        assert result["missing_count"] == 2
        assert result["filled_rate"] == 0.6
        assert result["distinct_count"] == 2
        info = {c["category"]: c for c in result["categories"]}
        assert info["信息化"]["count"] == 2
        assert info["信息化"]["budget_total"] == 400.0
        assert info["信息化"]["budget_mean"] == 200.0
        assert info["信息化"]["budget_sample_count"] == 2
        assert info["信息化"]["awarded_count"] == 1
        assert info["安防"]["count"] == 1

    def test_exact_match_no_vocabulary_folding(self):
        """品类是自由文本：精确匹配归并，近义不折叠（不臆造映射）。"""
        ds = AnalysisDataset(
            records=_rows(
                {"project_name": "A", "category": "信息化"},
                {"project_name": "B", "category": "信息技术"},  # 近义但不同串
                {"project_name": "C", "category": "信息化"},
            )
        )
        result = category_distribution(ds)
        assert result["distinct_count"] == 2
        counts = sorted(c["count"] for c in result["categories"])
        assert counts == [1, 2]

    def test_category_cleaned_before_grouping(self):
        """首尾空白清洗后聚合（同一品类不因空白分裂）。"""
        ds = AnalysisDataset(
            records=_rows(
                {"project_name": "A", "category": "  服务  "},
                {"project_name": "B", "category": "服务"},
            )
        )
        result = category_distribution(ds)
        assert result["distinct_count"] == 1
        assert result["categories"][0]["category"] == "服务"
        assert result["categories"][0]["count"] == 2

    def test_sorting_deterministic(self):
        """计数降序，并列按名（Unicode 码位）——确定性。"""
        ds = AnalysisDataset(
            records=_rows(
                {"project_name": "A", "category": "安防"},
                {"project_name": "B", "category": "服务"},
                {"project_name": "C", "category": "服务"},
            )
        )
        result = category_distribution(ds)
        names = [c["category"] for c in result["categories"]]
        # 计数：服务=2 > 安防=1
        assert names == ["服务", "安防"]

    def test_top_n_limit_but_distinct_full(self):
        """Top 截断品类条目，distinct_count 不受限。"""
        ds = AnalysisDataset(
            records=_rows(
                *(
                    {"project_name": f"P{i}", "category": f"类{i}"}
                    for i in range(8)
                )
            )
        )
        result = category_distribution(ds, top_n=3)
        assert len(result["categories"]) == 3
        assert result["distinct_count"] == 8

    def test_budget_missing_not_folded(self):
        """预算全缺：合计/均值 None，样本数 0。"""
        ds = AnalysisDataset(
            records=_rows(
                {"project_name": "A", "category": "服务", "budget": None},
                {"project_name": "B", "category": "服务"},
            )
        )
        entry = category_distribution(ds)["categories"][0]
        assert entry["budget_total"] is None
        assert entry["budget_mean"] is None
        assert entry["budget_sample_count"] == 0

    def test_empty_dataset(self):
        """空集：填充率 None（分母为 0），不猜数。"""
        result = category_distribution(AnalysisDataset(records=[]))
        assert result["filled_count"] == 0
        assert result["missing_count"] == 0
        assert result["filled_rate"] is None
        assert result["categories"] == []
        assert result["distinct_count"] == 0

    def test_all_missing(self):
        ds = AnalysisDataset(
            records=_rows(
                {"project_name": "A"}, {"project_name": "B", "category": ""}
            )
        )
        result = category_distribution(ds)
        assert result["missing_count"] == 2
        assert result["filled_count"] == 0
        assert result["filled_rate"] == 0.0

    def test_json_serializable(self):
        import json

        ds = AnalysisDataset(
            records=_rows({"project_name": "A", "category": "服务", "budget": 5.0})
        )
        assert "服务" in json.dumps(
            category_distribution(ds), ensure_ascii=False
        )


class TestCategorySectionRender:
    """二十节渲染（payload→Markdown 全链）。"""

    def test_section_twenty_rendered_with_data(self):
        from src.analyze.report_data import (
            build_analysis_payload,
            render_analysis_markdown,
        )

        ds = AnalysisDataset(
            records=_rows(
                {
                    "project_name": "智慧水务平台",
                    "category": "服务",
                    "budget": 120.0,
                    "region": "江苏",
                    "publish_date": "2026-03-01",
                },
                {
                    "project_name": "数据中心扩容",
                    "category": "信息化",
                    "budget": 800.0,
                    "region": "浙江",
                    "publish_date": "2026-03-02",
                },
                {"project_name": "无品类项目", "budget": 60.0},
            )
        )
        md = render_analysis_markdown(build_analysis_payload(ds))
        assert "## 二十、品类分布" in md
        assert "服务" in md
        assert "信息化" in md
        # 注明精确匹配归并口径（不臆造映射）
        assert "精确匹配" in md
        assert "[二十、品类分布" in md  # 目录可导航

    def test_section_skipped_without_category(self):
        """全数据集无品类 → 节跳过（七节填充率已揭示缺失）。"""
        from src.analyze.report_data import (
            build_analysis_payload,
            render_analysis_markdown,
        )

        ds = AnalysisDataset(records=_rows({"project_name": "A", "budget": 5.0}))
        md = render_analysis_markdown(build_analysis_payload(ds))
        assert "二十、品类分布" not in md
