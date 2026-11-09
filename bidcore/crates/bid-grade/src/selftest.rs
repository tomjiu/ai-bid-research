//! 判分器自测：完美运行全绿 + 破坏注入全捕获 + dedupe 合并运行 + 场景破坏。
//! 口径与 scripts/grade.py 自测对齐；新增 Rust 原生防线：**类型化 schema 的反序列化拒绝**
//! （Python 时代的「布尔字段伪装」破坏在类型化 schema 下于反序列化期即被拦截——编译期契约的运行期验证）。

use crate::fixtures::{Fixtures, GtAnchor, GtRequirement};
use crate::grade;
use bid_tools::schema::*;
use serde_json::json;
use std::collections::HashMap;

fn perfect_db(fx: &Fixtures) -> RunDb {
    let mut reqs = vec![];
    for (i, gt) in fx.gts.iter().enumerate() {
        reqs.push(ReqInfo {
            req_id: format!("REQ-{:03}", i + 1),
            gt_ids: vec![gt.gt_id.clone()],
            category: gt.category.clone(),
            clause_no: gt.clause_no.as_ref().and_then(|c| c.as_str()).map(String::from),
            anchors: gt.anchors.iter().map(|a| AnchorInfo {
                file: a.file.clone(), kind: a.kind.clone(),
                locator: a.locator.clone(), excerpt: a.excerpt.clone(),
            }).collect(),
            params: gt.params.as_object().map(|o| o.iter().map(|(k, v)| (k.clone(), v.clone())).collect()).unwrap_or_default(),
            source_file: "A-招标文件.docx".into(),
        });
    }
    let mut matrix = vec![];
    for gt in &fx.gts {
        let policy = match gt.expected_policy.as_deref() {
            Some("eligible") => "eligible".to_string(),
            Some("not_eligible") => "not_eligible".to_string(),
            _ => if ["评分项", "技术参数", "商务要求", "格式要求"].contains(&gt.category.as_str()) {
                "response_required".to_string()
            } else {
                "veto_item".to_string()
            },
        };
        let mut row = json!({
            "gt_id": gt.gt_id, "category": gt.category,
            "explicit_policy": true, "policy": policy,
        });
        if gt.gt_id == "GT-02" {
            row["policy"] = json!("eligible");
            row["policy_pre_addendum"] = json!("eligible");
            row["policy_post_addendum"] = json!("not_eligible");
        }
        if gt.gt_id == "GT-04" {
            row["policy"] = json!("not_eligible");
        }
        if gt.gt_id == "GT-13" {
            row["forbidden_bind"] = json!(true);
        }
        matrix.push(row);
    }
    // 补遗后终态：GT-02 翻转
    for row in matrix.iter_mut() {
        if row["gt_id"] == "GT-02" {
            row["policy"] = json!("not_eligible");
        }
    }
    let per_query = fx.queries.iter().map(|q| PerQuery {
        query_id: q["query_id"].as_str().unwrap().into(),
        hit: true,
        hit_text: q["expect"]["hit_text"].as_str().unwrap().into(),
        hit_file: q["expect"]["hit_file"].as_str().unwrap().into(),
        repeats_consistent: true,
    }).collect();
    RunDb {
        scenario: "full".into(),
        milestone: "full".into(),
        project: ProjectInfo { status: "EXPORTED".into(), content_version: 2 },
        files: vec![
            FileInfo { name: "A-招标文件.docx".into(), kind: "招标文件".into(),
                       sha256: "a".into(), pages: 31, tables: 6, chunks: 182, ocr_blocks: 0,
                       parse_status: "ok".into(), parse_summary: String::new() },
            FileInfo { name: "B1-设备清单.pdf".into(), kind: "附件".into(),
                       sha256: "b1".into(), pages: 2, tables: 0, chunks: 45, ocr_blocks: 0,
                       parse_status: "ok".into(), parse_summary: String::new() },
            FileInfo { name: "B2-投标函格式页-扫描件.pdf".into(), kind: "附件".into(),
                       sha256: "b2".into(), pages: 1, tables: 0, chunks: 20, ocr_blocks: 20,
                       parse_status: "ocr_required".into(), parse_summary: String::new() },
            FileInfo { name: "B3-图纸目录.xlsx".into(), kind: "图纸".into(),
                       sha256: "b3".into(), pages: 1, tables: 1, chunks: 23, ocr_blocks: 0,
                       parse_status: "ok".into(), parse_summary: String::new() },
        ],
        totals: Totals { files: 4, chunks: 270, parse_failed: 0, ocr_required: 1 },
        parse: ParseInfo { missing_sequence: vec![] },
        requirements: reqs,
        matrix,
        citation: Some(CitationInfo { unanchored_claims: 0, coverage: 1.0 }),
        findings: grade::RULES_8.iter().enumerate().map(|(i, c)| FindingInfo {
            rule_code: c.to_string(), kind: "DETERMINISTIC".into(),
            severity: if i < 3 { "BLOCKER" } else { "MAJOR" }.into(),
        }).collect(),
        exact: Some(ExactInfo { hits: 25, per_query }),
        conflicts: vec![json!({"conflict_id": "CONFLICT-01", "resolved": true,
                                "final_value": 4_650_000, "rule": "补遗优先"})],
        idempotency: Some(IdempotencyInfo {
            files_before: 4, files_after: 4, totals_before: 312, totals_after: 312 }),
        sections: vec![
            SectionInfo { id: "资格响应".into(), status: "ACCEPTED".into(), dirty: true,
                          last_model: Some("A".into()), rerun_count: 1 },
            SectionInfo { id: "技术方案-网络与安全".into(), status: "ACCEPTED".into(), dirty: true,
                          last_model: Some("A".into()), rerun_count: 1 },
            SectionInfo { id: "商务部分-报价".into(), status: "ACCEPTED".into(), dirty: true,
                          last_model: Some("A".into()), rerun_count: 1 },
            SectionInfo { id: "售后服务方案".into(), status: "ACCEPTED".into(), dirty: false,
                          last_model: Some("A".into()), rerun_count: 0 },
            SectionInfo { id: "项目团队".into(), status: "ACCEPTED".into(), dirty: false,
                          last_model: Some("A".into()), rerun_count: 0 },
            SectionInfo { id: "格式与签署".into(), status: "ACCEPTED".into(), dirty: false,
                          last_model: Some("A".into()), rerun_count: 0 },
        ],
        recheck: HashMap::from([("GT-02".to_string(), "全项目有效期重检已执行".to_string())]),
        export: Some(json!({"dark_bid_word_scan_hits": 0,
                             "artifact": {"pages_word_render": 168, "sha256": "deadbeefdeadbeef"}})),
        resume_plan: Some(json!({"sections": ["SEC-02", "SEC-03"]})),
        stability: Some(StabilityInfo { repeat_consistent: true }),
        last_tool_result: LastToolResult { error: None },
    }
}

