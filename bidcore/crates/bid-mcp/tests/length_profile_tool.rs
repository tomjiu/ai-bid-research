//! #287 篇幅档位工具面测试。
//!
//! 覆盖：
//! - `build_outline` 三种传参方式（档位 / 显式字数 / 都不给——验收 9）
//!   + 双参优先序（显式字数覆盖档位）+ 非法档位键显式拒
//! - `recommend_length_profile`（验收 8）：路由 / 空条款面 E_STATE /
//!   响应形态（alternatives 全档位 + reasons + signals 原始值回显）
//! - 门禁档位联动（验收 10）：E_TOTAL_CHARS_BELOW_MIN 随选中档位
//!   （outline_total_chars == 选中档目标，非固定 844,000）
//!
//! 真件：synth-tender A 件（docx——与 outline_default_quota 同款基座）。

use bid_mcp::{dispatch_with, BidService, ToolCall, ToolReply};
use serde_json::{json, Value};
use std::path::PathBuf;

fn call(svc: &mut BidService, tool: &str, args: Value) -> ToolReply {
    dispatch_with(svc, ToolCall { tool: tool.to_string(), args })
}

fn ok_result(reply: ToolReply) -> Value {
    match reply {
        ToolReply::Ok(out) => out.result,
        ToolReply::Err { error, .. } => panic!("预期成功，实际错误: {error}"),
    }
}

fn err_code(reply: ToolReply) -> String {
    match reply {
        ToolReply::Err { error, .. } => error.code().to_string(),
        ToolReply::Ok(out) => panic!("预期失败，实际成功: {}", out.result),
    }
}

fn fixtures_root() -> PathBuf {
    let p = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../../fixtures");
    std::fs::canonicalize(&p).unwrap_or(p)
}

fn tmp_ws(tag: &str) -> PathBuf {
    let d = std::env::temp_dir().join(format!(
        "bid-length-profile-{tag}-{}-{}",
        std::process::id(),
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_nanos()
    ));
    std::fs::create_dir_all(&d).unwrap();
    d
}

/// 建项 + 导入 synth-tender A 件 + 抽取 → (svc, pid)（与 outline_default_quota 同款）。
fn extracted_project(tag: &str) -> (BidService, String) {
    let ws = tmp_ws(tag);
    let mut svc = BidService::open(&ws)
        .expect("打开工作区")
        .with_fs_root(fixtures_root());
    ok_result(call(
        &mut svc,
        "create_bid_project",
        json!({
            "name": format!("#287 篇幅档位 {tag}"), "bid_deadline": "2026-11-30",
            "mode": "明标", "external_key": format!("length-profile-{tag}"),
        }),
    ));
    let pid = "PRJ-0001".to_string();
    let a = fixtures_root().join("synth-tender/招标文件/A-招标文件.docx");
    assert!(a.is_file(), "夹具缺失: {}", a.display());
    let import = ok_result(call(
        &mut svc,
        "import_tender_files",
        json!({
            "project_id": &pid,
            "files": [{ "upload_ref": a.display().to_string(),
                        "filename": "A-招标文件.docx", "kind": "招标文件" }],
        }),
    ));
    assert_eq!(import["totals"]["parse_failed"], json!(0), "A 件应解析成功: {import:?}");
    ok_result(call(
        &mut svc,
        "extract_requirements",
        json!({ "project_id": &pid }),
    ));
    (svc, pid)
}

