//! #88 审计 F-01/F-02 收口：致命项门在**导出路径**上的接线验收（MCP 面）。
//!
//! 与 bid-tools/tests/fatal_gap_gates.rs（findings 纯函数层）的分工：
//! 本文件证明门在 `export_bid_document` 的真实调用链上点火——
//! - **门 1e（★响应门）**：未响应★ REQ → 导出被拒（E_UNPROCESSABLE，
//!   消息含「★响应门」）；三要件人工豁免后放行；
//! - **门 1f（暗标联动门）**：mode=暗标 + 未启用暗标 → 拒（「暗标」）；
//!   mode=明标 + 暗标条款在场 → 导出成功 + W_DARK_BID_UNDECLARED 告警
//!   （既有 corpus-A 明标导出的兼容面——告警不拦）。
//!
//! 夹具链复用 export_tool.rs 的 svc_drafted 形态（合成 REQ + 真实链路过
//! 六前置门）。star_missing 子面 b（漏标豁免）的 parsed 注入面无公开 API
//! ——由 fatal_gap_gates.rs 单测覆盖（star_gate_findings 同源真源）。

use bid_domain::outline::OutlineSpec;
use bid_domain::{Anchor, DomainStore, ParseStatus, ProjectStatus, Requirement};
use bid_mcp::{dispatch_with, BidService, ToolCall, ToolReply};
use serde_json::{json, Value};
use std::collections::HashMap;
use std::path::PathBuf;

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
        "bid-fg88-{tag}-{}-{}",
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

fn star_req(id: &str, category: &str, excerpt: &str) -> Requirement {
    let mut params = HashMap::new();
    params.insert("star".to_string(), serde_json::Value::Bool(true));
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

fn pass_all_gates(svc: &mut BidService) {
    use bid_domain::review::{Decision, Gate};
    for gate in [Gate::AddendumWaiver, Gate::MatrixApproval, Gate::OutlineApproval] {
        svc.store_mut()
            .record_review(gate, &bid_domain::TrustedPrincipal::human("fg-lead"), Decision::Approved, vec![], None)
            .unwrap();
    }
}

/// PreExportConfirm——**正文定稿后**过（#180 内容摘要绑定：过门后改正文
/// 会被导出门拒「请重新审核」；起草永远在门 1b 之前完成）。
fn pass_pre_export_confirm(svc: &mut BidService) {
    use bid_domain::review::{Decision, Gate};
    svc.store_mut()
        .record_review(Gate::PreExportConfirm, &bid_domain::TrustedPrincipal::human("fg-lead"), Decision::Approved, vec![], None)
        .unwrap();
}

/// 六门前置全过 + 全叶起草的服务态。★暗标双性条款（REQ-0003）走**补遗
/// 注入**（section_id=None——零章节归属）：挂章节的 REQ 会被正文实写判
/// RESPONDED（#241 文本事实口径），门 1e 就无从点火——无归属正是
/// E_STAR_UNRESPONDED 的真实场景（补遗新增★条款忘了安排响应章节）。
/// star 标记面：补遗登记不产 params.star，用快照回环补（submit_block_marks
/// 的写入等价）。
fn drafted_with_star_req(tag: &str, mode: &str) -> (BidService, String, PathBuf) {
    let dir = tmp_dir(tag);
    let mut svc = BidService::open(&dir).unwrap();
    let pid = ok_result(call(&mut svc, "create_bid_project", json!({
        "name": "#88 门接线", "bid_deadline": "2026-12-31", "mode": mode,
        "external_key": tag,
    })))["project_id"]
    .as_str()
    .unwrap()
    .to_string();
    svc.store_mut()
        .upsert_file("A-招标文件.docx", "招标文件", &format!("sha-{tag}"), 10, 1, 50, 0, ParseStatus::Ok, "")
        .unwrap();
    // REQ-0001/0002 响应完备（过门 1a-1d 的主体）
    svc.set_requirements(vec![
        star_req("REQ-0001", "资格条件", "投标人须具备贰级资质（响应完备锚）"),
        star_req("REQ-0002", "否决项", "投标函须法定代表人签字（响应完备锚）"),
    ])
    .unwrap();
    let _ = svc
        .prepare_outline_and_matrix(OutlineSpec { target_total_chars: 1_500, max_reqs_per_leaf: 8 })
        .unwrap();
    // ★+暗标双性条款：补遗登记（零章节归属——暗标评审类实务上就是实质性条款，
    // 一夹具服务双门测试）
    let changes = svc
        .store_mut()
        .register_addendum_changes(&[bid_domain::rewrite::ChangeSpec {
            req_id: None,
            change_type: bid_domain::rewrite::ChangeType::RequirementAdded,
            old_text: String::new(),
            new_requirement: "★技术标部分采用暗标评审：正文中不得出现投标人名称，否则作否决投标处理。".into(),
            category: Some("商务要求".into()),
            clause_no: None,
            section_id: None, // 零章节影响——只进条款集与矩阵
            source_file_id: None,
        }])
        .unwrap();
    assert_eq!(changes.len(), 1, "补遗登记一条新增");
    let star_req_id = changes[0].change.req_id.clone();
    // 标记面等价：快照 → params.star=true → 整库替换（store_mut 是 &mut DomainStore）
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
    // 证据绑定 REQ-0001/0002（必选行响应）
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
                text_fingerprint: "fnv64:fg".into(),
            },
            fingerprint: "fnv64:fg".into(),
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
    pass_all_gates(&mut svc);
    // 全叶起草（mock 生成器）
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
    // PreExportConfirm 在定稿后（#180——起草在过门 1b 之前完成）
    pass_pre_export_confirm(&mut svc);
    (svc, pid, dir)
}

