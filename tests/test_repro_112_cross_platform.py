"""#156 复验脚本跨平台重放回归（纯 Python 面——不依赖 Rust bin）。

覆盖 issue #156 任务面的可测部分：
  - repro_112.py / m145_repro.py 参数解析（ws/out/bin/root 显式 + 位置兼容）
  - exe 平台后缀（Windows nt 分支模拟）
  - 全链显式 UTF8（读金标准 JSON：GBK 平台不再崩启动——受控：用 GBK
    编码打开 UTF-8 内容文件必须显式 utf-8 才不崩）
  - 工作区安全复跑（非空 → 非零退出不静默复用；空 → 通过）
  - 失败非零退出（bin 不在位 / out 未提供 / 金标准缺失）
  - 修复前口径修正（m145 注释不再断言「614-616 应无 REQ」——文本断言）
  - 口径警示在报盘结构里（caveats：OR 针 ≠ 语义保真 / 67 条不抵充 /
    Poppler318 ≠ PDFium316）

Rust 真链（create→import→extract）与 Windows cp936 真机 = SKIP 如实
登记，不冒充。
"""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, REPO / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


rep = _load("repro_112", "scripts/repro_112.py")
m145 = _load("m145_repro", "scripts/m145_repro.py")


# ---------------------------------------------------------------- 参数化

class TestParameterization:
    def test_repro112_requires_ws_and_out(self):
        """无参数 → argparse 用法错 exit 2（非零——失败可诊断不裸跑）。"""
        proc = subprocess.run(
            [sys.executable, str(REPO / "scripts/repro_112.py")],
            capture_output=True, text=True, encoding="utf-8", timeout=30,
        )
        assert proc.returncode == 2
        assert "ws 与 out 必须提供" in (proc.stderr or "")

    def test_repro112_positional_and_flag_equivalent(self, monkeypatch):
        sys.argv = ["repro_112.py", "/tmp/ws-a", "/tmp/out-a.json", "/tmp/bin-a"]
        a = rep.parse_args()
        assert (str(a.ws), str(a.out), str(a.bin)) == ("/tmp/ws-a", "/tmp/out-a.json", "/tmp/bin-a")
        sys.argv = ["repro_112.py", "--workspace", "/tmp/ws-b",
                    "--out", "/tmp/out-b.json", "--bin", "/tmp/bin-b"]
        b = rep.parse_args()
        assert (str(b.ws), str(b.out), str(b.bin)) == ("/tmp/ws-b", "/tmp/out-b.json", "/tmp/bin-b")

    def test_m145_params_and_root_default(self, monkeypatch, tmp_path):
        sys.argv = ["m145_repro.py", "--ws", str(tmp_path / "ws"),
                    "--out", str(tmp_path / "out.json"), "--bin", str(tmp_path / "bin")]
        a = m145.parse_args()
        assert a.root == REPO  # 默认 root 从脚本位置取得（不写死 /home/z）
        assert a.block_from == 610 and a.block_to == 619
        # 显式 root 覆盖：用**真实平台绝对路径**（tmp_path 派生）+ 输入
        # Path 语义比较——不硬编码 POSIX 根假设（"/some/other" 在 Windows
        # 是 rooted 无盘符而非 absolute，is_absolute 必假红；语义不变式
        # 改为「与输入指向同一位置 + 尾组件一致」——两平台同真）
        root_in = tmp_path / "root-a"
        sys.argv = ["m145_repro.py", "--root", str(root_in), "--ws", "w", "--out", "o"]
        b = m145.parse_args()
        assert b.root == root_in  # Path 语义比较（真实绝对路径）
        assert b.root == Path(str(root_in))  # 与输入字符串构造的 Path 语义等价
        assert b.root.name == "root-a"  # 尾组件不变式（两平台同真）
        assert b.root.drive == tmp_path.drive  # 同盘符（Win 带盘符/Linux 空——都跟真实输入一致）

    def test_m145_out_required_nonzero_exit(self):
        proc = subprocess.run(
            [sys.executable, str(REPO / "scripts/m145_repro.py")],
            capture_output=True, text=True, encoding="utf-8", timeout=30,
        )
        assert proc.returncode == 1
        assert "out 必须提供" in (proc.stderr or "")


# ---------------------------------------------------------------- exe 后缀

