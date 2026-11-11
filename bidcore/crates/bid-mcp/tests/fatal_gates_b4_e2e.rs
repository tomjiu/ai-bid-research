//! #88 审计批次 4：修复 6/7/8 在**导出路径**上的接线验收（MCP 面）。
//!
//! 与 fatal_gates_b4.rs（纯函数层）的分工：本文件证明三门在
//! `export_bid_document` 的真实调用链上点火——
//! - **门 1i（决策对账门，修复 6/F-05）**：章正文报价 vs 导出决策报价
//!   不一致 → 拒（消息含「对账」与维度键）；一致 → 放行；
//! - **门 1j（超篇幅可配置门，修复 8a/F-09）**：单叶超带超阈值 → 拒；
//!   `max_overrun_pct` 放宽 → 放行；`waive_length_overrun` 显式理由
//!   豁免 → 放行 + 豁免进 warnings 审计面；
//! - **门 1k（三件套数据缺位门，修复 7/F-06 P0-4）**：无主体信息档 +
//!   无决策字段 → 拒（投标函/身份证明/授权委托书数据缺位）；齐备 →
//!   放行；`waive_format_placeholder` 显式理由豁免 → 放行 + 审计面；
//! - **抽取健康度常驻（修复 8b/F-14）**：导出响应恒带 `extraction_health`
//!   （face/marked/regex_fallback/excluded/requirements），正则兜底文件
//!   > 0 时 warnings 提示核对通道。
//!
//! 夹具链复用 fatal_gates_e2e.rs 的 drafted_with_star_req 形态（补遗★
//! 条款 + NA 豁免隔离），另补：项目编号 REQ（投标函抬头数据源）+ 齐备
//! 主体信息档 + 齐备决策 profile。

use bid_domain::outline::OutlineSpec;
use bid_domain::party::BidderProfile;
use bid_domain::{Anchor, DomainStore, ParseStatus, ProjectStatus, Requirement};
use bid_mcp::{dispatch_with, BidService, ToolCall, ToolReply};
use serde_json::{json, Value};
use std::collections::HashMap;
use std::path::{Path, PathBuf};

fn call(svc: &mut BidService, tool: &str, args: Value) -> ToolReply {
    dispatch_with(svc, ToolCall { tool: tool.to_string(), args })
}

fn ok_result(reply: ToolReply) -> Value {
    match reply {
        ToolReply::Ok(out) => out.result,
        ToolReply::Err { error, .. } => panic!("预期成功，实际错误: {error}"),
    }
}

fn err_text(reply: &ToolReply) -> String {
    match reply {
        ToolReply::Err { error, .. } => error.to_string(),
        ToolReply::Ok(out) => panic!("预期错误，实际成功: {}", out.result),
    }
}

fn tmp_dir(tag: &str) -> PathBuf {
    let dir = std::env::temp_dir().join(format!(
        "bid-fgb4-{tag}-{}-{}",
        std::process::id(),
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_nanos(),
    ));
    let _ = std::fs::remove_dir_all(&dir);
    std::fs::create_dir_all(&dir).unwrap();
    dir
}

fn req_of(id: &str, category: &str, excerpt: &str, star: bool) -> Requirement {
    let mut params = HashMap::new();
    if star {
        params.insert("star".to_string(), serde_json::Value::Bool(true));
    }
    Requirement {
        id: id.into(),
        category: category.into(),
        clause_no: None,
        anchors: vec![Anchor {
            file: "A-招标文件.docx".into(),
            kind: "para".into(),
            locator: format!("第三章/{id}"),
            excerpt: excerpt.into(),
            block_idx: None,
            page: None,
            line: None,
        }],
        params,
        source_file: "A-招标文件.docx".into(),
    }
}

/// 项目编号 REQ（投标函抬头数据源——门 1k 的 project_no 真源）。
fn project_no_req() -> Requirement {
    let mut r = req_of(
        "REQ-0003",
        "商务要求",
        "招标公告载明项目编号：ZFCG-2026-B4",
        false,
    );
    r.params.insert(
        "model".to_string(),
        serde_json::Value::String("ZFCG-2026-B4".into()),
    );
    r
}

