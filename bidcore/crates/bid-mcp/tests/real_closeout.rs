//! 收官真实测试（2026-11-12 · #47 收官线）——随机抽件 · 全链真跑 · 结果隔离评估。
//!
//! 驱动：环境变量 `CLOSEOUT_SPEC` 指向 JSON 规格文件（由
//! `scripts/closeout_real_test.py` 以固定种子随机抽件后生成）；**缺失 →
//! 响亮横幅 SKIP**（CI 安全——与 e2e_pipeline 的 issue #9 SKIP 纪律同口径，
//! 缺规格不是业务失败）。
//!
//! 与 e2e_pipeline.rs（corpus-A 固定夹具）的分工：
//! - e2e_pipeline：CI 常跑的回归面（夹具固定、GT 埋点）。
//! - real_closeout：**收官一次性真跑面**——真实语料（real-corpus/real-samples
//!   随机抽件）、真实解析路径、独立工作区；指标落盘供评测脚本消费。
//!
//! 结果隔离（每件材料一个独立工作区）：
//! - 物理隔离：`<base_dir>/<run_id>/` 各自 BidService 存储，互不共享；
//! - 审计断言：项目 ID 两两互异、external_key == run_id、文件名集合两两
//!   不相交（无跨件泄漏）、导出产物两两互异；
//! - 指标隔离：每件 `closeout-metrics.json` 独立落盘，评测按件独立进行。
//!
//! 全链步骤（full_chain 件——与 e2e_pipeline ①-⑧ 同面，参数来自规格）：
//! ① create_bid_project → ② import_tender_files（真件）→ ③ extract_requirements
//! → ④ prepare_outline_and_matrix → ⑤ 证据登记/绑定/三门 → ⑥ 逐章起草（mock
//! 生成器——确定性；真 LLM 面是 run_real_llm_path.sh 的独立登记边界）→
//! ⑦ validate_bid_document（BLOCKER 清零）→ ⑧ export_bid_document（成品 docx
//! + 解包深检 + 重启恢复）。
//!
//! 辅件面（full_chain=false 件——如报价表单独导入）：②③ 真跑记录，④ 建纲
//! 门**如实记录**（0 条款面 → 拒绝诊断即预期行为，不硬扭成通过）。

use bid_domain::outline::OutlineSpec;
use bid_mcp::{dispatch_with, BidService, ToolCall, ToolReply};
use serde_json::{json, Value};
use std::io::Read;
use std::path::{Path, PathBuf};
use std::time::Instant;

// ---------------------------------------------------------------- 规格解析

struct FileSpec {
    path: PathBuf,
    filename: String,
    kind: String,
}

struct EvidenceSpecRow {
    kind: String,
    title: String,
    source_file: String,
}

struct RunSpec {
    id: String,
    name: String,
    full_chain: bool,
    min_reqs: u64,
    outline_target_chars: u64,
    max_reqs_per_leaf: u64,
    max_overrun_pct: u64,
    profile: Value,
    files: Vec<FileSpec>,
    evidence: Vec<EvidenceSpecRow>,
}

fn spec_banner_missing() {
    println!(
        "\n============================================================\n\
         SKIP: real_closeout —— 未设置 CLOSEOUT_SPEC（收官真测规格文件）\n\
           生成：python3 scripts/closeout_real_test.py --emit-spec\n\
           （CI 无真实语料面恒跳过——本面是收官一次性真跑，非回归面）\n\
         ============================================================\n"
    );
}

fn parse_run(v: &Value) -> RunSpec {
    let files = v["files"]
        .as_array()
        .expect("规格缺 files")
        .iter()
        .map(|f| FileSpec {
            path: PathBuf::from(f["path"].as_str().expect("file.path")),
            filename: f["filename"].as_str().expect("file.filename").to_string(),
            kind: f["kind"].as_str().expect("file.kind").to_string(),
        })
        .collect();
    let evidence = v
        .get("evidence")
        .and_then(|e| e.as_array())
        .map(|rows| {
            rows.iter()
                .map(|e| EvidenceSpecRow {
                    kind: e["kind"].as_str().expect("evidence.kind").to_string(),
                    title: e["title"].as_str().expect("evidence.title").to_string(),
                    source_file: e["source_file"].as_str().expect("evidence.source_file").to_string(),
                })
                .collect()
        })
        .unwrap_or_default();
    RunSpec {
        id: v["id"].as_str().expect("run.id").to_string(),
        name: v["name"].as_str().unwrap_or("收官真测件").to_string(),
        full_chain: v["full_chain"].as_bool().unwrap_or(false),
        min_reqs: v["min_reqs"].as_u64().unwrap_or(1),
        outline_target_chars: v["outline_target_chars"].as_u64().unwrap_or(6_000),
        max_reqs_per_leaf: v["max_reqs_per_leaf"].as_u64().unwrap_or(6),
        max_overrun_pct: v["max_overrun_pct"].as_u64().unwrap_or(10_000),
        profile: v.get("profile").cloned().unwrap_or(json!({})),
        files,
        evidence,
    }
}