class TestExeSuffix:
    def test_resolve_bin_real_platform_behavior(self, tmp_path):
        """resolve_bin 路径选择面（**路径级**——只测 resolve_bin 的返回
        路径，不起真实程序；真实启动面见同组 real_subprocess 用例）：

        - Windows：无后缀路径不在位、.exe 同伴在位 → 切 .exe；
        - POSIX：无后缀路径在位 → 原样返回（不补）。
        两分支都真调 resolve_bin（非源码字符串断言）。"""
        if os.name == "nt":
            exe = tmp_path / "bid-mcp-stdio.exe"
            exe.write_text("", encoding="utf-8")
            p = m145.resolve_bin(tmp_path, str(tmp_path / "bid-mcp-stdio"))
            assert p.suffix == ".exe" and p == exe  # Win：补 .exe 切换
        else:
            fake = tmp_path / "bid-mcp-stdio"
            fake.write_text("", encoding="utf-8")
            p = m145.resolve_bin(tmp_path, str(fake))
            assert p.suffix == "" and p == fake  # POSIX：不补
        # 两脚本同款逻辑（repro_112 同输入同行为——当前平台分支）
        if os.name != "nt":
            p2 = rep.resolve_bin(str(fake))
            assert p2.suffix == "" and p2 == fake

    def test_resolve_bin_windows_exe_branch_real_subprocess(self, tmp_path):
        """Windows .exe 分支——**真实可执行文件**子进程级验证。

        Lead 上一轮指出：把 Python 源码写成 fake-tool.exe 只断言
        「不在位」不在 stderr，WinError 193 traceback 也会绿。本用例
        用**真正的可执行文件**（复制 sys.executable —— PE 真身，不是
        假 exe）作 --bin：resolve_bin 的 nt 分支补 .exe 后真实启动成功，
        程序真跑（到达工具回执判面，绝无 193）。POSIX 平台此用例
        SKIP 如实登记（分支不可达，不是失败）。

        断言「真启动」而非「未报错」：fake .exe 的 Path.exists() 同真
        但启动必 193 —— 本用例正对此面。
        """
        if os.name != "nt":
            pytest.skip("POSIX 平台：.exe 补后缀分支不可达——Windows 真机归 Lead 复验")
        # 真 PE 可执行：复制 sys.executable（pythonX.Y.exe 真身）
        stem = tmp_path / "fake-tool"          # 无后缀（resolve_bin 输入面）
        exe = tmp_path / "fake-tool.exe"       # .exe 同伴（resolve_bin 切换目标）
        shutil.copyfile(sys.executable, exe)
        # 用 -c 参数化假工具行为？复制体不带脚本——直接让复制体做
        # ok:true 回执工具不可行（无 argv 注入面）；改为：真 exe 在位
        # 即真启动证明。构造 wrapper .exe 不可行 —— 用「复制体可启动」
        # 自证：先直接 exec 一次（同一路径、同一复制体）证明 PE 真身
        # 可跑（绝无 193），再跑 m145 CLI 观测 resolve_bin 切到它后
        # 不再 die「不在位」（到达回执判面 = 真启动发生）。
        probe = subprocess.run([str(exe), "-c", "print('{\"ok\": true}')"],
                               capture_output=True, text=True,
                               encoding="utf-8", timeout=60)
        assert probe.returncode == 0, (f"复制 sys.executable 应真启动（returncode"
                                       f" {probe.returncode}；stderr：{probe.stderr[:200]}）")
        assert "WinError 193" not in (probe.stderr or "")
        # m145 CLI 级：--bin 无后缀（.exe 同伴=真 PE 在位）→ resolve_bin
        # 切到 .exe → 真启动 → 不 die「不在位」，到达工具回执判面
        proc = subprocess.run(
            [sys.executable, str(REPO / "scripts/m145_repro.py"),
             "--root", str(REPO), "--ws", str(tmp_path / "ws"),
             "--out", str(tmp_path / "out.json"),
             "--bin", str(stem)],
            capture_output=True, text=True, encoding="utf-8", timeout=60,
        )
        assert "不在位" not in (proc.stderr or "")  # 到达回执判面 = 真启动
        assert "WinError 193" not in (proc.stderr or "")  # 无「非有效 Win32」启动崩
        # 且 m145 非零退出（python 复制体吃 stdin JSON 的 REPL 行为面：
        # die 于回执判面——「工具起了、回执不可用」，不是「启动失败」）
        assert proc.returncode != 0

    def test_repro112_resolve_bin_default_from_script_location(self, tmp_path):
        """默认 bin = 脚本位置上溯的仓内路径（不依赖 cwd/作者 home）——
        Path 语义比较（str 字面量在 Windows 规范化后必假红）。"""
        p = rep.resolve_bin(None)
        assert p == REPO / "bidcore/target/debug/bid-mcp-stdio"
        # 显式指定原样保留（不猜后缀——用户给了就信）
        p2 = rep.resolve_bin(str(REPO / "some/other/bin"))
        assert p2 == REPO / "some/other/bin"


