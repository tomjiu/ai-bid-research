"""ASCII 条形图测试（#601 R64）。"""

from __future__ import annotations

import sys

from src.analyze.charts import (
    ASCII_CHAR,
    BLOCK_CHAR,
    ZERO_CHAR,
    ascii_bar,
    console_bar_char,
    render_bars,
)


class TestAsciiBar:
    def test_full_width_at_max(self):
        assert ascii_bar(10, 10, width=5) == "█████"

    def test_proportional_fill(self):
        assert ascii_bar(5, 10, width=4) == "██  "

    def test_zero_shows_placeholder(self):
        bar = ascii_bar(0, 10, width=4)
        assert bar[0] == ZERO_CHAR
        assert len(bar) == 4

    def test_negative_treated_as_zero(self):
        assert ascii_bar(-3, 10, width=4)[0] == ZERO_CHAR

    def test_nonpositive_max_all_zero(self):
        assert ascii_bar(5, 0, width=3)[0] == ZERO_CHAR

    def test_min_one_char_for_tiny_value(self):
        # 极小非零值至少 1 格（可见性）
        assert ascii_bar(0.01, 100, width=10).startswith(BLOCK_CHAR)

    def test_ascii_fallback_char(self):
        assert ascii_bar(5, 10, width=4, char=ASCII_CHAR) == "##  "

    def test_width_zero_empty(self):
        assert ascii_bar(5, 10, width=0) == ""


class TestRenderBars:
    def test_alignment_and_values(self):
        lines = render_bars(
            [("杭州", 10), ("宁波", 5)], width=6
        )
                # 条宽 6：10/10→██████；5/10→███+3空格；行尾 " 数值"
        assert lines == ["杭州 │██████ 10", "宁波 │███    5"]

    def test_label_right_align_by_longest(self):
        lines = render_bars([("A", 1), ("很长标签", 2)], width=4)
        assert lines[0].startswith("   A │")
        assert lines[1].startswith("很长标签 │")

    def test_empty_items(self):
        assert render_bars([]) == []

    def test_show_value_off(self):
        lines = render_bars([("x", 3)], width=4, show_value=False)
        assert lines == ["x │████"]

    def test_fixed_label_width(self):
        lines = render_bars(
            [("a", 1)], width=2, label_width=5
        )
        assert lines[0] == "    a │██ 1"


class TestConsoleFallback:
    def test_utf8_console_gets_block(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "linux")

        class _Utf8:
            encoding = "utf-8"

        monkeypatch.setattr(sys, "stdout", _Utf8())
        assert console_bar_char() == BLOCK_CHAR

    def test_gbk_console_keeps_block(self, monkeypatch):
        """GBK（cp936）含几何块区（█=A880）——块字符原样可用。"""
        monkeypatch.setattr(sys, "platform", "win32")

        class _Gbk:
            encoding = "gbk"

        monkeypatch.setattr(sys, "stdout", _Gbk())
        assert console_bar_char() == BLOCK_CHAR

    def test_ascii_console_falls_back(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "win32")

        class _Ascii:
            encoding = "ascii"

        monkeypatch.setattr(sys, "stdout", _Ascii())
        assert console_bar_char() == ASCII_CHAR


class TestCliWiring:
    def test_analyze_stdout_includes_bars(self, tmp_path, capsys):
        # capsys 捕获流本身是 UTF-8（console_bar_char 自然选 █）
        import main as main_mod
        from src.storage.database import BidDatabase
        db = BidDatabase(tmp_path / "b.db")
        try:
            for i, region in enumerate(
                ["浙江省杭州市", "江苏省南京市", "广东省深圳市"]
            ):
                db.save_bid(
                    {
                        "bid_id": f"A-{i}",
                        "project_name": f"项目{i}",
                        "region": region,
                        "publish_date": "2026-01-05",
                    }
                )
        finally:
            db.close()
        rc = main_mod.main(
            [
                "analyze", "--db", str(tmp_path / "b.db"),
                "--output-dir", str(tmp_path / "r"),
            ]
        )
        assert rc == 0
        out = capsys.readouterr().out
        assert "区域 Top 5：" in out
        assert "│" in out and "█" in out