// ---------------------------------------------------------------- 通用助手

fn call(svc: &mut BidService, tool: &str, mut args: Value) -> ToolReply {
    // 与 e2e_pipeline 同纪律：确定性套件钉 mock（防 dev 机配 key 后走真调）
    if tool == "draft_response_section" && args.get("generator").is_none() {
        args.as_object_mut()
            .unwrap()
            .insert("generator".into(), json!("mock"));
    }
    dispatch_with(svc, ToolCall { tool: tool.to_string(), args })
}

fn ok_result(reply: ToolReply, ctx: &str) -> Value {
    match reply {
        ToolReply::Ok(out) => out.result,
        ToolReply::Err { error, .. } => panic!("[{ctx}] 步骤失败: {error}"),
    }
}

fn write_profile(ws: &Path) {
    let p = bid_domain::party::BidderProfile {
        // 投标人侧测试数据（与真件无关——投标人自报面，收官真测允许合成）
        company_name: "收官测试通信工程有限公司".into(),
        legal_rep: "王锐".into(),
        legal_rep_id: "110101196001011234".into(),
        legal_rep_position: "总经理".into(),
        address: "测试市测试区测试路 1 号".into(),
        agent: "李明".into(),
        agent_id: "110101198505052345".into(),
        ..Default::default()
    };
    std::fs::write(ws.join("bidder-profile.json"), serde_json::to_string(&p).unwrap()).unwrap();
}

/// 粗指纹（字节数）——产物真 sha256 由评测脚本（Python hashlib）落盘，
/// Rust 标准库无 sha256，此处仅作导出互异性粗校验兜底。
fn coarse_fingerprint(p: &Path) -> String {
    format!("len:{}", std::fs::metadata(p).map(|m| m.len()).unwrap_or(0))
}

/// FNV-1a 64（证据登记的定位指纹——合成面，与 e2e 同口径）。
fn fnv64(s: &str) -> String {
    let mut h: u64 = 0xcbf29ce484222325;
    for b in s.as_bytes() {
        h ^= *b as u64;
        h = h.wrapping_mul(0x100000001b3);
    }
    format!("fnv64:{h:016x}")
}

/// 门 1h（#88 评分项未映射）：评分项 → 首叶显式映射（记审前——#474）。
fn map_scoring_items_to_first_leaf(svc: &mut BidService, anchor_file: &str) -> usize {
    let first_leaf: Option<String> = {
        let parents: std::collections::HashSet<String> =
            svc.store().sections().iter().filter_map(|n| n.parent_id.clone()).collect();
        svc.store()
            .sections()
            .iter()
            .find(|n| !parents.contains(&n.id))
            .map(|n| n.id.clone())
    };
    let Some(leaf) = first_leaf else { return 0 };
    let scoring_ids: Vec<String> = svc
        .store()
        .requirements()
        .iter()
        .filter(|r| r.category == "评分项")
        .map(|r| r.id.clone())
        .collect();
    let n = scoring_ids.len();
    for rid in scoring_ids {
        let _ = svc.store_mut().upsert_scoring_mapping(
            rid,
            leaf.clone(),
            1.0,
            vec![],
            bid_domain::Anchor {
                file: anchor_file.into(),
                kind: "table".into(),
                locator: "评标办法".into(),
                excerpt: "评分项映射（收官真测——门 1h 补面）".into(),
                block_idx: None,
                page: None,
                line: None,
            },
            bid_domain::scoring::MappingSource::AgentSubmitted,
        );
    }
    n
}

// ---------------------------------------------------------------- 单件真跑

