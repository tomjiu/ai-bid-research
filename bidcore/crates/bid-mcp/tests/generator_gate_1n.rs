//! AUD2-CHN-01（issue #130）门 1n 接线验收：生成器汇总门在**导出路径**
//! 上的真实点火（MCP 面）。
//!
//! 审计背景：generator=auto 无 api_key 静默降 mock；mock 按构造填充
//! target±20% → 门 1c 字数门天然通过 → mock 模板稿可直达导出——正文
//! 注水/虚构的直接通道。本文件证明：
//! - **评分叶 mock 无豁免 → 拒**（E_UNPROCESSABLE，消息含「门 1n」+
//!   指名章节与生成器）；
//! - **非空豁免理由 → 放行且理由进 warnings**（对齐 1h waive 形态）；
//! - **全 real → 放行**（generator_summary.real 计数 + 评分叶 non_real=0）；
//! - **导出响应常驻 generator_summary 字段**（real/mock/external/unknown
//!   四类计数 + 评分叶分拆）。
//!
//! 留痕数据源：ChapterRecord.generator（draft 落盘由 trait kind 写入——
//! 本文件 TestRealGenerator 以 kind="real" + mock 同款篇幅纪律构造，
//! 专测门消费面，不发起真实 LLM 调用）。

use bid_domain::outline::OutlineSpec;
use bid_domain::{Anchor, ParseStatus, Requirement};
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
        "bid-g1n-{tag}-{}-{}",
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

fn b4_profile() -> Value {
    json!({
        "bid_amount": 3500000.0,
        "duration_days": 180,
        "validity_days": 90,
        "legal_rep_gender": "男",
        "project_no": "ZFCG-2026-G1N",
    })
}

fn b4_write_profile(ws: &std::path::Path) {
    let p = bid_domain::party::BidderProfile {
        company_name: "测试建设工程有限公司".into(),
        legal_rep: "王锐".into(),
        legal_rep_id: "110101196001011234".into(),
        legal_rep_position: "总经理".into(),
        address: "测试市测试区测试路 1 号".into(),
        agent: "李明".into(),
        agent_id: "110101198505052345".into(),
        ..Default::default()
    };
    std::fs::write(ws.join("bidder-profile.json"), serde_json::to_string(&p).unwrap()).unwrap();
}

fn mk_req(id: &str, category: &str, excerpt: &str) -> Requirement {
    Requirement {
        id: id.into(),
        category: category.into(),
        clause_no: None,
        anchors: vec![Anchor {
            file: "A-招标文件.docx".into(),
            kind: "para".into(),
            locator: "第二章/1.1".into(),
            excerpt: excerpt.into(),
            block_idx: None,
            page: None,
            line: None,
        }],
        params: Default::default(),
        source_file: "A-招标文件.docx".into(),
    }
}

/// 评分项 REQ（#252 评分驱动建纲的输入面：name/score/track/sub_items 专路签名）。
fn mk_scoring_req() -> Requirement {
    let mut params = HashMap::new();
    params.insert("name".to_string(), json!("服务方案"));
    params.insert("score".to_string(), json!(10.0));
    params.insert("track".to_string(), json!("技术评审"));
    params.insert(
        "sub_items".to_string(),
        json!(["总体架构", "实施步骤", "风险应对"]),
    );
    params.insert(
        "score_rules".to_string(),
        json!("服务方案（10分）：需包含总体架构、实施步骤、风险应对。"),
    );
    Requirement {
        id: "REQ-0003".into(),
        category: "评分项".into(),
        clause_no: None,
        anchors: vec![Anchor {
            file: "A-招标文件.docx".into(),
            kind: "para".into(),
            locator: "第五章/2.1".into(),
            excerpt: "服务方案（10分）：需包含总体架构、实施步骤、风险应对。".into(),
            block_idx: None,
            page: None,
            line: None,
        }],
        params,
        source_file: "A-招标文件.docx".into(),
    }
}

/// kind="real" 的测试生成器（内容走 mock 同款篇幅纪律——门 1c/1m 不误伤；
/// 本文件专测门 1n 的留痕消费面，不发起真实 LLM 调用）。
struct TestRealGenerator;

