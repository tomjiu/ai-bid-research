#!/usr/bin/env python3
"""probe_songjiang_points.py —— 批八审计：跨语料 D1 拆点正确性抽验。

松江（songjiang）用当前引擎拆出 8 细则/41 点（multifile 旧基线为 0）。
纪律：拆出的点必须能回源到源件原文（非虚构）——与 huaian A5 同款回源法。
"""
import json
import os
import re
import shutil
import subprocess

REPO = "/home/z/my-project/ai-bid-research"
BIN = os.path.join(REPO, "bidcore/target/debug/bid-mcp-stdio")
SRC = os.path.join(REPO, "real-corpus/telecom/parse-input/"
                     "A-telecom-shanghai-songjiang-光终端放装-招标文件.docx")
WS = "/home/z/my-project/ws-probe-songjiang"

shutil.rmtree(WS, ignore_errors=True)
os.makedirs(WS)
env = dict(os.environ, BID_WS=WS, BID_FS_ROOT=REPO)


def call(tool, args, timeout=240):
    line = json.dumps({"tool": tool, "args": args}, ensure_ascii=False)
    r = subprocess.run([BIN], input=line + "\n", capture_output=True, text=True,
                       env=env, timeout=timeout)
    out = r.stdout.strip().splitlines()
    return json.loads(out[-1]) if out else {}


r = call("create_bid_project", {"name": "拆点抽验-songjiang",
                                "bid_deadline": "2026-12-31", "mode": "明标",
                                "external_key": "probe-sj-pts"})
pid = r["data"]["project_id"]
call("import_tender_files", {"project_id": pid, "files": [
    {"upload_ref": SRC, "filename": os.path.basename(SRC), "kind": "招标文件"}]})
call("extract_requirements", {"project_id": pid})
r = call("build_outline", {"project_id": pid, "target_total_chars": 48000,
                           "max_reqs_per_leaf": 8, "project_version": "latest"})

# 源件全文（含表格）
from docx import Document
doc = Document(SRC)
paras = [p.text for p in doc.paragraphs]
for tb in doc.tables:
    for row in tb.rows:
        for cell in row.cells:
            paras.append(cell.text)
src_flat = re.sub(r"\s+", "", "\n".join(paras))

cov = call("check_scoring_coverage", {"project_id": pid})
pts_all = []
for c in cov.get("data", {}).get("criteria", []):
    for p in c.get("points", []):
        pts_all.append((c.get("criterion_id"), p.get("point")))

print(f"拆点总数: {len(pts_all)}（回源抽验）")
fail = []
for cid, pt in pts_all:
    p = re.sub(r"\s+", "", pt or "")
    if p and p not in src_flat:
        fail.append((cid, pt))
    else:
        print(f"  ✓ {cid}: {pt[:40]}")
for cid, pt in fail:
    print(f"  ✗ 无法回源: {cid}: {pt[:60]}")
print(f"回源: {len(pts_all)-len(fail)}/{len(pts_all)}，无法回源 {len(fail)}")
shutil.rmtree(WS, ignore_errors=True)
