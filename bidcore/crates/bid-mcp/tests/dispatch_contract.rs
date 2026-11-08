//! M0 骨架契约测试：**未实现 ≠ 成功**。
//!
//! 本文件存在的唯一目的：防止"骨架期工具返回空成功"这种假绿。
//! 每个未落地工具都必须被断言为 `UNIMPLEMENTED_INTERNAL`，而不是 ok=true。

use bid_mcp::{dispatch, dispatch_json, schema::ToolCall, TOOL_NAMES};
use serde_json::json;

fn call(tool: &str, args: serde_json::Value) -> bid_mcp::ToolReply {
    dispatch(ToolCall {
        tool: tool.to_string(),
        args,
    })
}

#[test]
fn tool_names_are_the_contract_twenty() {
    // V3-5（S-4）：8+1+2 = 11；#42 阶段 10 增 save_version = 12；
    // #68 阶段 2 增 check_bid_quality = 13；
    // #80 第三批 MCP 补齐增 4（build_outline / register_evidence /
    // bind_evidence / record_review_gate）= 17（G1/G2/G3——外部 Agent
    // 纯 MCP 驱动全链）；
    // #100 任务 3 增 3（score_price / score_section / score_document）
    // = 20（B1 价格分 + B2 自评的 MCP 接线——「能得几分、该报多少价」）；
    // #184 增 1（record_addendum_waiver——补遗分级阻塞的逐件人工确认）
    // = 21
    // #219 增 3（get_document_chunks / submit_block_marks /
    // get_coverage_report——全块覆盖：Agent 区间标记 + 引擎覆盖检查）= 24；
    // #226 增 1（set_matrix_override——否决项死锁的人工出口）= 25；
    // #243 增 1（recover_validating_state——历史异常态恢复出口）= 26
assert_eq!(TOOL_NAMES.len(), 50, "工具面必须恰为 44 个（21 + #219 全块覆盖三工具 + #226 否决项死锁出口 + #243 恢复出口 + #254 分段三工具 + #279 行协议发现面 + #287 篇幅档位推荐 + #285① ★漏标检测 + #285② 块级双向索引三工具 + #319 补遗后增量重写两工具 + #321 RT 生命周期/分工/重开/参数应答七工具 + #315 业绩库四工具）");
    for name in TOOL_NAMES {
        assert!(!name.is_empty());
    }
}

#[test]
fn unknown_tool_is_typed_not_found() {
    match call("not_a_tool", json!({})) {
        bid_mcp::ToolReply::Err { error, .. } => assert_eq!(error.code(), "E_NOTFOUND"),
        bid_mcp::ToolReply::Ok(o) => panic!("未知工具不得成功: {o:?}"),
    }
}

#[test]
fn unimplemented_tools_return_typed_unimplemented_not_ok() {
    // #145 任务 1：search_evidence 接线后清单**清空**——全部 20 工具实装
    // （骨架纪律保留：未来新增工具未接线时回到此清单，防止骨架与实现脱钩）。
    // 此前 B-1 落地 create/import；B5 落地 extract/matrix；#59 阶段 1-3 落地
    // draft/export/validate——不在此清单。
    let unimplemented: [&str; 0] = [];
    for tool in unimplemented {
        match call(tool, json!({})) {
            bid_mcp::ToolReply::Err { error, .. } => {
                assert_eq!(
                    error.code(),
                    "UNIMPLEMENTED_INTERNAL",
                    "{tool} 必须返回 UNIMPLEMENTED_INTERNAL（骨架期不得假装成功）"
                );
            }
            bid_mcp::ToolReply::Ok(o) => panic!("{tool} 骨架期不得成功，实际: {o:?}"),
        }
    }
}

#[test]
fn implemented_tool_returns_state_and_allowed_tools() {
    match call("get_bid_project_state", json!({"project_status": "DRAFT"})) {
        bid_mcp::ToolReply::Ok(out) => {
            assert_eq!(out.result["status"], "DRAFT");
            let allowed = out.result["allowed_next_tools"].as_array().unwrap();
            assert!(allowed.iter().any(|v| v == "create_bid_project"));
            assert_eq!(out.result["terminal"], false);
        }
        bid_mcp::ToolReply::Err { error, .. } => panic!("已落地工具不得失败: {error}"),
    }
}

#[test]
fn implemented_tool_rejects_bad_status_typed() {
    match call("get_bid_project_state", json!({"project_status": "NOT_A_STATUS"})) {
        bid_mcp::ToolReply::Err { error, .. } => assert_eq!(error.code(), "E_UNPROCESSABLE"),
        bid_mcp::ToolReply::Ok(o) => panic!("非法状态必须被拒: {o:?}"),
    }
}

#[test]
fn terminal_state_is_marked() {
    match call("get_bid_project_state", json!({"project_status": "EXPORTED"})) {
        bid_mcp::ToolReply::Ok(out) => assert_eq!(out.result["terminal"], true),
        bid_mcp::ToolReply::Err { error, .. } => panic!("{error}"),
    }
}