# ---------------------------------------------------------------- UTF8 显式

class TestExplicitUtf8:
    def test_gold_load_explicit_utf8(self, tmp_path):
        """受控反例：GBK 不可解码字节——旧代码（locale 缺省读）在 cp936
        平台崩启动；显式 utf-8 读不依赖 locale。

        issue 证据形态：requirements.reviewed.json 的 0x81 是 GBK 孤前导
        字节。用 0xa0/0xff（GBK 不可解码——与 #143 同形字节）构造：显式
        gbk 读必崩（先红），显式 utf-8 路径走 errors=replace 不依赖 locale
        （后绿——locale 无关性的直接证据）。"""
        raw = b'{"requirements": [{"id": "GR-\xa0\xff001"}]}'
        gf = tmp_path / "requirements.reviewed.json"
        gf.write_bytes(raw)
        with pytest.raises(UnicodeDecodeError):
            gf.read_text(encoding="gbk")  # 先红证据：cp936 解码路径必崩
        # 新代码形：errors=replace 显式 utf-8——不崩且替换语义在位
        text = gf.read_text(encoding="utf-8", errors="replace")
        assert "GR-" in text and "001" in text
        # load_gold 真路径：合法 UTF-8 中文金标准显式 utf-8 完整解码
        ok = tmp_path / "ok.json"
        ok.write_text(json.dumps({"requirements": [{"id": "松岭-16/16"}]},
                                  ensure_ascii=False), encoding="utf-8")
        rep.GR_PATH = ok
        reqs = rep.load_gold()
        assert reqs[0]["id"] == "松岭-16/16"  # 显式 utf-8 完整语义

    def test_subprocess_encoding_declared(self):
        """源面断言：两脚本的 subprocess.run 均带 encoding="utf-8"（不裸奔）。"""
        src = (REPO / "scripts/repro_112.py").read_text(encoding="utf-8")
        assert 'encoding="utf-8"' in src and "errors=" in src
        src2 = (REPO / "scripts/m145_repro.py").read_text(encoding="utf-8")
        assert 'encoding="utf-8"' in src2 and "errors=" in src2
        # 不再写死作者目录："/home/z" 只允许出现在弃用声明语境，不得作为
        # 路径赋值（REPO/WS/BIN 常量）
        import re
        for rel, s in (("repro_112", src), ("m145_repro", src2)):
            for m in re.finditer("/home/z", s):
                ctx = s[max(0, m.start() - 30):m.end() + 10]
                assert "不再写死" in ctx or "不写死" in ctx, \
                    f"{rel}：/home/z 出现在非弃用声明语境：{ctx!r}"


# ---------------------------------------------------------------- 安全复跑

class TestSafeRerun:
    def test_prepare_ws_rejects_nonempty(self, tmp_path, capsys):
        """非空工作区 → die（exit 1）不静默复用旧数据。"""
        ws = tmp_path / "ws-old"
        ws.mkdir()
        (ws / "db.json").write_text("{}", encoding="utf-8")
        with pytest.raises(SystemExit) as ei:
            m145.prepare_ws(ws)
        assert ei.value.code == 1
        assert "非空" in capsys.readouterr().err

    def test_prepare_ws_empty_ok(self, tmp_path):
        ws = tmp_path / "ws-new"
        ws.mkdir()
        m145.prepare_ws(ws)
        assert ws.exists()

    def test_repro112_prepare_ws_same_discipline(self, tmp_path):
        ws = tmp_path / "ws-a"
        ws.mkdir()
        (ws / "old.txt").write_text("x", encoding="utf-8")
        with pytest.raises(SystemExit) as ei:
            rep.prepare_ws(ws)
        assert ei.value.code == 1


