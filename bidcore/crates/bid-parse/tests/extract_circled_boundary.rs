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
//!   【交付前自查补记（诚实口径）】实测本输入修复后 REQ 总数=0：
//!   「支付合同金额100元。」是无编号普通行，抽取器无落账路径——
//!   与 #148 合入前 11bae540 同输入 requirements=[] 同口径，属**既有
//!   缺口**而非本修复新回归；不宣称「正确商务内容已保留」（见首测注释）。
//! - B：同一子项完整保留 2小时 与 360分钟 及各自约束短语，锚行逐行在位
//!   （OR 针命中不是完整语义——statement 与锚面都要全量核对）。
//!   【明示边界（支持范围）】吸收终点=**首个含量化的真实段落**（含其
//!   全部续行）；此前未结束段也吸收；已结束段落（段尾终结标点）与
//!   新子节/章头/同级新子项是绑定屏障（issue「不可跨已结束段落和新
//!   子节绑定」）。同子项**后续不同完整段**的条件不绑入头行 REQ——
//!   其普通行落账属上述既有缺口面，不在 #155 边界任务内扩面（防噪声）。
//! - 边界负例（交付前自查补）：同级新头（3）/章头/页码噪声（段中透明、
//!   不入 statement 与锚）/已结束段落屏障——见下方四测。
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

/// 带真实页号的行（页码噪声负例用——page_line_of 只认「第N页 行M」形态，
/// 无页号的 locator 判不出页码噪声）。
fn paged_line(idx: usize, page: u32, lno: u32, text: &str) -> Block {
    Block {
        idx,
        kind: BlockKind::PdfLine,
        locator: format!("第{page}页 行{lno}"),
        text: text.into(),
        cells: vec![],
    }
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
    // 【诚实口径（Lead 交付前自查）】本输入修复后 REQ 总数=0（探针实测）：
    // 「支付合同金额100元。」是无编号普通行，抽取器无 REQ 落账路径——
    // #148 合入前 11bae540 同输入 requirements=[]（issue #155 证据），
    // 属既有缺口而非本修复新回归。本修复的边界语义=消除 #148 的技术
    // 假阳性、恢复合入前不误抽行为；**不宣称商务内容已保留**。无编号
    // 普通量化行的落账面（商务/技术通用）为候选后续项，另行登记。
    assert!(
        !sts.iter().any(|(_, s)| s.contains("故障历时计算") && s.contains("100元")),
        "子项头与商务行不得绑定（上方主断言的同型直检）: {sts:?}"
    );
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

// ------------------------------------------- 边界负例（交付前自查补充）

/// 同级新子项头（3）边界：同列举簇的下一个子项是吸收终点——（2）不得
/// 吸入（3）头与其内容；（3）自身经同款头行吸收独立成 REQ（双向守卫：
/// 边界挡住旧子项越界 + 新子项不因边界而失活）。
#[test]
fn circled_head_absorb_stops_at_same_level_next_item() {
    let f = pf(vec![
        line(0, "第三章 采购需求"),
        line(1, "二、技术要求"),
        line(2, "（2）光缆线路故障历时计算："),
        line(3, "发生故障后2小时内到达现场，"),
        line(4, "要求单条光缆链路平均历时不得超过360分钟。"),
        line(5, "（3）光缆线路日常维护："),
        line(6, "维护周期不得超过30日历天。"),
    ]);
    let reqs = extract_requirements(&[f]);
    let sts = statements(&reqs);
    let (cat2, st2) = sts
        .iter()
        .find(|(_, s)| s.contains("故障历时计算"))
        .cloned()
        .unwrap_or_else(|| panic!("（2）子项头 REQ 应在位: {sts:?}"));
    assert_eq!(cat2, "技术参数");
    assert!(
        st2.contains("2小时") && st2.contains("360分钟"),
        "（2）自身内容完整: {st2}"
    );
    assert!(
        !st2.contains("日常维护") && !st2.contains("30日历天"),
        "（2）不得跨同级新头吸入（3）子项: {st2}"
    );
    let (cat3, st3) = sts
        .iter()
        .find(|(_, s)| s.contains("日常维护"))
        .cloned()
        .unwrap_or_else(|| {
            panic!("（3）子项头 REQ 应独立在位（边界挡吸收 ≠ 新子项失活）: {sts:?}")
        });
    assert_eq!(cat3, "技术参数");
    assert!(
        st3.contains("30日历天"),
        "（3）自身内容完整: {st3}"
    );
}

/// 章头边界：新章（第四章）内容不得被本章子项头吸收。
#[test]
fn circled_head_absorb_stops_at_chapter_head() {
    let f = pf(vec![
        line(0, "第三章 采购需求"),
        line(1, "二、技术要求"),
        line(2, "（2）光缆线路故障历时计算："),
        line(3, "发生故障后2小时内到达现场，"),
        line(4, "要求单条光缆链路平均历时不得超过360分钟。"),
        line(5, "第四章 合同条款"),
        line(6, "合同期限为12个月。"),
    ]);
    let reqs = extract_requirements(&[f]);
    let sts = statements(&reqs);
    let (_, st2) = sts
        .iter()
        .find(|(_, s)| s.contains("故障历时计算"))
        .cloned()
        .unwrap_or_else(|| panic!("（2）子项头 REQ 应在位: {sts:?}"));
    assert!(
        st2.contains("2小时") && st2.contains("360分钟"),
        "（2）自身内容完整: {st2}"
    );
    assert!(
        !st2.contains("合同条款") && !st2.contains("12个月"),
        "（2）不得跨章头吸入下一章内容: {st2}"
    );
}

/// 页码噪声段中透明（#450 B-18 同款纪律）：续行逗号后跨页——噪声行
/// 「— 2 —」不入 statement、不入锚，但**不截断**段落（续行 360分钟保留）。
#[test]
fn circled_head_absorb_page_noise_transparent_mid_paragraph() {
    let f = pf(vec![
        line(0, "第三章 采购需求"),
        line(1, "二、技术要求"),
        line(2, "（2）光缆线路故障历时计算："),
        line(3, "发生故障后2小时内到达现场，"),
        paged_line(4, 2, 1, "— 2 —"),
        line(5, "要求单条光缆链路平均历时不得超过360分钟。"),
    ]);
    let reqs = extract_requirements(&[f]);
    let sts = statements(&reqs);
    let (_, st2) = sts
        .iter()
        .find(|(_, s)| s.contains("故障历时计算"))
        .cloned()
        .unwrap_or_else(|| panic!("跨页续行子项 REQ 应在位: {sts:?}"));
    assert!(
        st2.contains("2小时") && st2.contains("360分钟"),
        "页码噪声不截断段落——跨页续行两量化值都在: {st2}"
    );
    assert!(
        !st2.contains("— 2 —") && !st2.contains("2 —"),
        "页码噪声不得混入 statement: {st2}"
    );
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
        !anchor_text.contains("— 2 —"),
        "页码噪声不得混入锚: {anchor_text}"
    );
    assert!(
        anchor_text.contains("不得超过360分钟"),
        "跨页续行内容锚在位: {anchor_text}"
    );
}

