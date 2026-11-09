"""src/analyze 渲染测试（#601 批次 C·R14）。"""

from __future__ import annotations

import re

import pytest

from src.analyze import (
    BidDataset,
    compute_stats,
    format_stats_markdown,
    save_analysis_report,
)
from src.report.generator import ReportGenerator


@pytest.fixture()
def sample_stats():
    ds = BidDataset(
        [
            {
                "bid_id": "A-1",
                "project_name": "智慧城市一期平台",
                "region": "浙江省杭州市",
                "budget": 1200.0,
                "publish_date": "2026-01-10",
                "winner": "甲公司",
            },
            {
                "bid_id": "A-2",
                "project_name": "数据中心设备采购",
                "region": "北京市",
                "budget": 800.0,
                "publish_date": "2026-02-15",
                "winner": "乙公司",
            },
            {
                "bid_id": "A-3",
                "project_name": "智慧城市二期",
                "region": "浙江省杭州市",
                "budget": None,
                "publish_date": "2026-02-20",
                "winner": "甲公司",
            },
        ]
    )
    return compute_stats(ds)


class TestFormatStatsMarkdown:
    def test_title_and_header(self, sample_stats):
        md = format_stats_markdown(sample_stats, title="测试报告")
        assert md.startswith("# 测试报告")
        assert "生成时间" in md
        assert "共 3 条项目" in md
        assert "1,000" in md  # 预算总额 2000.0 → 千分位
        assert "2,000" in md

    def test_budget_section_table(self, sample_stats):
        md = format_stats_markdown(sample_stats)
        assert "## 一、金额分布（万元）" in md
        assert "| 中位数 | 1,000 |" in md
        assert "| 样本数 | 2 |" in md

    def test_region_section(self, sample_stats):
        md = format_stats_markdown(sample_stats)
        assert "## 二、区域分布" in md
        assert "浙江省杭州市" in md
        assert "共 2 个不同地区" in md

    def test_trend_section_with_mom(self, sample_stats):
        md = format_stats_markdown(sample_stats)
        assert "## 三、月度趋势" in md
        assert "2026-01" in md and "2026-02" in md
        assert "环比上升 100.0%" in md

    def test_keyword_section(self, sample_stats):
        md = format_stats_markdown(sample_stats)
        assert "## 四、关键词频次" in md
        assert "智慧城市" in md
        # 样本三项目全部命中默认词表 → unmatched 提示不出场
        assert "未命中任何领域关键词" not in md

    def test_competition_section(self, sample_stats):
        md = format_stats_markdown(sample_stats)
        assert "## 五、竞争密度" in md
        assert "CR1 = 66.7%" in md
        assert "独立中标人：2 家" in md
        assert "| 甲公司 | 2 |" in md

    def test_none_rendered_as_dash(self):
        stats = compute_stats(BidDataset([]))
        md = format_stats_markdown(stats)
        assert "*无预算样本" in md
        assert "*无地区样本" in md
        assert "*无日期样本" in md
        assert "CR1 = —" in md

    def test_methodology_footer(self, sample_stats):
        md = format_stats_markdown(sample_stats)
        assert "### 口径说明" in md
        assert "离线确定性统计" in md

    def test_deterministic_rendering(self, sample_stats):
        """同一输入同一输出（除时间戳行外）。"""
        first = format_stats_markdown(sample_stats)
        second = format_stats_markdown(sample_stats)
        strip = lambda s: "\n".join(  # noqa: E731
            line for line in s.splitlines() if not line.startswith("- 生成时间")
        )
        assert strip(first) == strip(second)

    def test_no_markdown_syntax_leak(self, sample_stats):
        """渲染产物不含未闭合的表格分隔或占位符残留。"""
        md = format_stats_markdown(sample_stats)
        assert "None" not in md
        assert "{" not in md and "}" not in md


class TestSaveAnalysisReport:
    def test_save_via_report_generator(self, sample_stats, tmp_path):
        generator = ReportGenerator(
            output_dir=tmp_path / "reports", llm_client=_NoopLLM()
        )
        md = format_stats_markdown(sample_stats)
        result = save_analysis_report(generator, md, prefix="analysis_test")
        path = result["markdown"]
        assert path.endswith(".md")
        content = open(path, encoding="utf-8").read()
        assert "# 招标数据分析报告" in content

    def test_save_with_html_export(self, sample_stats, tmp_path):
        generator = ReportGenerator(
            output_dir=tmp_path / "reports", llm_client=_NoopLLM()
        )
        md = format_stats_markdown(sample_stats)
        result = save_analysis_report(
            generator, md, prefix="analysis_test", html=True
        )
        assert result["html"].endswith(".html")
        html = open(result["html"], encoding="utf-8").read()
        assert "<!DOCTYPE html>" in html
        assert "智慧城市" in html or "金额分布" in html


class _NoopLLM:
    """占位 LLM 客户端——渲染路径不触网。"""

    pass