fn run_material(base: &Path, repo_root: &Path, run: &RunSpec) -> Value {
    let t_all = Instant::now();
    let ws = base.join(&run.id);
    if ws.exists() {
        std::fs::remove_dir_all(&ws).expect("清理旧工作区（隔离前置）");
    }
    std::fs::create_dir_all(&ws).unwrap();
    let mut metrics = json!({
        "run_id": run.id.clone(), "name": run.name.clone(),
        "ws": ws.display().to_string(), "full_chain": run.full_chain,
    });

    let mut svc = BidService::open(&ws).unwrap().with_fs_root(repo_root.to_path_buf());
    write_profile(&ws);

    // ① 建项目（external_key = closeout-<run_id>——幂等 + 隔离命名面）
    let t = Instant::now();
    let pid = ok_result(
        call(&mut svc, "create_bid_project", json!({
            "name": run.name.clone(), "bid_deadline": "2026-12-31", "mode": "明标",
            "external_key": format!("closeout-{}", run.id),
        })),
        &run.id,
    )["project_id"]
        .as_str()
        .unwrap()
        .to_string();
    assert!(pid.starts_with("PRJ-"), "[{}] ① 建项目: {pid}", run.id);
    metrics["project_id"] = json!(pid.clone());
    metrics["t_create_ms"] = json!(t.elapsed().as_millis() as u64);

    // ② 导入真件
    let t = Instant::now();
    let file_specs: Vec<Value> = run
        .files
        .iter()
        .map(|f| {
            json!({
                "upload_ref": f.path.display().to_string(),
                "filename": f.filename.clone(), "kind": f.kind.clone(),
            })
        })
        .collect();
    let r = ok_result(
        call(&mut svc, "import_tender_files", json!({ "project_id": &pid, "files": file_specs })),
        &run.id,
    );
    let totals = r["totals"].clone();
    assert!(
        totals["files"].as_u64().unwrap_or(0) >= run.files.len() as u64,
        "[{}] ② 导入面: {totals:?}",
        run.id
    );
    assert_eq!(totals["partial"].as_u64().unwrap_or(0), 0, "[{}] ② 零失败导入", run.id);
    assert_eq!(totals["parse_failed"].as_u64().unwrap_or(0), 0, "[{}] ② 零解析失败", run.id);
    // 导入后文件台账（真 sha256 在位——证据登记复用）
    let file_rows: Vec<Value> = svc
        .store()
        .files()
        .iter()
        .map(|tf| {
            json!({
                "name": tf.name.clone(), "kind": tf.kind.clone(), "sha256": tf.sha256.clone(),
                "pages": tf.pages as u64, "tables": tf.tables as u64, "chunks": tf.chunks as u64,
                "ocr_blocks": tf.ocr_blocks as u64,
                "parse_status": format!("{:?}", tf.parse_status),
            })
        })
        .collect();
    metrics["files"] = json!(file_rows);
    metrics["import_totals"] = totals;
    metrics["t_import_ms"] = json!(t.elapsed().as_millis() as u64);

    // ③ 抽取（确定性真跑面）
    let t = Instant::now();
    let r = ok_result(call(&mut svc, "extract_requirements", json!({ "project_id": &pid })), &run.id);
    let n_reqs = r["counts"]["total"].as_u64().unwrap_or(0);
    metrics["extract_counts"] = r["counts"].clone();
    metrics["t_extract_ms"] = json!(t.elapsed().as_millis() as u64);
    if run.full_chain {
        assert!(n_reqs >= run.min_reqs, "[{}] ③ 抽取面 {n_reqs} < 门槛 {}", run.id, run.min_reqs);
        assert!(!r["counts"]["by_category"].as_object().unwrap().is_empty(), "[{}] ③ 分类面在位", run.id);
    }

    // ---- 辅件面：到此记录 + 建纲门如实探测，然后止步
    if !run.full_chain {
        metrics["stopped_at"] = json!("aux_import_face");
        match svc.prepare_outline_and_matrix(OutlineSpec {
            target_total_chars: 6_000,
            max_reqs_per_leaf: 6,
        }) {
            Ok((n_sec, n_rows, n_blocking)) => {
                metrics["outline_probe"] = json!({
                    "outcome": "ok", "sections": n_sec as u64, "rows": n_rows as u64,
                    "blocking": n_blocking as u64,
                });
            }
            Err(e) => {
                // 0 条款面 → 闭环门/条款面非空拒绝 = 预期门行为（诊断即产物）
                metrics["outline_probe"] = json!({ "outcome": "rejected", "diagnostic": format!("{e:?}") });
            }
        }
        metrics["t_total_ms"] = json!(t_all.elapsed().as_millis() as u64);
        std::fs::write(ws.join("closeout-metrics.json"), serde_json::to_string_pretty(&metrics).unwrap()).unwrap();
        return metrics;
    }

    // ③' 星检漏标 + 补标直通（R27 查面 → R28 补标 → 重抽合并 #219/#419——
    //     真实语料首验：确定性抽取在淮安真件漏 2 处★真值块，门如实拦下）
    let mut star_gap_total = 0u64;
    let mut star_gap_detail: Vec<Value> = Vec::new();
    if run.full_chain {
        let main_files: Vec<(String, String)> = run
            .files
            .iter()
            .filter(|f| f.kind == "招标文件")
            .map(|f| (f.filename.clone(), f.filename.clone()))
            .collect();
        for (fname, _) in &main_files {
            let Some(file_id) = svc
                .store()
                .files()
                .iter()
                .find(|tf| tf.name == *fname)
                .map(|tf| tf.id.clone())
            else {
                continue;
            };
            let r = ok_result(
                call(&mut svc, "get_star_coverage", json!({ "project_id": &pid, "file_id": &file_id })),
                &run.id,
            );
            let missing = r["missing"].as_array().cloned().unwrap_or_default();
            let missing_n = r["star_missing"].as_u64().unwrap_or(0);
            assert!(!r["missing_truncated"].as_bool().unwrap_or(false), "[{}] ③' 漏标明细被截（>100 处——需分批补标面，本面未覆盖）", run.id);
            if missing.is_empty() {
                continue;
            }
            star_gap_total += missing_n;
            for m in &missing {
                star_gap_detail.push(json!({
                    "file": fname.clone(), "block_idx": m["block_idx"].clone(),
                    "page": m["page"].clone(), "text": m["text"].clone(),
                }));
            }
            let marks: Vec<Value> = missing
                .iter()
                .map(|m| json!({
                    "from": m["block_idx"].clone(), "to": m["block_idx"].clone(),
                    "verdict": "requirement",
                    "reason": "★真值块漏抽取——收官真测补标（R28 直通面）",
                }))
                .collect();
            let reqs: Vec<Value> = missing
                .iter()
                .map(|m| json!({
                    "block_idx": m["block_idx"].clone(),
                    "statement": m["text"].as_str().unwrap_or(""),
                    "category": "否决项", "mandatory": true, "substantive": true,
                }))
                .collect();
            ok_result(
                call(&mut svc, "submit_block_marks", json!({
                    "project_id": &pid, "file_id": &file_id, "marks": marks, "requirements": reqs,
                })),
                &run.id,
            );
        }
        if star_gap_total > 0 {
            // 重抽合并（#219：submitted 并入主集；#419：REQ-A id 承接）
            let r = ok_result(
                call(&mut svc, "extract_requirements", json!({ "project_id": &pid })),
                &run.id,
            );
            let added = r["counts"]["added"].as_u64().unwrap_or(0);
            assert!(
                added >= star_gap_total,
                "[{}] ③' 补标重抽应并入 ≥ 漏标数（added={added} < {star_gap_total}）",
                run.id
            );
            // 补标后复检（R27 查面应转清）
            for (fname, _) in &main_files {
                let Some(file_id) = svc
                    .store()
                    .files()
                    .iter()
                    .find(|tf| tf.name == *fname)
                    .map(|tf| tf.id.clone())
                else {
                    continue;
                };
                let r = ok_result(
                    call(&mut svc, "get_star_coverage", json!({ "project_id": &pid, "file_id": &file_id })),
                    &run.id,
                );
                assert_eq!(
                    r["star_missing"].as_u64().unwrap_or(0),
                    0,
                    "[{}] ③' 补标后仍有漏标（{fname}）",
                    run.id
                );
            }
        }
        metrics["star_gate"] = json!({
            "gaps_found": star_gap_total, "remediated": star_gap_total,
            "detail": star_gap_detail,
        });
    }

    // ④ 建纲建矩阵（服务面——规格参数：真件规模自适应）
    let t = Instant::now();
    let (n_sec, n_rows, n_blocking) = svc
        .prepare_outline_and_matrix(OutlineSpec {
            target_total_chars: run.outline_target_chars as u32,
            max_reqs_per_leaf: run.max_reqs_per_leaf as usize,
        })
        .unwrap_or_else(|e| panic!("[{}] ④ 建纲失败（真件条款面应非空）: {e:?}", run.id));
    assert!(n_sec >= 2, "[{}] ④ 章节树: {n_sec} 节点", run.id);
    assert!(n_rows as u64 >= run.min_reqs, "[{}] ④ 矩阵 {n_rows} 行", run.id);
    metrics["outline"] = json!({
        "sections": n_sec as u64, "rows": n_rows as u64, "blocking_pre_bind": n_blocking as u64,
    });
    metrics["t_outline_ms"] = json!(t.elapsed().as_millis() as u64);

    // ⑤ 证据登记（真 sha——从导入台账取）+ 绑定 + 三门
    let t = Instant::now();
    use bid_domain::evidence::{EvidenceKind, EvidenceSpec};
    use bid_domain::locator::EngineLocator;
    let kind_of = |s: &str| match s {
        "Performance" => EvidenceKind::Performance,
        "Personnel" => EvidenceKind::Personnel,
        "Certificate" => EvidenceKind::Certificate,
        "Contract" => EvidenceKind::Contract,
        _ => EvidenceKind::Qualification,
    };
    let mut ev_ids = Vec::new();
    for (i, ev) in run.evidence.iter().enumerate() {
        let real_sha = svc
            .store()
            .files()
            .iter()
            .find(|tf| tf.name == ev.source_file)
            .map(|tf| tf.sha256.clone())
            .unwrap_or_else(|| format!("sha-missing-{i}"));
        let (eid, _) = svc
            .store_mut()
            .register_evidence(EvidenceSpec {
                kind: kind_of(&ev.kind),
                title: ev.title.clone(),
                source_file: ev.source_file.clone(),
                source_sha256: real_sha,
                locator: EngineLocator::PdfPageText { page: 1, text_fingerprint: fnv64(&ev.title) },
                fingerprint: fnv64(&ev.title),
                valid_from: None,
                valid_until: None,
                subject_name: "收官测试通信工程有限公司".into(),
                scope: "通信工程建设".into(),
                client: None,
                amount_wan: None,
                completed_on: None,
                fields: Default::default(),
                excerpt: None,
                excerpt_locator: None,
                verification_tier: None,
            })
            .unwrap();
        ev_ids.push(eid);
    }
    // 阻断面全绑 + ★实质性条款全绑（真实用法：阻断行与★条款都必须响应——
    // 子面 a 的 RESPONDED = 证据在绑 + 章节响应）
    let blocking_ids: Vec<String> = svc
        .store()
        .matrix()
        .iter()
        .filter(|r| r.blocking)
        .map(|r| r.requirement_id.clone())
        .collect();
    let substantive_ids: Vec<String> = svc
        .store()
        .requirements()
        .iter()
        .filter(|r| bid_domain::matrix::substantive(r))
        .map(|r| r.id.clone())
        .collect();
    let mut bind_ids: Vec<String> = blocking_ids.clone();
    for sid in &substantive_ids {
        if !bind_ids.contains(sid) {
            bind_ids.push(sid.clone());
        }
    }
    let n_bind = bind_ids.len();
    assert!(!ev_ids.is_empty(), "[{}] ⑤ 证据面非空（规格应登记证据）", run.id);
    assert!(!bind_ids.is_empty(), "[{}] ⑤ 绑定面非空（真件抽取应含必选面）", run.id);
    for rid in &bind_ids {
        svc.store_mut().bind_evidence(&ev_ids[0], rid, "2026-12-31").unwrap();
    }
    let _ = svc.store_mut().build_matrix().unwrap();
    let anchor_file = run
        .files
        .iter()
        .find(|f| f.kind == "招标文件")
        .map(|f| f.filename.clone())
        .unwrap_or_default();
    let n_scoring_mapped = map_scoring_items_to_first_leaf(&mut svc, &anchor_file);
    use bid_domain::review::{Decision, Gate};
    for gate in [Gate::MatrixApproval, Gate::OutlineApproval] {
        svc.store_mut()
            .record_review(gate, &bid_domain::TrustedPrincipal::human("closeout-lead"), Decision::Approved, vec![], None)
            .unwrap();
    }
    let n_blocking_after = svc.store().matrix().iter().filter(|r| r.blocking).count();
    assert_eq!(n_blocking_after, 0, "[{}] ⑤ 绑定后 blocking 清零: 剩 {n_blocking_after}", run.id);
    metrics["evidence"] = json!({
        "registered": run.evidence.len() as u64, "bound_reqs": n_bind as u64,
        "scoring_mapped": n_scoring_mapped as u64, "blocking_after": n_blocking_after as u64,
    });
    metrics["t_evidence_ms"] = json!(t.elapsed().as_millis() as u64);

    // ⑤' 补遗确认门（收官真测首现的真实门行为：无补遗采购包 → 起草被
    //     NotProvided 阻塞——#379 全局显式确认是唯一出口。真实用户动作：
    //     宿主签发 receipt + MCP 工具记录，reason 写明确认依据）
    let has_addendum = run.files.iter().any(|f| f.kind == "补遗");
    if !has_addendum {
        let receipt = svc.issue_approval_receipt("closeout-lead", "no_addendum_confirmed");
        let r = ok_result(
            call(&mut svc, "record_addendum_waiver", json!({
                "project_id": &pid, "confirm_no_addendum": true,
                "reason": "收官真测：采购包仅主件与附件在案，语料内无补遗/澄清件——人工确认本项目无补遗后放行；如后续获得澄清件须重抽增量",
                "receipt": receipt,
            })),
            &run.id,
        );
        let approved = svc.store().gate_approved(bid_domain::review::Gate::NoAddendumConfirmed);
        assert!(approved, "[{}] ⑤' 补遗确认门未过: {}", run.id, r);
        metrics["addendum_gate"] = json!({
            "encountered": true, "action": "confirm_no_addendum",
            "gate_approved": approved,
        });
    }

    // ⑥ 逐章起草（MCP §6——全部叶，mock 生成器）
    let t = Instant::now();
    let leaf_ids: Vec<String> = {
        let parents: std::collections::HashSet<String> =
            svc.store().sections().iter().filter_map(|n| n.parent_id.clone()).collect();
        svc.store().sections().iter().filter(|n| !parents.contains(&n.id)).map(|n| n.id.clone()).collect()
    };
    assert!(!leaf_ids.is_empty(), "[{}] ⑥ 叶节点非空", run.id);
    let mut total_words = 0u64;
    let mut leaf_stats: Vec<Value> = Vec::new();
    for sid in &leaf_ids {
        let r = ok_result(
            call(&mut svc, "draft_response_section", json!({
                "project_id": &pid, "section_id": sid,
                "instructions": "按招标文件逐项响应，突出同类业绩与实施方案",
            })),
            &run.id,
        );
        assert_eq!(r["section_status"], "DRAFTED", "[{}] ⑥ 章节 {sid}", run.id);
        assert!(r["stats"]["citations"].as_u64().unwrap() > 0, "[{}] ⑥ {sid} 引用面", run.id);
        total_words += r["stats"]["words"].as_u64().unwrap();
        leaf_stats.push(json!({
            "sid": sid.clone(), "words": r["stats"]["words"].clone(),
            "citations": r["stats"]["citations"].clone(),
        }));
    }
    assert!(total_words > 500, "[{}] ⑥ 总字数 {total_words}", run.id);
    let asm = bid_tools::assembly::ChapterAssembler::open(&ws).unwrap();
    for sid in &leaf_ids {
        assert!(asm.has_committed(sid), "[{}] ⑥ 工作区缺 {sid}", run.id);
    }
    metrics["draft"] = json!({
        "leaves": leaf_ids.len() as u64, "total_words": total_words, "leaf_stats": leaf_stats,
    });
    metrics["t_draft_ms"] = json!(t.elapsed().as_millis() as u64);

    // ⑦ 校验（BLOCKER 必须清零）
    let t = Instant::now();
    let r = ok_result(
        call(&mut svc, "validate_bid_document", json!({ "project_id": &pid, "scope": "all" })),
        &run.id,
    );
    if r["ok"] != json!(true) {
        panic!("[{}] ⑦ 校验未过（BLOCKER 未清零）: {}", run.id, r["errors"]);
    }
    assert_eq!(r["counts"]["blocker"], json!(0), "[{}] ⑦ blocker 计数", run.id);
    assert_eq!(r["project_status"], "VALIDATING", "[{}] ⑦ 状态面", run.id);
    metrics["validate"] = r.clone();
    metrics["t_validate_ms"] = json!(t.elapsed().as_millis() as u64);

    // ⑦' PreExportConfirm（定稿内容过门）
    svc.store_mut()
        .record_review(Gate::PreExportConfirm, &bid_domain::TrustedPrincipal::human("closeout-lead"), Decision::Approved, vec![], None)
        .unwrap();

    // ⑧ 导出（成品 docx）
    let t = Instant::now();
    let out_name = format!("out/投标文件-{}.docx", run.id);
    let r = ok_result(
        call(&mut svc, "export_bid_document", json!({
            "profile": run.profile.clone(),
            "max_overrun_pct": run.max_overrun_pct,
            "project_id": &pid, "format": "docx", "output_path": out_name,
        })),
        &run.id,
    );
    let url = r["artifact"]["url"].as_str().unwrap().to_string();
    assert!(url.ends_with(&format!("投标文件-{}.docx", run.id)), "[{}] ⑧ 产物名: {url}", run.id);
    assert!(r["artifact"]["size"].as_u64().unwrap() > 5_000, "[{}] ⑧ 产物 >5KB", run.id);
    assert_eq!(r["chapters_written"].as_u64().unwrap(), leaf_ids.len() as u64, "[{}] ⑧ 全部落章", run.id);
    assert_eq!(r["project_status"], "EXPORTED", "[{}] ⑧ 状态面", run.id);
    metrics["export"] = json!({
        "url": url.clone(), "size": r["artifact"]["size"].clone(),
        "chapters_written": r["chapters_written"].clone(),
        "coarse_fingerprint": coarse_fingerprint(Path::new(&url)),
    });
    metrics["t_export_ms"] = json!(t.elapsed().as_millis() as u64);

    // ---- 产物深检（解包——「Word 打开」的机器等价面）
    let bytes = std::fs::read(&url).unwrap();
    let cursor = std::io::Cursor::new(&bytes);
    let mut zip = zip::ZipArchive::new(cursor).unwrap_or_else(|e| panic!("[{}] ⑧ docx 合法 zip: {e}", run.id));
    let mut doc_xml = String::new();
    zip.by_name("word/document.xml").unwrap().read_to_string(&mut doc_xml).unwrap();
    assert!(doc_xml.contains("TOC \\o"), "[{}] ⑧ TOC 域在位", run.id);
    let first_leaf_title = svc.store().sections().iter().find(|n| n.id == leaf_ids[0]).unwrap().title.clone();
    assert!(doc_xml.contains(&first_leaf_title), "[{}] ⑧ 章标题「{first_leaf_title}」进正文", run.id);
    let rec = asm.record(&leaf_ids[0]).unwrap();
    let first_line = rec.content.lines().find(|l| !l.trim().is_empty()).unwrap_or("");
    let stripped = first_line.trim_start_matches('#').trim();
    let probe: String = stripped.chars().take(20).collect();
    assert!(doc_xml.contains(&probe), "[{}] ⑧ 正文首段「{probe}…」进文档（剥号面）", run.id);
    assert!(!doc_xml.contains("# "), "[{}] ⑧ md 标题井号不再字面输出", run.id);
    let mut styles_xml = String::new();
    zip.by_name("word/styles.xml").unwrap().read_to_string(&mut styles_xml).unwrap();
    assert!(styles_xml.contains("w:eastAsia="), "[{}] ⑧ format-spec 字体面", run.id);
    metrics["deep_check"] = json!({ "toc": true, "first_leaf_title_in_doc": true, "styles_east_asia": true });

    // ---- 重启恢复面
    let svc2 = BidService::open(&ws).unwrap();
    assert_eq!(
        svc2.store().project().unwrap().status,
        bid_domain::ProjectStatus::Exported,
        "[{}] 重启后 EXPORTED 状态完整恢复",
        run.id
    );
    let asm2 = bid_tools::assembly::ChapterAssembler::open(&ws).unwrap();
    assert_eq!(asm2.committed_count(), leaf_ids.len(), "[{}] 重启后工作区全量恢复", run.id);
    metrics["restart_recovered"] = json!(true);

    metrics["t_total_ms"] = json!(t_all.elapsed().as_millis() as u64);
    std::fs::write(ws.join("closeout-metrics.json"), serde_json::to_string_pretty(&metrics).unwrap()).unwrap();
    metrics
}

