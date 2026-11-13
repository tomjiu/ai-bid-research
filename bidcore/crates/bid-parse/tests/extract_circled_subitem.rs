//! #145：圈号子项（N）段落开条款一致性——松岭 GR-004 块级根因的最小复现。
//!
//! 复现（#112 复验报告 §4 / issue #145 正文）：松岭技术章「3、光缆传输链路
//! 完好率」的三个同型圈号子项：
//! - （1）头行 + 量化**同块**（「（1）…完好率≥95% 。」）→ 现状开 REQ（#266-C
//!   分支：re_list_cn 头 + re_quantified 同段命中）；
//! - （2）头行「（2）光缆线路故障历时计算：」**独立段**（尾冒号自成段），
//!   量化在**后行**（「要求单条光缆链路平均历时≤360分钟。」）→ 现状
//!   两半各缺其一（头行无量化 / 内容行无圈号头）→ 整条丢弃（GR-004 漏抽）；
//! - （5）同块形态 → 现状开 REQ。
//!
//! 修复语义（一致性）：列举簇内的圈号子项**头行**未独立成条款时，其
//! 「头 + 紧邻内容行」按同一子项合并判定——量化形态跨行在场即开 REQ
//! （锚逐行保真——与既有 para_anchors 纪律一致）。
//!
//! 验收（issue #145）：同型三子项（1）（2）（5）必同开 REQ；松岭重跑
//! 16/16（songling_baseline 三态门收敛归 manifest 刷新——另 PR 面）。

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

fn tech_texts(reqs: &[bid_domain::Requirement]) -> Vec<String> {
    reqs.iter()
        .filter(|r| r.category == "技术参数")
        .map(|r| r.anchors.iter().map(|a| a.excerpt.clone()).collect::<String>())
        .collect()
}

#[test]
fn circled_subitem_head_split_from_quantified_body_not_dropped() {
    // 松岭第 17-18 页技术章形态（康熙部首如实保留——解析面 NFKC 归一在位）：
    let f = pf(vec![
        line(0, "第三章 采购需求"),
        line(1, "二、技术要求"),
        line(2, "3、光缆链路完好率："),
        // （1）头 + 量化同块 → 现状即开（对照锚）
        line(3, "（1） 以承载监控点位的光缆链路条数为单位，每⽉进⾏考核，光缆链路完好率≥95% 。"),
        // （2）头行独立段（尾冒号）+ 内容行（量化在其中）——本修复面
        line(4, "（2）光缆线路故障历时计算："),
        line(5, "光缆线路故障历时从线路故障发⽣开始计算，⾄线路修复或倒通并经传输设备现场维护部⻔验证"),
        line(6, "可⽤时为⽌，要求单条光缆链路平均历时≤360分钟。计量单位为“分钟”。"),
        // （5）同块形态 → 现状即开（对照锚）
        line(7, "（5）接头损耗不大于0.1dB/个。"),
    ]);
    let reqs = extract_requirements(&[f]);
    let techs = tech_texts(&reqs);
    // 三子项同开（一致性验收——issue #145 正文「同型（1）（5）开 REQ 唯（2）被丢」）
    assert!(
        techs.iter().any(|t| t.contains("95%")),
        "（1）同块形态在位: {techs:?}"
    );
    assert!(
        techs.iter().any(|t| t.contains("360分钟") || t.contains("360")),
        "（2）头/内容分行形态不再丢弃（GR-004——漏响应风险）: {techs:?}"
    );
    assert!(
        techs.iter().any(|t| t.contains("0.1dB")),
        "（5）同块形态在位: {techs:?}"
    );
}

#[test]
fn circled_subitem_plain_head_without_quantified_stays_silent() {
    // 零激活纪律：无量化形态的子项头行（纯文字子项——非本修复面）
    // 保持现状（不新增噪声——修复只对「量化跨行在场」激活）。
    let f = pf(vec![
        line(0, "第三章 采购需求"),
        line(1, "二、技术要求"),
        line(2, "（1）服务响应承诺按合同条款执行："),
        line(3, "由双方另行协商确定具体响应流程。"),
    ]);
    let reqs = extract_requirements(&[f]);
    assert!(
        !tech_texts(&reqs).iter().any(|t| t.contains("响应承诺")),
        "无量化形态不激活（零新增噪声）: {reqs:?}"
    );
}
