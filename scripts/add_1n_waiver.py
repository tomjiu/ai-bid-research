#!/usr/bin/env python3
"""add_1n_waiver.py —— 给测试文件的 export_bid_document json 块批量插入门 1n 豁免
（mock 链测试适配——按事实改断言不删门）"""
import re, sys

REASON = "mock 链工程验收——非正式投标（#130 门 1n）"

def patch(path):
    lines = open(path).read().split("\n")
    out, i, n = [], 0, 0
    while i < len(lines):
        line = lines[i]
        out.append(line)
        if '"export_bid_document"' in line:
            # 在本调用块内找 "project_id" 行，其前插豁免（若块内尚无）
            j = i + 1
            depth_open = line.count("json!({")
            block_end = min(i + 25, len(lines))
            has_waiver = any("waive_scoring_leaf_generator" in lines[k] for k in range(i, block_end))
            while j < block_end:
                if '"project_id"' in lines[j] and not has_waiver:
                    indent = re.match(r"\s*", lines[j]).group(0)
                    out.append(f'{indent}"waive_scoring_leaf_generator": "{REASON}",')
                    n += 1
                    break
                out.append(lines[j])
                j += 1
            i = j
            continue
        i += 1
    if n:
        open(path, "w").write("\n".join(out))
    print(f"{path}: 插入 {n} 处")

for p in sys.argv[1:]:
    patch(p)
