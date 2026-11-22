#!/usr/bin/env python3
"""acceptance_closeout.py — 独立本地验收入口（#115 · TA-1 承接）。

一条命令重跑四验收分栏，产出五态结果 schema（PASS/FAIL/SKIP/BLOCKED/NOT_RUN）
+ 可重放日志（无密钥）+ 严格模式裁定。**不改 workflow / MCP 接口 / 业务实现**
（issue 红线），只做验收编排与结果协议。

四分栏（对应整改总表挂靠关系）：
  1. baseline    工程链真测重跑（closeout_real_test.py --all 的独立重放——
                 A/C 面 Rust 真跑 + B 面公告链独立再推导）
  2. songling67  #112 松岭 67 关键点素材在位性 + 16 条金标准召回断言
                 （67 条原始材料 MISSING → 严格模式必然非 PASS——如实分栏）
  3. multifile   #114 多文件统一矩阵素材齐套盘点（同项目主件+辅件集齐否）
  4. realagent   #113 真实 LLM 面登记（未执行即 NOT_RUN——不冒充已验）

严格模式（默认开）裁定规则（issue 正文：默认本地不可因跳过核心门宣称收官）：
  - 任一分栏 FAIL/BLOCKED/NOT_RUN → 整体 FAIL（exit 1）
  - --allow-skip 用于非收官语境的快速自查（整体可 PASS 但注明豁免了哪些面）

结果 schema（artifacts/acceptance-closeout/<ts>/result.json）：
  {schema_version, generated_at, mode, repo_head, host_facts, four_panels,
   overall: {verdict, blocking_reasons}, replay: {commands, exit_codes},
   redaction: {applied: "git-credentials/token/url-basic-auth"}}

日志可重放：每条外部命令记录 argv + cwd + exit_code + 时间戳；环境只留
键名集合（值一律脱敏）；日志写 artifacts/acceptance-closeout/<ts>/run.log。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

PANELS = ("baseline", "songling67", "multifile", "realagent")
# 六态词表（#115 条件 5 接线新增 EVIDENCE_UNCONFIRMED：真跑原始来源在案、
# 人工确认缺位——严格/宽松处置与 NOT_RUN 同构，报告渲染区分）
VERDICTS = ("PASS", "FAIL", "SKIP", "BLOCKED", "NOT_RUN", "EVIDENCE_UNCONFIRMED")

# 密钥形正则（日志/结果文件里出现的都替换为 <redacted>）
SECRET_PATTERNS = [
    re.compile(r"(?i)(token|password|secret|api[_-]?key)\s*[=:]\s*\S+"),
    re.compile(r"https://[^/\s]+:[^@\s]+@"),
]


def redact(text: str) -> str:
    for pat in SECRET_PATTERNS:
        text = pat.sub(lambda m: m.group(0).split("=")[0].split(":")[0] + "=<redacted>"
                       if "=" in m.group(0) else "<redacted>", text)
    return text


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------- 基础事实

def run_subprocess(args, *, cwd=None, timeout=None) -> subprocess.CompletedProcess:
    """subprocess 统一出口（#143）：显式 utf-8 + errors=replace + 启动失败伪返回。

    根因：text=True 不带 encoding 时按系统 locale 解码（Windows 中文 =
    GBK）——子进程输出含非 GBK 字节（如 closeout Rust 面的 UTF-8 中文
    路径名）即 UnicodeDecodeError 崩主流程，「单命令可重跑」验收判据在
    目标平台失效。本出口：
      - encoding/errors 显式——双平台行为一致（utf-8 为仓内命令行事实
        编码；errors=replace 保证任何字节流可解码——完整性以字节语义为
        准的场合不走本出口）；
      - 超时不抛——CompletedProcess 伪返回（returncode=124——GNU timeout
        惯例；stdout/stderr 带异常名与 partial 输出），裁定面照常走
        FAIL 分支，不静默；
      - 启动失败（FileNotFoundError 等可执行不在位）不抛——伪返回
        returncode=127（shell 惯例「command not found」），stdout 空、
        stderr 带异常名与缺的可执行名——「失败可诊断不崩」；
      - stdout/stderr 恒为 str（None 防卫在消费面——本出口兜底 ""）。
    """
    try:
        proc = subprocess.run(
            args, cwd=cwd, timeout=timeout,
            capture_output=True, text=True,
            encoding="utf-8", errors="replace",
        )
    except subprocess.TimeoutExpired as e:
        partial_out = e.stdout if isinstance(e.stdout, str) else (e.stdout or b"").decode("utf-8", "replace")
        partial_err = e.stderr if isinstance(e.stderr, str) else (e.stderr or b"").decode("utf-8", "replace")
        return subprocess.CompletedProcess(
            args=args, returncode=124,
            stdout=f"[TimeoutExpired after {timeout}s] {partial_out}",
            stderr=f"[TimeoutExpired after {timeout}s] {partial_err}",
        )
    except FileNotFoundError as e:
        return subprocess.CompletedProcess(
            args=args, returncode=127,
            stdout="",
            stderr=f"[FileNotFoundError] 可执行不在位：{e}",
        )
    except OSError as e:  # noqa: BLE001 —— 权限/ENOENT 等启动面失败同口径
        return subprocess.CompletedProcess(
            args=args, returncode=127,
            stdout="",
            stderr=f"[OSError] 启动失败：{e}",
        )
    return subprocess.CompletedProcess(
        args=proc.args, returncode=proc.returncode,
        stdout=proc.stdout if proc.stdout is not None else "",
        stderr=proc.stderr if proc.stderr is not None else "",
    )


def repo_head() -> dict:
    def git(*args):
        p = run_subprocess(["git", *args], cwd=REPO)
        return p.stdout.strip() if p.returncode == 0 else ""
    return {
        "head": git("rev-parse", "HEAD"),
        "branch": git("rev-parse", "--abbrev-ref", "HEAD"),
        "dirty_files": len(git("status", "--porcelain").splitlines()),
    }


def host_facts() -> dict:
    return {
        "platform": platform.platform(),
        "python": sys.version.split()[0],
        "machine": platform.machine(),
        "cargo": _cargo_version(),
        "env_keys": sorted(k for k in os.environ if not k.startswith("_")),
    }


def _cargo_version() -> str:
    p = run_subprocess(["cargo", "--version"])
    return p.stdout.strip() or "absent"


# ---------------------------------------------------------------- 分栏 1: baseline

def panel_baseline(run: bool, log) -> dict:
    """工程链真测重放：closeout_real_test.py --all（独立子进程，真跑非重读旧件）。

    判定：exit 0 且 closeout-report.json all_pass=true → PASS；
          exit 0 但 all_pass=false → FAIL（报告内明确未过面）；
          环境缺 cargo → BLOCKED（记录原因，不硬凑）；用户 --skip-baseline → SKIP。
    """
    entry = {"panel": "baseline", "verdict": None}
    if not run:
        entry.update(verdict="SKIP", reason="--skip-baseline")
        return entry
    if shutil.which("cargo") is None and not (Path.home() / ".cargo/bin/cargo").exists():
        entry.update(verdict="BLOCKED", reason="cargo 不在位（rust-env.sh 可自愈）")
        return entry
    cmd = [sys.executable, "scripts/closeout_real_test.py", "--all"]
    entry["command"] = cmd
    t0 = time.monotonic()
    proc = run_subprocess(cmd, cwd=REPO, timeout=7200)
    entry["duration_s"] = round(time.monotonic() - t0, 1)
    entry["exit_code"] = proc.returncode
    # stdout/stderr 双面落日志（#143 Lead 复验根因：旧面只记 stdout——
    # 子进程仅在 stderr 报错时错误完全不可见，无法自我定位）。
    # 尾部各 4000 字符（与旧 stdout 面同量级；完整流在 closeout 面自身的
    # rust-run.log / run.log）。
    log(redact("[baseline stdout 尾部] " + (proc.stdout or "")[-4000:]))
    log(redact("[baseline stderr 尾部] " + (proc.stderr or "")[-4000:]))
    entry["stderr_tail"] = redact((proc.stderr or "")[-2000:])
    report = REPO / "artifacts/closeout-real-20261112/closeout-report.json"
    all_pass = None
    if report.exists():
        try:
            all_pass = json.loads(report.read_text(encoding="utf-8")).get("all_pass")
        except Exception as e:  # noqa: BLE001
            entry["parse_error"] = str(e)
    entry["all_pass"] = all_pass
    if proc.returncode == 0 and all_pass:
        entry["verdict"] = "PASS"
    elif proc.returncode == 0 and all_pass is False:
        entry["verdict"] = "FAIL"
        entry["reason"] = "收官链退出 0 但 all_pass=false（见 closeout-report.json）"
    else:
        entry["verdict"] = "FAIL"
        entry["reason"] = f"退出码 {proc.returncode}（非零即 FAIL——日志 run.log）"
    return entry


# ---------------------------------------------------------------- 分栏 2: songling67

def panel_songling67(log) -> dict:
    """#112 素材在位性 + 16 条金标准召回断言（不发分子工作给 #112 本体，只固化验收面）。

    素材 5 项 MISSING（manifest 登记）→ 67 条原始数据不可用：
    - 非 #112 本体面：只断「素材在位性如实分栏」，不产 67 条全过假象；
    - 在位面可做：16 条金标准对 tender PDF 原文文本的召回断言（真跑）。
    """
    entry = {"panel": "songling67", "verdict": None}
    fixdir = REPO / "fixtures/songling-232762"
    if not fixdir.exists():
        entry.update(verdict="BLOCKED", reason="fixtures/songling-232762 整体缺失")
        return entry

    # 2a) manifest 声明的层 2 素材在位性
    m = json.loads((fixdir / "manifest.json").read_text(encoding="utf-8"))
    missing, present = [], []
    for key, f in m.get("files", {}).items():
        rel = f.get("path") if isinstance(f, dict) else None
        if f.get("status") == "MISSING":
            missing.append({"key": key, "expected": f.get("expected", "")[:80]})
        elif rel and (fixdir / rel).exists():
            present.append(key)
    entry["materials"] = {
        "present": present,
        "missing": missing,
        "n_missing": len(missing),
    }

    # 2b) 16 条金标准对 PDF 原文召回（pdfminer 已有研究链口径；无依赖则降 pdfplumber→BLOCKED）
    gold = json.loads((fixdir / "expected/requirements.reviewed.json").read_text(encoding="utf-8"))
    reqs = gold.get("requirements", [])
    pdf = fixdir / "tender/光纤租赁费招标文件.pdf"
    entry["gold_n"] = len(reqs)
    if not pdf.exists():
        entry.update(verdict="BLOCKED", reason="tender PDF 缺失")
        return entry
    t0 = time.monotonic()
    try:
        from pdfminer.high_level import extract_text  # noqa: PLC0415
        text = extract_text(str(pdf))
    except ImportError:
        entry.update(verdict="BLOCKED",
                     reason="pdfminer 缺（pip install pdfminer.six 后重跑——研究链已有依赖）")
        return entry
    except Exception as e:  # noqa: BLE001 —— 损件/损坏件：缺料同口径 BLOCKED 不 FAIL
        entry.update(verdict="BLOCKED", reason=f"PDF 解析失败（损件口径——BLOCKED）: {e}")
        return entry

    # 归一面：松岭 PDF 的 CID 字体抽出康熙部首形（⽇/⾃/⽂——U+2F00 区），
    # 金标准 needle 是统一表意文字（U+4E00 区）——NFKC 归一后可比；
    # 数字形差（20,000 vs 20000）做去逗号兜底（检索锚语义：同一数值事实的
    # 两种排版形态，非字符串严格相等）。
    import unicodedata
    text_norm = unicodedata.normalize("NFKC", text)

    def needle_hit(n: str) -> bool:
        if not n:
            return False
        if n in text_norm:
            return True
        return n.replace(",", "") in text_norm.replace(",", "")

    hit = miss = 0
    misses = []
    for r in reqs:
        # 金标准结构：retrieval_needles: list[str]（多锚——任一命中即算召回；
        # 兜底 excerpt/statement 首段是为老 schema 容错）
        needles = r.get("retrieval_needles") or []
        if not needles:
            for k in ("excerpt", "statement"):
                if r.get(k):
                    needles = [str(r[k])[:40]]
                    break
        ok = any(needle_hit(n) for n in needles)
        hit += ok
        if not ok:
            miss += 1
            misses.append({"id": r.get("id"), "needles": [str(n)[:40] for n in needles][:3]})
    entry["needle_recall"] = {"hit": hit, "miss": miss, "total": len(reqs),
                              "pdf_extract_s": round(time.monotonic() - t0, 1)}
    entry["misses"] = misses[:10]
    log(f"[songling67] 金标准 {len(reqs)} 条 needle 召回 {hit}/{len(reqs)}；"
        f"层2素材缺失 {len(missing)} 项")
    # 判定：素材缺 → 严格如实：gold 面全中 = 素材面 BLOCKED 的「可做部分已做」，
    # 但 67 条本体不可宣称 → 分栏整体 BLOCKED（缺料）——不 FAIL（非缺陷，是缺料）。
    if miss:
        entry["verdict"] = "FAIL"
        entry["reason"] = f"金标准 needle 召回缺 {miss} 条（检索面回归）"
    elif missing:
        entry["verdict"] = "BLOCKED"
        entry["reason"] = f"层2素材 {len(missing)} 项 MISSING（67 条本体面缺料——#112 如实口径）"
    else:
        entry["verdict"] = "PASS"
    return entry


# ---------------------------------------------------------------- 分栏 3: multifile

def panel_multifile(log) -> dict:
    """#114 多文件统一矩阵素材齐套盘点（同项目主件+技术规范+报价+补遗+证据）。

    盘点面：corpus 每域按「同项目身份」聚类文件；淮安电信项目（主件+技术规范+
    报价 xlsx+合同）是仓内唯一近齐套真实集。齐套 → PASS（素材在位，矩阵面本体
    归 #114）；缺料 → BLOCKED；零可用 → NOT_RUN。
    """
    entry = {"panel": "multifile", "verdict": None}
    huai_an = [
        ("A-telecom-huaian-主文件.docx", "招标文件"),
        ("B-telecom-huaian-技术规范书.docx", "技术规范"),
        ("B-telecom-huaian-报价文件.xlsx", "报价表"),
        ("B-telecom-huaian-合同.docx", "合同"),
    ]
    base = REPO / "real-corpus/telecom/parse-input"
    have = []
    for name, role in huai_an:
        p = base / name
        have.append({"role": role, "file": name,
                     "present": p.exists(),
                     **({"sha256_12": sha256_of(p)[:12], "bytes": p.stat().st_size}
                        if p.exists() else {})})
    entry["huaian_project_files"] = have
    # 补遗件（同项目变更/补遗公告）：corpus 内无淮安补遗件——如实登记
    entry["addendum_material"] = {
        "found": False,
        "note": "仓内无淮安项目补遗件（其余补遗形态见 gov-procurement 更正公告——属 B 面链路非矩阵件）",
    }
    n_present = sum(1 for x in have if x["present"])
    log(f"[multifile] 淮安项目 4 件中 {n_present} 在位")
    if n_present == len(huai_an):
        entry["verdict"] = "PASS"
        entry["note"] = "素材齐套性 PASS（矩阵/评分映射正确性本体归 #114 执行面——本栏只固化素材验收基线）"
    elif n_present:
        entry["verdict"] = "BLOCKED"
        entry["reason"] = f"淮安项目 {n_present}/{len(huai_an)} 件在位——缺料不拼凑"
    else:
        entry["verdict"] = "NOT_RUN"
        entry["reason"] = "多件素材零在位"
    return entry


# ---------------------------------------------------------------- 分栏 4: realagent

def panel_realagent(log) -> dict:
    """#113 真实 LLM 面登记（#115 条件 5 接线：证据识别半边）。

    三态：
    - **NOT_RUN**：无环境门也无已完成跑证据（旧行为）；
    - **EVIDENCE_UNCONFIRMED**（新）：artifacts/realagent-113-*/ 内在场
      已完成真跑证据（generator real>0 / mock=0 / llm-usage 在案）——
      原始来源半边成立，人工确认缺位（#169 口径：模型审校/自动跑
      ≠ 人工批准）；严格模式仍阻断整体 PASS（与 NOT_RUN 同处置）；
    - PASS：**人工确认在案后**才可达（审校 receipt 追认——不在本面板
      自动驱动，冒充即假绿）。
    """
    entry = {"panel": "realagent", "verdict": None}
    driver = REPO / "scripts/e2e_bid/run_real_llm_path.sh"
    entry["driver_exists"] = driver.exists()
    ws = os.environ.get("BID_REAL_PATH_WS")
    phase = os.environ.get("BID_REAL_PATH_PHASE")
    entry["env_gate"] = {"BID_REAL_PATH_WS": "set" if ws else "unset",
                         "BID_REAL_PATH_PHASE": "set" if phase else "unset"}
    # 人工中继痕迹（无则未执行——如实）
    relay_marker = None
    if ws:
        marker = Path(ws) / ".mang/human-chapter.md"
        if marker.exists():
            relay_marker = str(marker)
    entry["human_relay_marker"] = relay_marker
    # ---- 已完成真跑证据识别（原始来源半边）----
    evidence = None
    ev_dirs = sorted((REPO / "artifacts").glob("realagent-113-*/realagent-metrics.json")) \
        if (REPO / "artifacts").is_dir() else []
    for mf in reversed(ev_dirs):  # 最新优先
        try:
            m = json.loads(mf.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        gs = (m.get("export") or {}).get("generator_summary") or {}
        usage = m.get("llm_usage") or {}
        if gs.get("real", 0) > 0 and gs.get("mock", 0) == 0 and usage.get("calls", 0) > 0:
            evidence = {
                "dir": mf.parent.name,
                "leaves_real": gs.get("real"),
                "mock": gs.get("mock"),
                "llm_calls": usage.get("calls"),
                "llm_tokens": usage.get("total_tokens"),
                "model": next(iter((usage.get("by_model") or {"unknown": {}}).keys())),
                "coverage_points": (m.get("scoring_coverage") or {}).get("points_covered"),
                "export_sha256": ((m.get("export") or {}).get("sha256") or "")[:16],
                "docx_present": (mf.parent / "投标文件-realagent-113.docx").exists(),
            }
            break
    entry["evidence"] = evidence
    if evidence:
        # 原始来源在案；人工确认未在（审校 receipt）——诚实中间态
        entry["verdict"] = "EVIDENCE_UNCONFIRMED"
        entry["reason"] = (
            f"真跑证据在案（{evidence['leaves_real']} 叶 real/mock=0、"
            f"{evidence['llm_calls']} 次调用 {evidence['llm_tokens']} tokens、"
            f"成品 {evidence['export_sha256']}…）——待人工审校追认后转 PASS"
            f"（模型审校≠人工批准，#169）"
        )
        log(f"[realagent] EVIDENCE_UNCONFIRMED（{evidence['dir']}："
            f"real={evidence['leaves_real']} tokens={evidence['llm_tokens']}）——待人工追认")
        return entry
    if ws and phase and driver.exists():
        # 真跑归 #113 本体执行；本栏对已设环境的情况返回 NOT_RUN+提示（不重复
        # 驱动两相位中继——那是 #113 的人工步骤，自动化冒充即假绿）
        entry["verdict"] = "NOT_RUN"
        entry["reason"] = "环境门已设——两相位人工中继执行归 #113 本体（此处自动驱动=冒充人工步骤）"
    else:
        entry["verdict"] = "NOT_RUN"
        entry["reason"] = ("真实 LLM 通路未执行（BID_REAL_PATH_WS/PHASE 未设；"
                           "run_real_llm_path.sh 两相位人工中继是 #113 的登记边界）")
    log(f"[realagent] 真实 LLM 面 NOT_RUN 登记（env 门 {entry['env_gate']}）")
    return entry


# ---------------------------------------------------------------- 主裁定

def overall_verdict(panels: list[dict], strict: bool) -> tuple[str, list]:
    """严格模式：任一 FAIL/SKIP/BLOCKED/NOT_RUN → 整体 FAIL。

    宽松模式（--allow-skip，非收官自查）：SKIP/BLOCKED/NOT_RUN 不阻断，
    但 blocking_reasons 仍如实记录（结果文件里可追踪，报告渲染区分）。
    """
    reasons = []
    verdict = "PASS"
    for p in panels:
        v = p["verdict"]
        if v == "FAIL":
            reasons.append(f"{p['panel']}: FAIL —— {p.get('reason', '')}")
        elif strict and v in ("SKIP", "BLOCKED", "NOT_RUN", "EVIDENCE_UNCONFIRMED"):
            reasons.append(f"{p['panel']}: {v} —— {p.get('reason', '')}")
        elif not strict and v in ("SKIP", "BLOCKED", "NOT_RUN", "EVIDENCE_UNCONFIRMED"):
            reasons.append(f"[allow-skip 豁免] {p['panel']}: {v} —— {p.get('reason', '')}")
    if any(p["verdict"] == "FAIL" for p in panels) or (strict and reasons):
        verdict = "FAIL"
    elif not strict and any(p["verdict"] in ("SKIP", "BLOCKED", "NOT_RUN", "EVIDENCE_UNCONFIRMED") for p in panels):
        verdict = "PASS_WITH_SKIPS" if verdict == "PASS" else verdict
    return verdict, reasons


def render_md(result: dict) -> str:
    lines = ["# 本地验收收官报告（#115 · 独立入口）", "",
             f"- 生成：{result['generated_at']}（mode={result['mode']}）",
             f"- 仓库：{result['repo_head']['head'][:12]} @ {result['repo_head']['branch']}"
             f"（dirty {result['repo_head']['dirty_files']} 文件）", "",
             "| 分栏 | 裁定 | 关键事实 |", "|---|---|---|"]
    for p in result["four_panels"]:
        fact = ""
        if p["panel"] == "baseline":
            fact = f"exit={p.get('exit_code')} all_pass={p.get('all_pass')} 用时{p.get('duration_s')}s"
        elif p["panel"] == "songling67":
            r = p.get("needle_recall") or {}
            fact = f"金标准{p.get('gold_n')}条 needle 召回 {r.get('hit')}/{r.get('total')}；层2缺料 {p.get('materials', {}).get('n_missing')} 项"
        elif p["panel"] == "multifile":
            n = sum(1 for x in p.get("huaian_project_files", []) if x.get("present"))
            fact = f"淮安项目 {n}/4 件在位；补遗件={p.get('addendum_material', {}).get('found')}"
        elif p["panel"] == "realagent":
            fact = f"env 门 ws={p['env_gate']['BID_REAL_PATH_WS']} phase={p['env_gate']['BID_REAL_PATH_PHASE']}"
            ev = p.get("evidence")
            if ev:
                fact += f"；证据 {ev['dir']}（real={ev['leaves_real']} tokens={ev['llm_tokens']}）"
            if p.get("human_relay_marker"):
                fact += "；人工中继痕迹在案"
        lines.append(f"| {p['panel']} | **{p['verdict']}** | {fact} |")
    v = result["overall"]
    lines += ["", f"## 总裁定：{v['verdict']}", ""]
    if v["blocking_reasons"]:
        lines.append("阻断原因（严格模式——跳过核心门不得宣称收官）：")
        for r in v["blocking_reasons"]:
            lines.append(f"- {r}")
    else:
        lines.append("四分栏全 PASS（无阻断项）。")
    lines += ["", "## 重放", "",
              "```bash",
              *result["replay"]["commands"], "```", "",
              f"结果协议：{result['replay']['result_file']}（schema v{result['schema_version']}）",
              f"日志：{result['replay']['log_file']}（密钥形已脱敏：{result['redaction']['applied']}）"]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="#115 独立本地验收入口")
    ap.add_argument("--skip-baseline", action="store_true", help="跳过 baseline 真跑（分栏记 SKIP——严格模式整体 FAIL）")
    ap.add_argument("--allow-skip", action="store_true", help="宽松模式：SKIP/BLOCKED/NOT_RUN 不阻断整体（报告仍如实分栏）")
    ap.add_argument("--no-render", action="store_true", help="不写 REPORT.md（只留 result.json/run.log）")
    args = ap.parse_args()

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    outdir = REPO / "artifacts/acceptance-closeout" / ts
    outdir.mkdir(parents=True, exist_ok=True)
    log_path = outdir / "run.log"
    log_lines: list[str] = []

    def log(msg: str) -> None:
        stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
        line = f"[{stamp}] {msg}"
        log_lines.append(redact(line))
        print(redact(msg), flush=True)

    log(f"#115 独立验收启动：mode={'宽松(allow-skip)' if args.allow_skip else '严格'}")

    panels = [
        panel_songling67(log),
        panel_multifile(log),
        panel_realagent(log),
        panel_baseline(run=not args.skip_baseline, log=log),
    ]

    verdict, reasons = overall_verdict(panels, strict=not args.allow_skip)
    commands = [
        f"git -C {REPO} rev-parse HEAD  # {ts}",
        f"{sys.executable} scripts/acceptance_closeout.py"
        + ("" if not args.skip_baseline else " --skip-baseline")
        + ("" if not args.allow_skip else " --allow-skip"),
    ]
    result = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "mode": "strict" if not args.allow_skip else "allow-skip",
        "repo_head": repo_head(),
        "host_facts": host_facts(),
        "four_panels": panels,
        "overall": {"verdict": verdict, "blocking_reasons": reasons},
        "replay": {
            "commands": commands,
            "exit_codes": {p["panel"]: p.get("exit_code") for p in panels if "exit_code" in p},
            "result_file": str(outdir / "result.json"),
            "log_file": str(log_path),
        },
        "redaction": {"applied": "token/password/secret/api-key 形 + URL basic-auth"},
    }
    # 验证五态词表自洽（结果协议自检第一面）
    assert all(p["verdict"] in VERDICTS for p in panels), "协议违规：分栏裁定不在六态词表"
    assert verdict in (*VERDICTS, "PASS_WITH_SKIPS"), "协议违规：总裁定非法"

    (outdir / "result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    log_path.write_text("\n".join(log_lines) + "\n", encoding="utf-8")
    if not args.no_render:
        (outdir / "REPORT.md").write_text(render_md(result), encoding="utf-8")
    # latest 软链（幂等）
    latest = REPO / "artifacts/acceptance-closeout/latest"
    if latest.is_symlink() or latest.exists():
        latest.unlink()
    latest.symlink_to(outdir.name)

    print(f"\n总裁定：{verdict}")
    for r in reasons:
        print(f"  - {r}")
    print(f"产物：{outdir}/result.json + REPORT.md + run.log")
    return 0 if verdict == "PASS" or verdict == "PASS_WITH_SKIPS" else 1


if __name__ == "__main__":
    sys.exit(main())