fn scenario_db(base: &RunDb, kind: &str) -> RunDb {
    let mut db = base.clone();
    match kind {
        "TC-06" => {
            db.project.status = "DRAFTING".into();
            db.sections = vec![
                SectionInfo { id: "SEC-01".into(), status: "ACCEPTED".into(), dirty: false,
                              last_model: Some("A".into()), rerun_count: 0 },
                SectionInfo { id: "SEC-02".into(), status: "DRAFTING".into(), dirty: false,
                              last_model: Some("A".into()), rerun_count: 0 },
                SectionInfo { id: "SEC-03".into(), status: "PENDING".into(), dirty: false,
                              last_model: None, rerun_count: 0 },
            ];
        }
        "TC-08" => {
            db.sections = vec![
                SectionInfo { id: "SEC-01".into(), status: "ACCEPTED".into(), dirty: false,
                              last_model: Some("A".into()), rerun_count: 0 },
                SectionInfo { id: "SEC-02".into(), status: "DRAFTED".into(), dirty: false,
                              last_model: Some("B".into()), rerun_count: 1 },
            ];
        }
        "TC-11" => {
            db.project.status = "FILES_IMPORTED".into();
            db.sections = vec![];
            db.last_tool_result = LastToolResult { error: Some("E_STATE".into()) };
        }
        _ => {}
    }
    db.scenario = kind.to_string();
    db
}

