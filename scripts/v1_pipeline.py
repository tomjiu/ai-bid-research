#!/usr/bin/env python3
"""v1_pipeline.py — V1-a 解析覆盖（verification-plan §3.1 第一段）

M1 最小接口的**解析基座**（读面）+ parse_report 生成器：
  parse_docx(path)  正文段落（0 起序，不含表格内段落）+ 表格（合并单元格经 python-docx
                    归并寻址）+ 分节页眉页脚 + 非正文盘点（文本框/批注/修订——raw XML）
  parse_pdf(path)   逐页文本 + 文本层三态判定（full/partial/none）+ 逐页表格行数盘点
  parse_xlsx(path)  工作表 + 单元格（值/公式双通道）+ 合并区

定位发射（对齐引擎 Locator 七变体中的五变体，ooxml_util 语义仿真）：
  锚点 excerpt → 定位器。OCR 锚点（无文本层）→ scan_deferred（不伪装支持）。

诚实边界（V1-a 的产出即这些边界的确证）：
  - 页眉页脚条款可读可抽取，但引擎 Locator 无 header/footer 变体 → parsed_no_locator
  - 文本框/批注/修订：naive 正文遍历不可见（D2a 实证），raw XML 可盘点 → inventoried_no_locator
    （两处均归属引擎缺口 G6——回填 doc-engine-audit 差距矩阵）
  - 无文本层/部分页无文本层 → OCR 路径登记（D5 管道面，M1 解析面外）

用法：
  python3 scripts/v1_pipeline.py [--report PATH]   # 跑 corpus-A + corpus-R，输出 parse_report
"""
from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path

import fitz  # PyMuPDF
from docx import Document
from openpyxl import load_workbook

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ooxml_util import (  # noqa: E402
    emit_docx_paragraph, emit_docx_table_cell, emit_pdf_page_text,
    emit_xlsx_cell, emit_xlsx_region, norm_text,
)

REPO = Path(__file__).resolve().parent.parent
FIXTURES = REPO / "fixtures"
CORPUS_A = FIXTURES / "corpus-A"
CORPUS_R = FIXTURES / "corpus-R"

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


# ================================================================ DOCX 解析面
def parse_docx(path: Path) -> dict:
    doc = Document(str(path))
    paragraphs = [{"index": i, "text": p.text, "style": p.style.name if p.style else ""}
                  for i, p in enumerate(doc.paragraphs)]
    tables = []
    for ti, t in enumerate(doc.tables):
        cells = {}
        for r in range(len(t.rows)):
            for c in range(len(t.columns)):
                cells[f"{r},{c}"] = t.cell(r, c).text
        tables.append({"table_index": ti, "rows": len(t.rows), "cols": len(t.columns),
                       "cells": cells})
    headers, footers = [], []
    for si, sec in enumerate(doc.sections):
        for kind, part in [("default", sec.header), ("first", sec.first_page_header),
                           ("even", sec.even_page_header)]:
            if part is not None:
                for pi, p in enumerate(part.paragraphs):
                    if p.text.strip():
                        headers.append({"section": si, "kind": kind, "para": pi, "text": p.text})
        for kind, part in [("default", sec.footer), ("first", sec.first_page_footer),
                           ("even", sec.even_page_footer)]:
            if part is not None:
                for pi, p in enumerate(part.paragraphs):
                    if p.text.strip():
                        footers.append({"section": si, "kind": kind, "para": pi, "text": p.text})
    nonbody = _inventory_nonbody(path)
    return {"engine": "docx", "paragraphs": paragraphs, "tables": tables,
            "sections": len(doc.sections), "headers": headers, "footers": footers,
            "nonbody": nonbody}


