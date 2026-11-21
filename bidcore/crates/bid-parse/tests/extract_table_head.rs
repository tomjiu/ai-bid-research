//! #175：编号表格行不产格式 REQ——huaian「11.3」伪缺号收口。
//!
//! 根因（issue #175 正文）：第六章 投标文件格式 的编号格式件标题行在
//! 真实 DOCX 中常为 `table_row` 块（表9 行1 全宽合并单元形态），而编号
//! 条款抽取主循环只走 Para 块——同簇 11.1/11.2/11.4（para）各开 REQ，
//! 唯 11.3（table_row）静默掉落 → missing_sequence 按 REQ clause_no
//! 连续性判缺（伪缺号——编号在源文件不缺）。
//!
//! 修法（Lead 裁定口径，方案 1 收窄版）：未被任何专路/既有分支消费的
//! 点分编号表格行进「延迟候选」；主循环后与段面（全部已开 REQ）clause_no
//! 去重——前附表镜像正文的冗余副本（unicom 实测 45/45 全覆盖）不再双抽，
//! 同号仅表格在场的补开 REQ，类别随章节上下文（category_for 单一真源）。
//!
//! 守卫（数据行误入防线）：
//! - 点分形态 N(.N)+：纯数字行（行号「1」/费率表「100万元以下 1.5%」）
//!   无点不入候选（松岭实测负例）；
//! - 编号行的 □/…… 与段面编号分支同语义（填写值/模板尾注，不设守卫
//!   ——huaian 3.2.5「（9）……」是真实九子项条款的尾部模板注）；
//! - 专路优先：审查表/语义表/表头/否决/参数表分支先行消费的行零扰动
//!  （否决优先——shanxi 3.1.3 走表-N 编号，内容保全优先于编号连续性）。
//!
//! 验收对照（issue #175）：
//! - huaian 11.x 四条同簇全有 REQ（首测）；
//! - 同号已在段面开 REQ 的表格行不双抽（次测）；
//! - 数据行/占位行零激活（三四测）；
//! - 否决表格行仍走既有否决分支，条款号形态不变（五测）。

use bid_parse::extract::extract_requirements;
use bid_parse::{Block, BlockKind, ParsedFile};

