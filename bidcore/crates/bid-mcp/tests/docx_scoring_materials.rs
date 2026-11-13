//! #134（CHN-03）素材对账——DOCX 真表格评分表现状缺口实测。
//!
//! **素材先行纪律（issue 红线）**：不写解析器——本测试只对账「现状
//! 抽取对 7 件含真表格评分表的 DOCX 抽到多少评分行」。扫描器
//! （scripts/scan_docx_scoring_tables.py）已盘点出素材清单；本测试用
//! **真实链路**（create → import_tender_files → extract_requirements，
//! 每件独立项目零串扰）跑全部 7 件，把「评分项 REQ 数 / 评分表数据行
//! 数」对账打到 stderr（`#134 <file> | 评分表数据行≈N | 评分项 REQ=M |
//! 缺口=N-M`）——audit/materials-docx-scoring-tables.md 实测列的数据源。
//!
//! 断言策略：**不设阈值断言**（现状缺口本身就是交付物——硬断言会把
//! 「素材对账」变成「解析器验收」，违反先行纪律）。只断言链路本身真跑
//! 不崩（import totals.files == 1、extract 正常返回、素材在位）。
//!
//! SKIP 纪律（#9）：仓库根不可达时 skip。

use bid_mcp::{dispatch_with, BidService, ToolCall, ToolReply};
use serde_json::{json, Value};
use std::path::{Path, PathBuf};

fn repo_root() -> PathBuf {
    let p = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../..");
    std::fs::canonicalize(&p).unwrap_or(p)
}

fn call(svc: &mut BidService, tool: &str, args: Value) -> ToolReply {
    dispatch_with(svc, ToolCall { tool: tool.to_string(), args })
}

fn ok_result(reply: ToolReply, tag: &str) -> Value {
    match reply {
        ToolReply::Ok(out) => out.result,
        ToolReply::Err { error, .. } => panic!("[{tag}] 步骤失败: {error}"),
    }
}

/// 7 件素材（扫描器 2026-11-13 盘点：HAS_SCORING_TABLE）+ 每件评分表
/// 数据行真值（结构侧）。行真值口径：Σ(表格数据行数 − 表头行)——表头行
/// = 首行含 评分/评审/得分/分值 词（与扫描器 header_1row_preview 对齐；
/// 详表见 audit/materials-docx-scoring-tables.md §2）。
const MATERIALS: &[(&str, u64)] = &[
    ("real-corpus/telecom/parse-input/A-telecom-huaian-主文件.docx", 159),      // 47+12+12+12 − 4 表头
    ("real-corpus/telecom/parse-input/A-telecom-shanghai-songjiang-光终端放装-招标文件.docx", 41), // tbl#3 42 − 1
    ("real-corpus/telecom/parse-input/A-telecom-shanxi-灵枢智关-招标正文.docx", 76), // 30+15+12+12+12 − 5
    ("real-corpus/telecom/parse-input/A-unicom-ry-2026CUC-RJY-PT0783-招标文件.docx", 21), // 17+6 − 2
    ("real-samples/北京水利施工示范文本2025-LO.docx", 152),                     // 13 表共 164 − 12
    ("fixtures/real-tender-batch2/docx-jlyh/JLYHDH-2026-ZC122医养结合机构能力提升（三次）.docx", 14), // tbl#4 15 − 1
    ("fixtures/synth-tender/招标文件/A-招标文件.docx", 8),                     // 合成件 tbl#2 9 − 1
];

/// 单件真跑：独立工作区 + 独立项目 → import → extract → 返回评分项 REQ 数。
/// 素材导入选型：`.with_fs_root(repo_root)`（real_closeout.rs 同款受信根接线
/// ——仓内素材只读导入，不落位复制；#183 围栏语义内）。
fn audit_one(root: &Path, rel: &str, tag_no: usize) -> u64 {
    let dir = std::env::temp_dir().join(format!("m134-{tag_no}-{:?}", std::process::id()));
    std::fs::create_dir_all(&dir).unwrap();
    let mut svc = BidService::open(&dir).unwrap().with_fs_root(root.to_path_buf());
    let r = ok_result(
        call(&mut svc, "create_bid_project", json!({
            "name": format!("#134 素材对账-{tag_no}"), "bid_deadline": "2026-12-31",
            "mode": "明标", "external_key": format!("m134-{tag_no}"),
        })),
        rel,
    );
    let pid = r["project_id"].as_str().unwrap().to_string();

    let path = root.join(rel);
    assert!(path.exists(), "素材在位检查失败: {rel}");
    let imp = ok_result(
        call(&mut svc, "import_tender_files", json!({
            "project_id": &pid,
            "files": [{
                "upload_ref": path.display().to_string(),
                "filename": Path::new(rel).file_name().unwrap().to_string_lossy(),
                "kind": "招标文件",
            }],
        })),
        rel,
    );
    assert_eq!(imp["totals"]["files"].as_u64().unwrap_or(0), 1, "[{rel}] 导入面单件真跑");

    let _ext = ok_result(
        call(&mut svc, "extract_requirements", json!({ "project_id": &pid })),
        rel,
    );
    svc.store().requirements().iter()
        .filter(|r| r.category == "评分项")
        .count() as u64
}

#[test]
fn docx_scoring_tables_current_gap_audit() {
    let root = repo_root();
    if !root.join(".git").exists() {
        eprintln!("SKIP: docx_scoring_tables_current_gap_audit（仓库根不可达——非仓内运行）");
        return;
    }
    let mut summary: Vec<String> = Vec::new();
    for (i, (rel, truth_rows)) in MATERIALS.iter().enumerate() {
        let n_scoring = audit_one(&root, rel, i);
        let gap = truth_rows.saturating_sub(n_scoring);
        let line = format!("#134 {rel} | 评分表数据行≈{truth_rows} | 评分项 REQ={n_scoring} | 缺口={gap}");
        eprintln!("{line}");
        summary.push(line);
    }
    eprintln!("\n== #134 对账汇总（{} 件）==\n{}", MATERIALS.len(), summary.join("\n"));
}
