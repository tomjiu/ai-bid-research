#!/usr/bin/env python3
"""fullchain_audit.py —— #113 全链路静态审计器（用户指令：先查清整链问题，最后跑测试）。

链路六层静态审计（不依赖上游 LLM——限流窗口亦可跑）：
  A 解析层：REQ 380 无缺失/无重复/锚点可回溯源件（识别正确性）
  B 评分识别层：check_scoring_coverage 全量报告（39 细则点逐一命中/未命中）
  C 映射层：matrix 380 全有效 + 评分映射 36 + 孤儿叶检测
  D 起草层：48 叶草稿 ground-truth 值核对 + 内部名/测试名泄漏扫描
  E 导出层：v2/r3/r4/r5 四代成品交叉缺陷回归验证
输出：JSON 报告（fullchain-audit-report.json）+ 控制台摘要
"""
import json
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict

REPO = "/home/z/my-project/ai-bid-research"
BIN = os.path.join(REPO, "bidcore/target/debug/bid-mcp-stdio")
WS = "/home/z/my-project/ws-113-r6b"
SRC = os.path.join(REPO, "real-corpus/telecom/parse-input/A-telecom-huaian-主文件.docx")
ART = os.path.join(REPO, "artifacts")
REPORT = {}

env = dict(os.environ, BID_WS=WS, BID_FS_ROOT=REPO)


def call(tool, args, timeout=120):
    line = json.dumps({"tool": tool, "args": args}, ensure_ascii=False)
    r = subprocess.run([BIN], input=line + "\n", capture_output=True, text=True,
                       env=env, timeout=timeout)
    out = r.stdout.strip().splitlines()
    return json.loads(out[-1]) if out else {"ok": False, "error": {"what": "no output"}}


# ================= A 解析层 =================
def audit_parse():
    db = json.load(open(os.path.join(WS, "db.json")))
    d = db["domain"]
    reqs = d["requirements"]
    findings = []

    # A1 锚点完整性
    no_anchor = [r["id"] for r in reqs if not r.get("anchors")]
    no_excerpt = [r["id"] for r in reqs
                  if r.get("anchors") and not (r["anchors"][0].get("excerpt") or "").strip()]
    bad_file = [r["id"] for r in reqs
                if r.get("anchors") and r["anchors"][0].get("file") != "A-telecom-huaian-主文件.docx"]
    findings.append({"A1_锚点缺失": no_anchor})
    findings.append({"A2_锚点摘录为空": no_excerpt})
    findings.append({"A3_锚点文件异常": bad_file})

    # A4 重复文本检测（同文本多 REQ）
    texts = Counter()
    for r in reqs:
        for a in r.get("anchors", []):
            t = re.sub(r"\s+", "", (a.get("excerpt") or ""))[:120]
            if t:
                texts[t] += 1
    dups = {t[:60]: c for t, c in texts.items() if c > 1}
    findings.append({"A4_重复摘录(>1次)": dups})

    # A5 摘录回源验证（抽取源 docx 全文，摘录须为子串——识别正确性）
    from docx import Document
    doc = Document(SRC)
    src_paras = [p.text for p in doc.paragraphs]
    for tb in doc.tables:
        for row in tb.rows:
            for cell in row.cells:
                src_paras.append(cell.text)
    src_flat = re.sub(r"\s+", "", "\n".join(src_paras))
    miss = []
    for r in reqs:
        for a in r.get("anchors", []):
            e = re.sub(r"\s+", "", (a.get("excerpt") or ""))
            if e and e not in src_flat:
                miss.append({"req": r["id"], "excerpt": a.get("excerpt", "")[:80]})
    findings.append({"A5_摘录无法回溯源件": miss})

    # A6 分类分布
    cat = Counter(r.get("category", "?") for r in reqs)
    return {"req_total": len(reqs), "findings": findings, "category": dict(cat)}