fn pass_all_gates(svc: &mut BidService) {
    use bid_domain::review::{Decision, Gate};
    for gate in [Gate::AddendumWaiver, Gate::MatrixApproval, Gate::OutlineApproval] {
        svc.store_mut()
            .record_review(gate, &bid_domain::TrustedPrincipal::human("b4-lead"), Decision::Approved, vec![], None)
            .unwrap();
    }
}

fn pass_pre_export_confirm(svc: &mut BidService) {
    use bid_domain::review::{Decision, Gate};
    svc.store_mut()
        .record_review(Gate::PreExportConfirm, &bid_domain::TrustedPrincipal::human("b4-lead"), Decision::Approved, vec![], None)
        .unwrap();
}

/// 齐备主体信息落盘（bidder-profile.json——三件套的数据真源）。
fn write_full_bidder_profile(dir: &Path) {
    let p = BidderProfile {
        company_name: "测试建设工程有限公司".into(),
        legal_rep: "王锐".into(),
        legal_rep_id: "110101196001011234".into(),
        legal_rep_position: "总经理".into(),
        address: "测试市测试区测试路 1 号".into(),
        agent: "李明".into(),
        agent_id: "110101198505052345".into(),
        ..Default::default()
    };
    std::fs::write(
        dir.join("bidder-profile.json"),
        serde_json::to_string(&p).unwrap(),
    )
    .unwrap();
}

/// 齐备决策 profile（MCP 参数面——bid_amount 可覆盖用于对账测试）。
fn full_profile_json(bid_amount: f64) -> Value {
    json!({
        "bid_amount": bid_amount,
        "duration_days": 180,
        "validity_days": 90,
        "deposit_amount": 70000.0,
        "legal_rep_gender": "男",
    })
}

