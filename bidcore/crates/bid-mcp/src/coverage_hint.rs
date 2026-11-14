//! coverage_hint.rs —— #153：map_scoring_item 响应的覆盖面即时提示。
//!
//! 门 1h 数据源（`bid_tools::scoring_wire::build_scorer` 单一真源——与
//! `validate::unmapped_scoring_findings` / score_document 的 unmapped 面
//! 恒同口径）的轻量计数面：映射后「还差几个评分项」即时反馈，Agent 不必
//! 再调一次 check_scoring_coverage 才知道闭环没闭环。

use bid_domain::DomainStore;

/// 未映射评分项计数（0 = 门 1h 零豁免放行的数据面）。
pub fn unmapped_scoring_count(store: &DomainStore) -> usize {
    let (scorer, _items, _ledger_effective) = bid_tools::scoring_wire::build_scorer(store);
    scorer.unmapped_items().len()
}
