#!/usr/bin/env python3
"""multifile_acceptance.py — #114 完整多文件投标项目验收编排器（2026-11-18）。

一条龙：素材对账（清单/哈希/项目身份/真实合成标记 + 登记锚双向校验）
→ 生成验收规格（MULTIFILE_SPEC）→ 驱动 bid-mcp multifile_matrix 真跑
→ GT/期望对照评审（评审器独立于被测面——判分不在 Rust 里，防断言迁就实现）
→ 审计报告（audit/multifile-acceptance-2026-11-18.md）。

用法（分步可单独重跑，全量 `--all`）：
  python3 scripts/multifile_acceptance.py --emit-spec   # 对账 + 规格
  python3 scripts/multifile_acceptance.py --run-rust    # cargo 真跑五项目
  python3 scripts/multifile_acceptance.py --evaluate    # GT 对照 + 报告
  python3 scripts/multifile_acceptance.py --all

诚实边界（#114 口径——「无法取得完整真实项目则实测现有件并明确未覆盖」）：
  - 真实多件统一矩阵 = telecom 两组四件套（unicom-ry / huaian）——真实；
  - corpus-A 七件套（含澄清修改件）= 合成对照（GT 可判——确定性夹具）；
  - 投标人侧证据（EV-01/02/03）为合成投标人自报面（收官真测同款纪律，
    real_evidence=false 如实标记）——真实企业证据不在库（未覆盖登记）；
  - zjyd（C-变更公告 + B-立项批复）无主件 / cqyd 两件套 = 辅面如实记录。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "artifacts" / "multifile-acceptance-20261118"
SPEC_PATH = OUT / "multifile-spec.json"
INVENTORY_PATH = OUT / "inventory.json"
EVAL_PATH = OUT / "evaluation.json"
AUDIT_MD = REPO / "audit" / "multifile-acceptance-2026-11-18.md"

TELECOM = REPO / "real-corpus/telecom/parse-input"
CORPUS_A = REPO / "fixtures/corpus-A/files"
GT_REQS = REPO / "fixtures/corpus-A/ground-truth/requirements.jsonl"
GT_CONFLICTS = REPO / "fixtures/corpus-A/ground-truth/conflicts.json"
TELECOM_FLR = REPO / "real-corpus/telecom/file-level-report.json"
CORPUS_A_MANIFEST = REPO / "fixtures/corpus-A/manifest.json"


def run_subprocess(args, *, cwd=None, env=None, timeout=None) -> subprocess.CompletedProcess:
    """subprocess 统一出口（#143 同语义：utf-8 显式 / 超时 124 / 缺执行 127）。"""
    try:
        proc = subprocess.run(
            args, cwd=cwd, env=env, timeout=timeout,
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
            args=args, returncode=127, stdout="",
            stderr=f"[FileNotFoundError] 可执行不在位：{e}",
        )
    return proc


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------- 素材清单

