#!/usr/bin/env python3
"""repro_112.py —— #112 松岭 67 关键点产品复验的机器面（只读复跑，不改产品）。

口径（issue #112 验收原文）：
  - 原件 PDF 重跑抽取（真实工具链：create → import → extract）
  - 七类分类分布（资格条件/否决项/评分项/技术参数/商务要求/格式要求/其他）
  - 16 条人工复核金标准（expected/requirements.reviewed.json）逐项召回：
    数值+单位双侧归一（NFKC 康熙部首 + 千分位剥离）匹配，记录 REQ/页码出处
  - ★标记面（params.star）与商务表 ★锚文对照
  - 误分类抽样（其他/格式要求两类——锚文随行供人工判读）
  - 67 条原始材料是否取得：本脚本不碰 67 条（材料四路皆缺，见报告）——
    不凑数、不改抽取器、不自动升级金标准。

用法: python3 scripts/repro_112.py <ws_dir> <out_json> [bid-mcp-stdio 路径]
默认二进制 = 仓内 bidcore/target/debug/bid-mcp-stdio（重跑前自行确认基线提交）。
"""
import json
import os
import subprocess
import sys
import unicodedata
import hashlib
import time
from collections import Counter

WS, OUT = sys.argv[1], sys.argv[2]
BIN = sys.argv[3] if len(sys.argv) > 3 else os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "bidcore/target/debug/bid-mcp-stdio")
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PDF = os.path.join(REPO, "fixtures/songling-232762/tender/光纤租赁费招标文件.pdf")
_gr_doc = json.load(open(os.path.join(REPO, "fixtures/songling-232762/expected/requirements.reviewed.json")))
GR = _gr_doc["requirements"] if isinstance(_gr_doc, dict) else _gr_doc

env = dict(os.environ, BID_WS=WS, BID_FS_ROOT=REPO)
os.makedirs(WS, exist_ok=True)

steps = []  # (tool, ok, ms)


def call(tool, args):
    line = json.dumps({"tool": tool, "args": args}, ensure_ascii=False)
    t0 = time.time()
    r = subprocess.run([BIN], input=line + "\n", capture_output=True, text=True,
                       env=env, timeout=600)
    ms = int((time.time() - t0) * 1000)
    out = r.stdout.strip().splitlines()
    reply = json.loads(out[-1]) if out else {"ok": False, "error": "no output"}
    steps.append({"tool": tool, "ok": bool(reply.get("ok")), "ms": ms,
                  "returncode": r.returncode})
    return reply


# ---- 16 条金标准的检索键（run-notes.md §2/§3 的数值+单位与同义双锚）----
GR_KEYS = {
    "GR-001": ["295"],
    "GR-002": ["30M/s", "30M／s", "50M/s", "50M／s"],
    "GR-003": ["95%", "95％"],
    "GR-004": ["360"],
    "GR-005": ["15日历天", "15日历天调测"],
    "GR-006": ["双电源"],
    "GR-007": ["0.2dB", "0.2dB／", "0.2dB/"],
    "GR-008": ["服务地点"],
    "GR-009": ["验收要求"],
    "GR-010": ["17,000", "17000", "8,500", "8500"],
    "GR-011": ["20,000", "20000"],
    "GR-012": ["1,195,800", "1195800"],
    "GR-013": ["不缴纳", "无需缴纳"],
    "GR-014": ["90日", "90日历天", "九十日"],
    "GR-015": ["365", "1年", "一年"],
    "GR-016": ["不接受联合体", "不接受联合体投标", "联合体"],
}


def norm(s: str) -> str:
    """检索面归一：NFKC（康熙部首兼容字）+ 千分位剥离（#267 norm_n3 口径）。"""
    s = unicodedata.normalize("NFKC", s)
    return s.replace(",", "").replace("，", "")


# ---- 真实工具链三步 ----
r1 = call("create_bid_project", {
    "name": "复验#112", "bid_deadline": "2026-12-31", "mode": "明标",
    "external_key": "repro-112"})
assert r1.get("ok"), r1
pid = r1.get("project", {}).get("project_id") or "PRJ-0001"

