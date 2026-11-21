//! #178（AUD2 F-4）：DOCX 评分表行分值结构化——回归锁。
//!
//! 真实 DOCX 主件评分项 REQ 零 params.score（unicom 0/18、huaian 0/28
//! ——audit/multifile-acceptance §5）→ 分值驱动配额（HIS-A1/#131
//! Track::Scoring）在真实 DOCX 项目无从触发。修复后 DOCX 面两处补
//! 分值入参：编号行评分分支（括注形「（25分 技术评审）」）+ #175 延迟
//! 候选补开面（表格分值列 join 形态）。
//!
//! 注：unicom/huaian 素材不在仓（多文件验收外部素材）——本文件用构造
//! 形态锁行为面；真实件可达性以 docx-jlyh（真实 DOCX 主件）抽样验证，
//! 正式逐项验收归 #113 真实起草线。

use bid_parse::extract::extract_requirements;
use bid_parse::{Block, BlockKind, ParsedFile};

fn docx_pf(blocks: Vec<Block>) -> ParsedFile {
    ParsedFile {
        name: "A-test.docx".to_string(),
        sha256: "test".into(),
        pages: 1,
        tables: 1,
        has_text_layer: true,
        ocr_blocks: 0,
        blocks,
        parse_summary: "test".into(),
        components: vec![],
    }
}

fn para(idx: usize, locator: &str, text: &str) -> Block {
    Block { idx, kind: BlockKind::Para, locator: locator.into(), text: text.into(), cells: vec![] }
}

fn trow(idx: usize, locator: &str, text: &str, cells: &[&str]) -> Block {
    Block {
        idx,
        kind: BlockKind::TableRow,
        locator: locator.into(),
        text: text.into(),
        cells: cells.iter().map(|s| s.to_string()).collect(),
    }
}

fn score_of(reqs: &[bid_domain::Requirement], clause: &str) -> Option<serde_json::Value> {
    reqs.iter()
        .find(|r| r.clause_no.as_deref() == Some(clause))
        .and_then(|r| r.params.get("score").cloned())
}

/// 括注形分值：编号行「服务方案（25分 技术评审）：…」→ params.score=25。
#[test]
fn numbered_scoring_row_carries_paren_score() {
    let f = docx_pf(vec![
        para(0, "第三章 评标办法", "第三章 评标办法"),
        para(1, "第三章 评标办法 > 1.详细评审", "5.1 服务方案（25分 技术评审）：供应商需提供服务方案全文。"),
    ]);
    let reqs = extract_requirements(&[f]);
    let sc = score_of(&reqs, "5.1")
        .unwrap_or_else(|| panic!("5.1 评分行须携带 params.score（实得 REQ：{:?}）",
            reqs.iter().map(|r| (&r.clause_no, &r.category)).collect::<Vec<_>>()));
    assert_eq!(sc, serde_json::json!(25), "整数分值落 i64（矩阵 as_i64 口径）");
}

/// 小数分值形态：「（2.5分 …）」→ f64。
#[test]
fn fractional_score_keeps_f64() {
    let f = docx_pf(vec![
        para(0, "第三章 评标办法", "第三章 评标办法"),
        para(1, "第三章 评标办法 > 1.详细评审", "6.2 响应速度（2.5分 技术评审）：按响应时限评分。"),
    ]);
    let reqs = extract_requirements(&[f]);
    let sc = score_of(&reqs, "6.2").expect("6.2 须携带分值");
    assert_eq!(sc, serde_json::json!(2.5), "小数分值保 f64");
}

/// 表格行（#175 延迟候选面）：评分表行「7.1 名称+分值列 join」→ 分值入参。
#[test]
fn deferred_scoring_table_row_carries_score() {
    let f = docx_pf(vec![
        para(0, "第三章 评标办法", "第三章 评标办法"),
        trow(
            1,
            "第三章 评标办法 评分表 行1",
            "7.1 实施方案（30分 技术评审）根据项目特点制定",
            &["7.1", "实施方案（30分 技术评审）", "根据项目特点制定"],
        ),
    ]);
    let reqs = extract_requirements(&[f]);
    let sc = score_of(&reqs, "7.1")
        .unwrap_or_else(|| panic!("7.1 表格评分行须携带分值（实得 {:?}）",
            reqs.iter().map(|r| (&r.clause_no, &r.category, r.params.keys().collect::<Vec<_>>())).collect::<Vec<_>>()));
    assert_eq!(sc, serde_json::json!(30));
}

/// 非评分章的分值提及（正文「扣 1 分」类）不产 score——分支只在
/// 评分章上下文锁评分项时入参。
#[test]
fn non_scoring_chapter_does_not_carry_score() {
    let f = docx_pf(vec![
        para(0, "第二章 投标人须知", "第二章 投标人须知"),
        para(1, "第二章 投标人须知 > 3.其他", "8.1 逾期送达的，每延误一日按 1 分扣减。"),
    ]);
    let reqs = extract_requirements(&[f]);
    assert!(
        score_of(&reqs, "8.1").is_none(),
        "非评分章不产 params.score（防分值污染）"
    );
}
