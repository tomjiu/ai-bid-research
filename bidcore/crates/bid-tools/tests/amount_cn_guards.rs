//! amount_cn_guards.rs —— #113 机器审计修复批：金额面三盲区（先红后绿）。
//!
//! 素材纪律（真实成稿钉子，非合成简化句）：全部真句取自 #113 审计
//! `artifacts/realagent-113-20261122/投标文件-realagent-113.docx`（48 叶
//! glm-4-plus 真实起草，2026-11-22 跑批）+ 对照组 huaian 主文件 ground
//! truth。审计发现三类「虚构参数」面：
//! - 纯中文大写金额幻觉（玖拾陆万/捌万）——ASCII-only 扫描器盲区；
//! - 维度词盲区（投标担保 48 万）——AMOUNT_DIMS 词面缺口；
//! - 分项和 ≠ 总报价（段55：限价天花板被抄成分项报价 4810365+136000
//!   ≠ 总报价 4800000）——无算术一致性检查。
//!
//! 守卫只加不减：既有合法金额形态（大写与 ASCII 并存、上限语、日期）
//! 不回退。

use bid_tools::check::{
    extract_features, run_review, ChapterInput, CheckFinding, CheckKind, CheckSeverity, FeatureType,
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

fn amounts(content: &str) -> Vec<(String, String)> {
    extract_features(&chapter("SEC-T", content))
        .into_iter()
        .filter(|f| f.feature_type == FeatureType::Amount)
        .map(|f| (f.key, f.value))
        .collect()
}

fn findings(contents: &[&str]) -> Vec<CheckFinding> {
    let ids: Vec<String> = (0..contents.len()).map(|i| format!("SEC-{i:04}")).collect();
    let chapters: Vec<_> = contents
        .iter()
        .zip(&ids)
        .map(|(text, id)| chapter(id, text))
        .collect();
    run_review(&chapters, &HashSet::new()).findings
}

// ---------------------------------------------------------------- 红测：三盲区

/// 段121 真句（否决第 7 组）：纯大写金额「玖拾陆万元整」= 96 万——
/// 疑锚源文「不超过估算价 2%」（2%×480 万=9.6 万）量级错位成 96 万。
/// ground truth = 46,000（须知前附表 3.5.1）。抽取面必须命中大写形态。
#[test]
fn cn_uppercase_amount_is_extracted() {
    let content = "针对[REQ-0191]要求，我方已按照招标文件要求足额递交投标保证金，金额为人民币玖拾陆万元整，保证金的递交方式、期限和形式均符合招标文件规定，不存在任何瑕疵。";
    assert_eq!(
        amounts(content),
        vec![("投标保证金".to_string(), "960000".to_string())],
        "纯大写金额玖拾陆万元整必须入金额特征面（#113 审计段121）"
    );
}

/// 段171 真句（否决第 12 组）：「投标担保」维度词 + 大写 48 万——
/// 双盲区（词面 + 大写）。ground truth = 46,000。
#[test]
fn bid_guarantee_dim_and_uppercase_extracted() {
    let content = "针对[REQ-0316]，我方已严格按照招标文件要求提供足额、有效的投标担保，担保形式、金额及期限均符合招标文件规定，不存在任何瑕疵。投标担保金额为人民币肆拾捌万元整，有效期与投标有效期一致，确保投标担保的有效性和合规性。";
    assert_eq!(
        amounts(content),
        vec![("投标担保".to_string(), "480000".to_string())],
        "投标担保维度 + 大写肆拾捌万元整必须入特征面（#113 审计段171）"
    );
}

/// 段261 真句（须知 3.3-4.2）：「捌万元整」= 8 万——
/// 疑锚源文「最高不得超过 80 万元」上限截断。ground truth = 46,000。
#[test]
fn cn_uppercase_eight_wan_extracted() {
    let content = "针对 [REQ-0021] 要求，我方已按要求缴纳投标保证金，金额为人民币捌万元整。保证金已于投标截止日前通过电汇方式汇入招标人指定账户。";
    assert_eq!(
        amounts(content),
        vec![("投标保证金".to_string(), "80000".to_string())],
        "纯大写金额捌万元整必须入金额特征面（#113 审计段261）"
    );
}

/// 冲突检出：正确章（46000）vs 幻觉章（玖拾陆万）→ AmountConflict Blocker
/// —— 真跑缺陷复现（8 处正确 + 3 处幻觉零检出 = 假绿面）。
#[test]
fn hallucinated_deposit_conflict_is_blocker() {
    let fs = findings(&[
        "我方已按要求足额递交投标保证金人民币肆万陆仟圆整（￥46000），形式与期限均符合规定。",
        "针对[REQ-0191]要求，我方已按照招标文件要求足额递交投标保证金，金额为人民币玖拾陆万元整。",
    ]);
    let amount_fs: Vec<_> = fs.iter().filter(|f| f.kind == CheckKind::AmountConflict).collect();
    assert_eq!(amount_fs.len(), 1, "96000 vs 960000 互斥口径必须报冲突: {fs:?}");
    assert_eq!(amount_fs[0].severity, CheckSeverity::Blocker);
    assert!(
        amount_fs[0].message.contains("SEC-0001=960000"),
        "幻觉值必须出现在冲突消息: {:?}",
        amount_fs[0]
    );
}

/// 段55 真句（否决第 1 组）：分项报价之和 ≠ 总报价——
/// 设备 4,810,365 + 服务 136,000 = 4,946,365 ≠ 总报价 4,800,000。
/// 原样抄限价天花板当分项报价，真实评标必发澄清质疑。
#[test]
fn subtotal_sum_mismatch_is_blocker() {
    let fs = findings(&[
        "我方投标总报价为人民币肆佰捌拾万元整（4,800,000元），其中设备部分报价为4,810,365元，服务部分报价为136,000元，均未超过招标文件规定的最高投标限价要求[REQ-0058]。",
        "本项目投标总报价为人民币肆佰捌拾万元整（4,800,000元），投标保证金为人民币肆万陆仟圆整（46,000元），工期为37日历天。",
    ]);
    assert!(
        fs.iter().any(|f| f.kind == CheckKind::AmountConflict
            && f.severity == CheckSeverity::Blocker
            && f.message.contains("分项和")),
        "分项和不等必须报 Blocker（4810365+136000≠4800000）: {fs:?}"
    );
}

// ---------------------------------------------------------------- 守卫：只加不减

/// 大写与 ASCII 并存的合法形态：取首个合规值（肆万陆仟圆整=46000）——
/// amount_scan_guards F1 句的回归面（维度词前置同款形态）。
#[test]
fn uppercase_and_ascii_coexist_first_wins() {
    let content = "关于投标保证金要求，我方已严格按照规定足额递交了人民币肆万陆仟圆整（￥46000）的投标保证金，确保保证金金额准确无误。";
    assert_eq!(
        amounts(content),
        vec![("投标保证金".to_string(), "46000".to_string())],
        "大写先行命中同值 46000——不得回退既有 ASCII 抽取"
    );
}

/// 大写日期形态（贰拾贰年）不入金额面——日期守卫。
#[test]
fn cn_uppercase_date_form_not_amount() {
    let content = "本合同自贰拾贰年起算的投标保证金约定无效，具体以投标人须知前附表为准。";
    assert!(
        amounts(content).iter().all(|(k, _)| k != "投标保证金"),
        "贰拾贰年是日期成分非金额（守卫：终止紧邻年/月/日）"
    );
}

/// 上限语 + 大写金额：「最高不得超过人民币玖拾陆万元整」是条款上限复述
/// —— 非本方承诺值，不得入精确特征面（F2 大写版守卫）。
#[test]
fn upper_limit_phrase_with_uppercase_not_exact() {
    let content = "投标保证金一般不超过项目估算价的2%，但最高不得超过人民币玖拾陆万元整，本招标项目的投标保证金金额见投标人须知前附表。";
    assert!(
        amounts(content).iter().all(|(k, v)| !(k == "投标保证金" && !v.starts_with("<="))),
        "上限语前缀的大写金额不得当精确承诺值（上限形态 <=960000 或零特征均可）"
    );
}

// ---------------------------------------------------------------- 批七红测：D2 时间单位假阳

/// 批七（#113 全链审计 D2——r6b SEC-0043 实锚）：「投标保证金的有效期
/// 与投标有效期一致，均为90天」——90 后随时间单位（天）是时长面非金额
/// 面；裸数字兜底分支（int_digits>=2）把它抓成 Exact(90) 保证金 → 与
/// 他章 46000 正面冲突 = 假 BLOCKER（E_AMOUNT_CONFLICT 误拦导出）。
/// 守卫只加不减：同句真金额（带元/万单位）不回退。
#[test]
fn time_unit_after_number_is_not_amount() {
    let a = amounts("投标保证金的有效期与投标有效期一致，均为90天。");
    assert!(
        !a.iter().any(|(k, _)| k == "投标保证金"),
        "90 天（时长面）不得提取为投标保证金金额: {a:?}"
    );
    // 对照（守卫只加不减）：同句真金额带元单位不受时间守卫误伤
    let b = amounts("投标保证金为46000元，其有效期与投标有效期一致，均为90天。");
    assert!(
        b.iter().any(|(k, v)| k == "投标保证金" && v == "46000"),
        "带元真金额 46000 不受时间单位守卫误伤: {b:?}"
    );
    // 边界：日月年周同口径（「有效期90日」/「缴纳期限为30日」）
    let c = amounts("投标保证金的有效期为90日。");
    assert!(
        !c.iter().any(|(k, _)| k == "投标保证金"),
        "90 日（时长面）同样不得入金额面: {c:?}"
    );
}

// ---------------------------------------------------------------- 批八红测：D2 残余时间单位

/// 批八（#113 代码审计 G1——D2 残余漏洞）：原守卫表只覆盖 天/日/月/年/周/个，
/// 漏了同属时长/序列面的其余单位——
/// - **工作日**（无「个」形）：「履约保证金在签发验收证书后28工作日内退还」
///   的 28 后随 工——裸兜底（int_digits≥2）会抓成 Exact(28) 履约保证金，
///   与他章真值冲突 = 又一例 D2 家族假 BLOCKER；
/// - **小时/分钟**：电信运维类标书「服务费按90分钟计费/按100小时计费」的
///   时长价率面；
/// - **分期序列**：「服务费分12期支付」的 12 是期数非金额。
/// 修：守卫表补 工/小/分/秒/旬/期。守卫只加不减——真金额（元/万锚）不回退。
#[test]
fn time_unit_residual_forms_not_amount() {
    // 工作日（主实锚形态——履约保证金条款常见句式）
    let a = amounts("履约保证金在签发工程竣工验收证书后28工作日内一次性无息退还。");
    assert!(
        !a.iter().any(|(k, _)| k == "履约保证金"),
        "28 工作日（时长面）不得提取为履约保证金金额: {a:?}"
    );
    // 分钟（服务价率面——90 分钟是时长不是服务费金额）
    let b = amounts("上门服务费按90分钟计费，超出部分另行计算。");
    assert!(
        !b.iter().any(|(k, _)| k == "服务费"),
        "90 分钟（时长面）不得提取为服务费金额: {b:?}"
    );
    // 小时（同上价率面）
    let c = amounts("驻场服务费按100小时包干计费。");
    assert!(
        !c.iter().any(|(k, _)| k == "服务费"),
        "100 小时（时长面）不得提取为服务费金额: {c:?}"
    );
    // 分期序列数（期数非金额）
    let d = amounts("服务费分12期支付，每期金额相等。");
    assert!(
        !d.iter().any(|(k, _)| k == "服务费"),
        "12 期（序列面）不得提取为服务费金额: {d:?}"
    );
    // 守卫只加不减：真金额带元/万锚不受新守卫误伤
    let e = amounts("履约保证金金额为28万元，在签发验收证书后28工作日内退还。");
    assert!(
        e.iter().any(|(k, v)| k == "履约保证金" && v == "280000"),
        "带万真金额 28万 不得被工作日守卫误伤: {e:?}"
    );
}
