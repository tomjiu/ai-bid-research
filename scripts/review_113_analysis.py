#!/usr/bin/env python3
"""#113 独立审校面分析（模型审校——四维：虚构参数/证据引用/遗漏/重复模板）。

用法: python3 scripts/review_113_analysis.py <chapters_dir> <db.json>
（chapters_dir = 验收工作区 chapters/；db.json = 工作区账本）
"""
import json, glob, re, hashlib
from collections import Counter

import sys
CH = sys.argv[1] if len(sys.argv) > 1 else "/tmp/out113/chapters"
DB = json.load(open(sys.argv[2] if len(sys.argv) > 2 else "/tmp/out113/db.json"))
dom = DB["domain"]
reqs = {r["id"]: r for r in dom["requirements"]}
secs = {s["id"]: s for s in dom.get("outline", dom.get("sections", []))}

chapters = {}
for p in sorted(glob.glob(f"{CH}/SEC-*.json")):
    d = json.load(open(p))
    chapters[d["section_id"]] = d

print(f"章节数: {len(chapters)}")

# ---- 维度1：重复模板（跨章 n-gram 相似度——3-gram Jaccard 近似 + 开头句聚类）----
def grams(s, n=8):
    s = re.sub(r"\s+", "", s)
    return {s[i:i+n] for i in range(0, max(0, len(s)-n), 4)}

ids = sorted(chapters)
gram_sets = {i: grams(chapters[i]["content"]) for i in ids}
pairs = []
for a_i in range(len(ids)):
    for b_i in range(a_i+1, len(ids)):
        a, b = ids[a_i], ids[b_i]
        ga, gb = gram_sets[a], gram_sets[b]
        if not ga or not gb:
            continue
        j = len(ga & gb) / len(ga | gb)
        if j > 0.25:
            pairs.append((round(j, 2), a, b))
pairs.sort(reverse=True)
print(f"\n== 维度1 重复模板 ==")
print(f"高相似章对（3-gram Jaccard>0.25）: {len(pairs)}")
for j, a, b in pairs[:8]:
    print(f"  {j} {a}~{b}")

# 开头句式聚类（同模板起笔）
openers = Counter()
for i in ids:
    first = re.split(r"[。\n]", chapters[i]["content"][50:200])[0][:40]
    openers[first] += 1
print("开头句式 TOP5:", openers.most_common(5))

# ---- 维度2：证据引用面（合成证据被当实料引用？）----
print(f"\n== 维度2 证据引用 ==")
ev_cite = Counter()
ev_claim = []
for i in ids:
    c = chapters[i]["content"]
    for m in re.finditer(r"\[EV-\d+\]", c):
        ev_cite[m.group(0)] += 1
    # 「具备/拥有 + 资质/业绩」断言（无 EV 引用同句 = 未锚断言样本）
    for m in re.finditer(r"[^.。\n]*(?:具备|拥有|持有)[^.。\n]*(?:资质|证书|业绩)[^.。\n]*[。.]", c):
        s = m.group(0)
        if "[EV-" not in s and "[REQ-" not in s:
            ev_claim.append((i, s.strip()[:80]))
print("EV 引用分布:", dict(ev_cite))
print(f"未锚资质断言（无同句 EV/REQ 引用）: {len(ev_claim)} 条")
for i, s in ev_claim[:6]:
    print(f"  {i}: {s}")

# ---- 维度3：遗漏面（uncovered REQ）----
print(f"\n== 维度3 遗漏 ==")
covered = set()
for i in ids:
    for m in re.finditer(r"\[REQ-\d+\]", chapters[i]["content"]):
        covered.add(m.group(0)[1:-1])
all_req = set(reqs)
uncov = sorted(all_req - covered, key=lambda x: int(x.split("-")[1]))
print(f"未被任何章节引用的 REQ: {len(uncov)} → {uncov[:12]}")
# 关键面：否决项/评分项遗漏
cat_unc = Counter(reqs[r]["category"] for r in uncov)
print("未覆盖分类分布:", dict(cat_unc))

# ---- 维度4：虚构参数采样（数值与招标原文对账——关键决策数）----
print(f"\n== 维度4 数值对账（决策参数）==")
checks = {  # (正则, 期望说明)
    "投标有效期": (r"有效期[^。]{0,30}?(\d+)\s*天", "90 天（REQ-0105/PROFILE）"),
    "工期/交付": (r"(?:交付|工期|调测)[^。]{0,20}?(\d+)\s*(?:日历天|天)", "37 天（7+30，PROFILE duration_days）"),
    "最高限价": (r"(?:最高限价|最高投标限价)[^。]{0,30}?([\d,.]+)\s*万?元", "494.6 万限价内（bid_amount=480万）"),
}
for name, (pat, expect) in checks.items():
    hits = []
    for i in ids:
        for m in re.finditer(pat, chapters[i]["content"]):
            hits.append((i, m.group(1)))
    print(f"  {name}: 期望 {expect} | 命中 {len(hits)} 处 → {hits[:6]}")
