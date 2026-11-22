//! attachment_clause_hint.rs —— #177 含条款辅件按附件 kind 导入的回执提示
//! 验收契约（audit/multifile-acceptance-2026-11-18.md §3 F-3 / PR #172）。
//!
//! 现场真实多件项目里含条款的辅件（技术规范书典型——21 条业务要求）按
//! 缺省语义导入 kind=附件 时对矩阵完全不可见（unicom-ry 0/21 对照；alt
//! 探针按招标文件 kind 导入后 21 条全进矩阵）。机制：附件无条款抽取面，
//! kind 指派是语义决策、直接决定条款可见性。
//!
//! 修法（提示面——不扩功能、不自动改 kind）：kind=附件 且块面条款形态句
//! ≥ 8（实测校准：正例 17 / 纯附件负例 0 / 中间态 5）→ 导入回执
//! per_file.warnings 点名 + 指路重导。
//!
//! 验收对照（issue #177）：
//! | 用例 | 断言 |
//! |---|---|
//! | 1. unicom-ry 技术规范书按附件导入 | 回执可见 ATTACHMENT_CLAUSE_DENSE（非静默 0 条），行数/指路/「不自动改 kind」在提示面 |
//! | 2. 纯附件不误报 | 目录.docx（23 行目录条目——纯计数 21 行不可分，句子性过滤后 0）/ 投标一览表.xlsx（实测 5 行）/ 格式模板真件 / B3 图纸目录 → 全静默 |
//! | 3. kind 判别 | 同件按招标文件导入 → 无提示（附件面专属） |
//! | 4. 去重幂等 | 同 sha 重导附件 → 提示幂等复现；原档已有面 → 不提示（可见性失真豁免） |
//!
//! SKIP 纪律（#9）：素材不可达时 skip（real-corpus 与 batch2 均在仓内）。

use bid_domain::DomainStore;
use bid_parse::env_preflight::skip_if_fixture_missing;
use bid_tools::service::{import_files, ImportReport, ImportSpec};
use std::path::PathBuf;

fn repo_root() -> PathBuf {
    // crates/bid-tools → 仓库根
    let p = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../..");
    std::fs::canonicalize(&p).unwrap_or(p)
}

fn spec(path: PathBuf, filename: &str, kind: &str) -> ImportSpec {
    ImportSpec {
        upload_ref: path,
        filename: filename.to_string(),
        kind: kind.to_string(),
        expected_pages: None,
    }
}

fn new_store(key: &str) -> DomainStore {
    let mut s = DomainStore::new();
    s.create_project("i177 提示面", "ZFCG-2026-177", "明标", key).unwrap();
    s
}

fn unicom_tech_spec() -> PathBuf {
    repo_root().join("real-corpus/telecom/parse-input/B-unicom-ry-技术规范书.docx")
}

fn import_one(
    store: &mut DomainStore,
    parsed: &mut Vec<bid_parse::ParsedFile>,
    path: PathBuf,
    kind: &str,
) -> ImportReport {
    let filename = path.file_name().unwrap().to_string_lossy().into_owned();
    import_files(store, parsed, &[spec(path, &filename, kind)], None)
}

/// 验收 1：unicom-ry 技术规范书按附件导入 → 回执可见提示（非静默 0 条）。
#[test]
fn unicom_tech_spec_as_attachment_yields_visible_hint() {
    let path = unicom_tech_spec();
    if skip_if_fixture_missing("i177_acceptance_1", &[&path]) {
        return;
    }
    let mut store = new_store("i177-a1");
    let mut parsed = vec![];
    let r = import_one(&mut store, &mut parsed, path, "附件");
    assert_eq!(r.item_failures, 0, "引擎路径解析必须成功（mdcore rev af27043 后）");
    assert_eq!(r.per_file.len(), 1);
    let o = &r.per_file[0];
    assert!(o.chunks > 0, "解析产物在场（非空件）——回执同时携带块面计数");
    let hint = o
        .warnings
        .iter()
        .find(|w| w.contains("ATTACHMENT_CLAUSE_DENSE"))
        .expect("验收 1：按附件导入的条款密集件必须在回执可见（非静默 0 条）");
    assert!(hint.contains("17 行"), "实测行数入提示（探针校准值 17）: {hint}");
    assert!(hint.contains("kind=招标文件"), "重导指路: {hint}");
    assert!(hint.contains("不自动改 kind"), "语义决策留人: {hint}");
}

/// 验收 3（kind 判别）：同件按招标文件导入 → 无提示（有面 kind 不存在
/// 不可见问题——提示是附件面专属）。
#[test]
fn same_file_as_tender_kind_is_silent() {
    let path = unicom_tech_spec();
    if skip_if_fixture_missing("i177_kind_discriminator", &[&path]) {
        return;
    }
    let mut store = new_store("i177-kd");
    let mut parsed = vec![];
    let r = import_one(&mut store, &mut parsed, path, "招标文件");
    assert_eq!(r.item_failures, 0);
    assert!(
        r.per_file[0]
            .warnings
            .iter()
            .all(|w| !w.contains("ATTACHMENT_CLAUSE_DENSE")),
        "有面 kind 不提示：{:?}",
        r.per_file[0].warnings
    );
}

