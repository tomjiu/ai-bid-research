"""控制台颜色面测试（#601 R65）——NO_COLOR/tty/Windows VT 三线。"""

from __future__ import annotations

import sys

from src.colors import (
    RED,
    ColorPrinter,
    colorize,
    supports_color,
)


class _Stream:
    """可配置 tty/编码的流替身。"""

    def __init__(self, *, tty: bool = True):
        self._tty = tty
        self.written: list[str] = []

    def isatty(self) -> bool:
        return self._tty

    def write(self, text):
        self.written.append(text)

    def flush(self):
        pass


class TestSupportsColor:
    def test_no_color_env_wins_everything(self):
        stream = _Stream(tty=True)
        assert supports_color(stream, env={"NO_COLOR": "1"}) is False
        # 任意非空值（规范：存在即生效）
        assert supports_color(stream, env={"NO_COLOR": ""}) is True

    def test_not_a_tty_disables(self):
        stream = _Stream(tty=False)
        assert supports_color(stream, env={}) is False

    def test_dumb_term_disables(self):
        stream = _Stream(tty=True)
        assert supports_color(stream, env={"TERM": "dumb"}) is False

    def test_linux_tty_enables(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "linux")
        assert supports_color(_Stream(tty=True), env={"TERM": "xterm"})

    def test_windows_terminal_session_enables(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "win32")
        stream = _Stream(tty=True)
        assert (
            supports_color(stream, env={"WT_SESSION": "1"}) is True
        )

    def test_windows_legacy_console_without_vt_disables(
        self, monkeypatch
    ):
        monkeypatch.setattr(sys, "platform", "win32")

        # 无 ctypes.windll（Linux 沙箱里 windll 不存在）→ VT 失败 → 关色
        stream = _Stream(tty=True)
        assert supports_color(stream, env={}) is False

    def test_missing_isatty_attr_disables(self):
        class _NoTty:
            pass

        assert supports_color(_NoTty(), env={}) is False


class TestColorize:
    def test_wraps_when_enabled(self):
        assert colorize("错", RED, enabled=True) == "\033[31m错\033[0m"

    def test_plain_when_disabled(self):
        assert colorize("错", RED, enabled=False) == "错"


class TestColorPrinter:
    def test_err_red_on_enabled_stream(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "linux")
        stream = _Stream(tty=True)
        # env={}：宿主机 NO_COLOR（CI 常设）不干扰能力面单测
        cp = ColorPrinter(stream, env={})
        assert cp.enabled is True
        cp.err("数据库不存在")
        # print 分两次 write（文本 + 换行）
        assert stream.written[0] == "\033[31m数据库不存在\033[0m"
        assert stream.written[1] == "\n"

    def test_plain_when_no_color(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "linux")
        cp2 = ColorPrinter(_Stream(tty=True), env={"NO_COLOR": "1"})
        assert cp2.enabled is False

    def test_ok_green(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "linux")
        stream = _Stream(tty=True)
        cp = ColorPrinter(stream, env={})
        cp.ok("已入库 12 条")
        assert stream.written[0].startswith("\033[32m已入库")


class TestMainWiring:
    def test_error_path_uses_color_printer(self, tmp_path, capsys, monkeypatch):
        """db 不存在：stderr 走 ColorPrinter（此处 capsys 非 tty → 无色）。"""
        import main as main_mod

        rc = main_mod.main(
            ["db", "--db", str(tmp_path / "ghost.db"), "--stats"]
        )
        assert rc == 2
        assert "数据库不存在" in capsys.readouterr().err

    def test_stderr_printer_initialized_in_main(self, monkeypatch):
        import main as main_mod

        main_mod.main(["templates"])
        assert main_mod._STDERR_PRINTER is not None
