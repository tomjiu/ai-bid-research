//! P0-A（issue #35）：PDF 行级碎片修复 集成测试。
//!
//! 基线实锤（veto-measure 口径）：PDF 组 L1 0.4680 / L2 0.1148——
//! pdftotext 按物理行切块，否决条款被切成两三行后词表跨行失配；
//! 无编号普通条款不抽；词表缺「拒收/不予受理」面。本文件锁定：
//! - 段落重组（行尾无标点续行 / 行尾截断 / 短行碎片）
//! - 断段（编号新条款/章节头前断段）
//! - 词表扩展（拒收/不予受理/否决条件…）
//! - 例外从句排除（除…外）
//! - 语境传播（总括句 → 圈号列举继承；流程步骤排除）
//! - 评分结构行排除（分值聚集非否决）
//! - 幂等

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

fn line(idx: usize, locator: &str, text: &str) -> Block {
    Block { idx, kind: BlockKind::PdfLine, locator: locator.into(), text: text.into(), cells: vec![] }
}

fn cats(reqs: &[bid_domain::Requirement]) -> Vec<String> {
    reqs.iter().map(|r| r.category.clone()).collect()
}

fn veto_excerpts(reqs: &[bid_domain::Requirement]) -> Vec<String> {
    reqs.iter()
        .filter(|r| r.category == "否决项")
        .map(|r| r.anchors.iter().map(|a| a.excerpt.clone()).collect::<String>())
        .collect()
}

/// 段落重组：否决词被行尾切断（「…招标人」+「拒收投标文件。」）→ 整段判定命中。
#[test]
fn para_reassembly_cross_line_veto() {
    let f = pf(vec![
        line(0, "第6页 行1", "1.4.3 未提交有效凭证的，招标人"),
        line(1, "第6页 行2", "拒收投标文件。"),
    ]);
    let reqs = extract_requirements(&[f]);
    let vetos = veto_excerpts(&reqs);
    assert_eq!(vetos.len(), 1, "跨行否决条款应整段命中: {reqs:?}");
    // anchors 覆盖两行（excerpt 保真）
    assert!(vetos[0].contains("招标人"));
    assert!(vetos[0].contains("拒收投标文件"));
}

/// 段落重组：短行碎片（「拒收。」独立成行）——段落 REQ 覆盖全行
/// anchors；超短尾行（<6 字）保留独立碎片 REQ（GT 单行条款锚定面）。
///
/// #226 层 2 后文本改版：原文本「逾期送达…招标人将拒收」是规则说明形
/// （issue REQ-0007 同款），段落 REQ 不再落否决项——重组行为面改用非
/// 规则语境的否决句验证（意图不变：跨行否决词还原为整段判定）。
#[test]
fn para_reassembly_short_fragment() {
    let f = pf(vec![
        line(0, "第10页 行9", "未按要求密封的投标文件，评标委员会将"),
        line(1, "第10页 行10", "拒收。"),
    ]);
    let reqs = extract_requirements(&[f]);
    // 段落 REQ：两行 anchors，分类否决
    let para_req = reqs.iter().find(|r| r.anchors.len() == 2);
    assert!(para_req.is_some(), "段落 REQ 应覆盖两行: {reqs:?}");
    assert_eq!(para_req.unwrap().category, "否决项");
    // 超短尾行独立碎片 REQ（「拒收。」）
    assert!(reqs.iter().any(|r| r.anchors.len() == 1
        && r.anchors[0].excerpt == "拒收。"));

    // #226 集成面登记：规则说明形（逾期送达 + 招标人拒收）不再产否决 REQ
    let f2 = pf(vec![
        line(0, "第10页 行9", "逾期送达的投标文件的，招标人将"),
        line(1, "第10页 行10", "拒收。"),
    ]);
    let reqs2 = extract_requirements(&[f2]);
    assert!(
        reqs2.iter().all(|r| r.anchors.len() != 2 || r.category != "否决项"),
        "#226 规则说明形段落不落否决项: {reqs2:?}"
    );
}