r2 = call("import_tender_files", {
    "project_id": pid,
    "files": [{"upload_ref": PDF, "filename": "光纤租赁费招标文件.pdf",
               "kind": "招标文件", "expected_pages": 65}]})
assert r2.get("ok"), r2

r3 = call("extract_requirements", {"project_id": pid, "scope": "all"})
assert r3.get("ok"), r3

# ---- db.json 读取与核验面 ----
db = json.load(open(os.path.join(WS, "db.json")))
reqs = db["domain"]["requirements"]
cats = dict(Counter(r["category"] for r in reqs))
print(f"REQ 总数: {len(reqs)} | 七类分布: {json.dumps(cats, ensure_ascii=False)}")

# REQ 检索面：锚摘录（归一后拼接）+ 条款号
def req_haystack(r):
    parts = [a.get("excerpt", "") for a in r.get("anchors", [])]
    parts.append(r.get("clause_no") or "")
    return norm(" ".join(parts))


hay = {r["id"]: req_haystack(r) for r in reqs}
by_id = {r["id"]: r for r in reqs}

# 16 条逐项召回
gr_results = []
for gr in GR:
    gid = gr["id"]
    keys = GR_KEYS.get(gid, [])
    hits = []
    for rid, h in hay.items():
        for k in keys:
            if norm(k) in h:
                r = by_id[rid]
                page = next((a.get("page") for a in r.get("anchors", []) if a.get("page")), None)
                hits.append({"req": rid, "category": r["category"],
                             "key": k, "page": page,
                             "excerpt": next((a.get("excerpt", "") for a in r.get("anchors", [])
                                              if norm(k) in norm(a.get("excerpt", ""))), "")[:120]})
    gr_results.append({
        "gr": gid, "statement": gr.get("statement", "")[:80],
        "expected_category": gr.get("category"),
        "hit": bool(hits), "hits": hits,
        "category_match": any(h["category"] == gr.get("category") for h in hits),
    })
hit_n = sum(1 for g in gr_results if g["hit"])
cat_match_n = sum(1 for g in gr_results if g["category_match"])
print(f"16 条金标准召回: {hit_n}/16 | 其中分类与金标准一致: {cat_match_n}/16")

# ★标记面
star_reqs = [{"req": r["id"], "category": r["category"],
              "excerpt": (r.get("anchors") or [{}])[0].get("excerpt", "")[:80]}
             for r in reqs if (r.get("params") or {}).get("star")]
star_anchor_hits = [
    {"req": r["id"], "category": r["category"],
     "excerpt": a.get("excerpt", "")[:100]}
    for r in reqs for a in r.get("anchors", [])
    if "★" in a.get("excerpt", "") or "☆" in a.get("excerpt", "")]
print(f"★标记 REQ（params.star）: {len(star_reqs)} | 锚文含★字符: {len(star_anchor_hits)}")

# 误分类抽样（其他/格式要求——确定性抽样：每类前 12 条 + 均匀步进 8 条）
def sample(cat):
    items = [r for r in reqs if r["category"] == cat]
    n = len(items)
    if n == 0:
        return []
    idxs = sorted(set(list(range(min(12, n))) + list(range(0, n, max(1, n // 8)))[:8]))
    return [{"req": items[i]["id"],
             "clause": items[i].get("clause_no"),
             "anchors": [a.get("excerpt", "")[:90] for a in items[i].get("anchors", [])[:2]],
             "pages": [a.get("page") for a in items[i].get("anchors", [])[:3]]}
            for i in idxs]

out = {
    "pdf_sha256": hashlib.sha256(open(PDF, "rb").read()).hexdigest(),
    "pdf_bytes": os.path.getsize(PDF),
    "steps": steps,
    "req_total": len(reqs),
    "category_counts": cats,
    "gr_recall": {"hit": hit_n, "total": 16, "category_match": cat_match_n,
                  "items": gr_results},
    "star": {"params_star": star_reqs, "anchor_star": star_anchor_hits},
    "misclass_samples": {"其他": sample("其他"), "格式要求": sample("格式要求"),
                         "技术参数": sample("技术参数"), "商务要求": sample("商务要求")},
}
json.dump(out, open(OUT, "w"), ensure_ascii=False, indent=1)
print(f"报告数据落盘: {OUT}")