/// 补遗注入的★条款 id（豁免面用——id 由域层签发，不能硬编码）。
fn star_req_id_of(svc: &BidService) -> String {
    svc.store()
        .requirements()
        .iter()
        .find(|r| {
            r.params.get("star").and_then(|v| v.as_bool()) == Some(true)
                && r.anchors.is_empty() // 补遗新增（无锚）
        })
        .map(|r| r.id.clone())
        .expect("补遗★条款在位")
}

// ---------------------------------------------------------------- 门 1e

/// ★未响应（非必选类——门 1a 放行）→ 门 1e 拒；导出路径真实点火。
#[test]
fn star_gate_blocks_export_through_mcp() {
    let (mut svc, pid, _dir) = drafted_with_star_req("fg-star-block", "明标");
    let star_id = star_req_id_of(&svc);
    let reply = call(&mut svc, "export_bid_document", json!({
        "project_id": &pid, "format": "docx", "output_path": "out.docx",
    }));
    let msg = err_text(&reply);
    assert!(msg.contains("★响应门"), "门 1e 点火（实得：{msg}）");
    assert!(msg.contains(&star_id), "指名未响应条款 {star_id}（实得：{msg}）");
}

/// 三要件人工豁免（set_matrix_override）→ 门 1e 放行，导出成功。
#[test]
fn star_gate_legit_na_exemption_exports() {
    let (mut svc, pid, _dir) = drafted_with_star_req("fg-star-na", "明标");
    let star_id = star_req_id_of(&svc);
    svc.store_mut()
        .set_matrix_override(
            star_id.clone(),
            bid_domain::matrix::ResponseStatus::NotApplicable,
            Some("该★条款针对特定检测环境，本项目不适用（人工裁定）".into()),
            &bid_domain::TrustedPrincipal::human("fg-lead"),
        )
        .unwrap();
    let _ = svc.store_mut().build_matrix().unwrap();
    pass_pre_export_confirm(&mut svc); // #474：覆写动了计分面——重过门再导
    let reply = call(&mut svc, "export_bid_document", json!({
        "project_id": &pid, "format": "docx", "output_path": "out.docx",
    }));
    let r = ok_result(reply);
    assert!(r["artifact"]["sha256"].is_string(), "豁免后导出成功: {r}");
}

// ---------------------------------------------------------------- 门 1f

/// mode=暗标 + 导出未启用暗标 → 门 1f 拒（自相矛盾 fail-closed）。
#[test]
fn dark_bid_gate_blocks_light_export_when_mode_dark() {
    let (mut svc, pid, _dir) = drafted_with_star_req("fg-dark-block", "暗标");
    // ★ REQ 先豁免（隔离变量——本测只锁门 1f）
    let star_id = star_req_id_of(&svc);
    svc.store_mut()
        .set_matrix_override(
            star_id.clone(),
            bid_domain::matrix::ResponseStatus::NotApplicable,
            Some("聚焦暗标门的隔离豁免（人工裁定）".into()),
            &bid_domain::TrustedPrincipal::human("fg-lead"),
        )
        .unwrap();
    let _ = svc.store_mut().build_matrix().unwrap();
    pass_pre_export_confirm(&mut svc); // #474：覆写动了计分面——重过门再导
    let reply = call(&mut svc, "export_bid_document", json!({
        "project_id": &pid, "format": "docx", "output_path": "out.docx",
    }));
    let msg = err_text(&reply);
    assert!(msg.contains("暗标"), "门 1f 点火（实得：{msg}）");
    assert!(msg.contains("profile.dark_bid"), "给出修复通道（实得：{msg}）");
}

