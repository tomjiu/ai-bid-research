//! semantic_conflict_179.rs —— #179 异号语义冲突检不出（audit F-5 / PR
//! #172 §4 立项）的验收契约。
//!
//! ## 问题（issue 原文）
//!
//! GT CONFLICT-01 控制价冲突（A 件 6.1「480 万」vs C 补遗「三、招标控制价
//! 调整」→ 465 万）**条款号不同**，最小面冲突检测（同 clause_no 异文）口径
//! 内检不出——两版本 REQ 共在（摘录逐字落盘），但无语义归并/终裁面。
//!
//! ## 交付面
//!
//! 1. **语义冲突识别**：extract 响应 conflicts[] 新增语义级条目（补遗×主件
//!    同主题异号不同值——高价值三主题控制价/工期/保证金，纯函数
//!    bid-tools::semantic_conflicts）；
//! 2. **终裁面**：conflicts[].resolution 指路 register_addendum_changes 的
//!    value_changed 人工显式登记通道（补遗优先，人工确认后生效，**不自动
//!    改写**）。
//!
//! ## 验收对照（issue #179）
//!
//! | 用例 | 断言 |
//! |---|---|
//! | corpus-A CONFLICT-01：补遗导入后语义冲突可见 | extract conflicts[] 含 topic=控制价 条目：480 vs 465、两侧 REQ id、resolution.channel=register_addendum_changes |
//! | 人工登记终裁后 expected_final_value=4650000 | 按冲突条目 a 侧 req_id 登记 value_changed → change.new_requirement 携带 4650000、指令流 DIRTY 携带新要求 |
//! | 同号异文既有检测零回归 | 澄清修改文件-3.1.1（kind=补遗）的同号冲突面照旧（≥2 条 3.1.1/3.2.1），语义面不双报同号对 |
//!
//! SKIP 纪律（#9）：corpus-A 素材不可达时 skip。

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