/// 验收 9：build_outline 三种传参方式都工作 + 优先序 + 非法键拒。
#[test]
fn build_outline_three_param_forms() {
    // ---- 形态 1：都不给 → 默认档 Conservative 1,200,000
    let (mut svc, pid) = extracted_project("default");
    let out = ok_result(call(
        &mut svc,
        "build_outline",
        json!({ "project_id": &pid }),
    ));
    assert_eq!(out["length"]["profile"], json!("conservative"), "默认档: {out:?}");
    assert_eq!(out["length"]["target_total_chars"], json!(1_200_000));
    assert_eq!(out["length"]["approx_pages"], json!(1422));
    assert_eq!(
        svc.store().outline_total_chars(),
        1_200_000,
        "配额总和 = 默认档目标（门禁阈值随档）"
    );
    let _ = std::fs::remove_dir_all(tmp_ws("default"));

    // ---- 形态 2：length_profile 档位
    let (mut svc, pid) = extracted_project("profile");
    let out = ok_result(call(
        &mut svc,
        "build_outline",
        json!({ "project_id": &pid, "length_profile": "practical" }),
    ));
    assert_eq!(out["length"]["profile"], json!("practical"));
    assert_eq!(out["length"]["target_total_chars"], json!(400_000));
    assert_eq!(out["length"]["approx_pages"], json!(474));
    assert_eq!(svc.store().outline_total_chars(), 400_000);
    let _ = std::fs::remove_dir_all(tmp_ws("profile"));

    // ---- 形态 3：显式字数（custom 档回显）
    let (mut svc, pid) = extracted_project("chars");
    let out = ok_result(call(
        &mut svc,
        "build_outline",
        json!({ "project_id": &pid, "target_total_chars": 600_000 }),
    ));
    assert_eq!(out["length"]["profile"], json!("custom"), "非四档字数 → custom: {out:?}");
    assert_eq!(out["length"]["target_total_chars"], json!(600_000));
    assert_eq!(svc.store().outline_total_chars(), 600_000);
    let _ = std::fs::remove_dir_all(tmp_ws("chars"));

    // ---- 优先序：双参同给 → 显式字数覆盖档位
    let (mut svc, pid) = extracted_project("precedence");
    let out = ok_result(call(
        &mut svc,
        "build_outline",
        json!({ "project_id": &pid, "length_profile": "maximum",
                "target_total_chars": 500_000 }),
    ));
    assert_eq!(out["length"]["target_total_chars"], json!(500_000), "显式字数优先");
    assert_eq!(out["length"]["profile"], json!("custom"));
    let _ = std::fs::remove_dir_all(tmp_ws("precedence"));

    // ---- 非法档位键 → E_UNPROCESSABLE（拼错档不得静默落默认档）
    let (mut svc, pid) = extracted_project("badkey");
    assert_eq!(
        err_code(call(
            &mut svc,
            "build_outline",
            json!({ "project_id": &pid, "length_profile": "insurance" }),
        )),
        "E_UNPROCESSABLE"
    );
    let _ = std::fs::remove_dir_all(tmp_ws("badkey"));
}

/// 验收 8：recommend_length_profile——路由 / 前置 / 响应形态。
#[test]
fn recommend_length_profile_tool_contract() {
    // 路由：未知项目 E_NOTFOUND
    let (mut svc, _pid) = extracted_project("route");
    assert_eq!(
        err_code(call(
            &mut svc,
            "recommend_length_profile",
            json!({ "project_id": "P-不存在" }),
        )),
        "E_NOTFOUND"
    );

    // 前置：条款面空 → E_STATE（建项未抽取）
    let ws = tmp_ws("empty");
    let mut svc2 = BidService::open(&ws).expect("打开工作区").with_fs_root(fixtures_root());
    ok_result(call(
        &mut svc2,
        "create_bid_project",
        json!({ "name": "#287 空条款面", "bid_deadline": "2026-11-30",
                "mode": "明标", "external_key": "length-profile-empty" }),
    ));
    assert_eq!(
        err_code(call(
            &mut svc2,
            "recommend_length_profile",
            json!({ "project_id": "PRJ-0001" }),
        )),
        "E_STATE",
        "条款面空 → E_STATE 提示先 extract"
    );
    let _ = std::fs::remove_dir_all(ws);

    // 响应形态：五档 alternatives + reasons + signals 原始值（#133 补紧凑档）
    let out = ok_result(call(
        &mut svc,
        "recommend_length_profile",
        json!({ "project_id": "PRJ-0001" }),
    ));
    for key in [
        "recommended_profile", "profile_label", "target_chars", "approx_pages",
        "confidence", "reasons", "from_tender_spec", "alternatives", "signals", "next",
    ] {
        assert!(out.get(key).is_some(), "响应缺 {key}: {out:?}");
    }
    let alts = out["alternatives"].as_array().unwrap();
    assert_eq!(alts.len(), 5, "alternatives 必须全五档（用户能做选择）: {alts:?}");
    let alt_profiles: Vec<&str> = alts.iter().filter_map(|a| a["profile"].as_str()).collect();
    for expect in ["compact", "practical", "standard", "conservative", "maximum"] {
        assert!(alt_profiles.contains(&expect), "alternatives 缺 {expect}: {alt_profiles:?}");
    }
    for a in alts {
        assert!(a["when"].as_str().unwrap_or("").len() >= 8, "alternative 带 when 提示: {a:?}");
    }
    assert!(
        !out["reasons"].as_array().unwrap().is_empty(),
        "理由必须非空（逐信号一行）: {out:?}"
    );
    let signals = &out["signals"];
    for key in ["scoring_detail_count", "star_count", "budget_yuan", "tender_pages", "tender_type", "explicit_limit_chars"] {
        assert!(signals.get(key).is_some(), "signals 缺 {key}: {signals:?}");
    }
    // synth A 件（小型合成件）：细则数信号弱 → 置信度如实
    let conf = out["confidence"].as_str().unwrap();
    assert!(
        ["high", "medium", "low"].contains(&conf),
        "置信度枚举: {conf}"
    );
    // 推荐档有效性：recommended ∈ 五档 且 target_chars 匹配该档（synth 无明写篇幅）
    let rec = out["recommended_profile"].as_str().unwrap();
    assert!(
        ["compact", "practical", "standard", "conservative", "maximum"].contains(&rec),
        "推荐档枚举: {rec}"
    );
    if out["from_tender_spec"].is_null() {
        let expect = bid_domain::outline::LengthProfile::from_key(rec)
            .map(|p| p.target_total_chars())
            .unwrap();
        assert_eq!(out["target_chars"], json!(expect), "无明写时 target=推荐档字数");
    }
}