# (rel_path, kind, real, project, note)
FILE_PLAN: list[tuple[str, str, bool, str, str]] = [
    # ---- corpus-A 合成对照（7 件主集）----
    ("fixtures/corpus-A/files/A-招标文件.docx", "招标文件", False, "corpusA", "合成主件（manifest v0.6 确定性夹具）"),
    ("fixtures/corpus-A/files/B1-设备清单.pdf", "附件", False, "corpusA", "合成设备清单 PDF（40 行×8 列）"),
    ("fixtures/corpus-A/files/B2-投标函格式页-扫描件.pdf", "格式模板", False, "corpusA", "合成扫描件（无文本层——OCR 环境门外）"),
    ("fixtures/corpus-A/files/B3-图纸目录.xlsx", "图纸", False, "corpusA", "合成图纸目录 xlsx"),
    ("fixtures/corpus-A/files/C-补遗文件01.docx", "补遗", False, "corpusA", "合成补遗（控制价 465 万/开标日 11-27）"),
    ("fixtures/corpus-A/files/澄清修改文件-3.1.1.docx", "补遗", False, "corpusA", "合成澄清件（#425 生成——真实命名无前缀）"),
    # ---- unicom-ry 真实四件套 ----
    ("real-corpus/telecom/parse-input/A-unicom-ry-2026CUC-RJY-PT0783-招标文件.docx", "招标文件", True, "unicom-ry", "真件·联通软研院管理中台国资监管中心研发项目（LO .doc 转换留痕）"),
    ("real-corpus/telecom/parse-input/B-unicom-ry-技术规范书.docx", "附件", True, "unicom-ry", "真件·附件3 技术规范书"),
    ("real-corpus/telecom/parse-input/B-unicom-ry-详细评审表.xlsx", "评分办法", True, "unicom-ry", "真件·附件1 详细评审表（评分表）"),
    ("real-corpus/telecom/parse-input/B-unicom-ry-投标一览表.xlsx", "格式模板", True, "unicom-ry", "真件·附件4 投标一览表（LO .xls 转换留痕）"),
    # ---- huaian 真实四件套 ----
    ("real-corpus/telecom/parse-input/A-telecom-huaian-主文件.docx", "招标文件", True, "huaian", "真件·电信淮安本地视频能力平台建设采购项目"),
    ("real-corpus/telecom/parse-input/B-telecom-huaian-技术规范书.docx", "附件", True, "huaian", "真件·附件2 技术规范书"),
    ("real-corpus/telecom/parse-input/B-telecom-huaian-报价文件.xlsx", "附件", True, "huaian", "真件·附件3 报价文件"),
    ("real-corpus/telecom/parse-input/B-telecom-huaian-合同.docx", "附件", True, "huaian", "真件·附件1 合同"),
    # ---- cqyd 两件套 ----
    ("real-corpus/telecom/parse-input/A-cqyd-20260500728-重庆西永水冷空调-招标文件.pdf", "招标文件", True, "cqyd", "真件·重庆西永水冷空调群控系统优化项目"),
    ("real-corpus/telecom/parse-input/B-cqyd-招标公告.pdf", "附件", True, "cqyd", "真件·招标公告 PDF"),
    # ---- zjyd 两件套（无主件——辅面）----
    ("real-corpus/telecom/parse-input/C-zjyd-20260500552-数据库服务器-变更公告.pdf", "补遗", True, "zjyd", "真件·浙江移动数据库服务器变更公告（无主件在库）"),
    ("real-corpus/telecom/parse-input/B-zjyd-立项批复.pdf", "附件", True, "zjyd", "真件·浙江立项批复[2026]_321_号"),
]

# 投标人侧合成证据（真实企业证据不在库——real_evidence=false 面向全项目登记）
EV_FILES = [
    ("fixtures/corpus-A/files/evidence/EV-01-营业执照.pdf", "Qualification", "营业执照", None),
    ("fixtures/corpus-A/files/evidence/EV-02-电子与智能化工程专业承包二级资质证书.pdf", "Qualification",
     "电子与智能化工程专业承包二级资质证书", "2026-11-25"),
    ("fixtures/corpus-A/files/evidence/EV-03-类似业绩合同-智慧园区弱电工程.pdf", "Performance",
     "类似业绩合同-智慧园区弱电工程", None),
]


def corpus_a_evidence_specs() -> list[dict]:
    """corpus-A 全量 13 件证据（manifest 登记——EV-02 valid_until 翻转面真源）。"""
    m = json.load(open(CORPUS_A_MANIFEST, encoding="utf-8"))
    out = []
    for ev in m["stats"]["evidence"]:
        out.append({
            "kind": "Qualification",
            "title": Path(ev["path"]).stem,
            "source_file": Path(ev["path"]).name,
            "valid_until": ev.get("valid_until"),
        })
    return out


def bidder_evidence_specs() -> list[dict]:
    return [
        {"kind": k, "title": t, "source_file": Path(p).name, "valid_until": v}
        for (p, k, t, v) in EV_FILES
    ]


