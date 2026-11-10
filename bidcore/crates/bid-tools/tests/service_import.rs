//! B-1 服务层契约测试：`service::import_files` 导入管线（runner 提升后的单一真源）。
//!
//! 覆盖 MCP 壳之下的业务半边：落库真源口径（DomainStore）、解析累积
//! （M1-b 输入面）、不可读件的逐件失败语义、kind 分层放行（契约枚举
//! 校验属壳，服务层透传——运行器「证据」类别依赖此分层）。

use bid_domain::{DomainStore, ParseStatus, ProjectStatus};
use bid_parse::env_preflight::skip_if_fixture_missing;
use bid_tools::service::{import_files, BidService, ImportSpec};
use std::path::PathBuf;

fn fixtures() -> PathBuf {
    let p = std::env::var("BID_FIXTURES")
        .map(PathBuf::from)
        .unwrap_or_else(|_| {
            // crates/bid-tools → 仓库根
            PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../../fixtures")
        });
    // #183 围栏：词法 `..` 会被围栏预拒——受信夹具根统一 canonical 绝对路径
    std::fs::canonicalize(&p).unwrap_or(p)
}

fn spec(path: PathBuf, filename: &str, kind: &str) -> ImportSpec {
    ImportSpec { upload_ref: path, filename: filename.to_string(), kind: kind.to_string(), expected_pages: None }
}

/// 真实主文件（corpus-A A-招标文件.docx）经管线落库：统计面与
/// corpus_probe 硬口径一致（tables >= 5），状态机 DRAFT → FILES_IMPORTED，
/// 解析累积在位（M1-b 抽取输入面）。
#[test]
fn service_imports_corpus_a_main_file_into_store() {
    let mut store = DomainStore::new();
    store.create_project("p", "ZFCG-2026-GK-0311", "明标", "ext-svc").unwrap();
    let mut parsed = vec![];
    let a = fixtures().join("corpus-A/files/A-招标文件.docx");
    if skip_if_fixture_missing("service_imports_corpus_a_main_file_into_store", &[&a]) {
        return;
    }

    let report = import_files(&mut store, &mut parsed, &[spec(a.clone(), "A-招标文件.docx", "招标文件")], None);

    assert_eq!(report.item_failures, 0);
    assert_eq!(report.new_records, 1);
    assert_eq!(store.files().len(), 1);
    let f = &store.files()[0];
    assert_eq!(f.parse_status, ParseStatus::Ok);
    assert!(f.tables >= 5, "corpus_probe 硬口径：A 件表格 >= 5，实际 {}", f.tables);
    assert!(f.chunks > 0);
    assert_eq!(store.project().unwrap().status, ProjectStatus::FilesImported);
    assert_eq!(store.content_version(), 2, "create=1，导入=2");
    assert_eq!(parsed.len(), 1, "成功件入解析累积");
    assert_eq!(parsed[0].sha256, f.sha256, "累积面与落库面同源（sha256 一致）");
}

/// 不可读 upload_ref：无文件身份（无 sha）→ 不落库（空 sha 会污染幂等键
/// 空间）、逐件失败、批次不中止（R-01）。
#[test]
fn unreadable_upload_is_item_failure_and_not_recorded() {
    let mut store = DomainStore::new();
    store.create_project("p", "c", "明标", "ext-svc-ghost").unwrap();
    let mut parsed = vec![];
    let good = fixtures().join("corpus-R/D6-revisions/R6b-纯删除澄清.docx");
    if skip_if_fixture_missing("unreadable_upload_is_item_failure_and_not_recorded", &[&good]) {
        return;
    }
    let ghost = fixtures().join("no-such/ghost.docx");

    let report = import_files(
        &mut store,
        &mut parsed,
        &[spec(good, "R6b-纯删除澄清.docx", "补遗"), spec(ghost, "ghost.docx", "附件")],
        None,
    );

    assert_eq!(report.item_failures, 1);
    assert_eq!(store.files().len(), 1, "只有好件落库");
    assert!(store.files().iter().all(|f| !f.sha256.is_empty()), "不得以空 sha 落档");
    assert_eq!(parsed.len(), 1);
    // 无身份件在 per_file 中 file_id 为 None（对账面可见）
    assert!(report.per_file.iter().any(|o| o.file_id.is_none()));
}

