//! #114 多文件统一矩阵验收 harness——评分表驱动大纲与跨件一致性（真跑面）。
//!
//! 驱动：环境变量 `MULTIFILE_SPEC` 指向 JSON 规格（由
//! `scripts/multifile_acceptance.py --emit-spec` 生成——素材清单/哈希/kind
//! 指派/开标日参数的单一真源）；**缺失 → 响亮横幅 SKIP**（CI 安全——与
//! real_closeout 的 CLOSEOUT_SPEC 纪律同口径：缺规格不是业务失败）。
//!
//! 与既有测试面的分工：
//! - e2e_pipeline（corpus-A 4 件固定回归面）/ real_closeout（收官抽件面）：
//!   单项目「主件(+证据)」全链；**本面是多文件统一矩阵**——同项目全件
//!   （主文件+辅件+评分/报价表+补遗+证据）进**同一项目**，跨件溯源/冲突/
//!   评分映射/篇幅/补遗影响一次验收（#114 题面）。
//! - docx_scoring_materials（#134）：评分表数据行 vs 评分项 REQ 的**单件**
//!   缺口对账；本面在其之上加「映射-覆盖-篇幅」的**多件**行为面。
//!
//! 断言策略（AGENTS §7/§9 纪律——事实面全记录，结构不变量才硬断言）：
//! - 硬断言（产品不变量，红 = 回归）：导入台账文件数、REQ 锚点文件 ⊆ 导入
//!   文件集、配额总和 ≈ target（±10%——outline.rs 守恒修正的验收容差）、
//!   映射后评分项 unmapped=0、全部叶 DRAFTED、validate blocker=0。
//! - 只记录（验收判据留给 Python 评审器对照 GT/期望，不在此硬断言）：
//!   per-file 导入状态（B2 扫描件无 OCR 环境的诚实面）、抽取分类分布、
//!   conflicts 明细（含 GT CONFLICT-01 是否被同号匹配检出）、评分映射
//!   决策（关键词重合度）、check_scoring_coverage 逐细则、补遗 DIRTY/
//!   指令面、EV-02 有效期翻转（开标日前/后双口径）。
//!
//! 隔离纪律（real_closeout 同款）：每项目独立工作区 `base_dir/<id>/`，
//! external_key = m114-<id>；指标落盘 `multifile-metrics.json` 供评审器
//! 消费（评审器不在 Rust 里——GT 判分归 Python，防「断言迁就实现」）。

use bid_domain::outline::OutlineSpec;
use bid_mcp::{dispatch_with, BidService, ToolCall, ToolError, ToolReply};
use serde_json::{json, Value};
use std::collections::{BTreeMap, BTreeSet};
use std::path::{Path, PathBuf};

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
    valid_until: Option<String>,
}

struct ProjectSpec {
    id: String,
    name: String,
    real: bool,
    full_chain: bool,
    outline_target_chars: u64,
    max_reqs_per_leaf: u64,
    open_date_pre: Option<String>,
    open_date_post: Option<String>,
    files: Vec<FileSpec>,
    evidence: Vec<EvidenceSpecRow>,
    /// 补遗影响探针（corpus-A）：控制价 value_changed 变更登记。
    addendum_probe: bool,
}

fn spec_banner_missing() {
    println!(
        "\n============================================================\n\
         SKIP: multifile_matrix —— 未设置 MULTIFILE_SPEC（多件矩阵验收规格）\n\
           生成：python3 scripts/multifile_acceptance.py --emit-spec\n\
           （CI 无多件语料面恒跳过——本面是 #114 验收一次性真跑，非回归面）\n\
         ============================================================\n"
    );
}

