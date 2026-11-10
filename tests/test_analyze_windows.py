"""src/analyze.windows 响应窗口期测试（#601 R95）。

覆盖分布口径（中位/分位/极值）、三计数互斥完备（有效+缺失+
倒挂=总数）、短窗判定（严格小于/边界 20 不计）、示例清单确定性
排序、空集不猜数、自定义提示线。
"""

from src.analyze import AnalysisDataset
from src.analyze.windows import (
    SHORT_WINDOW_DAYS,
    response_windows,
)


def _rows(*rows):
    return [dict(r) for r in rows]


def _rec(name, publish, deadline, region=None):
    return {
        "project_name": name,
        "publish_date": publish,
        "deadline": deadline,
        "region": region,
    }


class TestResponseWindows:
    def test_distribution_stats(self):
        """中位/分位/极值按最近邻秩位口径。"""
        ds = AnalysisDataset(
            records=[
                _rec("A", "2026-01-01", "2026-01-21"),  # 20
                _rec("B", "2026-01-01", "2026-01-26"),  # 25
                _rec("C", "2026-01-01", "2026-01-31"),  # 30
                _rec("D", "2026-01-01", "2026-02-05"),  # 35
                _rec("E", "2026-01-01", "2026-02-10"),  # 40
            ]
        )
        result = response_windows(ds)
        assert result["sample_count"] == 5
        assert result["missing_count"] == 0
        assert result["invalid_count"] == 0
        assert result["min_days"] == 20
        assert result["max_days"] == 40
        assert result["median_days"] == 30
        assert result["p25_days"] == 25
        # 最近邻秩位：ceil(0.75×5)=第 4 个 → 35（非插值）
        assert result["p75_days"] == 35

    def test_counts_mutually_exclusive_exhaustive(self):
        """有效 + 缺失 + 倒挂 = 总记录数（口径可核对）。"""
        ds = AnalysisDataset(
            records=[
                _rec("正常", "2026-01-01", "2026-01-15"),  # 有效（短窗）
                _rec("缺截止", "2026-01-01", None),  # 缺失
                _rec("缺发布", None, "2026-01-20"),  # 缺失
                _rec("坏日期", "2026/1/1", "2026-01-20"),  # 不可解析→缺失
                _rec("倒挂", "2026-02-01", "2026-01-01"),  # 截止早于发布
                _rec("同日", "2026-01-01", "2026-01-01"),  # 窗口 0：有效
            ]
        )
        result = response_windows(ds)
        assert result["sample_count"] == 2
        assert result["missing_count"] == 3
        assert result["invalid_count"] == 1
        # 三计数之和 = 总数 6
        assert (
            result["sample_count"]
            + result["missing_count"]
            + result["invalid_count"]
            == 6
        )

    def test_invalid_excluded_from_distribution(self):
        """倒挂不进分布（min 不被 -31 污染）。"""
        ds = AnalysisDataset(
            records=[
                _rec("倒挂", "2026-02-01", "2026-01-01"),
                _rec("正常", "2026-01-01", "2026-01-31"),
            ]
        )
        result = response_windows(ds)
        assert result["invalid_count"] == 1
        assert result["sample_count"] == 1
        assert result["min_days"] == 30

    def test_short_window_strict_boundary(self):
        """短窗严格小于提示线：恰好 20 日不计，19 日计。"""
        ds = AnalysisDataset(
            records=[
                _rec("整20", "2026-01-01", "2026-01-21"),
                _rec("19日", "2026-01-01", "2026-01-20"),
            ]
        )
        result = response_windows(ds)
        assert result["short_window_count"] == 1
        assert result["short_window_rate"] == 0.5
        assert result["short_window_days"] == SHORT_WINDOW_DAYS
        assert [e["project_name"] for e in result["short_window_examples"]] == [
            "19日"
        ]

    def test_short_examples_ordering_deterministic(self):
        """示例按窗口升序、并列按项目名（Unicode 码位）——确定性。"""
        ds = AnalysisDataset(
            records=[
                _rec("乙项目", "2026-01-01", "2026-01-16"),  # 15
                _rec("甲项目", "2026-01-01", "2026-01-11"),  # 10
                _rec("丙项目", "2026-01-01", "2026-01-11"),  # 10 并列
                _rec("长窗", "2026-01-01", "2026-02-01"),  # 31 不进示例
            ]
        )
        result = response_windows(ds)
        names = [e["project_name"] for e in result["short_window_examples"]]
        # 窗口升序；同为 10 日的两项按名（Unicode 码位：丙 U+4E19 < 甲 U+7532）
        assert names == ["丙项目", "甲项目", "乙项目"]
        # 同输入两次调用结果一致（无隐藏状态）
        again = [
            e["project_name"]
            for e in response_windows(ds)["short_window_examples"]
        ]
        assert again == names

    def test_example_fields_carried(self):
        """示例携带区域/发布/截止原文（复核可直接定位）。"""
        ds = AnalysisDataset(
            records=[
                _rec("短窗项", "2026-03-05", "2026-03-15", region="江苏"),
            ]
        )
        result = response_windows(ds)
        example = result["short_window_examples"][0]
        assert example["window_days"] == 10
        assert example["region"] == "江苏"
        assert example["publish_date"] == "2026-03-05"
        assert example["deadline"] == "2026-03-15"
        # 区域缺失显式 None（不猜「未知」）
        ds2 = AnalysisDataset(records=[_rec("无区域", "2026-03-05", "2026-03-15")])
        assert response_windows(ds2)["short_window_examples"][0]["region"] is None

    def test_top_n_limit(self):
        """示例清单条数上限。"""
        ds = AnalysisDataset(
            records=[
                _rec(f"项目{i}", "2026-01-01", "2026-01-10") for i in range(8)
            ]
        )
        assert len(response_windows(ds)["short_window_examples"]) == 5
        assert len(response_windows(ds, top_n=3)["short_window_examples"]) == 3

    def test_empty_dataset_no_guessing(self):
        """空集：计数 0、统计全 None、占比 None——不猜数。"""
        result = response_windows(AnalysisDataset(records=[]))
        assert result["sample_count"] == 0
        assert result["missing_count"] == 0
        assert result["invalid_count"] == 0
        for key in (
            "median_days",
            "p25_days",
            "p75_days",
            "min_days",
            "max_days",
            "short_window_rate",
        ):
            assert result[key] is None
        assert result["short_window_examples"] == []

    def test_all_missing(self):
        """全部缺日期：missing 如实，统计 None。"""
        ds = AnalysisDataset(
            records=[_rec("A", None, "2026-01-01"), _rec("B", "2026-01-01", None)]
        )
        result = response_windows(ds)
        assert result["missing_count"] == 2
        assert result["sample_count"] == 0
        assert result["median_days"] is None
        assert result["short_window_rate"] is None

    def test_custom_short_window_line(self):
        """自定义提示线（更严口径）原样携带可追溯。"""
        ds = AnalysisDataset(
            records=[_rec("A", "2026-01-01", "2026-01-26")]  # 25 日
        )
        strict = response_windows(ds, short_window_days=30)
        assert strict["short_window_count"] == 1
        assert strict["short_window_days"] == 30
        assert response_windows(ds)["short_window_count"] == 0

    def test_json_serializable(self):
        """产物 JSON 可序列化（--json 消费面）。"""
        import json

        ds = AnalysisDataset(
            records=[_rec("A", "2026-01-01", "2026-01-15", region="江苏")]
        )
        text = json.dumps(response_windows(ds), ensure_ascii=False)
        assert "response" not in text  # 冒烟：不抛异常即通过
        assert "2026-01-15" in text


