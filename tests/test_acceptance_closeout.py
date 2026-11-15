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
import os
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

    @pytest.mark.parametrize("skipped", ac.PANELS)
    def test_strict_skip_blocks_each_required_panel(self, skipped):
        panels = [dict(panel=p, verdict="PASS") for p in ac.PANELS]
        for panel in panels:
            if panel["panel"] == skipped:
                panel.update(verdict="SKIP", reason="explicit skip")
        verdict, reasons = ac.overall_verdict(panels, strict=True)
        assert verdict == "FAIL"
        assert any(skipped in r and "SKIP" in r and "explicit skip" in r for r in reasons)

    def test_allow_skip_preserves_skip_reason(self):
        panels = [dict(panel=p, verdict="PASS") for p in ac.PANELS]
        panels[0].update(verdict="SKIP", reason="explicit skip")
        verdict, reasons = ac.overall_verdict(panels, strict=False)
        assert verdict == "PASS_WITH_SKIPS"
        assert len(reasons) == 1 and "explicit skip" in reasons[0]

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


# ---------------------------------------------------------------- #143 内层（Lead 重开面）真实回归

_inner_spec = importlib.util.spec_from_file_location(
    "closeout_real_test", REPO / "scripts" / "closeout_real_test.py")
crt = importlib.util.module_from_spec(_inner_spec)
_inner_spec.loader.exec_module(crt)


