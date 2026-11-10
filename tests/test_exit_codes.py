"""退出码规范测试（#601 R70）——各语义路径的码稳定性锁定。"""

import pytest

import main as main_mod
from src.exit_codes import (
    EXIT_CODE_TABLE,
    EXIT_DATA,
    EXIT_LLM,
    EXIT_OK,
    EXIT_USAGE,
    describe_exit_code,
)


class TestExitCodeContract:
    def test_constants(self):
        assert (EXIT_OK, EXIT_USAGE, EXIT_DATA, EXIT_LLM) == (0, 1, 2, 3)

    def test_describe(self):
        assert describe_exit_code(0).startswith("成功")
        assert "数据/环境错误" in describe_exit_code(2)
        assert "未定义" in describe_exit_code(99)

    def test_table_mentions_all_codes(self):
        for code in ("0", "1", "2", "3"):
            assert code in EXIT_CODE_TABLE


class TestExitPaths:
    def test_ok_path(self, tmp_path, capsys):
        rc = main_mod.main(["templates"])
        assert rc == EXIT_OK

    def test_usage_path_unknown_flag(self, capsys):
        """argparse 用法错误退 2（与其自身惯例一致——如实入规范）。"""
        with pytest.raises(SystemExit) as ei:
            main_mod.main(["analyze", "--no-such-flag"])
        assert ei.value.code == EXIT_DATA

    def test_data_path_missing_db(self, tmp_path, capsys):
        rc = main_mod.main(
            ["db", "--db", str(tmp_path / "ghost.db"), "--stats"]
        )
        assert rc == EXIT_DATA

    def test_data_path_missing_source(self, tmp_path, capsys):
        rc = main_mod.main(
            ["collect", "--source", str(tmp_path / "nope.json"),
             "--db", str(tmp_path / "x.db")]
        )
        assert rc == EXIT_DATA

    def test_bad_json_tolerant_mode_degrades_to_ok(self, tmp_path, capsys):
        """容忍模式：坏 JSON 登记 failure 后继续——进程级是 0。"""
        bad = tmp_path / "bad.json"
        bad.write_text("{oops", encoding="utf-8")
        rc = main_mod.main(
            ["collect", "--source", str(bad),
             "--db", str(tmp_path / "x.db")]
        )
        assert rc == EXIT_OK
        assert "失败" in capsys.readouterr().out

    def test_bad_json_strict_mode_is_data_error(self, tmp_path):
        bad = tmp_path / "bad.json"
        bad.write_text("{oops", encoding="utf-8")
        rc = main_mod.main(
            ["collect", "--source", str(bad), "--strict",
             "--db", str(tmp_path / "x.db")]
        )
        assert rc == EXIT_DATA

    def test_data_path_retry_without_key(self, tmp_path, monkeypatch):
        monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("DEEPSEEK_BASE_URL", raising=False)
        rc = main_mod.main(
            ["extract", "--db", str(tmp_path / "e.db"), "--retry"]
        )
        assert rc == EXIT_DATA

    def test_help_tail_lists_codes(self, capsys):
        # main() 直调：无 command 落到 print_help + return 1（帮助面码）
        rc = main_mod.main([])
        assert rc == EXIT_USAGE  # 1 = 无子命令专用
        err = capsys.readouterr().err
        assert "退出码" in err
        assert "docs/USER-GUIDE.md" in err
