//! #133 A2：预算上下文元计价金额——recommend 预算规模因子的信号馈给面。
//!
//! 背景（审计 AUD2-HIS-A2 修复前置）：真件（松岭 232762 / hq-dev）预算
//! 写作「4.预算⾦额： 1,195,800.00元」——元计价 + 千分位逗号，既有
//! 「X万元」模式（re_amount）不命中 → recommend_length_profile 的预算
//! 规模因子在这类件上无信号（工具层 signals.budget_yuan = null）。
//!
//! 本文件锁两道面：
//! - 纯函数面 `budget_yuan_wan`：预算/控制价/最高限价上下文命中 + 任意
//!   价格不误配（代理服务费/营业额/报价上限污染防）；
//! - 抽取面 fill_params：编号条款带预算元计价 → params.amount_wan（万元
//!   口径一致）；万元形态优先（同文本两形态并存）。

use bid_parse::extract::{budget_yuan_wan, extract_requirements};
use bid_parse::{Block, BlockKind, ParsedFile};

fn pf(blocks: Vec<Block>) -> ParsedFile {
    ParsedFile {
        name: "A-test.pdf".to_string(),
        sha256: "test".into(),
        pages: 1,
        tables: 0,
        has_text_layer: true,
        ocr_blocks: 0,
        blocks,
        parse_summary: "test".into(),
        components: vec![],
    }
}

fn line(idx: usize, locator: &str, text: &str) -> Block {
    Block { idx, kind: BlockKind::PdfLine, locator: locator.into(), text: text.into(), cells: vec![] }
}

/// 纯函数面：预算上下文元计价命中（松岭/hq-dev 实测形态）。
#[test]
fn budget_yuan_wan_hits_budget_context() {
    // 松岭真件形态（⾦为康熙部首区兼容字——预算上下文不受字形变体影响）
    assert_eq!(
        budget_yuan_wan("4.预算⾦额： 1,195,800.00元"),
        Some(119.58),
        "松岭预算行（元计价 + 千分位逗号 + ⾦字形变体）"
    );
    // hq-dev 真件形态
    assert_eq!(budget_yuan_wan("4.预算⾦额： 1,518,750.00元"), Some(151.875));
    // 控制价/最高限价上下文
    assert_eq!(budget_yuan_wan("本项目控制价：2,000,000元"), Some(200.0));
    assert_eq!(budget_yuan_wan("分包最高限价 500,000.00 元"), Some(50.0));
    // 万元值含小数（浮点近似比较——千分位剥离与 ÷10⁴ 的二进制误差容）
    let v = budget_yuan_wan("预算金额：99,999.99元").unwrap();
    assert!((v - 9.999999).abs() < 1e-9, "{v}");
}

/// 纯函数面：无预算上下文的任意价格不误配（污染防——规模因子信号
/// 一旦被价格污染会把大项目误判小项目、小项目误判大项目）。
#[test]
fn budget_yuan_wan_rejects_non_budget_prices() {
    // 代理服务费（真件实测形态：松岭「代理服务费：20000元」）
    assert_eq!(budget_yuan_wan("本项目代理服务费：20000元（贰万元整）"), None);
    // 营业额划型（万元形态的价格不在此面——由 re_amount 承载，且无预算上下文）
    assert_eq!(budget_yuan_wan("营业收入为3000万元以上，资产总额为5000万元"), None);
    // 报价上限类（无预算/控制价/最高限价锚词）
    assert_eq!(budget_yuan_wan("单台设备报价不得超过 50,000 元"), None);
    // 保证金（真件形态「投标保证金：20,000元」）
    assert_eq!(budget_yuan_wan("投标保证⾦的数额 20,000 元"), None);
    // 表头形态（无元尾缀——如实登记的限制面，提取层表格面后续立项）
    assert_eq!(budget_yuan_wan("预算⾦额（元）1,195,800.00"), None);
}

/// 抽取面：编号条款（fill_params 面）带预算元计价 → params.amount_wan。
#[test]
fn numbered_clause_budget_yuan_prices_amount_wan() {
    let f = pf(vec![
        line(0, "第1页 行1", "第一章 投标邀请"),
        line(1, "第1页 行2", "4.2 预算⾦额： 1,195,800.00元，报价超预算作无效标处理。"),
    ]);
    let reqs = extract_requirements(&[f]);
    let hit = reqs
        .iter()
        .find(|r| r.params.get("amount_wan").is_some())
        .unwrap_or_else(|| panic!("预算条款应携带 amount_wan: {reqs:?}"));
    let wan = hit.params.get("amount_wan").and_then(|v| v.as_f64()).unwrap();
    assert!(
        (wan - 119.58).abs() < 1e-6,
        "amount_wan 万元口径一致（1,195,800 元 = 119.58 万）: {wan}"
    );
}

/// 抽取面：万元形态优先（同文本两形态并存且值不同——万元面获胜，
/// budget_yuan 兑底面不得覆盖既有 re_amount 语义）。
#[test]
fn wan_form_takes_priority_over_budget_yuan() {
    let f = pf(vec![
        line(0, "第1页 行1", "第一章 投标邀请"),
        line(1, "第1页 行2", "4.3 预算⾦额：300万元（最高限价 2,800,000元）。"),
    ]);
    let reqs = extract_requirements(&[f]);
    let hit = reqs
        .iter()
        .find(|r| r.params.get("amount_wan").is_some())
        .unwrap_or_else(|| panic!("应携带 amount_wan: {reqs:?}"));
    let wan = hit.params.get("amount_wan").and_then(|v| v.as_f64()).unwrap();
    assert_eq!(wan, 300.0, "万元形态优先（300 万而非兑底面 280 万）");
}