/// mode=暗标 + profile.dark_bid=true + bidder_name → 门 1f 放行（暗标链路）。
#[test]
fn dark_bid_gate_passes_when_profile_dark_bid() {
    let (mut svc, pid, _dir) = drafted_with_star_req("fg-dark-pass", "暗标");
    let star_id = star_req_id_of(&svc);
    svc.store_mut()
        .set_matrix_override(
            star_id.clone(),
            bid_domain::matrix::ResponseStatus::NotApplicable,
            Some("聚焦暗标门的隔离豁免（人工裁定）".into()),
            &bid_domain::TrustedPrincipal::human("fg-lead"),
        )
        .unwrap();
    let _ = svc.store_mut().build_matrix().unwrap();
    pass_pre_export_confirm(&mut svc); // #474：覆写动了计分面——重过门再导
    let reply = call(&mut svc, "export_bid_document", json!({
        "project_id": &pid, "format": "docx", "output_path": "out.docx",
        "profile": { "dark_bid": true, "bidder_name": "测试建设工程有限公司" },
    }));
    let r = ok_result(reply);
    assert!(r["artifact"]["sha256"].is_string(), "暗标启用导出成功: {r}");
}

/// mode=明标 + 暗标条款在场（REQ-0003 换暗标条款文本）→ 导出成功 +
/// W_DARK_BID_UNDECLARED 告警（兼容面：告警不拦——升级面 Lead 裁决）。
#[test]
fn dark_bid_gate_warns_when_light_mode_with_dark_clause() {
    let (mut svc, pid, _dir) = drafted_with_star_req("fg-dark-warn", "明标");
    // ★先豁免（隔离变量——本测锁门 1f 告警面；暗标条款文本在 REQ 正文里）
    let star_id = star_req_id_of(&svc);
    svc.store_mut()
        .set_matrix_override(
            star_id.clone(),
            bid_domain::matrix::ResponseStatus::NotApplicable,
            Some("聚焦暗标门告警面的隔离豁免（人工裁定）".into()),
            &bid_domain::TrustedPrincipal::human("fg-lead"),
        )
        .unwrap();
    let _ = svc.store_mut().build_matrix().unwrap();
    pass_pre_export_confirm(&mut svc); // #474：覆写动了计分面——重过门再导
    let reply = call(&mut svc, "export_bid_document", json!({
        "project_id": &pid, "format": "docx", "output_path": "out.docx",
    }));
    let r = ok_result(reply);
    assert!(r["artifact"]["sha256"].is_string(), "明标+暗标条款 → 告警不拦: {r}");
    let warns: Vec<String> =
        serde_json::from_value(r["warnings"].clone()).unwrap_or_default();
    assert!(
        warns.iter().any(|w| w.contains("暗标")),
        "warnings 携带暗标未声明告警: {warns:?}"
    );
}

// ---------------------------------------------------------------- 门 1g

