"""平台文档契约测试（#601 R73）——文档与实现面不漂移。"""

from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
DOC = REPO / "docs" / "PLATFORM-NOTES.md"


class TestPlatformDocs:
    def test_doc_exists_and_substantial(self):
        text = DOC.read_text(encoding="utf-8")
        assert len(text) > 2000  # 不是占位文档

    @pytest.mark.parametrize(
        "topic,marker",
        [
            ("控制台加固", "errors=replace"),
            ("长路径", "LongPathsEnabled"),
            ("行尾契约", "字节一致"),
            ("WAL 回退", "journal_mode"),
            ("文件锁", "msvcrt"),
            ("在线备份", "--backup"),
            ("断点续跑", "--resume"),
            ("重试退避", "Retry-After"),
            ("冒烟脚本", "SMOKE OK"),
            ("保留名清洗", "COM1"),
            ("退出码指引", "exit_codes"),
            ("大小写折叠", "大小写"),
        ],
    )
    def test_covers_all_platform_features(self, topic, marker):
        text = DOC.read_text(encoding="utf-8")
        assert marker in text, f"平台文档缺主题[{topic}]标记[{marker}]"

    def test_mentions_both_platforms(self):
        text = DOC.read_text(encoding="utf-8")
        assert "Windows" in text and "Linux" in text

    def test_implementation_modules_referenced(self):
        text = DOC.read_text(encoding="utf-8")
        for module in (
            "src/platform.py",
            "src/locking.py",
            "src/storage/pragmas.py",
            "src/colors.py",
        ):
            assert module in text