/// 断段：行尾有终结标点 + 下一行是编号新条款 → 各自成段。
#[test]
fn para_break_on_new_clause() {
    let f = pf(vec![
        line(0, "第6页 行1", "3.4.2 投标人未提供有效营业执照的，其投标将被否决。"),
        line(1, "第6页 行2", "3.4.3 投标人须具备水利水电工程施工总承包贰级资质。"),
    ]);
    let reqs = extract_requirements(&[f]);
    assert_eq!(cats(&reqs), vec!["否决项".to_string(), "资格条件".to_string()]);
}

/// 词表扩展：拒收/否决条件面（#226 层 2 后，「招标人不予受理」形程序
/// 后果条款不再落否决项——见 veto_rule.rs；这里验证词表在非规则语境下
/// 仍命中，并集成面登记规则说明形的降级）。
#[test]
fn expanded_veto_lexicon() {
    // 评委处置形（非「招标人/逾期」规则语境）——词面命中且保留否决
    let f = pf(vec![
        line(0, "第14页 行37", "未按本章第 4.1.1 项要求密封的，评标委员会将予以拒收。"),
    ]);
    let reqs = extract_requirements(&[f]);
    assert_eq!(veto_excerpts(&reqs).len(), 1, "评委拒收形仍否决: {reqs:?}");

    // #226 集成面登记：程序后果条款（招标人不予受理）不产否决 REQ
    let f2 = pf(vec![
        line(0, "第14页 行38", "未按本章第 4.1.1 项要求密封的投标文件，招标人不予受理。"),
    ]);
    let reqs2 = extract_requirements(&[f2]);
    assert!(veto_excerpts(&reqs2).is_empty(), "#226 规则说明形不落否决: {reqs2:?}");
}

/// 例外从句排除：除…外 不算否决。
#[test]
fn exception_clause_excluded() {
    let f = pf(vec![
        line(0, "第8章 行5", "除不可抗力外，投标人应按期完成全部工程内容，"),
        line(1, "第8章 行6", "并保证工程质量达到合同约定标准。"),
    ]);
    let reqs = extract_requirements(&[f]);
    assert!(veto_excerpts(&reqs).is_empty(), "例外从句不应判否决: {reqs:?}");
}

/// 语境传播：总括句 → 圈号列举继承；流程步骤排除。
#[test]
fn context_propagation_and_procedure_guard() {
    let f = pf(vec![
        line(0, "第3页 行1", "9.2.2 下列行为，视为串通投标："),
        line(1, "第3页 行2", "⑴投标人之间相互约定抬高或压低投标报价；"),
        line(2, "第3页 行3", "⑵投标人之间约定，在招标项目中分别以高、中、低价位报价；"),
        // 流程步骤（评标职责——程序词排除）
        line(3, "第3页 行4", "⑴初步评审阶段负责资格评审和响应性评审；"),
    ]);
    let reqs = extract_requirements(&[f]);
    let vetos = veto_excerpts(&reqs);
    assert_eq!(vetos.len(), 3, "总括句 + 2 串通列举（流程职责行排除）: {reqs:?}");
    assert!(vetos.iter().all(|v| !v.contains("负责")));
}

/// 评分结构行排除：分值聚集（≥2 处「N分」）不判否决。
#[test]
fn score_shape_excluded() {
    let f = pf(vec![
        line(0, "第9页 行1", "评审标准："),
        line(1, "第9页 行2", "⑴工程特点及施工重点和难点分析准确、全面的，得1分，否则得0～1分；"),
    ]);
    let reqs = extract_requirements(&[f]);
    assert!(veto_excerpts(&reqs).is_empty(), "分值结构行不应判否决: {reqs:?}");
}