/// 补遗登记（value_changed）→ 章节 DIRTY + 改写指令 → 门 1g 拒；
/// dismiss 指令 → 清脏 → 导出放行（处置面即豁免——无参数豁免）。
#[test]
fn dirty_gate_blocks_then_dismiss_frees_export() {
    let (mut svc, pid, _dir) = drafted_with_star_req("fg-dirty", "明标");
    // ★先豁免（隔离变量——本测只锁门 1g）
    let star_id = star_req_id_of(&svc);
    svc.store_mut()
        .set_matrix_override(
            star_id.clone(),
            bid_domain::matrix::ResponseStatus::NotApplicable,
            Some("聚焦 DIRTY 门的隔离豁免（人工裁定）".into()),
            &bid_domain::TrustedPrincipal::human("fg-lead"),
        )
        .unwrap();
    let _ = svc.store_mut().build_matrix().unwrap();
    pass_pre_export_confirm(&mut svc);
    // 补遗 value_changed：REQ-0001（资格条件，已绑证据+章节）→ 章节 DIRTY + 指令
    let out = svc
        .register_addendum_changes(vec![bid_domain::rewrite::ChangeSpec {
            req_id: Some("REQ-0001".into()),
            change_type: bid_domain::rewrite::ChangeType::ValueChanged,
            old_text: "贰级资质".into(),
            new_requirement: "壹级资质（补遗变更）".into(),
            category: None,
            clause_no: None,
            section_id: None,
            source_file_id: None,
        }])
        .unwrap();
    assert!(!out.dirty_sections.is_empty(), "补遗登记打脏归属章节");
    let reply = call(&mut svc, "export_bid_document", json!({
        "project_id": &pid, "format": "docx", "output_path": "out.docx",
    }));
    let msg = err_text(&reply);
    assert!(msg.contains("DIRTY 门"), "门 1g 点火（实得：{msg}）");
    assert!(msg.contains("改写指令未处置"), "指名 stale 语义（实得：{msg}）");
    // 处置面：dismiss 全部 pending 指令 → 清脏 → 放行
    let sec = out.dirty_sections[0].clone();
    let pending: Vec<String> = svc
        .store()
        .pending_rewrite_directives_of(&sec)
        .iter()
        .map(|d| d.id.clone())
        .collect();
    assert!(!pending.is_empty(), "dismiss 前有 pending 指令");
    for did in pending {
        svc.store_mut().dismiss_rewrite_directive(&did).unwrap();
    }
    let reply = call(&mut svc, "export_bid_document", json!({
        "project_id": &pid, "format": "docx", "output_path": "out.docx",
    }));
    let r = ok_result(reply);
    assert!(r["artifact"]["sha256"].is_string(), "指令处置清脏 → 导出成功: {r}");
}

// ---------------------------------------------------------------- 门 1h

/// 补遗新增评分项（未映射）→ 门 1h 拒；waive_unmapped_scoring 非空理由
/// → 显式豁免导出成功（理由进 warnings 审计面）。
#[test]
fn unmapped_gate_blocks_then_waive_exports() {
    let (mut svc, pid, _dir) = drafted_with_star_req("fg-unmapped", "明标");
    // ★先豁免（隔离变量——本测只锁门 1h）
    let star_id = star_req_id_of(&svc);
    svc.store_mut()
        .set_matrix_override(
            star_id.clone(),
            bid_domain::matrix::ResponseStatus::NotApplicable,
            Some("聚焦 unmapped 门的隔离豁免（人工裁定）".into()),
            &bid_domain::TrustedPrincipal::human("fg-lead"),
        )
        .unwrap();
    // 补遗新增评分项（零章节影响——不触发 1g；评分项不进纲 → unmapped）
    let changes = svc
        .store_mut()
        .register_addendum_changes(&[bid_domain::rewrite::ChangeSpec {
            req_id: None,
            change_type: bid_domain::rewrite::ChangeType::RequirementAdded,
            old_text: String::new(),
            new_requirement: "补遗新增评分项：运维响应时效分级方案 5 分".into(),
            category: Some("评分项".into()),
            clause_no: None,
            section_id: None,
            source_file_id: None,
        }])
        .unwrap();
    assert_eq!(changes.len(), 1, "补遗登记一条评分项");
    let _ = svc.store_mut().build_matrix().unwrap();
    pass_pre_export_confirm(&mut svc);
    let reply = call(&mut svc, "export_bid_document", json!({
        "project_id": &pid, "format": "docx", "output_path": "out.docx",
    }));
    let msg = err_text(&reply);
    assert!(msg.contains("评分项未映射"), "门 1h 点火（实得：{msg}）");
    assert!(msg.contains("waive_unmapped_scoring"), "给出豁免通道（实得：{msg}）");
    // 空串豁免 = 不豁免（fail-closed）
    let reply = call(&mut svc, "export_bid_document", json!({
        "project_id": &pid, "format": "docx", "output_path": "out.docx",
        "waive_unmapped_scoring": "   ",
    }));
    let msg = err_text(&reply);
    assert!(msg.contains("waive_unmapped_scoring 须为非空理由"), "空串响亮拒: {msg}");
    // 非空理由 → 豁免导出 + warnings 审计
    let reply = call(&mut svc, "export_bid_document", json!({
        "project_id": &pid, "format": "docx", "output_path": "out.docx",
        "waive_unmapped_scoring": "补遗评分项与既有运维章合并评审（人工确认无需独立映射）",
    }));
    let r = ok_result(reply);
    assert!(r["artifact"]["sha256"].is_string(), "豁免后导出成功: {r}");
    let warns: Vec<String> =
        serde_json::from_value(r["warnings"].clone()).unwrap_or_default();
    assert!(
        warns.iter().any(|w| w.contains("评分项未映射") && w.contains("审计面记录")),
        "豁免进 warnings 审计面: {warns:?}"
    );
}
