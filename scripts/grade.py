#!/usr/bin/env python3
"""grade.py — corpus-A 判分器（verification-plan §2.2）

输入：夹具目录 + 一次完整流水线运行的产物（runs/<id>/{trace.jsonl, db.json}）
判分项（七项，全部确定性——不调模型、不解析自然语言语义）：
  G1 召回         REQ vs ground-truth 按 gt_id 对齐（允许条款合并但必须包含）
  G2 精确匹配     exact-25 查询命中与期望文本
  G3 矩阵 policy  EVIDENCE_LINKS 期望结论 vs 矩阵行（含 GT-04 MISSING / GT-02 翻转 / GT-13 禁绑）
  G4 引用存在率   unanchored_claims=0 且覆盖率 1.0（"引用支持"是 L3 语义面，不入本判分）
  G5 状态转换     expected-transitions 断言 vs db/trace（引擎缺口项计 SKIPPED 不判失败）
  G6 规则命中     确定性规则 8 类全命中
  G7 幂等重放     totals/chunks 前后不变

输出：report.json（逐项指标 + gt_id 级失败明细）+ --baseline 回归比对。

运行产物 db.json 约定（M1 起冻结）：
  project{status,content_version}  files[{name,parse_status,ocr_blocks}]  totals{chunks,...}
  requirements[{req_id,gt_ids[],category,clause_no,anchors[],params{}}]
  matrix[{gt_id,category,policy,policy_pre_addendum,policy_post_addendum,explicit_policy}]
  citation{unanchored_claims,coverage}  findings[{rule_code,kind,severity}]
  exact{hits,per_query[{query_id,hit,hit_text}]}  conflicts[{conflict_id,resolved,final_value,rule}]
  idempotency{files_before,files_after,totals_before,totals_after}
  sections[{id,status,last_model,dirty}]  export{dark_bid_word_scan_hits,artifact{pages_word_render,sha256}}
  resume_plan{sections[]}  last_tool_result{error}  stability{repeat_consistent}

用法：
  python3 scripts/grade.py --run runs/demo            # 判分一次运行
  python3 scripts/grade.py --self-test                # 判分器自测（完美运行 + 7 类破坏注入全捕获）
  python3 scripts/grade.py --run R --baseline prev.json
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fixture_spec as S  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
RULES_8 = ["CERT_EXPIRED", "PRICE_EXCEEDS_BUDGET", "DURATION_MISMATCH", "PAGE_LIMIT",
           "MISSING_SIGNATURE", "DARK_BID_WORD", "TODO_RESIDUE", "INJECTION_PATTERN"]


# ---------------------------------------------------------------- 路径解析（确定性）
def _req_by_gt(db: dict, gt: str) -> dict | None:
    """先查自报 gt_ids，再退对齐器（锚点/条款号/参数）——诚实管道不自报也能定位。"""
    for r in db.get("requirements", []):
        if gt in (r.get("gt_ids") or []):
            return r
    for r in db.get("requirements", []):
        if gt in aligned_gt_ids(r):
            return r
    return None


def _matrix_row(db: dict, gt: str) -> dict | None:
    for m in db.get("matrix", []):
        if m.get("gt_id") == gt:
            return m
    return None


def _file_by_key(db: dict, key: str) -> dict | None:
    for f in db.get("files", []):
        if key in (f.get("name") or ""):
            return f
    return None


def resolve_count(path: str, db: dict, trace: list) -> tuple[bool, object, str]:
    """返回 (可解析, 值, 说明)。计数型路径。"""
    if path == "requirements":
        return True, len(db.get("requirements", [])), ""
    if path == "requirements.gt_ids":
        ids = set()
        for r in db.get("requirements", []):
            ids.update(r.get("gt_ids") or [])
            ids |= aligned_gt_ids(r)  # 反标记回声：对齐器并集，自报无法虚增覆盖
        return True, sorted(ids), ""
    if path.startswith("requirements[gt=") and path.endswith("].anchors"):
        gt = path[len("requirements[gt="):-len("].anchors")]
        r = _req_by_gt(db, gt)
        return (True, len((r or {}).get("anchors", [])), "") if r else (False, None, f"REQ 未含 {gt}")
    if path.startswith("requirements[GT-") and ".params." in path:
        gt, field = path[len("requirements["):].split("].params.")
        r = _req_by_gt(db, gt.rstrip("]"))
        if not r:
            return False, None, f"REQ 未含 {gt}"
        return True, (r.get("params") or {}).get(field.rstrip("]")), ""
    if path.startswith("matrix[category=") and path.endswith("].explicit_policy"):
        cat = path[len("matrix[category="):-len("].explicit_policy")]
        n = sum(1 for m in db.get("matrix", []) if m.get("category") == cat and m.get("explicit_policy"))
        return True, n, ""
    if path == "idempotency.files_delta":
        idm = db.get("idempotency", {})
        return True, (idm.get("files_before") or 0) - (idm.get("files_after") or 0), ""
    if path == "idempotency.chunks_delta":
        idm = db.get("idempotency", {})
        return True, (idm.get("totals_before") or 0) - (idm.get("totals_after") or 0), ""
    if path == "exact_hits":
        return True, db.get("exact", {}).get("hits", 0), ""
    if path == "unanchored_claims":
        return True, db.get("citation", {}).get("unanchored_claims"), ""
    if path == "citation_coverage":
        return True, db.get("citation", {}).get("coverage"), ""
    if path == "parse_failures":
        return True, sum(1 for f in db.get("files", []) if f.get("parse_status") == "failed"), ""
    if path == "missing_sequence":
        return True, len(db.get("parse", {}).get("missing_sequence", [])), ""
    if path.startswith("files[") and "].ocr_blocks" in path:
        key = path[len("files["):path.index("].ocr_blocks")]
        f = _file_by_key(db, key)
        return (True, (f or {}).get("ocr_blocks", 0), "") if f else (False, None, f"无文件 {key}")
    if path == "sections":
        return True, len(db.get("sections", [])), ""
    if path == "files":
        return True, len(db.get("files", [])), ""
    if path == "totals.chunks":
        return True, db.get("totals", {}).get("chunks"), ""
    if path == "resume_plan.sections":
        return True, len(db.get("resume_plan", {}).get("sections", [])), ""
    if path.startswith("findings[") and "].severity=" in path:
        kind, sev = path[len("findings[kind="):].split("].severity=")
        n = sum(1 for f in db.get("findings", []) if f.get("kind") == kind and f.get("severity") == sev)
        return True, n, ""
    if path == "dark_bid_word_scan_hits":
        return True, db.get("export", {}).get("dark_bid_word_scan_hits"), ""
    if path == "findings":
        return True, len(db.get("findings", [])), ""
    return False, None, f"未支持的计数路径: {path}"


def resolve_state(path: str, db: dict, trace: list):
    """状态型路径（返回标量或小结构）。"""
    if path == "project.status":
        return True, db.get("project", {}).get("status"), ""
    if path.startswith("matrix[GT-") and "].policy" in path:
        gt, tail = path[len("matrix["):].split("].policy")
        row = _matrix_row(db, gt)
        if not row:
            return False, None, f"矩阵无 {gt} 行"
        if tail.startswith("@open_bid="):
            date = tail[len("@open_bid="):]
            post = S.PROJECT["open_bid_date_after_addendum"][:10]  # R2 P2-5：不再硬编码日期
            field = "policy_post_addendum" if date == post else "policy_pre_addendum"
            return True, row.get(field), f"@{date}"
        return True, row.get("policy"), ""
    if path.startswith("sections[") and "]" in path:
        sid, field = path[len("sections["):].split("].")
        for sec in db.get("sections", []):
            if sec.get("id") == sid:
                return True, sec.get(field), ""
        return False, None, f"无章节 {sid}"
    if path == "last_tool_result.error":
        if not trace:
            return False, None, "无轨迹"
        return True, trace[-1].get("result", {}).get("error"), ""
    if path == "artifact.pages_word_render":
        return True, db.get("export", {}).get("artifact", {}).get("pages_word_render"), ""
    if path == "artifact.sha256":
        return True, db.get("export", {}).get("artifact", {}).get("sha256"), ""
    if path == "requirements[GT-02].recheck":
        return True, db.get("recheck", {}).get("GT-02"), ""
    ok, val, note = resolve_count(path, db, trace)
    if ok:
        return True, val, note
    return False, None, f"未支持的状态路径: {path}"


def _cmp(op: str, actual, expected) -> bool:
    # 布尔陷阱（R2 P1-6）：Python 中 False==0 / True==1.0——布尔与数值互比一律判不相等
    if isinstance(actual, bool) or isinstance(expected, bool):
        return op == "==" and isinstance(actual, bool) and isinstance(expected, bool) and actual is expected
    try:
        if op == "==":
            return actual == expected
        if op == "!=":
            return actual != expected
        if op == ">=":
            return actual >= expected
        if op == "<=":
            return actual <= expected
        if op == ">":
            return actual > expected
        if op == "<":
            return actual < expected
        if op == "in":
            return actual in expected
    except TypeError:
        return False
    return False


# ---------------------------------------------------------------- 判分对齐器（反标记回声）
# 纪律（审计 S1 修正）：召回判定只认对齐器（clause_no / 锚点摘录包含 / 唯一参数值），
# 不信运行产物自报的 gt_ids——语料内已无任何 GT 标记，自报无法从源文件对齐的计入 unverified。
def _ambiguous_value_map() -> dict:
    """值→GT 集合；仅返回跨多 GT 的模糊值（用于排除）。"""
    m: dict = {}
    for gt in S.REQUIREMENTS:
        for v in gt["params"].values():
            if isinstance(v, (str, int, float)) and (isinstance(v, str) and len(v) >= 6 or
                                                    isinstance(v, (int, float)) and abs(v) >= 10_000):
                m.setdefault(v, set()).add(gt["gt_id"])
    return m


_AMBIG = {v for v, gts in _ambiguous_value_map().items() if len(gts) > 1}


def aligned_gt_ids(req: dict) -> set:
    """单条 REQ 对齐到的 GT 集合（确定性，v0.3 收紧防伪对齐——R2 审计 P0-1/2）：
    ① clause_no 双因子：命中要求该 REQ 同时携带 ≥1 个锚点或 ≥1 个佐证参数值
       （防抄目录枚举条款号伪对齐）；
    ② 锚点互含带长度约束：GT⊆REQ 要求 len(GT摘录)≥8 且 len(REQ摘录)≤3×len(GT摘录)
       （防全文锚点）；REQ⊆GT 要求 len(REQ摘录)≥8（防碎片锚点）；
    ③ 唯一参数值相等（模糊值跨 GT 共享则不参与）。"""
    ids = set()
    cl = req.get("clause_no")
    cl_list = cl if isinstance(cl, list) else ([cl] if cl else [])
    anchors = req.get("anchors") or []
    req_vals = {v for v in (req.get("params") or {}).values()
                if isinstance(v, (str, int, float)) and (
                    (isinstance(v, str) and len(v) >= 6) or
                    (isinstance(v, (int, float)) and abs(v) >= 10_000))} - _AMBIG
    has_corroboration = bool(anchors) or bool(req_vals)  # 双因子：条款号通道需佐证
    for gt in S.REQUIREMENTS:
        g = gt["gt_id"]
        if gt["clause_no"] and gt["clause_no"] in cl_list and has_corroboration:
            ids.add(g)
            continue
        hit = False
        for ga in gt.get("anchors", []):
            gex = ga.get("excerpt") or ""
            if len(gex) < 8:
                continue  # GT 摘录自身过短不参与互含（防碎片命中）
            for a in anchors:
                ex = a.get("excerpt") or ""
                if not ex:
                    continue
                if gex in ex and len(ex) <= 3 * len(gex):
                    hit = True
                elif ex in gex and len(ex) >= 8:
                    hit = True
                if hit:
                    break
            if hit:
                break
        if not hit:
            gt_vals = {v for v in gt["params"].values()
                      if isinstance(v, (str, int, float)) and (
                          (isinstance(v, str) and len(v) >= 6) or
                          (isinstance(v, (int, float)) and abs(v) >= 10_000))} - _AMBIG
            if gt_vals & req_vals:
                hit = True
        if hit:
            ids.add(g)
    return ids


# ---------------------------------------------------------------- 七判分项
def grade_recall(db: dict) -> dict:
    """G1 召回 + 精确率守门（v0.3：R2 审计 P0-3——召回之外加三道精确率硬门）：
    ① 类别一致性：每对 (REQ, GT) 对齐时 REQ.category 必须等于 GT.category；
    ② 对齐密度：单条 REQ 对齐 >3 个 GT 视为垃圾合并，记 finding 并判失败；
    ③ 反标记回声：召回只认对齐器，自报 gt_id 无法对齐的记 unverified 不计入。"""
    gt_ids = [r["gt_id"] for r in S.REQUIREMENTS]
    aligned_have: set = set()
    self_claimed: set = set()
    category_mismatch = []
    density_violations = []
    for r in db.get("requirements", []):
        ids = aligned_gt_ids(r)
        aligned_have |= ids
        self_claimed.update(r.get("gt_ids") or [])
        if len(ids) > 3:
            density_violations.append({"req_id": r.get("req_id"), "aligned": sorted(ids)})
        # category 支持单值或列表（合并 REQ 跨类别时声明全部所属类别）
        rc = r.get("category")
        req_cats = rc if isinstance(rc, list) else ([rc] if rc else [])
        for g in ids:
            gt_cat = next(x["category"] for x in S.REQUIREMENTS if x["gt_id"] == g)
            if gt_cat not in req_cats:
                category_mismatch.append({"req_id": r.get("req_id"), "gt": g,
                                          "req_category": rc, "gt_category": gt_cat})
    missing = [g for g in gt_ids if g not in aligned_have]
    # dedupe 锚点：GT-03/GT-14 各自锚点均须被某条 REQ 覆盖（未合并时各自成条；合并后同条双锚）
    dedupe_ok = True
    for g in ("GT-03", "GT-14"):
        covered = any(g in aligned_gt_ids(r) for r in db.get("requirements", []))
        if not covered:
            dedupe_ok = False
    recall = 1 - len(missing) / len(gt_ids)
    unverified = sorted(self_claimed - aligned_have)
    precision_ok = not category_mismatch and not density_violations
    return {"metric": recall, "missing": missing, "dedupe_anchors_ok": dedupe_ok,
            "unverified_self_claims": unverified,
            "category_mismatch": category_mismatch[:5], "density_violations": density_violations[:5],
            "note": "判分只认对齐器（锚点/条款号双因子/唯一参数）；类别不一致或单 REQ 对齐 >3 GT 即垃圾产物",
            "pass": recall == 1.0 and dedupe_ok and precision_ok}


def grade_exact(db: dict) -> dict:
    per = db.get("exact", {}).get("per_query", [])
    by_qid = {q["query_id"]: q for q in per}
    misses = []
    for q in S.QUERIES:
        got = by_qid.get(q["query_id"])
        if not got or not got.get("hit"):
            misses.append({"query_id": q["query_id"], "reason": "未命中"})
        elif q["expect"]["hit_text"] not in (got.get("hit_text") or ""):
            misses.append({"query_id": q["query_id"], "reason": f"命中文本不含期望（期望含『{q['expect']['hit_text'][:24]}』）"})
        elif got.get("hit_file") is not None and got.get("hit_file") != q["expect"]["hit_file"]:
            # R2 P2-7：运行产物自愿上报 hit_file 时核对期望命中文件（未上报则 V0 按自报口径放行）
            misses.append({"query_id": q["query_id"],
                           "reason": f"命中文件错（期望 {q['expect']['hit_file']}，实得 {got.get('hit_file')}）"})
    return {"metric": (len(S.QUERIES) - len(misses)) / len(S.QUERIES), "misses": misses,
            "pass": not misses,
            "note": "V0 口径：hit/hit_text 为运行产物自报，hit_file 自愿上报时才核——检索真实性待 M1 双通道落地后升 TESTED"}


def grade_policy(db: dict) -> dict:
    fails = []
    # 覆盖：资格 6 + 否决 5 显式 policy
    for cat, want in (("资格条件", 6), ("否决项", 5)):
        n = sum(1 for m in db.get("matrix", []) if m.get("category") == cat and m.get("explicit_policy"))
        if n != want:
            fails.append({"check": f"{cat}.explicit_policy", "got": n, "want": want})
    # 三态判定
    checks = [
        ("GT-04", "policy", "not_eligible", "项目经理证书缺失 → not_eligible"),
        ("GT-02", "policy_pre_addendum", "eligible", "原开标日临界有效"),
        ("GT-02", "policy_post_addendum", "not_eligible", "补遗后 EXPIRED 翻转"),
        ("GT-13", "forbidden_bind", True, "过期安许禁绑"),
    ]
    for gt, field, want, why in checks:
        row = _matrix_row(db, gt)
        got = (row or {}).get(field)
        if got != want:
            fails.append({"check": f"{gt}.{field}", "got": got, "want": want, "why": why})
    return {"fails": fails, "pass": not fails}


def grade_citation(db: dict) -> dict:
    cit = db.get("citation", {})
    unanchored = cit.get("unanchored_claims")
    coverage = cit.get("coverage")
    # R2 P1-6：类型 lint——布尔/缺型字段不得伪装通过（False==0 / True==1.0 陷阱）
    type_ok = isinstance(unanchored, int) and not isinstance(unanchored, bool) \
        and isinstance(coverage, (int, float)) and not isinstance(coverage, bool)
    ok = type_ok and unanchored == 0 and coverage == 1.0
    return {"unanchored_claims": unanchored, "coverage": coverage, "pass": ok,
            "note": "引用支持率（L3）不入自动判分，走 test-plan §5.3 人工抽检；布尔/缺型字段判 FAIL"}


def grade_rules(db: dict) -> dict:
    codes = {f.get("rule_code") for f in db.get("findings", []) if f.get("kind") == "DETERMINISTIC"}
    missed = [r for r in RULES_8 if r not in codes]
    return {"hit": len(RULES_8) - len(missed), "missed": missed, "pass": not missed}


def grade_idempotency(db: dict) -> dict:
    idm = db.get("idempotency", {})
    # R2 P1-3：None==None 假绿——before/after 任一缺失即判失败（未执行 ≠ 通过）
    complete = all(idm.get(k) is not None for k in ("files_before", "files_after",
                                                    "totals_before", "totals_after"))
    ok = complete and idm.get("files_before") == idm.get("files_after") \
        and idm.get("totals_before") == idm.get("totals_after")
    return {"files": [idm.get("files_before"), idm.get("files_after")],
            "totals": [idm.get("totals_before"), idm.get("totals_after")],
            "pass": ok,
            "note": "幂等重放未执行（字段缺失）判 FAIL，不再 None==None 假绿"}


def grade_transitions(db: dict, trace: list, et_dir: Path, only: set | None = None,
                      exclude: set | None = None) -> dict:
    """expected-transitions 断言解释器：可解析则判，引擎缺口/未支持路径 → SKIPPED。
    only/exclude：按 TC 编号过滤（一个运行产物对应一个场景，不是全部 12 个场景的叠加）。"""
    results, skipped = [], []
    for f in sorted(et_dir.glob("TC-*.json")):
        tc_id = f.stem
        if only and tc_id not in only:
            continue
        if exclude and tc_id in exclude:
            continue
        tc = json.loads(f.read_text(encoding="utf-8"))
        for a in tc.get("asserts", []):
            kind = a.get("kind")
            if kind == "engine_gap":
                skipped.append({"tc": tc["tc_id"], "gap": a.get("value"), "note": a.get("note", "")})
                continue
            if kind in ("repeat", "metric", "not_rerun", "dirty", "not_dirty", "conflict", "ocr", "set_cover", "rules_hit"):
                # set_cover / rules_hit 由 G1/G6 承接；其余需运行产物扩展字段
                if kind == "set_cover":
                    ok, val, _ = resolve_count(a["path"], db, trace)
                    want = set(a["value"])
                    results.append({"tc": tc["tc_id"], "kind": kind, "pass": ok and want <= set(val)})
                    continue
                if kind == "rules_hit":
                    codes = {x.get("rule_code") for x in db.get("findings", [])}
                    results.append({"tc": tc["tc_id"], "kind": kind,
                                    "pass": set(a["value"]) <= codes})
                    continue
                if kind == "repeat":
                    results.append({"tc": tc["tc_id"], "kind": kind,
                                    "pass": db.get("stability", {}).get("repeat_consistent") is True})
                    continue
                if kind == "dirty":
                    dirty_ids = {s["id"] for s in db.get("sections", []) if s.get("dirty")}
                    results.append({"tc": tc["tc_id"], "kind": kind,
                                    "pass": set(a["value"]) <= dirty_ids})
                    continue
                if kind == "not_dirty":
                    dirty_ids = {s["id"] for s in db.get("sections", []) if s.get("dirty")}
                    results.append({"tc": tc["tc_id"], "kind": kind,
                                    "pass": not (set(a["value"]) & dirty_ids)})
                    continue
                if kind == "not_rerun":
                    sid = a["path"][len("sections["):-1]  # R2 P2-6：精确解析括号 id，防前缀误配
                    sec = next((s for s in db.get("sections", []) if s.get("id") == sid), None)
                    results.append({"tc": tc["tc_id"], "kind": kind,
                                    "pass": sec is not None and sec.get("status") == a["value"]
                                    and sec.get("rerun_count", 0) == 0})
                    continue
                if kind == "conflict":
                    con = next((c for c in db.get("conflicts", []) if c.get("conflict_id") in a["path"]), None)
                    want = a["value"]
                    results.append({"tc": tc["tc_id"], "kind": kind,
                                    "pass": con is not None and con.get("resolved") is True
                                    and con.get("final_value") == want.get("final")
                                    and con.get("rule") == want.get("rule")})
                    continue
                if kind == "ocr":
                    key = a["path"].split("[")[1].split("]")[0]
                    fobj = _file_by_key(db, key)
                    n = (fobj or {}).get("ocr_blocks", 0)
                    results.append({"tc": tc["tc_id"], "kind": kind, "pass": _cmp(a.get("op", ">="), n, a["value"])})
                    continue
                if kind == "metric":
                    results.append({"tc": tc["tc_id"], "kind": kind, "pass": None,
                                    "note": "A/B 指标比较由 TC-10 专项报告承载"})
                    continue
                continue
            # state / count / policy / error：核心断言不可跳过（R2 P1-2）——路径不可解析即失败
            path = a.get("path", "")
            if kind == "count":
                ok, val, note = resolve_count(path, db, trace)
            else:
                ok, val, note = resolve_state(path, db, trace)
            if not ok:
                results.append({"tc": tc["tc_id"], "kind": kind, "path": path, "pass": False,
                                "reason": f"断言路径不可解析：{note}——留空字段不能中性化核心断言"})
                continue
            if kind == "error" or kind == "policy" or kind == "state":
                results.append({"tc": tc["tc_id"], "kind": kind, "path": path,
                                "pass": _cmp(a.get("op", "=="), val, a["value"]), "got": val})
            else:
                results.append({"tc": tc["tc_id"], "kind": kind, "path": path,
                                "pass": _cmp(a.get("op", "=="), val, a["value"]), "got": val})
    n_pass = sum(1 for r in results if r["pass"] is True)
    n_fail = sum(1 for r in results if r["pass"] is False)
    return {"asserts": results, "skipped": skipped,
            "pass": n_fail == 0, "summary": {"pass": n_pass, "fail": n_fail, "skipped": len(skipped)}}


def grade_run(run_dir: Path, fixtures: Path) -> dict:
    """判分一次运行产物。场景口径（R2 P1-1）：TC-06/TC-08/TC-11 是互斥场景，
    单一产物不叠加全部 12 场景——db 声明 scenario 字段（"full" 或 "TC-xx"）：
      full（默认）：全量断言除 TC-06/08/11（它们各有专用场景库自测）
      TC-06/TC-08/TC-11：只判该场景断言（真实流水线分别跑三个场景运行）"""
    db_path = run_dir / "db.json"
    trace_path = run_dir / "trace.jsonl"
    if not db_path.exists() or not trace_path.exists():
        raise SystemExit(f"[grade] 运行产物不完整：需要 {db_path} 与 {trace_path}"
                         f"（schema 见本文件 docstring；生成方式见 M1 里程碑）")
    db = json.loads(db_path.read_text(encoding="utf-8"))
    trace = [json.loads(l) for l in trace_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    scenario = db.get("scenario", "full")
    et_dir = fixtures / "corpus-A" / "expected-transitions"
    only = {scenario} if scenario.startswith("TC-") else None
    exclude = None if scenario.startswith("TC-") else {"TC-06", "TC-08", "TC-11"}
    report = {
        "run": str(run_dir),
        "scenario": scenario,
        "dimensions": {
            "G1_recall": grade_recall(db),
            "G2_exact": grade_exact(db),
            "G3_policy": grade_policy(db),
            "G4_citation": grade_citation(db),
            "G5_transitions": grade_transitions(db, trace, et_dir, only=only, exclude=exclude),
            "G6_rules": grade_rules(db),
            "G7_idempotency": grade_idempotency(db),
        },
    }
    report["verdict"] = "PASS" if all(
        d.get("pass", False) if isinstance(d, dict) else False for d in report["dimensions"].values()
    ) else "FAIL"
    return report


# ---------------------------------------------------------------- 自测：完美运行 + 破坏注入
def _perfect_db() -> dict:
    reqs = [{"req_id": f"REQ-{i:03d}", "gt_ids": [r["gt_id"]], "category": r["category"],
             "clause_no": r["clause_no"],
             "anchors": [dict(a) for a in r["anchors"]],
             "params": r["params"]}
            for i, r in enumerate(S.REQUIREMENTS, 1)]
    matrix = []
    for r in S.REQUIREMENTS:
        row = {"gt_id": r["gt_id"], "category": r["category"], "explicit_policy": True,
               "policy": {"eligible": "eligible", "not_eligible": "not_eligible"}.get(
                   r["expected_policy"], "response_required" if r["category"] in ("评分项", "技术参数", "商务要求", "格式要求") else "veto_item")}
        if r["gt_id"] == "GT-02":
            row.update({"policy": "eligible", "policy_pre_addendum": "eligible",
                        "policy_post_addendum": "not_eligible"})
        if r["gt_id"] == "GT-04":
            row["policy"] = "not_eligible"
        if r["gt_id"] == "GT-13":
            row["forbidden_bind"] = True
        matrix.append(row)
    # 补遗后终态：GT-02 翻转 not_eligible（params/锚点均取规格原值，GT-18 判 model_v2）
    row02 = _matrix_row({"matrix": matrix}, "GT-02")
    row02["policy"] = "not_eligible"
    per_q = [{"query_id": q["query_id"], "hit": True, "hit_text": q["expect"]["hit_text"]} for q in S.QUERIES]
    return {
        "project": {"status": "EXPORTED", "content_version": 2},
        "files": [
            {"name": "A-招标文件.docx", "parse_status": "ok"},
            {"name": "B1-设备清单.pdf", "parse_status": "ok"},
            {"name": "B2-投标函格式页-扫描件.pdf", "parse_status": "ocr_required", "ocr_blocks": 6},
            {"name": "B3-图纸目录.xlsx", "parse_status": "ok"},
        ],
        "totals": {"chunks": 312},
        "parse": {"missing_sequence": []},
        "requirements": reqs,
        "matrix": matrix,
        "citation": {"unanchored_claims": 0, "coverage": 1.0},
        "findings": [{"rule_code": c, "kind": "DETERMINISTIC", "severity": "BLOCKER" if i < 3 else "MAJOR"}
                     for i, c in enumerate(RULES_8)],
        "exact": {"hits": 25, "per_query": per_q},
        "conflicts": [{"conflict_id": "CONFLICT-01", "resolved": True,
                       "final_value": 4_650_000, "rule": "补遗优先"}],
        "idempotency": {"files_before": 4, "files_after": 4, "totals_before": 312, "totals_after": 312},
        "sections": [
            {"id": "资格响应", "status": "ACCEPTED", "dirty": True, "last_model": "A", "rerun_count": 1},
            {"id": "技术方案-网络与安全", "status": "ACCEPTED", "dirty": True, "last_model": "A", "rerun_count": 1},
            {"id": "商务部分-报价", "status": "ACCEPTED", "dirty": True, "last_model": "A", "rerun_count": 1},
            {"id": "售后服务方案", "status": "ACCEPTED", "dirty": False, "last_model": "A", "rerun_count": 0},
            {"id": "项目团队", "status": "ACCEPTED", "dirty": False, "last_model": "A", "rerun_count": 0},
            {"id": "格式与签署", "status": "ACCEPTED", "dirty": False, "last_model": "A", "rerun_count": 0},
            {"id": "SEC-02", "status": "DRAFTED", "dirty": False, "last_model": "B", "rerun_count": 0},
        ],
        "recheck": {"GT-02": "全项目有效期重检已执行"},
        "export": {"dark_bid_word_scan_hits": 0, "artifact": {"pages_word_render": 168, "sha256": "deadbeef" * 8}},
        "resume_plan": {"sections": ["SEC-02", "SEC-03"]},
        "stability": {"repeat_consistent": True},
        "last_tool_result": {"error": None},
    }


TRACE_PERFECT = [
    {"seq": 1, "tool": "create_bid_project", "result": {"project_id": "P-001"}},
    {"seq": 2, "tool": "import_tender_files", "result": {"files": 4}},
    {"seq": 3, "tool": "extract_requirements", "result": {"requirements": 25}},
    {"seq": 4, "tool": "export_bid_document", "result": {"sha256": "deadbeef" * 8}},
]

CORRUPTIONS = {
    "漏表格条款GT-11": lambda db: db.update(requirements=[r for r in db["requirements"] if "GT-11" not in r["gt_ids"]]),
    "矩阵GT-04误判eligible": lambda db: db["matrix"][3].update(policy="eligible"),
    "未锚定承诺": lambda db: db["citation"].update(unanchored_claims=2),
    "规则漏报DARK_BID_WORD": lambda db: db.update(findings=[f for f in db["findings"] if f["rule_code"] != "DARK_BID_WORD"]),
    "幂等重复入块": lambda db: db["idempotency"].update(totals_after=312 + 96),
    "精确查询Q-04未命中": lambda db: (db["exact"].update(hits=24), db["exact"]["per_query"][3].update(hit=False)),
    # ---- R2 审计新增攻击样本（固化进回归）----
    # 全文锚点：把全部 A 文摘录拼成单锚（≈R2 实测的 9670 字符全文粘贴）——
    # 旧对齐器下 25/25 假绿；v0.3 的 3× 长度上限必须整体拒绝
    "全文锚点伪对齐": lambda db: db.update(requirements=[
        {"req_id": "REQ-全文", "gt_ids": [], "category": "资格条件", "clause_no": None,
         "anchors": [{"file": "A-招标文件.docx", "kind": "para", "locator": "全文粘贴",
                      "excerpt": "。".join(a["excerpt"] for r in S.REQUIREMENTS
                                           for a in r["anchors"] if a["file"] == "A-招标文件.docx")}],
         "params": {}}]),
    "垃圾REQ伪对齐": lambda db: db.update(requirements=[
        {"req_id": f"REQ-junk-{i}", "gt_ids": [], "category": "其他",
         "clause_no": [r["clause_no"] for r in S.REQUIREMENTS if r["gt_id"] != "GT-11"],
         "anchors": [{"file": "A-招标文件.docx", "kind": "para", "locator": "任意", "excerpt": "投标报价超过招标控制价（最高限价）的，作否决投标处理。"}],
         "params": {"model_v2": S.MODELS["firewall_new"]}} for i in range(24)]),
    "布尔字段citation伪装": lambda db: db["citation"].update(unanchored_claims=False, coverage=True),
    "幂等字段缺失": lambda db: db.update(idempotency={}),
}


def _scenario_db(base: dict, kind: str) -> dict:
    """场景专用库：TC-06 断点恢复 / TC-08 换模型 / TC-11 越级防护。"""
    db = copy.deepcopy(base)
    if kind == "TC-06":
        db["project"]["status"] = "DRAFTING"
        db["sections"] = [
            {"id": "SEC-01", "status": "ACCEPTED", "dirty": False, "last_model": "A", "rerun_count": 0},
            {"id": "SEC-02", "status": "DRAFTING", "dirty": False, "last_model": "A", "rerun_count": 0},
            {"id": "SEC-03", "status": "PENDING", "dirty": False, "last_model": None, "rerun_count": 0},
        ]
    elif kind == "TC-08":
        db["sections"] = [
            {"id": "SEC-01", "status": "ACCEPTED", "dirty": False, "last_model": "A", "rerun_count": 0},
            {"id": "SEC-02", "status": "DRAFTED", "dirty": False, "last_model": "B", "rerun_count": 1},
        ]
    elif kind == "TC-11":
        db["project"]["status"] = "FILES_IMPORTED"
        db["sections"] = []
        db["last_tool_result"] = {"error": "E_STATE"}
    return db


def _grade_db(db: dict, trace: list, fixtures: Path, only: set | None = None,
              exclude: set | None = None) -> dict:
    et_dir = fixtures / "corpus-A" / "expected-transitions"
    return {
        "G1_recall": grade_recall(db),
        "G2_exact": grade_exact(db),
        "G3_policy": grade_policy(db),
        "G4_citation": grade_citation(db),
        "G5_transitions": grade_transitions(db, trace, et_dir, only=only, exclude=exclude),
        "G6_rules": grade_rules(db),
        "G7_idempotency": grade_idempotency(db),
    }


def self_test(fixtures: Path) -> int:
    import tempfile
    failed = 0
    scenarios = {"完整运行（除 TC-06/08/11 场景外全部断言）": (_perfect_db(), TRACE_PERFECT, None, {"TC-06", "TC-08", "TC-11"}),
                 "TC-06 断点恢复场景": (_scenario_db(_perfect_db(), "TC-06"), TRACE_PERFECT, {"TC-06"}, None),
                 "TC-08 换模型场景": (_scenario_db(_perfect_db(), "TC-08"), TRACE_PERFECT, {"TC-08"}, None),
                 "TC-11 越级防护场景": (_scenario_db(_perfect_db(), "TC-11"),
                                        TRACE_PERFECT[:-1] + [{"seq": 4, "tool": "draft_response_section", "result": {"error": "E_STATE"}}],
                                        {"TC-11"}, None)}
    for name, (db, trace, only, exclude) in scenarios.items():
        dims = _grade_db(db, trace, fixtures, only=only, exclude=exclude)
        bad = [k for k, v in dims.items() if not v.get("pass")]
        mark = "✓" if not bad else "✗"
        print(f"[自测] {mark} {name}：{'全绿' if not bad else '失败 ' + str(bad)}")
        if bad:
            failed += 1

    # 破坏注入：每处破坏必须被对应判分项捕获
    expectations = {
        "漏表格条款GT-11": "G1_recall",
        "矩阵GT-04误判eligible": "G3_policy",
        "未锚定承诺": "G4_citation",
        "规则漏报DARK_BID_WORD": "G6_rules",
        "幂等重复入块": "G7_idempotency",
        "精确查询Q-04未命中": "G2_exact",
        "标记回声伪造召回（自报无锚点）": "G1_recall",
        "全文锚点伪对齐": "G1_recall",
        "垃圾REQ伪对齐": "G1_recall",
        "布尔字段citation伪装": "G4_citation",
        "幂等字段缺失": "G7_idempotency",
    }

    def _corrupt_echo(db):
        """标记回声：REQ 自报全部 gt_id 但不带任何锚点/条款号/参数——对齐器必须拒绝。"""
        db["requirements"] = [
            {"req_id": "REQ-echo", "gt_ids": [f"GT-{i:02d}" for i in range(1, 26)],
             "category": "其他", "clause_no": None, "anchors": [], "params": {}}
        ]

    CORRUPTIONS2 = dict(CORRUPTIONS)
    CORRUPTIONS2["标记回声伪造召回（自报无锚点）"] = _corrupt_echo
    for name, corrupt in CORRUPTIONS2.items():
        db = _perfect_db()
        corrupt(db)
        dims = _grade_db(db, TRACE_PERFECT, fixtures, exclude={"TC-06", "TC-08", "TC-11"})
        dim_fail = [k for k, v in dims.items() if not v.get("pass")]
        ok = expectations.get(name) in dim_fail
        mark = "✓" if ok else "✗"
        print(f"[自测] {mark} 破坏『{name}』被捕获（失败维度: {dim_fail}）")
        if not ok:
            failed += 1

    # dedupe 合并运行：GT-03/GT-14 合为 1 条 REQ（24 条）——G1 召回与 TC-01 计数都须通过
    db_m = _perfect_db()
    r03 = next(r for r in db_m["requirements"] if "GT-03" in r["gt_ids"])
    r14 = next(r for r in db_m["requirements"] if "GT-14" in r["gt_ids"])
    r03["clause_no"] = [r03["clause_no"], r14["clause_no"]]
    r03["anchors"] = r03["anchors"] + r14["anchors"]
    r03["gt_ids"] = ["GT-03", "GT-14"]
    r03["category"] = [r03["category"], r14["category"]]  # 合并 REQ 声明全部所属类别
    db_m["requirements"] = [r for r in db_m["requirements"] if "GT-14" not in r["gt_ids"] or r is r03]
    dims = _grade_db(db_m, TRACE_PERFECT, fixtures, exclude={"TC-06", "TC-08", "TC-11"})
    bad = [k for k, v in dims.items() if not v.get("pass")]
    ok = not bad
    print(f"[自测] {'✓' if ok else '✗'} dedupe 合并运行（24 REQ 双锚点双编号）：{'全绿' if ok else '失败 ' + str(bad)}")
    if not ok:
        failed += 1

    # 场景破坏：TC-11 越级被放行（出现了副作用章节）
    db11 = _scenario_db(_perfect_db(), "TC-11")
    db11["sections"] = [{"id": "越级章节", "status": "DRAFTING", "dirty": False, "last_model": "A", "rerun_count": 0}]
    db11["last_tool_result"] = {"error": None}
    dims = _grade_db(db11, TRACE_PERFECT, fixtures, only={"TC-11"})
    g5_fail = [r for r in dims["G5_transitions"]["asserts"] if r["pass"] is False]
    ok = bool(g5_fail)
    print(f"[自测] {'✓' if ok else '✗'} 破坏『越级E_STATE被放行』被捕获（TC-11 断言失败 {len(g5_fail)} 条）")
    if not ok:
        failed += 1

    # 场景破坏 2（R2 P1-2）：TC-11 留空字段中性化——删 last_tool_result + 空 trace，断言必须变红而非 SKIP
    db11b = _scenario_db(_perfect_db(), "TC-11")
    db11b.pop("last_tool_result", None)
    dims = _grade_db(db11b, [], fixtures, only={"TC-11"})
    g5_fail = [r for r in dims["G5_transitions"]["asserts"] if r["pass"] is False]
    ok = bool(g5_fail)
    print(f"[自测] {'✓' if ok else '✗'} 破坏『留空字段中性化 E_STATE 断言』被捕获（不可解析即失败 {len(g5_fail)} 条）")
    if not ok:
        failed += 1

    print(f"\n判分器自测：{'全部通过' if failed == 0 else f'{failed} 项失败'}")
    return 0 if failed == 0 else 1


def main() -> int:
    args = sys.argv[1:]
    fixtures = REPO / "fixtures"
    if "--self-test" in args:
        return self_test(fixtures)
    if "--run" in args:
        run_dir = Path(args[args.index("--run") + 1])
        report = grade_run(run_dir, fixtures)
        out = run_dir / "report.json"
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"verdict": report["verdict"],
                          "dimensions": {k: v.get("pass") for k, v in report["dimensions"].items()},
                          "report": str(out)}, ensure_ascii=False, indent=2))
        if "--baseline" in args:
            base = json.loads(Path(args[args.index("--baseline") + 1]).read_text(encoding="utf-8"))
            regress = [k for k in report["dimensions"]
                       if base.get("dimensions", {}).get(k, {}).get("pass") and not report["dimensions"][k].get("pass")]
            print("回归比对：", regress if regress else "无回退")
            if regress:
                return 1
        return 0 if report["verdict"] == "PASS" else 1
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