# ================= B 评分识别层（MCP 正门） =================
def audit_scoring():
    r = call("check_scoring_coverage", {"project_id": "PRJ-0001"})
    if not r.get("ok"):
        return {"error": r.get("error")}
    data = r["data"]
    summ = data.get("summary", {})
    crit = data.get("criteria", [])
    out = {
        "criteria_total": summ.get("criteria_total"),
        "criteria_with_points": summ.get("criteria_with_points"),
        "criteria_unmapped": summ.get("criteria_unmapped"),
        "points_total": summ.get("points_total"),
        "points_covered": summ.get("points_covered"),
        "coverage_ratio": summ.get("coverage_ratio"),
        "hard_gates_excluded": summ.get("hard_gates_excluded"),
        "suggested_deduction": summ.get("suggested_deduction"),
        "uncovered": [],
        "no_points_criteria": [],
    }
    for c in crit:
        pts = c.get("points", [])
        if not pts:
            out["no_points_criteria"].append(
                {"id": c.get("criterion_id"), "excerpt": c.get("criteria_excerpt", "")[:60],
                 "max_score": c.get("max_score"), "mapped": c.get("mapped_sections")})
        for p in pts:
            if not p.get("hit_section"):
                out["uncovered"].append(
                    {"criterion": c.get("criterion_id"), "point": p.get("point"),
                     "mapped_sections": c.get("mapped_sections"),
                     "max_score": c.get("max_score")})
    # 章节维聚合：每个 SEC 承载的未命中点数（修复定向用）
    sec_uncovered = Counter()
    for u in out["uncovered"]:
        for s in (u.get("mapped_sections") or []):
            sec_uncovered[s] += 1
    out["uncovered_by_section"] = dict(sec_uncovered)
    return out


# ================= C 映射层 =================
def audit_mapping():
    db = json.load(open(os.path.join(WS, "db.json")))
    d = db["domain"]
    secs = {s["id"]: s for s in d["sections"]}
    leaves = [s for s in d["sections"] if s["level"] == 2]
    matrix = d["matrix"]
    findings = []

    # C1 matrix 全量有效
    bad_sec_detail = ["{0}→{1!r}".format(m["id"], m.get("response_section"))
                      for m in matrix if m.get("response_section") not in secs]
    none_sec_detail = ["{0} req={1}".format(m["id"], m.get("requirement_id"))
                       for m in matrix if not m.get("response_section")]
    findings.append({"C1_矩阵指向不存在章节(前12)": bad_sec_detail[:12]})
    findings.append({"C2_矩阵无响应章节(前12)": none_sec_detail[:12]})

    # C3 REQ↔矩阵 1:1 对账（380↔380）
    req_ids = {r["id"] for r in d["requirements"]}
    mtx_reqs = {m["requirement_id"] for m in matrix}
    findings.append({"C3_REQ不在矩阵": sorted(req_ids - mtx_reqs)[:20]})
    findings.append({"C4_矩阵多出REQ": sorted(mtx_reqs - req_ids)[:20]})

    # C5 孤儿叶（无任何 REQ 指向的叶）
    pointed = {m["response_section"] for m in matrix}
    orphans = [s["id"] for s in leaves if s["id"] not in pointed]
    findings.append({"C5_孤儿叶(无REQ指向)": orphans})

    # C6 叶自带 requirement_ids 与矩阵一致性
    sec_only = []
    for s in leaves:
        own = set(s.get("requirement_ids", []))
        by_mtx = {m["requirement_id"] for m in matrix
                  if m["response_section"] == s["id"]}
        if own != by_mtx:
            sec_only.append({"sec": s["id"], "own_not_in_mtx": sorted(own - by_mtx)[:5],
                              "mtx_not_in_own": sorted(by_mtx - own)[:5]})
    findings.append({"C6_叶REQLIST与矩阵不一致": sec_only})

    # C7 评分映射
    sm = d.get("scoring_mappings", [])
    sm_secs = [x["section_id"] for x in sm]
    findings.append({"C7_评分映射指向不存在章节": [s for s in sm_secs if s not in secs]})
    # C8 评分项 REQ（category 含评分/分值）与映射对账
    sc_reqs = [r["id"] for r in d["requirements"]
               if "评分" in (r.get("category") or "") or "分" in (r.get("category") or "")]
    mapped_sc = {x["scoring_req_id"] for x in sm}
    findings.append({"C8_评分类REQ数": len(sc_reqs), "未映射": sorted(set(sc_reqs) - mapped_sc)[:20]})
    return {"matrix_total": len(matrix), "leaves": len(leaves),
            "scoring_mappings": len(sm), "findings": findings}


