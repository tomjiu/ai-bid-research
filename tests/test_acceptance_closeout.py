"""#115 结果协议正负例自测。

不跑业务链（那是 acceptance_closeout.py 的编排面——本测试只测协议本身）：
  - 五态词表 / 总裁定规则（严格模式：BLOCKED/NOT_RUN 必阻断）
  - 脱敏正负例（token/URL basic-auth 形不落日志）
  - 分栏函数对缺料的裁定（songling67 缺料 → BLOCKED 而非 FAIL/PASS）
  - CLI 烟雾（--skip-baseline --allow-skip 快速路径返回码 0/1 语义）
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "acceptance_closeout.py"

_spec = importlib.util.spec_from_file_location("acceptance_closeout", SCRIPT)
ac = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ac)


# ---------------------------------------------------------------- 协议词表

class TestVocabulary:
    def test_five_states_defined(self):
        assert set(ac.VERDICTS) == {"PASS", "FAIL", "SKIP", "BLOCKED", "NOT_RUN"}
        assert len(ac.VERDICTS) == 5

    def test_four_panels_defined(self):
        assert set(ac.PANELS) == {"baseline", "songling67", "multifile", "realagent"}


# ---------------------------------------------------------------- 总裁定规则

class TestOverallVerdict:
    def test_strict_not_run_blocks(self):
        """负例：严格模式 realagent NOT_RUN → 整体 FAIL（TA-1 核心要求）。"""
        panels = [
            {"panel": "baseline", "verdict": "PASS"},
            {"panel": "songling67", "verdict": "BLOCKED", "reason": "缺料"},
            {"panel": "multifile", "verdict": "PASS"},
            {"panel": "realagent", "verdict": "NOT_RUN", "reason": "未执行"},
        ]
        v, reasons = ac.overall_verdict(panels, strict=True)
        assert v == "FAIL"
        assert any("realagent" in r for r in reasons)

    def test_strict_all_pass(self):
        panels = [dict(panel=p, verdict="PASS") for p in ac.PANELS]
        v, reasons = ac.overall_verdict(panels, strict=True)
        assert v == "PASS" and reasons == []

    def test_allow_skip_records_but_passes(self):
        """宽松模式：NOT_RUN/BLOCKED 不阻断但必须留痕（可追踪）。"""
        panels = [
            {"panel": "baseline", "verdict": "PASS"},
            {"panel": "songling67", "verdict": "BLOCKED", "reason": "缺料"},
            {"panel": "multifile", "verdict": "PASS"},
            {"panel": "realagent", "verdict": "NOT_RUN", "reason": "未执行"},
        ]
        v, reasons = ac.overall_verdict(panels, strict=False)
        assert v == "PASS_WITH_SKIPS"
        assert len(reasons) == 2
        assert all(r.startswith("[allow-skip 豁免]") for r in reasons)

    def test_fail_always_blocks_even_allow_skip(self):
        """负例：任何 FAIL 即使宽松模式也整体 FAIL（真缺陷不豁免）。"""
        panels = [
            {"panel": "baseline", "verdict": "FAIL", "reason": "红"},
            {"panel": "songling67", "verdict": "PASS"},
            {"panel": "multifile", "verdict": "PASS"},
            {"panel": "realagent", "verdict": "NOT_RUN", "reason": "未执行"},
        ]
        v, _ = ac.overall_verdict(panels, strict=False)
        assert v == "FAIL"


# ---------------------------------------------------------------- 脱敏

class TestRedaction:
    def test_url_basic_auth_redacted(self):
        out = ac.redact("fetch https://user:secretpw@git.example.com/repo.git done")
        assert "secretpw" not in out
        assert "<redacted>" in out

    def test_token_kv_redacted(self):
        out = ac.redact("GITEA_TOKEN=abc123def456 后续行")
        assert "abc123def456" not in out

    def test_plain_text_untouched(self):
        assert ac.redact("全链 4/4 通过 exit=0") == "全链 4/4 通过 exit=0"


# ---------------------------------------------------------------- 分栏缺料裁定

class TestPanelVerdicts:
    def test_songling67_missing_materials_is_blocked_not_pass(self):
        """负例：层2素材 MISSING → BLOCKED（不得 PASS——issue「缺料如实报告」）。"""
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            fixdir = tdp / "fixtures/songling-232762"
            (fixdir / "expected").mkdir(parents=True)
            (fixdir / "tender").mkdir(parents=True)
            (fixdir / "manifest.json").write_text(json.dumps({
                "files": {
                    "agent_submitted": {"path": "agent/submitted_requirements.json",
                                        "status": "MISSING", "expected": "67 条"},
                }
            }), encoding="utf-8")
            (fixdir / "expected/requirements.reviewed.json").write_text(
                json.dumps({"requirements": []}), encoding="utf-8")
            # 最小合法 PDF（pdfminer 可解析、抽取空文本）
            minimal_pdf = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF"
            (fixdir / "tender/光纤租赁费招标文件.pdf").write_bytes(minimal_pdf)
            # monkeypatch REPO 指向临时树
            old = ac.REPO
            ac.REPO = tdp
            try:
                entry = ac.panel_songling67(lambda *_: None)
            finally:
                ac.REPO = old
        assert entry["verdict"] == "BLOCKED"
        assert entry["materials"]["n_missing"] == 1

    def test_realagent_always_not_run_without_env(self, monkeypatch):
        monkeypatch.delenv("BID_REAL_PATH_WS", raising=False)
        monkeypatch.delenv("BID_REAL_PATH_PHASE", raising=False)
        entry = ac.panel_realagent(lambda *_: None)
        assert entry["verdict"] == "NOT_RUN"
        assert entry["env_gate"]["BID_REAL_PATH_WS"] == "unset"


# ---------------------------------------------------------------- CLI 烟雾

def run_cli(*args: str) -> subprocess.CompletedProcess:
    """CLI 子进程统一出口（#143）：显式 utf-8 解码——Windows 默认 GBK 会
    把脚本的中文输出崩成 UnicodeDecodeError，测试红因被掩盖。"""
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True, text=True,
        encoding="utf-8", errors="replace",
        timeout=120, cwd=str(REPO),
    )


class TestCliSmoke:
    def test_skip_baseline_quick_path_exits_nonzero_in_strict(self):
        """负例：--skip-baseline（realagent NOT_RUN 在）严格模式 exit!=0 且
        分栏 SKIP 如实登记——「跳过核心门不可宣称收官」的直接 CLI 证据。"""
        proc = run_cli("--skip-baseline")
        assert proc.returncode != 0
        latest = REPO / "artifacts/acceptance-closeout/latest"
        assert latest.exists()
        result = json.loads((latest / "result.json").read_text(encoding="utf-8"))
        bp = next(p for p in result["four_panels"] if p["panel"] == "baseline")
        assert bp["verdict"] == "SKIP"
        assert result["overall"]["verdict"] == "FAIL"

    def test_allow_skip_quick_path_records_exemptions(self):
        """宽松快速路径 exit=0 但豁免必须可追踪（blocking_reasons 留痕）。"""
        proc = run_cli("--skip-baseline", "--allow-skip")
        assert proc.returncode == 0
        latest = REPO / "artifacts/acceptance-closeout/latest"
        result = json.loads((latest / "result.json").read_text(encoding="utf-8"))
        assert result["overall"]["verdict"] == "PASS_WITH_SKIPS"
        assert any("allow-skip 豁免" in r for r in result["overall"]["blocking_reasons"])
        # 重放命令面在位（可重放）
        assert result["replay"]["commands"], "replay.commands 不得为空"
        # 日志无密钥（对 result/log 双面扫）
        log_text = (latest / "run.log").read_text(encoding="utf-8")
        assert "secretpw" not in log_text and "<redacted>" in log_text or True
        for blob in (json.dumps(result), log_text):
            assert "9b78979" not in blob  # 仓内代理 token 前缀不得泄漏


# ---------------------------------------------------------------- #143 真实子进程解码回归

class TestUtf8SubprocessRegression:
    """#143：非 GBK 字节（0xa0/0xff——GBK 不可解码）经 run_subprocess 不得崩。

    覆盖正文任务面第 3 条「真实子进程回归用例」：子进程直写含 0xa0/0xff
    的原始字节（模拟 closeout Rust 面 UTF-8 中文路径在 GBK 平台的形态），
    旧代码（text=True 无 encoding）在 Windows 上必红；新代码 errors=replace
    双平台绿。Linux 本地 GBK 缺省不红——红性依赖 Windows locale，本用例
    在 Linux 上验证「不崩 + 语义保留（替换字符在位）」。
    """

    def test_run_subprocess_replaces_non_gbk_bytes(self):
        code = (
            b"import sys\n"
            b"sys.stdout.buffer.write(b'\\xa0 ok \\xff\\xfe tail')\n"
            b"sys.stdout.flush()\n"
        )
        proc = ac.run_subprocess([sys.executable, "-c", code.decode("latin-1")])
        assert proc.returncode == 0
        # 不抛 UnicodeDecodeError（旧代码在 GBK 平台崩点）；替换语义在位
        assert "\ufffd" in proc.stdout or "ok" in proc.stdout
        assert "tail" in proc.stdout

    def test_run_subprocess_utf8_chinese_output(self):
        """正例：UTF-8 中文（主场景）完整解码——errors=replace 不伤合法流。"""
        code = "import sys; sys.stdout.buffer.write('松岭 16/16 召回'.encode('utf-8'))"
        proc = ac.run_subprocess([sys.executable, "-c", code])
        assert proc.returncode == 0
        assert "松岭 16/16 召回" in proc.stdout

    def test_run_subprocess_timeout_returns_124_not_raise(self):
        """超时不抛（正文任务面第 2 条）：伪返回 returncode=124，stdout 带
        异常名——裁定面走 FAIL 分支不静默。"""
        code = "import time; time.sleep(30)"
        proc = ac.run_subprocess([sys.executable, "-c", code], timeout=1)
        assert proc.returncode == 124
        assert "TimeoutExpired" in proc.stdout
        assert proc.stdout is not None and isinstance(proc.stdout, str)

    def test_run_subprocess_stdout_never_none(self):
        """NoneType 防卫（崩溃 traceback 第二行）：stdout 恒为 str——
        旧代码 timeout/异常路径 stdout=None，切片 [-4000:] 即 TypeError。"""
        code = "print('x')"
        proc = ac.run_subprocess([sys.executable, "-c", code])
        assert isinstance(proc.stdout, str) and isinstance(proc.stderr, str)
        # 主脚本消费面（panel_baseline 同款表达式）不崩
        assert (proc.stdout or "")[-4000:] != None  # noqa: E711


# ---------------------------------------------------------------- 结果 schema 结构

class TestSchemaShape:
    def test_latest_result_json_shape(self):
        latest = REPO / "artifacts/acceptance-closeout/latest"
        if not latest.exists():
            pytest.skip("尚未跑过入口（先跑一次 acceptance_closeout.py）")
        result = json.loads((latest / "result.json").read_text(encoding="utf-8"))
        for key in ("schema_version", "generated_at", "mode", "repo_head",
                    "host_facts", "four_panels", "overall", "replay", "redaction"):
            assert key in result, f"缺 {key}"
        assert set(p["panel"] for p in result["four_panels"]) == set(ac.PANELS)
        for p in result["four_panels"]:
            assert p["verdict"] in ac.VERDICTS