/// 验收 10：门禁按选中档位判定——E_TOTAL_CHARS_BELOW_MIN 的阈值 =
/// outline_total_chars()（选中档目标），非固定 844,000。
///
/// 直调域层校验器（validate_document——MCP 工具态门要 DRAFTING，此处
/// 校验的是**规则本身**与档位的联动，不走状态机面）。
#[test]
fn gate_follows_selected_profile() {
    // Practical 档建纲（400k）→ 总量门阈值 400k：起草 0 字 < 400k 必触发
    let (mut svc, pid) = extracted_project("gate");
    let _ = ok_result(call(
        &mut svc,
        "build_outline",
        json!({ "project_id": &pid, "length_profile": "practical" }),
    ));
    assert_eq!(svc.store().outline_total_chars(), 400_000, "Practical 档配额总和");
    let report = bid_tools::validate::validate_document(
        svc.store(),
        None,
        &mut bid_tools::validate::NoModel,
    )
    .expect("全量校验");
    let total = report
        .findings
        .iter()
        .find(|f| f.rule_code == "E_TOTAL_CHARS_BELOW_MIN")
        .unwrap_or_else(|| panic!("空稿必须触发 E_TOTAL_CHARS_BELOW_MIN: {:?}", report.findings));
    assert!(
        total.message.contains("400000"),
        "门禁阈值必须按选中档（Practical 400,000），非固定 844,000: {}",
        total.message
    );
    assert!(
        !total.message.contains("844000"),
        "不得再出现旧默认 844,000: {}",
        total.message
    );
    let _ = std::fs::remove_dir_all(tmp_ws("gate"));
}

// ---------------------------------------------------------------- 验收 11：真语料推荐合理性