#[test]
fn json_roundtrip_failure_is_typed() {
    let out = dispatch_json("{ this is not json");
    let v: serde_json::Value = serde_json::from_str(&out).unwrap();
    assert_eq!(v["ok"], false);
    assert_eq!(v["error"]["code"], "E_UNPROCESSABLE");
}

#[test]
fn tools_schema_lists_all_twenty() {
    let v = bid_mcp::tools_schema();
    let arr = v["tools"].as_array().unwrap();
assert_eq!(arr.len(), 50, "tools/list 必须列出全部 50 个工具");
    let implemented: Vec<&str> = arr
        .iter()
        .filter(|t| t["implemented"] == true)
        .map(|t| t["name"].as_str().unwrap())
        .collect();
    // B-1：create/import；B5：extract/matrix；V3-5（S-4）：list_evidence/list_tasks；
    // #59 阶段 1+2：draft_response_section / export_bid_document；
    // #68 阶段 2：check_bid_quality；
    // + get_bid_project_state（TOOL_NAMES 声明序）——工具落地时本清单同步
    // 收缩，防骨架与实现脱钩；
    // #100 任务 3：score_price / score_section / score_document（B1/B2 接线）；
    // #145 任务 1：search_evidence 接线 + save_version 补登（此前 is_implemented
    // 漏登致 tools/list 误报 false——#145 测试面抓出，如实登记）→ 全部 20 实装；
    // #184：record_addendum_waiver（补遗分级阻塞的逐件人工确认）→ 21 实装；
    // #219 增 3 覆盖工具 → 24 实装；
    // #226：set_matrix_override（否决项死锁出口）→ 25 实装；
    // #243：recover_validating_state（历史异常态恢复出口）→ 26 实装；
    // #285② 块级双向索引三工具 → 34 实装（只读）
    assert_eq!(
        implemented,
        vec![
            "create_bid_project",
            "import_tender_files",
            "extract_requirements",
            "get_compliance_matrix",
            "list_evidence",
            "list_tasks",
            "search_evidence",
            "draft_response_section",
            "validate_bid_document",
            "export_bid_document",
            "get_bid_project_state",
            "save_version",
            "check_bid_quality",
            "build_outline",
            "register_evidence",
            "bind_evidence",
            "record_review_gate",
            "record_addendum_waiver",
            "score_price",
            "score_section",
            "score_document",
            // #219 全块覆盖三工具
            "get_document_chunks",
            "submit_block_marks",
            "get_coverage_report",
            // #285 ① ★漏标检测（只读实装）
            "get_star_coverage",
            // #285 ② 块级双向索引三工具（只读实装）
            "get_requirement_provenance",
            "get_block_requirements",
            "get_annotation_overlay",
            // #318 评分细则逐条响应覆盖检查（只读实装）
            "check_scoring_coverage",
            // #226 层 1：否决项死锁的人工出口
            "set_matrix_override",
            // #243：历史异常态（VALIDATING+缺章）的受支持恢复出口
            "recover_validating_state",
            // #254 章节级增量写入三工具
            "append_section_segment",
            "rewrite_section_segment",
            "list_section_segments",
            // #319 补遗后增量重写两工具
            "register_addendum_changes",
            "rewrite_section_partial",
            // #287 篇幅档位推荐
            "recommend_length_profile",
            // #316 多标段/多包投标——按包发现面
            "list_packages",
            // #279 行协议发现面
            "list_tools",
            // #321（A-23）：RT 生命周期 + 分工 + 章节重开 + 参数应答工具族
            "assign_revision",
            "advance_revision",
            "complete_revision",
            "batch_task",
            "advance_task",
            "reopen_section",
            "set_param_responses",
            // #315 业绩材料库四工具（perf_tools.rs——登记/列表/推荐/写入）
            "register_performance",
            "list_performance",
            "recommend_performance",
            "write_performance_section",
        ]
    );
    // 描述面：新工具不得是 unknown（describe 遗漏即挂）
    for t in arr.iter().filter(|t| t["name"].as_str().unwrap().starts_with("score_")) {
        assert_ne!(t["description"], "unknown", "score_* 描述必须在场: {t}");
    }
    let ra = arr.iter().find(|t| t["name"] == "record_addendum_waiver").unwrap();
    assert_ne!(ra["description"], "unknown", "record_addendum_waiver 描述必须在场: {ra}");
    let rv = arr.iter().find(|t| t["name"] == "recover_validating_state").unwrap();
    assert_ne!(rv["description"], "unknown", "recover_validating_state 描述必须在场: {rv}");
    for t in arr.iter().filter(|t| t["name"].as_str().unwrap().starts_with("append_section")
        || t["name"].as_str().unwrap().starts_with("rewrite_section")
        || t["name"].as_str().unwrap().starts_with("list_section")
        || t["name"].as_str().unwrap().starts_with("register_addendum")) {
        assert_ne!(t["description"], "unknown", "#254/#319 分段与增量重写工具描述必须在场: {t}");
    }
    let lt = arr.iter().find(|t| t["name"] == "list_tools").unwrap();
    assert_ne!(lt["description"], "unknown", "#279 list_tools 描述必须在场: {lt}");
}

