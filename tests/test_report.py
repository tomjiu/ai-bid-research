"""src/report 模块单元测试。

LLM 客户端以 MagicMock/AsyncMock 替换，验证报告生成、
保存与 HTML 导出逻辑，不发起真实网络请求。
"""

import asyncio
import re
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.report.generator import ReportGenerator


@pytest.fixture()
def mock_llm() -> MagicMock:
    """返回 chat 恒定返回示例分析的 mock LLM 客户端。"""
    llm = MagicMock()
    llm.chat = AsyncMock(
        return_value=(
            "## 项目概况\n\n本项目为智慧园区平台建设，预算 350 万元。\n\n"
            "## 结论与建议\n\n建议尽早组建投标团队。\n\n"
            "- 准备资质材料\n- 对接采购人需求"
        )
    )
    return llm


@pytest.fixture()
def generator(tmp_path: Path, mock_llm: MagicMock) -> ReportGenerator:
    """返回使用临时输出目录与 mock LLM 的报告生成器。"""
    return ReportGenerator(
        llm_client=mock_llm, output_dir=tmp_path / "reports"
    )


class TestReportGenerator:
    """ReportGenerator 行为测试。"""

    def test_init_creates_output_dir(self, tmp_path: Path) -> None:
        """初始化时自动创建输出目录。"""
        target = tmp_path / "nested" / "reports"
        ReportGenerator(llm_client=MagicMock(), output_dir=target)
        assert target.is_dir()

    def test_generate_bid_report_saves_markdown(
        self, generator: ReportGenerator, mock_llm: MagicMock
    ) -> None:
        """单项目报告：调用 LLM 并保存为带编号前缀的 Markdown 文件。"""
        analysis_data = {
            "project_name": "智慧园区综合管理平台",
            "budget": 350.0,
            "region": "浙江省 杭州市",
        }
        path = asyncio.run(
            generator.generate_bid_report("ZJ-2026-001", analysis_data)
        )

        assert path.exists()
        assert path.suffix == ".md"
        assert path.parent == generator.output_dir
        assert path.name.startswith("bid_ZJ-2026-001_")

        content = path.read_text(encoding="utf-8")
        assert "智慧园区综合管理平台" in content
        assert "ZJ-2026-001" in content
        assert "投标分析报告" in content
        assert "结论与建议" in content
        # LLM 被调用且携带 system 消息
        assert mock_llm.chat.await_count == 1
        messages = mock_llm.chat.await_args.args[0]
        assert messages[0]["role"] == "system"

    def test_generate_competition_report_saves_markdown(
        self, generator: ReportGenerator
    ) -> None:
        """竞争态势报告：文件名含关键词与时间窗口信息。"""
        path = asyncio.run(
            generator.generate_competition_report("智慧城市", days=30)
        )

        assert path.exists()
        assert path.name.startswith("competition_智慧城市_")
        content = path.read_text(encoding="utf-8")
        assert "智慧城市" in content
        assert "近 30 天" in content

    def test_generate_bid_report_sanitizes_filename(
        self, tmp_path: Path, mock_llm: MagicMock
    ) -> None:
        """文件名前缀中的路径非法字符被清理。"""
        gen = ReportGenerator(
            llm_client=mock_llm, output_dir=tmp_path / "r"
        )
        path = asyncio.run(gen.generate_bid_report("a/b\\c 001", {"project_name": "X"}))
        assert "/" not in path.name
        assert "\\" not in path.name
        assert re.match(r"bid_a_b_c_001_\d{8}_\d{6}\.md", path.name)

    def test_save_report_timestamp_naming(
        self, generator: ReportGenerator
    ) -> None:
        """_save_report 生成 <prefix>_<时间戳>.md 命名文件。"""
        path = generator._save_report("# 手动保存", "prefix_demo")
        assert re.fullmatch(r"prefix_demo_\d{8}_\d{6}\.md", path.name)
        assert path.read_text(encoding="utf-8") == "# 手动保存"

    def test_export_html_produces_styled_page(
        self, generator: ReportGenerator
    ) -> None:
        """export_html 输出包含标题、正文的完整 HTML 页面。"""
        md_path = generator._save_report(
            "# 投标分析报告：示例项目\n\n"
            "## 项目概况\n\n预算 **350 万元**，详见 `招标文件`。\n\n"
            "- 资质要求高\n- 工期紧\n\n"
            "> 注意：本报告由 AI 生成。\n",
            "export_demo",
        )
        html_path = generator.export_html(md_path)

        assert html_path.exists()
        assert html_path.suffix == ".html"
        assert html_path == md_path.with_suffix(".html")

        page = html_path.read_text(encoding="utf-8")
        assert "<!DOCTYPE html>" in page
        assert "lang=\"zh-CN\"" in page
        assert "<title>投标分析报告：示例项目</title>" in page
        assert "<h1>" in page and "投标分析报告：示例项目" in page
        assert "<h2>项目概况</h2>" in page
        assert "<strong>350 万元</strong>" in page
        assert "<code>招标文件</code>" in page
        assert "<ul>" in page and "<li>资质要求高</li>" in page
        assert "<blockquote>" in page
        assert "font-family" in page

    def test_export_html_missing_source_raises(
        self, generator: ReportGenerator
    ) -> None:
        """源 Markdown 不存在时抛出 FileNotFoundError。"""
        with pytest.raises(FileNotFoundError):
            generator.export_html(generator.output_dir / "not_exist.md")

    def test_markdown_to_html_paragraphs(self) -> None:
        """普通文本行渲染为段落。"""
        html_out = ReportGenerator.markdown_to_html("第一段。\n\n第二段。")
        assert html_out.count("<p>") == 2
        assert "第一段。" in html_out
        assert "第二段。" in html_out

    def test_markdown_to_html_escapes_html(self) -> None:
        """Markdown 内嵌 HTML 标签被转义。"""
        html_out = ReportGenerator.markdown_to_html("内容含 <script>alert(1)</script> 标签")
        assert "<script>" not in html_out
        assert "&lt;script&gt;" in html_out

    def test_report_pipeline_md_to_html_roundtrip(
        self, generator: ReportGenerator
    ) -> None:
        """完整链路：LLM 生成报告 → 保存 → 导出 HTML，两文件均存在。"""
        md_path = asyncio.run(
            generator.generate_bid_report("PRJ-42", {"project_name": "全链路项目"})
        )
        html_path = generator.export_html(md_path)
        assert md_path.exists() and html_path.exists()
        assert "全链路项目" in html_path.read_text(encoding="utf-8")
