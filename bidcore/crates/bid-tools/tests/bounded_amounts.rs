//! PR #157 blocker: bidder upper bounds are constraints, not exact amounts.
//! Synthetic text exercises the public extract_features/check_global/run_review path.

use bid_tools::check::{
    check_global, extract_features, run_review, ChapterInput, CheckFinding, CheckKind,
    CheckSeverity, FeatureTuple, FeatureType,
};
use std::collections::HashSet;

fn chapter<'a>(section_id: &'a str, content: &'a str) -> ChapterInput<'a> {
    ChapterInput {
        section_id,
        content,
        citations: &[],
        target_chars: None,
    }
}

fn amount_features(content: &str) -> Vec<FeatureTuple> {
    extract_features(&chapter("SEC-BOUND", content))
        .into_iter()
        .filter(|f| f.feature_type == FeatureType::Amount)
        .collect()
}

fn conflicts(contents: &[&str]) -> Vec<CheckFinding> {
    let ids: Vec<String> = (0..contents.len()).map(|i| format!("SEC-{i:04}")).collect();
    let chapters: Vec<_> = contents
        .iter()
        .zip(&ids)
        .map(|(text, id)| chapter(id, text))
        .collect();
    run_review(&chapters, &HashSet::new()).findings
}

#[test]
fn bidder_upper_bound_conflicts_with_higher_exact_quote() {
    let findings = conflicts(&["我方投标总报价不超过400万元。", "投标总报价为450万元。"]);
    assert_eq!(
        findings.len(),
        1,
        "bidder <=400万 vs exact450万 must conflict: {findings:?}"
    );
    assert_eq!(findings[0].kind, CheckKind::AmountConflict);
    assert_eq!(findings[0].severity, CheckSeverity::Blocker);
    assert!(
        findings[0].message.contains("SEC-0000=<=4000000"),
        "bound must remain explicit: {:?}",
        findings[0]
    );
    assert!(findings[0].message.contains("SEC-0001=4500000"));
}

#[test]
fn bidder_upper_bound_is_not_exact_and_accepts_equal_or_lower() {
    let features = amount_features("我方投标总报价不超过400万元。");
    assert_eq!(features.len(), 1, "bidder bound must not disappear");
    assert_eq!(features[0].key, "投标总报价");
    assert_eq!(
        features[0].value, "<=4000000",
        "upper bound is not an exact commitment"
    );
    for exact in ["投标总报价为350万元。", "投标总报价为400万元。"] {
        assert!(
            conflicts(&["我方投标总报价不超过400万元。", exact]).is_empty(),
            "legal quote: {exact}"
        );
    }
}

#[test]
fn multiple_bidder_upper_limits_intersect_without_conflict() {
    let contents = [
        "我方投标总报价不超过400万元。",
        "本公司投标总报价不得高于500万元。",
    ];
    assert_eq!(amount_features(contents[0]).len(), 1);
    assert_eq!(amount_features(contents[1]).len(), 1);
    assert!(
        conflicts(&contents).is_empty(),
        "different upper bounds can coexist"
    );
    assert!(conflicts(&[contents[0], contents[1], "投标总报价350万元。"]).is_empty());
    assert_eq!(
        conflicts(&[contents[0], contents[1], "投标总报价450万元。"]).len(),
        1,
        "tightest bound wins"
    );
}

#[test]
fn bidder_bounds_normalize_currency_units_and_reference_noise() {
    for text in [
        "我方投标总报价不超过人民币４００万元。",
        "本单位的投标总报价不得超出400万元。",
        "本节报价说明\n我方投标总报价不超过400万元。",
        "本公司投标总报价不得超过￥4,000,000元。",
        "我方投标总报价不高于RMB 400万圆。",
        "我方投标总报价不超出CNY 400.0 万元。",
        "我方投标总报价按照[REQ-0106]和[EV-0032]承诺不得高于人民币400万元。",
    ] {
        let features = amount_features(text);
        assert_eq!(
            features.len(),
            1,
            "currency/ID protected: {text}: {features:?}"
        );
        assert_eq!(
            features[0].value, "<=4000000",
            "currency/ID normalization: {text}"
        );
        assert_eq!(
            conflicts(&[text, "投标总报价450万元。"]).len(),
            1,
            "bound must reach global comparison: {text}"
        );
        assert!(conflicts(&[text, "投标总报价4,000,000元。"]).is_empty());
    }
}

