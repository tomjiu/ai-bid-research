//! recover_validating_gate1i.rs —— #152：VALIDATING 门 1i 冲突在案的受支持恢复通道。
//!
//! 缺陷形态（#113 F4，PR #149）：全叶 DRAFTED 的健康 VALIDATING 态，门 1i
//! 冲突在案时 MCP 面无合法改稿路径——draft_response_section → E_STATE、
//! recover_validating_state → 拒（只收缺章异常态）、reopen_section → 拒
//!（只收 ACCEPTED）、段账本空（整稿路径）——唯一出口是手改 db.json
//!（契约明令禁止）= 门 1i 在 VALIDATING 触发即结构性死锁。
//!
//! 修法（Lead 裁量取 B）：`recover_validating_state` 扩第二恢复基础「门 1i
//! 冲突在案」（run_review_from_store 全局柱——与 export 门 1i 同源；决策面
//! 冲突锚 DECISION 不入此面，调整导出决策即解，不须恢复）。
//!
//! 状态构造纪律（#151 落地后仍持久的路径）：一致段稿 → validate 推进 →
//! 补遗 value_changed（#319——VALIDATING 合法变更通道）→ 段级改写引入
//! 跨章金额冲突——「导出前段级改写引入新冲突」的实测面。

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

fn err_text(reply: ToolReply) -> String {
    match reply {
        ToolReply::Err { error, .. } => error.to_string(),
        ToolReply::Ok(out) => panic!("预期拒绝，实际成功: {}", out.result),
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

/// 「两叶 + 证据绑定 + 补遗豁免」服务态（与 #423/#151 夹具同构）。
fn svc_two_leaves(tag: &str) -> (BidService, String, String, String) {
    let mut svc = BidService::new();
    let pid = ok_result(call(&mut svc, "create_bid_project", json!({
        "name": "152-VALIDATING-恢复测试", "bid_deadline": "2026-12-31", "mode": "明标", "external_key": tag,
    })))["project_id"].as_str().unwrap().to_string();
    svc.store_mut().upsert_file(
        "A-招标文件.docx", "招标文件", "sha-152", 10, 1, 50, 0,
        bid_domain::ParseStatus::Ok, "",
    ).unwrap();
    svc.set_requirements(vec![
        mk_req("REQ-0001", "投标保证金须按招标文件要求缴纳"),
        mk_req("REQ-0002", "服务费按合同约定支付"),
    ]).unwrap();
    svc.prepare_outline_and_matrix(OutlineSpec { target_total_chars: 400, max_reqs_per_leaf: 1 })
        .unwrap();
    use bid_domain::evidence::{EvidenceKind, EvidenceSpec};
    use bid_domain::locator::EngineLocator;
    let (eid, _) = svc.store_mut().register_evidence(EvidenceSpec {
        kind: EvidenceKind::ProductDoc,
        title: "缴费凭证".into(),
        source_file: "EV-152.pdf".into(),
        source_sha256: "sha-152-ev".into(),
        locator: EngineLocator::DocxParagraph { paragraph_index: 5, text_fingerprint: "fnv64:152".into() },
        fingerprint: "fnv64:152".into(),
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
    use bid_domain::review::{Decision, Gate};
    svc.store_mut()
        .record_review(Gate::AddendumWaiver, &bid_domain::TrustedPrincipal::human("recover-152-test"), Decision::Approved, vec![], None)
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

/// 填充内容（零数字/零维度词/零占位词的填充句 + 金额句收尾；按叶配额
/// 精确到带内——字数规则零发现，金额口径是唯一变量）。
fn padded(svc: &BidService, sid: &str, sentence: &str) -> String {
    let target: usize = svc.store().sections().iter()
        .find(|n| n.id == sid)
        .map(|n| n.target_chars.max(220) as usize)
        .unwrap_or(220);
    let filler = "本章围绕缴费安排与费用构成作出说明，相关口径以招标文件及合同约定为准，我方承诺按约定履行相应义务与责任。";
    let need = target.saturating_sub(sentence.chars().count());
    let prefix: String = filler.repeat(need / filler.chars().count() + 1)
        .chars().take(need).collect();
    format!("{prefix}{sentence}")
}

/// 段级起草（append——段账本在位，rewrite_section_partial 才有改写对象）。
fn append_padded(svc: &mut BidService, pid: &str, sid: &str, sentence: &str) {
    let content = padded(svc, sid, sentence);
    let out = ok_result(call(svc, "append_section_segment", json!({
        "project_id": pid, "section_id": sid, "content": content,
    })));
    assert_eq!(out["changed"], json!(true), "首段不得被幂等去重：{out}");
}

/// 构造「健康 VALIDATING + 门 1i 冲突在案」（#151 落地后仍持久的路径）：
/// 一致段稿过校验推进 → 补遗 value_changed → 段级改写引入 3580000 冲突。
fn validating_with_gate1i_conflict(tag: &str) -> (BidService, String, String, String) {
    let (mut svc, pid, a, b) = svc_two_leaves(tag);
    append_padded(&mut svc, &pid, &a, "本项目投标保证金为 3500000 元，由基本账户转出。");
    append_padded(&mut svc, &pid, &b, "费用说明：投标保证金金额为 3500000 元，详见附表。");
    let v = ok_result(call(&mut svc, "validate_bid_document", json!({
        "project_id": &pid, "scope": "all",
    })));
    assert_eq!(v["ok"], json!(true), "一致口径基线须过校验：{v}");
    assert_eq!(svc.store().project().unwrap().status, ProjectStatus::Validating);

    // 补遗到达（#319——VALIDATING 合法变更通道）：REQ-0002 值变更 → DIRTY + 指令
    let old_sentence = "费用说明：投标保证金金额为 3500000 元，详见附表。";
    let reg = ok_result(call(&mut svc, "register_addendum_changes", json!({
        "project_id": &pid,
        "changes": [{
            "change_type": "value_changed",
            "req_id": "REQ-0002",
            "old_text": old_sentence,
            "new_requirement": "投标保证金缴纳口径以补遗文件最新约定为准",
        }],
    })));
    let directive = &reg["directives"][0];
    let directive_id = directive["id"].as_str().expect("指令 id").to_string();
    let section_id = directive["section_id"].as_str().expect("指令目标章节").to_string();
    let segment_id = directive["affected_segments"][0]["segment_id"]
        .as_str().expect("受影响段 id（段级起草在位）").to_string();

    // 段级改写引入冲突值——「导出前段级改写引入新冲突」的实测面
    let rewritten = padded(&svc, &section_id, "费用说明：投标保证金金额为 3580000 元，详见附表。");
    ok_result(call(&mut svc, "rewrite_section_partial", json!({
        "project_id": &pid,
        "directive_id": &directive_id,
        "rewrites": [{ "segment_id": &segment_id, "content": rewritten }],
    })));

    // 门 1i 面（同源真源）：冲突在案
    let q = ok_result(call(&mut svc, "check_bid_quality", json!({ "project_id": &pid })));
    let gc = q["global_conflicts"].as_array().expect("global_conflicts 必须在场");
    assert!(
        gc.iter().any(|g| g["kind"] == json!("amount_conflict")),
        "段级改写后门 1i 应见金额冲突（实际 {gc:?}）"
    );
    (svc, pid, a, b)
}

/// 验收 1（#152 红核）：门 1i 冲突在案的健康 VALIDATING → 经恢复通道回
/// DRAFTING → 整稿改稿对齐 → 重校验放行 + 冲突清零（全程 MCP 面，零
/// db.json 手改——「改稿对齐后重试」出口真正可达）。
#[test]
fn gate1i_conflict_recovers_then_revalidates_clean() {
    let (mut svc, pid, _a, b) = validating_with_gate1i_conflict("v152-core");
    let r = ok_result(call(&mut svc, "recover_validating_state", json!({
        "project_id": &pid,
        "reason": "门1i 金额冲突在案——回 DRAFTING 改稿对齐（#152 受支持出口）",
    })));
    assert_eq!(r["status"], json!("DRAFTING"), "恢复须回 DRAFTING：{r}");
    assert_eq!(svc.store().project().unwrap().status, ProjectStatus::Drafting);

    // 改稿通道解锁：整稿重写对齐口径（DRAFTING 面）
    let fixed = padded(&svc, &b, "费用说明：投标保证金金额为 3500000 元，详见附表。");
    ok_result(call(&mut svc, "draft_response_section", json!({
        "project_id": &pid, "section_id": &b, "content": fixed,
    })));

    // 重校验放行 + 门 1i 冲突面清零
    let v = ok_result(call(&mut svc, "validate_bid_document", json!({
        "project_id": &pid, "scope": "all",
    })));
    assert_eq!(v["ok"], json!(true), "对齐后重校验须放行：{v}");
    assert_eq!(svc.store().project().unwrap().status, ProjectStatus::Validating);
    let q = ok_result(call(&mut svc, "check_bid_quality", json!({ "project_id": &pid })));
    assert_eq!(q["global_conflicts"], json!([]), "门 1i 冲突面须清零：{q}");
}

/// 验收 2（守卫不放宽）：无冲突的健康 VALIDATING → 恢复通道仍拒（健康态
/// 不构成恢复条件——第二基础不是任意回退门；决策面冲突调整导出参数即解）。
#[test]
fn healthy_validating_without_conflict_still_refused() {
    let (mut svc, pid, a, b) = svc_two_leaves("v152-refuse");
    append_padded(&mut svc, &pid, &a, "本项目投标保证金为 3500000 元，由基本账户转出。");
    append_padded(&mut svc, &pid, &b, "费用说明：投标保证金金额为 3500000 元，详见附表。");
    let v = ok_result(call(&mut svc, "validate_bid_document", json!({
        "project_id": &pid, "scope": "all",
    })));
    assert_eq!(v["ok"], json!(true));
    assert_eq!(svc.store().project().unwrap().status, ProjectStatus::Validating);
    let err = err_text(call(&mut svc, "recover_validating_state", json!({
        "project_id": &pid, "reason": "尝试无事实基础的回退",
    })));
    assert!(err.contains("不构成恢复条件"), "健康态拒因须明示：{err}");
}
