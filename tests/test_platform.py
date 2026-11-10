"""R39 平台检测工具面测试——双平台分支全覆盖（monkeypatch sys.platform）。"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from src.platform import (
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

    def test_no_encoding_attr_is_safe(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "linux")

        class _NoEnc:
            pass

        monkeypatch.setattr(sys, "stdout", _NoEnc())
        assert console_encoding_safe() is True


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