impl bid_tools::draft::SectionGenerator for TestRealGenerator {
    fn generate(
        &mut self,
        input: &bid_tools::draft::SectionDraftInput,
    ) -> Result<bid_tools::draft::GeneratedDraft, String> {
        Ok(bid_tools::draft::GeneratedDraft {
            content: bid_tools::draft::generate_mock(input),
        })
    }
    fn kind(&self) -> &'static str {
        "real"
    }
}

fn pass_setup_gates(svc: &mut BidService) {
    use bid_domain::review::{Decision, Gate};
    svc.store_mut()
        .record_review(
            Gate::AddendumWaiver,
            &bid_domain::TrustedPrincipal::human("lead"),
            Decision::Approved,
            vec![],
            None,
        )
        .unwrap();
    for gate in [Gate::MatrixApproval, Gate::OutlineApproval] {
        svc.store_mut()
            .record_review(gate, &bid_domain::TrustedPrincipal::human("lead"), Decision::Approved, vec![], None)
            .unwrap();
    }
}

fn pass_pre_export_confirm(svc: &mut BidService) {
    use bid_domain::review::{Decision, Gate};
    svc.store_mut()
        .record_review(Gate::PreExportConfirm, &bid_domain::TrustedPrincipal::human("lead"), Decision::Approved, vec![], None)
        .unwrap();
}

