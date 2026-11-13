//! map_scoring_item_tool.rs —— #153：评分项 → 章节显式映射的 MCP 写面。
//!
//! 缺陷形态（#113 F5，PR #149）：评分项 REQ → 大纲章节显式映射此前只有
//! 服务层 API（upsert_scoring_mapping，收官测试进程内直调）；MCP 面无写
//! 入口 → 外部 Agent 纯 MCP 驱动评分项悬空 → 门 1h 必豁免（#149 waive
//! 理由在案）→ 评分项响应面系统性缺失（真实验收 28/31 无正文覆盖）。
//!
//! 修法：新增 MCP 工具 `map_scoring_item`（req_id + section_id +
//! weight_share + anchor[+evidence_refs]）包装域层 upsert_scoring_mapping
//!（AgentSubmitted 落账）；TOOL_NAMES/schema/dispatch/状态门/契约五面同步
//! （tool-surface --write 派生面重生成）。
//!
//! 验收闭环：纯 MCP 面 map_scoring_item 逐项映射 → check_scoring_coverage
//! unmapped=0 → 门 1h 数据源（unmapped_scoring_findings）清零——零豁免
//! 自然放行。

use bid_domain::outline::OutlineSpec;
use bid_mcp::{dispatch_with, BidService, ToolCall, ToolReply};
use serde_json::{json, Value};

fn call(svc: &mut BidService, tool: &str, args: Value) -> ToolReply {
    dispatch_with(svc, ToolCall { tool: tool.to_string(), args })
}

fn ok_result(reply: ToolReply) -> Value {
    match reply {
        ToolReply::Ok(out) => out.result,
        ToolReply::Err { error, .. } => panic!("预期成功，实际错误: {error}"),
    }
}

fn err_text(reply: ToolReply) -> String {
    match reply {
        ToolReply::Err { error, .. } => error.to_string(),
        ToolReply::Ok(out) => panic!("预期拒绝，实际成功: {}", out.result),
    }
}

fn score_req(id: &str, excerpt: &str, score: f64) -> bid_domain::Requirement {
    use bid_domain::{Anchor, Requirement};
    let mut params = std::collections::HashMap::new();
    params.insert("score".to_string(), serde_json::json!(score));
    Requirement {
        id: id.into(),
        category: "评分项".into(),
        clause_no: None,
        anchors: vec![Anchor {
            file: "A-招标文件.docx".into(),
            kind: "para".into(),
            locator: format!("第四章 评标办法/{id}"),
            excerpt: excerpt.into(),
            block_idx: None,
            page: None,
            line: None,
        }],
        params,
        source_file: "A-招标文件.docx".into(),
    }
}

fn body_req(id: &str, excerpt: &str) -> bid_domain::Requirement {
    use bid_domain::{Anchor, Requirement};
    Requirement {
        id: id.into(),
        category: "技术参数".into(),
        clause_no: None,
        anchors: vec![Anchor {
            file: "A-招标文件.docx".into(),
            kind: "para".into(),
            locator: format!("第五章 技术要求/{id}"),
            excerpt: excerpt.into(),
            block_idx: None,
            page: None,
            line: None,
        }],
        params: Default::default(),
        source_file: "A-招标文件.docx".into(),
    }
}