# ================= D 起草层 =================
GROUND_TRUTH = {
    "保证金_46,000": ["肆万陆仟", "46,000", "46000"],
    "限价_4,946,365": ["4,810,365", "136,000", "4,946,365", "4810365", "4946365"],
    "工期_37天": ["37", "三十七"],
    "有效期_90天": ["90", "九十"],
    "业绩_260万": ["260", "贰佰陆拾"],
    "业绩日_2023-05-20": ["2023"],
    "资格线_200万": ["200", "贰佰万"],
}
PROJ_NAME = "中国电信股份有限公司淮安分公司2026年淮安本地视频能力平台建设采购项目"
LEAK_PATTERNS = {
    "测试名泄漏": [r"验收#113", r"真实LLM起草", r"测试"],
    "内部项目号": [r"PRJ-\d+"],
}


def audit_draft():
    ch_dir = os.path.join(WS, "chapters")
    secs = {}
    db = json.load(open(os.path.join(WS, "db.json")))
    for s in db["domain"]["sections"]:
        secs[s["id"]] = s["title"]
    res = {"leaves": 0, "empty_or_short": [], "no_citations": [],
           "leaks": [], "gt_present": defaultdict(list), "gt_absent_all": {},
           "cap_direction_hits": []}
    all_text = []
    for fn in sorted(os.listdir(ch_dir)):
        if not fn.endswith(".json"):
            continue
        c = json.load(open(os.path.join(ch_dir, fn)))
        sid = c["section_id"]
        txt = c.get("content", "")
        res["leaves"] += 1
        if len(txt) < 200:
            res["empty_or_short"].append({"sid": sid, "len": len(txt)})
        if not c.get("citations"):
            res["no_citations"].append(sid)
        for label, pats in LEAK_PATTERNS.items():
            for p in pats:
                for m in re.finditer(p, txt):
                    res["leaks"].append({"sid": sid, "kind": label,
                                         "hit": txt[max(0, m.start()-20):m.end()+20]})
        all_text.append(txt)
        # 报价方向门（反写句检测——与引擎 E_BID_CAP_DIRECTION 同口径粗扫）
        for sent in re.split(r"[。；！？\n]", txt):
            if re.search(r"限价", sent) and re.search(r"报价|总价", sent) \
               and re.search(r"高于|超过|超出", sent):
                res["cap_direction_hits"].append({"sid": sid, "sent": sent[:80]})
    full = "\n".join(all_text)
    for k, pats in GROUND_TRUTH.items():
        hits = [p for p in pats if p in full]
        res["gt_present"][k] = hits if hits else []
        if not hits:
            res["gt_absent_all"][k] = True
    res["proj_name_count"] = full.count(PROJ_NAME[:20])
    res["total_chars"] = len(full)
    return res


# ================= E 导出层（四代交叉） =================
def audit_export():
    versions = {
        "v2": "realagent-113-v2-20261124",
        "r3": "realagent-113-v3-20261124-r3",
        "r4": "realagent-113-v3-20261124-r4",
        "r5": "realagent-113-v3-20261124-r5",
    }
    out = {}
    for tag, d in versions.items():
        path = os.path.join(ART, d, "投标文件-realagent-113.docx")
        if not os.path.exists(path):
            out[tag] = {"missing": True}
            continue
        from docx import Document
        doc = Document(path)
        paras = [p.text for p in doc.paragraphs if p.text.strip()]
        ntab = len(doc.tables)
        full = "\n".join(paras)
        for tb in doc.tables:
            for row in tb.rows:
                for cell in row.cells:
                    full += "\n" + cell.text
        rep = {
            "paras": len(paras), "tables": ntab, "chars": len(full),
            "leak_验收#113": len(re.findall(r"验收#113", full)),
            "leak_测试": len(re.findall(r"测试", full)),
            "leak_PRJ": len(re.findall(r"PRJ-\d", full)),
            "gt_保证金46k": ("肆万陆仟" in full) or ("46,000" in full),
            "gt_业绩260万": ("260" in full) or ("贰佰陆拾" in full),
            "gt_工期37": "37" in full,
            "gt_有效期90": "90" in full,
            "报价高于限价反写": len(re.findall(
                r"高于.{0,12}限价|限价.{0,12}高于|报价高于|总价高于|超过.{0,10}限价", full)),
            "proj_name_count": full.count(PROJ_NAME[:20]),
            "评标方法矛盾": ("最低价" in full and "综合评估" in full),
        }
        out[tag] = rep
    return out


