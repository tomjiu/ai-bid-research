//! qual_lexicon_symmetry.rs —— #189（AUD2-19）：资格词表单一真源 +
//! 评分分值形态空格口径的跨格式对称锁定。
//!
//! 审计 AUD2-19：extract.rs PDF 私有 re_qual 与 veto_lexicon 共享表差集
//! 两向（PDF 独有「级资质」；共享独有「项目负责人|项目总监|监理工程师|
//! 具备.*资质|须具备」5 形态）——同一条款跨格式资格分类不同（#428 只
//! 统一了否决词面，资格面漏修）。修复后（「级资质」上提并入共享表、
//! PDF 侧消费真源）本文件锁定三件事：
//!
//! 1. **词面层**：差集两向探针 `is_qual` 同判 true（含上提的「级资质」
//!    与下发的 5 形态）；
//! 2. **分类层对称**：共享独有形态探针在 docx / pdf 两格式下
//!    `extract_requirements` 分类全等且落「资格条件」——修复前 PDF 侧
//!    miss（编号行落章节兜底类），即「同一条款跨格式分类不同」本体；
//! 3. **score_shape 空格口径**：pdftotext 插空格形态「10 分」在 PDF 面
//!    计为分值形态（≥2 处 → 评分语义行）——修复前 `\d+分` 不容空格，
//!    评分结构行判定漏计。
//!
//! 探针为「编号头 + 资格章上下文」形态（两侧落账最小共同形态，对齐
//! veto_cross_format_symmetry.rs 的形态解剖）。

use bid_parse::extract::extract_requirements;
use bid_parse::veto_lexicon;
use bid_parse::{Block, BlockKind, ParsedFile};

fn docx_pf(text: &str) -> ParsedFile {
    docx_pf_in(text, "第二章 投标人须知 > 3.资格审查")
}

fn docx_pf_in(text: &str, locator: &str) -> ParsedFile {
    ParsedFile {
        name: "A-test.docx".to_string(),
        sha256: "test".into(),
        pages: 1,
        tables: 0,
        has_text_layer: true,
        ocr_blocks: 0,
        blocks: vec![Block {
            idx: 0,
            kind: BlockKind::Para,
            locator: locator.into(),
            text: format!("2.3 {text}"),
            cells: vec![],
        }],
        parse_summary: "test".into(),
        components: vec![],
    }
}

fn pdf_pf(text: &str) -> ParsedFile {
    pdf_pf_in(text, "第二章 投标人须知 行1")
}

fn pdf_pf_in(text: &str, locator: &str) -> ParsedFile {
    pdf_pf_blocks(vec![
        // PDF 侧章上下文来自块流中的章标题行（chapter_of 按块匹配），探针
        // 须带章头块——对齐 veto_cross_format_symmetry.rs 的形态解剖。
        Block {
            idx: 0,
            kind: BlockKind::PdfLine,
            locator: "行0".into(),
            text: locator.split(" 行").next().unwrap_or(locator).to_string(),
            cells: vec![],
        },
        Block {
            idx: 1,
            kind: BlockKind::PdfLine,
            locator: locator.into(),
            text: format!("2.3 {text}"),
            cells: vec![],
        },
    ])
}

fn pdf_pf_blocks(blocks: Vec<Block>) -> ParsedFile {
    ParsedFile {
        name: "A-test.pdf".to_string(),
        sha256: "test".into(),
        pages: 1,
        tables: 0,
        has_text_layer: true,
        ocr_blocks: 0,
        blocks,
        parse_summary: "test".into(),
        components: vec![],
    }
}

fn cats(files: &[ParsedFile]) -> Vec<String> {
    extract_requirements(files)
        .into_iter()
        .map(|r| r.category)
        .collect()
}

/// 词面层：差集两向探针同判 true。
#[test]
fn qual_lexicon_diffs_both_directions_hit() {
    // 共享独有 5 形态（修复前 PDF 面 miss 的差集向）
    for t in [
        "项目负责人须为本单位在职员工",
        "项目总监具有五年以上经验",
        "监理工程师持有效证书",
        "投标人须具备市政公用工程资质",
        "施工人员须具备特种作业资质",
    ] {
        assert!(veto_lexicon::is_qual(t), "共享独有形态须命中: {t}");
    }
    // PDF 独有形态上提（「级资质」——修复前共享表 miss）
    for t in ["投标人具有二级资质", "企业具备甲级资质"] {
        assert!(veto_lexicon::is_qual(t), "上提形态「级资质」须命中: {t}");
    }
    // 既有双面形态不回归
    assert!(veto_lexicon::is_qual("投标人须提供营业执照副本"));
    assert!(!veto_lexicon::is_qual("普通商务条款无资格语义"));
}

/// 分类层对称：共享独有形态探针在两格式下同落「资格条件」
/// （修复前 PDF 侧 miss——编号行落章节兜底「其他」）。
#[test]
fn qual_category_symmetric_across_formats() {
    for t in [
        "项目负责人须为本单位在职员工",
        "监理工程师持有效注册证书",
        "投标人须具备同类项目实施资质",
    ] {
        let d = cats(&[docx_pf(t)]);
        let p = cats(&[pdf_pf(t)]);
        assert_eq!(
            d, p,
            "跨格式分类须全等（探针 {t:?}：docx={d:?} pdf={p:?}）"
        );
        assert_eq!(
            d.first().map(String::as_str),
            Some("资格条件"),
            "资格探针须落资格条件（探针 {t:?} 实得 {d:?}）"
        );
    }
}

/// score_shape 空格口径：pdftotext 插空格形态「10 分」在 PDF 面计为
/// 分值形态——「≥2 处分值」的评分语义行不因空格漏计（修复前
/// `\d+分` 不容空格，本探针行的分值计数为 0 → 走非评分分支）。
#[test]
fn score_shape_tolerates_pdftotext_spaces_on_pdf_face() {
    // 评标办法章内「≥2 处 N分（可带空格）」→ 评分项锁定（P0-B 修订 2
    // ——分值形态锁只在评标办法章内生效，探针须放评分章上下文）
    let text = "本项评分 10 分，其中方案完整性 5 分，实施进度 5 分";
    let d = cats(&[docx_pf_in(text, "第三章 评标办法 > 1.详细评审")]);
    let p = cats(&[pdf_pf_in(text, "第三章 评标办法 行1")]);
    assert_eq!(d, p, "评分结构行跨格式分类须全等: docx={d:?} pdf={p:?}");
    assert_eq!(
        d.first().map(String::as_str),
        Some("评分项"),
        "带空格分值形态的评分结构行须锁评分项（实得 {d:?}）"
    );
}
