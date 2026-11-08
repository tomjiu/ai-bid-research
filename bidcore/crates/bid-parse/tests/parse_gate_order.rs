//! #529（B-23 门序收口）回归：parse_file / parse_file_with_sha 的
//! **扩展名门 → 字节门 → 哈希** 顺序与错误文案契约。
//!
//! 原实现第一步全文件哈希：超限件（>500MB）与不支持类型被拒前白读一遍。
//! 本文件锁三件事：
//! 1. 不支持扩展名 → 立即「不支持的文件类型 .{ext}」（不进任何内容读）；
//! 2. 超限 pdf（稀疏文件秒建）→ 「pdf 防护拒绝: 输入字节超限」（文案与
//!    engines::parse_pdf 内层门完全一致——门序前置不改变拒绝语义）；
//! 3. `parse_file_with_sha` 与 `parse_file` 对同一夹具产出等价（sha 回填
//!    来自调用方——import 链复用幂等面哈希的正确性）。

use std::path::PathBuf;

fn temp_path(name: &str) -> PathBuf {
    let d = std::env::temp_dir().join(format!("bidparse-gate-{}-{}", std::process::id(), name));
    std::fs::create_dir_all(&d).unwrap();
    d.join(name)
}

#[test]
fn unsupported_extension_rejected_before_any_read() {
    let p = temp_path("not-supported.zip");
    std::fs::write(&p, b"PK\x03\x04 whatever").unwrap();
    let err = bid_parse::parse_file(&p, "not-supported.zip").unwrap_err();
    assert!(
        err.contains("不支持的文件类型 .zip"),
        "扩展名门应先于一切内容读：{err}"
    );
    // with_sha 同款门序（哈希由调用方给——扩展名不合法时照样先拒）
    let err2 =
        bid_parse::parse_file_with_sha(&p, "not-supported.zip", "sha256:deadbeef").unwrap_err();
    assert!(
        err2.contains("不支持的文件类型 .zip"),
        "with_sha 扩展名门：{err2}"
    );
}

#[test]
fn oversized_pdf_rejected_by_gate_with_same_message() {
    // 稀疏文件：set_len 立即生效（不写内容），>500MB 门即拒——
    // 若实现退回「先哈希」旧序，本测试会因全量读 600MB 而显著变慢。
    let p = temp_path("oversized.pdf");
    let f = std::fs::File::create(&p).unwrap();
    f.set_len(bid_parse::guard::LIMIT_INPUT_BYTES_PDF + 1).unwrap();
    drop(f);

    let err = bid_parse::parse_file(&p, "oversized.pdf").unwrap_err();
    assert!(
        err.contains("pdf 防护拒绝") && err.contains("输入字节超限"),
        "字节门文案与 engines::parse_pdf 内层门一致：{err}"
    );
    let err2 =
        bid_parse::parse_file_with_sha(&p, "oversized.pdf", "sha256:deadbeef").unwrap_err();
    assert!(
        err2.contains("pdf 防护拒绝") && err2.contains("输入字节超限"),
        "with_sha 同款字节门（幂等复检）：{err2}"
    );
    std::fs::remove_file(&p).ok();
}

#[test]
fn with_sha_matches_parse_file_on_fixture() {
    // 同一夹具两入口等价：sha256 回填都正确（parse_file 自算 / with_sha 复用）。
    let root = env!("CARGO_MANIFEST_DIR");
    let candidates = [
        "../../fixtures/corpus-A/files/A-招标文件.pdf",
        "../../real-corpus/water/files/04_某水利工程施工标段_施工招标文件.pdf",
    ];
    let Some(path) = candidates
        .iter()
        .map(|c| std::path::Path::new(root).join(c))
        .find(|p| p.is_file())
    else {
        eprintln!("SKIP：仓内无轻量 pdf 夹具（corpus 未随测试环境携带）");
        return;
    };
    let name = path.file_name().unwrap().to_string_lossy().to_string();
    let a = bid_parse::parse_file(&path, &name).expect("parse_file 夹具解析");
    let sha = bid_parse::sha256_file(&path).unwrap();
    let b =
        bid_parse::parse_file_with_sha(&path, &name, &sha).expect("with_sha 夹具解析");
    assert_eq!(a.sha256, sha, "parse_file 自算哈希应与流式哈希一致");
    assert_eq!(a.sha256, b.sha256, "两入口 sha 回填一致");
    assert_eq!(a.blocks.len(), b.blocks.len(), "两入口块数一致");
    assert_eq!(a.parse_summary, b.parse_summary, "两入口 parse_summary 一致");
}
