//! validate_gate1i_consistency.rs —— #151：validate(P6) 与 export 门 1i 同源对称。
//!
//! 缺陷形态（#113 F3 实测，PRJ-0001 @ main 5d1ad69，PR #149）：
//! 跨章金额冲突在案时 `validate_bid_document` scope=all 的 deterministic
//! findings 零金额面 → ok=true 推进 DRAFTING→VALIDATING；export 门 1i 读
//! 同一 `run_review_from_store` 真源却硬拦（无豁免）——同一冲突面
//! 「先过门后撞门」，改稿通道被 E_STATE 关死（#152 的结构根因）。
//!
//! 修法：validate 的 blocker 判定纳入 global_conflicts（四类全局冲突恒
//! BLOCKER，与门 1i 恒同口径）。冲突在 DRAFTING 期被拦 → 改稿通道
//! （draft_response_section / set_matrix_override / 证据补绑）保持开放。
//!
//! 夹具纪律：外部稿直注（与 #423 global_consistency_tool 同构——引擎不
//! 生成只提交）；内容按叶配额精确填充（字数带零发现——金额冲突是唯一
//! 变量，不夹带 E_CHARS_*/E_TOTAL_CHARS_* 噪声）。

use bid_domain::outline::OutlineSpec;
use bid_domain::ProjectStatus;
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

fn mk_req(id: &str, excerpt: &str) -> bid_domain::Requirement {
    use bid_domain::{Anchor, Requirement};
    Requirement {
        id: id.into(),
        category: "商务要求".into(),
        clause_no: None,
        anchors: vec![Anchor {
            file: "A-招标文件.docx".into(),
            kind: "para".into(),
            locator: format!("第二章/{id}"),
            excerpt: excerpt.into(),
            block_idx: None,
            page: None,
            line: None,
        }],
        params: Default::default(),
        source_file: "A-招标文件.docx".into(),
    }
}

/// 「两叶 + 证据绑定 + 补遗豁免」服务态（与 #423 global_consistency_tool
/// 同构——每叶 1 REQ → 两叶；商务要求须证据佐证才可起草）。
fn svc_two_leaves(tag: &str) -> (BidService, String, String, String) {
    let mut svc = BidService::new();
    let pid = ok_result(call(&mut svc, "create_bid_project", json!({
        "name": "validate-门1i-同源测试", "bid_deadline": "2026-12-31", "mode": "明标", "external_key": tag,
    })))["project_id"].as_str().unwrap().to_string();
    svc.store_mut().upsert_file(
        "A-招标文件.docx", "招标文件", "sha-151", 10, 1, 50, 0,
        bid_domain::ParseStatus::Ok, "",
    ).unwrap();
    svc.set_requirements(vec![
        mk_req("REQ-0001", "投标保证金须按招标文件要求缴纳"),
        mk_req("REQ-0002", "服务费按合同约定支付"),
    ]).unwrap();
    svc.prepare_outline_and_matrix(OutlineSpec { target_total_chars: 400, max_reqs_per_leaf: 1 })
        .unwrap();
    // 素材面（#110）：商务要求类 REQ 须有证据佐证，否则 draft 拒生成
    use bid_domain::evidence::{EvidenceKind, EvidenceSpec};
    use bid_domain::locator::EngineLocator;
    let (eid, _) = svc.store_mut().register_evidence(EvidenceSpec {
        kind: EvidenceKind::ProductDoc,
        title: "缴费凭证".into(),
        source_file: "EV-151.pdf".into(),
        source_sha256: "sha-151-ev".into(),
        locator: EngineLocator::DocxParagraph { paragraph_index: 5, text_fingerprint: "fnv64:151".into() },
        fingerprint: "fnv64:151".into(),
        valid_from: None,
        valid_until: None,
        subject_name: "某公司".into(),
        scope: "商务承诺佐证".into(),
        client: None,
        amount_wan: None,
        completed_on: None,
        fields: Default::default(),
        excerpt: None,
        excerpt_locator: None,
        verification_tier: None,
    }).unwrap();
    for rid in ["REQ-0001", "REQ-0002"] {
        svc.store_mut().bind_evidence(&eid, rid, "2026-12-31").unwrap();
    }
    let _ = svc.store_mut().build_matrix().unwrap();
    // L3 无补遗阻塞的人工出口（与 #423 同口径）
    use bid_domain::review::{Decision, Gate};
    svc.store_mut()
        .record_review(Gate::AddendumWaiver, &bid_domain::TrustedPrincipal::human("validate-gate1i-test"), Decision::Approved, vec![], None)
        .unwrap();
    let parents: std::collections::HashSet<&str> = svc.store().sections().iter()
        .filter_map(|n| n.parent_id.as_deref()).collect();
    let leaves: Vec<String> = svc.store().sections().iter()
        .filter(|n| !parents.contains(&n.id[..]))
        .map(|n| n.id.clone()).collect();
    assert!(leaves.len() >= 2, "每叶 1 REQ 应产出 ≥2 叶（实际 {}）", leaves.len());
    let (a, b) = (leaves[0].clone(), leaves[1].clone());
    (svc, pid, a, b)
}