/// 六门前置全过 + 全叶起草 + ★补遗条款 NA 豁免的服务态（门 1e 隔离——
/// 本文件的测试对象是 1i/1j/1k，不与 1e 交叉点火）。
fn drafted_ready(tag: &str) -> (BidService, String, PathBuf) {
    let dir = tmp_dir(tag);
    let mut svc = BidService::open(&dir).unwrap();
    let pid = ok_result(call(&mut svc, "create_bid_project", json!({
        "name": "#88 批4接线", "bid_deadline": "2026-12-31", "mode": "明标",
        "external_key": tag,
    })))["project_id"]
    .as_str()
    .unwrap()
    .to_string();
    svc.store_mut()
        .upsert_file("A-招标文件.docx", "招标文件", &format!("sha-{tag}"), 10, 1, 50, 0, ParseStatus::Ok, "")
        .unwrap();
    svc.set_requirements(vec![
        req_of("REQ-0001", "资格条件", "投标人须具备贰级资质（响应完备锚）", true),
        req_of("REQ-0002", "否决项", "投标函须法定代表人签字（响应完备锚）", false),
        project_no_req(),
    ])
    .unwrap();
    let _ = svc
        .prepare_outline_and_matrix(OutlineSpec { target_total_chars: 1_500, max_reqs_per_leaf: 8 })
        .unwrap();
    // 补遗★条款（零章节归属）+ star 标记（快照回环——与批次 1 夹具同法）
    let changes = svc
        .store_mut()
        .register_addendum_changes(&[bid_domain::rewrite::ChangeSpec {
            req_id: None,
            change_type: bid_domain::rewrite::ChangeType::RequirementAdded,
            old_text: String::new(),
            new_requirement: "★技术标部分采用暗标评审：正文中不得出现投标人名称，否则作否决投标处理。".into(),
            category: Some("商务要求".into()),
            clause_no: None,
            section_id: None,
            source_file_id: None,
        }])
        .unwrap();
    let star_req_id = changes[0].change.req_id.clone();
    let mut v = serde_json::to_value(svc.store().to_snapshot()).unwrap();
    let reqs = v
        .get_mut("requirements")
        .and_then(|r| r.as_array_mut())
        .expect("requirements 序列化在位");
    for r in reqs.iter_mut() {
        if r["id"].as_str() == Some(star_req_id.as_str()) {
            let mut params = r
                .get("params")
                .cloned()
                .unwrap_or_else(|| serde_json::json!({}));
            params["star"] = serde_json::Value::Bool(true);
            r["params"] = params;
        }
    }
    let snap: bid_domain::StoreSnapshot = serde_json::from_value(v).unwrap();
    *svc.store_mut() = DomainStore::restore(snap).unwrap();
    // 证据绑定（必选行响应完备）
    use bid_domain::evidence::{EvidenceKind, EvidenceSpec};
    use bid_domain::locator::EngineLocator;
    let (eid, _) = svc
        .store_mut()
        .register_evidence(EvidenceSpec {
            kind: EvidenceKind::Qualification,
            title: "贰级资质证书".into(),
            source_file: "EV-01.pdf".into(),
            source_sha256: format!("sha-ev-{tag}"),
            locator: EngineLocator::DocxParagraph {
                paragraph_index: 3,
                text_fingerprint: "fnv64:b4".into(),
            },
            fingerprint: "fnv64:b4".into(),
            valid_from: None,
            valid_until: None,
            subject_name: "某公司".into(),
            scope: "测试".into(),
            client: None,
            amount_wan: None,
            completed_on: None,
            fields: Default::default(),
            excerpt: None,
            excerpt_locator: None,
            verification_tier: None,
        })
        .unwrap();
    for rid in ["REQ-0001", "REQ-0002"] {
        svc.store_mut().bind_evidence(&eid, rid, "2026-12-31").unwrap();
    }
    let _ = svc.store_mut().build_matrix().unwrap();
    // ★条款 NA 豁免（门 1e 隔离）
    svc.store_mut()
        .set_matrix_override(
            star_req_id,
            bid_domain::matrix::ResponseStatus::NotApplicable,
            Some("聚焦批4门的隔离豁免（人工裁定）".into()),
            &bid_domain::TrustedPrincipal::human("b4-lead"),
        )
        .unwrap();
    let _ = svc.store_mut().build_matrix().unwrap();
    pass_all_gates(&mut svc);
    // 全叶起草（mock）
    let leaf_ids: Vec<String> = {
        let parents: std::collections::HashSet<String> =
            svc.store().sections().iter().filter_map(|n| n.parent_id.clone()).collect();
        svc.store()
            .sections()
            .iter()
            .filter(|n| !parents.contains(&n.id))
            .map(|n| n.id.clone())
            .collect()
    };
    assert!(!leaf_ids.is_empty());
    for sid in &leaf_ids {
        svc.draft_section(sid, None, None, None, &mut bid_tools::draft::MockGenerator).unwrap();
    }
    assert_eq!(svc.store().project().unwrap().status, ProjectStatus::Drafting);
    pass_pre_export_confirm(&mut svc);
    (svc, pid, dir)
}

/// 含指定 REQ 的叶章节 id。
fn leaf_of(svc: &BidService, req_id: &str) -> String {
    let has_child =
        |id: &str| svc.store().sections().iter().any(|n| n.parent_id.as_deref() == Some(id));
    svc.store()
        .sections()
        .iter()
        .find(|n| !has_child(&n.id) && n.requirement_ids.iter().any(|r| r == req_id))
        .map(|n| n.id.clone())
        .unwrap_or_else(|| panic!("{req_id} 未归属任何叶章节"))
}

/// 以外部生成器重写某叶正文（改稿后须重过 PreExportConfirm——#180）。
/// 正文填充到叶配额（总篇幅门 E_TOTAL_CHARS_BELOW_MIN 是硬指标——
/// 短换文会把全稿拉下限；填充句无数字无维度词，不污染门 1i 比对面）。
fn redraft_leaf(svc: &mut BidService, req_id: &str, content: &str) {
    let sid = leaf_of(svc, req_id);
    let target = svc
        .store()
        .sections()
        .iter()
        .find(|n| n.id == sid)
        .map(|n| n.target_chars)
        .unwrap_or(0);
    let filler = "本章节响应内容详实充分，逐项对应招标文件要求并给出实施说明与支撑索引。";
    let mut body = content.to_string();
    while body.chars().count() < target as usize {
        body.push('\n');
        body.push_str(filler);
    }
    svc.draft_section(
        &sid,
        None,
        None,
        None,
        &mut bid_tools::draft::ExternalGenerator { content: body },
    )
    .unwrap();
    pass_pre_export_confirm(svc);
}