/// 目录行防御：带引导点的目录条目不抽取不建上下文。
#[test]
fn toc_line_defense() {
    let f = pf(vec![
        line(0, "第2页 行1", "第一章 投标公告 ............................... 5"),
        line(1, "第2页 行2", "第二章 投标人须知 ........................... 12"),
    ]);
    let reqs = extract_requirements(&[f]);
    assert!(reqs.is_empty());
}

/// 幂等：同输入两遍全等。
#[test]
fn idempotent_extraction() {
    let blocks = vec![
        line(0, "第6页 行1", "1.4.3 未提交有效凭证的，招标人"),
        line(1, "第6页 行2", "拒收投标文件。"),
        line(2, "第6页 行3", "9.2.2 下列行为，视为串通投标："),
        line(3, "第6页 行4", "⑴投标人之间相互约定抬高或压低投标报价；"),
    ];
    let r1 = extract_requirements(&[pf(blocks.clone())]);
    let r2 = extract_requirements(&[pf(blocks)]);
    assert_eq!(r1, r2);
}

// ============================ #450（B-18）：页界噪声——不吞不截 ============================

/// #450（B-18）：跨页否决条款 + 页码行 + 重复页眉（≥3 页）——机制复现
/// 与修复验收。
///
/// 修前（机制坐实）：段落扩展无页界守卫——页码行「3」（非 skip 行：无
/// 省略号/点线）与页眉行「XX水库除险加固工程招标文件」被拼进条款
/// para_text →「招标人拒收投标文件」被噪声截断成「招标人拒3XX水库…
/// 收投标文件」→ 否决词「拒收」失配（L2 missed 面）+ excerpt 污染。
/// 修后：噪声透明穿越——不吞（不进 para_text/anchors）不截（条款整段
/// 还原为与 para_reassembly_cross_line_veto 同款已验证文本，词表跨页
/// 匹配）。页眉在第 3/4/5 三页页首重复（≥3 页门槛——真页眉重复面
/// 3~122 页，见 extract.rs repeated_edges 校准注释）。
#[test]
fn para_page_noise_transparent_cross_page_veto() {
    let f = pf(vec![
        line(0, "第2页 行8", "1.4.3 未提交有效凭证的，招标人拒"),
        line(1, "第3页 行1", "3"),
        line(2, "第3页 行2", "XX水库除险加固工程招标文件"),
        line(3, "第3页 行3", "收投标文件。"),
        line(4, "第4页 行1", "4"),
        line(5, "第4页 行2", "XX水库除险加固工程招标文件"),
        line(6, "第4页 行3", "7.1.1 计划工期为 540 日历天。"),
        line(7, "第5页 行1", "5"),
        line(8, "第5页 行2", "XX水库除险加固工程招标文件"),
        line(9, "第5页 行3", "8.2.1 违约金按合同专用条款约定计取。"),
    ]);
    let reqs = extract_requirements(&[f]);
    // ①跨页否决整段还原：词表跨页匹配命中（修前被噪声截断失配）
    let vetos = veto_excerpts(&reqs);
    assert_eq!(vetos.len(), 1, "跨页否决条款应命中: {reqs:?}");
    assert!(vetos[0].contains("招标人拒"), "条款首行在场: {vetos:?}");
    assert!(vetos[0].contains("收投标文件"), "跨页续行在场: {vetos:?}");
    // ②噪声不进锚（excerpt 保真——页码/页眉不在任何 REQ 的锚面）
    assert!(
        !reqs.iter().any(|r| r
            .anchors
            .iter()
            .any(|a| a.excerpt.trim() == "3" || a.excerpt.trim() == "4")),
        "页码行不得成为锚: {reqs:?}"
    );
    assert!(
        !reqs.iter().any(|r| r
            .anchors
            .iter()
            .any(|a| a.excerpt.contains("水库除险加固"))),
        "页眉行不得成为锚: {reqs:?}"
    );
    // ③噪声行不产 junk REQ（页眉独立段落/页码碎片过滤双面）
    assert!(
        !reqs.iter().any(|r| r.anchors.len() == 1
            && r.anchors[0].excerpt.trim() == "XX水库除险加固工程招标文件"),
        "页眉行不得独立成 REQ: {reqs:?}"
    );
}