class TestWindowSectionRender:
    """十八节渲染（payload→Markdown 全链）。"""

    def _ds(self):
        return AnalysisDataset(
            records=[
                _rec("智慧水务平台", "2026-03-01", "2026-03-21", region="江苏"),
                _rec("数据中心扩容", "2026-03-02", "2026-03-12", region="浙江"),
                _rec("安防改造", "2026-03-05", "2026-04-05", region="广东"),
                _rec("缺截止项目", "2026-03-06", None),
            ]
        )

    def test_section_eighteen_rendered_with_data(self):
        from src.analyze.report_data import (
            build_analysis_payload,
            render_analysis_markdown,
        )

        md = render_analysis_markdown(build_analysis_payload(self._ds()))
        assert "## 十八、响应窗口期（发布→截止，天）" in md
        assert "中位（天）" in md
        # 短窗示例表渲染（数据中心扩容 10 日 < 20）
        assert "数据中心扩容" in md
        assert "研究提示非违规认定" in md
        # 目录含新节（可导航）
        assert "[十八、响应窗口期" in md

    def test_section_skipped_without_valid_samples(self):
        """无有效样本 → 节跳过（不渲染空壳）。"""
        from src.analyze.report_data import (
            build_analysis_payload,
            render_analysis_markdown,
        )

        ds = AnalysisDataset(records=[_rec("缺日期", None, None)])
        md = render_analysis_markdown(build_analysis_payload(ds))
        assert "十八、响应窗口期" not in md

    def test_short_examples_table_only_when_present(self):
        """无短窗时不出示例子表（主表仍渲染）。"""
        from src.analyze.report_data import (
            build_analysis_payload,
            render_analysis_markdown,
        )

        ds = AnalysisDataset(
            records=[_rec("长窗A", "2026-03-01", "2026-04-20")]  # 50 日
        )
        md = render_analysis_markdown(build_analysis_payload(ds))
        assert "## 十八、响应窗口期" in md
        assert "最紧迫短窗" not in md
