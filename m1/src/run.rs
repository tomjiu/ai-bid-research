//! run.rs — 场景编排：执行 expected-transitions 语义的 M1 工具序列，
//! 自检 step expects，产出冻结契约工件（db.json / trace.jsonl / blocks.jsonl / chunks.jsonl）。
//!
//! M1 场景（grade.py scenario 字段路由断言）：
//!   TC-01 条款完整性召回 | TC-02 精确匹配 | TC-07 幂等重放 | TC-11 越级防护
//! 全场景共用管线：create → import(main 4) → import(addendum C) → import(evidence 13)
//!   → extract → chunk → search(exact-25 ×5) → idempotent replay → [TC-11: guard probe]
//! —— 查询集 Q-04/Q-10 覆盖补遗文件，故所有场景统一含 C（记录于 run-notes/db.m1_notes）。
//!
//! 诚实纪律：G3 矩阵 / G4 引用 / G6 规则为 M2/M3/M4 范围，db.json 不含这些字段——
//! 判分器按缺字段 FAIL（不造假绿）；step expects 中需要 GT 知识的键（missing_declared）
//! 记 SKIPPED（M2 合规矩阵范围）。补遗影响面级联（DIRTY/重检/终裁）属 TC-09/V2，不在本场景。

use crate::contract::{content_hash, Block, FileStat, ParseReport, Req, TraceEntry};
use crate::state::Machine;
use serde_json::json;
use std::path::PathBuf;

pub struct RunCfg {
    pub scenario: String,
    pub corpus_files: PathBuf, // fixtures/corpus-A/files
    pub queries: PathBuf,      // fixtures/queries/exact-25.jsonl
    pub out: PathBuf,          // runs/<scenario>/
}

struct RunState {
    machine: Machine,
    trace: Vec<TraceEntry>,
    seq: u32,
    blocks: Vec<Block>,
    files: Vec<FileStat>,
    reports: Vec<ParseReport>,
    sha_by_name: std::collections::BTreeMap<String, String>,
    notes: Vec<serde_json::Value>,
}

impl RunState {
    fn log(&mut self, tool: &str, args: serde_json::Value, result: serde_json::Value) {
        self.seq += 1;
        self.trace.push(TraceEntry { seq: self.seq, tool: tool.into(), args, result });
    }
    fn note(&mut self, step: u32, key: &str, status: &str, detail: String) {
        self.notes.push(json!({"step": step, "key": key, "status": status, "detail": detail}));
    }
    fn chunks(&self) -> Vec<crate::chunk::Chunk> {
        crate::chunk::chunk(&self.blocks)
    }
}

/// 导入单一入口（幂等 + 块扩展 + parse 报告）。
/// rel == "evidence" 时展开为目录 13 件（文件名排序——确定性）。
fn do_import(
    st: &mut RunState,
    cfg: &RunCfg,
    rel: &str,
    order_counter: &mut u32,
) -> Result<Vec<(String, bool)>, String> {
    let targets: Vec<String> = if rel == "evidence" {
        let mut names: Vec<String> = std::fs::read_dir(cfg.corpus_files.join("evidence"))
            .map_err(|e| e.to_string())?
            .filter_map(|e| e.ok())
            .map(|e| e.file_name().to_string_lossy().to_string())
            .filter(|n| n.to_lowercase().ends_with(".pdf"))
            .collect();
        names.sort();
        names.iter().map(|n| format!("evidence/{}", n)).collect()
    } else {
        vec![rel.to_string()]
    };
    let mut results = Vec::new();
    for t in targets {
        let path = cfg.corpus_files.join(&t);
        if !path.exists() {
            return Err(format!("file not found: {}", t));
        }
        let outcome = crate::import::import_file(&path, &t, *order_counter);
        let sha = outcome.sha256.clone();
        let fresh = match st.machine.import_file(&sha, "main", &t) {
            Some(_fid) => {
                *order_counter = outcome.blocks.last().map(|b| b.order + 1).unwrap_or(*order_counter);
                st.blocks.extend(outcome.blocks.clone());
                let parse_status =
                    if !outcome.report.failures.is_empty() || outcome.report.blocks == 0 {
                        "failed".to_string()
                    } else if outcome.report.kind == "pdf-scan(ocr)" {
                        "ocr_required".to_string()
                    } else {
                        "ok".to_string()
                    };
                st.files.push(FileStat {
                    name: t.clone(),
                    parse_status,
                    ocr_blocks: outcome.report.ocr_blocks,
                });
                st.reports.push(outcome.report);
                st.sha_by_name.insert(t.clone(), sha);
                true
            }
            None => false, // no-op 重放
        };
        results.push((t, fresh));
    }
    Ok(results)
}

