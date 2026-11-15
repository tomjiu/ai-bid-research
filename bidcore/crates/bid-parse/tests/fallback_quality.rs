//! Unsupported ToUnicode arrays must not manufacture accepted text.
use bid_parse::pdf_text::parse_via_fallback;

#[test]
fn unused_array_cmap_does_not_reject_english() {
    let path = std::env::temp_dir().join(format!("bid167-unused-{}.pdf", std::process::id()));
    let pdf = String::from_utf8(array_pdf().to_vec()).unwrap().replace(
        "/F1 12 Tf <0020002100220023>",
        "/F2 12 Tf (Normal English information without requirements)",
    );
    std::fs::write(&path, pdf).unwrap();
    let parsed = parse_via_fallback(&path, "english.pdf").unwrap();
    std::fs::remove_file(path).unwrap();
    assert!(parsed
        .blocks
        .iter()
        .any(|b| b.text.contains("Normal English")));
}

#[test]
fn scan_with_unused_array_map_remains_no_text_layer() {
    let path = std::env::temp_dir().join(format!("bid167-scan-{}.pdf", std::process::id()));
    let pdf = String::from_utf8(array_pdf().to_vec())
        .unwrap()
        .replace("BT /F1 12 Tf <0020002100220023> Tj ET", "q Q");
    std::fs::write(&path, pdf).unwrap();
    let err = parse_via_fallback(&path, "scan.pdf").unwrap_err();
    std::fs::remove_file(path).unwrap();
    assert!(err.contains("无文本层"), "{err}");
    assert!(!err.contains("PDF_QUALITY_UNSUPPORTED_CMAP"), "{err}");
}

#[test]
fn scalar_map_with_english_quotes_is_accepted() {
    let path = std::env::temp_dir().join(format!("bid167-quotes-{}.pdf", std::process::id()));
    let pdf = String::from_utf8(array_pdf().to_vec())
        .unwrap()
        .replace("[<0020> <0032> <0030> <4EBA>]", "<201C>");
    std::fs::write(&path, pdf).unwrap();
    let parsed = parse_via_fallback(&path, "quotes.pdf").unwrap();
    std::fs::remove_file(path).unwrap();
    assert_eq!(parsed.blocks[0].text, "“”„‟");
}

fn array_pdf() -> &'static [u8] {
    b"%PDF-1.4
1 0 obj
<< /Font << /F1 2 0 R >> >>
endobj
2 0 obj
<< /Type /Font /Subtype /Type0 /Encoding /Identity-H /ToUnicode 3 0 R >>
endobj
3 0 obj
<< /Length 100 >>
stream
1 beginbfrange
<0020> <0023> [<0020> <0032> <0030> <4EBA>]
endbfrange
endstream
endobj
4 0 obj
<< /Length 60 >>
stream
BT /F1 12 Tf <0020002100220023> Tj ET
endstream
endobj
%%EOF
"
}

#[test]
fn used_array_cmap_is_fail_visible() {
    let path = std::env::temp_dir().join(format!("bid167-array-{}.pdf", std::process::id()));
    std::fs::write(&path, array_pdf()).unwrap();
    let result = parse_via_fallback(&path, "array.pdf");
    std::fs::remove_file(path).unwrap();
    let error = result.expect_err("unsupported used array map must not be accepted as text");
    assert!(error.contains("PDF_QUALITY_UNSUPPORTED_CMAP"), "{error}");
}
