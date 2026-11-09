#!/usr/bin/env python3
"""v1_export.py — V1-c 导出保真（verification-plan §3.1 第三段）

技术标完整交付样本构建器（bright/dark 双变体）+ 两级保真检查：
  一级（结构读回，python-docx）：书签 10、域代码（TOC/PAGE/NUMPAGES）、图片部件、
    分页符计数、合并单元格表格、分节页眉页脚
  二级（LO headless 渲染，LibreOffice 25.2）：DOCX→PDF 后逐页断言——
    精确页数（渲染口径，非估算）、分页纪律（每章节起新页）、页眉在正文页出现且
    封面页不出现、页脚页码域渲染、图片页含图像对象

口径说明（诚实边界）：
  - 双 Office 复验（Word + WPS 人工）本环境不可执行——按 test-plan §5.5 记为
    待人工步骤，LO 渲染级断言先行为可自动化部分；
  - LO 产物 PDF 字节非确定（文档 ID/时间戳）——断言取**属性**不取字节哈希；
  - DOCX 本体经 freeze_docx 字节级确定（T7e 重生成哈希一致断言）。

引用链（V1-b 消费）：build_bid_docx 返回 chains——每条含
  条款定位器（A/C 源，DocxParagraph/DocxTableCell）+ 证据定位器（EV/B1 源，
  PdfPageText）+ 正文引用定位器（导出件，DocxParagraph + bookmark 名）。
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fixture_spec as S  # noqa: E402
import v1_pipeline  # noqa: E402
from ooxml_util import freeze_docx, norm_text, sha256_file  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
CORPUS_A = REPO / "fixtures" / "corpus-A"

# ---------------------------------------------------------------- 引用链规格
# 10 条：条款（A/C 锚点）→ 证据（EV/B1）→ 正文引用（导出件书签段）
# GT-18 为补遗版本链（USG6650E→USG6705E，latest_version_wins）——正文引用取调整后型号
CHAIN_GTS = ["GT-01", "GT-02", "GT-03", "GT-05", "GT-06", "GT-13", "GT-15", "GT-16", "GT-17", "GT-18"]

_CHAIN_EV_DESC = {
    "GT-01": ("EV-01-营业执照.pdf", "营业执照副本"),
    "GT-02": ("EV-02-电子与智能化工程专业承包二级资质证书.pdf", "电子与智能化工程专业承包二级资质证书"),
    "GT-03": ("EV-03-类似业绩合同-智慧园区弱电工程.pdf", "类似业绩合同（智慧园区弱电工程等三项）"),
    "GT-05": ("EV-06-财务审计报告-2025年度.pdf", "2025 年度财务审计报告（标准无保留意见）"),
    "GT-06": ("EV-07-无失信记录承诺函.pdf", "无失信记录承诺函及信用查询记录"),
    "GT-13": ("EV-13-安全生产许可证.pdf", "安全生产许可证（附有效期说明与续期安排）"),
    "GT-15": ("EV-10-项目团队人员证书-网络工程师高级.pdf", "项目团队网络工程师（高级）人员证书"),
    "GT-16": ("B1-设备清单.pdf", "设备清单（附件 B1，应用服务器 GW-8000-T4）"),
    "GT-17": ("B1-设备清单.pdf", "设备清单（附件 B1，核心交换机 S5735-L48T4X-A1）"),
    "GT-18": ("B1-设备清单.pdf", "设备清单（附件 B1，防火墙型号按补遗 01 调整）"),
}

_BODY_SECTION_OF_GT = {  # 埋点 → 导出件章节（对齐 sections.jsonl 分类）
    "GT-01": "资格响应", "GT-02": "资格响应", "GT-03": "资格响应",
    "GT-05": "资格响应", "GT-06": "资格响应",
    "GT-13": "售后服务方案", "GT-15": "项目团队",
    "GT-16": "技术方案-网络与安全", "GT-17": "技术方案-网络与安全",
    "GT-18": "技术方案-网络与安全",
}

CIT_BODY_TEXT = {
    "GT-01": "响应说明：满足招标文件第 3.2.1 条资格要求，随附营业执照副本（EV-01）为有效存续证明。",
    "GT-02": "响应说明：满足招标文件第 3.2.2 条资质要求，随附电子与智能化工程专业承包二级资质证书（EV-02），有效期覆盖投标截止日。",
    "GT-03": "响应说明：满足招标文件第 3.2.3 条类似业绩要求，随附智慧园区弱电工程等三项合同（EV-03/EV-04/EV-05）。",
    "GT-05": "响应说明：满足招标文件第 3.2.5 条财务状况要求，随附 2025 年度财务审计报告（EV-06，标准无保留意见）。",
    "GT-06": "响应说明：满足招标文件第 3.2.6 条信用要求，随附无失信记录承诺函及信用查询记录（EV-07）。",
    "GT-13": "响应说明：满足招标文件第 4.2 条售后服务评分要求，随附安全生产许可证（EV-13）并说明有效期续期安排。",
    "GT-15": "响应说明：满足招标文件第 4.4 条项目团队评分要求，随附网络工程师（高级）人员证书（EV-10）。",
    "GT-16": "响应说明：应用服务器选用 GW-8000-T4，已列入设备清单（附件 B1），完全响应招标文件第五章 5.1 参数表要求。",
    "GT-17": "响应说明：核心交换机选用 S5735-L48T4X-A1，已列入设备清单（附件 B1），完全响应招标文件第五章 5.2 参数表要求。",
    "GT-18": "响应说明：防火墙型号按补遗文件 01 由 USG6650E-AC550 调整为 USG6705E-AC650（设备清单附件 B1 同步调整），响应以最新版本为准。",
}

SECTIONS_ORDER = ["资格响应", "技术方案-网络与安全", "售后服务方案", "项目团队",
                  "商务部分-报价", "格式与签署"]

BRIGHT_COMPANY = "杭州示例智能科技有限公司（示例用虚构主体）"
FORBIDDEN_WORDS = [BRIGHT_COMPANY, S.USCC, "示例智能"]  # 暗标禁字表（含长中短三级）


# ---------------------------------------------------------------- 低层 XML 工具
def _add_bookmark(paragraph, name: str, bid: int):
    start = OxmlElement("w:bookmarkStart")
    start.set(qn("w:id"), str(bid))
    start.set(qn("w:name"), name)
    end = OxmlElement("w:bookmarkEnd")
    end.set(qn("w:id"), str(bid))
    paragraph._p.insert(0, start)
    paragraph._p.append(end)


def _add_field(paragraph, instr: str, placeholder: str = ""):
    """简单域：begin + instrText + separate[+placeholder] + end（PAGE/NUMPAGES/TOC）。"""
    run = paragraph.add_run()
    fld = OxmlElement("w:fldChar")
    fld.set(qn("w:fldCharType"), "begin")
    run._r.append(fld)
    run = paragraph.add_run()
    instr_el = OxmlElement("w:instrText")
    instr_el.set(qn("xml:space"), "preserve")
    instr_el.text = instr
    run._r.append(instr_el)
    run = paragraph.add_run()
    fld = OxmlElement("w:fldChar")
    fld.set(qn("w:fldCharType"), "separate")
    run._r.append(fld)
    if placeholder:
        paragraph.add_run(placeholder)
    run = paragraph.add_run()
    fld = OxmlElement("w:fldChar")
    fld.set(qn("w:fldCharType"), "end")
    run._r.append(fld)


def _page_break(doc):
    from docx.enum.text import WD_BREAK
    p = doc.add_paragraph()
    p.add_run().add_break(WD_BREAK.PAGE)


def _make_org_chart_png(path: Path):
    """确定性实施组织架构图（PIL 绘制，无随机）。静态字体——可变字体 PIL 渲染空白（v0.4 字体事实）。"""
    from PIL import Image, ImageDraw, ImageFont
    W, H = 900, 430
    img = Image.new("RGB", (W, H), (255, 255, 255))
    d = ImageDraw.Draw(img)
    font = ImageFont.truetype("/usr/share/fonts/truetype/chinese/SarasaMonoSC-Regular.ttf", 20)
    boxes = [(360, 30, 540, 80, "项目经理"),
             (140, 150, 320, 200, "网络组"), (390, 150, 510, 200, "安全组"),
             (580, 150, 760, 200, "实施组"), (200, 290, 380, 340, "质检员"),
             (520, 290, 700, 340, "资料员")]
    for x0, y0, x1, y1, label in boxes:
        d.rectangle((x0, y0, x1, y1), outline=(60, 60, 60), width=2)
        tw = d.textlength(label, font=font)
        d.text(((x0 + x1 - tw) / 2, (y0 + y1) / 2 - 14), label, fill=(30, 30, 30), font=font)
    for x0, y0, x1, y1, _ in boxes[1:]:
        d.line((450, 80, 450, (80 + y0) // 2 + 10), fill=(60, 60, 60), width=2)
        d.line((450, (80 + y0) // 2 + 10, (x0 + x1) / 2, (80 + y0) // 2 + 10), fill=(60, 60, 60), width=2)
        d.line(((x0 + x1) / 2, (80 + y0) // 2 + 10, (x0 + x1) / 2, y0), fill=(60, 60, 60), width=2)
    d.line((300, 200, 300, 290), fill=(60, 60, 60), width=2)
    d.line((610, 200, 610, 290), fill=(60, 60, 60), width=2)
    # 像素自证（防可变字体静默空白）：节点标签必须真实落在像素层
    import numpy as np
    _a = np.asarray(img.convert("L"))
    assert (_a < 150).sum() >= 1500, f"组织架构图暗像素过少（{(_a < 150).sum()}<1500）——标签未渲染"
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, format="PNG", optimize=True)


# ---------------------------------------------------------------- 构建器
def build_bid_docx(out_path: Path, variant: str = "bright", workdir: Path | None = None) -> dict:
    """技术标交付样本构建（bright=明标带投标人标识；dark=暗标零标识）。
    返回 {chains, docx_sha256, page_breaks, ...}。"""
    assert variant in ("bright", "dark")
    tmp = workdir or out_path.parent
    img_path = Path(tmp) / "_org_chart.png"
    _make_org_chart_png(img_path)

    doc = Document()
    # ---- 封面（第 1 节：无页眉页脚）
    sec1 = doc.sections[0]
    for text, size, bold in [
            (S.PROJECT["name"], 22, True), ("技术标", 34, True),
            (f"项目编号：{S.PROJECT['code']}", 14, False),
            (f"投标人：{BRIGHT_COMPANY}" if variant == "bright" else "投标人：＿＿＿＿（暗标评审——不得出现任何可识别投标人信息）", 16, False),
            ("日期：2026 年 11 月", 14, False)]:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run(text)
        run.font.size = Pt(size)
        run.font.bold = bold
    if variant == "bright":
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run(f"统一社会信用代码：{S.USCC}")
        run.font.size = Pt(12)
    _page_break(doc)

    # ---- 第 2 节：目录 + 正文（页眉页脚）
    sec2 = doc.add_section(WD_SECTION.NEW_PAGE)
    sec2.header.is_linked_to_previous = False
    sec2.header.paragraphs[0].text = f"项目编号：{S.PROJECT['code']}｜技术标"
    sec2.header.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
    footer = sec2.footer
    footer.is_linked_to_previous = False
    fp = footer.paragraphs[0]
    fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    fp.add_run("第 ")
    _add_field(fp, "PAGE")
    fp.add_run(" 页 共 ")
    _add_field(fp, "NUMPAGES")
    fp.add_run(" 页")

    doc.add_heading("目录", level=1)
    toc_p = doc.add_paragraph()
    _add_field(toc_p, 'TOC \\o "1-2" \\h \\z \\u', placeholder="（目录域——打印前请更新域）")

    # ---- 正文六章
    chains = []
    bid = 100  # 书签 id 基（避开默认样式书签区段）
    break_before = True  # 首个正文章节也从目录页分页开新页
    for si, sec_title in enumerate(SECTIONS_ORDER):
        if break_before:
            _page_break(doc)
        break_before = True
        doc.add_heading(sec_title, level=1)
        if sec_title == "资格响应":
            doc.add_paragraph("本章按招标文件第三章资格要求逐条响应，佐证材料索引见各响应条目。")
        elif sec_title == "技术方案-网络与安全":
            doc.add_paragraph("本章给出网络与安全设备选型响应表及实施组织架构。")
            t = doc.add_table(rows=5, cols=5)
            t.style = "Table Grid"
            t.alignment = WD_TABLE_ALIGNMENT.CENTER
            t.cell(0, 0).merge(t.cell(0, 1))  # 设备信息 横向合并
            t.cell(0, 0).text = "设备信息"
            t.cell(0, 2).merge(t.cell(0, 3)).merge(t.cell(0, 4))  # 响应信息 横向合并
            t.cell(0, 2).text = "响应信息"
            for i, h in enumerate(["名称", "型号"]):
                t.cell(1, i).text = h
            for i, h in enumerate(["响应", "数量", "备注"]):
                t.cell(1, 2 + i).text = h
            rows = [("应用服务器", "GW-8000-T4", "完全响应", "4 台", ""),
                    ("核心交换机", "S5735-L48T4X-A1", "完全响应", "2 台", ""),
                    ("防火墙", "USG6705E-AC650", "完全响应", "2 台", "型号按补遗 01 调整")]
            for r, row in enumerate(rows):
                for c, v in enumerate(row):
                    t.cell(2 + r, c).text = v
            doc.add_paragraph("实施组织架构：")
            doc.add_picture(str(img_path), width=Cm(14))
        elif sec_title == "售后服务方案":
            doc.add_paragraph("本章按招标文件售后服务要求给出服务承诺与保障措施。")
            doc.add_paragraph("服务承诺：7×24 小时热线响应，2 小时内响应、4 小时内到场（市区范围）；"
                              "质保期内每月不少于 1 次巡检，常用备件本地库存不少于 50 项。")
        elif sec_title == "项目团队":
            doc.add_paragraph("本章列出项目团队关键岗位与人员资格。")
            doc.add_paragraph("项目经理：具备注册建造师执业资格，无在建项目；技术负责人：网络工程师（高级）。")
        elif sec_title == "商务部分-报价":
            doc.add_paragraph("本章为商务报价说明（样本件——完整报价明细见商务标分册）。")
            doc.add_paragraph("报价口径：以人民币元为单位，含税总价不高于最高限价；报价构成与设备清单（附件 B1）逐项对应。")
        elif sec_title == "格式与签署":
            doc.add_paragraph("本章载明签署与装订要求。")
            doc.add_paragraph("投标文件按正本 1 份、副本 4 份装订；以下为盖章处（正式递交件在此页加盖单位公章）：")
            sp = doc.add_paragraph()
            sp.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = sp.add_run("（盖单位公章处）")
            run.font.size = Pt(16)
            run.font.bold = True
        # 该章引用链段落（书签）
        for gt in [g for g in CHAIN_GTS if _BODY_SECTION_OF_GT[g] == sec_title]:
            p = doc.add_paragraph(CIT_BODY_TEXT[gt])
            name = f"CIT-{gt}"
            _add_bookmark(p, name, bid)
            bid += 1
            chains.append({"gt_id": gt, "bookmark": name, "body_text": CIT_BODY_TEXT[gt],
                           "clause_no": _clause_no(gt), "evidence": _CHAIN_EV_DESC[gt][0],
                           "evidence_desc": _CHAIN_EV_DESC[gt][1]})

    doc.save(str(out_path))
    # app.xml Company：bright 注入（证明清零非空洞）；dark 移除
    _patch_app_xml_company(out_path, company=("示例智能科技" if variant == "bright" else None))
    # docProps：bright 常规署名；dark 清零（V1-d G3 业务侧缓解）
    freeze_docx(out_path, core_props={"creator": "ai-bid-research" if variant == "bright" else "",
                                      "lastModifiedBy": "ai-bid-research" if variant == "bright" else ""})
    img_path.unlink(missing_ok=True)
    return {"variant": variant, "docx": str(out_path), "chains": chains,
            "docx_sha256": sha256_file(out_path),
            "page_breaks": len(SECTIONS_ORDER), "bookmarks": len(chains)}


def _clause_no(gt_id: str) -> str:
    reqs = {r["gt_id"]: r for r in S.REQUIREMENTS}
    return reqs[gt_id]["clause_no"]


def _patch_app_xml_company(path: Path, company: str | None):
    """docProps/app.xml Company 字段：注入（bright）/ 移除（dark）。"""
    with zipfile.ZipFile(path) as z:
        items = {i.filename: z.read(i.filename) for i in z.infolist()}
    key = "docProps/app.xml"
    if key not in items:
        return
    xml = items[key].decode("utf-8")
    if company:
        if "<Company>" in xml:
            xml = xml.replace(xml[xml.index("<Company>"):xml.index("</Company>") + len("</Company>")],
                              f"<Company>{company}</Company>")
        else:
            xml = xml.replace("</Properties>", f"<Company>{company}</Company></Properties>")
    else:
        import re
        xml = re.sub(r"<Company>[^<]*</Company>", "", xml)
    items[key] = xml.encode("utf-8")
    tmp = path.with_suffix(".docx.tmp")
    with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_DEFLATED) as zout:
        for name, data in items.items():
            zout.writestr(name, data)
    tmp.replace(path)


# ---------------------------------------------------------------- 条款/证据定位器
def build_chain_locators() -> list[dict]:
    """用 V1-a 解析面为 10 条链发射条款定位器与证据定位器（源文件侧）。"""
    parsed = {
        "A-招标文件.docx": v1_pipeline.parse_docx(CORPUS_A / "files" / "A-招标文件.docx"),
        "C-补遗文件01.docx": v1_pipeline.parse_docx(CORPUS_A / "files" / "C-补遗文件01.docx"),
    }
    ev_dir = CORPUS_A / "files" / "evidence"
    for gt, (ev_file, _) in _CHAIN_EV_DESC.items():
        p = ev_dir / ev_file if ev_file.startswith("EV-") else CORPUS_A / "files" / ev_file
        parsed[ev_file] = v1_pipeline.parse_pdf(p)
    reqs = {r["gt_id"]: r for r in S.REQUIREMENTS}
    out = []
    for gt in CHAIN_GTS:
        r = reqs[gt]
        clause_anchor = next(a for a in r["anchors"] if a["file"].startswith(("A-", "C-")))
        clause_loc = v1_pipeline.locate_anchor(clause_anchor, parsed)
        ev_file = _CHAIN_EV_DESC[gt][0]
        ev_loc = v1_pipeline.locate_anchor({"file": ev_file, "excerpt": _ev_probe(gt, ev_file),
                                            "kind": "table"}, parsed)
        out.append({"gt_id": gt, "clause_no": r["clause_no"], "clause_anchor": clause_anchor,
                    "clause_locator": clause_loc,
                    "evidence_file": ev_file, "evidence_locator": ev_loc})
    return out


def _ev_probe(gt: str, ev_file: str) -> str:
    """证据文件内探针文本（用于发射 PdfPageText 定位器）。"""
    probes = {
        "GT-01": "独立承担民事责任能力的法人营业执照" if False else "名称：杭州示例智能科技有限公司",
        "GT-02": "资质类别及等级：电子与智能化工程专业承包 二级",
        "GT-03": "合同名称：某智慧园区一期弱电系统工程",
        "GT-05": "审计意见：标准无保留意见",
        "GT-06": "承诺内容：本单位未被列入失信被执行人名单",
        "GT-13": "许可范围：建筑施工",
        "GT-15": "专业：网络工程师（高级）",
        "GT-16": "GW-8000-T4",
        "GT-17": "S5735-L48T4X-A1",
        "GT-18": "USG6650E-AC550",
    }
    return probes[gt]


# ---------------------------------------------------------------- LO 渲染
def lo_convert_pdf(docx_path: Path, outdir: Path) -> Path:
    outdir.mkdir(parents=True, exist_ok=True)
    env_home = outdir / ".loprofile"
    env_home.mkdir(exist_ok=True)
    cmd = ["soffice", "--headless", "--norestore",
           f"-env:UserInstallation=file://{env_home}",
           "--convert-to", "pdf", "--outdir", str(outdir), str(docx_path)]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=180,
                       env={"HOME": str(env_home), "PATH": "/usr/bin:/bin"})
    pdf = outdir / (docx_path.stem + ".pdf")
    if r.returncode != 0 or not pdf.exists():
        raise RuntimeError(f"LO 转换失败: {r.stderr[:300]}")
    return pdf


# ---------------------------------------------------------------- V1-c 保真检查
def run_fidelity_checks(docx_path: Path, workdir: Path) -> dict:
    """一级结构读回 + 二级 LO 渲染断言。"""
    doc = Document(str(docx_path))
    xml = zipfile.ZipFile(docx_path).read("word/document.xml").decode("utf-8")

    # ---- 一级：结构读回
    bookmarks = []
    import re
    for m in re.finditer(r'<w:bookmarkStart[^>]*w:name="(CIT-[^"]+)"', xml):
        bookmarks.append(m.group(1))
    checks = {
        "bookmarks_10": len(bookmarks) == 10,
        "toc_field": 'TOC \\o' in xml,
        "page_field_footer": any("PAGE" in zipfile.ZipFile(docx_path).read(n).decode("utf-8")
                                  for n in zipfile.ZipFile(docx_path).namelist()
                                  if n.startswith("word/footer")),
        "numpages_field": any("NUMPAGES" in zipfile.ZipFile(docx_path).read(n).decode("utf-8")
                              for n in zipfile.ZipFile(docx_path).namelist()
                              if n.startswith("word/footer")),
        "image_part": any(n.startswith("word/media/") for n in zipfile.ZipFile(docx_path).namelist()),
        "page_breaks_7": xml.count('<w:br w:type="page"/>') == 7,
        "merged_table": "设备信息" in xml and "响应信息" in xml,
        "sections_2": len(doc.sections) == 2,
        "header_text": any("项目编号" in (p.text or "") for s in doc.sections for p in s.header.paragraphs),
        "seal_placeholder": "盖单位公章处" in xml,
    }

    # ---- 二级：LO 渲染
    pdf = lo_convert_pdf(docx_path, workdir)
    import fitz
    d = fitz.open(str(pdf))
    page_texts = [p.get_text() for p in d]
    # 图片实际绘制位置（get_images 会受共享资源字典影响——取 bbox 级 get_image_info）
    page_img_drawn = [len(p.get_image_info()) for p in d]
    norm = [re.sub(r"\s+", "", t) for t in page_texts]
    n = len(page_texts)
    render = {
        "pages": n,
        "cover_no_header": "｜技术标" not in norm[0],
        "header_on_body_pages": all("项目编号" in t for t in page_texts[1:]),
        "footer_page_numbers": all(f"第{i + 1}页" in norm[i] for i in range(1, n)),
        "toc_page": "目录" in page_texts[1],
        "each_section_new_page": _sections_on_distinct_pages(page_texts),
        "image_page_present": any(c > 0 for c in page_img_drawn),
        "image_drawn_on_tech_page": page_img_drawn[_page_of_section(page_texts, "技术方案-网络与安全")] > 0,
        "citation_visible": all(any(p in t for t in norm)
                                 for p in ["满足招标文件第3.2.1条", "满足招标文件第4.4条",
                                           "响应以最新版本为准"]),
    }
    return {"docx": str(docx_path), "structure": checks, "render": render,
            "pdf_pages": n, "lo_manual_note": "Word+WPS 人工复验为待人工步骤（test-plan §5.5）"}


def _has_part(path: Path, name: str) -> bool:
    return name in zipfile.ZipFile(path).namelist()


def _sections_on_distinct_pages(page_texts: list[str]) -> bool:
    pages = {}
    for sec in SECTIONS_ORDER:
        hit = [i for i, t in enumerate(page_texts) if sec in t]
        if len(hit) != 1:
            return False
        pages[sec] = hit[0]
    return list(pages.values()) == sorted(pages.values()) and len(set(pages.values())) == len(pages)


def _page_of_section(page_texts: list[str], section: str) -> int:
    for i, t in enumerate(page_texts):
        if section in t:
            return i
    return -1


# ---------------------------------------------------------------- CLI
def main() -> int:
    out = Path(sys.argv[sys.argv.index("--out") + 1]) if "--out" in sys.argv else REPO / "artifacts" / "v1"
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        bright = out / "技术标-导出样本.docx"
        info = build_bid_docx(bright, "bright", workdir=td)
        report = run_fidelity_checks(bright, td / "lo")
        locators = build_chain_locators()
        report["chains"] = [{"gt_id": c["gt_id"], "bookmark": c["bookmark"]} for c in info["chains"]]
        report["chain_locators"] = locators
        (out / "export-report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"docx_sha256": info["docx_sha256"],
                          "structure": report["structure"], "render": report["render"]},
                         ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