// ---------------------------------------------------------------- 门 1k（修复 7 / P0-4）

/// 无主体信息档 + 无决策字段 → 门 1k 拒（三件套数据缺位 = 成品【待填】
/// 废标级——审计修复优先序第 1 位）。
#[test]
fn format_placeholder_gate_blocks_incomplete_export() {
    let (mut svc, pid, _dir) = drafted_ready("b4-fp-block");
    let reply = call(&mut svc, "export_bid_document", json!({
        "project_id": &pid, "format": "docx", "output_path": "out.docx",
    }));
    let msg = err_text(&reply);
    assert!(msg.contains("格式件"), "门 1k 点火（实得：{msg}）");
    assert!(msg.contains("投标函"), "投标函缺位指名（实得：{msg}）");
    assert!(msg.contains("法定代表人"), "身份证明缺位指名（实得：{msg}）");
    assert!(msg.contains("授权委托"), "授权委托书缺位指名（实得：{msg}）");
}

/// 齐备（主体信息档 + 决策 profile）→ 放行；抽取健康度常驻在响应
/// （regex_fallback ≥ 1——本夹具零标记）+ warnings 提示核对通道。
#[test]
fn format_placeholder_gate_passes_and_health_standing() {
    let (mut svc, pid, dir) = drafted_ready("b4-fp-pass");
    write_full_bidder_profile(&dir);
    let r = ok_result(call(&mut svc, "export_bid_document", json!({
        "project_id": &pid, "format": "docx", "output_path": "out.docx",
        "profile": full_profile_json(3_500_000.0),
    })));
    assert!(r["artifact"]["sha256"].is_string(), "齐备导出成功: {r}");
    // 修复 8b：抽取健康度常驻（结构面——face/regex_fallback/excluded/
    // requirements 四计数恒在；本夹具未走真实解析（直接 upsert 文件 +
    // REQ 注入），regex_fallback 如实为 0——真实导入链的正则兜底计数
    // 由 real_corpus 既有链覆盖）
    let h = &r["extraction_health"];
    assert!(h["face_files"].is_u64(), "face_files 计数在位: {h}");
    assert!(h["regex_fallback_files"].is_u64(), "regex_fallback 计数在位: {h}");
    assert!(h["excluded_blocks"].is_u64(), "excluded_blocks 计数在位: {h}");
    assert!(h["requirements"].as_u64().unwrap_or(0) >= 3, "REQ 计数在列: {h}");
}

/// waive_format_placeholder 显式理由 → 放行 + 豁免进 warnings 审计面。
#[test]
fn format_placeholder_waiver_exports_with_audit() {
    let (mut svc, pid, _dir) = drafted_ready("b4-fp-waive");
    let r = ok_result(call(&mut svc, "export_bid_document", json!({
        "project_id": &pid, "format": "docx", "output_path": "out.docx",
        "waive_format_placeholder": "测试场景：确认带【待填】导出（人工担责）",
    })));
    assert!(r["artifact"]["sha256"].is_string(), "显式豁免导出成功: {r}");
    let warnings = r["warnings"].as_array().cloned().unwrap_or_default();
    assert!(
        warnings
            .iter()
            .any(|w| w.as_str().unwrap_or("").contains("豁免") && w.as_str().unwrap_or("").contains("三件套")),
        "豁免进 warnings 审计面: {warnings:?}"
    );
}

// ---------------------------------------------------------------- 门 1i（修复 6 / F-05）