// ---------------------------------------------------------------- #522（C-22）：工具面二分不变量

/// 工具面必须二分：`TOOL_NAMES` == 各状态 allowed_tools 并集 ∪ UNGATED_TOOLS，
/// 且两集不相交。
///
/// 防的是 C-22 的复发形态：新工具接线时不设状态门（合法——如 #285② 对账
/// 三工具），但也没登记进 UNGATED_TOOLS → get_bid_project_state 的
/// allowed_next_tools/ungated_tools 两字段都看不到它 → Agent 对「当前可调
/// 面」的回显出现缺口。本测试与 tool-surface 的派生面纪律互补：
/// tool-surface 管「加工具同步派生面」，本测试管「加工具登记门归属」。
#[test]
fn tool_names_partition_into_gated_and_ungated() {
    use bid_domain::{ProjectStatus, UNGATED_TOOLS};
    use std::collections::BTreeSet;

    let statuses = [
        ProjectStatus::Draft,
        ProjectStatus::FilesImported,
        ProjectStatus::RequirementsExtracted,
        ProjectStatus::MatrixReady,
        ProjectStatus::EvidenceBound,
        ProjectStatus::Drafting,
        ProjectStatus::Validating,
        ProjectStatus::Reviewing,
        ProjectStatus::ReadyToExport,
        ProjectStatus::Exported,
    ];
    let gated: BTreeSet<&str> = statuses
        .iter()
        .flat_map(|s| s.allowed_tools().iter().copied())
        .collect();
    let ungated: BTreeSet<&str> = UNGATED_TOOLS.iter().copied().collect();

    // ① 不相交：登记进 UNGATED_TOOLS 的工具不得同时出现在任何状态门表
    //    （否则 guard_tool 语义与「无门」声明矛盾）。
    let overlap: Vec<&str> = gated.intersection(&ungated).copied().collect();
    assert!(
        overlap.is_empty(),
        "UNGATED_TOOLS 与状态门表重叠（矛盾登记）: {overlap:?}"
    );

    // ② 全覆盖：每个 TOOL_NAMES 工具要么进某状态门表、要么登记无门集。
    //    漏登即回显缺口（C-22 原始形态）。
    let union: BTreeSet<&str> = gated.union(&ungated).copied().collect();
    let all: BTreeSet<&str> = TOOL_NAMES.iter().copied().collect();
    let missing: Vec<&str> = all.difference(&union).copied().collect();
    assert!(
        missing.is_empty(),
        "以下工具既不在任何状态门表也不在 UNGATED_TOOLS——回显缺口，请登记归属: {missing:?}"
    );

    // ③ 无幽灵：门表/无门集里的名字必须是真工具（防拼写错成永久死条目）。
    let ghosts: Vec<&str> = union.difference(&all).copied().collect();
    assert!(
        ghosts.is_empty(),
        "门表/无门集存在 TOOL_NAMES 之外的幽灵名: {ghosts:?}"
    );

    // ④ 数量对账：44 = 状态门并集 + 无门集（演进时同步改这里——与
    //    tool_names_are_the_contract 的计数断言同款纪律）。
    assert_eq!(all.len(), 50);
    assert_eq!(gated.len() + ungated.len(), 50, "门表并集 {} + 无门 {} 应 == 50", gated.len(), ungated.len());
}

/// ungated_tools 回显在位且与状态无关（#522 验收：任何状态下值一致）。
#[test]
fn project_state_echoes_ungated_tools() {
    for st in ["DRAFT", "FILES_IMPORTED", "MATRIX_READY", "DRAFTING", "EXPORTED"] {
        match call("get_bid_project_state", json!({ "project_status": st })) {
            bid_mcp::ToolReply::Ok(out) => {
                let ungated = out.result["ungated_tools"].as_array().unwrap();
                let names: Vec<&str> =
                    ungated.iter().map(|v| v.as_str().unwrap()).collect();
                assert_eq!(
                    names,
                    bid_domain::UNGATED_TOOLS.to_vec(),
                    "{st} 态 ungated_tools 应与单一真源一致"
                );
                // 回显与状态门不重叠（同一份不变量的运行面复证）
                let allowed: Vec<&str> = out.result["allowed_next_tools"]
                    .as_array()
                    .unwrap()
                    .iter()
                    .map(|v| v.as_str().unwrap())
                    .collect();
                for t in &names {
                    assert!(!allowed.contains(t), "{st} 态 {t} 不应同时出现在两清单");
                }
            }
            bid_mcp::ToolReply::Err { error, .. } => panic!("{st} 态查询失败: {error}"),
        }
    }
}