/// 明示边界（issue #155「不可跨已结束段落…绑定」）：同子项**后续不同
/// 完整段**（段尾句号各自终结）不绑入头行 REQ——首个含量化段吸收完毕
/// 即为子项正文终点。
/// 【诚实口径】后续完整段的量化条件（本例 360分钟）当前**无任何 REQ
/// 落账**——无编号普通行的既有缺口（与 A 反例商务行同类，11bae540 前
/// 同样不抽），非本修复新回归；候选后续面另行登记，不在 #155 内扩面。
#[test]
fn circled_head_absorb_never_binds_across_finished_paragraph() {
    let f = pf(vec![
        line(0, "第三章 采购需求"),
        line(1, "二、技术要求"),
        line(2, "（2）光缆线路故障历时计算："),
        line(3, "发生故障后2小时内到达现场。"),
        line(4, "要求单条光缆链路平均历时不得超过360分钟。"),
    ]);
    let reqs = extract_requirements(&[f]);
    let sts = statements(&reqs);
    let (_, st2) = sts
        .iter()
        .find(|(_, s)| s.contains("故障历时计算"))
        .cloned()
        .unwrap_or_else(|| panic!("首个量化段的子项 REQ 应在位: {sts:?}"));
    assert!(
        st2.contains("2小时") && !st2.contains("360分钟"),
        "已结束段落是绑定屏障——头行 REQ 只含首个量化段: {st2}"
    );
    // 屏障直检：任何 REQ 不得同时携带子项头与后续完整段内容
    // （跨已结束段落绑定的直接检测——与 A 测同型纪律）。
    assert!(
        !sts.iter()
            .any(|(_, s)| s.contains("故障历时计算") && s.contains("360分钟")),
        "子项头不得跨已结束段落绑定后续段: {sts:?}"
    );
}

// ---------------------------------------- #173：页界噪声紧随头行（残留边界收口）