/// 章正文报价 3500000 vs 决策报价 3580000 → 门 1i 拒（跨面金额冲突——
/// 评标否决点）；消息指名维度键与双面位置。
#[test]
fn cross_check_gate_blocks_amount_conflict() {
    let (mut svc, pid, dir) = drafted_ready("b4-cc-block");
    write_full_bidder_profile(&dir);
    redraft_leaf(
        &mut svc,
        "REQ-0003",
        "我司投标总报价为 3500000 元，与开标一览表载明金额一致，报价唯一且不作调整。",
    );
    let reply = call(&mut svc, "export_bid_document", json!({
        "project_id": &pid, "format": "docx", "output_path": "out.docx",
        "profile": full_profile_json(3_580_000.0),
    }));
    let msg = err_text(&reply);
    assert!(msg.contains("对账"), "门 1i 点火（实得：{msg}）");
    assert!(msg.contains("投标总报价"), "维度键指名（实得：{msg}）");
    assert!(msg.contains("DECISION") || msg.contains("3500000"), "双面位置/值在列（实得：{msg}）");
}

/// 决策与章正文一致 → 放行（正面对照）。
#[test]
fn cross_check_gate_passes_consistent_decision() {
    let (mut svc, pid, dir) = drafted_ready("b4-cc-pass");
    write_full_bidder_profile(&dir);
    redraft_leaf(
        &mut svc,
        "REQ-0003",
        "我司投标总报价为 3500000 元，与开标一览表载明金额一致，报价唯一且不作调整。",
    );
    let r = ok_result(call(&mut svc, "export_bid_document", json!({
        "project_id": &pid, "format": "docx", "output_path": "out.docx",
        "profile": full_profile_json(3_500_000.0),
    })));
    assert!(r["artifact"]["sha256"].is_string(), "一致放行: {r}");
}

// ---------------------------------------------------------------- 门 1j（修复 8a / F-09）

/// 单叶超带 300%（4× 配额）→ 门 1j 拒；max_overrun_pct 放宽 → 放行；
/// waive_length_overrun 显式理由 → 放行 + 审计面。
#[test]
fn length_overrun_gate_blocks_and_configurable_and_waivable() {
    let (mut svc, pid, dir) = drafted_ready("b4-len-block");
    write_full_bidder_profile(&dir);
    // REQ-0001 叶超带：正文 = 4 × 配额（filler 句无数字无引用锚——
    // 不污染门 1i 比对面）
    let sid = leaf_of(&svc, "REQ-0001");
    let target = svc
        .store()
        .sections()
        .iter()
        .find(|n| n.id == sid)
        .map(|n| n.target_chars)
        .unwrap();
    assert!(target > 0, "配额在位（实得 {target}）");
    let unit = "本章节响应内容详实充分，逐项对应招标文件要求并给出实施说明。";
    let content = unit.repeat((target as usize * 4 / unit.chars().count()) + 1);
    redraft_leaf(&mut svc, "REQ-0001", &content);

    // 默认阈值 50% → 拒
    let reply = call(&mut svc, "export_bid_document", json!({
        "project_id": &pid, "format": "docx", "output_path": "out.docx",
        "profile": full_profile_json(3_500_000.0),
    }));
    let msg = err_text(&reply);
    assert!(msg.contains("超篇幅"), "门 1j 点火（实得：{msg}）");

    // 阈值放宽（+10000% = 实质停用）→ 放行（可配置语义）
    let r = ok_result(call(&mut svc, "export_bid_document", json!({
        "project_id": &pid, "format": "docx", "output_path": "out2.docx",
        "profile": full_profile_json(3_500_000.0),
        "max_overrun_pct": 10000,
    })));
    assert!(r["artifact"]["sha256"].is_string(), "阈值放宽放行: {r}");

    // 显式理由豁免 → 放行 + 审计面
    let r = ok_result(call(&mut svc, "export_bid_document", json!({
        "project_id": &pid, "format": "docx", "output_path": "out3.docx",
        "profile": full_profile_json(3_500_000.0),
        "waive_length_overrun": "测试场景：确认超带导出（人工担责）",
    })));
    assert!(r["artifact"]["sha256"].is_string(), "显式豁免导出成功: {r}");
    let warnings = r["warnings"].as_array().cloned().unwrap_or_default();
    assert!(
        warnings
            .iter()
            .any(|w| w.as_str().unwrap_or("").contains("豁免") && w.as_str().unwrap_or("").contains("超篇幅")),
        "豁免进 warnings 审计面: {warnings:?}"
    );
}