/// 自测入口：返回失败计数（0 = 全部通过）。
pub fn run(fx: &Fixtures) -> usize {
    let mut failed = 0usize;
    // ---- 场景全绿 ----
    let cases: Vec<(&str, RunDb, Option<&str>)> = vec![
        ("完整运行（全七项）", perfect_db(fx), None),
        ("TC-06 断点恢复场景", scenario_db(&perfect_db(fx), "TC-06"), Some("TC-06")),
        ("TC-08 换模型场景", scenario_db(&perfect_db(fx), "TC-08"), Some("TC-08")),
        ("TC-11 越级防护场景", scenario_db(&perfect_db(fx), "TC-11"), Some("TC-11")),
    ];
    for (name, db, only) in &cases {
        let report = if let Some(tc) = only {
            let mut d = db.clone();
            d.scenario = tc.to_string();
            d.milestone = "full".into();
            grade::grade_run(&d, fx)
        } else {
            grade::grade_run(db, fx)
        };
        let bad: Vec<&String> = report["dimensions"].as_object().unwrap()
            .iter().filter(|(_, v)| v["pass"].as_bool() != Some(true))
            .map(|(k, _)| k).collect();
        let mark = if bad.is_empty() { "✓" } else { "✗" };
        println!("[自测] {mark} {name}：{}", if bad.is_empty() { "全绿".into() } else { format!("失败 {bad:?}") });
        if !bad.is_empty() { failed += 1; }
    }

    // ---- 破坏注入：每处必须被对应判分项捕获 ----
    let perfect = perfect_db(fx);
    let all_gt_ids: Vec<String> = fx.gts.iter().map(|g| g.gt_id.clone()).collect();
    let full_anchor_text: String = fx.gts.iter()
        .flat_map(|g| g.anchors.iter().filter(|a| a.file == "A-招标文件.docx"))
        .map(|a| a.excerpt.clone()).collect::<Vec<_>>().join("。");
    let junk_clauses: Vec<Option<String>> = fx.gts.iter().filter(|g| g.gt_id != "GT-11")
        .map(|g| g.clause_no.as_ref().and_then(|c| c.as_str()).map(String::from))
        .collect();
    type Corrupt = Box<dyn Fn(&mut RunDb)>;
    let corruptions: Vec<(&str, &str, Corrupt)> = vec![
        ("漏表格条款GT-11", "G1_recall", Box::new(|db: &mut RunDb| {
            db.requirements.retain(|r| !r.gt_ids.contains(&"GT-11".to_string()));
        })),
        ("矩阵GT-04误判eligible", "G3_policy", Box::new(|db: &mut RunDb| {
            for row in db.matrix.iter_mut() {
                if row["gt_id"] == "GT-04" { row["policy"] = json!("eligible"); }
            }
        })),
        ("未锚定承诺", "G4_citation", Box::new(|db: &mut RunDb| {
            if let Some(c) = db.citation.as_mut() { c.unanchored_claims = 2; }
        })),
        ("规则漏报DARK_BID_WORD", "G6_rules", Box::new(|db: &mut RunDb| {
            db.findings.retain(|f| f.rule_code != "DARK_BID_WORD");
        })),
        ("幂等重复入块", "G7_idempotency", Box::new(|db: &mut RunDb| {
            if let Some(i) = db.idempotency.as_mut() { i.totals_after += 96; }
        })),
        ("精确查询Q-04未命中", "G2_exact", Box::new(|db: &mut RunDb| {
            if let Some(e) = db.exact.as_mut() {
                e.hits = 24;
                if let Some(p) = e.per_query.iter_mut().find(|p| p.query_id == "Q-04") {
                    p.hit = false;
                }
            }
        })),
        ("标记回声伪造召回（自报无锚点）", "G1_recall", Box::new(move |db: &mut RunDb| {
            let ids: Vec<String> = all_gt_ids.clone();
            db.requirements = vec![ReqInfo {
                req_id: "REQ-echo".into(), gt_ids: ids, category: "其他".into(),
                clause_no: None, anchors: vec![], params: Default::default(),
                source_file: "A-招标文件.docx".into(),
            }];
        })),
        ("全文锚点伪对齐", "G1_recall", Box::new(move |db: &mut RunDb| {
            db.requirements = vec![ReqInfo {
                req_id: "REQ-全文".into(), gt_ids: vec![], category: "资格条件".into(),
                clause_no: None,
                anchors: vec![AnchorInfo { file: "A-招标文件.docx".into(), kind: "para".into(),
                                             locator: "全文粘贴".into(),
                                             excerpt: full_anchor_text.clone() }],
                params: Default::default(), source_file: "A-招标文件.docx".into(),
            }];
        })),
        ("垃圾REQ伪对齐", "G1_recall", Box::new(move |db: &mut RunDb| {
            let clauses = junk_clauses.clone();
            let mut junk = vec![];
            for i in 0..24 {
                junk.push(ReqInfo {
                    req_id: format!("REQ-junk-{i}"), gt_ids: vec![], category: "其他".into(),
                    clause_no: clauses.get(i).cloned().flatten(),
                    anchors: vec![AnchorInfo { file: "A-招标文件.docx".into(), kind: "para".into(),
                                                 locator: "任意".into(),
                                                 excerpt: "投标报价超过招标控制价（最高限价）的，作否决投标处理。".into() }],
                    params: Default::default(), source_file: "A-招标文件.docx".into(),
                });
            }
            db.requirements = junk;
        })),
        ("幂等字段缺失", "G7_idempotency", Box::new(|db: &mut RunDb| {
            db.idempotency = None;
        })),
    ];
    for (name, expect_dim, corrupt) in &corruptions {
        let mut db = perfect.clone();
        corrupt(&mut db);
        let report = grade::grade_run(&db, fx);
        let dim_fail: Vec<&String> = report["dimensions"].as_object().unwrap()
            .iter().filter(|(_, v)| v["status"].as_str() == Some("FAIL"))
            .map(|(k, _)| k).collect();
        let ok = dim_fail.iter().any(|d| d.as_str() == *expect_dim);
        let mark = if ok { "✓" } else { "✗" };
        println!("[自测] {mark} 破坏『{name}』被捕获（失败维度: {dim_fail:?}）");
        if !ok { failed += 1; }
    }

    // ---- Rust 原生防线：类型化 schema 拒绝伪装字段（Python 时代「布尔伪装」破坏的新形态）----
    {
        let mut db = perfect.clone();
        if let Some(c) = db.citation.as_mut() {
            c.coverage = 1.0; // 类型上只能是 f64——布尔伪装在编译期不可能
        }
        let raw = serde_json::to_string(&db).unwrap();
        let mut bad = raw.replace("\"unanchored_claims\":0", "\"unanchored_claims\":false");
        bad = bad.replace("\"coverage\":1.0", "\"coverage\":true");
        let parsed: Result<RunDb, _> = serde_json::from_str(&bad);
        let ok = parsed.is_err();
        println!("[自测] {} 破坏『布尔字段伪装』被反序列化拒绝（类型化 schema 契约）",
                 if ok { "✓" } else { "✗" });
        if !ok { failed += 1; }
    }

    // ---- dedupe 合并运行：GT-03/GT-14 合为 1 条 REQ（24 条）全绿 ----
    {
        let mut db = perfect.clone();
        let mut r03 = db.requirements.iter().position(|r| r.gt_ids.contains(&"GT-03".to_string())).unwrap();
        let r14 = db.requirements.iter().position(|r| r.gt_ids.contains(&"GT-14".to_string())).unwrap();
        let r14v = db.requirements[r14].clone();
        db.requirements[r03].gt_ids = vec!["GT-03".into(), "GT-14".into()];
        db.requirements[r03].anchors.extend(r14v.anchors.iter().cloned());
        // 合并 REQ 声明全部所属类别（逗号连写 = Python 列表口径的类型化等价物）
        if db.requirements[r03].category != r14v.category {
            let a = db.requirements[r03].category.clone();
            let b = r14v.category.clone();
            db.requirements[r03].category = format!("{a},{b}");
        }
        db.requirements[r03].clause_no = db.requirements[r03].clause_no.clone();
        db.requirements.remove(r14);
        let _ = &mut r03;
        let report = grade::grade_run(&db, fx);
        let bad: Vec<&String> = report["dimensions"].as_object().unwrap()
            .iter().filter(|(_, v)| v["pass"].as_bool() != Some(true))
            .map(|(k, _)| k).collect();
        let ok = bad.is_empty();
        println!("[自测] {} dedupe 合并运行（24 REQ 双锚点）：{}",
                 if ok { "✓" } else { "✗" },
                 if ok { "全绿".into() } else { format!("失败 {bad:?}") });
        if !ok { failed += 1; }
    }

    // ---- 场景破坏：TC-11 越级被放行（出现副作用章节）----
    {
        let mut db11 = scenario_db(&perfect, "TC-11");
        db11.sections = vec![SectionInfo { id: "越级章节".into(), status: "DRAFTING".into(),
                                            dirty: false, last_model: Some("A".into()), rerun_count: 0 }];
        db11.last_tool_result = LastToolResult { error: None };
        db11.scenario = "TC-11".into();
        db11.milestone = "full".into();
        let report = grade::grade_run(&db11, fx);
        let g5_fail = report["dimensions"]["G5_transitions"]["detail"]["asserts"]
            .as_array().map(|a| a.iter().filter(|r| r["pass"].as_bool() == Some(false)).count())
            .unwrap_or(0);
        let ok = g5_fail > 0;
        println!("[自测] {} 破坏『越级E_STATE被放行』被捕获（TC-11 断言失败 {g5_fail} 条）",
                 if ok { "✓" } else { "✗" });
        if !ok { failed += 1; }
    }

    // ---- 场景破坏 2：TC-11 留空字段中性化（error=None + 空断言上下文）----
    {
        let mut db11b = scenario_db(&perfect, "TC-11");
        db11b.last_tool_result = LastToolResult { error: None };
        db11b.scenario = "TC-11".into();
        db11b.milestone = "full".into();
        let report = grade::grade_run(&db11b, fx);
        let g5_fail = report["dimensions"]["G5_transitions"]["detail"]["asserts"]
            .as_array().map(|a| a.iter().filter(|r| r["pass"].as_bool() == Some(false)).count())
            .unwrap_or(0);
        let ok = g5_fail > 0;
        println!("[自测] {} 破坏『留空字段中性化 E_STATE 断言』被捕获（断言失败 {g5_fail} 条）",
                 if ok { "✓" } else { "✗" });
        if !ok { failed += 1; }
    }
    failed
}

pub fn _unused(_a: &GtRequirement, _b: &GtAnchor) {}
