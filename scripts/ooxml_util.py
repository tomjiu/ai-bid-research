#!/usr/bin/env python3
"""ooxml_util.py — V1 验证套件的共享工具层

内容分三块：
1. freeze_zip / XLSX_FIXED_CORE：OOXML 字节级确定性纪律（从 fixture_gen.py
   原样抽取——生成物哈希必须与抽取前逐字节一致，由 run_tests T6 回归把关）。
2. fnv64：mdcore evidence::fingerprint::Fnv64 的逐位复刻（FNV-1a 64，
   算法前缀编码 `fnv64:{016x}`；公开测试向量防实现漂移——与引擎侧
   crates/evidence/src/fingerprint.rs 的 known_vector 一致）。
3. Locator 语义仿真：mdcore evidence::locator::Locator 七变体中 V1 用到的
   五变体（XlsxCell/XlsxRegion/DocxParagraph/DocxTableCell/PdfPageText）的
   emit/resolve。判定语义与引擎 sidecar::refresh_document 一致：
     - 位置在 + 指纹同 → valid
     - 位置在 + 指纹异 → stale_content（二级失效："位置在但内容换"）
     - 位置失（索引越界/表列越界/工作表缺失/页越界）→ stale_position
   引擎本体（Rust）在本验证环境不可执行——本模块是其**语义级仿真**，
   验证口径已在 verification-plan §3.1 V1-b 标注（SEMUL ≠ ENGINE_RUN）。
"""
from __future__ import annotations

import hashlib
import json
import re
import zipfile
from pathlib import Path

FREEZE_DATE = (1980, 1, 1, 0, 0, 0)  # zip 冻结时间戳（与 fixture_gen 单一纪律）

# ---------------------------------------------------------------- 确定性 zip
XLSX_FIXED_CORE = (b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\r\n'
                   b'<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
                   b'xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" '
                   b'xmlns:dcmitype="http://purl.org/dc/dcmitype/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
                   b'<dc:creator>ai-bid-research fixture</dc:creator><cp:lastModifiedBy>ai-bid-research fixture</cp:lastModifiedBy>'
                   b'<dcterms:created xsi:type="dcterms:W3CDTF">2026-10-16T09:00:00Z</dcterms:created>'
                   b'<dcterms:modified xsi:type="dcterms:W3CDTF">2026-10-16T09:00:00Z</dcterms:modified>'
                   b'</cp:coreProperties>')


def freeze_zip(path: Path, patches: dict[str, bytes] | None = None):
    """重写 zip 归档：固定时间戳 + 固定条目顺序 + 可选条目内容补丁 → 字节级确定性。
    （openpyxl 的 ExcelWriter 会在 save 时强制写入当前时间到 docProps/core.xml——
     其 modified 属性无法通过 wb.properties 预置，只能在归档层修补。）"""
    patches = patches or {}
    tmp = path.with_suffix(path.suffix + ".tmp")
    with zipfile.ZipFile(path, "r") as zin, \
         zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_DEFLATED) as zout:
        for info in sorted(zin.infolist(), key=lambda i: i.filename):
            data = patches.get(info.filename) or zin.read(info.filename)
            zi = zipfile.ZipInfo(info.filename, date_time=FREEZE_DATE)
            zi.compress_type = zipfile.ZIP_DEFLATED
            zi.external_attr = info.external_attr
            zout.writestr(zi, data)
    tmp.replace(path)


def freeze_docx(path: Path, core_props: dict[str, str] | None = None):
    """DOCX 确定性化：python-docx 保存的 docProps 时间戳不冻结 → 归档层补丁。
    core_props 可选覆盖 dc:creator / cp:lastModifiedBy（V1-d 元数据清零用：
    传 {"creator": "", "lastModifiedBy": ""} 得到空标识）。"""
    patches: dict[str, bytes] = {}
    with zipfile.ZipFile(path) as z:
        if "docProps/core.xml" in z.namelist():
            xml = z.read("docProps/core.xml").decode("utf-8")
            creator = core_props.get("creator") if core_props else None
            lmb = core_props.get("lastModifiedBy") if core_props else None
            if creator is not None:
                xml = re.sub(r"<dc:creator>[^<]*</dc:creator>",
                             f"<dc:creator>{creator}</dc:creator>", xml)
            if lmb is not None:
                xml = re.sub(r"<cp:lastModifiedBy>[^<]*</cp:lastModifiedBy>",
                             f"<cp:lastModifiedBy>{lmb}</cp:lastModifiedBy>", xml)
            xml = re.sub(r'<dcterms:created xsi:type="dcterms:W3CDTF">[^<]*</dcterms:created>',
                         '<dcterms:created xsi:type="dcterms:W3CDTF">2026-10-16T09:00:00Z</dcterms:created>', xml)
            xml = re.sub(r'<dcterms:modified xsi:type="dcterms:W3CDTF">[^<]*</dcterms:modified>',
                         '<dcterms:modified xsi:type="dcterms:W3CDTF">2026-10-16T09:00:00Z</dcterms:modified>', xml)
            patches["docProps/core.xml"] = xml.encode("utf-8")
    freeze_zip(path, patches)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


