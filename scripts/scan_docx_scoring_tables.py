#!/usr/bin/env python3
"""scan_docx_scoring_tables.py — #134 素材盘点：DOCX 真表格评分表扫描。

对全仓 DOCX 素材（corpus-A/corpus-R/real-tender-batch2/real-samples/
real-corpus/synth-tender）逐件解包 word/document.xml：
  ① 提取所有真表格（<w:tbl>），识别「评分表形态」（启发式：表头或首列
     含 评分/评审/得分/分值/细则 等词 + 表内有 N 分 数值格）；
  ② 记录结构描述：表格数 / 评分表索引 / 行列规模 / 合并单元格
     （<w:vMerge>/<w:gridSpan>/<w:hMerge> 计数）/ 跨页形态（分节符前后的
     表格延续——DOCX 无显式跨页标记，以「行数>15 或 vMerge 在场」近似
     标注候选跨页，如实注明口径）；
  ③ 现状缺口实测：把评分表行文本拼出后，与 bid-parse scoring_table.rs 的
     行锚判据（N.NN + 主观|客观 token）比对——抽不到的行 = 现状缺口清单
     （哪些行抽不到 / 评分值是否丢失）。

产物：audit/materials-docx-scoring-tables.md 的数据底稿（stdout JSON）。
不写解析器（#134 纪律：素材先行——本脚本只做素材对账）。
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# 素材根（issue 正文清单 + 实仓核对）
ROOTS = [
    "fixtures/corpus-A/files",
    "fixtures/corpus-R",
    "fixtures/real-tender-batch2",
    "real-samples",
    "real-corpus/telecom/parse-input",
    "fixtures/synth-tender/招标文件",
]

SCORING_WORDS = ("评分", "评审", "评标", "得分", "分值", "细则")
TRACK_WORDS = ("主观", "客观")
SCORE_CELL = re.compile(r"^\s*\d{1,3}(?:\.\d{1,2})?\s*$")


def docx_tables(p: Path) -> list[dict]:
    with zipfile.ZipFile(p) as z:
        xml = z.read("word/document.xml").decode("utf-8")
    tables = []
    for ti, tbl in enumerate(re.findall(r"<w:tbl>.*?</w:tbl>", xml, re.S), 1):
        rows = re.findall(r"<w:tr[ >].*?</w:tr>", tbl, re.S)
        row_cells = []
        for r in rows:
            cells = re.findall(r"<w:tc>.*?</w:tc>", r, re.S)
            texts = [re.sub(r"\s+", "", re.sub(r"<[^>]+>", "", c)) for c in cells]
            row_cells.append(texts)
        vmerge = len(re.findall(r"<w:vMerge[ />]", tbl))
        gridspan = len(re.findall(r"<w:gridSpan[ />]", tbl))
        hmerge = len(re.findall(r"<w:hMerge[ />]", tbl))
        tables.append({
            "idx": ti, "n_rows": len(rows), "n_cols_max": max((len(c) for c in row_cells), default=0),
            "vmerge_cells": vmerge, "gridspan_cells": gridspan, "hmerge_cells": hmerge,
            "first_row": row_cells[0] if row_cells else [],
            "rows": row_cells,
        })
    return tables


def is_scoring_like(t: dict) -> bool:
    """评分表形态启发式：表头/首行或首两行含评分词 + 表内存在分值数值格。"""
    head = "".join("".join(r) for r in t["rows"][:2])
    has_word = any(w in head for w in SCORING_WORDS)
    has_track = any(any(w in "".join(r) for w in TRACK_WORDS) for r in t["rows"])
    has_score_cell = any(
        any(SCORE_CELL.match(c) for c in r if c)
        for r in t["rows"]
    )
    return has_word and has_score_cell and (has_track or has_word)


def row_anchor_status(rows: list[list[str]]) -> dict:
    """现状缺口实测：scoring_table.rs 行锚 = N.NN + 主观|客观 token。

    把每行拼为单文本后测 token 在场性——抽不到的行数即现状缺口
    （PDF 线性化路径的判据；DOCX 真表格本就不走该路——此处对账
    「若沿用现判据会丢多少行」）。
    """
    anchor = re.compile(r"\d{1,3}(?:\.\d{1,2})?\s*(?:主观|客观)")
    total_rows = len(rows)
    with_anchor = sum(1 for r in rows if anchor.search("".join(r)))
    # 分值列在场性（行含独立数值格）
    score_rows = sum(1 for r in rows if any(SCORE_CELL.match(c) for c in r if c))
    return {
        "n_rows": total_rows,
        "rows_with_pdftext_anchor": with_anchor,
        "rows_with_standalone_score_cell": score_rows,
        "loss_if_reusing_pdf_anchor": total_rows - with_anchor,
    }


def main() -> int:
    out = {"files": [], "n_docx": 0, "n_with_scoring_table": 0}
    for root in ROOTS:
        rootp = REPO / root
        if not rootp.exists():
            out["files"].append({"root": root, "status": "ROOT_MISSING"})
            continue
        for p in sorted(rootp.rglob("*.docx")):
            if p.name.startswith("~$"):
                continue
            try:
                tables = docx_tables(p)
            except Exception as e:  # noqa: BLE001
                out["files"].append({"root": root, "file": str(p.relative_to(REPO)),
                                     "status": "UNREADABLE", "error": str(e)[:80]})
                continue
            scoring = [t for t in tables if is_scoring_like(t)]
            rec = {
                "root": root, "file": str(p.relative_to(REPO)),
                "sha256_12": hashlib.sha256(p.read_bytes()).hexdigest()[:12],
                "bytes": p.stat().st_size,
                "n_tables": len(tables),
                "n_scoring_tables": len(scoring),
                "status": "HAS_SCORING_TABLE" if scoring else ("NO_SCORING_TABLE" if tables else "NO_TABLE"),
            }
            if scoring:
                out["n_with_scoring_table"] += 1
                # 跨页候选口径（如实：DOCX 无显式跨页标记——行数/合并度近似）
                rec["scoring_tables"] = [{
                    "idx": t["idx"], "rows": t["n_rows"], "cols": t["n_cols_max"],
                    "vmerge": t["vmerge_cells"], "gridspan": t["gridspan_cells"],
                    "hmerge": t["hmerge_cells"],
                    "cross_page_candidate": t["n_rows"] > 15 or t["vmerge_cells"] > 0,
                    "header_1row_preview": [c[:12] for c in t["first_row"][:8]],
                    "anchor_audit": row_anchor_status(t["rows"]),
                } for t in scoring]
            out["files"].append(rec)
            out["n_docx"] += 1
    json.dump(out, sys.stdout, ensure_ascii=False, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