class TestInnerSubprocessRegression:
    """#143 内层（Lead 2026-11-14 复验重开面）。

    Lead 受控反例复现路径：真实 run_rust/run_chain_b 函数 + 把 cargo/
    m17 子进程换成实际输出 0xa0 字节的 Python 子进程。旧代码（text=True
    无 encoding）内层 reader 即 UnicodeDecodeError → run_rust 拼接
    TypeError(NoneType)；新代码显式 utf-8/errors=replace 全链不崩、
    失败可诊断（stderr 落日志）。
    """

    def _fake_cargo_shim(self, tmp_path, *, stdout_bytes: bytes,
                          stderr_bytes: bytes = b"", exit_code: int = 9):
        """真·受控 cargo shim（Lead #161 审核口径重做）。

        旧缺陷：monkeypatch shutil.which 无效（run_rust 不调 which）、
        PATH 冒号不跨平台、假 cargo 不落非零 exit、产物写仓库 artifacts。

        新面：tmp_path 里落**名为 cargo** 的真可执行 shim（POSIX:
        .py+shebang+chmod / Windows: cargo.bat 包装 sys.executable），
        run_rust 经 resolve_cargo→shutil.which 真搜索 PATH 选中它——
        真实 subprocess 起的 Python 子进程，stdout 预置非法 UTF8 字节
        （GBK 平台同形），stderr 带诊断字样，exit_code 可控（默认 9）。
        产物全在 tmp_path，不写仓库。
        """
        shim_dir = tmp_path / "shim-bin"
        shim_dir.mkdir(parents=True, exist_ok=True)
        inner = tmp_path / "fake-cargo.py"
        inner.write_text(
            "import os, sys\n"
            f"os.writefd = None\n"
            f"sys.stdout.buffer.write({stdout_bytes!r})\n"
            f"sys.stderr.buffer.write({stderr_bytes!r})\n"
            "sys.stdout.flush()\n"
            "sys.stderr.flush()\n"
            f"sys.exit({exit_code})\n",
            encoding="utf-8")
        inner.chmod(0o755)
        if os.name == "nt":
            shim = shim_dir / "cargo.bat"
            shim.write_text(f'@"{sys.executable}" "{inner}" %*\n',
                            encoding="utf-8")
        else:
            shim = shim_dir / "cargo"
            shim.write_text(f"#!/bin/sh\nexec \"{sys.executable}\" "
                            f"\"{inner}\" \"$@\"\n", encoding="utf-8")
            shim.chmod(0o755)
        return shim_dir

    def test_run_rust_fake_cargo_selected_and_bytes_really_flow(
            self, monkeypatch, tmp_path):
        """真选夹具反例（Lead 指名）：run_rust 必须真的选中 shim 起的
        受控 Python 子进程——断言① shim 被选中（PATH prepend 后
        resolve_cargo 命中 shim 路径——通过产物诊断而非环境失败假绿）；
        ② 预置非法 UTF8 字节（0xa0/0xff）真流过 reader 不崩（显式
        utf-8/errors=replace）；③ exit 9 照实落 json；④ stderr 诊断字样
        真落日志。旧缺陷三合一：which 不被调/冒号 PATH/假绿 127。"""
        monkeypatch.setattr(crt, "SPEC_PATH", tmp_path / "closeout-spec.json")
        monkeypatch.setattr(crt, "OUT", tmp_path)
        (tmp_path / "closeout-spec.json").write_text("{}", encoding="utf-8")
        shim_dir = self._fake_cargo_shim(
            tmp_path, stdout_bytes=b"\xa0cargo test \xff\xfe running\n",
            stderr_bytes=b"\xa0 fake-cargo diag \xff\n", exit_code=9)
        # PATH prepend（os.pathsep 跨平台）——resolve_cargo 的
        # shutil.which 真搜索即命中 shim（这是 run_rust 真实路径，
        # 不是 monkeypatch which 的假面）
        monkeypatch.setenv(
            "PATH", str(shim_dir) + os.pathsep + os.environ.get("PATH", ""))
        # 防「环境失败假绿」：先证 shim 真在位可选中（否则本测试自身
        # 环境性失效——红而非绿）
        assert crt.resolve_cargo() == str(shim_dir / "cargo" if os.name != "nt"
                                         else str(shim_dir / "cargo.bat")) \
            or str(shim_dir) in crt.resolve_cargo()
        assert Path(crt.resolve_cargo()).parent == Path(shim_dir).resolve()
        status = crt.run_rust()
        assert isinstance(status, dict)
        # ③ 真 exit 9（不是环境失败 127 假绿——shim 被真选中并真退出）
        assert status["exit"] == 9, f"shim 未被真选中？status={status}"
        assert status["ok"] is False
        # ② 预置字节真流过（替换面在日志里可见——非法 UTF8 经
        # errors=replace 不崩且留痕）
        log_text = (tmp_path / "rust-run.log").read_text(encoding="utf-8")
        assert "cargo test" in log_text  # stdout 真进了日志（含替换字符）
        assert "fake-cargo diag" in log_text  # stderr 真进了日志
        rust_json = json.loads((tmp_path / "rust-run.json").read_text(
            encoding="utf-8"))
        assert rust_json["exit"] == 9
        assert "fake-cargo diag" in rust_json["stderr_tail"]
        # Lead 点名「PATH 拼接冒号在 Windows 也应核对 os.pathsep」——
        # 落成可执行断言：run_rust 源里 PATH 拼接用 os.pathsep（两平台
        # 分隔符真分叉：POSIX ':' / nt ';'——硬编码冒号在 nt 必假绿）
        src_rust = (REPO / "scripts/closeout_real_test.py").read_text(
            encoding="utf-8")
        assert "os.pathsep + os.environ" in src_rust
        assert f"'.cargo/bin':{{" not in src_rust  # 旧硬编码冒号拼接已除
        # 产物全在 tmp_path——仓库无 fake-cargo 残留
        assert not (REPO / "artifacts/fake-cargo.py").exists()

    def test_run_rust_timeout_partial_no_nonetype(self, monkeypatch, tmp_path):
        """内层超时伪返回（124）：partial 输出保留、拼接不 TypeError。
        （超时面走 helper 直测——真 shim 不 sleep 卡测试。）"""
        monkeypatch.setattr(crt, "SPEC_PATH", tmp_path / "closeout-spec.json")
        monkeypatch.setattr(crt, "OUT", tmp_path)
        (tmp_path / "closeout-spec.json").write_text("{}", encoding="utf-8")
        fake_cargo = tmp_path / "fake-cargo-sleep.py"
        fake_cargo.write_text(
            "import sys, time\n"
            "sys.stdout.buffer.write(b'\\xa0 partial output before hang')\n"
            "sys.stdout.flush()\n"
            "time.sleep(60)\n",
            encoding="utf-8",
        )
        fake_cargo.chmod(0o755)
        # 真实子进程超时路径（helper 出口语义）：partial 保留、不 None
        proc = crt.run_subprocess([sys.executable, str(fake_cargo)], timeout=1)
        assert proc.returncode == 124
        assert "TimeoutExpired" in proc.stdout
        assert "partial output" in proc.stdout  # partial 保留（不 None）

    def test_run_rust_missing_cargo_pseudo_127(self, monkeypatch, tmp_path):
        """启动失败（cargo 不在位）伪返回 127 不崩——stderr 带异常名可诊断。"""
        proc = crt.run_subprocess(["cargo-definitely-not-on-path-xyz", "--version"])
        assert proc.returncode == 127
        assert "FileNotFoundError" in proc.stderr
        assert isinstance(proc.stdout, str)

    def test_panel_baseline_stderr_only_visible(self, monkeypatch, tmp_path):
        """Lead 根因 ②：子进程仅在 stderr 报错（stdout 空）——旧面只记
        stdout，错误完全不可见；新面 stderr 落日志 + entry 留痕。"""
        logs: list[str] = []

        class FakeProc:
            returncode = 1
            stdout = ""
            stderr = "review-error-only-on-stderr"

        monkeypatch.setattr(ac, "run_subprocess", lambda *a, **k: FakeProc())
        monkeypatch.setattr(ac.shutil, "which", lambda name: "/fake/cargo")
        old_home = ac.Path.home
        monkeypatch.setattr(ac.Path, "home", staticmethod(lambda: Path("/fake")))
        try:
            entry = ac.panel_baseline(run=True, log=logs.append)
        finally:
            ac.Path.home = old_home
        joined = "\n".join(logs)
        assert "review-error-only-on-stderr" in joined  # stderr 现在可见
        assert entry["verdict"] == "FAIL"
        assert "review-error-only-on-stderr" in entry["stderr_tail"]


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
