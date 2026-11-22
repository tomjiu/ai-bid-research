//! #176 回归锁：unicom-ry 详细评审表.xlsx（UTF-16LE customXml——WPS 形态）。
//!
//! 修复前（mdcore rev f4328ebf 门 3 编码盲区）：`engine rejected: invalid
//! part customXml/item1.xml: truncated: 16 unclosed element(s) at EOF`
//! 整件拒收——customXml/item1.xml 实为 FF FE BOM 的完整良构 woProps，
//! 按 UTF-8 读导致 NUL 高位污染 quick-xml 结构面。
//!
//! 修复（mdcore #242 / PR #243，rev dc8c647 bump）：门 3 BOM 探测 →
//! UTF-16 部件流式转码后校验（提取关键部件 xl/ 的 UTF-16 仍两模式恒拒
//! ——能力边界）；customXml/ 边缘部件良构失败两模式恒降级警告。
//!
//! 本测试钉**真实件**导入恢复（#176 验收件：real-corpus/telecom/
//! parse-input 原件，sha 对 file-level-report.json 登记）——评分表
//! 数据行完整在场（分值列见 #178 xlsx 面跟进）。

use std::path::PathBuf;

#[test]
fn unicom_xlsx_utf16_customxml_imports() {
    let path = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("../../../real-corpus/telecom/parse-input/B-unicom-ry-详细评审表.xlsx");
    assert!(
        path.exists(),
        "缺少真件夹具 {}（不能静默通过）",
        path.display()
    );
    let pf = bid_engine::parse_xlsx_via_engine(&path)
        .unwrap_or_else(|e| panic!("UTF-16LE customXml 件应恢复导入（mdcore #242 修复面），实得 {e:?}"));
    // 件形态锚：24 行（标题 + 表头「序号|1级类别|2级类别|评分项|评分细则|分值」
    // + 22 数据行）、2 表
    assert_eq!(pf.blocks.len(), 24, "行数锚（修前整件拒收，无行可言）");
    assert_eq!(pf.tables, 2);
    let rows: Vec<&bid_parse::Block> = pf
        .blocks
        .iter()
        .filter(|b| matches!(b.kind, bid_parse::BlockKind::XlsxRow))
        .collect();
    assert_eq!(rows.len(), 24);
    // 表头行在位（含全角空格形态「评  分  项」/「分 值」——引擎 cells
    // 保真，识别面归 NFKC 归一层）
    let header = &rows[1];
    let joined = header.cells.join("|");
    assert!(joined.contains("分 值"), "表头分值列：{joined:?}");
    assert!(joined.contains("评  分  项"), "表头评分项列：{joined:?}");
    // 首数据行分值格（纯数字「3」——分值独立列形态，#178 xlsx 面）
    assert!(
        rows[2].cells.last().map(|c| c.trim() == "3").unwrap_or(false),
        "首数据行分值格应为 3：{:?}",
        rows[2].cells.last()
    );
}