/// kind 分层：契约七类枚举校验属 MCP 壳——服务层透传（运行器「证据」
/// 类别走同管线，不因枚举被拒）。
#[test]
fn service_passes_kind_through_without_contract_enum() {
    let mut store = DomainStore::new();
    store.create_project("p", "c", "明标", "ext-svc-kind").unwrap();
    let mut parsed = vec![];
    let ev = fixtures().join("corpus-A/files/evidence/EV-01-营业执照.pdf");
    if skip_if_fixture_missing("service_passes_kind_through_without_contract_enum", &[&ev]) {
        return;
    }
    // PDF 导入依赖外部工具链（pdftotext）——无工具环境按 SKIP 机制跳过。
    if bid_parse::env_preflight::skip_if_env_missing(
        "service_passes_kind_through_without_contract_enum", &["pdftotext"]) {
        return;
    }

    let report = import_files(&mut store, &mut parsed, &[spec(ev, "evidence/EV-01-营业执照.pdf", "证据")], None);

    assert_eq!(report.item_failures, 0);
    assert_eq!(store.files()[0].kind, "证据", "服务层不重复契约枚举（分层：壳校验、层透传）");
}

/// BidService 聚合面：store / parsed 同一服务态内可见（MCP dispatch_with
/// 的注入体），import 方法与自由函数同源。
#[test]
fn bid_service_holds_store_and_parsed_together() {
    let mut svc = BidService::new().with_fs_root(fixtures());
    assert!(svc.store().project().is_err());
    svc.store_mut().create_project("p", "c", "暗标", "ext-svc-bid").unwrap();
    let d1a = fixtures().join("corpus-R/D1-tables/D1a-合并表头跨页表.docx");
    if skip_if_fixture_missing("bid_service_holds_store_and_parsed_together", &[&d1a]) {
        return;
    }

    let report = svc.import(&[spec(d1a, "D1a-合并表头跨页表.docx", "招标文件")]).unwrap();

    assert_eq!(report.item_failures, 0);
    assert_eq!(svc.store().files().len(), 1);
    assert_eq!(svc.parsed().len(), 1);
    assert_eq!(svc.store().files()[0].chunks, svc.parsed()[0].blocks.len());
}

