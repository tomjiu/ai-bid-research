"""src/report 模块单元测试。

LLM 客户端以 MagicMock/AsyncMock 替换，验证报告生成、
保存与 HTML 导出逻辑，不发起真实网络请求。
"""

import asyncio
import re
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.report.generator import ReportGenerator
from src.storage.database import BidDatabase


def _make_db_row(bid_id: str, name: str, **overrides) -> dict:
    """构造模拟的数据库项目记录。

    Args:
        bid_id: 招标编号。
        name: 项目名称。
        overrides: 覆盖默认值的字段。

    Returns:
        项目记录字典（与 BidDatabase.get_bid 返回结构一致）。
    """
    row = {
        "id": 1,
        "bid_id": bid_id,
        "project_name": name,
        "region": "浙江省 杭州市",
        "budget": 350.0,
        "publish_date": datetime.now().strftime("%Y-%m-%d"),
        "deadline": None,
        "category": "服务",
        "purchaser": "某市大数据局",
        "agency": None,
        "winner": "云图科技",
        "source_url": None,
        "requirements": ["ISO9001 认证"],
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    row.update(overrides)
    return row


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

    def test_markdown_to_html_table(self) -> None:
        """Markdown 表格（含分隔行与对齐写法）渲染为 <table>。"""
        md = (
            "| 编号 | 项目 | 预算（万元） |\n"
            "|---|:---:|---:|\n"
            "| ZJ-001 | 智慧园区 | 350 |\n"
            "| ZJ-002 | 智慧交通 | **120** |\n"
        )
        html_out = ReportGenerator.markdown_to_html(md)
        assert "<table>" in html_out and "</table>" in html_out
        assert "<thead>" in html_out and "<tbody>" in html_out
        assert "<th>编号</th>" in html_out
        assert "<th>项目</th>" in html_out
        assert "<td>ZJ-001</td>" in html_out
        assert "<td>智慧园区</td>" in html_out
        # 数据行内粗体正常渲染，分隔行不出现在输出中
        assert "<strong>120</strong>" in html_out
        assert "---:" not in html_out

    def test_markdown_to_html_table_then_paragraph(self) -> None:
        """表格结束后接普通段落，互不干扰。"""
        md = "| A | B |\n|---|---|\n| 1 | 2 |\n\n表格说明段落。"
        html_out = ReportGenerator.markdown_to_html(md)
        assert "<table>" in html_out
        assert "<p>表格说明段落。</p>" in html_out

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

    # ------------------------------------------------------------------
    # 数据库集成
    # ------------------------------------------------------------------

    def test_generate_bid_report_from_db(
        self, tmp_path: Path, mock_llm: MagicMock
    ) -> None:
        """analysis_data 为空时按编号从数据库自动取数。"""
        db = BidDatabase(tmp_path / "bids.db")
        try:
            db.save_bid(
                {
                    "bid_id": "DB-001",
                    "project_name": "数据库取数项目",
                    "budget": 120.0,
                }
            )
            gen = ReportGenerator(
                llm_client=mock_llm, output_dir=tmp_path / "r", db=db
            )
            path = asyncio.run(gen.generate_bid_report("DB-001"))
            content = path.read_text(encoding="utf-8")
            assert "数据库取数项目" in content
            # 提示词中应包含库内真实数据
            prompt = mock_llm.chat.await_args.args[0][1]["content"]
            assert "数据库取数项目" in prompt
        finally:
            db.close()

    def test_generate_bid_report_no_data_raises(
        self, generator: ReportGenerator
    ) -> None:
        """既无 analysis_data 又未接库时报 ValueError。"""
        with pytest.raises(ValueError, match="未接入数据库"):
            asyncio.run(generator.generate_bid_report("ANY-1"))

    def test_generate_bid_report_db_missing_id_raises(
        self, tmp_path: Path, mock_llm: MagicMock
    ) -> None:
        """数据库中不存在该编号时报 LookupError。"""
        db = BidDatabase(tmp_path / "bids.db")
        try:
            gen = ReportGenerator(
                llm_client=mock_llm, output_dir=tmp_path / "r", db=db
            )
            with pytest.raises(LookupError, match="DB-404"):
                asyncio.run(gen.generate_bid_report("DB-404"))
        finally:
            db.close()

    def test_generate_competition_report_uses_db_rows(
        self, tmp_path: Path, mock_llm: MagicMock
    ) -> None:
        """竞争报告：接入数据库后提示词携带真实项目清单。"""
        db = BidDatabase(tmp_path / "bids.db")
        try:
            db.import_bids(
                [
                    _make_db_row(
                        "C-001", "智慧园区平台一期", budget=300.0, winner="云图科技"
                    ),
                    _make_db_row("C-002", "智慧园区平台二期", budget=450.0, winner=None),
                ]
            )
            gen = ReportGenerator(
                llm_client=mock_llm, output_dir=tmp_path / "r", db=db
            )
            path = asyncio.run(
                gen.generate_competition_report("智慧园区", days=30)
            )
        finally:
            db.close()

        content = path.read_text(encoding="utf-8")
        assert "本地数据库 2 条项目记录" in content
        prompt = mock_llm.chat.await_args.args[0][1]["content"]
        assert "智慧园区平台一期" in prompt
        assert "智慧园区平台二期" in prompt
        assert "云图科技" in prompt

    def test_generate_competition_report_db_empty_notes_gap(
        self, tmp_path: Path, mock_llm: MagicMock
    ) -> None:
        """竞争报告：库内无记录时提示词明确说明数据缺口。"""
        db = BidDatabase(tmp_path / "empty.db")
        try:
            gen = ReportGenerator(
                llm_client=mock_llm, output_dir=tmp_path / "r", db=db
            )
            path = asyncio.run(
                gen.generate_competition_report("量子计算", days=7)
            )
        finally:
            db.close()

        content = path.read_text(encoding="utf-8")
        assert "本地数据库 0 条项目记录" in content
        prompt = mock_llm.chat.await_args.args[0][1]["content"]
        assert "无记录" in prompt

    def test_generate_competition_report_without_db_keeps_placeholder(
        self, generator: ReportGenerator
    ) -> None:
        """未接库时保持占位提示并标注数据来源。"""
        path = asyncio.run(
            generator.generate_competition_report("智慧城市", days=7)
        )
        content = path.read_text(encoding="utf-8")
        assert "数据来源：通用行业知识（未接入本地数据库）" in content


class TestSaveReportCollision:
    """同秒多次保存不互相覆盖（管道连续两轮运行的场景）。"""

    def test_same_second_saves_do_not_overwrite(
        self, generator: ReportGenerator
    ) -> None:
        first = generator._save_report("# 第一份", "collide")
        second = generator._save_report("# 第二份", "collide")
        assert first != second
        assert first.read_text(encoding="utf-8") == "# 第一份"
        assert second.read_text(encoding="utf-8") == "# 第二份"
        # 第二份带序号后缀（同秒时）
        if first.stem.endswith(
            tuple(f"_{i}" for i in range(1, 10))
        ) is False and second.stem.split("_")[-1].isdigit():
            pass  # 同秒 → second 有 _N 后缀；跨秒 → 均无后缀，两者皆合法
