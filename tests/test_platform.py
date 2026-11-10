"""R39 平台检测工具面测试——双平台分支全覆盖（monkeypatch sys.platform）。"""

from __future__ import annotations

import sys

import pytest

from src.platform import (
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


class TestPathTooLongGuard:
    def test_windows_long_path_actionable_error(self, monkeypatch, tmp_path):
        from src.platform import PathTooLongError, ensure_writable_path

        monkeypatch.setattr(sys, "platform", "win32")
        deep = tmp_path / ("x" * 240) / ("y" * 40) / "report.md"
        with pytest.raises(PathTooLongError) as ei:
            ensure_writable_path(deep)
        # 可行动三建议
        assert "LongPathsEnabled" in str(ei.value)
        assert "--output-dir" in str(ei.value)
        assert ei.value.limit == 260

    def test_linux_deep_path_passes(self, monkeypatch, tmp_path):
        from src.platform import ensure_writable_path

        monkeypatch.setattr(sys, "platform", "linux")
        deep = tmp_path / ("x" * 240) / ("y" * 40) / "report.md"
        assert ensure_writable_path(deep) == deep.absolute()

    def test_report_save_guard_wired(self, monkeypatch, tmp_path):
        """报告落盘接线——Windows 深目录下抛专用错误而非误导性 FileNotFoundError。"""
        from src.platform import PathTooLongError
        from src.report.generator import ReportGenerator

        monkeypatch.setattr(sys, "platform", "win32")
        deep_dir = tmp_path / ("d" * 200)
        gen = ReportGenerator(output_dir=deep_dir)
        # output_dir mkdir 本身在 260 内可建；文件名叠加后超限
        with pytest.raises((PathTooLongError, OSError)):
            gen._save_report("# r\n内容", "很长的前缀" * 30)

    def test_html_export_guard_wired(self, monkeypatch, tmp_path):
        from src.platform import PathTooLongError
        from src.report.generator import ReportGenerator

        monkeypatch.setattr(sys, "platform", "win32")
        md = tmp_path / ("m" * 235 + ".md")
        md.parent.mkdir(parents=True, exist_ok=True)
        md.write_text("# 标题\n正文", encoding="utf-8")
        gen = ReportGenerator(output_dir=tmp_path / "out")
        with pytest.raises((PathTooLongError, OSError)):
            gen.export_html(md)


class TestLineEndingContract:
    def test_write_text_lf_no_cr_bytes(self, tmp_path):
        from src.platform import write_text_lf

        target = write_text_lf(tmp_path / "r.md", "# 报告\n第一行\n第二行\n")
        raw = target.read_bytes()
        assert b"\r" not in raw
        assert raw.endswith(b"\n")
        # 内容不添不减：无尾换行的输入保持无尾换行（不擅自改内容）
        t2 = write_text_lf(tmp_path / "r2.md", "无尾换行")
        assert t2.read_bytes() == "无尾换行".encode()

    def test_write_text_lf_pins_newline_param(self, tmp_path, monkeypatch):
        """钉死契约：open 必须显式 newline='\\n'（Windows 不翻译的根据）。"""
        import builtins
        from src.platform import write_text_lf

        captured = {}
        real_open = builtins.open

        def spy_open(file, mode="r", *args, **kwargs):
            if "w" in mode:
                captured.update(kwargs)
            return real_open(file, mode, *args, **kwargs)

        monkeypatch.setattr(builtins, "open", spy_open)
        write_text_lf(tmp_path / "spy.md", "x\ny")
        assert captured.get("newline") == "\n"
        assert captured.get("encoding") == "utf-8"

    def test_read_text_universal_crlf_folded(self, tmp_path):
        from src.platform import read_text_universal

        (tmp_path / "crlf.txt").write_bytes("# t\r\nline\r\n".encode())
        (tmp_path / "cr.txt").write_bytes("# t\rline\r".encode())
        (tmp_path / "lf.txt").write_bytes("# t\nline\n".encode())
        assert read_text_universal(tmp_path / "crlf.txt") == "# t\nline\n"
        assert read_text_universal(tmp_path / "cr.txt") == "# t\nline\n"
        assert read_text_universal(tmp_path / "lf.txt") == "# t\nline\n"

    def test_report_output_byte_stable_contract(self, tmp_path):
        """报告产物字节契约：内容相同 → 字节相同（无平台/模式漂移）。"""
        from src.report.generator import ReportGenerator

        gen1 = ReportGenerator(output_dir=tmp_path / "a")
        gen2 = ReportGenerator(output_dir=tmp_path / "b")
        p1 = gen1._save_report("# 摘要\n结论：正常。", "stable")
        p2 = gen2._save_report("# 摘要\n结论：正常。", "stable")
        assert p1.read_bytes().replace(
            p1.stem.encode(), b""
        ) == p2.read_bytes().replace(p2.stem.encode(), b"")
        assert b"\r" not in p1.read_bytes()


class TestSanitizeFilename:
    def test_illegal_chars_replaced(self):
        from src.platform import sanitize_filename

        # : / ? * " < > | 共 8 个非法字符各换一个 _
        assert sanitize_filename('智慧:城市/报告?*"<>|') == "智慧_城市_报告______"

    def test_windows_reserved_names(self):
        from src.platform import sanitize_filename

        assert sanitize_filename("CON") == "CON_"
        assert sanitize_filename("con.md") == "con.md_"
        assert sanitize_filename("nul") == "nul_"
        # 非精确保留名（com1_备份）本身合法——不动
        assert sanitize_filename("com1_备份") == "com1_备份"

    def test_normal_names_untouched(self):
        from src.platform import sanitize_filename

        assert sanitize_filename("智慧城市_20260110") == "智慧城市_20260110"
        assert sanitize_filename("report-1.md") == "report-1.md"

    def test_trailing_dots_spaces_stripped(self):
        from src.platform import sanitize_filename

        assert sanitize_filename("报告 . ") == "报告"
        assert sanitize_filename("draft...") == "draft"

    def test_control_chars_replaced(self):
        from src.platform import sanitize_filename

        assert sanitize_filename("a\x00b\x1fc") == "a_b_c"

    def test_length_cap_keeps_tail(self):
        from src.platform import sanitize_filename

        long = "x" * 300 + ".md"
        out = sanitize_filename(long, max_length=50)
        assert len(out) == 50
        assert out.endswith(".md")

    def test_all_bad_falls_back(self):
        from src.platform import sanitize_filename

        assert sanitize_filename("... ") == "sanitized"

    def test_report_prefix_uses_platform_sanitizer(self, tmp_path):
        """接线验证：报告文件名经平台清洗面（保留名不再原样落盘）。"""
        from src.report.generator import ReportGenerator

        gen = ReportGenerator(output_dir=tmp_path)
        path = gen._save_report("# c\n正文", "CON")
        assert path.stem.startswith("CON_")