/// 真语料推荐档位合理性（issue #287 验收 11）：
/// - hq-dev-procure（69★ 设备采购）→ Conservative 或 Maximum
/// - wenming（8★ 传媒服务）→ Standard 或 Conservative
/// - nm-health-terminal（询价小项目）→ Practical
///
/// 环境门（AGENTS 测试纪律 + issue #9）：布局引擎（poppler 三件套或
/// MDC_PDFIUM_LIB）不在位 → SKIP 横幅；导入失败（无引擎形态下兜底路
/// fail-loud）→ SKIP 横幅。断言按档位**集合**断（信号面跨解析路有
/// 细粒度差异，档位结论必须稳定）。
#[test]
fn real_corpus_recommendation_sanity() {
    // 环境门：poppler 三件套 或 pdfium 显式库（#285 同款双臂）
    let pdfium_ok = std::env::var("MDC_PDFIUM_LIB")
        .map(|p| !p.is_empty() && std::path::Path::new(&p).exists())
        .unwrap_or(false);
    if !pdfium_ok
        && bid_parse::env_preflight::skip_if_env_missing(
            "star_287_real_corpus_recommendation",
            bid_parse::env_preflight::POPPLER_TEXT_TOOLS,
        )
    {
        return;
    }
    let root = fixtures_root();
    // 真实招标标题（manifest.title）作项目名——类型推断吃项目名，测试名
    // 会污染信号（保真：Agent 建项时用的就是招标标题）
    let manifest_title = |batch: &str, id: &str| -> String {
        let m = std::fs::read_to_string(root.join(batch).join("manifest.json"))
            .unwrap_or_default();
        let v: Value = serde_json::from_str(&m).unwrap_or(json!({}));
        v["tenders"]
            .as_array()
            .and_then(|a| {
                a.iter()
                    .find(|t| t["id"] == json!(id))
                    .and_then(|t| t["title"].as_str())
                    .map(String::from)
            })
            .unwrap_or_else(|| id.to_string())
    };
    // #133 规模因子后期望集（预算走 params ∪ 锚文兜底两面）：
    // - hq-dev（151.9 万预算/89 页/28 细则/29★）：基档 Conservative，
    //   预算 < 200 万 + 页数 ≤ 100 且预算 < 500 万 → 两档下调 → practical；
    // - wenming（30 万/63 页/8★）：同型两档下调 → compact/practical；
    // - nm-health（batch2 缺件 SKIP）：同口径。
    let cases: &[(&str, &str, PathBuf, &[&str])] = &[
        (
            "hq-dev-procure-230001",
            "real-tender-batch1",
            root.join("real-tender-batch1/hq-dev-procure-230001"),
            &["practical"],
        ),
        (
            "wenming-longjiang-230001",
            "real-tender-batch1",
            root.join("real-tender-batch1/wenming-longjiang-230001"),
            &["compact", "practical"],
        ),
        (
            "nm-health-terminal",
            "real-tender-batch2",
            root.join("real-tender-batch2/nm-health-terminal"),
            &["compact", "practical"],
        ),
    ];
    for (id, batch, dir, allowed) in cases {
        let title = manifest_title(batch, id);
        let Some(pdf) = std::fs::read_dir(&dir)
            .ok()
            .and_then(|rd| {
                rd.filter_map(|e| e.ok())
                    .map(|e| e.path())
                    .find(|p| p.extension().map(|e| e == "pdf").unwrap_or(false))
            })
        else {
            eprintln!("【SKIP】{id} fixture 不在仓（{dir:?}）");
            continue;
        };
        let ws = tmp_ws("corpus");
        let mut svc = match BidService::open(&ws) {
            Ok(s) => s.with_fs_root(&dir),
            Err(e) => panic!("打开工作区: {e}"),
        };
        ok_result(call(
            &mut svc,
            "create_bid_project",
            json!({ "name": &title, "bid_deadline": "2026-12-31",
                    "mode": "明标", "external_key": format!("length-287-{id}") }),
        ));
        let import = match call(
            &mut svc,
            "import_tender_files",
            json!({ "project_id": "PRJ-0001", "files": [{
                "upload_ref": pdf.display().to_string(),
                "filename": pdf.file_name().unwrap().to_string_lossy(), "kind": "招标文件" }]}),
        ) {
            ToolReply::Ok(out) => out.result,
            ToolReply::Err { error, .. } => {
                eprintln!("【SKIP】{id} 本环境导入失败（{error}）——无外部引擎形态，推荐信号不可信");
                let _ = std::fs::remove_dir_all(&ws);
                continue;
            }
        };
        if import["per_file"][0]["parse_status"] != json!("ok") {
            eprintln!("【SKIP】{id} 解析不开（{:?}）", import["per_file"][0]["parse_error"]);
            let _ = std::fs::remove_dir_all(&ws);
            continue;
        }
        ok_result(call(
            &mut svc,
            "extract_requirements",
            json!({ "project_id": "PRJ-0001" }),
        ));
        let out = ok_result(call(
            &mut svc,
            "recommend_length_profile",
            json!({ "project_id": "PRJ-0001" }),
        ));
        let rec = out["recommended_profile"].as_str().unwrap_or("");
        let sig = &out["signals"];
        println!(
            "[{id}] → {rec}（细则 {} ★{} 预算 {:?} 类型 {} 明写 {:?}）\n  理由: {:?}",
            sig["scoring_detail_count"], sig["star_count"], sig["budget_yuan"],
            sig["tender_type"], sig["explicit_limit_chars"],
            out["reasons"].as_array().map(|a| a.iter().filter_map(|v| v.as_str()).collect::<Vec<_>>()).unwrap_or_default()
        );
        assert!(
            allowed.contains(&rec),
            "{id} 推荐档 {rec} 不在预期集 {allowed:?}（验收 11 档位合理性）\n{out}"
        );
        let _ = std::fs::remove_dir_all(&ws);
    }
}

// ---------------------------------------------------------------- #133 A2：松岭真件门（环境门）

/// 层1 互斥锁（与 songling_scoring_outline 同因：4G/2核沙箱 PDF 解析内存约束）。
fn engine_lock() -> &'static std::sync::Mutex<()> {
    static LOCK: std::sync::OnceLock<std::sync::Mutex<()>> = std::sync::OnceLock::new();
    LOCK.get_or_init(|| std::sync::Mutex::new(()))
}