/// 夹具：资格 + 否决（证据绑定过门 1a）+ **评分项 REQ-0003**（评分叶在位）。
/// gen_kind: "mock" | "real" —— 全叶统一生成器（留痕面）。
fn svc_drafted(tag: &str, gen_kind: &str) -> (BidService, String, PathBuf) {
    let dir = tmp_dir(tag);
    let mut svc = BidService::open(&dir).unwrap();
    b4_write_profile(&dir);
    let pid = ok_result(call(&mut svc, "create_bid_project", json!({
        "name": "#130 门 1n 测试", "bid_deadline": "2026-12-31", "mode": "明标",
        "external_key": tag,
    })))["project_id"]
        .as_str()
        .unwrap()
        .to_string();
    svc.store_mut()
        .upsert_file("A-招标文件.docx", "招标文件", &format!("sha-{tag}"), 10, 1, 50, 0, ParseStatus::Ok, "")
        .unwrap();
    svc.set_requirements(vec![
        mk_req("REQ-0001", "资格条件", "投标人须具备水利水电工程施工总承包贰级及以上资质"),
        mk_req("REQ-0002", "否决项", "投标文件未经法定代表人签字的作否决处理"),
        mk_scoring_req(),
    ])
    .unwrap();
    let _ = svc
        .prepare_outline_and_matrix(OutlineSpec { target_total_chars: 1_500, max_reqs_per_leaf: 8 })
        .unwrap();
    // 评分叶在位（#252 评分驱动建纲——REQ-0003 经 OutlineDerived 映射绑定响应叶）
    let scoring_leaf: Option<String> = svc
        .store()
        .scoring_mappings()
        .iter()
        .find(|m| m.scoring_req_id == "REQ-0003")
        .map(|m| m.section_id.clone());
    assert!(
        scoring_leaf.is_some(),
        "评分项 REQ-0003 应有映射响应叶（评分驱动建纲；实得 mappings：{:?}）",
        svc.store().scoring_mappings().iter().map(|m| (&m.scoring_req_id, &m.section_id)).collect::<Vec<_>>()
    );
    // 证据绑定（门 1a 放行面）
    use bid_domain::evidence::EvidenceSpec;
    use bid_domain::locator::EngineLocator;
    let (eid, _) = svc
        .store_mut()
        .register_evidence(EvidenceSpec {
            kind: bid_domain::evidence::EvidenceKind::Qualification,
            title: "贰级资质证书".into(),
            source_file: "EV-01.pdf".into(),
            source_sha256: format!("sha-ev-{tag}"),
            locator: EngineLocator::DocxParagraph { paragraph_index: 3, text_fingerprint: "fnv64:g1n".into() },
            fingerprint: "fnv64:g1n".into(),
            valid_from: None,
            valid_until: None,
            subject_name: "某建设工程有限公司".into(),
            scope: "水利水电".into(),
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
    pass_setup_gates(&mut svc);
    // 全叶起草（统一生成器——mock 或 test-real）
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
        match gen_kind {
            "real" => {
                svc.draft_section(sid, None, None, None, &mut TestRealGenerator).unwrap();
            }
            _ => {
                svc.draft_section(sid, None, None, None, &mut bid_tools::draft::MockGenerator).unwrap();
            }
        }
    }
    pass_pre_export_confirm(&mut svc);
    (svc, pid, dir)
}

// ---------------------------------------------------------------- 门 1n 三态

/// 评分叶 mock 无豁免 → 拒（消息指名章节 + 生成器 + 修复通道）。
#[test]
fn mock_scoring_leaf_blocks_export() {
    let (mut svc, pid, _dir) = svc_drafted("block", "mock");
    let reply = call(&mut svc, "export_bid_document", json!({
        "profile": b4_profile(),
        "project_id": &pid, "format": "docx", "output_path": "out.docx",
    }));
    let msg = err_text(&reply);
    assert!(msg.contains("门 1n"), "门 1n 点火（实得：{msg}）");
    assert!(msg.contains("评分叶"), "指名评分叶（实得：{msg}）");
    assert!(msg.contains("mock"), "指名生成器（实得：{msg}）");
    assert!(msg.contains("waive_scoring_leaf_generator"), "豁免通道透出（实得：{msg}）");
}

/// 非空豁免理由 → 放行；理由进 warnings；generator_summary 如实计数。
#[test]
fn waived_mock_scoring_leaf_exports_with_audit_warning() {
    let (mut svc, pid, dir) = svc_drafted("waive", "mock");
    let r = ok_result(call(&mut svc, "export_bid_document", json!({
        "profile": b4_profile(),
        "project_id": &pid, "format": "docx", "output_path": "out.docx",
        "waive_scoring_leaf_generator": "mock 链收官测试——非正式投标，模板稿可接受",
    })));
    let warnings: Vec<String> = r["warnings"]
        .as_array()
        .unwrap()
        .iter()
        .filter_map(|w| w.as_str().map(String::from))
        .collect();
    assert!(
        warnings.iter().any(|w| w.contains("#130 豁免") && w.contains("mock 链收官测试")),
        "豁免理由进 warnings 审计面（实得：{warnings:?}）"
    );
    let gs = &r["generator_summary"];
    assert!(gs["scoring_leaves_total"].as_u64().unwrap() >= 1, "评分叶计数 ≥1");
    assert!(gs["scoring_leaves_non_real"].as_u64().unwrap() >= 1, "非 real 评分叶 ≥1");
    assert!(gs["mock"].as_u64().unwrap() >= 1, "mock 计数 ≥1");
    assert!(dir.join("out.docx").is_file(), "产物落盘");
}

/// 全 real → 放行；generator_summary.real 计数 + 评分叶 non_real=0（常驻字段）。
#[test]
fn all_real_scoring_leaf_exports_with_summary() {
    let (mut svc, pid, _dir) = svc_drafted("real", "real");
    let r = ok_result(call(&mut svc, "export_bid_document", json!({
        "profile": b4_profile(),
        "project_id": &pid, "format": "docx", "output_path": "out.docx",
    })));
    let gs = &r["generator_summary"];
    // 常驻字段在位（四类计数 + 评分叶分拆——导出响应契约面）
    for key in ["real", "mock", "external", "unknown", "scoring_leaves_total", "scoring_leaves_non_real"] {
        assert!(gs[key].is_u64(), "generator_summary.{key} 常驻（实得：{gs}）");
    }
    assert!(gs["real"].as_u64().unwrap() >= 1, "real 计数 ≥1（实得：{gs}）");
    assert_eq!(gs["mock"].as_u64().unwrap(), 0, "零 mock");
    assert_eq!(gs["scoring_leaves_non_real"].as_u64().unwrap(), 0, "评分叶全 real");
}

/// 空串豁免 = 不豁免（fail-closed 不放水——参数前置校验面）。
#[test]
fn empty_waiver_reason_is_rejected_at_param_layer() {
    let (mut svc, pid, _dir) = svc_drafted("empty-waive", "mock");
    let reply = call(&mut svc, "export_bid_document", json!({
        "profile": b4_profile(),
        "project_id": &pid, "format": "docx", "output_path": "out.docx",
        "waive_scoring_leaf_generator": "   ",
    }));
    let msg = err_text(&reply);
    assert!(msg.contains("waive_scoring_leaf_generator"), "空串拒绝（实得：{msg}）");
}