/// #450 守卫①：页码行须数字 == 本行页号——单页文档里的数字行（页号 1、
/// 文本「12」）不是页码噪声，照旧参与段落拼接（防误杀正文数字行——
/// 「投标保证金金额为 12 万元整」被物理换行拆出的「12」）。
#[test]
fn para_page_noise_guard_digits_must_match_own_page() {
    let f = pf(vec![
        line(0, "第1页 行1", "3.2.5 投标保证金金额为"),
        line(1, "第1页 行2", "12"),
        line(2, "第1页 行3", "万元整。"),
    ]);
    let reqs = extract_requirements(&[f]);
    // 「12」被拼进段落（不是噪声）——整段 REQ 覆盖三行
    let para_req = reqs.iter().find(|r| r.anchors.len() == 3);
    assert!(para_req.is_some(), "数字行照旧拼接（守卫不误杀）: {reqs:?}");
    let joined: String = para_req
        .unwrap()
        .anchors
        .iter()
        .map(|a| a.excerpt.as_str())
        .collect();
    assert!(joined.contains("12"), "数字内容保真: {joined}");
}

/// #450 守卫②：页眉须 ≥3 页重复——恰好 2 页的边缘重复不判噪声照旧参与
/// 重组。真件实证（黑龙江 hq 件）：「采购包3：」恰在第 30/32 页页首各
/// 出现一次，2 页门槛会把它误判页眉 → 段界移动吞 REQ（资格条件 32→28）；
/// batch1 全部 ≥2 重复均为巧合命中，真页眉重复 3~122 页——门槛取 3。
#[test]
fn para_page_noise_guard_header_needs_three_pages() {
    let f = pf(vec![
        // 同一资质面文本恰在第 2/3 两页页首（行1）——巧合面，2 页 < 3 页门槛
        // （若误判噪声会整行剥离——资格 REQ 消失；不判则照旧产资格 REQ）
        line(0, "第2页 行1", "具备同类工程资质证书的投标人续前页表"),
        line(1, "第2页 行2", "8.1.2 逾期送达的投标文件，招标人将"),
        line(2, "第2页 行3", "不予受理。"),
        line(3, "第3页 行1", "具备同类工程资质证书的投标人续前页表"),
        line(4, "第3页 行2", "9.1.1 合同工期自开工报告批准之日起算。"),
    ]);
    let reqs = extract_requirements(&[f]);
    // ①恰 2 页重复 → 不是噪声 → 照旧作为普通行参与（资格 REQ 在场——零激活）
    assert!(
        reqs.iter().any(|r| r
            .anchors
            .iter()
            .any(|a| a.excerpt.contains("具备同类工程资质证书"))),
        "恰 2 页重复不判噪声，照旧产 REQ: {reqs:?}"
    );
    // ②既有行为不变：跨行否决照旧还原
    let vetos = veto_excerpts(&reqs);
    assert_eq!(vetos.len(), 1, "跨行否决照旧还原: {reqs:?}");
}

/// #450 守卫③：装饰形态页码行（「— 12 —」）同样透明穿越——真实 pdftotext
/// 输出的页脚装饰页码常见形态。
#[test]
fn para_page_noise_dressed_page_number_footer() {
    let f = pf(vec![
        line(0, "第11页 行5", "6.3.2 投标人存在串通投标行为的，其"),
        line(1, "第11页 行6", "— 11 —"),
        line(2, "第12页 行1", "投标将被否决。"),
        line(3, "第12页 行2", "12"),
        line(4, "第12页 行3", "（正文续）其他条款内容。"),
    ]);
    let reqs = extract_requirements(&[f]);
    let vetos = veto_excerpts(&reqs);
    assert_eq!(vetos.len(), 1, "装饰页码不截断否决词: {reqs:?}");
    assert!(
        vetos[0].contains("串通投标"),
        "否决短语完整还原（修前被「— 11 —」截断）: {vetos:?}"
    );
}

