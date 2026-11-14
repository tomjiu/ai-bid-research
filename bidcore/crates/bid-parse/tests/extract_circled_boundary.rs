//! #155：圈号子项头吸收的边界回归——跨节误归属（A）与首量化截断（B）。
//!
//! 复现（issue #155 正文，复验版本 main 5d1ad697 = PR #148 合入后）：
//! - **A 跨节吸收**：`circled_head_absorb` 边界集缺 re_subsection/段落完整性
//!   判断——子项头「（2）光缆线路故障历时计算：」跨过已结束句与新子节头
//!   「三、商务要求」吸收商务量化行「支付合同金额100元。」，产出一条
//!   statement 含整个商务节的技术参数（假阳性；合并前 11bae540 同输入
//!   requirements=[]）。
//! - **B 首量化截断**：吸收循环 `re_quantified` 首次命中即 return——
//!   「（2）头 + 2小时行 + 360分钟行」只保留 2小时，同子项的
//!   「不得超过360分钟」整行丢失（#145 修复仍不完整）。
//!
//! 修复语义（#155 任务原文）：按**真实段落**、章/节、同级列举边界吸收
//! 整个子项，不以首个数值作为正文终点；不可跨已结束段落和新子节绑定。
//!
//! 验收（issue #155）：
//! - A：无商务 100 元被技术头吸收；商务内容只在正确归属下保留
//!   （任何含「100元」的 REQ 不得是技术参数——允许其为商务面 REQ）。
//! - B：同一子项完整保留 2小时 与 360分钟 及各自约束短语，锚行逐行在位
//!   （OR 针命中不是完整语义——statement 与锚面都要全量核对）。
//! - 原 #145 最小两例（tests/extract_circled_subitem.rs）与真实松岭
//!   基线不回归（另面复跑）。

use bid_parse::extract::extract_requirements;
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

fn line(idx: usize, text: &str) -> Block {
    Block { idx, kind: BlockKind::PdfLine, locator: format!("l{idx}"), text: text.into(), cells: vec![] }
}

/// 全类别 REQ 的 (category, statement) 面——误归属断言用（不限于技术参数）。
fn statements(reqs: &[bid_domain::Requirement]) -> Vec<(String, String)> {
    reqs.iter()
        .map(|r| {
            let st = r
                .params
                .get("statement")
                .and_then(|v| v.as_str())
                .unwrap_or("")
                .to_string();
            (r.category.clone(), st)
        })
        .collect()
}

// ---------------------------------------------------------------- A：跨节吸收

/// issue #155 反例 A 原文形态：子项头 → 无量化完整句 → 新子节头 → 商务量化行。
/// 当前缺陷：技术参数 statement 吸入「三、商务要求」+「100元」。
#[test]
fn circled_head_absorb_must_not_cross_into_next_subsection() {
    let f = pf(vec![
        line(0, "第三章 采购需求"),
        line(1, "二、技术要求"),
        line(2, "（2）光缆线路故障历时计算："),
        line(3, "由双方另行协商确定。"),
        line(4, "三、商务要求"),
        line(5, "支付合同金额100元。"),
    ]);
    let reqs = extract_requirements(&[f]);
    let sts = statements(&reqs);
    // 验收 A：无商务 100 元被技术头吸收——技术参数面不得含 100元。
    assert!(
        !sts.iter().any(|(c, s)| c == "技术参数" && s.contains("100元")),
        "技术参数不得吸收商务 100 元（跨节误归属）: {sts:?}"
    );
    // 边界完整性：任何 REQ 不得同时携带技术子项头与新子节头/商务正文
    // （跨节绑定的直接检测——不依赖类别裁决）。
    assert!(
        !sts.iter()
            .any(|(_, s)| s.contains("故障历时计算") && (s.contains("商务要求") || s.contains("100元"))),
        "子项头与商务节内容不得绑定进同一 REQ: {sts:?}"
    );
    // 正确归属守卫：含 100元 的 REQ（若在）必须是商务面——非技术参数。
    if let Some((c, s)) = sts.iter().find(|(_, s)| s.contains("100元")) {
        assert_ne!(
            c, "技术参数",
            "商务量化内容误归属技术参数: {c} / {s}"
        );
    }
}