/// #133 A2 验收（issue 原文）：松岭重跑推荐档位 ≠ 1.2M（规模因子生效）；
/// 紧凑档可选（alternatives 含 compact）。
///
/// 审计 AUD2-HIS-A2 实锤面：松岭 65 页/预算 119.6 万/20 评分细则 →
/// 旧算法推保险型 1.2M 字（≈1422 页）——小项目现实篇幅落在阶梯之外。
/// 新算法：预算 < 200 万 + 页数 ≤ 100 且预算 < 500 万 → 两档规模下调
/// → 实用型 400k（≈474 页，中型服务现实篇幅带 200-500 页顶端）。
#[test]
fn songling_133_scale_factors_recommend_gate() {
    use bid_parse::env_preflight::{skip_if_env_missing, skip_if_fixture_missing, POPPLER_TEXT_TOOLS};
    if skip_if_env_missing("songling_133_scale_recommend", POPPLER_TEXT_TOOLS) {
        return; // SKIP（环境缺 poppler——如实跳过，不伪造）
    }
    let _guard = engine_lock().lock().unwrap();
    let pdf = fixtures_root().join("songling-232762/tender/光纤租赁费招标文件.pdf");
    if skip_if_fixture_missing("songling_133_scale_recommend", &[&pdf]) {
        return;
    }

    // 全链：导入 → 抽取（推荐信号来自 REQ 面——无需建纲）
    let ws = tmp_ws("songling-133");
    let mut svc = BidService::open(&ws)
        .expect("打开工作区")
        .with_fs_root(fixtures_root());
    ok_result(call(
        &mut svc,
        "create_bid_project",
        json!({
            "name": "松岭规模因子推荐", "bid_deadline": "2026-11-30",
            "mode": "明标", "external_key": "sl-133-scale",
        }),
    ));
    let import = ok_result(call(
        &mut svc,
        "import_tender_files",
        json!({
            "project_id": "PRJ-0001",
            "files": [{ "upload_ref": pdf.display().to_string(),
                        "filename": "光纤租赁费招标文件.pdf", "kind": "招标文件" }],
        }),
    ));
    assert_eq!(import["totals"]["parse_failed"], json!(0), "松岭件应解析成功: {import:?}");
    ok_result(call(
        &mut svc,
        "extract_requirements",
        json!({ "project_id": "PRJ-0001" }),
    ));

    let out = ok_result(call(
        &mut svc,
        "recommend_length_profile",
        json!({ "project_id": "PRJ-0001" }),
    ));
    let _ = std::fs::remove_dir_all(&ws);

    // 门 1（issue 验收原文）：推荐档位 ≠ 1.2M——规模因子生效
    let rec = out["recommended_profile"].as_str().unwrap();
    assert_ne!(
        rec, "conservative",
        "#133 A2：松岭（119.6 万/65 页）不再推保险型 1.2M: {out:?}"
    );
    // 门 2：实用型（400k ≈ 474 页——降 2 档：Conservative → Standard → Practical）
    assert_eq!(rec, "practical", "松岭面 → 实用型: {out:?}");
    assert_eq!(out["target_chars"], json!(400_000));
    // 门 3：理由明示规模因子（命中行 + 下调结算行）
    let joined = out["reasons"].as_array().unwrap()
        .iter().filter_map(|s| s.as_str()).collect::<Vec<_>>().join("\n");
    assert!(joined.contains("规模下调一档"), "规模因子命中行缺失: {joined}");
    assert!(joined.contains("规模因子命中"), "下调结算行缺失: {joined}");
    // 门 4：信号回显——页数/预算真值在场（65 页/119.58 万；预算走锚文
    // 兜底面：para 预算行无 params.amount_wan——bid_parse::budget_yuan_wan）
    let pages = out["signals"]["tender_pages"].as_u64().unwrap();
    assert!((60..=65).contains(&pages), "松岭页数信号 ≈ 65: {pages}");
    let budget = out["signals"]["budget_yuan"].as_u64().unwrap();
    assert_eq!(budget, 1_195_800, "松岭预算信号 119.58 万（锚文兜底面）: {budget}");
    // 门 5（issue 验收原文）：紧凑档可选——alternatives 全五档含 compact
    let alts = out["alternatives"].as_array().unwrap();
    assert!(alts.iter().any(|a| a["profile"] == json!("compact")), "紧凑档可选: {alts:?}");
}