/// #173（#145 残留登记）：圈号子项头行在**页尾**、量化正文在**次页**——
/// 中间隔页码噪声行。当前缺陷：吸收循环在 `page_noisy.contains(&k)` 处
/// break——噪声被当作吸收终点，整条子项丢 REQ（同簇（1）（5）量化同块
/// 时正常开 REQ——同型行为不一致）。
///
/// 复现形态（#145 评论 2026-11-13 17:32 登记的合成四块同构）：
/// ```text
/// （3）故障响应时限：
/// -第2页-          ← 页界噪声（页码行）
/// 自故障发生起算，要求平均响应时长≤30分钟。
/// ```
///
/// 验收（#173 issue 正文）：修复后 REQ 在位，statement 含头行与量化约束
/// 文本，锚逐行在位（头行锚 + 次页内容行锚），噪声行不入 statement、
/// 不入锚（#450 B-18「不吞不截不混」纪律）。
#[test]
fn circled_head_absorb_page_noise_transparent_after_head() {
    let f = pf(vec![
        paged_line(0, 1, 38, "第三章 采购需求"),
        paged_line(1, 1, 39, "二、技术要求"),
        paged_line(2, 1, 40, "（3）故障响应时限："),
        // 页界噪声：头行是本页最后一个真行，量化内容在次页
        paged_line(3, 2, 1, "-第2页-"),
        paged_line(4, 2, 2, "自故障发生起算，要求平均响应时长≤30分钟。"),
    ]);
    let reqs = extract_requirements(&[f]);
    let sts = statements(&reqs);
    let (cat, st3) = sts
        .iter()
        .find(|(_, s)| s.contains("故障响应时限"))
        .cloned()
        .unwrap_or_else(|| {
            panic!("页尾头行+次页量化的子项 REQ 应在位（#173 修复面）: {sts:?}")
        });
    assert_eq!(cat, "技术参数", "子项头 REQ 归属技术参数: {cat}");
    assert!(
        st3.contains("故障响应时限") && st3.contains("平均响应时长≤30分钟"),
        "头行与次页量化约束都必须在 statement 中（不吞）: {st3}"
    );
    assert!(
        !st3.contains("第2页") && !st3.contains("2页-"),
        "页码噪声不得混入 statement（不混）: {st3}"
    );
    // 锚面：头行锚 + 次页内容行锚逐行在位，噪声行无锚
    let head_req = reqs
        .iter()
        .find(|r| {
            r.params
                .get("statement")
                .and_then(|v| v.as_str())
                .map(|s| s.contains("故障响应时限"))
                .unwrap_or(false)
        })
        .expect("子项头 REQ 应在位");
    let anchor_text: String = head_req.anchors.iter().map(|a| a.excerpt.as_str()).collect();
    assert!(
        anchor_text.contains("（3）故障响应时限"),
        "头行锚在位: {anchor_text}"
    );
    assert!(
        anchor_text.contains("平均响应时长≤30分钟"),
        "次页内容行锚在位（不截）: {anchor_text}"
    );
    assert!(
        !anchor_text.contains("第2页") && !anchor_text.contains("2页-"),
        "页码噪声不得混入锚（不混）: {anchor_text}"
    );
}

/// #173 纵深负例：头行页尾 + 噪声 + 次页是**结构边界**（新子节头）——
/// 透明穿越不得把边界判据也穿掉：噪声后的首个真行仍按边界全集判定，
/// 吸收必须停（不因穿越而跨节吸收——#155-A 语义保持）。
#[test]
fn circled_head_absorb_page_noise_traversal_still_stops_at_structural_boundary() {
    let f = pf(vec![
        paged_line(0, 1, 38, "第三章 采购需求"),
        paged_line(1, 1, 39, "二、技术要求"),
        paged_line(2, 1, 40, "（3）故障响应时限："),
        paged_line(3, 2, 1, "-第2页-"),
        // 次页首行是新子节头——结构边界，不是可吸收正文
        paged_line(4, 2, 2, "三、商务要求"),
        paged_line(5, 2, 3, "支付合同金额100元。"),
    ]);
    let reqs = extract_requirements(&[f]);
    let sts = statements(&reqs);
    // 穿越后的边界判据保持：无量化形态 → 头行不开 REQ（零激活纪律），
    // 且不得跨节吸收商务量化行（#155-A 反例的跨页变体）。
    assert!(
        !sts.iter()
            .any(|(_, s)| s.contains("故障响应时限") && (s.contains("商务要求") || s.contains("100元"))),
        "噪声穿越不得绕过结构边界——子项头不得跨节吸收: {sts:?}"
    );
    assert!(
        !sts.iter().any(|(c, s)| c == "技术参数" && s.contains("100元")),
        "商务量化内容不得经噪声穿越误归属技术参数: {sts:?}"
    );
}