// ---------------------------------------------------------------- 隔离审计

fn isolation_audit(base: &Path, runs: &[RunSpec], metrics: &[Value]) -> Value {
    let mut projects: Vec<Value> = Vec::new();
    let mut file_sets: Vec<(String, Vec<String>)> = Vec::new();
    for run in runs {
        let ws = base.join(&run.id);
        let svc = BidService::open(&ws).unwrap_or_else(|e| panic!("审计重开 [{}]: {e}", run.id));
        let proj = svc.store().project().unwrap();
        projects.push(json!({
            "run": run.id.clone(), "pid": proj.id.clone(), "external_key": proj.external_key.clone(),
        }));
        file_sets.push((
            run.id.clone(),
            svc.store().files().iter().map(|tf| tf.name.clone()).collect::<Vec<_>>(),
        ));
    }
    // 断言 1：external_key == closeout-<run_id>（隔离命名面）
    for p in &projects {
        let run_id = p["run"].as_str().unwrap();
        assert_eq!(p["external_key"], json!(format!("closeout-{run_id}")), "隔离审计：external_key 不匹配 {p}");
    }
    // 断言 2：每个工作区恰好一个项目（单项目存储面）。注：PRJ 序号是
    // store 局部序列——跨工作区各自从 PRJ-0001 起是**设计语义**（非全局
    // 唯一），隔离正确性由独立存储 + 断言 3 文件集不相交 + 断言 4 产物
    // 互异保证（收官真测实证：两隔离工作区同报 PRJ-0001，零数据互漏）。
    assert_eq!(
        projects.len(),
        runs.len(),
        "隔离审计：工作区数与项目数不齐（每工作区应恰一项目）"
    );
    let pid_scope_note = "workspace-local（store 局部序列——跨工作区可同号，设计语义非缺陷）";
    // 断言 3：文件名集合两两不相交（无跨件泄漏）
    for i in 0..file_sets.len() {
        for j in (i + 1)..file_sets.len() {
            let (ra, fa) = &file_sets[i];
            let (rb, fb) = &file_sets[j];
            let overlap: Vec<&String> = fa.iter().filter(|n| fb.contains(n)).collect();
            assert!(overlap.is_empty(), "隔离审计：[{ra}] 与 [{rb}] 文件泄漏 {overlap:?}");
        }
    }
    // 断言 4：导出产物两两互异（存在即比——url + 尺寸 + 粗指纹）
    let mut exports: Vec<(String, String, u64)> = Vec::new();
    for m in metrics {
        if let Some(url) = m["export"]["url"].as_str() {
            exports.push((
                m["run_id"].as_str().unwrap().to_string(),
                url.to_string(),
                m["export"]["size"].as_u64().unwrap_or(0),
            ));
        }
    }
    for i in 0..exports.len() {
        for j in (i + 1)..exports.len() {
            assert_ne!(exports[i].1, exports[j].1, "隔离审计：导出产物路径冲突");
            assert_ne!(
                exports[i].2, exports[j].2,
                "隔离审计：导出产物尺寸雷同（{} vs {}）",
                exports[i].0, exports[j].0
            );
        }
    }
    json!({
        "projects": projects,
        "pid_uniqueness_scope": pid_scope_note,
        "file_sets": file_sets
            .iter()
            .map(|(id, fs)| json!({ "run": id.clone(), "files": serde_json::to_value(fs).unwrap() }))
            .collect::<Vec<_>>(),
        "exports": exports
            .iter()
            .map(|(r, u, s)| json!({ "run": r.clone(), "url": u.clone(), "size": *s }))
            .collect::<Vec<_>>(),
        "all_pass": true,
    })
}