def _inventory_nonbody(path: Path) -> dict:
    """非正文结构盘点（raw XML）：文本框/批注/修订——naive 正文遍历的盲区。"""
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        doc_xml = z.read("word/document.xml").decode("utf-8", errors="replace")
        comments_xml = z.read("word/comments.xml").decode("utf-8", errors="replace") \
            if "word/comments.xml" in names else ""
    import re
    txbx = re.findall(r"<w:txbxContent>.*?</w:txbxContent>", doc_xml, re.S)
    textbox_texts = ["".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", tb)) for tb in txbx]
    comments = re.findall(r"<w:comment [^>]*w:author=\"([^\"]*)\"[^>]*>(.*?)</w:comment>",
                          comments_xml, re.S)
    comment_texts = [{"author": a, "text": "".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", body))}
                     for a, body in comments]
    ins_blocks = re.findall(r"<w:ins [^>]*>(.*?)</w:ins>", doc_xml, re.S)
    del_blocks = re.findall(r"<w:del [^>]*>(.*?)</w:del>", doc_xml, re.S)
    ins_texts = ["".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", b)) for b in ins_blocks]
    del_texts = ["".join(re.findall(r"<w:delText[^>]*>([^<]*)</w:delText>", b)) for b in del_blocks]
    inv = {"textboxes": textbox_texts, "comments": comment_texts,
           "revisions": {"ins": ins_texts, "del": del_texts}}
    inv["counts"] = {"textbox": len(textbox_texts), "comment": len(comment_texts),
                     "ins": len(ins_texts), "del": len(del_texts)}
    return inv


# ================================================================ PDF 解析面
def parse_pdf(path: Path) -> dict:
    d = fitz.open(str(path))
    pages = []
    for i, p in enumerate(d):
        text = p.get_text()
        pages.append({"page": i + 1, "chars": len(text.strip()),
                      "text": text, "images": len(p.get_images())})
    with_text = sum(1 for p in pages if p["chars"] > 0)
    if with_text == len(pages):
        layer = "full"
    elif with_text == 0:
        layer = "none"
    else:
        layer = "partial"
    return {"engine": "pdf", "pages": pages, "text_layer": layer,
            "page_count": len(pages)}


# ================================================================ XLSX 解析面
def parse_xlsx(path: Path) -> dict:
    wb_f = load_workbook(str(path), data_only=False)   # 公式通道
    wb_v = load_workbook(str(path), data_only=True)    # 缓存值通道（openpyxl 写出的件无缓存 → None）
    sheets = {}
    for name in wb_f.sheetnames:
        ws_f, ws_v = wb_f[name], wb_v[name]
        cells = {}
        for row in ws_f.iter_rows():
            for cell in row:
                if cell.value is None:
                    continue
                v = ws_v[cell.coordinate].value
                formula = cell.value if isinstance(cell.value, str) and cell.value.startswith("=") else None
                cells[cell.coordinate] = (v if v is not None else "", formula)
        sheets[name] = {"cells": cells,
                        "merged": [str(r) for r in ws_f.merged_cells.ranges]}
    return {"engine": "xlsx", "sheets": sheets}


# ================================================================ 锚点定位
def locate_anchor(anchor: dict, parsed_by_file: dict) -> dict:
    """锚点 → 定位器结果。返回 {status, locator|reason}。
    status: located / scan_deferred / not_found / no_locator_variant"""
    fname = anchor["file"]
    excerpt = anchor["excerpt"]
    parsed = parsed_by_file.get(fname)
    if parsed is None:
        return {"status": "not_found", "reason": f"未解析文件 {fname}"}
    if parsed["engine"] == "pdf":
        if parsed["text_layer"] == "none":
            return {"status": "scan_deferred",
                    "reason": "无文本层（全扫描页）——OCR 路径，M1 解析面外（D5 管道面）"}
        hits = [p for p in parsed["pages"] if excerpt in p["text"]]
        if not hits:
            image_pages = [p["page"] for p in parsed["pages"] if p["chars"] == 0]
            if image_pages:
                return {"status": "scan_deferred",
                        "reason": f"文本层未命中；无文本层页 {image_pages} 为 OCR 候选"
                                  "（图文混排件无法在解析面确认是否在图像页——D5 管道面）"}
            return {"status": "not_found", "reason": "文本层未命中（各页均有文本层）"}
        return {"status": "located",
                "locator": emit_pdf_page_text(hits[0]["page"], hits[0]["text"]),
                "note": f"命中 {len(hits)} 页（PdfPageText 页级定位——区域变体引擎待扩展）"}
    if parsed["engine"] == "docx":
        if anchor.get("kind") == "table":
            for t in parsed["tables"]:
                for key, text in t["cells"].items():
                    if excerpt in text:
                        r, c = key.split(",")
                        return {"status": "located",
                                "locator": emit_docx_table_cell(t["table_index"], int(r), int(c), text)}
            return {"status": "not_found", "reason": "表格单元格未命中"}
        for p in parsed["paragraphs"]:
            if excerpt in p["text"]:
                return {"status": "located", "locator": emit_docx_paragraph(p["index"], p["text"])}
        return {"status": "not_found", "reason": "正文段落未命中"}
    if parsed["engine"] == "xlsx":
        for name, sheet in parsed["sheets"].items():
            for coord, (value, formula) in sheet["cells"].items():
                if excerpt in str(value) or (formula and excerpt in formula):
                    return {"status": "located",
                            "locator": emit_xlsx_cell(name, coord, str(value), formula)}
        return {"status": "not_found", "reason": "工作表单元格未命中"}
    return {"status": "not_found", "reason": "未知引擎"}


# ================================================================ corpus-R 结构探针
# 每层文件的结构特征必须经解析面**可定位或可判定**——不是"文件存在"式弱断言。
CORPUS_R_PROBES = {
    "D1-tables/D1a-合并表头跨页表.docx": {
        "engine": "docx",
        "probes": [
            {"id": "D1a-P1", "excerpt": "设备信息", "expect": "docx_table_cell",
             "note": "两行嵌套表头横向合并后寻址稳定"},
            {"id": "D1a-P2", "excerpt": "核心交换机", "expect": "docx_table_cell"},
            {"id": "D1a-P3", "excerpt": "网络设备", "expect": "docx_table_cell",
             "note": "类别列纵向合并：合并区任一坐标取到同一文本"},
            {"id": "D1a-P4", "excerpt": "本表结构为合成示例", "expect": "docx_paragraph"},
        ],
    },
    "D1-tables/D1b-宽表公式.xlsx": {
        "engine": "xlsx",
        "probes": [
            {"id": "D1b-P1", "excerpt": "量价汇总表", "expect": "xlsx_cell",
             "note": "合并标题区 A1（区域左上角寻址）"},
            {"id": "D1b-P2", "excerpt": "=E3*620", "expect": "xlsx_cell_formula",
             "note": "公式通道：F3 值指纹（空缓存）+ 公式指纹双通道"},
            {"id": "D1b-P3", "excerpt": "=SUM(F3:F14)", "expect": "xlsx_cell_formula"},
        ],
    },
    "D2-nonbody/D2a-非正文条款.docx": {
        "engine": "docx",
        "probes": [
            {"id": "D2a-P1", "excerpt": "澄清一：机房建设标准", "expect": "docx_paragraph"},
            {"id": "D2a-H1", "excerpt": "页眉载明", "expect": "header_no_locator_variant",
             "note": "页眉条款：可读可抽取，但引擎 Locator 无 header 变体（G7）"},
            {"id": "D2a-F1", "excerpt": "受控文件编号", "expect": "footer_no_locator_variant",
             "note": "页脚条款：同上（G7）"},
            {"id": "D2a-T1", "excerpt": "文本框条款", "expect": "inventoried_no_locator",
             "note": "文本框：naive 正文遍历不可见，raw XML 盘点（G7）"},
            {"id": "D2a-C1", "excerpt": "评审查疑点", "expect": "inventoried_no_locator",
             "note": "批注：comments part 盘点（G7）"},
            {"id": "D2a-R1", "excerpt": "修订插入", "expect": "inventoried_no_locator",
             "note": "修订 w:ins：naive 不可见，raw XML 盘点（G7）"},
        ],
    },
    "D5-scanned/D5a-全扫描双栏盖章.pdf": {
        "engine": "pdf",
        "probes": [
            {"id": "D5a-P1", "excerpt": "评标办法附表", "expect": "scan_deferred",
             "note": "全扫描页：文本层 none → OCR 路径登记"},
        ],
    },
    "D5-scanned/D5b-图文混排.pdf": {
        "engine": "pdf",
        "probes": [
            {"id": "D5b-P1", "excerpt": "澄清通知", "expect": "pdf_page_text",
             "note": "第 1 页文本层可定位"},
            {"id": "D5b-P2", "excerpt": "响应偏离表", "expect": "scan_deferred",
             "note": "第 2 页纯图像：partial 判定 + 该页 OCR 路径"},
        ],
    },
}


def probe_corpus_r(parsed_by_file: dict) -> list[dict]:
    results = []
    for rel, spec in CORPUS_R_PROBES.items():
        parsed = parsed_by_file.get(rel)
        if parsed is None:
            for pr in spec["probes"]:
                results.append({"probe": pr["id"], "expect": pr["expect"],
                                "status": "not_found", "reason": "文件未解析"})
            continue
        # 非正文盘点预取
        nonbody = parsed.get("nonbody") or {}
        nb_all_text = ("".join(nonbody.get("textboxes", []))
                       + "".join(c["text"] for c in nonbody.get("comments", []))
                       + "".join(nonbody.get("revisions", {}).get("ins", []))
                       + "".join(nonbody.get("revisions", {}).get("del", [])))
        hf_text = "".join(h["text"] for h in parsed.get("headers", [])) + \
                  "".join(f["text"] for f in parsed.get("footers", []))
        for pr in spec["probes"]:
            exp, excerpt = pr["expect"], pr["excerpt"]
            kind = "para" if exp == "docx_paragraph" else "table"
            hit = locate_anchor({"file": rel, "excerpt": excerpt, "kind": kind}, {rel: parsed})
            if exp == "docx_paragraph":
                got = hit if hit["status"] == "located" else None
                if got and got["locator"]["kind"] != "docx_paragraph":
                    got = None  # 命中表格不算段落探针通过
                results.append({"probe": pr["id"], "expect": exp,
                                "status": "located" if got else "not_found"})
            elif exp in ("docx_table_cell", "xlsx_cell"):
                results.append({"probe": pr["id"], "expect": exp,
                                "status": "located" if hit["status"] == "located" else "not_found",
                                "locator": hit.get("locator")})
            elif exp == "xlsx_cell_formula":
                ok = (hit["status"] == "located" and hit.get("locator", {}).get("formula_fingerprint"))
                results.append({"probe": pr["id"], "expect": exp,
                                "status": "located" if ok else "not_found",
                                "locator": hit.get("locator")})
            elif exp == "pdf_page_text":
                results.append({"probe": pr["id"], "expect": exp,
                                "status": "located" if hit["status"] == "located" else "not_found"})
            elif exp == "scan_deferred":
                results.append({"probe": pr["id"], "expect": exp,
                                "status": "located" if hit["status"] == "scan_deferred" else "not_found",
                                "detail": hit.get("reason", "")})
            elif exp in ("header_no_locator_variant", "footer_no_locator_variant"):
                # 可读（页眉页脚抽取命中）但无定位器变体 → parsed_no_locator（G7 归因）
                results.append({"probe": pr["id"], "expect": exp,
                                "status": "parsed_no_locator" if excerpt in hf_text else "not_found",
                                "gap": "G7"})
            elif exp == "inventoried_no_locator":
                results.append({"probe": pr["id"], "expect": exp,
                                "status": "parsed_no_locator" if excerpt in nb_all_text else "not_found",
                                "gap": "G7"})
    return results


# ================================================================ 主流程
def build_parse_report() -> dict:
    # ---- corpus-A 五件 + corpus-R 五件
    targets = [
        ("A-招标文件.docx", CORPUS_A / "files" / "A-招标文件.docx"),
        ("B1-设备清单.pdf", CORPUS_A / "files" / "B1-设备清单.pdf"),
        ("B2-投标函格式页-扫描件.pdf", CORPUS_A / "files" / "B2-投标函格式页-扫描件.pdf"),
        ("B3-图纸目录.xlsx", CORPUS_A / "files" / "B3-图纸目录.xlsx"),
        ("C-补遗文件01.docx", CORPUS_A / "files" / "C-补遗文件01.docx"),
    ]
    parsed_by_file: dict[str, dict] = {}
    file_reports = []
    for fname, path in targets:
        if fname.endswith(".docx"):
            parsed = parse_docx(path)
        elif fname.endswith(".pdf"):
            parsed = parse_pdf(path)
        else:
            parsed = parse_xlsx(path)
        parsed_by_file[fname] = parsed
        file_reports.append(_file_report(fname, parsed))
    # GT 锚点定位
    reqs = [json.loads(l) for l in (CORPUS_A / "ground-truth" / "requirements.jsonl").read_text(
        encoding="utf-8").splitlines() if l.strip()]
    anchor_results = []
    for r in reqs:
        for a in r["anchors"]:
            res = locate_anchor(a, parsed_by_file)
            anchor_results.append({"gt_id": r["gt_id"], "file": a["file"], "kind": a["kind"],
                                   **res})
    located = sum(1 for x in anchor_results if x["status"] == "located")
    deferred = [x for x in anchor_results if x["status"] == "scan_deferred"]
    failed = [x for x in anchor_results if x["status"] not in ("located", "scan_deferred")]
    text_layer_anchors = len(anchor_results) - len(deferred)
    # ---- corpus-R
    r_parsed = {}
    for rel in CORPUS_R_PROBES:
        p = CORPUS_R / rel
        if p.exists():
            r_parsed[rel] = (parse_docx(p) if rel.endswith(".docx")
                             else parse_pdf(p) if rel.endswith(".pdf")
                             else parse_xlsx(p))
    probes = probe_corpus_r(r_parsed)
    locatable_expect = [p for p in probes if p["expect"] in
                        ("docx_paragraph", "docx_table_cell", "xlsx_cell", "xlsx_cell_formula",
                         "pdf_page_text", "scan_deferred")]
    gap_expect = [p for p in probes if p["expect"].endswith("no_locator_variant")
                  or p["expect"] == "inventoried_no_locator"]
    loc_ok = sum(1 for p in locatable_expect if p["status"] in ("located", "scan_deferred"))
    gap_ok = sum(1 for p in gap_expect if p["status"] == "parsed_no_locator")
    return {
        "suite": "V1-a 解析覆盖",
        "corpus_a": {
            "files": file_reports,
            "anchors": {"total": len(anchor_results), "located": located,
                        "scan_deferred": len(deferred),
                        "text_layer_located": located,
                        "text_layer_total": text_layer_anchors,
                        "coverage_text_layer": round(located / text_layer_anchors, 4) if text_layer_anchors else None,
                        "failures": failed},
            "anchor_detail": anchor_results,
        },
        "corpus_r": {
            "probes": probes,
            "locatable": {"expect": len(locatable_expect), "pass": loc_ok},
            "gap_attributed": {"expect": len(gap_expect), "detected": gap_ok,
                               "gap": "G7（页眉页脚/文本框/批注/修订——引擎 Locator 无变体，业务侧 M1 同边界）"},
        },
    }


def _file_report(fname: str, parsed: dict) -> dict:
    rep = {"file": fname, "engine": parsed["engine"]}
    if parsed["engine"] == "docx":
        rep["units"] = {"paragraphs": len(parsed["paragraphs"]), "tables": len(parsed["tables"]),
                        "sections": parsed["sections"],
                        "header_paras": len(parsed["headers"]), "footer_paras": len(parsed["footers"])}
        nb = parsed["nonbody"]["counts"]
        rep["nonbody_inventory"] = nb
    elif parsed["engine"] == "pdf":
        rep["units"] = {"pages": parsed["page_count"],
                        "pages_with_text": sum(1 for p in parsed["pages"] if p["chars"] > 0),
                        "pages_with_images": sum(1 for p in parsed["pages"] if p["images"])}
        rep["text_layer"] = parsed["text_layer"]
    else:
        rep["units"] = {"sheets": len(parsed["sheets"]),
                        "cells": sum(len(s["cells"]) for s in parsed["sheets"].values()),
                        "formula_cells": sum(1 for s in parsed["sheets"].values()
                                             for (_, f) in s["cells"].values() if f)}
        rep["merged_ranges"] = {n: s["merged"] for n, s in parsed["sheets"].items()}
    return rep


def main() -> int:
    report = build_parse_report()
    out = Path(sys.argv[sys.argv.index("--report") + 1]) if "--report" in sys.argv else None
    ca = report["corpus_a"]
    cr = report["corpus_r"]
    print("[V1-a] corpus-A 文本层锚点覆盖:",
          f"{ca['anchors']['located']}/{ca['anchors']['text_layer_total']}",
          f"（扫描层登记 {ca['anchors']['scan_deferred']}）")
    for f in ca["anchors"]["failures"]:
        print("  ✗", f["gt_id"], f["file"], f.get("reason"))
    print("[V1-a] corpus-R 结构探针:",
          f"可定位 {cr['locatable']['pass']}/{cr['locatable']['expect']}",
          f"| G7 归因检出 {cr['gap_attributed']['detected']}/{cr['gap_attributed']['expect']}")
    for p in cr["probes"]:
        if p["status"] == "not_found":
            print("  ✗", p["probe"], p["expect"])
    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"报告 → {out}")
    ok = (ca["anchors"]["located"] == ca["anchors"]["text_layer_total"]
          and not ca["anchors"]["failures"]
          and cr["locatable"]["pass"] == cr["locatable"]["expect"]
          and cr["gap_attributed"]["detected"] == cr["gap_attributed"]["expect"])
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