/// 验收 1 + 2 + 3：语义冲突可见（CONFLICT-01）+ 同号异文零回归 +
/// 人工登记终裁（expected_final_value=4650000）。
#[test]
fn corpus_a_semantic_conflict_visible_and_adjudication_flow() {
    let root = repo_root();
    let a_file = root.join("fixtures/corpus-A/files/A-招标文件.docx");
    if !a_file.is_file() {
        eprintln!("[SKIP] corpus-A 素材不可达: {}", a_file.display());
        return;
    }
    let ws = std::env::temp_dir().join(format!(
        "i179-{:?}-{:?}",
        std::process::id(),
        std::thread::current().id()
    ));
    let _ = std::fs::remove_dir_all(&ws);
    std::fs::create_dir_all(&ws).unwrap();
    let mut svc = BidService::open(&ws).unwrap().with_fs_root(root.clone());

    let pid = ok(&mut svc, "create_bid_project", json!({
        "name": "#179 语义冲突", "bid_deadline": "2026-12-31", "mode": "明标",
        "external_key": "i179-semantic-conflict",
    }))["project_id"]
        .as_str()
        .unwrap()
        .to_string();

    let import = ok(&mut svc, "import_tender_files", json!({
        "project_id": pid,
        "files": [
            { "upload_ref": "fixtures/corpus-A/files/A-招标文件.docx", "filename": "A-招标文件.docx", "kind": "招标文件" },
            { "upload_ref": "fixtures/corpus-A/files/C-补遗文件01.docx", "filename": "C-补遗文件01.docx", "kind": "补遗" },
            { "upload_ref": "fixtures/corpus-A/files/澄清修改文件-3.1.1.docx", "filename": "澄清修改文件-3.1.1.docx", "kind": "补遗" },
        ],
    }));
    assert_eq!(import["totals"]["files"].as_u64(), Some(3), "三件全导入");

    let extract = ok(&mut svc, "extract_requirements", json!({ "project_id": pid }));
    let conflicts = extract["conflicts"].as_array().cloned().unwrap_or_default();
    assert!(!conflicts.is_empty(), "冲突面必须有产出（同号 2 + 语义 ≥1）");

    // ---- 验收 3：同号异文既有检测零回归（澄清修改 3.1.1/3.2.1 ×主件）
    let same_clause: Vec<&Value> = conflicts
        .iter()
        .filter(|c| c.get("semantic").is_none())
        .collect();
    assert!(
        same_clause.len() >= 2,
        "同号异文面（既有检测）零回归——≥2 条（3.1.1/3.2.1）：{conflicts:?}"
    );
    for c in &same_clause {
        let reason = c["reason"].as_str().unwrap_or_default();
        assert!(
            reason.contains("主文件与补遗文本不一致"),
            "同号面 reason 口径不变：{reason}"
        );
    }

    // ---- 验收 1：语义冲突可见（GT CONFLICT-01——控制价 480 vs 465）
    let semantic: Vec<&Value> = conflicts
        .iter()
        .filter(|c| c.get("semantic").and_then(Value::as_bool).unwrap_or(false))
        .collect();
    let cp = semantic
        .iter()
        .find(|c| c["topic"].as_str() == Some("控制价"))
        .unwrap_or_else(|| panic!("语义面必须含 topic=控制价（GT CONFLICT-01）：{conflicts:?}"));
    let main_v = cp["main_value"].as_f64().unwrap_or(0.0);
    let ad_v = cp["addendum_value"].as_f64().unwrap_or(0.0);
    assert!(
        (main_v - 480.0).abs() < 1e-6 && (ad_v - 465.0).abs() < 1e-6,
        "GT 真值：主件 480 万 vs 补遗 465 万（实测 {main_v} vs {ad_v}）"
    );
    assert_eq!(cp["value_unit"].as_str(), Some("万元"));
    // 两侧 REQ 可定位（终裁登记的外部键）
    let a_id = cp["a"].as_str().unwrap_or_default();
    let b_id = cp["b"].as_str().unwrap_or_default();
    assert!(!a_id.is_empty() && !b_id.is_empty(), "a/b REQ id 在场");
    // 终裁面：resolution 指路人工显式登记通道（不自动改写）
    let res = &cp["resolution"];
    assert_eq!(res["rule"].as_str(), Some("补遗优先（后到有效版本）"));
    assert_eq!(res["channel"].as_str(), Some("register_addendum_changes"));
    assert_eq!(res["change_type"].as_str(), Some("value_changed"));
    assert_eq!(res["req_id"].as_str(), Some(a_id), "登记目标 = 主件侧 REQ");
    let hint = res["new_requirement_hint"].as_str().unwrap_or_default();
    assert!(hint.contains("465"), "登记素材携带补遗新值: {hint}");

    // 语义面条目的来源面（A 主件 × C 补遗——摘录真源）
    let reason = cp["reason"].as_str().unwrap_or_default();
    assert!(
        reason.contains("A-招标文件.docx") && reason.contains("C-补遗文件01.docx"),
        "reason 点名两侧来源：{reason}"
    );

    // ---- 验收 2：人工登记终裁后 expected_final_value=4650000
    // 大纲先建（register_addendum_changes 的状态窗口）
    ok(&mut svc, "build_outline", json!({ "project_id": pid }));
    // 按冲突条目的 a 侧 req_id 显式登记（人工确认语义——本测代人工执行
    // 登记动作，登记本身即「人工确认后生效」的通道行为）
    let reg = ok(&mut svc, "register_addendum_changes", json!({
        "project_id": pid,
        "changes": [{
            "change_type": "value_changed",
            "req_id": a_id,
            "old_text": "招标控制价：人民币 480 万元（含税）",
            "new_requirement": "三、招标控制价调整：招标控制价调整为人民币 465 万元（4650000 元，含税）——补遗文件01 终裁",
        }],
    }));
    let changes = reg["changes"].as_array().cloned().unwrap_or_default();
    assert_eq!(changes.len(), 1, "变更登记落账");
    let new_req_text = changes[0]["new_requirement"].as_str().unwrap_or_default();
    assert!(
        new_req_text.contains("4650000") && new_req_text.contains("465"),
        "终裁值 4650000（GT expected_final_value）随变更落账：{new_req_text}"
    );
    // 指令流在场（DIRTY/改写指令——人工登记后进入，非自动改写）
    let directives = reg["directives"].as_array().cloned().unwrap_or_default();
    assert!(
        !directives.is_empty(),
        "value_changed 登记必须进入改写指令流（终裁后下游按 465 万口径重写）"
    );
    let directives_text = format!("{directives:?}");
    assert!(
        directives_text.contains("465"),
        "指令流携带终裁新值 465：{}",
        &directives_text.chars().take(300).collect::<String>()
    );
    let _ = std::fs::remove_dir_all(&ws);
}
