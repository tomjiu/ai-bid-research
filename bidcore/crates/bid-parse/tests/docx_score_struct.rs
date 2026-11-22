//! #178（AUD2 F-4）：DOCX 评分表行分值结构化——回归锁。
//!
//! 真实 DOCX 主件评分项 REQ 零 params.score（unicom 0/18、huaian 0/28
//! ——audit/multifile-acceptance §5）→ 分值驱动配额（HIS-A1/#131
//! Track::Scoring）在真实 DOCX 项目无从触发。修复后 DOCX 面两处补
//! 分值入参：编号行评分分支（括注形「（25分 技术评审）」）+ #175 延迟
//! 候选补开面（表格分值列 join 形态）。
//!
//! #178 收口轮（分值独立列形态）：huaian 评标办法前附表·详细评审区
//! 六列对齐表（评审内容|评分因素|分值|评分标准）——review_table 表头
//! 识别收录「评分因素」变体后，14 条评分项带独立列分值（合计 = 满分
//! 100），不良行为「-」行明示无分值。unicom 面分值在附件
//! 详细评审表.xlsx（引擎拒收 = #176 跨仓面，此处锁「不变」防误动）。

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

// ================= #178 收口轮：真实件「分值独立列」形态 =================

fn telecom_dir() -> std::path::PathBuf {
    std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("../../../real-corpus/telecom/parse-input")
}

/// huaian 真实主件：评标办法前附表·详细评审区（六列对齐表）14 条评分项
/// 从分值独立列取数（合计 = 满分 100），不良行为「-」行明示无分值。
/// 修复前（PR #172 §5 实测）：评分项 0/28 带分值。
#[test]
fn huaian_real_scoring_table_carries_scores() {
    let path = telecom_dir().join("A-telecom-huaian-主文件.docx");
    assert!(
        path.exists(),
        "缺少真件夹具 {}（不能静默通过）",
        path.display()
    );
    let pf = bid_engine::parse_docx_via_engine(&path).expect("huaian 解析");
    let reqs = extract_requirements(&[pf]);
    let table_rows: Vec<&bid_domain::Requirement> = reqs
        .iter()
        .filter(|r| {
            r.category == "评分项"
                && r.clause_no
                    .as_deref()
                    .is_some_and(|c| c.starts_with("评标办法前附表-"))
        })
        .collect();
    assert_eq!(
        table_rows.len(),
        15,
        "详细评审区 14 评分行 + 1 不良行为行：{:?}",
        table_rows.iter().map(|r| &r.clause_no).collect::<Vec<_>>()
    );
    let scored: Vec<i64> = table_rows
        .iter()
        .filter_map(|r| r.params.get("score").and_then(|v| v.as_i64()))
        .collect();
    assert_eq!(scored.len(), 14, "14 条带独立列分值（「-」行无分值）");
    // 分值合计 = 满分 100（商务 12 + 技术服务 28 + 价格 60——件内
    // 「分值构成」自述口径，数值自证）
    assert_eq!(scored.iter().sum::<i64>(), 100, "分值列合计应等于满分");
    // 逐项形态（组名小计「（12分）」不得顶替行分值——行分值 6 在场）
    assert!(scored.contains(&6), "类似业绩 6 分");
    assert!(scored.contains(&4), "管理能力 4 分");
    assert!(scored.contains(&2), "投标文件质量/空间压降/免重构 2 分");
    assert!(scored.contains(&60), "价格分 60 分");
    // 不良行为行：明示「-」→ 评分项在场但无分值（不为它编造分数）
    let dash_row = table_rows
        .iter()
        .find(|r| !r.params.contains_key("score"))
        .expect("「-」行应保留为无分值评分项");
    assert!(
        dash_row
            .anchors
            .first()
            .map(|a| a.excerpt.contains("不良行为"))
            .unwrap_or(false),
        "无分值行应是不良行为行：{:?}",
        dash_row.clause_no
    );
    // 分值 JSON 口径：整数 i64（矩阵 as_i64 消费面——#178 口径统一）
    assert!(
        table_rows
            .iter()
            .filter(|r| r.params.contains_key("score"))
            .all(|r| r.params.get("score").unwrap().is_i64()),
        "全部行分值落 i64"
    );
    // 评分细则随行（score_rules 承载细则文本——结构化切分验收项）
    assert!(
        table_rows
            .iter()
            .filter(|r| r.params.contains_key("score_rules"))
            .count()
            >= 14,
        "评分标准列应随行入 params.score_rules"
    );
}

/// unicom 真实主件：分值在附件「详细评审表.xlsx」（引擎拒收 = #176
/// 跨仓面）——DOCX 侧评分项 18 条保持 0 分值。锁「不变」防误动：
/// 本修复只收「评分因素+分值列」对齐形态，unicom「条款内容|评分因素」
/// 无分值列，不触。
#[test]
fn unicom_real_scoring_unchanged_pending_xlsx() {
    let path = telecom_dir().join("A-unicom-ry-2026CUC-RJY-PT0783-招标文件.docx");
    assert!(
        path.exists(),
        "缺少真件夹具 {}（不能静默通过）",
        path.display()
    );
    let pf = bid_engine::parse_docx_via_engine(&path).expect("unicom 解析");
    let reqs = extract_requirements(&[pf]);
    let scoring: Vec<&bid_domain::Requirement> = reqs
        .iter()
        .filter(|r| r.category == "评分项")
        .collect();
    assert_eq!(scoring.len(), 18, "unicom 评分项计数不变（PR #172 §5 口径）");
    assert!(
        scoring.iter().all(|r| !r.params.contains_key("score")),
        "unicom DOCX 面仍零分值——分值解锁依赖 #176（xlsx 引擎容错）"
    );
}
