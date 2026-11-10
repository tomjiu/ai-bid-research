"""R39 平台检测工具面测试——双平台分支全覆盖（monkeypatch sys.platform）。"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from src.platform import (
    _stream_can_encode_chinese,
    configure_console_safe,
    console_encoding_safe,
    filesystem_case_sensitive,
    is_linux,
    is_macos,
    is_windows,
    max_path_length,
    normalize_path_key,
    path_too_long,
    platform_label,
)


class TestPlatformBooleans:
    def test_windows_branch(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "win32")
        assert is_windows() is True
        assert is_linux() is False
        assert is_macos() is False
        assert platform_label() == "windows"

    def test_linux_branch(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "linux")
        assert is_windows() is False
        assert is_linux() is True
        assert platform_label() == "linux"

    def test_macos_branch(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "darwin")
        assert is_macos() is True
        assert platform_label() == "macos"

    def test_unknown_platform(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "freebsd14")
        assert platform_label() == "other"
        assert is_windows() is False


class TestMaxPath:
    def test_windows_260(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "win32")
        assert max_path_length() == 260

    def test_linux_4096(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "linux")
        assert max_path_length() == 4096

    def test_path_too_long_windows(self, monkeypatch, tmp_path):
        monkeypatch.setattr(sys, "platform", "win32")
        deep = tmp_path.joinpath("x" * 240, "y" * 30, "report.md")
        assert path_too_long(deep) is True
        assert path_too_long(tmp_path / "a.md") is False

    def test_path_too_long_linux_generous(self, monkeypatch, tmp_path):
        monkeypatch.setattr(sys, "platform", "linux")
        deep = tmp_path.joinpath("x" * 240, "y" * 30, "report.md")
        assert path_too_long(deep) is False


class TestCaseSensitivity:
    def test_windows_case_insensitive(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "win32")
        assert filesystem_case_sensitive() is False

    def test_linux_case_sensitive(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "linux")
        assert filesystem_case_sensitive() is True

    def test_windows_path_key_folds(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "win32")
        assert normalize_path_key("Data\\Bids.DB") == "data/bids.db"

    def test_linux_key_preserves_case(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "linux")
        assert normalize_path_key("Data/Bids.DB") == "Data/Bids.DB"
        # 盘符样式路径（Windows 配置迁移）仍折叠
        assert normalize_path_key("C:/Data/Bids.DB") == "c:/data/bids.db"


class TestConsoleEncoding:
    def test_utf8_safe(self, monkeypatch, fake_stdout_factory):
        monkeypatch.setattr(sys, "platform", "linux")
        fake = fake_stdout_factory("utf-8")
        monkeypatch.setattr(sys, "stdout", fake)
        assert console_encoding_safe() is True

    def test_gbk_chinese_capable(self, monkeypatch, fake_stdout_factory):
        # GBK 能编码「招标公告测试」——虽非 UTF-8 也不炸
        monkeypatch.setattr(sys, "platform", "win32")
        fake = fake_stdout_factory("gbk")
        monkeypatch.setattr(sys, "stdout", fake)
        assert console_encoding_safe() is True

    def test_ascii_unsafe_for_chinese(self, monkeypatch, fake_stdout_factory):
        monkeypatch.setattr(sys, "platform", "win32")
        fake = fake_stdout_factory("ascii")
        monkeypatch.setattr(sys, "stdout", fake)
        assert console_encoding_safe() is False

    def test_no_encoding_attr_unverified(self, monkeypatch):
        # 编码属性缺失 → 未验证 → 不安全（防御性语义，与加固面一致）
        monkeypatch.setattr(sys, "platform", "linux")

        class _NoEnc:
            pass

        monkeypatch.setattr(sys, "stdout", _NoEnc())
        assert console_encoding_safe() is False


@pytest.fixture
def fake_stdout_factory():
    """构造带指定 encoding 属性的 stdout 替身。"""

    def _make(encoding: str):
        class _Fake:
            pass

        obj = _Fake()
        obj.encoding = encoding
        return obj

    return _make


class TestConfigureConsoleSafe:
    def _fake_stream(self, encoding: str, can_reconfigure: bool = True):
        class _FakeStream:
            def __init__(self):
                self.encoding = encoding
                self.reconfigure_kwargs = None
                if can_reconfigure:
                    self.calls = []

            def reconfigure(self, **kwargs):
                self.reconfigure_kwargs = kwargs

        return _FakeStream() if can_reconfigure else object()

    def test_gbk_stream_gets_replace(self, monkeypatch):
        import src.platform as plat

        out = self._fake_stream("gbk")
        # 让中文可编码但方框图不可——模拟 cp936 真实短板
        monkeypatch.setattr(plat, "_stream_can_encode_chinese", lambda s: False)
        monkeypatch.setattr(sys, "stdout", out)
        monkeypatch.setattr(sys, "stderr", self._fake_stream("utf-8"))
        actions = plat.configure_console_safe()
        assert "stdout:errors=replace" in actions
        assert out.reconfigure_kwargs == {"errors": "replace"}

    def test_utf8_streams_untouched(self, monkeypatch):
        monkeypatch.setattr(sys, "stdout", self._fake_stream("utf-8"))
        monkeypatch.setattr(sys, "stderr", self._fake_stream("UTF-8"))
        assert configure_console_safe() == []

    def test_non_reconfigurable_stream_skipped(self, monkeypatch):
        # 无 reconfigure 方法的流（如 StringIO 特化或已 detach）不炸
        monkeypatch.setattr(sys, "stdout", self._fake_stream("ascii", False))
        monkeypatch.setattr(sys, "stderr", self._fake_stream("utf-8"))
        assert configure_console_safe() == []

    def test_reconfigure_failure_swallowed(self, monkeypatch):
        class _Exploding:
            encoding = "ascii"

            def reconfigure(self, **kwargs):
                raise ValueError("underlying buffer is detached")

        monkeypatch.setattr(sys, "stdout", _Exploding())
        monkeypatch.setattr(sys, "stderr", _Exploding())
        assert configure_console_safe() == []

    def test_ascii_stream_flagged(self, monkeypatch):
        monkeypatch.setattr(sys, "stdout", self._fake_stream("ascii"))
        monkeypatch.setattr(sys, "stderr", self._fake_stream("ascii"))
        actions = configure_console_safe()
        assert len(actions) == 2

    def test_can_encode_chinese_detection(self):
        assert _detect("utf-8") is True
        assert _detect("gbk") is True  # GBK 覆盖常用汉字
        assert _detect("ascii") is False
        assert _detect("") is False  # 无编码信息 → 未验证 → 加固


def _detect(encoding: str) -> bool:
    from src.platform import _stream_can_encode_chinese

    class _S:
        pass

    s = _S()
    s.encoding = encoding
    return _stream_can_encode_chinese(s)


class TestMainWiring:
    def test_console_hardening_before_any_output(self, monkeypatch, capsys):
        # main() 先加固再解析——GBK 控制台下 --help 含中文不崩
        import main as main_mod

        hardened = []
        monkeypatch.setattr(
            main_mod, "configure_console_safe", lambda: hardened.append(1) or []
        )
        rc = main_mod.main(["templates"])
        assert hardened == [1]
        assert rc == 0