/// A 的纵深防御（无子节头标记形态）：已结束段落（段尾终结标点）无量化
/// → 吸收必须停在本段，不得跨段绑定后续正文行（#155「不可跨已结束
/// 段落绑定」——即使下一节没有显式子节头）。
#[test]
fn circled_head_absorb_stops_at_finished_unquantified_paragraph() {
    let f = pf(vec![
        line(0, "第三章 采购需求"),
        line(1, "二、技术要求"),
        line(2, "（2）光缆线路故障历时计算："),
        line(3, "由双方另行协商确定。"),
        // 无「三、商务要求」标记——正文行直接跟在已结束句后
        line(4, "支付合同金额100元。"),
    ]);
    let reqs = extract_requirements(&[f]);
    let sts = statements(&reqs);
    assert!(
        !sts.iter().any(|(c, s)| c == "技术参数" && s.contains("100元")),
        "已结束段落后的正文行不得被技术头跨段吸收: {sts:?}"
    );
    assert!(
        !sts.iter()
            .any(|(_, s)| s.contains("故障历时计算") && s.contains("100元")),
        "子项头不得跨已结束段落绑定后续行: {sts:?}"
    );
}

// ---------------------------------------------------------------- B：首量化截断

/// issue #155 反例 B 原文形态：子项头 → 量化行（2小时，行尾逗号＝续行）
/// → 同段量化行（360分钟）。当前缺陷：首量化命中即返回，360 分钟丢失。
#[test]
fn circled_head_absorb_keeps_all_quantifications_of_same_subitem() {
    let f = pf(vec![
        line(0, "第三章 采购需求"),
        line(1, "二、技术要求"),
        line(2, "（2）光缆线路故障历时计算："),
        line(3, "发生故障后2小时内到达现场，"),
        line(4, "要求单条光缆链路平均历时不得超过360分钟。"),
    ]);
    let reqs = extract_requirements(&[f]);
    let sts = statements(&reqs);
    // 验收 B：同一子项完整保留 2小时 与 360分钟（不以首个数值为终点）。
    let Some((cat, st)) = sts
        .iter()
        .find(|(_, s)| s.contains("故障历时计算"))
        .cloned()
    else {
        panic!("子项头 REQ 应在位（#145 面不回归）: {sts:?}")
    };
    assert_eq!(cat, "技术参数", "子项头 REQ 归属技术参数: {cat}");
    assert!(
        st.contains("2小时") && st.contains("360分钟"),
        "同一子项的两个量化值必须都在 statement 中: {st}"
    );
    // 「及各自约束」：比较关系/约束短语逐项核对（OR 针命中不是完整语义）。
    assert!(
        st.contains("发生故障后2小时内到达现场"),
        "2小时 的约束短语（响应时限）必须完整保留: {st}"
    );
    assert!(
        st.contains("不得超过360分钟"),
        "360分钟 的比较关系（不得超过）必须完整保留: {st}"
    );
    // 锚行逐行在位：头行 + 两个内容行（锚面全量——防 statement 拼接但锚缺行）。
    let head_req = reqs
        .iter()
        .find(|r| {
            r.params
                .get("statement")
                .and_then(|v| v.as_str())
                .map(|s| s.contains("故障历时计算"))
                .unwrap_or(false)
        })
        .expect("子项头 REQ 应在位");
    let anchor_text: String = head_req.anchors.iter().map(|a| a.excerpt.as_str()).collect();
    assert!(
        anchor_text.contains("（2）光缆线路故障历时计算"),
        "头行锚在位: {anchor_text}"
    );
    assert!(
        anchor_text.contains("发生故障后2小时内到达现场"),
        "2小时 内容行锚在位: {anchor_text}"
    );
    assert!(
        anchor_text.contains("不得超过360分钟"),
        "360分钟 内容行锚在位: {anchor_text}"
    );
}
