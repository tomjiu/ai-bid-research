#!/usr/bin/env python3
"""m145 复现：松岭块 612-618 圈号子项（1）（2）（5）的 REQ 开/不开不一致。

步骤：create → import（PDF）→ extract → 对块 612-618 逐块：
  - get_block_requirements（单块 REQ 锚归属——#183 只读发现面）
  - 块原文文本（含行号/圈号形态）
产出 stdout 对照表 + 落盘 /tmp/m145-out/（614-616 应无 REQ 锚——漏抽实锤）。
"""
import json
import os
import subprocess
import sys

REPO = "/home/z/my-project/ai-bid-research"
BIN = os.path.join(REPO, "bidcore/target/debug/bid-mcp-stdio")
WS = "/tmp/m145-ws"
PDF = REPO + "/fixtures/songling-232762/tender/光纤租赁费招标文件.pdf"

env = dict(os.environ, BID_WS=WS, BID_FS_ROOT=REPO)
os.makedirs(WS, exist_ok=True)


def call(tool, args):
    line = json.dumps({"tool": tool, "args": args}, ensure_ascii=False)
    r = subprocess.run([BIN], input=line + "\n", capture_output=True, text=True,
                       env=env, timeout=600)
    out = r.stdout.strip().splitlines()
    return json.loads(out[-1]) if out else {}


r = call("create_bid_project", {"name": "m145-repro", "bid_deadline": "2026-12-31",
                                "mode": "明标", "external_key": "m145-repro"})
pid = r["data"]["project_id"]
r = call("import_tender_files", {"project_id": pid, "files": [
    {"upload_ref": PDF, "filename": "光纤租赁费招标文件.pdf", "kind": "招标文件"}]})
fid = (r["data"].get("file_ids") or [None])[0]
print("pid:", pid, "| import:", r.get("ok"), "| file_id:", fid)
if not fid:
    print("import files 结构:", json.dumps(r["data"], ensure_ascii=False)[:400])
    sys.exit(1)

call("extract_requirements", {"project_id": pid})

# 找 file_id（若上面没拿到）
if not fid:
    r = call("get_bid_project_state", {"project_id": pid})
    print("state:", json.dumps(r.get("data", {}), ensure_ascii=False)[:600])

for idx in range(610, 620):
    r = call("get_block_requirements", {"project_id": pid, "file_id": fid, "block_idx": idx})
    d = r.get("data", {})
    text = d.get("text") or ""
    req_ids = d.get("req_ids") or []
    print(f"--- block {idx}: req_ids={req_ids} | verdict={d.get('verdict')}")
    print(f"    text: {text[:90]!r}")