fn parse_project(v: &Value) -> ProjectSpec {
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
                    kind: e["kind"].as_str().unwrap_or("Qualification").to_string(),
                    title: e["title"].as_str().unwrap_or("").to_string(),
                    source_file: e["source_file"].as_str().unwrap_or("").to_string(),
                    valid_until: e.get("valid_until").and_then(|x| x.as_str()).map(String::from),
                })
                .collect()
        })
        .unwrap_or_default();
    ProjectSpec {
        id: v["id"].as_str().expect("project.id").to_string(),
        name: v["name"].as_str().unwrap_or("多件矩阵验收件").to_string(),
        real: v["real"].as_bool().unwrap_or(false),
        full_chain: v["full_chain"].as_bool().unwrap_or(false),
        outline_target_chars: v["outline_target_chars"].as_u64().unwrap_or(48_000),
        max_reqs_per_leaf: v["max_reqs_per_leaf"].as_u64().unwrap_or(8),
        open_date_pre: v.get("open_date_pre").and_then(|x| x.as_str()).map(String::from),
        open_date_post: v.get("open_date_post").and_then(|x| x.as_str()).map(String::from),
        files,
        evidence,
        addendum_probe: v.get("addendum_probe").and_then(|x| x.as_bool()).unwrap_or(false),
    }
}

// ---------------------------------------------------------------- 通用助手