/// 夹具：1 评分项 + N 正文叶（评分项不进正文 #126——叶绑定走技术参数
/// REQ）。返回 (svc, pid, 评分项 id, 叶 id 清单)。
fn svc_scoring_project(tag: &str, body_reqs: usize) -> (BidService, String, String, Vec<String>) {
    let mut svc = BidService::new();
    let pid = ok_result(call(&mut svc, "create_bid_project", json!({
        "name": "153-评分映射测试", "bid_deadline": "2026-12-31", "mode": "明标", "external_key": tag,
    })))["project_id"].as_str().unwrap().to_string();
    svc.store_mut().upsert_file(
        "A-招标文件.docx", "招标文件", "sha-153", 10, 1, 50, 0,
        bid_domain::ParseStatus::Ok, "",
    ).unwrap();
    let mut reqs = vec![score_req(
        "REQ-0001",
        "4.1 技术方案完整性与针对性 20 分（方案须覆盖架构与选型）",
        20.0,
    )];
    for i in 0..body_reqs {
        reqs.push(body_req(&format!("REQ-{i:04}"), &format!("5.{i} 核心设备须满足现场运行要求条款示例 {i}")));
    }
    svc.set_requirements(reqs).unwrap();
    svc.prepare_outline_and_matrix(OutlineSpec {
        target_total_chars: 300 * body_reqs as u32,
        max_reqs_per_leaf: 1,
    }).unwrap();
    let parents: std::collections::HashSet<&str> = svc.store().sections().iter()
        .filter_map(|n| n.parent_id.as_deref()).collect();
    let leaves: Vec<String> = svc.store().sections().iter()
        .filter(|n| !parents.contains(&n.id[..]))
        .map(|n| n.id.clone()).collect();
    assert!(!leaves.is_empty(), "正文 REQ 应产出 ≥1 叶");
    (svc, pid, "REQ-0001".into(), leaves)
}

fn map_args(pid: &str, req_id: &str, section_id: &str, weight: f64) -> Value {
    json!({
        "project_id": pid,
        "req_id": req_id,
        "section_id": section_id,
        "weight_share": weight,
        "anchor": {
            "file": "A-招标文件.docx",
            "kind": "para",
            "locator": "第四章 评标办法",
            "excerpt": "4.1 技术方案完整性与针对性 20 分（方案须覆盖架构与选型）",
        },
    })
}

/// 验收 1（红核 + 闭环）：纯 MCP 面 map_scoring_item 逐项映射 →
/// check_scoring_coverage unmapped=0 → 门 1h 数据源清零（零豁免放行）。
#[test]
fn mcp_map_face_completes_coverage_loop() {
    let (mut svc, pid, sreq, leaves) = svc_scoring_project("v153-loop", 1);
    let leaf = &leaves[0];

    // 前置事实：评分项未映射——coverage unmapped=1，门 1h 数据源非空
    let cov0 = ok_result(call(&mut svc, "check_scoring_coverage", json!({ "project_id": &pid })));
    assert_eq!(cov0["summary"]["criteria_unmapped"], json!(1), "映射前应见 1 条未映射：{cov0}");
    assert!(
        !bid_tools::validate::unmapped_scoring_findings(svc.store()).is_empty(),
        "映射前门 1h 数据源应非空（unmapped_scoring_findings）"
    );

    // MCP 写面映射（#153 红钉：此前工具不存在）
    let m = ok_result(call(&mut svc, "map_scoring_item", map_args(&pid, &sreq, leaf, 1.0)));
    assert!(m["mapping"]["id"].as_str().unwrap().starts_with("SM-"), "映射须签发 SM-xxxx：{m}");
    assert_eq!(m["mapping"]["created_from"], json!("AGENT_SUBMITTED"), "MCP 面来源恒 AGENT_SUBMITTED：{m}");
    assert_eq!(m["mapping"]["weight_share"], json!(1.0));

    // 覆盖闭环：unmapped=0 + 门 1h 数据源清零
    let cov1 = ok_result(call(&mut svc, "check_scoring_coverage", json!({ "project_id": &pid })));
    assert_eq!(cov1["summary"]["criteria_unmapped"], json!(0), "映射后 unmapped 须归零：{cov1}");
    assert!(
        bid_tools::validate::unmapped_scoring_findings(svc.store()).is_empty(),
        "映射后门 1h 数据源须清零（零豁免自然放行）"
    );
}

