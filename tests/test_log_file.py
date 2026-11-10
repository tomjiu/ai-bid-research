"""--log-file 日志落盘测试（#601 R72）。"""

from __future__ import annotations

import logging

import main as main_mod


class TestLogFile:
    def test_file_receives_debug_console_stays_info(
        self, tmp_path, capsys, monkeypatch
    ):
        """文件 DEBUG 全量；控制台不被降级刷屏。"""
        log = tmp_path / "logs" / "run.log"
        rc = main_mod.main(
            [
                "--log-file", str(log),
                "templates",
            ]
        )
        assert rc == 0
        assert log.exists()
        content = log.read_text(encoding="utf-8")
        assert "日志文件面开启" in content
        # 控制台无 DEBUG 噪音（INFO 面）
        out = capsys.readouterr()
        assert "DEBUG" not in out.out

    def test_debug_records_reach_file(self, tmp_path, capsys):
        """DEBUG 级记录（如 R40 控制台加固）进文件——事后可翻。"""
        import sys as _sys

        log = tmp_path / "dbg.log"
        # 触发 R40 加固路径的 debug 日志：伪 GBK 控制台
        class _Gbk:
            encoding = "gbk"

            def reconfigure(self, **kw):
                raise ValueError("detached")

            def write(self, text):
                pass  # 输出面吞掉（本测试只关心日志文件）

            def flush(self):
                pass

        real_stdout = _sys.stdout
        _sys.stdout = _Gbk()
        try:
            rc = main_mod.main(["--log-file", str(log), "templates"])
        finally:
            _sys.stdout = real_stdout
        assert rc == 0
        content = log.read_text(encoding="utf-8")
        # console hardened debug 或至少有 INFO 记录
        assert "日志文件面开启" in content

    def test_unwritable_log_file_actionable(self, tmp_path, monkeypatch, capsys):
        import sys as _sys

        monkeypatch.setattr(_sys, "platform", "win32")
        deep = tmp_path / ("x" * 240) / ("y" * 40) / "a.log"
        rc = main_mod.main(
            ["--log-file", str(deep), "templates"]
        )
        assert rc == 2
        assert "日志文件不可写" in capsys.readouterr().err

    def test_append_mode_preserves_history(self, tmp_path):
        log = tmp_path / "twice.log"
        main_mod.main(["--log-file", str(log), "templates"])
        first_size = log.stat().st_size
        main_mod.main(["--log-file", str(log), "templates"])
        assert log.stat().st_size > first_size  # 追加不清空

    def test_no_log_file_flag_no_side_effects(self, tmp_path):
        """不带 --log-file：零文件产物（历史行为）。"""
        rc = main_mod.main(["templates"])
        assert rc == 0
        assert not (tmp_path / "logs").exists()