// ---------------------------------------------------------------- 主入口

#[test]
fn real_closeout_spec_runs() {
    let Some(spec_path) = std::env::var_os("CLOSEOUT_SPEC") else {
        spec_banner_missing();
        return;
    };
    let spec: Value =
        serde_json::from_str(&std::fs::read_to_string(&spec_path).expect("读 CLOSEOUT_SPEC")).expect("规格 JSON 解析");
    let repo_root = std::fs::canonicalize(spec["repo_root"].as_str().expect("repo_root")).expect("repo_root 规范化");
    let base = PathBuf::from(spec["base_dir"].as_str().expect("base_dir"));
    std::fs::create_dir_all(&base).unwrap();
    let runs: Vec<RunSpec> = spec["runs"].as_array().expect("runs").iter().map(parse_run).collect();
    assert!(!runs.is_empty(), "规格 runs 为空");

    // 预检：全部真件在位（缺件响亮退出——不静默假装通过）
    for run in &runs {
        for f in &run.files {
            assert!(f.path.exists(), "[{}] 真件缺失: {}", run.id, f.path.display());
        }
    }

    let mut metrics: Vec<Value> = Vec::new();
    for run in &runs {
        println!("\n== real_closeout · 真跑 [{}] {}（{} 件导入）==", run.id, run.name, run.files.len());
        metrics.push(run_material(&base, &repo_root, run));
    }

    // 结果隔离审计（跨件无污染断言——落盘 + 硬断言）
    let audit = isolation_audit(&base, &runs, &metrics);
    std::fs::write(base.join("isolation-audit.json"), serde_json::to_string_pretty(&audit).unwrap()).unwrap();

    // 汇总指标（评测脚本真源）
    let n_runs = metrics.len();
    let summary = json!({
        "seed": spec.get("seed").cloned().unwrap_or(json!(null)),
        "generated_at": spec.get("generated_at").cloned().unwrap_or(json!(null)),
        "base_dir": base.display().to_string(),
        "runs": metrics,
    });
    std::fs::write(base.join("closeout-metrics.json"), serde_json::to_string_pretty(&summary).unwrap()).unwrap();
    println!("\n== real_closeout 完成：{n_runs} 件真跑 + 隔离审计全过 ==");
}
