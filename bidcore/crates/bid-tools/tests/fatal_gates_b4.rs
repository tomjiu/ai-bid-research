//! #88 审计批次 4：修复 6/7/8 的纯函数层单测。
//!
//! 与 fatal_gap_gates.rs（批次 1-2，门 1e/1f findings 层）同族分工：
//! - **修复 6（F-05 勘误口径 / P1-11）**：decision 对账——
//!   [`run_review_from_store_with_decision`] 把导出决策值（投标总报价/
//!   工期）临时注入比对面（不落库也能比）；章正文 vs 决策值冲突 =
//!   AmountConflict/ScheduleConflict（BLOCKER——门 1i 的消费面）；
//!   一致放行；无关维度数字零误报；
//! - **修复 7（F-06 / P0-4，审计修复优先序第 1 位）**：三件套数据缺位
//!   门——投标函/法定代表人身份证明/授权委托件的**数据字段**缺位 →
//!   E_FORMAT_PLACEHOLDER BLOCKER（成品将落【待填】= 报价缺项废标级）；
//!   齐备零 findings；设计性空位（签字/日期/年龄等人工现场填写位）不在
//!   门面——字段级检查天然不覆盖，与成品语义精确对齐（不误拦）；
//! - **修复 8a（F-09 / P1-7）**：超篇幅可配置门——超带超阈值 →
//!   E_CHARS_OVER_LIMIT BLOCKER；阈值内放行；阈值可配（收紧/放宽语义
//!   正确，边界严格大于不含等号）。
//!
//! 接线面（export_document 消费三门 + 豁免面 + 抽取健康度常驻）见
//! bid-mcp/tests/fatal_gates_b4_e2e.rs（真实导出路径点火）。

use bid_domain::outline::{OutlineNode, SectionStatus};
use bid_domain::{Anchor, DomainStore, ProjectStatus, Requirement};
use bid_tools::check::CheckKind;
use bid_tools::export::ExportDecision;
use bid_tools::review_wire::run_review_from_store_with_decision;
use bid_tools::validate::{format_placeholder_gate_findings, length_overrun_gate_findings};
use bid_domain::party::BidderProfile;
use std::collections::HashMap;

// ---------------------------------------------------------------- 夹具