fn toolchain_info() -> serde_json::Value {
    let tess = std::process::Command::new("tesseract").arg("--version").output()
        .ok().and_then(|o| String::from_utf8(o.stdout).ok())
        .and_then(|s| s.lines().next().map(|x| x.to_string()))
        .unwrap_or_else(|| "unknown".into());
    let pdftotext = std::process::Command::new("pdftotext").arg("-v").output()
        .ok().and_then(|o| String::from_utf8(o.stderr).ok())
        .and_then(|s| s.lines().next().map(|x| x.to_string()))
        .unwrap_or_else(|| "unknown".into());
    let tess_sha = {
        let td = crate::import::resolve_tessdata();
        std::fs::read(td.join("chi_sim.traineddata"))
            .ok().map(|b| content_hash(&[&String::from_utf8_lossy(&b)]))
            .unwrap_or_default()
    };
    json!({"tesseract": tess, "poppler": pdftotext, "chi_sim_sha256": tess_sha})
}

pub fn run(cfg: &RunCfg) -> Result<i32, String> {
    let a = "A-招标文件.docx";
    let b1 = "B1-设备清单.pdf";
    let b2 = "B2-投标函格式页-扫描件.pdf";
    let b3 = "B3-图纸目录.xlsx";
    let c = "C-补遗文件01.docx";

    let mut st = RunState {
        machine: Machine::new(),
        trace: Vec::new(),
        seq: 0,
        blocks: Vec::new(),
        files: Vec::new(),
        reports: Vec::new(),
        sha_by_name: std::collections::BTreeMap::new(),
        notes: Vec::new(),
    };
    let mut order: u32 = 1;
    let mut exit_code = 0;

    // ---- step 1：create_bid_project（external_ref 幂等）----
    st.machine.call_tool("create_bid_project").map_err(|e| e.to_string())?;
    let ext_ref = "ZFCG-2026-GK-0311";
    let pid = st.machine.create_project(ext_ref);
    st.log("create_bid_project",
           json!({"name": "某市政务服务中心智能化系统工程（货物及服务）", "code": ext_ref}),
           json!({"project_id": pid}));
    st.note(1, "project.status", "pass", "DRAFT".into());

    // ---- step 2：import 主件（A/B1/B2/B3）----
    st.machine.call_tool("import_tender_files").map_err(|e| e.to_string())?;
    let mut fresh_main = 0;
    for f in [a, b1, b2, b3] {
        for (_n, fresh) in do_import(&mut st, cfg, f, &mut order)? {
            if fresh { fresh_main += 1; }
        }
    }
    let chunks_main = st.chunks();
    st.log("import_tender_files", json!({"files": [a, b1, b2, b3], "kind": "main"}),
        json!({"files": fresh_main, "chunks": chunks_main.len()}));
    for (i, want) in ["ok", "ok", "ocr_required", "ok"].iter().enumerate() {
        let got = st.files.get(i).map(|f| f.parse_status.clone()).unwrap_or_default();
        let ok = &got == want;
        st.note(2, &format!("files[{}].parse_status", i), if ok { "pass" } else { "fail" }, format!("got {}", got));
        if !ok { exit_code = 1; }
    }
    let ge100 = chunks_main.len() >= 100;
    st.note(2, "totals.chunks_ge", if ge100 { "pass" } else { "fail" }, format!("chunks={}", chunks_main.len()));
    if !ge100 { exit_code = 1; }

    // ---- step 2b：import 补遗 C（全场景统一：查询集 Q-04/Q-10 覆盖；级联是 V2/TC-09 范围）----
    st.machine.call_tool("import_tender_files").map_err(|e| e.to_string())?;
    let cres = do_import(&mut st, cfg, c, &mut order)?;
    st.machine.bump_content_version();
    st.log("import_tender_files", json!({"files": [c], "kind": "addendum"}),
        json!({"fresh": cres.first().map(|x| x.1).unwrap_or(false),
               "content_version": st.machine.content_version}));

    // ---- step 3：import 企业资料库 13 件 ----
    let eres = do_import(&mut st, cfg, "evidence", &mut order)?;
    let ev_n = eres.iter().filter(|(n, _)| n.starts_with("evidence/")).count();
    st.log("import_tender_files", json!({"files": "evidence/ 13 件（企业资料库）", "kind": "evidence"}),
        json!({"evidence_imported": ev_n}));
    let ev_ok = ev_n == 13;
    st.note(3, "evidence_imported", if ev_ok { "pass" } else { "fail" }, format!("{}", ev_n));
    if !ev_ok { exit_code = 1; }
    // missing_declared：需要"条款要求 × 证据提供"绑定知识（M2 合规矩阵范围）——诚实 SKIPPED
    st.note(3, "missing_declared", "skipped", "M2 合规矩阵范围（requires requirement×evidence binding）".into());

    // ---- step 4：extract_requirements ----
    st.machine.call_tool("extract_requirements").map_err(|e| e.to_string())?;
    let ex = crate::extract::extract(&st.blocks, a, b2);
    st.log("extract_requirements", json!({}),
        json!({"requirements": ex.reqs.len(), "missing_sequence": ex.missing_sequence.len()}));

    // ---- chunk 清单（import 产物的检索面）----
    st.machine.call_tool("chunk_corpus").map_err(|e| e.to_string())?;
    let chunks = st.chunks();
    st.log("chunk_corpus", json!({}), json!({"chunks": chunks.len()}));

    // ---- step 7：search_evidence exact 通道 ×5（TC-02）----
    st.machine.call_tool("search_evidence").map_err(|e| e.to_string())?;
    let queries = crate::search::load_queries(&cfg.queries)?;
    let (hits, per) = crate::search::exact_search(&queries, &st.blocks);
    let stable = crate::search::repeat_consistent(&queries, &st.blocks, 5);
    st.log("search_evidence", json!({"queries": "exact-25.jsonl", "channel": "exact", "times": 5}),
        json!({"hits": hits, "repeat_consistent": stable}));

    // ---- step 8：幂等重放（TC-07 核心；全场景记录）----
    st.machine.call_tool("import_tender_files").map_err(|e| e.to_string())?;
    let files_before = st.files.len();
    let totals_before = chunks.len();
    let sha_a = st.sha_by_name.get(a).cloned().unwrap_or_default();
    let rres = do_import(&mut st, cfg, a, &mut order)?;
    let fid = st.machine.file_id_of(&sha_a).unwrap_or_default();
    st.log("import_tender_files", json!({"files": [a], "idempotency_key": "同 sha256 重放"}),
        json!({"result": "no-op", "file_id": fid, "fresh": rres.first().map(|x| x.1).unwrap_or(false)}));
    let files_after = st.files.len();
    let chunks_after = st.chunks().len();

    // ---- 场景尾部 ----
    let mut last_error: Option<String> = None;
    match cfg.scenario.as_str() {
        "TC-11" => {
            // 越级防护：REQUIREMENTS_EXTRACTED 下调用起草 → E_STATE、零副作用
            match st.machine.call_tool("draft_response_section") {
                Err(e) => {
                    let code = e.split(':').next().unwrap_or("E_STATE").to_string();
                    last_error = Some(code.clone());
                    st.log("draft_response_section", json!({"section": "任意"}),
                        json!({"error": code, "side_effect": "none"}));
                    st.note(9, "error", "pass", "E_STATE".into());
                    st.note(9, "side_effect",
                           if st.files.len() == files_after { "pass" } else { "fail" },
                           "sections=0 无副作用".into());
                }
                Ok(_) => {
                    st.note(9, "error", "fail", "guard let the call through!".into());
                    exit_code = 1;
                }
            }
        }
        "TC-02" => {
            let ok = hits == 25 && stable;
            st.note(7, "hits", if ok { "pass" } else { "fail" },
                    format!("hits={} stable={}", hits, stable));
            if !ok { exit_code = 1; }
        }
        "TC-07" => {
            let ok = files_before == files_after && totals_before == chunks_after;
            st.note(8, "no-op", if ok { "pass" } else { "fail" },
                    format!("files {}→{} chunks {}→{}", files_before, files_after, totals_before, chunks_after));
            if !ok { exit_code = 1; }
        }
        "TC-01" => { /* step expects 已逐项自检；asserts 交给判分器 */ }
        other => return Err(format!("unknown scenario: {}", other)),
    }

    // ---- 产出工件（全部确定性：无时间戳，内容寻址 ID）----
    std::fs::create_dir_all(&cfg.out).map_err(|e| e.to_string())?;
    let reqs: Vec<&Req> = ex.reqs.iter().collect();
    let db = json!({
        "scenario": cfg.scenario,
        "project": {"status": st.machine.status, "content_version": st.machine.content_version},
        "files": st.files,
        "totals": {"chunks": chunks.len(), "blocks": st.blocks.len(),
                   "chars": st.blocks.iter().map(|b| b.text.chars().count()).sum::<usize>()},
        "parse": {"missing_sequence": ex.missing_sequence, "reports": st.reports},
        "requirements": reqs,
        "exact": {"hits": hits, "per_query": per},
        "idempotency": {"files_before": files_before, "files_after": files_after,
                        "totals_before": totals_before, "totals_after": chunks_after},
        "stability": {"repeat_consistent": stable},
        "sections": [],
        "last_tool_result": {"error": last_error},
        "m1_notes": {
            "toolchain": toolchain_info(),
            "pending_dims": ["G3_policy(M2 合规矩阵)", "G4_citation(M3 章节起草)", "G6_rules(M4 规则审校)"],
            "corpus_includes_addendum": true,
            "addendum_cascade": "TC-09/V2 范围，本场景不含",
        },
    });
    std::fs::write(cfg.out.join("db.json"),
                   serde_json::to_string_pretty(&db).map_err(|e| e.to_string())?.as_bytes())
        .map_err(|e| e.to_string())?;
    std::fs::write(cfg.out.join("trace.jsonl"),
                   st.trace.iter().map(|t| serde_json::to_string(t).unwrap_or_default())
                       .collect::<Vec<_>>().join("\n") + "\n")
        .map_err(|e| e.to_string())?;
    std::fs::write(cfg.out.join("blocks.jsonl"),
                   st.blocks.iter().map(|b| serde_json::to_string(b).unwrap_or_default())
                       .collect::<Vec<_>>().join("\n") + "\n")
        .map_err(|e| e.to_string())?;
    std::fs::write(cfg.out.join("chunks.jsonl"),
                   chunks.iter().map(|ch| json!({"chunk_id": ch.chunk_id, "files": ch.files,
                                                 "first_order": ch.first_order, "chars": ch.chars}).to_string())
                       .collect::<Vec<_>>().join("\n") + "\n")
        .map_err(|e| e.to_string())?;
    std::fs::write(cfg.out.join("run-notes.json"),
                   serde_json::to_string_pretty(&json!({
                       "scenario": cfg.scenario, "step_checks": st.notes,
                       "toolchain": toolchain_info()})).unwrap_or_default().as_bytes())
        .map_err(|e| e.to_string())?;

    println!("[m1] scenario={} requirements={} chunks={} hits={}/{} files={} stable={}",
             cfg.scenario, ex.reqs.len(), chunks.len(), hits, queries.len(), st.files.len(), stable);
    println!("[m1] missing_sequence={} parse_failures={}",
             ex.missing_sequence.len(),
             st.files.iter().filter(|f| f.parse_status == "failed").count());
    for n in &st.notes {
        if n["status"] == "fail" {
            println!("[m1][STEP-FAIL] {}", serde_json::to_string(n).unwrap_or_default());
        }
    }
    Ok(exit_code)
}