def main():
    print("==== A 解析层 ====")
    REPORT["A_parse"] = audit_parse()
    a = REPORT["A_parse"]
    for f in a["findings"]:
        k = list(f.keys())[0]
        v = f[k]
        n = len(v) if isinstance(v, (list, dict)) else v
        print(f"  {k}: {n}")
    print(f"  分类: {a['category']}")

    print("==== B 评分识别层 ====")
    REPORT["B_scoring"] = audit_scoring()
    b = REPORT["B_scoring"]
    print(f"  细则 {b.get('criteria_total')} 条 / 拆点 {b.get('points_total')} / "
          f"覆盖 {b.get('points_covered')} / ratio {b.get('coverage_ratio')}")
    for u in b.get("uncovered", []):
        print(f"  未命中: {u['criterion']} 点「{u['point']}」 max_score={u['max_score']}")
    for c in b.get("no_points_criteria", []):
        print(f"  拆点失败细则: {c['id']} 「{c['excerpt']}」")

    print("==== C 映射层 ====")
    REPORT["C_mapping"] = audit_mapping()
    c = REPORT["C_mapping"]
    print(f"  matrix {c['matrix_total']} / leaves {c['leaves']} / 评分映射 {c['scoring_mappings']}")
    for f in c["findings"]:
        k = list(f.keys())[0]
        v = f[k]
        if isinstance(v, dict):
            print(f"  {k}: {v}")
        elif isinstance(v, list) and v and isinstance(v[0], dict):
            print(f"  {k}: {len(v)} -> {v[:3]}")
        else:
            print(f"  {k}: {len(v) if isinstance(v, list) else v}")
            if isinstance(v, list) and v:
                print(f"    明细: {v[:6]}")

    print("==== D 起草层(r6 中间产物) ====")
    REPORT["D_draft"] = audit_draft()
    d = REPORT["D_draft"]
    print(f"  叶 {d['leaves']} / 总字 {d['total_chars']} / 正名出现 {d['proj_name_count']}")
    print(f"  空短叶: {len(d['empty_or_short'])} / 无引用叶: {len(d['no_citations'])}")
    print(f"  泄漏命中: {len(d['leaks'])}")
    for lk in d["leaks"][:8]:
        print(f"    {lk['sid']} {lk['kind']}: …{lk['hit']}…")
    print(f"  报价方向门粗扫命中: {len(d['cap_direction_hits'])}")
    for h in d["cap_direction_hits"][:5]:
        print(f"    {h['sid']}: {h['sent']}")
    print("  ground-truth 出现面:")
    for k, v in d["gt_present"].items():
        print(f"    {k}: {'✓ ' + str(v) if v else '✗ 全缺'}")

    print("==== E 导出层（四代交叉） ====")
    REPORT["E_export"] = audit_export()
    for tag, rep in REPORT["E_export"].items():
        if rep.get("missing"):
            print(f"  {tag}: 缺")
            continue
        print(f"  {tag}: paras={rep['paras']} tables={rep['tables']} chars={rep['chars']} "
              f"验收#113={rep['leak_验收#113']} 测试={rep['leak_测试']} PRJ={rep['leak_PRJ']} "
              f"46k={rep['gt_保证金46k']} 260万={rep['gt_业绩260万']} "
              f"反写={rep['报价高于限价反写']} 矛盾={rep['评标方法矛盾']} 正名={rep['proj_name_count']}")

    with open("/home/z/my-project/scripts/fullchain-audit-report.json", "w") as f:
        json.dump(REPORT, f, ensure_ascii=False, indent=1)
    print("\n报告已写 fullchain-audit-report.json")


if __name__ == "__main__":
    main()
