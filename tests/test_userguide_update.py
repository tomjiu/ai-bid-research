"""USER-GUIDE 增量清单契约测试（#601 R76）。"""

from pathlib import Path

import pytest

DOC = (
    Path(__file__).resolve().parent.parent / "docs" / "USER-GUIDE.md"
)


class TestUserGuideIncrement:
    def test_quickref_chapter_exists(self):
        text = DOC.read_text(encoding="utf-8")
        # 章号随 main 侧「导入向导」章（R33/PR #61）合入顺延：九 → 十
        assert "## 十、研究 CLI 功能速查" in text

    @pytest.mark.parametrize(
        "feature,marker",
        [
            ("递归采集", "--recursive"),
            ("断点续跑", "--resume"),
            ("快照对比", "--diff"),
            ("在线备份", "--backup"),
            ("库状态", "--status"),
            ("JSON 导出", "--json"),
            ("模板渲染", "--show"),
            ("日志落盘", "--log-file"),
            ("优先序", "--priority"),
            ("版本横幅", "--version"),
            ("平台文档指引", "PLATFORM-NOTES"),
            ("冒烟自检", "smoke-linux.sh"),
            ("质量巡检命令", "data-quality"),
            ("运行台账", "--runs"),
        ],
    )
    def test_all_new_features_documented(self, feature, marker):
        text = DOC.read_text(encoding="utf-8")
        assert marker in text, f"手册缺[{feature}]标记[{marker}]"

    def test_report_sections_listed(self):
        text = DOC.read_text(encoding="utf-8")
        for section in ("十二", "十三", "十四", "十五", "十六", "十七"):
            assert section in text

    def test_platform_notes_cross_reference(self):
        text = DOC.read_text(encoding="utf-8")
        assert "PLATFORM-NOTES.md" in text


class TestBatchMDocs:
    """批 L/M 文档增量契约（R91）。"""

    @pytest.mark.parametrize(
        "feature,marker",
        [
            ("近重复边界声明", "duplicates.py"),
            ("语义质量边界声明", "语义扩展（R81/R89）"),
            ("去重导出", "--dedupe"),
            ("质量门槛", "--min-score"),
        ],
    )
    def test_boundary_and_guide_updated(self, feature, marker):
        root = Path(__file__).resolve().parent.parent
        boundary = (root / "docs" / "PYTHON-BOUNDARY.md").read_text(
            encoding="utf-8"
        )
        guide = (root / "docs" / "USER-GUIDE.md").read_text(encoding="utf-8")
        assert marker in boundary or marker in guide, (
            f"[{feature}] 标记 [{marker}] 未见于任何文档"
        )
