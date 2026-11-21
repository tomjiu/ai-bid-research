//! #187（AUD2-4/5/6）：转换面安全收口三合一——回归锁。
//!
//! - AUD2-4：convert_to_pdf_word 面智能引号注入——原仅转义 ASCII 单引号，
//!   智能引号（PowerShell 单引号同义词，中文标书名「'十四五'规划」常见）
//!   裸进 '…' 字面量断裂字符串（DoS）/恶意构造注入任意 PS 语句。修复后
//!   与 doc2docx 面（#165）共用 `ps_single_quoted_literal` 单一真源。
//! - AUD2-5：.doc 转换 fallback 目录固定共享名（temp/bid-doc-convert）+
//!   sha16 内容寻址缓存——预置 {sha16}.docx 投毒面。修复后 pid+nanos 唯一。
//! - AUD2-6：超时 taskkill /F /IM WINWORD.EXE 强杀用户全部 Word——修复后
//!   对齐 doc2docx「归属无法确认时不强杀」策略（本文件锁消息文案面；
//!   Windows 行为面 Linux 不可测，代码审读 + PR 登记）。

use bid_tools::service::ps_single_quoted_literal;

/// AUD2-4 主锁：智能引号路径编码为 [char]N 码位拼接——脚本字面量不含
/// 任何裸智能引号（PS 单引号同义词零出现）。
#[test]
fn ps_literal_encodes_smart_quotes_as_char_units() {
    let out = ps_single_quoted_literal("标书‘十四五’规划.docx");
    assert!(out.contains("[char]"), "智能引号须编码为 [char]N 形态: {out}");
    assert!(!out.contains('\u{2018}'), "裸 U+2018 不得出现在字面量: {out}");
    assert!(!out.contains('\u{2019}'), "裸 U+2019 不得出现在字面量: {out}");
    assert!(!out.contains('\u{201A}'), "裸 U+201A 不得出现在字面量: {out}");
    assert!(!out.contains('\u{201B}'), "裸 U+201B 不得出现在字面量: {out}");
    // 普通中文字符以码位形态在位（#165 既有语义：含智能引号 → 全串
    // 编码；「标」= U+6807 = 26631）
    assert!(out.contains("[char]26631"), "非引号字符以码位保留（标=26631）: {out}");
}

/// AUD2-4 次锁：四形态智能引号全覆盖（U+2018/2019/201A/201B）。
#[test]
fn ps_literal_covers_all_four_smart_quote_forms() {
    for probe in ['\u{2018}', '\u{2019}', '\u{201A}', '\u{201B}'] {
        let path = format!("a{probe}b.docx");
        let out = ps_single_quoted_literal(&path);
        assert!(!out.contains(probe), "形态 {probe:?} 须编码（实得 {out}）");
    }
}

/// AUD2-4 三锁：纯 ASCII 撇号路径走双写（#165 既有语义不回归）。
#[test]
fn ps_literal_ascii_apostrophe_doubled() {
    let out = ps_single_quoted_literal("C:\\temp\\it's a doc.docx");
    assert!(out.contains("it''s"), "ASCII 撇号双写: {out}");
    assert!(!out.contains("[char]"), "纯 ASCII 不走码位编码: {out}");
}

/// AUD2-4 四锁：doc2docx 脚本生成消费共用真源（#165 面零回归）。
#[test]
fn doc2docx_script_consumes_shared_literal() {
    let script = bid_tools::service::build_doc2docx_script("‘十四五’.docx", "out.docx");
    assert!(script.contains("[char]8216"), "doc2docx 面共用真源（U+2018=8216）");
    assert!(!script.contains('\u{2018}'), "doc2docx 脚本无裸智能引号");
}

/// AUD2-5：fallback 目录唯一化——预置固定名投毒不再命中共享目录。
/// （import_doc_converted 私有；行为锁通过「固定名目录不再被创建/使用」
/// 的间接面：连续两次构造的目录名不同。目录构造内联在私有函数中，
/// 本锁以源码 grep 断言固定名字面量已移除——Windows/Linux 双面成立。）
#[test]
fn fallback_convert_dir_no_fixed_shared_name() {
    let src = std::fs::read_to_string(concat!(
        env!("CARGO_MANIFEST_DIR"),
        "/src/service.rs"
    ))
    .expect("service.rs 可读");
    assert!(
        !src.contains(r#".join("bid-doc-convert")"#),
        "固定共享名 temp/bid-doc-convert 不得再现（AUD2-5）"
    );
    assert!(
        src.contains("bid-doc-convert-{}-{}"),
        "唯一名构造（pid+nanos）应在位（AUD2-5）"
    );
}

/// AUD2-6：taskkill /F /IM 强杀命令移除（源码锁——Windows 行为面
/// Linux 不可测，文案面见超时错误信息）。
#[test]
fn no_blanket_taskkill_on_user_word_processes() {
    let src = std::fs::read_to_string(concat!(
        env!("CARGO_MANIFEST_DIR"),
        "/src/service.rs"
    ))
    .expect("service.rs 可读");
    assert!(
        !src.contains("\"/F\", \"/IM\", \"WINWORD.EXE\""),
        "taskkill /F /IM WINWORD.EXE 强杀不得再现（AUD2-6——杀用户全部 Word）"
    );
    assert!(
        src.contains("归属无法确认时不强杀"),
        "不强杀策略文案应在位（对齐 doc_conversion.rs）"
    );
}
