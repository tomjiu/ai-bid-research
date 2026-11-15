//! amount_scan_guards.rs —— #150：金额扫描器双守卫（引用编号 + 上限语）。
//!
//! 素材纪律（真实成稿钉子，非合成简化句）：两句原文取自 PR #149 真实 LLM
//! 验收成稿 `artifacts/realagent-2026-11-13/chapters/`（47 叶 glm-4-plus
//! 真实起草）：
//! - SEC-0015（F1）：`[REQ-0106]` 引用编号抢先命中维度词句内首个数字——
//!   特征值 106 顶掉真实承诺值 46000（￥46000）；
//! - SEC-0044（F2）：复述条款上限「最高不得超过80万元」——法规上限被当
//!   承诺值 800000。
//!
//! 守卫只加不减：合法金额形态（单位锚/裸多位数/逗号剥离）不回退。

use bid_tools::check::{extract_features, ChapterInput, FeatureType};

/// 抽取 content 的全部金额特征 (key, value)——单一夹具入口。
fn amounts(content: &str) -> Vec<(String, String)> {
    let citations: Vec<String> = Vec::new();
    let ch = ChapterInput {
        section_id: "SEC-T",
        content,
        citations: &citations,
        target_chars: None,
    };
    extract_features(&ch)
        .into_iter()
        .filter(|f| f.feature_type == FeatureType::Amount)
        .map(|f| (f.key, f.value))
        .collect()
}

/// F1 真句钉子（SEC-0015 原句）：[REQ-0106] 的编号段不得抢先命中——
/// 承诺值 = ￥46000 → 归一 "46000"。
#[test]
fn f1_reference_id_not_taken_as_amount() {
    let content = "关于投标保证金要求，我方已严格按照 [REQ-0106] 的规定，足额递交了人民币肆万陆仟圆整（￥46000）的投标保证金，确保保证金金额准确无误且无任何瑕疵，避免因保证金问题导致投标被否决。";
    assert_eq!(
        amounts(content),
        vec![("投标保证金".to_string(), "46000".to_string())],
        "引用编号 0106 应被守卫跳过，承诺值取 ￥46000"
    );
}

/// F2 真句钉子（SEC-0044 原句两联）：「最高不得超过80万元」是条款上限
/// 复述，非承诺值——800000 不得入特征面；句内其余数字（2%）为比率面。
/// 整段零金额特征。
#[test]
fn f2_upper_limit_phrase_not_taken_as_amount() {
    let content = "投标保证金一般不超过项目估算价的2%，但最高不得超过80万元人民币，本招标项目的投标保证金金额见投标人须知前附表。根据投标人须知前附表，本项目的投标保证金金额为人民币XX万元，不超过项目估算价的2%，且符合招标文件规定的最高限额要求。";
    assert_eq!(
        amounts(content),
        Vec::<(String, String)>::new(),
        "上限语 80万 与 2% 比率均不得入金额特征面"
    );
}

/// 守卫只加不减：合法金额形态不回退（单位锚 / 裸多位数 / 逗号剥离）。
#[test]
fn legit_amount_forms_unchanged() {
    assert_eq!(
        amounts("本项目投标保证金 50 万元，以保函形式提交。"),
        vec![("投标保证金".to_string(), "500000".to_string())]
    );
    assert_eq!(
        amounts("投标保证金：46,000元，缴纳方式见招标文件。"),
        vec![("投标保证金".to_string(), "46000".to_string())]
    );
    assert_eq!(
        amounts("本项目投标总报价为480万元整。"),
        vec![("投标总报价".to_string(), "4800000".to_string())]
    );
}

/// 引用形态变体：无括号 REQ-0107 / 括号 [EV-0032] 同守卫——跳过后取句内
/// 下一个合规数字（不因守卫把整句判空）。
#[test]
fn reference_variants_skip_to_next_number() {
    assert_eq!(
        amounts("投标保证金按REQ-0107的规定缴纳46,000元。"),
        vec![("投标保证金".to_string(), "46000".to_string())]
    );
    assert_eq!(
        amounts("投标保证金依据[EV-0032]的要求缴纳46000元。"),
        vec![("投标保证金".to_string(), "46000".to_string())]
    );
}
