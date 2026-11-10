"""src/analyze.stats 预算×区域交叉表测试（#601 R36）。

覆盖分桶边界（左闭右开/无上界/None）、稠密矩阵补零、区域排序与
Top 上限（未知区域末位附加）、空集不猜数、payload 接线与九节渲染。
"""

from src.analyze import (
    AnalysisDataset,
    build_analysis_payload,
    render_analysis_markdown,
)
from src.analyze.stats import budget_bucket_label, budget_region_crosstab


class TestBucketLabel:
    """分桶边界口径（左闭右开）。"""

    def test_boundaries(self):
        assert budget_bucket_label(0.0) == "0-100万"
        assert budget_bucket_label(99.99) == "0-100万"
        assert budget_bucket_label(100.0) == "100-500万"  # 左闭
        assert budget_bucket_label(499.99) == "100-500万"
        assert budget_bucket_label(500.0) == "500-1000万"
        assert budget_bucket_label(4999.99) == "1000-5000万"
        assert budget_bucket_label(5000.0) == "5000万+"  # 末桶无上界
        assert budget_bucket_label(999999.0) == "5000万+"

    def test_none_budget_is_unknown(self):
        assert budget_bucket_label(None) == "预算未知"


class TestCrosstab:
    """交叉矩阵口径。"""

    def test_dense_matrix_with_zero_fill(self):
        ds = AnalysisDataset(
            records=[
                {"region": "浙江", "budget": 350.0},
                {"region": "浙江", "budget": 8000.0},
                {"region": "江苏", "budget": None},
            ]
        )
        matrix = budget_region_crosstab(ds)
        assert set(matrix) == {"浙江", "江苏"}
        assert matrix["浙江"]["100-500万"] == 1
        assert matrix["浙江"]["5000万+"] == 1
        assert matrix["浙江"]["0-100万"] == 0  # 稠密补零
        assert matrix["江苏"]["预算未知"] == 1
        # 行合计 = 区域记录数
        assert sum(matrix["浙江"].values()) == 2

    def test_region_order_count_desc_tie_by_name(self):
        ds = AnalysisDataset(
            records=[
                {"region": "乙省", "budget": 1.0},
                {"region": "甲省", "budget": 1.0},
                {"region": "丙省", "budget": 1.0},
                {"region": "丙省", "budget": 2.0},
            ]
        )
        assert list(budget_region_crosstab(ds)) == ["丙省", "乙省", "甲省"]

    def test_top_regions_cap_with_unknown_appended(self):
        rows = []
        for name in ("甲省", "乙省", "丙省"):
            rows += [
                {"region": name, "budget": 1.0},
                {"region": name, "budget": 2.0},
            ]
        rows.append({"region": None, "budget": 1.0})  # 未知区域
        ds = AnalysisDataset(records=rows)
        matrix = budget_region_crosstab(ds, top_regions=3)
        # 三省各 2 条进 Top3；未知 1 条未进前列 → 末位附加（缺口可见）
        assert list(matrix) == ["丙省", "乙省", "甲省", "未知"]

    def test_equal_counts_tie_name_includes_unknown_naturally(self):
        """计数并列时按名称确定性排序——「未知」(U+672A) 先于「省」(U+7701)。"""
        ds = AnalysisDataset(
            records=[
                {"region": "省A", "budget": 1.0},
                {"region": None, "budget": 1.0},
            ]
        )
        assert list(budget_region_crosstab(ds)) == ["未知", "省A"]

    def test_empty_dataset_returns_empty(self):
        assert budget_region_crosstab(AnalysisDataset(records=[])) == {}

    def test_all_unknown_region_only(self):
        ds = AnalysisDataset(records=[{"region": None, "budget": 5.0}])
        matrix = budget_region_crosstab(ds)
        assert list(matrix) == ["未知"]
        assert matrix["未知"]["0-100万"] == 1


class TestPayloadAndRender:
    """payload 接线与九节渲染。"""

    def test_payload_contains_crosstab(self):
        payload = build_analysis_payload(
            AnalysisDataset(
                records=[{"region": "浙江", "budget": 350.0}]
            )
        )
        assert payload["budget_region_crosstab"]["浙江"]["100-500万"] == 1

    def test_render_section_nine_present(self):
        payload = build_analysis_payload(
            AnalysisDataset(
                records=[
                    {"region": "浙江", "budget": 350.0},
                    {"region": "江苏", "budget": None},
                ]
            )
        )
        markdown = render_analysis_markdown(payload)
        assert "## 九、预算 × 区域交叉" in markdown
        assert "预算未知" in markdown
        assert "合计" in markdown

    def test_render_skipped_when_only_unknown_region(self):
        """只有未知区域 = 无区域信号 → 跳节（同二节口径）。"""
        payload = build_analysis_payload(
            AnalysisDataset(records=[{"region": None, "budget": 5.0}])
        )
        markdown = render_analysis_markdown(payload)
        assert "九、预算 × 区域交叉" not in markdown