/// 验收 2（校验面透传——域层 fail-loud 不吞错）：weight 越界 / 非评分类
/// 别 / 幽灵章节 / 幽灵证据 / anchor 缺失 / 状态门外——各面响亮拒。
#[test]
fn map_scoring_item_validation_faces() {
    let (mut svc, pid, sreq, leaves) = svc_scoring_project("v153-vals", 2);
    let leaf_a = leaves[0].clone();
    let leaf_b = leaves[1].clone();

    let e1 = err_text(call(&mut svc, "map_scoring_item", map_args(&pid, &sreq, &leaf_a, 1.5)));
    assert!(e1.contains("越界"), "weight 越界须响亮拒：{e1}");
    let e2 = err_text(call(&mut svc, "map_scoring_item", map_args(&pid, "REQ-0000", &leaf_a, 1.0)));
    assert!(e2.contains("仅评分项") || e2.contains("不存在"), "非评分类别须拒：{e2}");
    let e3 = err_text(call(&mut svc, "map_scoring_item", map_args(&pid, &sreq, "SEC-9999", 1.0)));
    assert!(e3.contains("不存在"), "幽灵章节须拒：{e3}");
    let mut ghost = map_args(&pid, &sreq, &leaf_a, 1.0);
    ghost["evidence_refs"] = json!(["EV-9999"]);
    let e4 = err_text(call(&mut svc, "map_scoring_item", ghost));
    assert!(e4.contains("EV-9999"), "幽灵证据须拒：{e4}");
    let mut no_anchor = map_args(&pid, &sreq, &leaf_a, 1.0);
    no_anchor.as_object_mut().unwrap().remove("anchor");
    let e5 = err_text(call(&mut svc, "map_scoring_item", no_anchor));
    assert!(e5.contains("anchor"), "anchor 缺失须拒（映射依据溯源面）：{e5}");

    // 状态门：Draft 态（无纲）拒——映射面 DRAFTING+ 开放
    let mut fresh = BidService::new();
    let pid2 = ok_result(call(&mut fresh, "create_bid_project", json!({
        "name": "153-早态", "bid_deadline": "2026-12-31", "mode": "明标", "external_key": "v153-early",
    })))["project_id"].as_str().unwrap().to_string();
    let e6 = err_text(call(&mut fresh, "map_scoring_item", map_args(&pid2, &sreq, &leaf_a, 1.0)));
    assert!(e6.contains("E_STATE"), "无纲早态须状态门拒：{e6}");

    // 聚合不变量（#224）：同评分项跨两节 0.7+0.7 → 拒；0.7+0.3 → 过
    ok_result(call(&mut svc, "map_scoring_item", map_args(&pid, &sreq, &leaf_a, 0.7)));
    let e7 = err_text(call(&mut svc, "map_scoring_item", map_args(&pid, &sreq, &leaf_b, 0.7)));
    assert!(e7.contains("份额合计") || e7.contains("1.0"), "份额合计超限须拒：{e7}");
    ok_result(call(&mut svc, "map_scoring_item", map_args(&pid, &sreq, &leaf_b, 0.3)));
}

/// 验收 3（幂等更新面）：同 (req, section) 键重提 = 更新非身份字段，
/// 不追加新账本行、不重复计数。
#[test]
fn map_scoring_item_idempotent_update() {
    let (mut svc, pid, sreq, leaves) = svc_scoring_project("v153-idem", 1);
    let leaf = &leaves[0];
    let m1 = ok_result(call(&mut svc, "map_scoring_item", map_args(&pid, &sreq, leaf, 1.0)));
    let m2 = ok_result(call(&mut svc, "map_scoring_item", map_args(&pid, &sreq, leaf, 0.5)));
    assert_eq!(
        m1["mapping"]["id"], m2["mapping"]["id"],
        "同键重提须命中同一 SM-id（更新非追加）：{m1} vs {m2}"
    );
    assert_eq!(m2["mapping"]["weight_share"], json!(0.5), "份额更新生效：{m2}");
    assert_eq!(svc.store().scoring_mappings().len(), 1, "账本不得追加重复行");
}