fn req_with_params(id: &str, category: &str, excerpt: &str, params: HashMap<String, serde_json::Value>) -> Requirement {
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

fn leaf(id: &str, title: &str, content: &str, target: u32) -> OutlineNode {
    OutlineNode {
        id: id.into(),
        parent_id: None,
        title: title.into(),
        level: 1,
        order: 1,
        requirement_ids: vec!["REQ-0001".into()],
        target_chars: target,
        status: SectionStatus::Drafted,
        dirty: false,
        content: Some(content.into()),
        content_attempt: 1,
    }
}

/// 双叶（order 唯一——文档序全局唯一是域层硬约束）。
fn leaf2(id: &str, title: &str, content: &str, target: u32, order: u32) -> OutlineNode {
    let mut n = leaf(id, title, content, target);
    n.order = order;
    n
}

fn store_at_drafted() -> DomainStore {
    let mut s = DomainStore::new();
    s.create_project("#88 批4门测", "ZFCG-2026-B4", "明标", "b4-key").unwrap();
    s.advance_project_status(ProjectStatus::FilesImported).unwrap();
    let mut params = HashMap::new();
    params.insert("model".to_string(), serde_json::Value::String("ZFCG-2026-B4".into()));
    s.set_requirements(vec![req_with_params(
        "REQ-0001",
        "商务要求",
        "招标公告载明项目编号：ZFCG-2026-B4",
        params,
    )])
    .unwrap();
    s
}

/// 齐备的决策面（报价/工期/有效期/法定代表人性别——三件全部决策栏）。
fn full_decision() -> ExportDecision {
    ExportDecision {
        bid_amount: Some(3_500_000.0),
        duration_days: Some(180),
        validity_days: Some(90),
        legal_rep_gender: Some("男".into()),
        ..Default::default()
    }
}

/// 齐备的主体信息（三件套全部字段在位）。
fn full_profile() -> BidderProfile {
    BidderProfile {
        company_name: "测试建设工程有限公司".into(),
        legal_rep: "王锐".into(),
        legal_rep_id: "110101196001011234".into(),
        legal_rep_position: "总经理".into(),
        address: "测试市测试区测试路 1 号".into(),
        agent: "李明".into(),
        agent_id: "110101198505052345".into(),
        ..Default::default()
    }
}

// ---------------------------------------------------------------- 修复 6：决策对账

/// 章正文报价 3500000 vs 决策报价 3580000 → AmountConflict（位置锚双面：
/// SEC 与 DECISION）——审计 P1-11 典型失守场景（投标函报价与正文不一致）。
#[test]
fn decision_amount_conflicts_with_chapter() {
    let mut s = store_at_drafted();
    s.set_outline(vec![leaf(
        "SEC-0001",
        "投标函",
        "我司投标总报价为 3500000 元，与开标一览表载明金额一致。",
        100,
    )])
    .unwrap();
    let mut d = full_decision();
    d.bid_amount = Some(3_580_000.0);
    let out = run_review_from_store_with_decision(&s, &d);
    let conflicts: Vec<_> = out
        .findings
        .iter()
        .filter(|f| f.kind == CheckKind::AmountConflict)
        .collect();
    assert_eq!(conflicts.len(), 1, "决策 vs 章正文金额冲突必报: {:?}", out.findings);
    assert!(conflicts[0].message.contains("投标总报价"), "维度键指名: {}", conflicts[0].message);
    assert!(conflicts[0].message.contains("DECISION"), "决策面位置锚在列: {}", conflicts[0].message);
    assert!(conflicts[0].message.contains("SEC-0001"), "章位置锚在列: {}", conflicts[0].message);
}

/// 章正文工期 180 天 vs 决策工期 90 天 → ScheduleConflict。
#[test]
fn decision_duration_conflicts_with_chapter() {
    let mut s = store_at_drafted();
    s.set_outline(vec![leaf(
        "SEC-0001",
        "实施方案",
        "本项目工期 180 日历天，自监理开工令载明的开工日起算。",
        100,
    )])
    .unwrap();
    let mut d = full_decision();
    d.duration_days = Some(90);
    let out = run_review_from_store_with_decision(&s, &d);
    assert!(
        out.findings
            .iter()
            .any(|f| f.kind == CheckKind::ScheduleConflict && f.message.contains("DECISION")),
        "决策工期 vs 章正文工期冲突必报: {:?}",
        out.findings
    );
}

/// 决策值与章正文一致 → 零冲突（正面对照——同值不报）。
#[test]
fn decision_consistent_with_chapter_no_conflict() {
    let mut s = store_at_drafted();
    s.set_outline(vec![leaf(
        "SEC-0001",
        "投标函",
        "我司投标总报价为 350 万元，工期 180 日历天。",
        100,
    )])
    .unwrap();
    let out = run_review_from_store_with_decision(&s, &full_decision());
    assert!(
        out.findings.iter().all(|f| !f.kind.is_global()),
        "同值零冲突: {:?}",
        out.findings
    );
}

/// 词面扩展零误报：无关维度数字（服务费）与决策报价互不干扰。
#[test]
fn decision_injection_no_cross_dimension_noise() {
    let mut s = store_at_drafted();
    s.set_outline(vec![leaf(
        "SEC-0001",
        "商务响应",
        "本项目涉及的服务费为 5000 元，由中标人支付。",
        100,
    )])
    .unwrap();
    let out = run_review_from_store_with_decision(&s, &full_decision());
    assert!(
        out.findings.iter().all(|f| !f.kind.is_global()),
        "不同维度键不构成冲突: {:?}",
        out.findings
    );
}

/// 决策面缺省（None/0）不注入比对行——不落库的面没有可比值，零注入
/// 零冲突（诚实面：缺决策字段由修复 7 的【待填】门拦截，不在本门越界）。
#[test]
fn decision_absent_injects_nothing() {
    let mut s = store_at_drafted();
    s.set_outline(vec![leaf(
        "SEC-0001",
        "投标函",
        "我司投标总报价为 3500000 元。",
        100,
    )])
    .unwrap();
    let out = run_review_from_store_with_decision(&s, &ExportDecision::default());
    assert!(
        out.findings.iter().all(|f| !f.kind.is_global()),
        "零决策零注入零冲突: {:?}",
        out.findings
    );
}

// ---------------------------------------------------------------- 修复 7：三件套数据缺位门

/// 全缺（default profile + default decision + 无项目编号 REQ）→ 三件全报，
/// 字段清单指名（成品将落【待填】的每一个数据字段）。
#[test]
fn placeholder_gate_reports_all_missing_data_fields() {
    // 零参数 REQ（无 model 键——项目编号数据源同时缺位）
    let mut s = DomainStore::new();
    s.create_project("#88 批4门测", "ZFCG-2026-B4", "明标", "b4-key").unwrap();
    s.advance_project_status(ProjectStatus::FilesImported).unwrap();
    s.set_requirements(vec![req_with_params(
        "REQ-0001",
        "商务要求",
        "普通商务条款（无项目编号参数）",
        HashMap::new(),
    )])
    .unwrap();
    s.set_outline(vec![leaf("SEC-0001", "投标函", "正文在位。", 100)])
        .unwrap();
    let findings = format_placeholder_gate_findings(
        &s,
        &BidderProfile::default(),
        &ExportDecision::default(),
    );
    assert_eq!(findings.len(), 3, "三件全报: {findings:?}");
    for f in &findings {
        assert_eq!(f.rule_code, "E_FORMAT_PLACEHOLDER");
        assert_eq!(f.severity, "BLOCKER");
    }
    let joined = findings
        .iter()
        .map(|f| f.message.clone())
        .collect::<Vec<_>>()
        .join("\n");
    // 投标函面：抬头 + 三决策栏 + 项目编号
    for kw in ["投标函", "投标人名称", "项目编号", "投标总报价", "工期", "投标有效期"] {
        assert!(joined.contains(kw), "投标函缺位字段指名 {kw}: {joined}");
    }
    // 法定代表人身份证明面
    for kw in ["法定代表人身份证明", "法定代表人姓名", "身份证号", "职务", "注册地址", "性别"] {
        assert!(joined.contains(kw), "身份证明缺位字段指名 {kw}: {joined}");
    }
    // 授权委托书面
    for kw in ["授权委托书", "受托人姓名", "受托人身份证号"] {
        assert!(joined.contains(kw), "授权委托书缺位字段指名 {kw}: {joined}");
    }
}

/// 齐备（profile + decision + 项目编号 REQ 参数）→ 零 findings。
#[test]
fn placeholder_gate_passes_full_inputs() {
    let mut s = store_at_drafted();
    s.set_outline(vec![leaf("SEC-0001", "投标函", "正文在位。", 100)])
        .unwrap();
    let findings = format_placeholder_gate_findings(&s, &full_profile(), &full_decision());
    assert!(
        findings.is_empty(),
        "齐备零 findings: {findings:?}"
    );
}

/// 项目编号显式决策面：无 REQ 参数账但 decision.project_no 在场 →
/// 投标函不报缺位（其余件照报——显式 > 抽取兜底的解析序钉死）。
#[test]
fn placeholder_gate_project_no_explicit_decision_wins() {
    let mut s = DomainStore::new();
    s.create_project("#88 批4门测", "ZFCG-2026-B4", "明标", "b4-key").unwrap();
    s.advance_project_status(ProjectStatus::FilesImported).unwrap();
    s.set_requirements(vec![req_with_params(
        "REQ-0001",
        "商务要求",
        "普通商务条款（无项目编号参数）",
        HashMap::new(),
    )])
    .unwrap();
    s.set_outline(vec![leaf("SEC-0001", "投标函", "正文在位。", 100)])
        .unwrap();
    let mut d = ExportDecision::default();
    d.project_no = Some("ZFCG-2026-B4".into());
    let findings = format_placeholder_gate_findings(&s, &full_profile(), &d);
    let letter = findings
        .iter()
        .find(|f| f.message.contains("投标函数据缺位"))
        .expect("决策三栏缺位仍在（只有 project_no 补齐）");
    assert!(
        !letter.message.contains("项目编号"),
        "显式 project_no 在场不报编号缺位: {}",
        letter.message
    );
}

/// 设计性空位不在门面：签字/日期/年龄等人工现场填写位是模板固有结构，
/// 不进字段级检查（成品语义 = 数据字段缺位才拦——与审计 P0-4 口径对齐）。
#[test]
fn placeholder_gate_ignores_designed_blanks() {
    let mut s = store_at_drafted();
    s.set_outline(vec![leaf("SEC-0001", "投标函", "正文在位。", 100)])
        .unwrap();
    // 齐备输入下三件渲染仍含【签字人姓名】【出具日期】等设计位——
    // 门零 findings（上测正面钉）；此处再钉边界：只缺一个字段 → 恰一条。
    let mut p = full_profile();
    p.legal_rep_id.clear();
    let findings = format_placeholder_gate_findings(&s, &p, &full_decision());
    assert_eq!(findings.len(), 1, "单字段缺位单条: {findings:?}");
    assert!(findings[0].message.contains("身份证号"), "指名缺位字段: {}", findings[0].message);
}

// ---------------------------------------------------------------- 修复 8a：超篇幅可配置门

/// 超带 99%（199/100）在默认阈值 50% 之上 → BLOCKER；阈值放宽到 100%
/// → 放行（可配置语义：阈值是调用方裁决面）。
#[test]
fn length_overrun_gate_fires_over_threshold_and_configurable() {
    let mut s = store_at_drafted();
    let content = "长".repeat(199);
    s.set_outline(vec![leaf("SEC-0001", "技术方案", &content, 100)])
        .unwrap();
    let f50 = length_overrun_gate_findings(&s, 50);
    assert_eq!(f50.len(), 1, "超 99% > 50% 阈值必报: {f50:?}");
    assert_eq!(f50[0].rule_code, "E_CHARS_OVER_LIMIT");
    assert_eq!(f50[0].severity, "BLOCKER");
    assert_eq!(f50[0].section_id.as_deref(), Some("SEC-0001"));
    assert!(f50[0].message.contains("199") && f50[0].message.contains("100"), "实际/配额在列: {}", f50[0].message);

    let f100 = length_overrun_gate_findings(&s, 100);
    assert!(f100.is_empty(), "超 99% ≤ 100% 阈值放行: {f100:?}");
}

/// 边界严格大于：恰超阈值 1% 拒、等于阈值放行（50% 阈值 × 150 字配额）。
#[test]
fn length_overrun_gate_boundary_is_strictly_greater() {
    let mk = |chars: usize| {
        let mut st = store_at_drafted();
        st.set_outline(vec![leaf("SEC-0001", "技术方案", &"长".repeat(chars), 100)])
            .unwrap();
        st
    };
    let s_over = mk(151);
    assert_eq!(
        length_overrun_gate_findings(&s_over, 50).len(),
        1,
        "151 > 150（+51% > 50%）拒"
    );
    let s_eq = mk(150);
    assert!(
        length_overrun_gate_findings(&s_eq, 50).is_empty(),
        "150 = 150（+50% = 50%）放行——边界不含等号"
    );
}

/// 带内（140/100 = +40%）与零配额叶不进门面。
#[test]
fn length_overrun_gate_ignores_in_band_and_unquotaed() {
    let mut s = store_at_drafted();
    s.set_outline(vec![
        leaf2("SEC-0001", "技术方案", &"长".repeat(140), 100, 1),
        leaf2("SEC-0002", "附件说明", "无配额章节正文。", 0, 2),
    ])
    .unwrap();
    assert!(
        length_overrun_gate_findings(&s, 50).is_empty(),
        "带内 + 零配额零 findings"
    );
}