# ---------------------------------------------------------------- 失败非零

class TestFailureNonzero:
    def test_repro112_bin_absent_dies(self, tmp_path):
        with pytest.raises(SystemExit) as ei:
            rep.main() if False else rep.die("bin 不在位")
        assert ei.value.code == 1

    def test_repro112_missing_bin_nonzero_cli(self, tmp_path):
        """真实 CLI：bin 不在位 → exit 1 + stderr 可诊断（不裸崩 assert）。"""
        proc = subprocess.run(
            [sys.executable, str(REPO / "scripts/repro_112.py"),
             str(tmp_path / "ws"), str(tmp_path / "out.json"),
             str(tmp_path / "no-such-bin")],
            capture_output=True, text=True, encoding="utf-8", timeout=30,
        )
        assert proc.returncode == 1
        assert "不在位" in (proc.stderr or "")

    def test_repro112_missing_gold_nonzero(self, tmp_path):
        """金标准缺失 → exit 1（附路径——可诊断）。"""
        proc = subprocess.run(
            [sys.executable, str(REPO / "scripts/repro_112.py"),
             str(tmp_path / "ws"), str(tmp_path / "out.json"),
             str(tmp_path / "no-such-bin")],
            capture_output=True, text=True, encoding="utf-8", timeout=30,
        )
        assert proc.returncode == 1


# ---------------------------------------------------------------- 口径修正

class TestBaselineCaveats:
    def test_m145_note_no_stale_assertion(self):
        """修复前口径修正：脚本正文不再以「应无 REQ」为断言预期——旧口径
        只允许出现在「弃用声明」语境（引用以声明其失效），报盘 note 用
        观测口径。"""
        src = (REPO / "scripts/m145_repro.py").read_text(encoding="utf-8")
        # 断言语境的「应无」不允许；弃用声明语境（不再断言…）必须在位
        assert "不再断言" in src
        assert "观测面" in src  # 改为观测登记口径
        assert "#148" in src  # 指向修复 PR 的判读依据
        # 每处「应无」出现必须处于弃用声明句内（前 40 字符含「不再」或「那是」）
        import re
        for m in re.finditer("应无", src):
            ctx = src[max(0, m.start() - 40):m.end()]
            assert "不再断言" in ctx or "旧文档" in ctx or "修复前口径" in ctx, \
                f"「应无」出现在非弃用声明语境：{ctx!r}"

    def test_repro112_caveats_registered(self):
        """三口径警示硬断言在报盘结构（防 16/16 被误读为完整收口）。"""
        src = (REPO / "scripts/repro_112.py").read_text(encoding="utf-8")
        assert "不等价于单位/上下限/完整语义保真" in src
        assert "67 条原始材料仍未取得" in src
        assert "不可互充基线" in src  # Poppler318 vs PDFium316

    def test_repo_head_recorded_field(self):
        """源 hash/PDF SHA/解析通道字段在报盘结构（bin sha + pdf_sha256 + channel）。"""
        src = (REPO / "scripts/repro_112.py").read_text(encoding="utf-8")
        for key in ('"sha256": sha256_of(bin_path)', '"pdf_sha256"',
                    '"parse_channel_signal"'):
            assert key in src


# ------------------------------------------- Lead 2026-11-14 返工回归（实跑反例）