/// B-13（#415）：OCR「白扫」——全页 OCR 成功但零行块的诚实空在导入
/// 响应面必须有 per-file 告警（内容丢失 vs 空文件可区分）。
///
/// 真链：python3+reportlab 现场生成 2 页空白 PDF（无文本层、无图像内容
/// ——OCR 渲染页全成功 0 行块）→ import_files → per_file.warnings 含
/// OCR_BLANK_SCAN 且页数可定位。此前该形态零信号（同批其他件会掩盖
/// 全局 ZERO_REQUIREMENTS）。
///
/// 环境门：全 PDF 链四件套 + chi_sim 语言数据（缺件显式 SKIP 横幅——
/// CI Windows 无 poppler/tesseract 不跑，本机 Linux 全链真跑）。
#[test]
fn ocr_blank_scan_surfaces_per_file_warning() {
    if bid_parse::env_preflight::skip_if_env_missing(
        "ocr_blank_scan_surfaces_per_file_warning",
        bid_parse::env_preflight::FULL_PDF_CHAIN,
    ) {
        return;
    }
    // #591 误报根治：生成器依赖（python3 + reportlab）也走环境门——
    // 旧版只在下方 assert! 处判红（CI 装齐 poppler+tesseract+chi_sim 却缺
    // reportlab → 判红，但业务代码零缺陷）。现在缺件走 SKIP 横幅，
    // 与 FULL_PDF_CHAIN 同口径（issue #9：依赖缺失不得伪装成业务 FAIL）。
    if bid_parse::env_preflight::skip_if_env_missing(
        "ocr_blank_scan_surfaces_per_file_warning",
        bid_parse::env_preflight::SYNTH_FIXTURE_DEPS,
    ) {
        return;
    }
    // 现场生成空白扫描形 PDF（#380 同款纪律：python3+reportlab 现场生成，
    // 缺件跳过横幅——不留仓内大文件）
    let tmp = std::env::temp_dir().join(format!("b13-blank-{}", std::process::id()));
    std::fs::create_dir_all(&tmp).expect("临时目录创建失败");
    let pdf = tmp.join("S-空白扫描件.pdf");
    let gen = std::process::Command::new("python3")
        .arg("-c")
        .arg(
            "from reportlab.pdfgen import canvas\n\
             c = canvas.Canvas('S-空白扫描件.pdf')\n\
             c.showPage()\n\
             c.showPage()\n\
             c.save()\n",
        )
        .current_dir(&tmp)
        .output()
        .expect("python3 启动失败");
    assert!(
        gen.status.success(),
        "reportlab 生成失败: {}",
        String::from_utf8_lossy(&gen.stderr)
    );
    if skip_if_fixture_missing("ocr_blank_scan_surfaces_per_file_warning", &[&pdf]) {
        return;
    }

    let mut store = DomainStore::new();
    store.create_project("p", "ZFCG-2026-GK-0415", "明标", "ext-b13").unwrap();
    let mut parsed = vec![];
    let report = import_files(
        &mut store,
        &mut parsed,
        &[spec(pdf, "S-空白扫描件.pdf", "招标文件")],
        None,
    );

    // 诚实空语义：导入 Ok（白扫不是失败——空扫描件可能是真空文件）
    assert_eq!(report.item_failures, 0, "白扫是诚实空不是失败: {:?}", report.per_file.iter().flat_map(|p| p.errors.clone()).collect::<Vec<_>>());
    assert_eq!(report.per_file.len(), 1);
    let pf = &report.per_file[0];
    assert_eq!(pf.parse_status, ParseStatus::OcrRequired, "无文本层件落 OcrRequired 档");
    assert_eq!(pf.chunks, 0, "白扫件零文本块产出");
    assert_eq!(pf.pages, 2, "reportlab 两页空白");
    let hit = pf
        .warnings
        .iter()
        .find(|w| w.contains("OCR_BLANK_SCAN"))
        .expect("白扫必须有 per-file 告警（B-13——此前内容丢失与空文件不可区分）");
    assert!(hit.contains("2 页"), "页数入告警定位: {hit}");
    // 落库面同源：parse_summary 已带「0 行块」（#380 前就有），响应面新告警双通道可见
    let f = &store.files()[0];
    assert!(f.parse_summary.contains("0 行块"), "summary 面维持既有可见性: {}", f.parse_summary);
}