/// #450 守卫④：真件形态页码行「-第N⻚-」——部首 ⻚（U+2EDA，CJK 部首
/// 区**无 NFKC 分解**——康熙部首 ⾴→頁 能归一，⻚ 不能）。黑龙江 batch1
/// 统一导出 PDF 的页脚实测形态；白名单显式收编 ⻚/頁 后透明穿越。
/// 修前机制：该形态不被识别 → 页码行成段头 → 主循环分支链不产 REQ
/// （junk 段头）→ 段内真续行一并丢失（吞面——hq 件 pkg2/pkg3 营业执
/// 照行、pkg3 医疗行实测丢失的根因）。
#[test]
fn para_page_noise_radical_page_char_footer() {
    let f = pf(vec![
        line(0, "第27页 行33", "3.4.5 投标文件未按规定格式签署并加盖"),
        line(1, "第27页 行34", "-第27⻚-"),
        line(2, "第28页 行1", "公章的，其投标将被否决。"),
        line(3, "第28页 行2", "-第28⻚-"),
        line(4, "第29页 行1", "4.1.1 其他条款内容照常。"),
    ]);
    let reqs = extract_requirements(&[f]);
    // ①部首形态页码不截断否决词（修前「-第27⻚-」做段头吞整段）
    let vetos = veto_excerpts(&reqs);
    assert_eq!(vetos.len(), 1, "部首页码不吞不截否决条款: {reqs:?}");
    assert!(vetos[0].contains("签署并加盖"), "条款首行在场: {vetos:?}");
    assert!(
        vetos[0].contains("公章的，其投标将被否决"),
        "跨页续行在场（修前整段被 junk 段头吞）: {vetos:?}"
    );
    // ②部首页码不进锚（excerpt 保真）
    assert!(
        !reqs.iter().any(|r| r
            .anchors
            .iter()
            .any(|a| a.excerpt.trim() == "-第27⻚-" || a.excerpt.trim() == "-第28⻚-")),
        "部首页码不得成为锚: {reqs:?}"
    );
}

/// #450 守卫⑤：条款号单元格「2.1」（评分表线性化形态——裸编号行 +
/// 次行内容）在页 21 时数字拼接「21」撞页号——多游程 + 点号白名单双
/// 护栏不判页码噪声（实测黑龙江 wenming 件：误判会丢评分项 REQ 18→17）。
/// 同款护栏顺带覆盖「21.」（点号不在 issue 形态清单）。
#[test]
fn para_page_noise_guard_clause_number_cell_not_page_no() {
    let f = pf(vec![
        line(0, "第21页 行19", "2.1"),
        line(1, "第21页 行20", "采购包1："),
        line(2, "第21页 行21", "以投标报价为主要评分因素。"),
        line(3, "第22页 行1", "22"),
        line(4, "第22页 行2", "3.1 以技术方案为主要评分因素。"),
    ]);
    let reqs = extract_requirements(&[f]);
    // 「2.1」+「采购包1：」照旧成段（条款号行不被当页码剥离）
    assert!(
        reqs.iter().any(|r| r
            .anchors
            .iter()
            .any(|a| a.excerpt.trim() == "2.1")),
        "条款号单元格「2.1」不是页码噪声: {reqs:?}"
    );
    // 裸页码「22」（页 22）照旧透明穿越——不进锚
    assert!(
        !reqs.iter().any(|r| r
            .anchors
            .iter()
            .any(|a| a.excerpt.trim() == "22")),
        "真页码「22」不进锚: {reqs:?}"
    );
}
