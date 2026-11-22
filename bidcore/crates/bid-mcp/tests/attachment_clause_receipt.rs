//! #177 回执面（MCP import_tender_files）——附件 kind 条款密集提示透出验证。
//!
//! 服务层（bid-tools import_files）的判据与正负例钉在
//! bid-tools/tests/attachment_clause_hint.rs；本测试只钉**契约面**：
//! 提示经 per_file[].warnings 透出到 import_tender_files 响应（Agent
//! 第一现场可见——非静默 0 条），严格模式语义不变（提示不失败、不改
//! 状态机、不自动改 kind）。
//!
//! SKIP 纪律（#9）：素材不可达时 skip。

use bid_mcp::{dispatch_with, BidService, ToolCall, ToolReply};
use serde_json::{json, Value};
use std::path::PathBuf;

fn repo_root() -> PathBuf {
    let p = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../..");
    std::fs::canonicalize(&p).unwrap_or(p)
}

fn call(svc: &mut BidService, tool: &str, args: Value) -> ToolReply {
    dispatch_with(svc, ToolCall { tool: tool.to_string(), args })
}

fn ok(svc: &mut BidService, tool: &str, args: Value) -> Value {
    match call(svc, tool, args) {
        ToolReply::Ok(out) => out.result,
        ToolReply::Err { error, .. } => panic!("{tool} 应成功但失败: {error}"),
    }
}

/// unicom-ry 技术规范书经 MCP 导入（kind=附件）→ 回执 per_file[0].warnings
/// 携带 ATTACHMENT_CLAUSE_DENSE；kind 回显不变（不自动改 kind）。
#[test]
fn mcp_receipt_carries_clause_dense_hint_for_attachment_kind() {
    let path = repo_root().join("real-corpus/telecom/parse-input/B-unicom-ry-技术规范书.docx");
    if !path.exists() {
        eprintln!("[SKIP] 素材不可达: {}", path.display());
        return;
    }
    let ws = std::env::temp_dir().join(format!(
        "i177-mcp-{:?}-{:?}",
        std::process::id(),
        std::thread::current().id()
    ));
    let _ = std::fs::remove_dir_all(&ws);
    std::fs::create_dir_all(&ws).unwrap();
    let mut svc = BidService::open(&ws).unwrap().with_fs_root(repo_root());

    let pid = ok(&mut svc, "create_bid_project", json!({
        "name": "#177 回执面", "bid_deadline": "2026-12-31", "mode": "明标",
        "external_key": "i177-mcp-receipt",
    }))["project_id"]
        .as_str()
        .unwrap()
        .to_string();

    let rel = path
        .strip_prefix(repo_root())
        .map(|p| p.to_string_lossy().into_owned())
        .unwrap_or_else(|_| path.to_string_lossy().into_owned());
    let out = ok(&mut svc, "import_tender_files", json!({
        "project_id": pid,
        "files": [{ "upload_ref": rel, "filename": "B-unicom-ry-技术规范书.docx", "kind": "附件" }],
    }));
    // per_file 数量与幂等面
    let per_file = out["per_file"].as_array().expect("per_file 在场");
    assert_eq!(per_file.len(), 1);
    let entry = &per_file[0];
    // 回执面可见提示（验收 1 的 MCP 半边）
    let warnings = entry["warnings"].as_array().cloned().unwrap_or_default();
    let hint = warnings
        .iter()
        .map(|w| w.as_str().unwrap_or_default())
        .find(|w| w.contains("ATTACHMENT_CLAUSE_DENSE"))
        .expect("MCP 回执必须透出提示（Agent 第一现场）");
    assert!(hint.contains("17 行"), "行数入提示: {hint}");
    assert!(hint.contains("kind=招标文件"), "指路重导: {hint}");
    // 不自动改 kind（语义决策留人）——回显仍是导入时登记的附件
    assert_eq!(entry["kind"].as_str(), Some("附件"), "kind 不被提示面改写");
    // 提示不失败（totals 正常、无 item_errors）
    assert_eq!(out["totals"]["files"].as_u64(), Some(1));
    let _ = std::fs::remove_dir_all(&ws);
}