def emit_inventory() -> dict:
    """素材对账：清单 + sha256 + 项目身份 + 真实/合成标记 + 登记锚双向校验。"""
    flr = json.load(open(TELECOM_FLR, encoding="utf-8"))
    telecom_sha = {x["name"]: x["sha256"] for x in flr["parse_summary"]}
    manifest_files = {}
    m = json.load(open(CORPUS_A_MANIFEST, encoding="utf-8"))
    for f in m["files"]:
        manifest_files[Path(f["path"]).name] = f["sha256"]

    rows = []
    for (rel, kind, real, project, note) in FILE_PLAN:
        p = REPO / rel
        assert p.exists(), f"素材在位检查失败: {rel}"
        sha = sha256_of(p)
        # 登记锚校验：telecom → file-level-report；corpus-A → manifest
        anchor = None
        if real:
            reg = telecom_sha.get(p.name)
            anchor = "MATCH" if reg == sha else ("DRIFT" if reg else "NO_RECORD")
        else:
            reg = manifest_files.get(p.name)
            anchor = "MATCH" if reg == sha else ("DRIFT" if reg else "NO_RECORD")
        rows.append({
            "rel": rel, "name": p.name, "project": project, "kind": kind,
            "real": real, "bytes": p.stat().st_size, "sha256": sha,
            "hash_anchor": anchor, "note": note,
        })
    for (rel, _k, _t, _v) in EV_FILES:
        p = REPO / rel
        assert p.exists(), f"证据件在位检查失败: {rel}"
        sha = sha256_of(p)
        reg = manifest_files.get(p.name)
        rows.append({
            "rel": rel, "name": p.name, "project": "corpusA(evidence)", "kind": "附件(证据)",
            "real": False, "bytes": p.stat().st_size, "sha256": sha,
            "hash_anchor": "MATCH" if reg == sha else ("DRIFT" if reg else "NO_RECORD"),
            "note": "合成证据件（投标人侧自报面）",
        })
    # corpus-A 全量证据（13 件——corpusA 项目全件导入面，逐一登记）
    for e in corpus_a_evidence_specs():
        if e["source_file"] in {r["name"] for r in rows}:
            continue
        p = CORPUS_A / "evidence" / e["source_file"]
        assert p.exists(), f"corpus-A 证据件在位检查失败: {e['source_file']}"
        sha = sha256_of(p)
        reg = manifest_files.get(e["source_file"])
        rows.append({
            "rel": str(p.relative_to(REPO)), "name": e["source_file"], "project": "corpusA(evidence)",
            "kind": "附件(证据)", "real": False, "bytes": p.stat().st_size, "sha256": sha,
            "hash_anchor": "MATCH" if reg == sha else ("DRIFT" if reg else "NO_RECORD"),
            "note": "合成证据件（corpus-A manifest 登记）",
        })
    inv = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repo": "ai-bid-research",
        "issue": 114,
        "files": rows,
        "summary": {
            "total": len(rows),
            "real": sum(1 for r in rows if r["real"]),
            "synthetic": sum(1 for r in rows if not r["real"]),
            "hash_anchor_match": sum(1 for r in rows if r["hash_anchor"] == "MATCH"),
            "hash_anchor_drift": sum(1 for r in rows if r["hash_anchor"] == "DRIFT"),
            "hash_anchor_no_record": sum(1 for r in rows if r["hash_anchor"] == "NO_RECORD"),
        },
    }
    OUT.mkdir(parents=True, exist_ok=True)
    json.dump(inv, open(INVENTORY_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"[inventory] {len(rows)} 件对账完成 → {INVENTORY_PATH}")
    for r in rows:
        if r["hash_anchor"] != "MATCH":
            print(f"  [!] {r['name']}: hash_anchor={r['hash_anchor']}")
    return inv


def emit_spec() -> dict:
    inv = emit_inventory()
    ev13 = corpus_a_evidence_specs()
    ev3 = bidder_evidence_specs()

    def file_entry(rel: str, kind: str) -> dict:
        return {
            "path": str(REPO / rel),
            "filename": Path(rel).name,
            "kind": kind,
        }

    projects = [
        {
            "id": "corpusA-full",
            "name": "corpus-A 全件统一矩阵（合成对照·GT 可判）",
            "real": False,
            "full_chain": True,
            "outline_target_chars": 48000,
            "max_reqs_per_leaf": 8,
            "open_date_pre": "2026-11-15",
            "open_date_post": "2026-11-27",
            "addendum_probe": True,
            "real_evidence": False,
            "files": [file_entry(rel, kind) for (rel, kind, *_r) in
                      [r for r in FILE_PLAN if r[3] == "corpusA"]]
                      + [file_entry(p, "附件") for (p, _k, _t, _v) in EV_FILES]
                      + [file_entry(f"fixtures/corpus-A/files/evidence/{e['source_file']}", "附件")
                         for e in ev13 if e["source_file"] not in
                         [Path(p).name for (p, _k, _t, _v) in EV_FILES]],
            "evidence": ev13,
        },
        {
            "id": "unicom-ry",
            "name": "联通软研院国资监管中心研发项目——真实四件套（招标文件+技术规范+详细评审表+投标一览表）",
            "real": True,
            "full_chain": True,
            "outline_target_chars": 48000,
            "max_reqs_per_leaf": 8,
            "addendum_probe": False,
            "real_evidence": False,
            "files": [file_entry(rel, kind) for (rel, kind, *_r) in
                      [r for r in FILE_PLAN if r[3] == "unicom-ry"]]
                      + [file_entry(p, "附件") for (p, _k, _t, _v) in EV_FILES],
            "evidence": ev3,
        },
        {
            "id": "huaian",
            "name": "电信淮安本地视频能力平台建设——真实四件套（主文件+技术规范+报价+合同）",
            "real": True,
            "full_chain": True,
            "outline_target_chars": 48000,
            "max_reqs_per_leaf": 8,
            "addendum_probe": False,
            "real_evidence": False,
            "files": [file_entry(rel, kind) for (rel, kind, *_r) in
                      [r for r in FILE_PLAN if r[3] == "huaian"]]
                      + [file_entry(p, "附件") for (p, _k, _t, _v) in EV_FILES],
            "evidence": ev3,
        },
        {
            "id": "cqyd",
            "name": "重庆西永水冷空调——真实两件套（招标文件 PDF + 招标公告）",
            "real": True,
            "full_chain": False,
            "files": [file_entry(rel, kind) for (rel, kind, *_r) in
                      [r for r in FILE_PLAN if r[3] == "cqyd"]],
        },
        {
            "id": "zjyd",
            "name": "浙江移动数据库服务器——变更公告+立项批复（无主件辅面）",
            "real": True,
            "full_chain": False,
            "files": [file_entry(rel, kind) for (rel, kind, *_r) in
                      [r for r in FILE_PLAN if r[3] == "zjyd"]],
        },
        {
            # 统一矩阵辅探针：技术规范书按「招标文件」kind 导入（条款面形态）
            # ——对照 unicom-ry 主探针（技术规范书=附件 → 零 REQ 的设计边界）。
            # 详评表已知引擎拒收（不入本探针——解析面已在主探针留痕）。
            "id": "unicom-ry-alt",
            "name": "unicom-ry 统一矩阵辅探针——技术规范书按招标文件 kind（跨件 REQ 溯源对照面）",
            "real": True,
            "full_chain": False,
            "files": [
                file_entry("real-corpus/telecom/parse-input/A-unicom-ry-2026CUC-RJY-PT0783-招标文件.docx", "招标文件"),
                file_entry("real-corpus/telecom/parse-input/B-unicom-ry-技术规范书.docx", "招标文件"),
                file_entry("real-corpus/telecom/parse-input/B-unicom-ry-投标一览表.xlsx", "格式模板"),
            ],
        },
    ]
    spec = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "base_dir": str(OUT),
        "repo_root": str(REPO),
        "inventory": str(INVENTORY_PATH),
        "projects": projects,
    }
    json.dump(spec, open(SPEC_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"[spec] {len(projects)} 项目规格 → {SPEC_PATH}")
    return spec


# ---------------------------------------------------------------- Rust 真跑

def resolve_cargo() -> str:
    got = shutil.which("cargo")
    if got:
        return got
    home_cargo = Path.home() / ".cargo/bin/cargo"
    if home_cargo.exists():
        return str(home_cargo)
    return ""


def run_rust() -> int:
    cargo = resolve_cargo()
    if not cargo:
        print("[run-rust] cargo 不在位（shutil.which 与 ~/.cargo/bin 均未命中）", file=sys.stderr)
        return 2
    env = os.environ.copy()
    env["MULTIFILE_SPEC"] = str(SPEC_PATH)
    env["CARGO_PROFILE_DEV_DEBUG"] = "0"
    env["CARGO_PROFILE_TEST_DEBUG"] = "0"
    env["CARGO_INCREMENTAL"] = "0"
    cargo_dir = str(Path(cargo).resolve().parent)
    env["PATH"] = cargo_dir + os.pathsep + env.get("PATH", "")
    proc = run_subprocess(
        [cargo, "test", "-p", "bid-mcp", "--test", "multifile_matrix", "--", "--nocapture"],
        cwd=str(REPO / "bidcore"), env=env, timeout=3600,
    )
    sys.stdout.write(proc.stdout)
    sys.stderr.write(proc.stderr)
    (OUT / "rust-run.log").write_text(
        f"$ cargo test -p bid-mcp --test multifile_matrix -- --nocapture\n"
        f"exit={proc.returncode}\n\n{proc.stdout}\n{proc.stderr}", encoding="utf-8")
    print(f"[run-rust] exit={proc.returncode}（日志 → {OUT / 'rust-run.log'}）")
    return proc.returncode


# ---------------------------------------------------------------- GT 对照评审

def _norm(s: str) -> str:
    return re.sub(r"\s+", "", s or "")


def _req_excerpts(r: dict) -> list[str]:
    """REQ 全锚文而（excerpt + anchor_excerpts——多锚 REQ 不漏第二锚后的 GT 文本）。"""
    out = [r.get("excerpt") or ""]
    out.extend(r.get("anchor_excerpts") or [])
    return [x for x in out if x]


def eval_corpus_a_gt(metrics: dict) -> dict:
    """corpus-A GT 对照（25 条 REQ 召回 / 冲突 / 翻转 / 控制价版本 / 去重）。"""
    gt_rows = [json.loads(l) for l in open(GT_REQS, encoding="utf-8") if l.strip()]
    reqs = metrics["requirements"]
    by_file_clause = {}
    for r in reqs:
        by_file_clause.setdefault((r["source_file"], r.get("clause_no")), []).append(r)

    hits = []
    clause_hit = excerpt_hit = category_hit = 0
    for gt in gt_rows:
        anchor_files = [a["file"] for a in gt["anchors"]]
        cand = []
        for af in anchor_files:
            cand.extend(by_file_clause.get((af, gt["clause_no"]), []))
        gt_norm = _norm(gt["anchors"][0]["excerpt"])
        # 同文件同号未中 → 同文件全号模糊兜底（锚文包含——命中即记，注明口径）
        soft = []
        if not cand:
            for r in reqs:
                if r["source_file"] in anchor_files and gt_norm and any(
                    gt_norm in _norm(x) for x in _req_excerpts(r)
                ):
                    soft.append(r)
        row_hit = bool(cand or soft)
        if cand or soft:
            clause_hit += 1
        target = (cand or soft)[0] if (cand or soft) else None
        if target and target["category"] == gt["category"]:
            category_hit += 1
        if target and gt_norm and any(
            gt_norm in _norm(x) or _norm(x) in gt_norm for x in _req_excerpts(target)
        ):
            excerpt_hit += 1
        hits.append({
            "gt_id": gt["gt_id"], "clause_no": gt["clause_no"],
            "category": gt["category"], "anchor_file": anchor_files[0],
            "hit": row_hit, "match_kind": "exact" if cand else ("soft" if soft else "miss"),
            "req_category": target["category"] if target else None,
            "excerpt_hit": bool(target and gt_norm and any(
                gt_norm in _norm(x) or _norm(x) in gt_norm for x in _req_excerpts(target))),
        })
    gt_total = len(gt_rows)

    # 冲突对照：#425 已证（澄清修改件 3.1.1/3.2.1 同号异文 → 2 条）；
    # GT CONFLICT-01（控制价 A:6.1 vs C:三、——异号语义冲突）→ 同号匹配口径预期检不出
    conflicts = metrics.get("extract_conflicts", [])
    clar_conflicts = [c for c in conflicts if "3.1.1" in c.get("reason", "") or "3.2.1" in c.get("reason", "")]
    ctrl_conflicts = [c for c in conflicts if ("控制价" in c.get("reason", "") or "465" in c.get("reason", ""))]

    # 控制价版本共在（A 480 万 / C 465 万）
    versions = metrics.get("control_price_versions", [])
    has_480 = any("480" in (v.get("excerpt") or "") for v in versions if v["source_file"].startswith("A-"))
    has_465 = any("465" in (v.get("excerpt") or "") for v in versions if v["source_file"].startswith("C-"))

    # EV-02 翻转
    flip = (metrics.get("validity_flip_probe") or [{}])[0]
    flip_pre = flip.get("pre", {})
    flip_post = flip.get("post", {})

    # 补遗影响探针
    probe = metrics.get("addendum_change_probe", {})
    dirty_n = len(probe.get("dirty_sections", [])) if isinstance(probe, dict) else 0
    directives_n = len(probe.get("directives", [])) if isinstance(probe, dict) else 0

    return {
        "gt_total": gt_total,
        "clause_recall": clause_hit,
        "excerpt_recall": excerpt_hit,
        "category_hit": category_hit,
        "hits_detail": hits,
        "conflicts_total": len(conflicts),
        "clarifying_conflicts_detected": len(clar_conflicts),
        "control_price_conflict_detected": len(ctrl_conflicts),
        "control_price_versions": {"A_480": has_480, "C_465": has_465, "rows": versions},
        "ev02_flip": {"pre": flip_pre, "post": flip_post},
        "addendum_probe": {"dirty_sections": dirty_n, "directives": directives_n, "raw_skipped": "skipped" in probe},
        "merge_stats": metrics.get("extract_merge"),
    }


def eval_real_project(metrics: dict, pid: str) -> dict:
    """真实项目矩阵评审（对照 #134 基线 + 跨件一致性期望）。"""
    files = metrics.get("files", [])
    per_file_reqs = metrics.get("reqs_by_file", {})
    by_cat = (metrics.get("extract_counts") or {}).get("by_category", {})
    conflicts = metrics.get("extract_conflicts", [])
    scoring = metrics.get("scoring_mapping", {})
    coverage = (metrics.get("scoring_coverage") or {}).get("summary", {})
    # 章节配额分布（叶 = 未被任何节点引用为 parent 的节点）
    tree = metrics.get("section_tree", [])
    parent_ids = {n["parent_id"] for n in tree if n.get("parent_id")}
    leaves = [n for n in tree if n["id"] not in parent_ids]
    quotas = sorted((n["target_chars"] for n in leaves), reverse=True)
    quota_sum = sum(quotas) if quotas else 0
    mapped_sections = {d["section_id"] for d in scoring.get("decisions", [])}
    mapped_quota = sum(n["target_chars"] for n in leaves if n["id"] in mapped_sections)
    baseline_134 = {"unicom-ry": 18, "huaian": 28}.get(pid)
    return {
        "pid": pid,
        "import": {
            "files": metrics.get("import_totals", {}),
            "per_file": [
                {"name": f["name"], "kind": f["kind"], "parse_status": f["parse_status"],
                 "chunks": f["chunks"], "tables": f["tables"], "pages": f["pages"]}
                for f in files
            ],
            "partial": metrics.get("import_partial"),
            "item_errors": metrics.get("import_item_errors", []),
            "waived_failed_files": metrics.get("waived_failed_files", []),
            "draft_input_integrity": (metrics.get("draft") or {}).get("input_integrity"),
        },
        "extract": {
            "total": metrics.get("req_count"),
            "by_category": by_cat,
            "by_file": per_file_reqs,
            "scoring_reqs_134_baseline": baseline_134,
            "scoring_reqs_now": by_cat.get("scoring"),
            "conflicts": len(conflicts),
            "missing_sequence": len(metrics.get("extract_missing_sequence", [])),
        },
        "scoring_mapping": {
            "items": scoring.get("scoring_items"),
            "unmapped_before": scoring.get("unmapped_before"),
            "unmapped_after": scoring.get("unmapped_after"),
            "decisions": scoring.get("decisions", []),
        },
        "quota": {
            "leaves": len(leaves), "leaf_quota_sum": quota_sum,
            "target": metrics.get("outline", {}).get("quota_target"),
            "top5_share": (sum(quotas[:5]) / quota_sum) if quota_sum else 0,
            "mapped_scoring_leaf_quota_sum": mapped_quota,
            "mapped_scoring_leaf_quota_share": (mapped_quota / quota_sum) if quota_sum else 0,
        },
        "coverage": coverage,
        "validate": metrics.get("validate"),
    }


def evaluate() -> dict:
    all_path = OUT / "multifile-all.json"
    if not all_path.exists():
        print(f"[evaluate] 缺 {all_path}（先 --run-rust）", file=sys.stderr)
        sys.exit(2)
    data = json.load(open(all_path, encoding="utf-8"))
    by_id = {m["id"]: m for m in data["projects"]}

    evaluation = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "issue": 114,
        "inventory_summary": json.load(open(INVENTORY_PATH, encoding="utf-8"))["summary"],
        "corpus_a_gt": eval_corpus_a_gt(by_id["corpusA-full"]),
        "real_projects": {
            pid: eval_real_project(by_id[pid], pid)
            for pid in ("unicom-ry", "huaian", "cqyd", "zjyd", "unicom-ry-alt") if pid in by_id
        },
        "notes": [
            "评审器独立于被测面（GT 判分在 Python——Rust 只落事实与结构不变量断言）",
            "soft 命中口径：同文件同号未中时按锚文包含兜底（命中即记，口径列明）",
        ],
    }
    json.dump(evaluation, open(EVAL_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"[evaluate] → {EVAL_PATH}")
    gt = evaluation["corpus_a_gt"]
    print(f"  corpus-A GT: {gt['gt_total']} 条 | clause 召回 {gt['clause_recall']} | "
          f"excerpt {gt['excerpt_recall']} | category {gt['category_hit']}")
    print(f"  冲突: 澄清件 {gt['clarifying_conflicts_detected']}（#425 期望 2）| "
          f"控制价语义冲突检出 {gt['control_price_conflict_detected']}（同号口径预期 0——GAP 登记）")
    for pid, r in evaluation["real_projects"].items():
        print(f"  {pid}: REQ={r['extract']['total']} 评分项={r['extract']['scoring_reqs_now']} "
              f"(#134 基线 {r['extract']['scoring_reqs_134_baseline']}) 冲突={r['extract']['conflicts']} "
              f"unmapped {r['scoring_mapping']['unmapped_before']}→{r['scoring_mapping']['unmapped_after']}")
    return evaluation


def main() -> int:
    ap = argparse.ArgumentParser(description="#114 多文件统一矩阵验收编排器")
    ap.add_argument("--emit-spec", action="store_true", help="素材对账 + 生成 MULTIFILE_SPEC")
    ap.add_argument("--run-rust", action="store_true", help="cargo 真跑 multifile_matrix")
    ap.add_argument("--evaluate", action="store_true", help="GT/期望对照评审")
    ap.add_argument("--all", action="store_true", help="一条龙")
    args = ap.parse_args()

    if not (args.emit_spec or args.run_rust or args.evaluate or args.all):
        ap.print_help()
        return 2
    if args.all or args.emit_spec:
        emit_spec()
    if args.all or args.run_rust:
        rc = run_rust()
        if rc != 0:
            return rc
    if args.all or args.evaluate:
        evaluate()
    return 0


if __name__ == "__main__":
    sys.exit(main())