/// #47 R10（跨平台硬化②）：Windows 保留名/非法字符件——**文件可读但名字
/// 不可移植**（Linux 壳放行 `CON.docx`，Windows 壳开不了同库）→ 域层导入
/// 门逐件失败登记（分账不中止）、不落库（不污染 sha 幂等键空间）、批次中
/// 好件照常导入。
///
/// 平台门（AGENTS.md §13.1）：保留名样本只能在 Unix 制备（Windows 侧
/// `fs::write("CON.docx")` 直接被 OS 拒）——运行时探测，制备失败打 SKIP
/// 横幅（13.2：横幅 + 原因 + 补救指引）。
#[test]
fn windows_illegal_names_are_item_failures_and_not_recorded() {
    // ── 样本制备（Unix-only 形态：CON.docx / 报告 .docx 尾随空格 / con 目录段） ──
    let tmp = std::env::temp_dir().join(format!("r10-names-{}", std::process::id()));
    std::fs::create_dir_all(&tmp).expect("临时目录创建失败");
    let con = tmp.join("CON.docx");
    let trailing = tmp.join("报告.docx ");
    let con_dir_good = tmp.join("con-dir/NUL.xlsx"); // 目录段目录名不在保留表（con-dir）
    if let Err(e) = (|| -> std::io::Result<()> {
        std::fs::write(&con, b"PK\x03\x04r10-con")?;
        std::fs::write(&trailing, b"PK\x03\x04r10-trailing")?;
        std::fs::create_dir_all(tmp.join("con-dir"))?;
        std::fs::write(&con_dir_good, b"PK\x03\x04r10-nul")?;
        Ok(())
    })() {
        // Windows/受限环境：OS 拒建保留名样本——本测试的验证对象在
        // 该平台由文件系统原生保证（根本建不出这种文件），如实 SKIP。
        eprintln!();
        eprintln!("====================================================================");
        eprintln!("SKIP: windows_illegal_names_are_item_failures_and_not_recorded");
        eprintln!("reason: PLATFORM_CANNOT_CREATE_FIXTURE: {e}");
        eprintln!("补救：在 Linux/Unix 壳真跑（保留名样本仅 Unix 可制备——Windows 侧");
        eprintln!("      OS 原生拒绝创建，名字门由文件系统自身代劳）");
        eprintln!("====================================================================");
        return;
    }
    // 好件样本：真 fixture 拷进围栏根（upload_ref 必须落在受信根内）
    let good_src = fixtures().join("corpus-A/files/A-招标文件.docx");
    if skip_if_fixture_missing(
        "windows_illegal_names_are_item_failures_and_not_recorded",
        &[&good_src],
    ) {
        return;
    }
    let good = tmp.join("A-招标文件.docx");
    std::fs::copy(&good_src, &good).expect("好件拷贝失败");

    let mut svc = BidService::new().with_fs_root(&tmp);
    svc.store_mut().create_project("p", "R10-NS", "明标", "ext-r10").unwrap();
    // 相对形态 upload_ref（锚定 roots[0]——rel 计算走围栏真源）
    let report = svc.import(&[
        spec(PathBuf::from("CON.docx"), "CON.docx", "招标文件"),
        spec(PathBuf::from("A-招标文件.docx"), "A-招标文件.docx", "招标文件"),
        spec(PathBuf::from("con-dir/NUL.xlsx"), "NUL.xlsx", "附件"),
        spec(PathBuf::from("报告.docx "), "报告.docx ", "附件"),
    ])
    .expect("分账语义：名字不可移植是逐件失败不是批次错");

    // 逐件失败 3 件（保留名文件 + 保留名目录内件 + 尾随空格件），好件 1 件成功
    assert_eq!(report.item_failures, 3, "分账不中止：{:#?}", report.per_file);
    assert_eq!(report.new_records, 1, "好件照常落库：{:#?}", report.per_file);
    assert_eq!(svc.store().files().len(), 1, "坏名字件不落库（库内只有好件）");
    assert!(
        svc.store().files().iter().all(|f| !f.sha256.is_empty()),
        "不落空 sha（幂等键空间不污染）"
    );
    // per_file 分账面：三坏一好全可见（R3 item_errors 面），错误文案带
    // 稳定 reason 码（UI 分账明细可定位「为什么这件没进」）
    assert_eq!(report.per_file.len(), 4);
    let con_out = report.per_file.iter().find(|o| o.filename == "CON.docx")
        .expect("保留名件在分账中");
    assert!(con_out.file_id.is_none(), "无文件身份（未落库）");
    assert!(
        con_out.errors.iter().any(|e| e.contains("windows_reserved_device_name")),
        "保留名 reason 码可见：{:?}", con_out.errors
    );
    let nul_out = report.per_file.iter().find(|o| o.filename == "NUL.xlsx")
        .expect("目录内保留名件在分账中");
    assert!(
        nul_out.errors.iter().any(|e| e.contains("windows_reserved_device_name")),
        "目录内 NUL.xlsx 同拒（rel 段逐段过检）：{:?}", nul_out.errors
    );
    let trail_out = report.per_file.iter().find(|o| o.filename == "报告.docx ")
        .expect("尾随空格件在分账中");
    assert!(
        trail_out.errors.iter().any(|e| e.contains("windows_trailing_dot_or_space")),
        "尾随空格 reason 码可见：{:?}", trail_out.errors
    );
    let good_out = report.per_file.iter().find(|o| o.filename == "A-招标文件.docx")
        .expect("好件在分账中");
    assert!(good_out.file_id.is_some(), "好件有文件身份");

    let _ = std::fs::remove_dir_all(&tmp);
}