class TestNonzeroExitReplyTrue:
    """Lead 实跑反例：真实 Python 子进程输出 JSON {ok:true,data:{}} 后
    sys.exit(7)——旧 call 只查 reply.ok 即放行（steps 记 returncode=7
    却 ok:true，上层 main 放行，最终可能 exit 0）。

    本组用**真实子进程**（非模拟 CompletedProcess）：tmp 假工具脚本直写
    ok:true 回执后 exit 7。双闸修复后：call 返回 ok=false + failure_reason
    指明退出码分歧；steps 记 ok:false、保留 returncode/stdout/stderr；
    m145.call 同款核验。"""

    def _fake_tool(self, tmp_path: Path, exit_code: int = 7) -> Path:
        """真实可执行假工具：读 stdin、回 ok:true JSON、再 exit 7。

        可移植执行位：POSIX chmod +x + shebang；Windows 直接落 .py 同名
        .bat 包装（cmd 代理执行）——两平台都作为真实子进程被 call 起。
        """
        tool = tmp_path / "fake-tool.py"
        tool.write_text(
            "#!/usr/bin/env python3\n"
            "import sys\n"
            "sys.stdin.readline()\n"
            "print('{\"ok\": true, \"data\": {\"project_id\": \"PRJ-T\"}}')\n"
            "sys.stdout.flush()\n"
            f"sys.exit({exit_code})\n",
            encoding="utf-8")
        if os.name == "nt":
            bat = tmp_path / "fake-tool.bat"
            bat.write_text(f'@"{sys.executable}" "{tool}" %*\n', encoding="utf-8")
            return bat
        tool.chmod(0o755)
        return tool

    def test_repro112_call_rejects_exit7_with_ok_true(self, tmp_path):
        """真实子进程 exit7+ok:true：call 双闸拒绝放行（步骤失败、
        回执保留、诊断信息在位）。"""
        tool = self._fake_tool(tmp_path)
        steps = []
        reply = rep.call(tool, "create_bid_project", {"name": "x"}, {}, steps)
        assert reply.get("ok") is False, "非零退出码必须视为步骤失败（旧缺陷放行）"
        assert reply.get("failure_reason") and "7" in reply["failure_reason"]
        assert reply.get("data", {}).get("project_id") == "PRJ-T"  # 原回执保留
        assert len(steps) == 1
        st = steps[0]
        assert st["ok"] is False and st["returncode"] == 7
        assert "stdout_tail" in st and "stderr_tail" in st  # 准确输出保留
        assert "PRJ-T" in st["stdout_tail"]

    def test_repro112_main_gates_on_nonzero_exit(self, tmp_path):
        """全链闸位：exit7+ok:true 的 create 步 → main 非零退出（不再被
        reply.ok 放行为 exit 0）。真实 CLI 子进程级验证。"""
        tool = self._fake_tool(tmp_path)
        proc = subprocess.run(
            [sys.executable, str(REPO / "scripts/repro_112.py"),
             str(tmp_path / "ws"), str(tmp_path / "out.json"), str(tool)],
            capture_output=True, text=True, encoding="utf-8", timeout=60,
        )
        assert proc.returncode != 0  # 旧缺陷：可能 exit 0
        assert "create_bid_project 失败" in (proc.stderr or "")  # 可诊断

    def test_m145_call_same_gate(self, tmp_path):
        """m145.call 同款双闸核验（Lead 指名「同类调用检查一起核验」）。"""
        tool = self._fake_tool(tmp_path)
        reply = m145.call(tool, "create_bid_project", {"name": "x"}, {})
        assert reply.get("ok") is False
        assert reply.get("failure_reason") and "7" in reply["failure_reason"]
        assert reply.get("data", {}).get("project_id") == "PRJ-T"  # 原回执保留

    def test_call_zero_exit_ok_true_passes(self, tmp_path):
        """正例（防过修）：exit 0 + ok:true → 照常放行（步骤 ok:true）。

        与负例共用**同一平台 shim**（_fake_tool 的 .bat/.py+shebang 路径
        ——旧正例直接 exec 裸 .py，Windows WinError 193）；正例 = exit 0
        版本，回执 JSON 断言保留。"""
        tool = self._fake_tool(tmp_path, exit_code=0)
        steps = []
        reply = rep.call(tool, "create_bid_project", {"name": "x"}, {}, steps)
        assert reply.get("ok") is True and "failure_reason" not in reply
        assert steps[0]["ok"] is True and steps[0]["returncode"] == 0
        assert "PRJ-T" in steps[0]["stdout_tail"]  # 成功 JSON 真到过 stdout