# ---------------------------------------------------------------- FNV-1a 64（引擎复刻）
_FNV_OFFSET = 0xcbf2_9ce4_8422_2325
_FNV_PRIME = 0x0000_0100_0000_01b3
_MASK64 = 0xFFFF_FFFF_FFFF_FFFF


def fnv64_bytes(data: bytes) -> int:
    h = _FNV_OFFSET
    for b in data:
        h ^= b
        h = (h * _FNV_PRIME) & _MASK64
    return h


def fnv64(text: str) -> str:
    """带算法前缀的内容指纹（与引擎 ContentFingerprint 序列化一致：`fnv64:{016x}`）。"""
    return f"fnv64:{fnv64_bytes(text.encode('utf-8')):016x}"


# 引擎公开测试向量（fingerprint.rs::known_vector）——防实现漂移
assert fnv64_bytes(b"") == 0xcbf2_9ce4_8422_2325, "FNV-1a 空串向量漂移"
assert fnv64_bytes(b"a") == 0xaf63_dc4c_8601_ec8c, "FNV-1a 'a' 向量漂移"


# ---------------------------------------------------------------- Locator 语义仿真
def norm_text(text: str) -> str:
    """段落规范化文本（引擎侧由应用层计算后传入——此处采用最保守口径：
    去首尾空白 + 内部连续空白折叠为单空格；不删标点（一字之差必须失效）。"""
    return re.sub(r"\s+", " ", text).strip()


def emit_docx_paragraph(paragraph_index: int, text: str) -> dict:
    """Locator::DocxParagraph { paragraph_index(0起), text_fingerprint }"""
    return {"kind": "docx_paragraph", "paragraph_index": paragraph_index,
            "text_fingerprint": fnv64(norm_text(text))}


def emit_docx_table_cell(table_index: int, row: int, col: int, text: str) -> dict:
    """Locator::DocxTableCell { table_index, row, col, text_fingerprint }"""
    return {"kind": "docx_table_cell", "table_index": table_index, "row": row, "col": col,
            "text_fingerprint": fnv64(norm_text(text))}


def emit_xlsx_cell(sheet: str, cell: str, value: str, formula: str | None) -> dict:
    """Locator::XlsxCell { sheet, cell(A1 大写规范化), value_fingerprint, formula_fingerprint }"""
    return {"kind": "xlsx_cell", "sheet": sheet, "cell": cell.upper(),
            "value_fingerprint": fnv64(value),
            "formula_fingerprint": fnv64(formula) if formula is not None else None}


def emit_xlsx_region(sheet: str, start: str, end: str, row_major_texts: list[str]) -> dict:
    """Locator::XlsxRegion { sheet, start, end, region_fingerprint(行优先拼接序) }"""
    return {"kind": "xlsx_region", "sheet": sheet, "start": start.upper(), "end": end.upper(),
            "region_fingerprint": fnv64(norm_text(" ".join(row_major_texts)))}


def emit_pdf_page_text(page: int, text: str) -> dict:
    """Locator::PdfPageText { page(1起), text_fingerprint }"""
    return {"kind": "pdf_page_text", "page": page, "text_fingerprint": fnv64(norm_text(text))}


def resolve_docx_paragraph(loc: dict, paragraphs: list[str]) -> str:
    """按引擎 refresh_document 语义判定：valid / stale_content / stale_position。
    paragraphs = 当前正文规范化文本指纹表（索引 → 指纹）。"""
    i = loc["paragraph_index"]
    if i >= len(paragraphs):
        return "stale_position"  # 索引越界 = 段落已删（引擎 unwrap_or(true) 分支）
    return "valid" if paragraphs[i] == loc["text_fingerprint"] else "stale_content"


def resolve_xlsx_cell(loc: dict, sheets: dict) -> str:
    """sheets: {sheet_name: {A1: (value_str, formula_or_None)}}"""
    cells = sheets.get(loc["sheet"])
    if cells is None:
        return "stale_position"
    hit = cells.get(loc["cell"])
    if hit is None:
        return "stale_position"
    value, formula = hit
    if fnv64(value) != loc["value_fingerprint"]:
        return "stale_content"
    f_now = fnv64(formula) if formula is not None else None
    f_then = loc.get("formula_fingerprint")
    # 公式通道：None(无公式) ≠ Some(公式) 与 公式变更 即使缓存值相同都失效
    if f_now != f_then:
        return "stale_content"
    return "valid"


def resolve_pdf_page_text(loc: dict, pages: list[str]) -> str:
    """pages: 1 起页文本表（index0 = 第1页）。"""
    p = loc["page"]
    if p < 1 or p > len(pages):
        return "stale_position"
    return "valid" if fnv64(norm_text(pages[p - 1])) == loc["text_fingerprint"] else "stale_content"


# ---------------------------------------------------------------- 报告输出
def write_json(path: Path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict]):
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