/// 验收 2：纯附件不误报（issue 点名格式模板/图纸为负例集）。
///
/// - 目录.docx：23 块全目录条目形态（「一、投标承诺书」）——纯计数判据
///   21 行与正例不可分，句子性过滤后 0 行，判据成立的实证钉；
/// - 投标一览表.xlsx：实测 5 行条款形态句（< 8 门槛）；
/// - 格式模板真件（nm-health-terminal 官方附件）：实测 0 行；
/// - B3-图纸目录.xlsx：图纸类内容按附件导入同不误报（实测 0 行）。
#[test]
fn pure_attachments_do_not_false_positive() {
    let root = repo_root();
    let cases: Vec<(PathBuf, &str)> = vec![
        (
            root.join("fixtures/real-tender-batch2/nm-health-terminal/附件/目录.docx"),
            "附件",
        ),
        (
            root.join("real-corpus/telecom/parse-input/B-unicom-ry-投标一览表.xlsx"),
            "附件",
        ),
        (
            root.join("fixtures/real-tender-batch2/nm-health-terminal/附件/其他材料.docx"),
            "格式模板",
        ),
        (
            root.join("fixtures/real-tender-batch2/nm-health-terminal/附件/主要商务要求承诺书.docx"),
            "格式模板",
        ),
        (
            root.join("fixtures/real-tender-batch2/nm-health-terminal/附件/投标人基本情况表.docx"),
            "格式模板",
        ),
        (
            root.join("fixtures/corpus-A/files/B3-图纸目录.xlsx"),
            "附件",
        ),
    ];
    for (i, (path, kind)) in cases.iter().enumerate() {
        if skip_if_fixture_missing("i177_acceptance_2", &[path]) {
            continue;
        }
        let mut store = new_store(&format!("i177-a2-{i}"));
        let mut parsed = vec![];
        let r = import_one(&mut store, &mut parsed, path.clone(), kind);
        assert_eq!(r.item_failures, 0, "负例解析必须成功（解析失败另有 errors 面）");
        assert!(
            r.per_file[0]
                .warnings
                .iter()
                .all(|w| !w.contains("ATTACHMENT_CLAUSE_DENSE")),
            "纯附件/格式模板不得误报（{} kind={}）：{:?}",
            path.display(),
            kind,
            r.per_file[0].warnings
        );
    }
}

/// 验收 4：去重路径的幂等与豁免。
///
/// - 同 sha 同身份重导（附件→附件）：提示幂等复现（回执一致性）；
/// - 原档已有条款面（招标文件→附件重导）：件对矩阵可见，提示失真 → 豁免
///   （METADATA_CONFLICT 仍在——身份面与提示面各说各话）。
#[test]
fn dedup_path_idempotent_hint_and_face_exemption() {
    let path = unicom_tech_spec();
    if skip_if_fixture_missing("i177_dedup", &[&path]) {
        return;
    }
    // 4a：附件首导 → 重导同 sha 同 kind 同名 → 提示幂等复现
    let mut store = new_store("i177-dedup-a");
    let mut parsed = vec![];
    let r1 = import_one(&mut store, &mut parsed, path.clone(), "附件");
    assert_eq!(r1.item_failures, 0);
    assert!(
        r1.per_file[0].warnings.iter().any(|w| w.contains("ATTACHMENT_CLAUSE_DENSE")),
        "首导（附件）必须有提示"
    );
    let r2 = import_one(&mut store, &mut parsed, path.clone(), "附件");
    assert_eq!(r2.item_failures, 0);
    assert!(r2.per_file[0].deduplicated, "同 sha 重导 = 幂等 no-op");
    assert!(
        r2.per_file[0].warnings.iter().any(|w| w.contains("ATTACHMENT_CLAUSE_DENSE")),
        "幂等重导的回执同样携带提示（回执一致性——同件同判）"
    );

    // 4b：原档 kind=招标文件（有面）→ 同 sha 以附件重导 → 提示豁免
    let mut store_b = new_store("i177-dedup-b");
    let mut parsed_b = vec![];
    let r3 = import_one(&mut store_b, &mut parsed_b, path, "招标文件");
    assert_eq!(r3.item_failures, 0);
    assert!(
        !r3.per_file[0].warnings.iter().any(|w| w.contains("ATTACHMENT_CLAUSE_DENSE")),
        "招标文件首导无提示"
    );
    let path_again = unicom_tech_spec();
    let r4 = import_one(&mut store_b, &mut parsed_b, path_again, "附件");
    assert_eq!(r4.item_failures, 0);
    assert!(r4.per_file[0].deduplicated);
    assert!(
        r4.per_file[0]
            .warnings
            .iter()
            .any(|w| w.contains("METADATA_CONFLICT")),
        "身份冲突照常登记（#188 面）：{:?}",
        r4.per_file[0].warnings
    );
    assert!(
        !r4.per_file[0]
            .warnings
            .iter()
            .any(|w| w.contains("ATTACHMENT_CLAUSE_DENSE")),
        "原档已有条款面（可见）时提示失真——豁免：{:?}",
        r4.per_file[0].warnings
    );
}