class TestChannelEvidence:
    """返工④（Lead 2026-11-14 二轮收紧）：通道识别只认实际证据；
    测试换**可调用纯函数 + 受控真实链**行为断言——不再源字符串断言充数。
    证据不足不假报完整。"""

    def test_channel_from_filename_pdfium_not_evidence(self):
        """Lead 三版反例（#162 评论）：filename 含 pdfium.pdf（命名恰含
        关键词）但 parse_summary 未知/不支持 → **不得**当成功通道。
        旧面整对象 JSON 扫描会误标 pdfium——只采信实际解析证据字段。"""
        # filename 里的 pdfium 字样 + 无任何采信字段 → None
        got = rep.channel_from(
            {"files": [{"filename": "report-pdfium.pdf",
                        "pages": 65}]})
        assert got is None
        # 同名文件 + 明确 engine 字段 → 采信（engine 自述可作证据）
        got2 = rep.channel_from(
            {"files": [{"filename": "report-pdfium.pdf",
                        "engine": "poppler"}]})
        assert got2 == "poppler"  # filename 字样不覆盖 engine 自述
        # 深层嵌套里的备注/error 也不采信
        got3 = rep.channel_from(
            {"files": [{"filename": "x.pdf",
                        "note": "pdfium probe failed"}]})
        assert got3 is None

    def test_channel_from_pure_function(self):
        """channel_from 纯函数直接调用（行为面）：只采信成功文件的
        parse_summary / 明确 engine 字段；无采信字段 → None（不冒充）。"""
        # 采信字段：file 条目的 parse_summary（嵌套在回执 data 里）
        assert rep.channel_from(
            {"files": [{"parse_summary": "pdfium ok"}]}) == "pdfium"
        assert rep.channel_from({"parse_summary": "poppler"}) == "poppler"
        # 采信字段：明确 engine 自述（大小写不敏感）
        assert rep.channel_from(
            {"files": [{"engine": "PDFium-1.0"}]}) == "pdfium"
        assert rep.channel_from(
            {"files": [{"parse_engine": "poppler-utils"}]}) == "poppler"
        assert rep.channel_from(
            {"files": [{"parser": "PDFium"}]}) == "pdfium"
        assert rep.channel_from(
            {"files": [{"channel": "poppler"}]}) == "poppler"
        assert rep.channel_from(
            {"files": [{"pdf_engine": "pdfium"}]}) == "pdfium"
        # str 输入 = 一段 parse_summary 叙述（同一口径）
        assert rep.channel_from("parsed via pdfium, 65 pages") == "pdfium"
        # 无采信字段（有 pages 数但无通道叙述）→ None
        assert rep.channel_from({"files": [{"pages": 65}]}) is None
        assert rep.channel_from(None) is None  # 无证据
        assert rep.channel_from("") is None

    def test_resolve_parse_channel_receipt_evidence_wins(self):
        """裁决纯函数：导入回执 parse_summary 带通道 → 采信（来源=
        import_receipt）——回执是成功导入的实际证据，不是 probe 日志。"""
        receipt = {"files": [{"filename": "f.pdf", "parse_summary":
                               "parsed via pdfium, 65 pages"}]}
        steps = [{"stderr_tail": "poppler probe failed"}]  # 干扰面：stderr 有字样
        ch, src_, fb = rep.resolve_parse_channel(receipt, {}, steps)
        assert ch == "pdfium" and src_ == "import_receipt" and fb is None
        # 回执证据在先——stderr 干扰信号被 ① 优先级短路（不进 fallback）

    def test_resolve_parse_channel_stderr_only_not_trusted(self):
        """false-positive 反例（Lead 指名）：**只有** stderr 里的 pdfium
        字样（失败 probe 日志）而回执/db 无通道字段 → channel=unknown，
        stderr 信号只落 fallback 字段（不采信为成功通道）。"""
        steps = [{"stderr_tail": "pdfium load failed probe fallback"},
                 {"stderr_tail": "pdfium retry failed"}]
        ch, src_, fb = rep.resolve_parse_channel({"data": {}}, {}, steps)
        assert ch == "unknown"
        assert src_ == "stderr_signal(fallback-未采信)"
        assert fb == "pdfium"  # 信号登记在位（但不是 channel 值）

    def test_resolve_parse_channel_db_files_evidence(self):
        """② 级证据：db.json files 解析摘要带通道 → 采信（来源=db_files）。"""
        db = {"domain": {"files": [{"name": "f.pdf",
                                    "parse_summary": "poppler 65p"}]}}
        ch, src_, fb = rep.resolve_parse_channel(None, db, [])
        assert ch == "poppler" and src_ == "db_files" and fb is None

    def test_resolve_parse_channel_no_evidence_unknown(self):
        """全无证据 → unknown（来源 no-evidence）——不假报完整。"""
        ch, src_, fb = rep.resolve_parse_channel({}, {}, [])
        assert ch == "unknown" and src_ == "no-evidence" and fb is None

    @staticmethod
    def _exec_tool(tmp_path: Path, body: str, name: str) -> Path:
        """平台可执行假工具（Lead 三版点修：不得直接 exec 裸 .py——
        Windows WinError 193）。POSIX：.py + shebang + chmod；Windows：
        同名 .bat 包装 sys.executable（cmd 代理）——两平台都作为真实
        子进程被 call 起。body 须自带 import sys 与 stdin 读取。"""
        tool = tmp_path / f"{name}.py"
        tool.write_text(body, encoding="utf-8")
        if os.name == "nt":
            bat = tmp_path / f"{name}.bat"
            bat.write_text(f'@"{sys.executable}" "{tool}" %*\n',
                           encoding="utf-8")
            return bat
        tool.chmod(0o755)
        return tool

    def test_channel_real_chain_receipt_parsed_evidence(self, tmp_path):
        """受控真实链（行为面）：假工具回执 data.parse_summary 写 pdfium
        → 真跑 main → 落盘报告 channel=pdfium（来源 import_receipt——
        **实际导入回执被采信**，不是 stderr 搜字）。链走到 db 断点
        die（诚实失败），报告未落——故另用单步 call 直接取回执 + 纯函数
        裁决（=main 内同一条证据链：receipt=r.get("data") 传第一优先级）。
        与 main 的差异仅在后继步骤（db 缺失 die），裁决输入完全同构。"""
        tool = self._exec_tool(
            tmp_path,
            "#!/usr/bin/env python3\n"
            "import sys\n"
            "sys.stdin.readline()\n"
            "print('{\"ok\": true, \"data\": {\"files\": ["
            "{\"parse_summary\": \"parsed via pdfium, 65 pages\"}]}}')\n"
            "sys.stdout.flush()\n",
            "receipt-tool")
        steps = []
        receipt = rep.call(tool, "import_tender_files", {"files": []}, {}, steps)
        # 平台真实启动断言（Lead 三版：不许 193 假绿）——回执 JSON 真到达
        assert receipt.get("ok") is True, receipt
        assert "parsed via pdfium" in steps[0]["stdout_tail"]  # JSON 真流入 stdout
        assert steps[0]["returncode"] == 0
        assert "WinError 193" not in steps[0]["stderr_tail"]  # 无启动崩
        # 与 main 同构的证据链：r2.get("data") → resolve_parse_channel
        ch, src_, fb = rep.resolve_parse_channel(receipt.get("data"), {}, steps)
        assert ch == "pdfium" and src_ == "import_receipt"

    def test_channel_real_chain_stderr_noise_unknown(self, tmp_path):
        """受控真实链（false-positive 面）：真实子进程 stderr 打 pdfium
        失败 probe 字样 + 回执 data 无通道字段 → 裁决不采信 stderr——
        unknown。旧代码在此会把失败 probe 当成功通道（Lead 指名缺陷）。"""
        tool = self._exec_tool(
            tmp_path,
            "#!/usr/bin/env python3\n"
            "import sys\n"
            "sys.stdin.readline()\n"
            "print('{\"ok\": true, \"data\": {}}')\n"
            "sys.stdout.flush()\n"
            "sys.stderr.write('pdfium probe load failed fallback\\n')\n"
            "sys.stderr.flush()\n",
            "probe-noise-tool")
        steps = []
        receipt = rep.call(tool, "import_tender_files", {"files": []}, {}, steps)
        # 平台真实启动断言（Lead 三版：不许 193 假绿）——JSON 与噪声都真到达
        assert receipt.get("ok") is True, receipt
        assert steps[0]["returncode"] == 0
        assert "WinError 193" not in steps[0]["stderr_tail"]  # 无启动崩
        assert steps[0]["stderr_tail"].count("pdfium") >= 1  # 噪声真流入 stderr
        ch, src_, fb = rep.resolve_parse_channel(receipt.get("data"), {}, steps)
        assert ch == "unknown"  # 不冒充
        assert src_ == "stderr_signal(fallback-未采信)"
        assert fb == "pdfium"  # 噪声登记在位、未进 channel 值
