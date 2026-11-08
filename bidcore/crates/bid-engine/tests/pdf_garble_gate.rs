//! #557（B-12 残留面）：pdfium 文本层乱码闸三态测试。
//!
//! 缺陷背景：`parse_pdf_via_engine` 对**纯文本乱码件**直采信——pdfium 在
//! CID-CJK 解码失败的件上照样「成功」输出 Latin-1 乱码残渣（any_text_layer=
//! true、无空页），映射照常产块，乱码静默进 blocks。闸 [`pdf_garble_gate`]
//! 在采信前过 `bid_parse::pdf_text::probe_cjk_garble_pages`（单一真源）：
//! Garbled → `MappingGap`，调用方（service.rs 的 `or_else`）回退旧路径的
//! 完整仲裁链（#169/#200）。
//!
//! **无需 pdfium**：直接构造 `EnginePdf`（合成页文本）+ 真实夹具字节
//! （`C-补遗文件.pdf`——字典声明 STSong-Light + Adobe-GB1，探针的
//! `cid_cjk_font_in_use` 判据在此字节上为真）。乱码残渣串取自 CI 实测
//! 形态（addendum_recovery.rs `cjk_garble_probe_three_states` 同款样本）。

use bid_engine::pdf_garble_gate;
use bid_engine::types::EnginePdf;

fn fixture_addendum() -> std::path::PathBuf {
    std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("../../../fixtures/synth-tender/招标文件/C-补遗文件.pdf")
}

/// 诚实 SKIP：夹具不在时不能用「pass」冒充通过（issue #9 口径）。
fn require_fixture() -> Option<Vec<u8>> {
    let p = fixture_addendum();
    if !p.exists() {
        eprintln!(
            "【SKIP】缺少补遗夹具 {}（本回归不能验证，但不伪装通过）",
            p.display()
        );
        return None;
    }
    Some(std::fs::read(&p).expect("夹具读取失败"))
}

/// CI 实测乱码残渣（Windows poppler 缺 CMap 资源的输出形态——与
/// addendum_recovery.rs `cjk_garble_probe_three_states` 同款样本，两测试
/// 面共享同一形态家族）。
const GARBLED: &str = "g--^{,NN\"lS;bfzagu?b?riTQ^sS^oeyveWeN01 S\n\
    s[?bheNLRQ[,,O\\YNonNOe90g,eWeNN:bheNv~~bLRNbheNQwgT{Il_eHR\n\
    NNNKYNg,eWeNN:Q0bhN\"e6R0g,eWT 24 \\eQNfbVbgxn/0\n\
    1.1 SbheN~[v_he\"2026-11-18 09:30\"SfN:\"2026-11-30 09:30\"";

/// 正常解码的中文页（同字体声明的合法输出形态）。
const CLEAN: &str = "某市第一人民医院智慧病房物联网平台建设项目补遗文件（01 号）\n\
    1.1 原招标文件规定的开标时间变更为 2026-11-30 09:30；调整后的控制价 1580 万元。";

fn pdf_of(pages: Vec<String>) -> EnginePdf {
    let any_text_layer = pages
        .iter()
        .any(|t| t.chars().filter(|c| !c.is_whitespace()).count() >= 16);
    EnginePdf {
        pages,
        any_text_layer,
    }
}

/// ① 乱码页 + CJK 声明字节 → 闸拒（MappingGap——回退旧路径仲裁链）。
#[test]
fn garbled_pages_with_cjk_font_rejected() {
    let Some(raw) = require_fixture() else { return };
    let pdf = pdf_of(vec![GARBLED.to_string()]);
    let err = pdf_garble_gate(&raw, &pdf).expect_err("乱码页必须被闸拒");
    match err {
        bid_engine::EngineError::MappingGap(msg) => {
            assert!(msg.contains("CJK 乱码"), "MappingGap 语义应指明乱码回退：{msg}");
        }
        other => panic!("期望 MappingGap，实际 {other:?}"),
    }
}

/// ② 正常中文页 + 同字节 → 闸放行（零误伤——干净文本层照常走引擎映射）。
#[test]
fn clean_chinese_pages_pass() {
    let Some(raw) = require_fixture() else { return };
    let pdf = pdf_of(vec![CLEAN.to_string()]);
    pdf_garble_gate(&raw, &pdf).expect("正常中文页必须放行（零误伤）");
}

/// ③ 英文件（无 CJK 声明）+ 乱码形态页 → NoSignal 放行（防误伤：探针对
/// 无 CJK 字体声明的件永不激活——闸不拦英文件）。
#[test]
fn english_pdf_never_gated() {
    let english_pdf = b"%PDF-1.4\n1 0 obj\n<< /BaseFont /Helvetica /Type /Font /Subtype /Type1 >>\nendobj\n%%EOF";
    let pdf = pdf_of(vec![GARBLED.to_string()]);
    pdf_garble_gate(english_pdf, &pdf).expect("无 CJK 声明的字节必须放行（NoSignal 防误伤）");
}

/// ④ 样本不足（<32 非空白）→ NoSignal 放行（空文本层由上层既有判定处理，
/// 与探针退化面一致）。
#[test]
fn insufficient_sample_passes() {
    let Some(raw) = require_fixture() else { return };
    let pdf = pdf_of(vec!["short text".to_string()]);
    pdf_garble_gate(&raw, &pdf).expect("样本不足必须放行（NoSignal）");
}
