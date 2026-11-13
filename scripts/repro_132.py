#!/usr/bin/env python3
"""repro_132.py —— #132 修复前后复现：松岭 65 页整件抽取 → 评分面/REQ-0180 状态
用法: python3 scripts/repro_132.py <ws_dir> <out_json>
"""
import json, os, subprocess, sys

WS, OUT = sys.argv[1], sys.argv[2]
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIN = os.path.join(REPO, "bidcore/target/debug/bid-mcp-stdio")
PDF = os.path.join(REPO, "fixtures/songling-232762/tender/光纤租赁费招标文件.pdf")

env = dict(os.environ, BID_WS=WS, BID_FS_ROOT=REPO)
os.makedirs(WS, exist_ok=True)

def call(tool, args):
    line = json.dumps({"tool": tool, "args": args}, ensure_ascii=False)
    r = subprocess.run([BIN], input=line + "\n", capture_output=True, text=True, env=env, timeout=300)
    out = r.stdout.strip().splitlines()
    return json.loads(out[-1]) if out else {"ok": False, "error": "no output"}

r1 = call("create_bid_project", {
    "name": "复现#132", "bid_deadline": "2026-12-31", "mode": "明标", "external_key": "repro-132"})
assert r1.get("ok"), r1
pid = r1.get("project", {}).get("project_id") or r1.get("project_id") or "PRJ-0001"
print("project:", pid)

r2 = call("import_tender_files", {
    "project_id": pid, "files": [{"upload_ref": PDF, "filename": "光纤租赁费招标文件.pdf",
                                   "kind": "招标文件", "expected_pages": 65}]})
assert r2.get("ok"), r2
print("import ok")

r3 = call("extract_requirements", {"project_id": pid, "scope": "all"})
assert r3.get("ok"), r3
stats = r3.get("requirements") or r3.get("stats") or {}
print("extract ok:", json.dumps(stats, ensure_ascii=False)[:200])

db = json.load(open(os.path.join(WS, "db.json")))
reqs = db["domain"]["requirements"]
from collections import Counter
cats = dict(Counter(r["category"] for r in reqs))
print(f"REQ 总数: {len(reqs)} | 类别: {cats}")

out = {"total": len(reqs), "categories": cats, "scoring": [], "req0180": None}
for r in reqs:
    if r["category"] == "评分项":
        out["scoring"].append({
            "id": r["id"], "score": (r.get("params") or {}).get("score"),
            "section": (r.get("params") or {}).get("section"),
            "anchor": ((r.get("anchors") or [{}])[0].get("excerpt") or "")[:150],
            "params_keys": sorted((r.get("params") or {}).keys()),
        })
    if r["id"] == "REQ-0180":
        out["req0180"] = {"category": r["category"],
                          "params": r.get("params") or {},
                          "anchors": [a.get("excerpt", "")[:200] for a in r.get("anchors", [])]}
json.dump(out, open(OUT, "w"), ensure_ascii=False, indent=1)

sc = [s for s in out["scoring"] if s["score"] is not None]
print(f"带分值评分项: {len(sc)} 条, 分值合计: {sum(s['score'] for s in sc)}")
for s in out["scoring"]:
    print(f"  {s['id']} score={s['score']} section={s.get('section')} keys={s['params_keys']}")
    print(f"    anchor: {s['anchor'][:80]}")
if out["req0180"]:
    print("\n=== REQ-0180 ===")
    print("category:", out["req0180"]["category"])
    print("params:", json.dumps(out["req0180"]["params"], ensure_ascii=False)[:400])
    for a in out["req0180"]["anchors"]:
        print("anchor:", a[:150])
