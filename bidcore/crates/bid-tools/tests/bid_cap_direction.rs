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

fn store_with_leaf(_tag: &str, content: &str) -> DomainStore {
    store_with_excerpt(content, "本项目设置最高投标限价 4946365 元。")
}

fn store_with_excerpt(content: &str, excerpt: &str) -> DomainStore {
    let mut s = DomainStore::new();
    s.create_project("批六方向门", "ZFCG-2026-B6", "明标", "b6-key")
        .unwrap();
    s.advance_project_status(ProjectStatus::FilesImported)
        .unwrap();
    s.set_requirements(vec![req("REQ-0001", "商务要求", excerpt)])
        .unwrap();
    s.set_outline(vec![leaf("SEC-0001", "否决情形响应", content)])
        .unwrap();
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
    assert!(fs.is_empty(), "限价语境但非报价方向断言 → 不误报: {fs:?}");
}

// #222: Preserve lawful source quotations; never hide a later bidder assertion.
const CAP_RULE: &str = "投标人投标报价高于最高投标限价的，其投标将被否决。";

fn store_with_cap_rule(content: &str) -> DomainStore {
    store_with_excerpt(content, CAP_RULE)
}

#[test]
fn source_rule_quote_generated_by_mock_is_not_bidder_assertion() {
    use bid_tools::draft::{generate_mock, ReqBrief, SectionDraftInput};
    let input = SectionDraftInput {
        section_id: "SEC-0001".into(),
        title: "否决情形响应".into(),
        target_chars: 100,
        requirements: vec![ReqBrief {
            id: "REQ-0001".into(),
            category: "商务要求".into(),
            excerpt: CAP_RULE.into(),
        }],
        evidences: vec![],
        instructions: None,
    };
    let content = generate_mock(&input);
    assert!(
        content.contains(CAP_RULE),
        "Source excerpt must remain unchanged"
    );
    let findings = cap_findings(&store_with_cap_rule(&content));
    assert!(
        findings.is_empty(),
        "Source rule is not a bidder over-cap claim: {findings:?}"
    );
}

#[test]
fn source_quote_cannot_hide_actual_over_cap_assertion_after_it() {
    let content = format!("针对 [REQ-0001]「{CAP_RULE}」我方报价高于最高限价。");
    assert!(!cap_findings(&store_with_cap_rule(&content)).is_empty());
}

#[test]
fn arbitrary_quoted_over_cap_claim_remains_blocker() {
    let content = "我方确认「我方投标总报价高于最高限价」，并承担其后果。";
    assert!(!cap_findings(&store_with_cap_rule(content)).is_empty());
}

#[test]
fn conditional_rule_quote_not_backed_by_requirement_is_not_exempt() {
    let content = format!("针对 [REQ-0001]「{CAP_RULE}」我方完全满足。");
    assert!(!cap_findings(&store_with_leaf("unverified", &content)).is_empty());
}

#[test]
fn unrelated_negation_cannot_cancel_over_cap_predicate() {
    for content in [
        "我方报价不含税且高于最高限价。",
        "我方报价低于成本但高于最高限价。",
        "我方无偏离，投标总价超过最高限价。",
    ] {
        assert!(
            !cap_findings(&store_with_leaf("negation", content)).is_empty(),
            "Missed {content}"
        );
    }
}

#[test]
fn later_over_cap_predicate_is_checked_after_legal_first_occurrence() {
    for content in [
        "我方分项报价不高于对应限价，但投标总报价高于最高限价。",
        "我方分项报价未超过对应限价，但投标总价超过最高限价。",
        "我方分项报价未超出对应限价，但投标总价超出最高限价。",
    ] {
        assert!(
            !cap_findings(&store_with_leaf("repeat", content)).is_empty(),
            "Missed {content}"
        );
    }
}

#[test]
fn predicate_subject_and_object_determine_comparison_direction() {
    for content in [
        "最高限价高于我方投标总报价。",
        "我方报价高于成本且低于最高限价。",
        "我方投标报价不高于最高限价。",
    ] {
        assert!(
            cap_findings(&store_with_leaf("objects", content)).is_empty(),
            "False positive: {content}"
        );
    }
}

#[test]
fn bidder_total_amount_over_cap_remains_blocker() {
    assert!(!cap_findings(&store_with_leaf("total", "我方投标总额高于最高限价。")).is_empty());
}
#[test]
fn source_quote_inserted_inside_bidder_assertion_cannot_hide_it() {
    for content in [
        format!("我方报价（依据规则「{CAP_RULE}」）高于最高限价。"),
        format!("我方报价高于（依据规则「{CAP_RULE}」）最高限价。"),
    ] {
        assert!(
            !cap_findings(&store_with_cap_rule(&content)).is_empty(),
            "Missed {content}"
        );
    }
}

#[test]
fn comparison_reference_and_adverb_are_not_new_subjects() {
    for content in [
        "我方报价与最高限价相比，高于该限价10%。",
        "我方报价以最高限价为基准，最终超过该限价10%。",
        "我方投标总报价在预算内仍高于最高限价。",
        "我方报价在成本核算后高于最高限价。",
        "我方报价超过预算限价。",
    ] {
        assert!(
            !cap_findings(&store_with_leaf("adverbs", content)).is_empty(),
            "Missed {content}"
        );
    }
}

#[test]
fn explicit_predicate_negation_passes_but_double_negation_does_not() {
    for content in [
        "我方报价并非高于最高限价。",
        "我方报价不可能超过最高限价。",
        "我方报价未曾超过最高限价。",
    ] {
        assert!(
            cap_findings(&store_with_leaf("negative", content)).is_empty(),
            "False positive {content}"
        );
    }
    for content in [
        "我方报价不得不超过最高限价。",
        "我方报价不是不高于最高限价。",
    ] {
        assert!(
            !cap_findings(&store_with_leaf("double", content)).is_empty(),
            "Missed {content}"
        );
    }
}

#[test]
fn long_source_aside_cannot_hide_outer_over_cap_assertion() {
    let excerpt = format!("第一章招标公告/投标邀请书 1.4最高投标限价 本项目设置最高投标限价，最高投标限价详见招标公告，{CAP_RULE}");
    for content in [
        format!("我方报价（依据规则「{excerpt}」）高于最高限价。"),
        format!("我方报价高于（依据规则「{excerpt}」）最高限价。"),
    ] {
        assert!(!cap_findings(&store_with_excerpt(&content, &excerpt)).is_empty());
    }
}

#[test]
fn source_verified_veto_enumeration_is_not_bidder_over_cap_claim() {
    let excerpt = "（7）投标报价低于成本或者高于招标文件设定的最高投标限价。";
    let content = format!("针对 [REQ-0001]「{excerpt}」的要求，我方承诺完全满足，无偏离。");
    assert!(cap_findings(&store_with_excerpt(&content, excerpt)).is_empty());
}

#[test]
fn source_rule_and_independent_over_cap_claim_inside_same_quote_still_block() {
    let excerpt = format!("{CAP_RULE}我方投标总报价高于最高限价。");
    let content = format!("引用「{excerpt}」");
    assert!(!cap_findings(&store_with_excerpt(&content, &excerpt)).is_empty());
}