/// 外部稿直注起草（content 在场即 external 语义）。
fn draft_external(svc: &mut BidService, pid: &str, sid: &str, content: &str) -> Value {
    ok_result(call(svc, "draft_response_section", json!({
        "project_id": pid, "section_id": sid, "content": content,
    })))
}

/// 按叶配额精确填充后直注（填充句零数字/零维度词/零占位词——字数带
/// 零发现，金额句是唯一变量；配额 0 的叶按 220 保底——两叶合计 ≥440
/// ≥ outline_total_chars(400)，E_TOTAL_CHARS_BELOW_MIN 不触发）。
fn draft_padded(svc: &mut BidService, pid: &str, sid: &str, sentence: &str) -> Value {
    let target: usize = svc.store().sections().iter()
        .find(|n| n.id == sid)
        .map(|n| n.target_chars.max(220) as usize)
        .unwrap_or(220);
    let filler = "本章围绕缴费安排与费用构成作出说明，相关口径以招标文件及合同约定为准，我方承诺按约定履行相应义务与责任。";
    let need = target.saturating_sub(sentence.chars().count());
    let prefix: String = filler.repeat(need / filler.chars().count() + 1)
        .chars().take(need).collect();
    // Truncated filler must not run into the assertion's subject token. Preserve
    // exact quota while making the final padding character a sentence boundary.
    let mut prefix = prefix;
    if !prefix.is_empty() {
        prefix.pop();
        prefix.push('。');
    }
    let content = format!("{prefix}{sentence}");
    draft_external(svc, pid, sid, &content)
}

fn validate(svc: &mut BidService, pid: &str) -> Value {
    ok_result(call(svc, "validate_bid_document", json!({
        "project_id": pid, "scope": "all",
    })))
}

/// 验收 1（#151 红钉）：跨章金额冲突在案 → validate ok=false +
/// E_AMOUNT_CONFLICT 进 errors（BLOCKER），项目留在 DRAFTING（改稿通道
/// 开放——「先过门后撞门」死路的解）。
#[test]
fn cross_chapter_amount_conflict_blocks_validate_and_advance() {
    let (mut svc, pid, a, b) = svc_two_leaves("v151-conflict");
    draft_padded(&mut svc, &pid, &a, "本项目投标保证金为 3500000 元，由基本账户转出。");
    draft_padded(&mut svc, &pid, &b, "费用说明：投标保证金金额为 3580000 元，详见附表。");
    let v = validate(&mut svc, &pid);
    assert_eq!(v["ok"], json!(false), "跨章金额冲突必须翻 ok=false（F3：不得先过门后撞门）");
    let codes: Vec<&str> = v["errors"].as_array().unwrap().iter()
        .map(|e| e["rule_code"].as_str().unwrap()).collect();
    assert!(codes.contains(&"E_AMOUNT_CONFLICT"), "errors 须含 E_AMOUNT_CONFLICT（实际 {codes:?}）");
    assert_eq!(
        svc.store().project().unwrap().status,
        ProjectStatus::Drafting,
        "冲突在案校验失败 → 不推进（#243 语义：留 DRAFTING 可改稿重试）"
    );
}

/// 验收 2（两面恒同口径）：同一冲突面 check_bid_quality 的
/// global_conflicts 与 validate 的 E_AMOUNT_CONFLICT 同源可见——P5/P6/P8
/// 三面读同一真源，不再出现 P6 零金额面 vs P8 硬拦的劈叉。
#[test]
fn validate_and_gate1i_see_same_conflict_face() {
    let (mut svc, pid, a, b) = svc_two_leaves("v151-same-face");
    draft_padded(&mut svc, &pid, &a, "本项目投标保证金为 3500000 元，由基本账户转出。");
    draft_padded(&mut svc, &pid, &b, "费用说明：投标保证金金额为 3580000 元，详见附表。");
    // 门 1i 同源面：check_bid_quality.global_conflicts 可见 amount_conflict
    let q = ok_result(call(&mut svc, "check_bid_quality", json!({ "project_id": &pid })));
    let gc = q["global_conflicts"].as_array().expect("global_conflicts 必须在场");
    assert!(
        gc.iter().any(|g| g["kind"] == json!("amount_conflict")),
        "门 1i 面应见 amount_conflict（实际 {gc:?}）"
    );
    // validate 面：同一冲突以 E_AMOUNT_CONFLICT 进 errors
    let v = validate(&mut svc, &pid);
    assert_eq!(v["ok"], json!(false));
    let codes: Vec<&str> = v["errors"].as_array().unwrap().iter()
        .map(|e| e["rule_code"].as_str().unwrap()).collect();
    assert!(codes.contains(&"E_AMOUNT_CONFLICT"), "validate 与门 1i 恒同口径（实际 {codes:?}）");
}

