"""eval 子命令 CLI 测试 + 真实 API 端到端（环境门）（#601 批次 E·R23）。"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

import main as cli

FIXTURES = Path(__file__).parent.parent / "fixtures" / "announcements"
GOLD = FIXTURES / "gold-extraction.json"


class TestEvalCLI:
    def test_rule_mode_full(self, capsys):
        code = cli.main(["eval", "--gold", str(GOLD)])
        assert code == 0
        out = capsys.readouterr().out
        assert "抽取质量评估（rule）" in out
        assert "字段命中率 100.0%（14/14）" in out
        assert "bid_id: 2/2" in out

    def test_texts_dir_override(self, capsys, tmp_path):
        texts = tmp_path / "texts"
        texts.mkdir()
        (texts / "hlj-smartcity.txt").write_text(
            (FIXTURES / "raw" / "hlj-smartcity.txt").read_text(
                encoding="utf-8"
            ),
            encoding="utf-8",
        )
        code = cli.main(
            ["eval", "--gold", str(GOLD), "--texts", str(texts)]
        )
        # 只有 1/3 语料在场：hlj 命中；zj-cloud 缺文本（未命中标注字段）；
        # noise 缺文本（预期失败但无法评估 → verdict 不一致）
        out = capsys.readouterr().out
        assert "抽取质量评估" in out
        assert code in (0, 1)  # 缺件评估的退出码依命中率而定

    def test_missing_gold_exit_2(self, tmp_path, capsys):
        code = cli.main(["eval", "--gold", str(tmp_path / "nope.json")])
        assert code == 2
        assert "不存在" in capsys.readouterr().err

    def test_bad_gold_exit_2(self, tmp_path, capsys):
        bad = tmp_path / "bad.json"
        bad.write_text('["array"]', encoding="utf-8")
        (tmp_path / "raw").mkdir()  # 目录先就位——让错误落在 gold 装载
        code = cli.main(["eval", "--gold", str(bad)])
        assert code == 2
        assert "不可用" in capsys.readouterr().err

    def test_api_mode_without_key_exit_2(self, capsys, monkeypatch):
        monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        code = cli.main(["eval", "--gold", str(GOLD), "--mode", "api"])
        assert code == 2
        assert "DEEPSEEK_API_KEY" in capsys.readouterr().err

    def test_missing_texts_dir_exit_2(self, tmp_path, capsys):
        code = cli.main(
            ["eval", "--gold", str(GOLD), "--texts", str(tmp_path / "nope")]
        )
        assert code == 2
        assert "原文目录不存在" in capsys.readouterr().err

    def test_help_registered(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            cli.main(["--help"])
        assert exc_info.value.code == 0
        assert "eval" in capsys.readouterr().out


class TestRealAPIEndToEnd:
    """真实 API 端到端（#601 批次 E）——环境门：无密钥显式 SKIP。

    与仓内「测试环境门」纪律一致（AGENTS.md 三之二）：
    SKIP 不是通过也不是失败——本环境无法验证。
    """

    def test_llm_extraction_on_synthetic_gold(self, capsys):
        api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv(
            "OPENAI_API_KEY"
        )
        if not api_key:
            print(
                "=" * 60
                + "\nSKIP: test_llm_extraction_on_synthetic_gold\n"
                "reason: ENV_MISSING: DEEPSEEK_API_KEY / OPENAI_API_KEY\n"
                "补救: export DEEPSEEK_API_KEY=... 后重跑本测试\n"
                + "=" * 60
            )
            return

        code = cli.main(["eval", "--gold", str(GOLD), "--mode", "api"])
        out = capsys.readouterr().out
        # 真实 API 只断言「评估完成且产出命中率数字」——
        # LLM 输出有方差，不设硬阈值（那是 rule 基线的事）
        assert code in (0, 1)
        assert "抽取质量评估（api）" in out
        assert "字段命中率" in out
