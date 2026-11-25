//! 批六④（r5 审读 A1 根治面）：报价 vs 限价的语义方向门
//! `E_BID_CAP_DIRECTION`（BLOCKER）。
//!
//! r5 实况（段114，REQ-0116 响应）：正文写「投标总报价为人民币肆佰捌拾万
//! 元整（4,800,000元），**高于**招标文件设定的最高投标限价」——事实反写
//! （480 万 < 限价 494.6 万），自认否决项；同稿段174 又正确写「不低于成本
//! 也不高于限价」——正反并存，数值一致性门（S-5）拦不住（数值都对），纯
//! 语义方向错误。
//!
//! 契约（先红后绿）：
//! 1. 反写句（报价 + 高于/超过/超出 + 限价，同句、无限定否定）→
//!    E_BID_CAP_DIRECTION BLOCKER；
//! 2. 合法句（「未超过」「不高于」「低于」限价）→ 0 命中（不误拦）；
//! 3. 限价语境但无报价主体的句子（如「限价高于成本的说法不成立」）→
//!    0 误报。

use bid_domain::outline::{OutlineNode, SectionStatus};
use bid_domain::{Anchor, DomainStore, ProjectStatus, Requirement};
use bid_tools::validate::{validate_document, NoModel};

// ---------------------------------------------------------------- 夹具

fn req(id: &str, category: &str, excerpt: &str) -> Requirement {
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
        params: Default::default(),
        source_file: "A-招标文件.docx".into(),
    }
}

fn leaf(id: &str, title: &str, content: &str) -> OutlineNode {
    OutlineNode {
        id: id.into(),
        parent_id: None,
        title: title.into(),
        level: 1,
        order: 1,
        requirement_ids: vec!["REQ-0001".into()],
        target_chars: 50, // 带内（正文字数 < 80% 配额也只 MINOR/评分外告警）
        status: SectionStatus::Drafted,
        dirty: false,
        content: Some(content.into()),
        content_attempt: 1,
    }
}

fn store_with_leaf(tag: &str, content: &str) -> DomainStore {
    let mut s = DomainStore::new();
    s.create_project("批六方向门", "ZFCG-2026-B6", "明标", "b6-key").unwrap();
    s.advance_project_status(ProjectStatus::FilesImported).unwrap();
    s.set_requirements(vec![req(
        "REQ-0001",
        "商务要求",
        "本项目设置最高投标限价 4946365 元。",
    )])
    .unwrap();
    s.set_outline(vec![leaf("SEC-0001", "否决情形响应", content)]).unwrap();
    s.build_matrix().unwrap();
    s
}

fn cap_findings(store: &DomainStore) -> Vec<String> {
    let mut nm = NoModel;
    let report = validate_document(store, None, &mut nm).unwrap();
    report
        .findings
        .iter()
        .filter(|f| f.rule_code == "E_BID_CAP_DIRECTION")
        .map(|f| f.message.clone())
        .collect()
}

// ---------------------------------------------------------------- ① 反写句 → BLOCKER

#[test]
fn reversed_direction_assertion_reports_blocker() {
    let store = store_with_leaf(
        "reversed",
        "针对 [REQ-0116] 我方投标总报价为人民币肆佰捌拾万元整（4,800,000元），高于招标文件设定的最高投标限价。我方将提供成本构成分析。",
    );
    let fs = cap_findings(&store);
    assert!(
        !fs.is_empty(),
        "反写句（报价高于限价）必须报 E_BID_CAP_DIRECTION: {:?}",
        fs
    );
    let mut nm = NoModel;
    let report = validate_document(&store, None, &mut nm).unwrap();
    let f = report
        .findings
        .iter()
        .find(|f| f.rule_code == "E_BID_CAP_DIRECTION")
        .unwrap();
    assert_eq!(f.severity, "BLOCKER", "废标级方向断言错误");
    assert!(f.section_id.as_deref() == Some("SEC-0001"), "定位到章");
}

// ---------------------------------------------------------------- ② 合法句 → 0 命中（不误拦）

#[test]
fn legal_negated_direction_assertions_pass_clean() {
    let store = store_with_leaf(
        "legal",
        "我方任意一项报价均未超过对应部分最高投标限价，符合招标文件要求。本投标文件既不低于成本也不高于最高投标限价。投标总报价低于本项目最高投标限价，未将最高投标限价作为本方分项报价。",
    );
    let fs = cap_findings(&store);
    assert!(
        fs.is_empty(),
        "『未超过/不高于/低于/未将限价作分项』合法句不得误拦: {fs:?}"
    );
}

// ---------------------------------------------------------------- ③ 无报价主体 → 0 误报

#[test]
fn cap_context_without_bid_subject_is_ignored() {
    let store = store_with_leaf(
        "no_subject",
        "评标委员会认为该限价高于成本的说法不成立。招标人公布最高投标限价后不再上调。设备采购金额超过采购计划，需另行审批。",
    );
    let fs = cap_findings(&store);
    assert!(
        fs.is_empty(),
        "限价语境但非报价方向断言 → 不误报: {fs:?}"
    );
}
