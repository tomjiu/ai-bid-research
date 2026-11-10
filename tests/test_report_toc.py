"""报告目录（TOC）测试（#601 R63）。"""

from src.analyze import (
    AnalysisDataset,
    build_analysis_payload,
    render_analysis_markdown,
)
from src.analyze.report_data import build_toc, _slugify_heading


def _rich_dataset():
    """触发多节的完整数据集。"""
    rows = []
    for i in range(6):
        rows.append(
            {
                "bid_id": f"T-{i}",
                "project_name": f"智慧城市大数据项目{i}",
                "region": "浙江省杭州市",
                "budget": 100.0 + i * 50,
                "publish_date": f"2026-0{i+1}-10",
                "winner": "甲公司" if i % 2 else None,
                "purchaser": "大数据局",
                "category": "信息化",
            }
        )
    return AnalysisDataset(records=rows)


class TestBuildToc:
    def test_extracts_h2_h3_with_indent(self):
        md = (
            "# 报告\n\n## 一、总览\n\n正文\n\n"
            "### 子节\n\n## 二、明细\n"
        )
        toc = build_toc(md)
        assert "## 目录" in toc
        assert "- [一、总览](#一总览)" in toc
        assert "  - [子节](#子节)" in toc
        assert "- [二、明细](#二明细)" in toc

    def test_h1_excluded_and_depth_cap(self):
        md = "# 顶级\n\n## 节\n\n#### 深层\n"
        toc = build_toc(md)
        assert "顶级" not in toc
        assert "深层" not in toc  # > max_depth 不收录

    def test_code_block_headings_ignored(self):
        md = "## 真\n\n```python\n## 假（代码块内）\n```\n"
        toc = build_toc(md)
        assert "假" not in toc and "真" in toc

    def test_no_self_reference(self):
        md = "## 目录\n\n## 一、节\n"
        toc = build_toc(md)
        assert toc.count("[目录]") == 0

    def test_empty_returns_empty(self):
        assert build_toc("# 只有顶级\n\n正文") == ""

    def test_slug_chinese_kept_punct_dropped(self):
        assert _slugify_heading("十、预算离群标记（IQR）") == "十预算离群标记iqr"


class TestReportInjection:
    def test_full_report_has_toc_after_header(self):
        md = render_analysis_markdown(build_analysis_payload(_rich_dataset()))
        assert "## 目录" in md
        # TOC 在首个内容节之前
        assert md.index("## 目录") < md.index("## 一、")
        # 目录条目本身出现在标题后
        assert md.index("- [") > md.index("# 领域数据分析报告")

    def test_toc_lists_many_sections(self):
        md = render_analysis_markdown(build_analysis_payload(_rich_dataset()))
        for heading in ("二、区域分布", "三、月度发布趋势"):
            assert f"- [{heading}](#" in md

    def test_html_export_anchor_compatible(self):
        """HTML 导出面（自建锚点）不受 TOC 影响——含 TOC 的报告可正常导出。"""
        from src.report.generator import ReportGenerator

        gen = ReportGenerator(output_dir="/tmp/r63-out")
        payload = build_analysis_payload(_rich_dataset())
        md = render_analysis_markdown(payload)
        path = gen._save_report(md, "toc-check")
        html = gen.export_html(path)
        assert html.exists()
        content = html.read_text(encoding="utf-8")
        assert "目录" in content