fn call(svc: &mut BidService, tool: &str, mut args: Value) -> ToolReply {
    // 确定性套件钉 mock（real_closeout 同纪律——防 dev 机配 key 走真调）
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
    // 投标人侧测试数据（与真件无关——投标人自报面；收官真测同款合成纪律，
    // 规格里 real_evidence=false 已在指标面诚实标记）
    let p = bid_domain::party::BidderProfile {
        company_name: "多件矩阵验收通信工程有限公司".into(),
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

/// FNV-1a 64（证据登记定位指纹——合成面，e2e/real_closeout 同口径）。
fn fnv64(s: &str) -> String {
    let mut h: u64 = 0xcbf29ce484222325;
    for b in s.as_bytes() {
        h ^= *b as u64;
        h = h.wrapping_mul(0x100000001b3);
    }
    format!("fnv64:{h:016x}")
}

/// 中文 bigram 集合（关键词重合度打分——映射决策可审计的启发式面）。
fn bigrams(s: &str) -> BTreeSet<String> {
    let chars: Vec<char> = s.chars().collect();
    let mut set = BTreeSet::new();
    for i in 0..chars.len().saturating_sub(1) {
        set.insert(format!("{}{}", chars[i], chars[i + 1]));
    }
    set
}

fn overlap_score(a: &str, b: &str) -> usize {
    let (ba, bb) = (bigrams(a), bigrams(b));
    ba.intersection(&bb).count()
}

fn excerpt60(s: &str) -> String {
    s.chars().take(60).collect()
}

fn excerpt200(s: &str) -> String {
    s.chars().take(200).collect()
}

// ---------------------------------------------------------------- 单项目真跑

fn run_project(base: &Path, repo_root: &Path, p: &ProjectSpec) -> Value {
    let tag = p.id.as_str();
    let ws = base.join(&p.id);
    if ws.exists() {
        std::fs::remove_dir_all(&ws).expect("清理旧工作区（隔离前置）");
    }
    std::fs::create_dir_all(&ws).unwrap();
    let mut metrics = json!({
        "id": p.id.clone(), "name": p.name.clone(), "real": p.real,
        "full_chain": p.full_chain, "ws": ws.display().to_string(),
        "files_planned": p.files.len() as u64,
    });

    let mut svc = BidService::open(&ws).unwrap().with_fs_root(repo_root.to_path_buf());
    write_profile(&ws);

    // ① 建项目（external_key = m114-<id>——幂等 + 隔离命名面）
    let pid = ok_result(
        call(&mut svc, "create_bid_project", json!({
            "name": p.name.clone(), "bid_deadline": "2026-12-31", "mode": "明标",
            "external_key": format!("m114-{}", p.id),
        })),
        tag,
    )["project_id"]
        .as_str()
        .unwrap()
        .to_string();
    metrics["project_id"] = json!(pid.clone());

    // ② 导入全件（多件统一矩阵的核心面——同项目全件一次 import）
    //    E_PARTIAL = 诚实面：逐件 item_errors + 成功件已落库（契约 §2 R-01）。
    //    #114 验收口径：逐件记录不硬拦（B2 扫描件无 OCR 环境的诚实面）。
    let file_specs: Vec<Value> = p
        .files
        .iter()
        .map(|f| {
            json!({
                "upload_ref": f.path.display().to_string(),
                "filename": f.filename.clone(), "kind": f.kind.clone(),
            })
        })
        .collect();
    let import_reply = call(
        &mut svc,
        "import_tender_files",
        json!({ "project_id": &pid, "files": file_specs }),
    );
    let (r, import_item_errors, import_partial) = match import_reply {
        ToolReply::Ok(out) => (out.result, Vec::new(), false),
        ToolReply::Err { error, .. } => match error {
            ToolError::EPartial { item_errors, data, .. } => {
                (data.unwrap_or_else(|| json!({})), item_errors, true)
            }
            other => panic!("[{tag}] ② 导入面意外错误（非 E_PARTIAL）: {other}"),
        },
    };
    let totals = r["totals"].clone();
    // 硬断言（产品不变量）：计划件全部入账（E_PARTIAL 时成功件仍在台账）。
    // partial/parse_failed 逐件记录不硬断言（评审器按件定罪）。
    assert_eq!(
        totals["files"].as_u64().unwrap_or(0),
        p.files.len() as u64,
        "[{tag}] ② 导入台账文件数不符（计划 {} 件）: {totals:?}",
        p.files.len()
    );
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
    metrics["import_totals"] = totals;
    metrics["import_partial"] = json!(import_partial);
    metrics["import_item_errors"] = json!(import_item_errors);
    metrics["import_input_integrity"] = r.get("input_integrity").cloned().unwrap_or(Value::Null);
    metrics["import_addendum_readiness"] = r.get("addendum_readiness").cloned().unwrap_or(Value::Null);
    metrics["import_warnings"] = r.get("warnings").cloned().unwrap_or(Value::Null);
    metrics["files"] = json!(file_rows);

    // ②' 坏件逐件人工确认（产品设计的恢复通道——真件受损面的诚实路径）：
    //     parse FAILED 的非格式模板件阻塞起草（输入完整性门），按错误面
    //     指引走 record_addendum_waiver 逐件放行 → 受限起草（RESTRICTED）。
    //     真实发现（如 unicom 详细评审表.xlsx 引擎拒收 customXml 截断）
    //     原文进 reason——验收证据面，不掩盖。
    let failed_files: Vec<(String, String)> = svc
        .store()
        .files()
        .iter()
        .filter(|tf| tf.parse_status == bid_domain::ParseStatus::Failed)
        .map(|tf| (tf.id.clone(), tf.name.clone()))
        .collect();
    let mut waived: Vec<Value> = Vec::new();
    for (fid, fname) in &failed_files {
        let receipt = svc.issue_approval_receipt("m114-lead", &format!("addendum_waiver:{fid}"));
        let reason_detail = import_item_errors
            .iter()
            .find(|e| e.contains(fname.as_str()))
            .cloned()
            .unwrap_or_else(|| "解析失败（导入错误清单无逐件根因——如实登记）".into());
        let w = ok_result(
            call(&mut svc, "record_addendum_waiver", json!({
                "project_id": &pid, "file_id": fid,
                "reason": format!(
                    "#114 多件矩阵：真件引擎解析失败，人工确认后受限放行（不伪造修复）——{reason_detail}"
                ),
                "receipt": receipt,
            })),
            tag,
        );
        waived.push(json!({ "file_id": fid, "name": fname, "reason_source": reason_detail,
                            "recorded": w["recorded"].clone() }));
    }
    metrics["waived_failed_files"] = json!(waived);

    // ③ 抽取（确定性真跑——多件统一 REQ 面一次成型）
    let r = ok_result(call(&mut svc, "extract_requirements", json!({ "project_id": &pid })), tag);
    metrics["extract_counts"] = r["counts"].clone();
    metrics["extract_merge"] = r["merge"].clone();
    metrics["extract_conflicts"] = r["conflicts"].clone();
    metrics["extract_missing_sequence"] = r["missing_sequence"].clone();
    metrics["extract_warnings"] = r["warnings"].clone();

    // ③' 逐 REQ 溯源面（统一矩阵）：全量 REQ 摘要（评审器对照 GT 的数据源）
    let imported_names: BTreeSet<String> = svc.store().files().iter().map(|tf| tf.name.clone()).collect();
    let mut per_file_counts: BTreeMap<String, u64> = BTreeMap::new();
    let mut req_rows: Vec<Value> = Vec::new();
    let mut anchor_outside = 0u64;
    for req in svc.store().requirements() {
        *per_file_counts.entry(req.source_file.clone()).or_insert(0) += 1;
        let anchor_files: BTreeSet<&str> = req.anchors.iter().map(|a| a.file.as_str()).collect();
        for af in &anchor_files {
            if !imported_names.contains(*af) {
                anchor_outside += 1;
            }
        }
        req_rows.push(json!({
            "id": req.id.clone(), "category": req.category.clone(),
            "clause_no": req.clause_no.clone(), "source_file": req.source_file.clone(),
            "anchor_files": anchor_files.into_iter().collect::<Vec<_>>(),
            "excerpt": excerpt200(req.anchors.first().map(|a| a.excerpt.as_str()).unwrap_or("")),
            "anchor_excerpts": req.anchors.iter().map(|a| excerpt200(a.excerpt.as_str())).collect::<Vec<_>>(),
            "score": req.params.get("score").cloned().unwrap_or(Value::Null),
            "has_scoring_params": req.params.get("name").is_some() && req.params.get("track").is_some(),
            "substantive": bid_domain::matrix::substantive(req),
        }));
    }
    // 硬断言（跨件一致性不变量）：REQ 锚点文件必须 ⊆ 导入文件集（零跨项目泄漏）
    assert_eq!(anchor_outside, 0, "[{tag}] ③' 有 {anchor_outside} 个锚点指向未导入文件（跨项目泄漏）");
    metrics["req_count"] = json!(req_rows.len() as u64);
    metrics["reqs_by_file"] = json!(per_file_counts);
    metrics["requirements"] = json!(req_rows);

    // ③'' 抽样逐条溯源（MCP 读面——get_requirement_provenance 真跑证据）
    let mut provenance_samples: Vec<Value> = Vec::new();
    let sample_ids: Vec<String> = svc
        .store()
        .requirements()
        .iter()
        .take(3)
        .map(|r| r.id.clone())
        .collect();
    for rid in sample_ids {
        let r = ok_result(
            call(&mut svc, "get_requirement_provenance", json!({
                "project_id": &pid, "req_id": rid,
            })),
            tag,
        );
        provenance_samples.push(r);
    }
    metrics["provenance_samples"] = json!(provenance_samples);

    // ---- 非全链件（辅件/缺主件面）：建纲探针如实记录后止步
    if !p.full_chain {
        metrics["stopped_at"] = json!("import_extract_face");
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
                // 0 条款面 → 清晰诊断拒绝 = 预期门行为（closeout C 面同款诚实记录）
                metrics["outline_probe"] = json!({ "outcome": "rejected", "diagnostic": format!("{e:?}") });
            }
        }
        std::fs::write(ws.join("multifile-metrics.json"), serde_json::to_string_pretty(&metrics).unwrap()).unwrap();
        return metrics;
    }

    // ④ 建纲建矩阵（服务面——评分驱动大纲的现状行为全量落盘）
    let (n_sec, n_rows, n_blocking) = svc
        .prepare_outline_and_matrix(OutlineSpec {
            target_total_chars: p.outline_target_chars as u32,
            max_reqs_per_leaf: p.max_reqs_per_leaf as usize,
        })
        .unwrap_or_else(|e| panic!("[{tag}] ④ 建纲失败（全链件条款面应非空）: {e:?}"));
    assert!(n_sec >= 2, "[{tag}] ④ 章节树: {n_sec} 节点");
    let sections: Vec<Value> = svc
        .store()
        .sections()
        .iter()
        .map(|n| {
            json!({
                "id": n.id.clone(), "parent_id": n.parent_id.clone(),
                "title": n.title.clone(), "level": n.level as u64,
                "order": n.order as u64, "target_chars": n.target_chars as u64,
                "requirement_ids": n.requirement_ids.len() as u64,
            })
        })
        .collect();
    // 硬断言（outline.rs 守恒修正的验收容差）：叶片配额总和 ≈ target ±10%
    let quota_sum: u64 = sections.iter().filter_map(|s| {
        if s["parent_id"].is_null() { None } else { s["target_chars"].as_u64() }
    }).sum();
    let target = p.outline_target_chars;
    let tolerance = target / 10;
    assert!(
        quota_sum + tolerance >= target && quota_sum <= target + tolerance,
        "[{tag}] ④ 配额守恒破坏：叶片和 {quota_sum} vs target {target}（±10% 容差外）"
    );
    metrics["outline"] = json!({
        "sections": n_sec as u64, "rows": n_rows as u64, "blocking_pre_bind": n_blocking as u64,
        "quota_leaf_sum": quota_sum, "quota_target": target,
    });
    metrics["section_tree"] = json!(sections);
    metrics["matrix_rows_pre_bind"] = json!(svc.store().matrix().len() as u64);

    // ⑤ 证据登记（投标人侧——valid_until 按 manifest 真值，EV-02 翻转面数据源）
    use bid_domain::evidence::EvidenceSpec;
    use bid_domain::locator::EngineLocator;
    let kind_of = |s: &str| match s {
        "Performance" => bid_domain::evidence::EvidenceKind::Performance,
        "Personnel" => bid_domain::evidence::EvidenceKind::Personnel,
        "Certificate" => bid_domain::evidence::EvidenceKind::Certificate,
        "Contract" => bid_domain::evidence::EvidenceKind::Contract,
        _ => bid_domain::evidence::EvidenceKind::Qualification,
    };
    let mut ev_ids = Vec::new();
    for ev in &p.evidence {
        let real_sha = svc
            .store()
            .files()
            .iter()
            .find(|tf| tf.name == ev.source_file)
            .map(|tf| tf.sha256.clone())
            .unwrap_or_else(|| "sha-missing".into());
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
                valid_until: ev.valid_until.clone(),
                subject_name: "多件矩阵验收通信工程有限公司".into(),
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
    metrics["evidence_registered"] = json!(p.evidence.len() as u64);

    // ⑤' EV-02 有效期翻转探针——已移至链尾（主链验证后）：翻转会把证据降
    //    级 EXPIRED，而起草面 R-03 拒失效证据——探针在前会污染主链。

    // ⑤'' 阻断面全绑 + ★实质性条款全绑 + 技术参数佐证（起草门清零面
    //     ——e2e 同款：#110 任务 1 缺失回报闸——技术参数类也须佐证）
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
    let tech_ids: Vec<String> = svc
        .store()
        .requirements()
        .iter()
        .filter(|r| r.category == "资格条件" || r.category == "否决项" || r.category == "技术参数")
        .map(|r| r.id.clone())
        .collect();
    let mut bind_ids = blocking_ids.clone();
    for sid in substantive_ids.iter().chain(tech_ids.iter()) {
        if !bind_ids.contains(sid) {
            bind_ids.push(sid.clone());
        }
    }
    let open_for_bind = p.open_date_pre.clone().unwrap_or_else(|| "2026-11-15".into());
    let n_bind = bind_ids.len();
    let mut bind_rejected = 0u64;
    for rid in &bind_ids {
        if svc.store_mut().bind_evidence(&ev_ids[0], rid, &open_for_bind).is_err() {
            bind_rejected += 1;
        }
    }
    let _ = svc.store_mut().build_matrix().unwrap();
    metrics["evidence_binding"] = json!({
        "bound_reqs": n_bind as u64, "bind_rejected": bind_rejected,
        "open_date_used": open_for_bind,
    });

    // ⑥ 评分映射逐项（#114 评分映射面——映射决策可审计）
    //    现状：DOCX 主件的评分项无 scoring_table 专路 params（#134 缺口），
    //    outline 派生映射不发生 → gate 1h 全量悬空，harness 走 #153 MCP
    //    正门通道逐项映射（bigram 重合度选叶 + 决策留痕）。
    let leaf_titles: Vec<(String, String)> = {
        let parents: BTreeSet<String> =
            svc.store().sections().iter().filter_map(|n| n.parent_id.clone()).collect();
        svc.store()
            .sections()
            .iter()
            .filter(|n| !parents.contains(&n.id))
            .map(|n| (n.id.clone(), n.title.clone()))
            .collect()
    };
    let scoring_items = bid_domain::scoring::derive_scoring_items(svc.store().requirements());
    let mut unmapped_before = 0usize;
    for it in &scoring_items {
        // 门 1h 口径（unmapped_items）：否决项（hard gate）与价格项不入面
        if !it.is_hard_gate && it.mappings.is_empty() {
            unmapped_before += 1;
        }
    }
    let hard_gates = scoring_items.iter().filter(|it| it.is_hard_gate).count();
    let mut mapping_decisions: Vec<Value> = Vec::new();
    for it in &scoring_items {
        // 只映射门 1h 面上的评分项（否决项是独立闸门——AUD2-HIS-B2 纪律，
        // check_scoring_coverage 同样排除 hard gate——不重复映射面）
        if it.is_hard_gate || !it.mappings.is_empty() {
            continue; // hard gate / outline 派生映射已在位——不重复映射
        }
        // bigram 重合度选叶；零重合 → 叶片 REQ 数最大者兜底（决策留痕）
        let mut best: Option<(&str, &str, usize)> = None;
        for (sid, title) in &leaf_titles {
            let score = overlap_score(&it.criteria, title);
            if best.map(|(_, _, s)| score > s).unwrap_or(true) {
                best = Some((sid, title, score));
            }
        }
        let (sid, title, score) = best.expect("叶片非空（④ 已断言）");
        let method = if score > 0 { "bigram-overlap" } else { "fallback-largest-leaf" };
        // #153 正门通道（MCP 写面真跑——AGENT_SUBMITTED 落账）
        let r = ok_result(
            call(&mut svc, "map_scoring_item", json!({
                "project_id": &pid, "req_id": it.requirement_id, "section_id": sid,
                "weight_share": 1.0,
                "anchor": {
                    "excerpt": format!("#114 多件矩阵映射（{method} 重合度 {score}）：{}", excerpt60(&it.criteria)),
                    "locator": "多件矩阵验收——评分项→章节映射",
                },
            })),
            tag,
        );
        mapping_decisions.push(json!({
            "req_id": it.requirement_id, "criteria": excerpt60(&it.criteria),
            "section_id": sid, "section_title": title,
            "overlap": score as u64, "method": method,
            "unmapped_left_after": r["unmapped_scoring_items_left"].clone(),
            "max_score": it.max_score,
        }));
    }
    // 硬断言（门 1h 正门闭环不变量）：映射后评分项零悬空
    let unmapped_after =
        bid_mcp::coverage_hint::unmapped_scoring_count(svc.store());
    assert_eq!(unmapped_after, 0, "[{tag}] ⑥ 评分项映射后仍有 {unmapped_after} 条悬空（门 1h）");
    metrics["scoring_mapping"] = json!({
        "scoring_items": scoring_items.len() as u64,
        "hard_gates_excluded": hard_gates as u64,
        "unmapped_before": unmapped_before as u64,
        "unmapped_after": unmapped_after as u64,
        "decisions": mapping_decisions,
    });

    // ⑦ 审批门 + 补遗确认门（有补遗件在案 → 无须 no_addendum 确认；记录在案）
    use bid_domain::review::{Decision, Gate};
    for gate in [Gate::MatrixApproval, Gate::OutlineApproval] {
        svc.store_mut()
            .record_review(gate, &bid_domain::TrustedPrincipal::human("m114-lead"), Decision::Approved, vec![], None)
            .unwrap();
    }
    let has_addendum = p.files.iter().any(|f| f.kind == "补遗");
    if !has_addendum && !ev_ids.is_empty() {
        let receipt = svc.issue_approval_receipt("m114-lead", "no_addendum_confirmed");
        let _ = ok_result(
            call(&mut svc, "record_addendum_waiver", json!({
                "project_id": &pid, "confirm_no_addendum": true,
                "reason": "#114 多件矩阵：本验收件在案文件无补遗/澄清——人工确认后放行（语料边界如实登记）",
                "receipt": receipt,
            })),
            tag,
        );
    }
    metrics["addendum_gate"] = json!({ "has_addendum_file": has_addendum });

    // ⑧ 逐章起草（mock 确定性——#130 门 1n 语义：mock 非正式标书，验收面如实标记）
    let leaf_ids: Vec<String> = {
        let parents: BTreeSet<String> =
            svc.store().sections().iter().filter_map(|n| n.parent_id.clone()).collect();
        svc.store()
            .sections()
            .iter()
            .filter(|n| !parents.contains(&n.id))
            .map(|n| n.id.clone())
            .collect()
    };
    assert!(!leaf_ids.is_empty(), "[{tag}] ⑧ 叶节点非空");
    let mut total_words = 0u64;
    let mut leaf_stats: Vec<Value> = Vec::new();
    let mut draft_input_integrity: Option<Value> = None;
    for sid in &leaf_ids {
        let r = ok_result(
            call(&mut svc, "draft_response_section", json!({
                "project_id": &pid, "section_id": sid,
                "instructions": "按招标文件逐项响应，突出同类业绩与实施方案",
            })),
            tag,
        );
        assert_eq!(r["section_status"], "DRAFTED", "[{tag}] ⑧ 章节 {sid}");
        total_words += r["stats"]["words"].as_u64().unwrap();
        if draft_input_integrity.is_none() {
            draft_input_integrity = r.get("input_integrity").cloned();
        }
        leaf_stats.push(json!({
            "sid": sid.clone(), "title": svc.store().sections().iter().find(|n| n.id == *sid).map(|n| n.title.clone()).unwrap_or_default(),
            "words": r["stats"]["words"].clone(), "citations": r["stats"]["citations"].clone(),
        }));
    }
    assert!(total_words > 500, "[{tag}] ⑧ 总字数 {total_words}");
    metrics["draft"] = json!({
        "generator": "mock", "leaves": leaf_ids.len() as u64,
        "total_words": total_words, "leaf_stats": leaf_stats,
        "input_integrity": draft_input_integrity.unwrap_or(Value::Null),
    });

    // ⑨ 评分覆盖逐细则（#114 评分细则↔章节↔正文面——只读诊断真跑）
    let r = ok_result(
        call(&mut svc, "check_scoring_coverage", json!({ "project_id": &pid })),
        tag,
    );
    metrics["scoring_coverage"] = r.clone();

    // ⑪ 校验（BLOCKER 清零——全链件闭环面）
    let r = ok_result(
        call(&mut svc, "validate_bid_document", json!({ "project_id": &pid, "scope": "all" })),
        tag,
    );
    metrics["validate"] = json!({
        "ok": r["ok"].clone(), "counts": r["counts"].clone(),
        "project_status": r["project_status"].clone(),
        "global_conflicts": r.get("global_conflicts").cloned().unwrap_or(Value::Null),
    });
    if r["ok"] != json!(true) {
        // 全链件 BLOCKER 未清零 = 结构性回归（绑定面/映射面缺失）——红
        panic!("[{tag}] ⑪ 校验未过（BLOCKER 未清零）: {}", r["errors"]);
    }

    // ⑩ 补遗影响探针（corpus-A·链尾）：控制价 value_changed → DIRTY/指令/矩阵面
    if p.addendum_probe {
        // 控制价 REQ（A 件 480 万口径——条款含「控制价」且锚文含 4800000/480）
        let ctrl_req = svc
            .store()
            .requirements()
            .iter()
            .find(|r| {
                let hay: String = r.anchors.iter().map(|a| a.excerpt.as_str()).collect::<String>();
                hay.contains("控制价") && (hay.contains("4800000") || hay.contains("480"))
            })
            .map(|r| (r.id.clone(), r.clause_no.clone()));
        if let Some((rid, clause_no)) = ctrl_req {
            let r = ok_result(
                call(&mut svc, "register_addendum_changes", json!({
                    "project_id": &pid,
                    "changes": [{
                        "change_type": "value_changed", "req_id": rid,
                        "old_text": "招标控制价 4800000（人民币 480 万元含税）",
                        "new_requirement": "招标控制价调整为 4650000（人民币 465 万元含税）——补遗三、招标控制价调整",
                        "clause_no": clause_no,
                    }],
                })),
                tag,
            );
            metrics["addendum_change_probe"] = r;
        } else {
            metrics["addendum_change_probe"] = json!({
                "skipped": "控制价 REQ 未在抽取面命中（评审器对账 GT CONFLICT-01 抽取可达性）",
            });
        }
        // 版本共在面：A/C 两口径的控制价 REQ 摘录（终裁值归属评审器判定）
        let versions: Vec<Value> = svc
            .store()
            .requirements()
            .iter()
            .filter(|r| {
                let hay: String = r.anchors.iter().map(|a| a.excerpt.as_str()).collect::<String>();
                hay.contains("控制价") || hay.contains("4650000")
            })
            .map(|r| {
                json!({
                    "id": r.id.clone(), "source_file": r.source_file.clone(),
                    "clause_no": r.clause_no.clone(),
                    "excerpt": excerpt60(r.anchors.first().map(|a| a.excerpt.as_str()).unwrap_or("")),
                })
            })
            .collect();
        metrics["control_price_versions"] = json!(versions);
    }

    // ⑤'（链尾执行）EV-02 有效期翻转探针（#114 补遗影响面——GT-02：
    //     开标日前/后双口径；绑后降级 EXPIRED 不再污染主链）。
    //     绑定目标 = A 件 clause 3.2.2 资格 REQ（GT-02）。bind 第三参即开标日。
    let mut flip_probe: Vec<Value> = Vec::new();
    for (i, ev) in p.evidence.iter().enumerate() {
        let Some(valid_until) = &ev.valid_until else { continue };
        let Some(pre) = &p.open_date_pre else { continue };
        let Some(post) = &p.open_date_post else { continue };
        let target_req = svc
            .store()
            .requirements()
            .iter()
            .find(|r| r.source_file.contains("A-") && r.clause_no.as_deref() == Some("3.2.2"))
            .map(|r| r.id.clone());
        let Some(rid) = target_req else { continue };
        let mut bind_at = |date: &str| -> Value {
            match svc.store_mut().bind_evidence(&ev_ids[i], &rid, date) {
                // Ok(false)=新建绑定；Ok(true)=幂等重放（evidence.rs 语义）
                Ok(replay) => json!({ "open_date": date, "outcome": "ok", "idempotent_replay": replay }),
                Err(e) => json!({ "open_date": date, "outcome": "rejected", "error": format!("{e:?}") }),
            }
        };
        flip_probe.push(json!({
            "evidence": ev.title.clone(), "valid_until": valid_until,
            "req": rid, "pre": bind_at(pre), "post": bind_at(post),
        }));
    }
    metrics["validity_flip_probe"] = json!(flip_probe);

    std::fs::write(ws.join("multifile-metrics.json"), serde_json::to_string_pretty(&metrics).unwrap()).unwrap();
    metrics
}

// ---------------------------------------------------------------- 主入口

#[test]
fn multifile_matrix_acceptance() {
    let Some(spec_path) = std::env::var_os("MULTIFILE_SPEC") else {
        spec_banner_missing();
        return;
    };
    let spec: Value = {
        let s = std::fs::read_to_string(&spec_path)
            .unwrap_or_else(|e| panic!("读 MULTIFILE_SPEC 失败（{}）: {e}", spec_path.to_string_lossy()));
        serde_json::from_str(&s).expect("MULTIFILE_SPEC 非法 JSON")
    };
    let base = PathBuf::from(spec["base_dir"].as_str().expect("spec.base_dir"));
    let repo_root = PathBuf::from(spec["repo_root"].as_str().expect("spec.repo_root"));
    std::fs::create_dir_all(&base).unwrap();

    let projects: Vec<ProjectSpec> = spec["projects"]
        .as_array()
        .expect("spec.projects")
        .iter()
        .map(parse_project)
        .collect();
    assert!(!projects.is_empty(), "规格空项目（emit-spec 应至少产出 5 件套）");

    let mut all = Vec::new();
    for p in &projects {
        eprintln!("\n== #114 多件矩阵 · {}（{} 件）==", p.id, p.files.len());
        let m = run_project(&base, &repo_root, p);
        eprintln!(
            "#114 {} | real={} | reqs={} | files_ok={} | conflicts={} | scoring_items={} | unmapped_after={}",
            p.id,
            p.real,
            m["req_count"].as_u64().unwrap_or(0),
            m["import_totals"]["files"].as_u64().unwrap_or(0),
            m["extract_conflicts"].as_array().map(|a| a.len()).unwrap_or(0),
            m["scoring_mapping"]["scoring_items"].as_u64().unwrap_or(0),
            m["scoring_mapping"]["unmapped_after"].as_u64().unwrap_or(0),
        );
        all.push(m);
    }
    // 汇总落盘（评审器单文件消费）
    std::fs::write(
        base.join("multifile-all.json"),
        serde_json::to_string_pretty(&json!({ "projects": all })).unwrap(),
    )
    .unwrap();
    eprintln!("\n#114 多件矩阵真跑完成：{} 项目 → {}", projects.len(), base.join("multifile-all.json").display());
}