/// 验收 3（守卫不误伤）：口径一致的两章 → validate ok=true + 正常推进
/// VALIDATING（#151 只把「真冲突」翻红，不把一致面误拦）。
#[test]
fn consistent_amounts_still_pass_and_advance() {
    let (mut svc, pid, a, b) = svc_two_leaves("v151-consistent");
    draft_padded(&mut svc, &pid, &a, "本项目投标保证金为 3500000 元，由基本账户转出。");
    draft_padded(&mut svc, &pid, &b, "费用说明：投标保证金金额为 3500000 元，详见附表。");
    let v = validate(&mut svc, &pid);
    assert_eq!(v["ok"], json!(true), "口径一致不得误拦：{v}");
    assert_eq!(svc.store().project().unwrap().status, ProjectStatus::Validating, "ok=true 正常推进");
}

/// 验收 4（改稿闭环）：冲突拦截（留 DRAFTING）→ 改稿对齐 → 重校验放行
/// ——「改稿对齐后重试」出口真正可达（全程 MCP 面，零 db.json 手改）。
#[test]
fn conflict_fix_then_revalidate_passes() {
    let (mut svc, pid, a, b) = svc_two_leaves("v151-fix-loop");
    draft_padded(&mut svc, &pid, &a, "本项目投标保证金为 3500000 元，由基本账户转出。");
    draft_padded(&mut svc, &pid, &b, "费用说明：投标保证金金额为 3580000 元，详见附表。");
    let v1 = validate(&mut svc, &pid);
    assert_eq!(v1["ok"], json!(false), "冲突在案先拦（DRAFTING 期）");
    assert_eq!(svc.store().project().unwrap().status, ProjectStatus::Drafting);
    // 改稿通道开放：重写 b 叶口径对齐
    draft_padded(&mut svc, &pid, &b, "费用说明：投标保证金金额为 3500000 元，详见附表。");
    let v2 = validate(&mut svc, &pid);
    assert_eq!(v2["ok"], json!(true), "对齐后放行：{v2}");
    assert_eq!(svc.store().project().unwrap().status, ProjectStatus::Validating);
}

/// PR #157 blocker: the public draft -> quality -> validate path must retain a
/// bidder upper bound, block a higher exact quote, then allow a legal correction.
#[test]
fn bidder_bounded_quote_blocks_validate_then_legal_correction_passes() {
    for legal in ["350", "400"] {
        let (mut svc, pid, a, b) = svc_two_leaves(&format!("v157-bound-{legal}"));
        draft_padded(&mut svc, &pid, &a, "我方投标总报价不超过400万元。");
        draft_padded(&mut svc, &pid, &b, "投标总报价为450万元。");
        let q = ok_result(call(&mut svc, "check_bid_quality", json!({ "project_id": &pid })));
        assert!(q["global_conflicts"].as_array().unwrap().iter()
            .any(|g| g["kind"] == json!("amount_conflict")), "bidder bound must reach quality: {q}");
        let v = validate(&mut svc, &pid);
        assert_eq!(v["ok"], json!(false), "450万 exceeds bidder <=400万: {v}");
        assert!(v["errors"].as_array().unwrap().iter()
            .any(|e| e["rule_code"] == "E_AMOUNT_CONFLICT"));
        assert_eq!(svc.store().project().unwrap().status, ProjectStatus::Drafting);
        draft_padded(&mut svc, &pid, &b, &format!("投标总报价为{legal}万元。"));
        let fixed = validate(&mut svc, &pid);
        assert_eq!(fixed["ok"], json!(true), "legal correction {legal}万 must pass: {fixed}");
        assert_eq!(svc.store().project().unwrap().status, ProjectStatus::Validating);
    }
}

#[test]
fn regulatory_budget_cap_is_not_bidder_quote_in_validate() {
    let (mut svc, pid, a, b) = svc_two_leaves("v157-regulatory-cap");
    draft_padded(&mut svc, &pid, &a, "项目预算不得超过人民币400万元。");
    draft_padded(&mut svc, &pid, &b, "投标总报价为450万元。");
    let v = validate(&mut svc, &pid);
    assert_eq!(v["ok"], json!(true), "regulatory cap is not an exact bidder amount: {v}");
    assert_eq!(svc.store().project().unwrap().status, ProjectStatus::Validating);
}