#[test]
fn nonbidder_budget_caps_and_generic_bidder_rules_stay_ignored() {
    for text in [
        "项目预算不得超过400万元。",
        "投标总报价不超过400万元。",
        "我方投标总报价不超过2026，详见附表。",
        "我方项目预算不得超过400万元。",
        "我方投标保证金不得超过80万元。",
        "项目预算不得超过人民币400万元。",
        "招标控制价不高于￥4,000,000元。",
        "招标文件要求投标总报价不得超过400万元。",
        "投标人投标总报价不得超过400万元。",
        "采购人投标总报价不超过400万元。",
        "招标方投标总报价不超过400万元。",
        "我方已阅读招标文件。项目预算不得超过400万元。",
        "我方理解采购要求，项目预算不得超过400万元。",
        "非我方投标总报价不超过400万元。",
        "其他投标人的本公司投标总报价不超过400万元。",
    ] {
        assert!(
            amount_features(text).is_empty(),
            "nonbidder/regulatory cap must not become a commitment: {text}"
        );
        assert!(conflicts(&[text, "投标总报价450万元。"]).is_empty());
    }
}

#[test]
fn exact_conflicts_remain_even_with_compatible_loose_bound() {
    let findings = conflicts(&[
        "我方投标总报价不超过500万元。",
        "投标总报价350万元。",
        "投标总报价450万元。",
    ]);
    assert_eq!(
        findings.len(),
        1,
        "bound must not hide unequal exact commitments"
    );
    assert_eq!(findings[0].kind, CheckKind::AmountConflict);
}

#[test]
fn single_chapter_bounded_conflict_and_feature_replay_are_deterministic() {
    let text = "我方投标总报价不超过400万元。我方投标总报价为450万元。";
    let features = amount_features(text);
    let findings = check_global(&features);
    assert_eq!(
        findings.len(),
        1,
        "intra-chapter contradiction must be detected"
    );
    let json = serde_json::to_string(&features).unwrap();
    let replay: Vec<FeatureTuple> = serde_json::from_str(&json).unwrap();
    assert_eq!(check_global(&replay), findings);
    let mut reversed = features;
    reversed.reverse();
    assert_eq!(check_global(&reversed), findings);
    assert_eq!(conflicts(&[text]).len(), 1);
}

#[test]
fn legacy_exact_tuple_comparison_and_invalid_bounds_do_not_weaken() {
    let exact = |value: &str| FeatureTuple {
        feature_type: FeatureType::Amount,
        key: "投标总报价".into(),
        value: value.into(),
        section_id: "SEC-EXTERNAL".into(),
    };
    // check_global is public: distinct legacy exact strings retain old behavior.
    assert_eq!(check_global(&[exact("0400"), exact("400")]).len(), 1);
    for invalid in ["<=oops", "<=-1", "<=9223372036854775808"] {
        assert_eq!(check_global(&[exact(invalid), exact("400")]).len(), 1);
    }
}

#[test]
fn review_bounds_never_cross_owner_dimension_or_explicit_quotes() {
    for text in [
        "我方投标总报价另报，项目预算不超过400万元。",
        "我方投标总报价另报，其他投标人投标总报价不超过400万元。",
        "招标文件规定：我方投标总报价不超过400万元。",
        "我方投标总报价引用条款“不超过400万元”。",
    ] {
        assert!(amount_features(text).is_empty(), "wrong ownership: {text}: {:?}", amount_features(text));
        assert!(conflicts(&[text, "投标总报价为450万元。"]).is_empty());
    }
}
#[test]
fn review_symbolic_limits_are_constraints_and_regulations_are_not_commitments() {
    for relation in ["≤", "<=", "＜＝"] {
        let own = format!("我方投标总报价{relation}400万元。");
        assert_eq!(amount_features(&own)[0].value, "<=4000000");
        assert!(conflicts(&[&own, "投标总报价350万元。"]).is_empty());
        assert_eq!(conflicts(&[&own, "投标总报价450万元。"]).len(), 1);
        assert!(amount_features(&format!("项目预算{relation}400万元。")).is_empty());
    }
}
#[test]
fn review_loose_bound_never_masks_legacy_exact_string_conflict() {
    let features = ["0400", "400", "<=500"].map(|value| FeatureTuple {
        feature_type: FeatureType::Amount, key: "投标总报价".into(), value: value.into(), section_id: value.into()
    });
    assert_eq!(check_global(&features).len(), 1);
}
#[test]
fn bidder_zero_bound_and_fractional_wan_use_existing_integer_yuan_policy() {
    assert!(conflicts(&["本企业投标总报价不得超出0万元。", "投标总报价为0元。"]).is_empty());
    assert_eq!(conflicts(&["本企业投标总报价不得超出0万元。", "投标总报价为1元。"]).len(), 1);
    assert!(conflicts(&["本单位投标总报价不超过0.04万元。", "投标总报价为400元。"]).is_empty());
    assert_eq!(conflicts(&["本单位投标总报价不超过0.04万元。", "投标总报价为401元。"]).len(), 1);
}
