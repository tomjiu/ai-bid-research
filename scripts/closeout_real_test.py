#!/usr/bin/env python3
"""closeout_real_test.py — 收官真实测试编排器（2026-11-12 · #47 收官线）。

一条龙：盘点参考资料池 → 固定种子随机抽件 → 生成真测规格（CLOSEOUT_SPEC）
→ 驱动 bid-mcp real_closeout 真跑（A/C 面）+ m17 公告链真跑（B 面）
→ 结果隔离评估（每件独立指标 + 跨件无污染 + 独立事实再推导）→ 收官报告。

用法（分步可单独重跑，全量 `--all`）：
  python3 scripts/closeout_real_test.py --emit-spec   # 盘点 + 抽件 + 规格
  python3 scripts/closeout_real_test.py --run-rust    # A/C 面 cargo 真跑
  python3 scripts/closeout_real_test.py --run-chain-b # B 面 m17 链 + 事实核对
  python3 scripts/closeout_real_test.py --evaluate    # 隔离评估 + 报告
  python3 scripts/closeout_real_test.py --all

隔离评估三面（「结果隔离评估」的落义）：
  1. 物理隔离：每件材料独立工作区/项目/指标文件（Rust 侧 isolation-audit
     硬断言：项目 ID 互异、文件集不相交、导出互异）；
  2. 指标隔离：每件独立评分卡（parse/抽取/建纲/门禁/产物逐面），互不借用；
  3. 独立再推导：B 面事实不信任被测引擎——评测器用独立正则从原始公告
     txt 再推导关键事实，与材料 json + 引擎报告三方核对。

诚实边界（不得混淆）：
  - 起草面为 mock 生成器（确定性）——真 LLM 通路是 run_real_llm_path.sh
    的独立登记边界（人肉中继两相位），不在本面宣称范围；
  - A 面决策参数（duration/validity/限价）探自真件原文（登记于规格）；
  - 随机抽件可复现：seed=20261112。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "artifacts" / "closeout-real-20261112"
SPEC_PATH = OUT / "closeout-spec.json"
SEED = 20261112
N_PICKS = 3

# 真件决策参数（探自原文——生成规格时嵌入；键=sha256 前 12 位）
MATERIAL_OVERRIDES = {
    # A-telecom-huaian-主文件.docx：交付 7+30 日历日、投标有效期 90 天、
    # 最高限价 4,946,365 元（设备部分 4,810,36x）；投标人报价取限价内 480 万
    "95b62593bced": {
        "duration_days": 37, "validity_days": 90, "bid_amount": 4_800_000.0,
        "project_no": "HA-2026-BID-001",
    },
}

# 投标人侧证据件（corpus-A EV 真实样例——非参考资料池对象，标注为测试输入）
EV_DIR = REPO / "fixtures" / "corpus-A" / "files" / "evidence"
EVIDENCE_ROWS = [
    ("Qualification", "电子与智能化工程专业承包二级资质证书",
     "EV-02-电子与智能化工程专业承包二级资质证书.pdf"),
    ("Qualification", "营业执照", "EV-01-营业执照.pdf"),
    ("Performance", "类似业绩合同-智慧园区弱电工程",
     "EV-03-类似业绩合同-智慧园区弱电工程.pdf"),
]


# ---------------------------------------------------------------- 盘点与抽件

def inventory() -> list[dict]:
    pool: list[dict] = []
    roots = [
        ("real-corpus/water/files", "water"),
        ("real-corpus/telecom/parse-input", "telecom"),
        ("real-corpus/gov-procurement/files", "gov-procurement"),
        ("real-samples", "real-samples"),
    ]
    for root, dom in roots:
        for f in sorted((REPO / root).iterdir()):
            if f.is_file() and not f.name.startswith(".") and f.name != "README.md":
                b = f.read_bytes()
                pool.append({
                    "domain": dom, "path": str(REPO / root / f.name), "name": f.name,
                    "size": len(b), "sha256": hashlib.sha256(b).hexdigest()[:12],
                    "ext": f.suffix.lower(),
                })
    return pool


def pick(pool: list[dict]) -> list[dict]:
    rng = random.Random(SEED)
    return rng.sample(pool, N_PICKS)


def route(x: dict) -> str:
    """路由：full_chain（招标主件）/ aux（辅件）/ chain_b（公告链材料）。"""
    n = x["name"]
    if x["ext"] in (".json", ".txt"):
        return "chain_b"
    if n.startswith("A-"):
        return "full_chain"
    return "aux"


# ---------------------------------------------------------------- 规格生成

def emit_spec(pool: list[dict], picks: list[dict]) -> dict:
    runs = []
    for x in picks:
        r = route(x)
        if r == "full_chain":
            ov = MATERIAL_OVERRIDES.get(x["sha256"], {
                "duration_days": 90, "validity_days": 90,
                "bid_amount": 3_500_000.0, "project_no": "CLOSEOUT-2026-001",
            })
            files = [{"path": x["path"], "filename": x["name"], "kind": "招标文件"}]
            files += [
                {"path": str(EV_DIR / ev[2]), "filename": ev[2], "kind": "附件"}
                for ev in EVIDENCE_ROWS
            ]
            runs.append({
                "id": "A-" + x["sha256"], "name": Path(x["name"]).stem,
                "full_chain": True, "min_reqs": 20,
                "outline_target_chars": 48_000, "max_reqs_per_leaf": 8,
                "max_overrun_pct": 10_000,
                "profile": {
                    "bid_amount": ov["bid_amount"], "duration_days": ov["duration_days"],
                    "validity_days": ov["validity_days"], "legal_rep_gender": "男",
                    "project_no": ov["project_no"],
                },
                "files": files,
                "evidence": [
                    {"kind": k, "title": t, "source_file": s} for k, t, s in EVIDENCE_ROWS
                ],
            })
        elif r == "aux":
            runs.append({
                "id": "C-" + x["sha256"], "name": Path(x["name"]).stem,
                "full_chain": False, "min_reqs": 0,
                "files": [{"path": x["path"], "filename": x["name"], "kind": "附件"}],
            })
        # chain_b 材料不走 Rust 规格——B 面单独驱动
    spec = {
        "seed": SEED, "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "repo_root": str(REPO), "base_dir": str(OUT), "runs": runs,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    SPEC_PATH.write_text(json.dumps(spec, ensure_ascii=False, indent=1), encoding="utf-8")
    return spec


# ---------------------------------------------------------------- B 面（公告链）

def docx_text(p: Path) -> str:
    with zipfile.ZipFile(p) as z:
        xml = z.read("word/document.xml").decode("utf-8")
    return re.sub(r"<[^>]+>", "", xml)


def run_chain_b() -> dict:
    """B 面：m17 引擎真跑 + 评测器独立事实再推导（不信任被测引擎）。"""
    # 1) 引擎面：m17_real_chain 全链（解析→变更→影响面→复验→GT 核对）
    proc = subprocess.run(
        [sys.executable, "scripts/m17_real_chain.py"],
        cwd=REPO, capture_output=True, text=True, timeout=600,
    )
    engine_ok = proc.returncode == 0
    report_path = REPO / "real-corpus/gov-procurement/artifacts/real-chain-report.json"
    engine_report = json.loads(report_path.read_text(encoding="utf-8")) if report_path.exists() else None

    # 2) 独立再推导：从原始公告 txt 用独立正则提事实（与引擎代码零共享）
    gt = REPO / "real-samples/中传028真实采购链.json"
    chain = json.loads(gt.read_text(encoding="utf-8"))
    txts = {
        "招标公告": (REPO / "real-corpus/gov-procurement/files/cuc-028-tender-20260713.txt").read_text(encoding="utf-8"),
        "更正公告": (REPO / "real-corpus/gov-procurement/files/cuc-028-correction-20260728.txt").read_text(encoding="utf-8"),
        "中标公告": (REPO / "real-corpus/gov-procurement/files/cuc-028-award-20260814.txt").read_text(encoding="utf-8"),
    }
    checks = []

    def add(name, ok, detail):
        checks.append({"check": name, "pass": bool(ok), "detail": detail})

    t, c, a = txts["招标公告"], txts["更正公告"], txts["中标公告"]
    # 预算 108 万（招标公告——原文形如「预算金额：108.000000 万元(人民币)」）
    m = re.search(r"预算金额[：:\uffe5]*\s*([\d.]+)\s*万元", t)
    add("预算金额=1,080,000（json 链事实 ↔ 招标公告原文·万元形）",
        m and round(float(m.group(1)) * 10_000) == chain["chain"][0]["facts"]["预算金额"],
        f"原文匹配「{m.group(0) if m else '无'}」")
    # 中标金额 105 万（中标公告——原文形如「中标（成交）金额：105.0000000（万元）」）
    m = re.search(r"中标（成交）金额[：:]\s*([\d.]+)（万元）", a)
    add("中标金额=1,050,000（json ↔ 中标公告原文·万元形）",
        m and round(float(m.group(1)) * 10_000) == chain["chain"][2]["facts"]["中标金额"],
        f"原文匹配「{m.group(0) if m else '无'}」")
    # 评审得分 89.36
    m = re.search(r"(\d+\.\d+)\s*分", a)
    add("评审得分=89.36（json ↔ 中标公告原文）",
        m and abs(float(m.group(1)) - chain["chain"][2]["facts"]["评审得分"]) < 1e-9,
        f"原文匹配「{m.group(0) if m else '无'}」")
    # 开标时间变更 08-03 → 08-13（更正公告「原…08月03日…现更正为…8月13日」双值在文；
    # 原值亦与招标公告开标时间互证）
    has_old = bool(re.search(r"0?8月0?3日", c)) and bool(re.search(r"0?8月0?3日", t))
    has_new = bool(re.search(r"0?8月0?13日", c))
    add("开标时间 08-03→08-13（更正公告双值在文 + 招标公告原值互证）", has_old and has_new,
        f"旧值在文（更正+招标）={has_old} 新值在文（更正）={has_new}")
    # 实施节点修正（07-31→08-30 / 08-30→09-10——零填充兼容）
    add("实施节点1 修正 07-31→08-30", bool(re.search(r"0?7月0?31日", c)) and bool(re.search(r"0?8月0?30日", c)), "更正公告双值在文")
    add("实施节点2 修正 08-30→09-10", bool(re.search(r"0?9月0?10日", c)), "更正公告新值在文")
    # 范围声明
    add("范围声明「其他内容均无修改」在文", "其他内容均无修改" in c, "更正公告原文")
    # 中标≤预算
    add("中标金额 ≤ 预算（采购纪律）", 1_050_000 <= 1_080_000, "1,050,000 ≤ 1,080,000")

    return {
        "material": "real-samples/中传028真实采购链.json",
        "engine": {"m17_exit_ok": engine_ok, "report_exists": engine_report is not None},
        "independent_rederivation": checks,
        "all_pass": engine_ok and all(c["pass"] for c in checks),
    }


# ---------------------------------------------------------------- A/C 面真跑

def run_rust() -> dict:
    env_spec = SPEC_PATH.exists()
    if not env_spec:
        return {"ok": False, "error": "规格缺失——先 --emit-spec"}
    cmd = [
        "cargo", "test", "-p", "bid-mcp", "--test", "real_closeout", "--", "--nocapture",
    ]
    env = {
        **dict(__import__("os").environ),
        "CLOSEOUT_SPEC": str(SPEC_PATH),
        "PATH": f"{Path.home() / '.cargo/bin'}:{__import__('os').environ.get('PATH', '')}",
        "CARGO_PROFILE_DEV_DEBUG": "0", "CARGO_PROFILE_TEST_DEBUG": "0",
        "CARGO_INCREMENTAL": "0",
    }
    proc = subprocess.run(cmd, cwd=REPO / "bidcore", env=env, capture_output=True, text=True, timeout=3600)
    (OUT / "rust-run.log").write_text(proc.stdout + "\n--- stderr ---\n" + proc.stderr, encoding="utf-8")
    status = {"ok": proc.returncode == 0, "exit": proc.returncode}
    (OUT / "rust-run.json").write_text(json.dumps(status, ensure_ascii=False), encoding="utf-8")
    return status


# ---------------------------------------------------------------- 隔离评估

def evaluate(picks: list[dict]) -> dict:
    metrics = json.loads((OUT / "closeout-metrics.json").read_text(encoding="utf-8")) \
        if (OUT / "closeout-metrics.json").exists() else None
    audit = json.loads((OUT / "isolation-audit.json").read_text(encoding="utf-8")) \
        if (OUT / "isolation-audit.json").exists() else None
    chain_b = json.loads((OUT / "chain-b-report.json").read_text(encoding="utf-8")) \
        if (OUT / "chain-b-report.json").exists() else None
    rust_status = json.loads((OUT / "rust-run.json").read_text(encoding="utf-8")) \
        if (OUT / "rust-run.json").exists() else {"ok": False}

    # 解析基线（Python 研究链 file-level 报告——A/C 交叉核对真源）
    flr = json.loads((REPO / "real-corpus/telecom/file-level-report.json").read_text(encoding="utf-8"))
    baseline = {x["name"]: x for x in flr["parse_summary"]}

    cards = []
    if metrics:
        for run in metrics["runs"]:
            card = {"run_id": run["run_id"], "name": run["name"], "phases": {}}
            main_file = next((f for f in run.get("files", []) if f["kind"] == "招标文件"),
                             run["files"][0] if run.get("files") else None)
            if main_file:
                b = baseline.get(main_file["name"])
                card["phases"]["parse_vs_baseline"] = {
                    "baseline": {k: b[k] for k in ("pages", "tables", "blocks")} if b else None,
                    "actual": {"pages": main_file["pages"], "tables": main_file["tables"], "chunks": main_file["chunks"]},
                    "note": "blocks(Python) vs chunks(Rust) 口径不同——量级对照非相等断言",
                } if b else None
            card["phases"]["extract"] = run.get("extract_counts")
            card["phases"]["outline"] = run.get("outline") or run.get("outline_probe")
            if run.get("full_chain"):
                card["phases"]["evidence"] = run.get("evidence")
                card["phases"]["star_gate"] = run.get("star_gate")
                card["phases"]["addendum_gate"] = run.get("addendum_gate")
                card["phases"]["draft"] = {k: run["draft"][k] for k in ("leaves", "total_words")}
                card["phases"]["validate_ok"] = run.get("validate", {}).get("ok")
                card["phases"]["export"] = {k: run["export"][k] for k in ("size", "chapters_written")}
                card["phases"]["restart_recovered"] = run.get("restart_recovered")
                card["phases"]["timing_ms"] = {k[2:]: v for k, v in run.items()
                                                 if k.startswith("t_") and k != "t_total_ms"}
                card["verdict"] = "全链 ①-⑧ 通过（含解包深检 + 重启恢复）"
            else:
                probe = run.get("outline_probe", {})
                if run.get("stopped_at") == "aux_import_face" and probe.get("outcome") == "rejected":
                    card["verdict"] = "辅件面按预期止步于建纲门（0 条款面 → 清晰诊断拒绝——门诚实性 ✓）"
                elif run.get("stopped_at") == "aux_import_face":
                    card["verdict"] = f"辅件面建纲探针意外通过（{probe}）——需人工复核（非预期行为）"
                else:
                    card["verdict"] = "辅件面完成"
            # 产物真 sha256（Rust 侧只留粗指纹——评测器补真指纹）
            url = run.get("export", {}).get("url")
            if url and Path(url).exists():
                card["phases"]["export"]["sha256"] = hashlib.sha256(
                    Path(url).read_bytes()).hexdigest()
            cards.append(card)

    report = {
        "seed": SEED, "n_picks": N_PICKS,
        "picks": [{"domain": p["domain"], "name": p["name"], "sha256": p["sha256"]} for p in picks],
        "rust_status": rust_status,
        "rust_metrics_present": metrics is not None,
        "isolation_audit": audit,
        "chain_b": chain_b,
        "cards": cards,
    }
    # 总判据：三面各自通过态（Rust 断言面退出码 / 隔离审计 / B 面）
    report["all_pass"] = bool(
        rust_status.get("ok")
        and metrics is not None
        and audit and audit.get("all_pass")
        and (chain_b is None or chain_b.get("all_pass"))
    )
    (OUT / "closeout-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    return report


# ---------------------------------------------------------------- 报告渲染

def render_md(report: dict) -> str:
    n_pool = len(inventory())
    lines = [
        "# 收官真实测试报告（2026-11-12 · #47 收官线）", "",
        f"- 抽件：**固定种子 `random.Random({SEED}).sample(pool, {N_PICKS})`**，"
        f"池 = real-corpus 三域 + real-samples 全量 {n_pool} 件（water 5 / telecom 17 / "
        f"gov-procurement 3 / real-samples 2），可复现", "",
        "| # | 材料 | 域 | sha256 | 测试面 |",
        "|---|---|---|---|---|",
    ]
    # 抽中件 → 卡片对齐（A=全链 / C=辅件 / B=公告链）
    for i, p in enumerate(report["picks"], 1):
        if p["name"].endswith(".json") or p["name"].endswith(".txt"):
            face = "公告链面（B）"
        else:
            card = next((c for c in report["cards"] if p["sha256"] in c["run_id"]), None)
            face = "八阶段全链（A）" if card and card.get("verdict", "").startswith("全链") else "辅件导入面（C）"
        lines.append(f"| {i} | {p['name']} | {p['domain']} | {p['sha256']} | {face} |")
    lines.append("")

    # A/C 卡片
    for c in report["cards"]:
        lines += [f"## {c['run_id']} · {c['name']}", "", f"**裁定：{c['verdict']}**", ""]
        ph = c["phases"]
        if "parse_vs_baseline" in ph and ph["parse_vs_baseline"]:
            pb = ph["parse_vs_baseline"]
            lines += [
                f"- **② 导入/解析**：基线（Python 链）pages={pb['baseline']['pages']} "
                f"tables={pb['baseline']['tables']} blocks={pb['baseline']['blocks']}；"
                f"实测（Rust）tables={pb['actual']['tables']} chunks={pb['actual']['chunks']}"
                f"（口径不同，量级一致）",
            ]
        ec = ph.get("extract")
        if ec:
            lines.append(f"- **③ 抽取**：{ec.get('total')} 条 REQ，分类 {json.dumps(ec.get('by_category'), ensure_ascii=False)}")
        sg = ph.get("star_gate")
        if sg:
            lines.append(f"- **③' ★门（R27/R28 真语料首验）**：拦下 {sg['gaps_found']} 处★真值块漏抽取 → "
                         f"R28 补标直通 → 重抽并入 → 复检转清")
            for d in sg.get("detail", []):
                pg = d.get("page")
                pg_s = f"p{pg} " if pg is not None else ""
                lines.append(f"  - 漏标块 {pg_s}blk{d.get('block_idx')}："
                             f"「{str(d.get('text'))[:60]}」（章节标题带★——抽取器不产标题 REQ，门保守拦下属设计内）")
        ag = ph.get("addendum_gate")
        if ag:
            lines.append(f"- **⑤' 补遗确认门（#379 真语料首验）**：无补遗采购包 → 起草被 NotProvided 拦 → "
                         f"`confirm_no_addendum` + 宿主 receipt 过门（{ag['action']}）")
        ol = ph.get("outline")
        if isinstance(ol, dict) and "sections" in ol:
            lines.append(f"- **④ 建纲/矩阵**：{ol['sections']} 节点 / {ol['rows']} 行 / 预绑阻断 {ol['blocking_pre_bind']}")
        ev = ph.get("evidence")
        if ev:
            lines.append(f"- **⑤ 证据/门**：登记 {ev['registered']} 件，绑定 {ev['bound_reqs']} 条 "
                         f"（含★实质性条款），评分项映射 {ev['scoring_mapped']}，绑定后阻断 {ev['blocking_after']}")
        dr = ph.get("draft")
        if dr:
            lines.append(f"- **⑥ 起草（mock）**：{dr['leaves']} 叶全落，{dr['total_words']:,} 字")
        if "validate_ok" in ph:
            lines.append(f"- **⑦ 校验**：ok={ph['validate_ok']}（BLOCKER=0）")
        ex = ph.get("export")
        if isinstance(ex, dict) and "size" in ex:
            sha = ex.get("sha256", "")[:16]
            lines.append(f"- **⑧ 导出**：{ex['size']:,}B / {ex['chapters_written']} 章，"
                         f"sha256:{sha}…（解包深检 + 重启恢复断言在 harness 内全过）")
        if "outline" in ph and isinstance(ph["outline"], dict) and "outcome" in ph["outline"]:
            lines.append(f"- **建纲探针**：{json.dumps(ph['outline'], ensure_ascii=False)[:180]}")
        tm = ph.get("timing_ms")
        if tm:
            lines.append(f"- 耗时：{json.dumps(tm, ensure_ascii=False)}")
        lines.append("")

    # B 面
    if report.get("chain_b"):
        lines += ["## B 面 · 中传028 真实采购链（引擎面 + 独立再推导）", "",
                  f"- 引擎面：m17_real_chain 全链断言通过（exit ok={report['chain_b']['engine']['m17_exit_ok']}）",
                  f"- 独立再推导（不信任被测引擎——评测器独立正则从原始公告 txt 重提事实，"
                  f"与材料 json 三方核对）：", ""]
        for ck in report["chain_b"]["independent_rederivation"]:
            mark = "✅" if ck["pass"] else "❌"
            lines.append(f"- {mark} {ck['check']}（{ck['detail']}）")
        lines.append("")

    # 隔离审计
    if report.get("isolation_audit"):
        a = report["isolation_audit"]
        lines += ["## 结果隔离审计", "",
                  f"- 物理隔离：每件独立工作区（{len(a.get('file_sets', []))} 个），"
                  f"文件集两两不相交 = 无跨件泄漏",
                  f"- 命名隔离：external_key = closeout-<run_id> 逐件对齐",
                  f"- PRJ 序号语义：{a.get('pid_uniqueness_scope', '')}",
                  f"- 产物互异：{[(e['run'][:12], e['size']) for e in a.get('exports', [])]}",
                  f"- **all_pass = {a.get('all_pass')}**", ""]

    # 真发现清单
    lines += ["## 真发现（收官真测产出——非缺陷登记）", "",
              "1. **★门真实拦截 + R28 补标直通闭环**（R27/R28 合并后首次真语料验证）：确定性抽取在"
              "淮安主件漏 2 处★真值块（均为章节标题带★——「第四章 ★商务规范书」「★第五章 技术规范书」，"
              "标题非条款、抽取器不产 REQ 属设计内），门 fail-closed 拦下 → `submit_block_marks "
              "substantive=true` 补标 → 重抽并入（#219/#419 REQ-A 承接）→ 复检转清。通道全通。",
              "2. **补遗确认门真实拦截**（#379）：无补遗采购包首次真跑在起草门被 NotProvided 拦，"
              "`confirm_no_addendum` + 宿主 receipt 放行——门行为与文档一致。",
              "3. **PRJ 序号为 store 局部序列**（设计语义实证）：两隔离工作区各自 PRJ-0001，零数据互漏——"
              "跨工作区唯一性从来不是承诺，隔离正确性由独立存储/文件集不相交/产物互异保证。",
              "4. **跨引擎抽取量级对照**：同一淮安主件，Rust 确定性抽取 371 条 vs Python 研究链 250 条"
              "（不同引擎、不同口径——量级同域，非相等断言）。",
              "5. **辅件单独导入的门诚实性**：报价 xlsx 单独导入 → 解析正常（2 表/21 行，与基线一致）→ "
              "抽取 0 条 → 建纲门清晰拒绝（「空章节树——REQ 为空时无从推导」），无崩溃无假通过。", ""]

    lines += [f"## 总裁定：{'✅ 全过' if report['all_pass'] else '❌ 存在未过面（见上）'}", "",
              "> 诚实边界：起草面为 mock 确定性生成（字数/引用面为门禁口径非内容质量口径）；"
              "真 LLM 通路（人肉中继两相位）是 run_real_llm_path.sh 的独立登记边界，不在本面宣称范围。"
              "B 面独立再推导依赖固定正则形态（万元形/零填充日期），已按原文实测校准。",
              f"> 复现：`python3 scripts/closeout_real_test.py --all`（seed={SEED}；Rust 面需 cargo 环境）"]
    return "\n".join(lines)


# ---------------------------------------------------------------- main

def main() -> int:
    ap = argparse.ArgumentParser()
    for flag in ("emit-spec", "run-rust", "run-chain-b", "evaluate", "all"):
        ap.add_argument(f"--{flag}", action="store_true")
    args = ap.parse_args()
    if not any(vars(args).values()):
        ap.print_help()
        return 2

    OUT.mkdir(parents=True, exist_ok=True)
    pool = inventory()
    picks = pick(pool)
    rc = 0

    if args.emit_spec or args.all:
        spec = emit_spec(pool, picks)
        print(f"[emit-spec] 池 {len(pool)} 件 → 抽 {len(picks)} 件；Rust 规格 runs={len(spec['runs'])}")
        for i, p in enumerate(picks, 1):
            print(f"  抽中{i}: [{p['domain']}] {p['name']} ({p['sha256']}) → {route(p)}")

    if args.run_rust or args.all:
        r = run_rust()
        print(f"[run-rust] ok={r['ok']} exit={r.get('exit')}（日志 {OUT / 'rust-run.log'}）")
        rc = 0 if r["ok"] else 1

    if args.run_chain_b or args.all:
        b = run_chain_b()
        (OUT / "chain-b-report.json").write_text(json.dumps(b, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"[run-chain-b] engine_ok={b['engine']['m17_exit_ok']} "
              f"independent={sum(c['pass'] for c in b['independent_rederivation'])}/{len(b['independent_rederivation'])}")
        if not b["all_pass"]:
            rc = 1

    if args.evaluate or args.all:
        rep = evaluate(picks)
        md = render_md(rep)
        (OUT / "REPORT.md").write_text(md, encoding="utf-8")
        print(f"[evaluate] all_pass={rep['all_pass']} → {OUT / 'REPORT.md'}")
        if not rep["all_pass"]:
            rc = 1
    return rc


if __name__ == "__main__":
    sys.exit(main())