fn pf(blocks: Vec<Block>) -> ParsedFile {
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

fn clause_nos(reqs: &[bid_domain::Requirement]) -> Vec<String> {
    reqs.iter().filter_map(|r| r.clause_no.clone()).collect()
}

/// huaian 真实形态最小化：第六章 格式件同簇 11.1/11.2（纯编号 para）+
/// 11.3（表9 行1 全宽合并 table_row）+ 11.4（编号+标题 para）。
/// 修复前：11.3 整条无 REQ（伪缺号复现）；修复后：四条同簇全在。
#[test]
fn numbered_table_head_opens_req_when_para_missing() {
    let f = pf(vec![
        para(1, "第六章  投标文件格式", "11.1"),
        para(2, "第六章  投标文件格式", "中国电信在职员工、离职或退休后三年内在我方担任法定代表人或董监高的情况表"),
        para(3, "第六章  投标文件格式", "11.2"),
        para(4, "第六章  投标文件格式", "承诺函"),
        trow(
            5,
            "第六章  投标文件格式 表9 行1",
            "11.3供应商关键人员重要亲属在电信公司工作信息登记表",
            &["11.3供应商关键人员重要亲属在电信公司工作信息登记表"],
        ),
        para(6, "第六章  投标文件格式", "11.4中国电信江苏公司供应商单位法人、股东、监事信息表"),
    ]);
    let reqs = extract_requirements(&[f]);
    let nos = clause_nos(&reqs);
    for want in ["11.1", "11.2", "11.3", "11.4"] {
        assert!(
            nos.iter().any(|n| n == want),
            "同簇 {want} 应有 REQ（实有 clause_no：{nos:?}）"
        );
    }
    let r113 = reqs
        .iter()
        .find(|r| r.clause_no.as_deref() == Some("11.3"))
        .expect("11.3 REQ 应在位（#175 修复面）");
    assert_eq!(
        r113.category, "格式要求",
        "类别随章节上下文（格式章 → 格式要求，与同簇 para 一致）；实得 {}",
        r113.category
    );
    assert!(
        r113.anchors.iter().any(|a| a.excerpt.contains("供应商关键人员重要亲属")),
        "锚摘录应含标题原文：{:?}",
        r113.anchors.iter().map(|a| a.excerpt.as_str()).collect::<Vec<_>>()
    );
}

/// 前附表镜像形态：同号已在段面开 REQ 的表格行是冗余副本，不得双抽
/// （unicom 前附表 45/45 全覆盖即此形态——双抽会污染矩阵）。
#[test]
fn numbered_table_head_dedup_when_para_already_covers() {
    let f = pf(vec![
        para(1, "第二章  投标人须知", "3.1 评标委员会组成人数：5人以上单数。"),
        trow(
            2,
            "第二章  投标人须知前附表 行1",
            "3.1 评标委员会组成人数 5人以上单数",
            &["3.1", "评标委员会组成人数", "5人以上单数"],
        ),
    ]);
    let reqs = extract_requirements(&[f]);
    let c31 = reqs
        .iter()
        .filter(|r| r.clause_no.as_deref() == Some("3.1"))
        .count();
    assert_eq!(c31, 1, "同号 3.1 只得一条 REQ（段面已开，表格行不双抽）；实得 {c31}");
}

/// 数据行守卫：无点分编号形态的表格行（费率表「100万元以下 1.5%」/
/// 行号「1」「2」）零激活——不产任何 REQ。
#[test]
fn plain_number_data_rows_stay_out() {
    let f = pf(vec![
        trow(1, "第三章  评标办法 表2 行1", "100万元以下 1.5% 1.5% 1.0%", &["100万元以下", "1.5%", "1.5%", "1.0%"]),
        trow(2, "第三章  评标办法 表2 行2", "100～500万元 1.1% 0.8% 0.7%", &["100～500万元", "1.1%", "0.8%", "0.7%"]),
        trow(3, "第六章  投标文件格式 表3 行1", "1", &["1"]),
        trow(4, "第六章  投标文件格式 表3 行2", "2", &["2"]),
    ]);
    let reqs = extract_requirements(&[f]);
    assert!(
        reqs.is_empty(),
        "纯数字/费率数据行不得产 REQ（实得 {} 条：{:?}）",
        reqs.len(),
        clause_nos(&reqs)
    );
}

/// 【同簇同行为】编号行的 □/…… 是条款自身的填写值/模板尾注——段面编号
/// 分支（re_clause 命中即开 REQ）不带 is_placeholder 守卫，表格编号头
/// 同语义：huaian 3.2.5 实测「（9）……」是真实九子项条款的模板尾注，
/// 整条须开 REQ（守卫会误杀真条款）。数据行防线是点分形态判据（次测）。
#[test]
fn numbered_placeholder_row_follows_para_semantics() {
    let f = pf(vec![trow(
        1,
        "第六章  投标文件格式 表4 行1",
        "11.5 □ 涉及  □ 不涉及",
        &["11.5", "□ 涉及", "□ 不涉及"],
    )]);
    let reqs = extract_requirements(&[f]);
    assert_eq!(reqs.len(), 1, "编号 □ 行与段面编号分支同语义：开 REQ（填写值入 statement），实得 {}", reqs.len());
    assert_eq!(reqs[0].clause_no.as_deref(), Some("11.5"));
}

/// 专路优先零扰动：否决表格行仍走既有否决分支（条款号 = 表-N 形态），
/// 不进 #175 编号头路径（条款号不得变成点分形态）。
#[test]
fn veto_table_row_keeps_existing_path() {
    let f = pf(vec![trow(
        1,
        "第二章  投标人须知 表1 行3",
        "3.1 有下列情形之一的，其投标将被否决：与招标人串通投标",
        &["3.1", "有下列情形之一的，其投标将被否决", "与招标人串通投标"],
    )]);
    let reqs = extract_requirements(&[f]);
    assert_eq!(reqs.len(), 1, "否决行应产一条 REQ（既有分支），实得 {}", reqs.len());
    let r = &reqs[0];
    assert_eq!(r.category, "否决项", "否决词行类别不变");
    assert_eq!(r.clause_no.as_deref(), Some("表-3"), "条款号保持 表-N 形态（实得 {:?}）", r.clause_no);
}

/// 前附表型条款行（三格：编号+标题+内容）在段面无同号时补开 REQ
/// （songjiang 3.2.5/5.2.5、huaian 3.2.5/7.2.4 真实形态）。
#[test]
fn front_matter_clause_row_opens_req_when_missing() {
    let f = pf(vec![trow(
        1,
        "第二章  投标人须知前附表 行7",
        "3.2.5 电子投标文件的编制 投标人需按照如下要求编制电子投标文件",
        &["3.2.5", "电子投标文件的编制", "投标人需按照如下要求编制电子投标文件"],
    )]);
    let reqs = extract_requirements(&[f]);
    assert_eq!(reqs.len(), 1, "段面缺号的编号条款行应补开一条 REQ，实得 {}", reqs.len());
    assert_eq!(reqs[0].clause_no.as_deref(), Some("3.2.5"));
}
