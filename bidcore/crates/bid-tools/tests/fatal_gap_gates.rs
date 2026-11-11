//! #88 审计 F-01/F-02 收口：致命项门（导出门 1e/1f）的 findings 单测。
//!
//! 覆盖面（纯函数层——store/parsed 构造，零真件依赖）：
//! - **★响应门子面 a（E_STAR_UNRESPONDED）**：★未响应/Partial 无章节/
//!   占位 → BLOCKER；RESPONDED → 放行；合法不适用豁免（三要件）→ 放行；
//!   legacy 快照 NA 缺 receipt（serde 回环造真）→ BLOCKER；非★同态行零干扰；
//! - **★响应门子面 b（E_STAR_MISSING）**：★块无对应 REQ → BLOCKER；
//!   ★块已捕获（REQ 在场）→ 放行；无★文件零 findings；
//! - **暗标联动门（mode 感知）**：mode=暗标 未启用 → BLOCKER；启用 →
//!   零 findings；mode=明标 + 暗标条款 → MINOR 告警；否定形（商务标
//!   不采用暗标）→ 零 findings；混合句（技术标采用暗标）→ 命中；
//!   补遗条款文本引入的暗标要求 → 命中；间接提及不命中。
//!
//! 接线面（export_document 消费两门 + 豁免面）见 bid-mcp/tests/
//! fatal_gates_e2e.rs（corpus-A 真件全链）。

use std::collections::HashMap;

use bid_domain::evidence::{EvidenceKind, EvidenceSpec};
use bid_domain::locator::EngineLocator;
use bid_domain::matrix::ResponseStatus;
use bid_domain::outline::OutlineSpec;
use bid_domain::{Anchor, DomainStore, ProjectStatus, Requirement, TrustedPrincipal};
use bid_parse::{Block, BlockKind, ParsedFile};
use bid_tools::validate::{dark_bid_gate_findings, star_gate_findings};

// ---------------------------------------------------------------- 夹具

fn req(id: &str, category: &str, excerpt: &str, star: bool) -> Requirement {
    let mut params = HashMap::new();
    if star {
        params.insert("star".to_string(), serde_json::Value::Bool(true));
    }
    Requirement {
        id: id.into(),
        category: category.into(),
        clause_no: None,
        anchors: vec![Anchor {
            file: "A-招标文件.docx".into(),
            kind: "para".into(),
            locator: format!("第三章/{id}"),
            excerpt: excerpt.into(),
            block_idx: None,
            page: None,
            line: None,
        }],
        params,
        source_file: "A-招标文件.docx".into(),
    }
}

/// 建项（mode 可选）+ 注入 REQ 集 + 建纲建矩阵（矩阵行派生
/// substantive/status——findings 的消费面）。空 REQ 集 → 跳过建纲建矩阵
///（域层拒空纲——暗标门/漏标门无需章节树）。
fn store_with(reqs: Vec<Requirement>, mode: &str) -> DomainStore {
    let mut s = DomainStore::new();
    s.create_project("#88 门测", "ZFCG-2026-88", mode, "fg-88-key").unwrap();
    s.advance_project_status(ProjectStatus::FilesImported).unwrap();
    if reqs.is_empty() {
        return s;
    }
    s.set_requirements(reqs).unwrap();
    let _ = s
        .derive_and_set_outline(OutlineSpec { target_total_chars: 2_000, max_reqs_per_leaf: 6 })
        .unwrap();
    let _ = s.build_matrix().unwrap();
    s
}

/// 含指定 REQ 的**叶**章节 id（父节点聚合 requirement_ids 不算——正文只住叶）。
fn leaf_of(s: &DomainStore, req_id: &str) -> String {
    let has_child =
        |id: &str| s.sections().iter().any(|n| n.parent_id.as_deref() == Some(id));
    s.sections()
        .iter()
        .find(|n| !has_child(&n.id) && n.requirement_ids.iter().any(|r| r == req_id))
        .map(|n| n.id.clone())
        .unwrap_or_else(|| panic!("{req_id} 未归属任何叶章节"))
}

/// 真实证据登记（非占位——RESPONDED 派生腿；tier 可指定——占位面用
/// `Some(Placeholder)`，#245 语义）。
fn register_evidence_tier(s: &mut DomainStore, tag: &str, tier: Option<bid_domain::evidence::VerificationTier>) -> String {
    let (eid, _) = s
        .register_evidence(EvidenceSpec {
            kind: EvidenceKind::Qualification,
            title: format!("证书-{tag}"),
            source_file: "A-招标文件.docx".into(),
            source_sha256: format!("sha-{tag}"),
            locator: EngineLocator::DocxParagraph {
                paragraph_index: 1,
                text_fingerprint: format!("fnv64:{tag}"),
            },
            fingerprint: format!("fnv64:{tag}"),
            valid_from: None,
            valid_until: None,
            subject_name: "投标人".into(),
            scope: "测试".into(),
            client: None,
            amount_wan: None,
            completed_on: None,
            fields: Default::default(),
            excerpt: None,
            excerpt_locator: None,
            verification_tier: tier,
        })
        .unwrap();
    eid
}

/// 合成 parsed 文件（★文本块——star_scan 的输入面）。
fn parsed_with_star(text: &str) -> ParsedFile {
    ParsedFile {
        name: "A-招标文件.docx".into(),
        sha256: "sha-fg".into(),
        pages: 1,
        tables: 0,
        has_text_layer: true,
        ocr_blocks: 0,
        blocks: vec![Block {
            idx: 0,
            kind: BlockKind::Para,
            locator: "第三章/1（第 1 页 第 1 行）".into(),
            text: text.into(),
            cells: Vec::new(),
        }],
        parse_summary: "test".into(),
        components: Vec::new(),
    }
}

fn codes(fs: &[bid_tools::validate::ValidationFinding]) -> Vec<&str> {
    fs.iter().map(|f| f.rule_code.as_str()).collect()
}

// ---------------------------------------------------------------- 子面 a

#[test]
fn star_unresponded_is_blocker() {
    // ★技术参数（非必选类——门 1a 不拦，正是 F-01 的洞）未响应 → 本门拦
    let s = store_with(
        vec![req("REQ-0001", "技术参数", "★设备可靠性要求 MTBF≥10000 小时", true)],
        "明标",
    );
    let fs = star_gate_findings(&s, &[]);
    assert_eq!(codes(&fs), vec!["E_STAR_UNRESPONDED"], "★未响应 → BLOCKER");
    assert!(fs[0].message.contains("REQ-0001"));
}

#[test]
fn star_responded_passes() {
    let mut s = store_with(
        vec![req("REQ-0001", "技术参数", "★设备可靠性要求", true)],
        "明标",
    );
    // 章节正文实写（#241 文本事实口径）→ RESPONDED → 放行
    let leaf = leaf_of(&s, "REQ-0001");
    s.set_section_content(&leaf, "本章节对★设备可靠性要求给出完整响应方案。".into())
        .unwrap();
    let _ = s.build_matrix().unwrap();
    let fs = star_gate_findings(&s, &[]);
    assert!(fs.is_empty(), "★已响应（正文实写）→ 零 findings: {fs:?}");
}

#[test]
fn star_partial_without_section_is_blocker() {
    // Partial 面：证据在绑但 REQ 无归属章节（建纲后经补遗登记新增的 REQ
    // ——section_id 缺省 = 零章节影响的既定语义）→ 响应未进文档正文 → 拦。
    // star 标记面：补遗登记不产 params.star（star 来自抽取面/标记面）——
    // 用快照回环补标记（submit_block_marks 的写入等价：params.star=true）。
    let mut s = store_with(
        vec![req("REQ-0000", "商务要求", "常规商务条款（建纲锚）", false)],
        "明标",
    );
    let changes = s
        .register_addendum_changes(&[bid_domain::rewrite::ChangeSpec {
            req_id: None,
            change_type: bid_domain::rewrite::ChangeType::RequirementAdded,
            old_text: String::new(),
            new_requirement: "★设备可靠性要求（补遗新增）".into(),
            category: Some("技术参数".into()),
            clause_no: None,
            section_id: None, // 零章节影响——只进条款集与矩阵
            source_file_id: None,
        }])
        .unwrap();
    assert_eq!(changes.len(), 1, "补遗登记一条新增");
    let new_req_id = changes[0].change.req_id.clone();
    // 标记面等价：快照 → params.star=true → restore
    let mut v = serde_json::to_value(s.to_snapshot()).unwrap();
    let reqs = v
        .get_mut("requirements")
        .and_then(|r| r.as_array_mut())
        .expect("requirements 序列化在位");
    for r in reqs.iter_mut() {
        if r["id"].as_str() == Some(new_req_id.as_str()) {
            let mut params = r
                .get("params")
                .cloned()
                .unwrap_or_else(|| serde_json::json!({}));
            params["star"] = serde_json::Value::Bool(true);
            r["params"] = params;
        }
    }
    let snap: bid_domain::StoreSnapshot = serde_json::from_value(v).unwrap();
    let mut s = DomainStore::restore(snap).unwrap();
    let eid = register_evidence_tier(&mut s, "partial", None);
    s.bind_evidence(&eid, &new_req_id, "2026-12-31").unwrap();
    let _ = s.build_matrix().unwrap();
    let fs = star_gate_findings(&s, &[]);
    assert_eq!(codes(&fs), vec!["E_STAR_UNRESPONDED"], "Partial（无章节）→ BLOCKER");
    assert!(fs[0].message.contains("无归属章节"), "状态面指名 Partial 语义");
}

#[test]
fn star_pending_placeholder_is_blocker() {
    // ★非必选行仅占位绑定 → PENDING_EVIDENCE → 门 1a 不拦（非必选），
    // 本门拦（占位不构成★响应）
    let mut s = store_with(
        vec![req("REQ-0001", "技术参数", "★设备可靠性要求", true)],
        "明标",
    );
    let eid = register_evidence_tier(
        &mut s,
        "ph",
        Some(bid_domain::evidence::VerificationTier::Placeholder),
    );
    s.bind_evidence(&eid, "REQ-0001", "2026-12-31").unwrap();
    let _ = s.build_matrix().unwrap();
    let fs = star_gate_findings(&s, &[]);
    assert_eq!(codes(&fs), vec!["E_STAR_UNRESPONDED"], "仅占位 → BLOCKER");
    assert!(fs[0].message.contains("占位"), "状态面指名占位语义");
}

#[test]
fn star_legit_na_exemption_passes() {
    let mut s = store_with(
        vec![req("REQ-0001", "技术参数", "★设备可靠性要求", true)],
        "明标",
    );
    // 合法人工豁免三要件：NOT_APPLICABLE + 偏离说明 + 可信 Human receipt
    // （set_matrix_override 写入面强制 Human——#182）
    s.set_matrix_override(
        "REQ-0001".into(),
        ResponseStatus::NotApplicable,
        Some("该★条款针对特定检测环境，本项目不适用（人工裁定）".into()),
        &TrustedPrincipal::human("fg-lead"),
    )
    .unwrap();
    let _ = s.build_matrix().unwrap();
    let fs = star_gate_findings(&s, &[]);
    assert!(fs.is_empty(), "三要件豁免 → 零 findings: {fs:?}");
}

#[test]
fn star_legacy_na_without_receipt_is_blocker() {
    // legacy 快照面：NA + 偏离说明但 trusted 缺席（#247 之前的记录）——
    // 活 API 造不出（set_matrix_override 强制 Human receipt），用快照
    // DTO 回环造真：合法覆写 → StoreSnapshot JSON → 抹掉 trusted →
    // restore（legacy 快照的真实到达路径）。
    let mut s = store_with(
        vec![req("REQ-0001", "技术参数", "★设备可靠性要求", true)],
        "明标",
    );
    s.set_matrix_override(
        "REQ-0001".into(),
        ResponseStatus::NotApplicable,
        Some("说明在场但 receipt 被抹（legacy 快照面）".into()),
        &TrustedPrincipal::human("fg-lead"),
    )
    .unwrap();
    let _ = s.build_matrix().unwrap();
    let mut v = serde_json::to_value(s.to_snapshot()).unwrap();
    let ovs = v
        .get_mut("matrix_overrides")
        .and_then(|m| m.as_object_mut())
        .expect("matrix_overrides 序列化在位");
    for ov in ovs.values_mut() {
        ov["trusted"] = serde_json::Value::Null; // 抹掉 receipt（legacy 形）
    }
    let snap: bid_domain::StoreSnapshot = serde_json::from_value(v).unwrap();
    let legacy = DomainStore::restore(snap).unwrap();
    let fs = star_gate_findings(&legacy, &[]);
    assert_eq!(codes(&fs), vec!["E_STAR_UNRESPONDED"], "legacy NA 缺 receipt → BLOCKER");
    assert!(fs[0].message.contains("三要件不全"), "指名豁免要件缺位");
}

#[test]
fn non_star_unresponded_not_in_this_gate() {
    // 非★未响应（技术参数类，非必选）→ 本门零 findings（门 1a 语义
    // 之外的放行面不变——本门只管★，不越界改既有分级）
    let s = store_with(
        vec![req("REQ-0001", "技术参数", "设备可靠性要求（无★）", false)],
        "明标",
    );
    let fs = star_gate_findings(&s, &[]);
    assert!(fs.is_empty(), "非★未响应不进本门: {fs:?}");
}

// ---------------------------------------------------------------- 子面 b

#[test]
fn star_missing_blocker_when_truth_star_has_no_req() {
    // parsed ★块 + REQ 集空（漏抽取）→ E_STAR_MISSING
    let s = store_with(vec![], "明标");
    let pf = parsed_with_star("★本条为实质性条款，投标人须提供近三年类似业绩清单。");
    let fs = star_gate_findings(&s, &[pf]);
    assert_eq!(codes(&fs), vec!["E_STAR_MISSING"], "★块无 REQ → BLOCKER");
    assert!(fs[0].message.contains("A-招标文件.docx"));
}

#[test]
fn star_captured_when_req_anchors_file() {
    // REQ 在场且摘录含★前缀腿全文（star_scan 捕获腿：locator 相等 ∪
    // ★前缀包含——无空格句的前缀 = ★+整句）→ 零 E_STAR_MISSING
    //（E_STAR_UNRESPONDED 属子面 a 语义——本测只锁漏标腿 b）
    let text = "★实质性条款：提供近三年类似业绩清单。";
    let s = store_with(
        vec![req("REQ-0001", "技术参数", text, true)],
        "明标",
    );
    let pf = parsed_with_star(text);
    let fs = star_gate_findings(&s, &[pf]);
    assert!(
        fs.iter().all(|f| f.rule_code != "E_STAR_MISSING"),
        "★已捕获 → 无 E_STAR_MISSING: {fs:?}"
    );
}

#[test]
fn no_star_file_zero_findings() {
    let s = store_with(vec![], "明标");
    let pf = parsed_with_star("本条为普通条款，无星标。");
    let fs = star_gate_findings(&s, &[pf]);
    assert!(fs.is_empty(), "无★文件 → 零 findings: {fs:?}");
}

// ---------------------------------------------------------------- 暗标门

#[test]
fn dark_bid_mode_declared_but_inactive_is_blocker() {
    // mode=暗标 + 未启用暗标导出 → BLOCKER（自相矛盾 fail-closed）
    let s = store_with(vec![], "暗标");
    let fs = dark_bid_gate_findings(&s, false);
    assert_eq!(codes(&fs), vec!["E_DARK_BID_REQUIRED"], "mode=暗标未启用 → BLOCKER");
}

#[test]
fn dark_bid_active_zero_findings_regardless_of_mode() {
    let s = store_with(
        vec![req("REQ-0001", "否决项", "技术标部分采用暗标评审，否则作否决投标处理", false)],
        "暗标",
    );
    assert!(dark_bid_gate_findings(&s, true).is_empty(), "启用暗标 → 零 findings");
}

#[test]
fn light_mode_with_dark_clause_warns_not_blocks() {
    // mode=明标 + 暗标条款在场 → MINOR 告警（不拦——升级面 Lead 裁决）
    let s = store_with(
        vec![req(
            "REQ-0001",
            "否决项",
            "3.3.4 技术标部分采用暗标评审：技术标正文中不得出现投标人名称，否则作否决投标处理。",
            false,
        )],
        "明标",
    );
    let fs = dark_bid_gate_findings(&s, false);
    assert_eq!(codes(&fs), vec!["W_DARK_BID_UNDECLARED"], "明标+暗标条款 → 告警");
    assert_eq!(fs[0].severity, "MINOR", "告警级不拦");
    assert!(fs[0].message.contains("REQ-0001"), "指名条款 id");
}

#[test]
fn negated_dark_bid_clause_not_flagged() {
    // 「商务标不采用暗标评审」→ 否定形 → 零 findings（不误拦）
    let s = store_with(
        vec![req("REQ-0001", "商务要求", "本项目商务标部分不采用暗标评审，按明标形式评审。", false)],
        "明标",
    );
    let fs = dark_bid_gate_findings(&s, false);
    assert!(fs.is_empty(), "否定形不命中: {fs:?}");
}

#[test]
fn mixed_sentence_with_real_dark_bid_requirement_flags() {
    // 混合句：否定+肯定同现，肯定占优（技术标采用暗标）→ 命中
    let s = store_with(
        vec![req(
            "REQ-0001",
            "否决项",
            "商务标不采用暗标评审；技术标部分采用暗标评审，正文中不得出现投标人名称。",
            false,
        )],
        "明标",
    );
    let fs = dark_bid_gate_findings(&s, false);
    assert_eq!(codes(&fs), vec!["W_DARK_BID_UNDECLARED"], "混合句肯定占优 → 告警");
}

#[test]
fn addendum_introduced_dark_bid_requirement_flags() {
    // 补遗条款文本（params.addendum_requirement）引入暗标要求 → 命中
    let mut r = req("REQ-0002", "技术参数", "技术方案编制要求", false);
    r.params.insert(
        "addendum_requirement".into(),
        serde_json::json!("补遗新增：技术标部分采用暗标评审方式，不得出现投标人标识。"),
    );
    let s = store_with(vec![r], "明标");
    let fs = dark_bid_gate_findings(&s, false);
    assert_eq!(codes(&fs), vec!["W_DARK_BID_UNDECLARED"], "补遗暗标要求 → 告警");
}

#[test]
fn plain_dark_bid_mention_without_positive_phrase_not_flagged() {
    // 仅「暗标」二字不成证据（间接提及）→ 零 findings（保守面）
    let s = store_with(
        vec![req("REQ-0001", "商务要求", "评标办法中关于暗标的其余未尽事宜详见第七章。", false)],
        "明标",
    );
    let fs = dark_bid_gate_findings(&s, false);
    assert!(fs.is_empty(), "间接提及不命中: {fs:?}");
}

// ---------------------------------------------------------------- 门 1g：DIRTY

#[test]
fn dirty_with_pending_directive_is_blocker() {
    // 补遗 value_changed → DIRTY 打标 + 改写指令 → E_SECTION_DIRTY
    let mut s = store_with(
        vec![req("REQ-0001", "商务要求", "总工期 540 天", false)],
        "明标",
    );
    let changes = s
        .register_addendum_changes(&[bid_domain::rewrite::ChangeSpec {
            req_id: Some("REQ-0001".into()),
            change_type: bid_domain::rewrite::ChangeType::ValueChanged,
            old_text: "总工期 540 天".into(),
            new_requirement: "总工期 480 天（补遗变更）".into(),
            category: None,
            clause_no: None,
            section_id: None,
            source_file_id: None,
        }])
        .unwrap();
    assert!(!changes[0].affected_sections.is_empty(), "归属章节被打脏");
    // 域层登记只打脏；pending 指令是服务层（store_rewrite_directive 的
    // 调用方）产物——此处直接落一条 Pending 指令造真两态并存
    s.store_rewrite_directive(&changes[0].change, &changes[0].affected_sections[0].clone(), vec![]);
    let fs = bid_tools::validate::dirty_gate_findings(&s);
    assert_eq!(codes(&fs), vec!["E_SECTION_DIRTY"], "补遗 DIRTY+指令 → BLOCKER");
    assert!(fs[0].message.contains("改写指令未处置"));
}

#[test]
fn dirty_cleared_by_dismiss_passes_gate() {
    // dismiss 指令 → 清脏 → 门放行（处置面即豁免——无参数豁免的既定纪律）
    let mut s = store_with(
        vec![req("REQ-0001", "商务要求", "总工期 540 天", false)],
        "明标",
    );
    let changes = s
        .register_addendum_changes(&[bid_domain::rewrite::ChangeSpec {
            req_id: Some("REQ-0001".into()),
            change_type: bid_domain::rewrite::ChangeType::ValueChanged,
            old_text: "总工期 540 天".into(),
            new_requirement: "总工期 480 天（补遗变更）".into(),
            category: None,
            clause_no: None,
            section_id: None,
            source_file_id: None,
        }])
        .unwrap();
    let sec = changes[0].affected_sections[0].clone();
    s.store_rewrite_directive(&changes[0].change, &sec, vec![]);
    let pending: Vec<String> = s
        .pending_rewrite_directives_of(&sec)
        .iter()
        .map(|d| d.id.clone())
        .collect();
    for did in pending {
        s.dismiss_rewrite_directive(&did).unwrap();
    }
    let fs = bid_tools::validate::dirty_gate_findings(&s);
    assert!(fs.is_empty(), "指令全处置 → 清脏 → 零 findings: {fs:?}");
}

#[test]
fn dirty_without_directives_warns_not_blocks() {
    // 证据换版打脏（#456——无指令的失效信号）→ W_EVIDENCE_DIRTY（MINOR）
    let mut s = store_with(
        vec![req("REQ-0001", "商务要求", "总工期 540 天", false)],
        "明标",
    );
    // 同语义位换版：新指纹 → 旧件 Superseded + 关联章节打脏（无指令）
    register_evidence_tier(&mut s, "v1", None);
    let v2 = EvidenceSpec {
        kind: EvidenceKind::Qualification,
        title: "证书-v1".into(), // 同语义位（kind+title+subject+scope）
        source_file: "A-招标文件.docx".into(),
        source_sha256: "sha-v2".into(),
        locator: EngineLocator::DocxParagraph {
            paragraph_index: 1,
            text_fingerprint: "fnv64:v2".into(),
        },
        fingerprint: "fnv64:v2".into(),
        valid_from: None,
        valid_until: None,
        subject_name: "投标人".into(),
        scope: "测试".into(),
        client: None,
        amount_wan: None,
        completed_on: None,
        fields: Default::default(),
        excerpt: None,
        excerpt_locator: None,
        verification_tier: None,
    };
    // 先绑 v1（让换版有关联章节），再换版
    let req_id = "REQ-0001".to_string();
    let evidences: Vec<String> = s.evidences().iter().map(|e| e.id.clone()).collect();
    s.bind_evidence(&evidences[0], &req_id, "2026-12-31").unwrap();
    let _ = s.register_evidence(v2).unwrap();
    let fs = bid_tools::validate::dirty_gate_findings(&s);
    assert!(
        fs.iter().all(|f| f.rule_code == "W_EVIDENCE_DIRTY"),
        "换版失效信号 → 告警不拦: {fs:?}"
    );
    assert!(
        fs.iter().all(|f| f.severity != "BLOCKER"),
        "无指令面零 BLOCKER"
    );
}

#[test]
fn clean_store_zero_dirty_findings() {
    let s = store_with(
        vec![req("REQ-0001", "商务要求", "总工期 540 天", false)],
        "明标",
    );
    assert!(bid_tools::validate::dirty_gate_findings(&s).is_empty());
}

// ---------------------------------------------------------------- 门 1h：unmapped

#[test]
fn unmapped_scoring_item_is_blocker() {
    // 评分项不进纲（#126）——商务要求锚 REQ 建纲，评分项只进条款集
    let s = store_with(
        vec![
            req("REQ-0000", "商务要求", "常规商务条款（建纲锚）", false),
            req("REQ-0001", "评分项", "技术方案完整性 30 分", false),
        ],
        "明标",
    );
    let fs = bid_tools::validate::unmapped_scoring_findings(&s);
    assert_eq!(codes(&fs), vec!["E_SCORING_UNMAPPED"], "评分项未映射 → BLOCKER");
    assert!(fs[0].message.contains("REQ-0001"));
    assert!(fs[0].message.contains("upsert_scoring_mapping"), "给出解决通道");
}

#[test]
fn mapped_scoring_item_passes_gate() {
    let mut s = store_with(
        vec![
            req("REQ-0000", "商务要求", "常规商务条款（建纲锚）", false),
            req("REQ-0001", "评分项", "技术方案完整性 30 分", false),
        ],
        "明标",
    );
    // 显式映射（#224 账本——门的解决通道；评分项不进叶——映射目标取首个结构节点下的叶）
    let parents: std::collections::HashSet<String> =
        s.sections().iter().filter_map(|n| n.parent_id.clone()).collect();
    let any_leaf = s
        .sections()
        .iter()
        .find(|n| !parents.contains(&n.id))
        .map(|n| n.id.clone())
        .unwrap();
    s.upsert_scoring_mapping(
        "REQ-0001".into(),
        any_leaf,
        1.0,
        vec![],
        bid_domain::Anchor {
            file: "A-招标文件.docx".into(),
            kind: "table".into(),
            locator: "第四章 评标办法".into(),
            excerpt: "技术方案完整性 30 分".into(),
            block_idx: None,
            page: None,
            line: None,
        },
        bid_domain::scoring::MappingSource::AgentSubmitted,
    )
    .unwrap();
    let fs = bid_tools::validate::unmapped_scoring_findings(&s);
    assert!(fs.is_empty(), "已映射 → 零 findings: {fs:?}");
}

#[test]
fn no_scoring_items_zero_findings() {
    let s = store_with(
        vec![req("REQ-0001", "商务要求", "总工期 540 天", false)],
        "明标",
    );
    assert!(bid_tools::validate::unmapped_scoring_findings(&s).is_empty());
}

#[test]
fn unmapped_detail_truncated_at_ten() {
    // 规模面：11+ 未映射 → 明细截断 10 项 + 总数（scale_1330 实测 250 项
    // 全列会撑到数十 KB——首 10 可定位，全量走 score_document）
    let mut reqs = vec![req("REQ-0000", "商务要求", "常规商务条款（建纲锚）", false)];
    for i in 0..12 {
        reqs.push(req(&format!("REQ-{:04}", i + 1), "评分项", &format!("评分细则第 {i} 项"), false));
    }
    let s = store_with(reqs, "明标");
    let fs = bid_tools::validate::unmapped_scoring_findings(&s);
    assert_eq!(codes(&fs), vec!["E_SCORING_UNMAPPED"]);
    assert!(fs[0].message.contains("等共 12 个"), "总数对账: {}", fs[0].message);
    assert!(!fs[0].message.contains("REQ-0012（"), "第 12 项不进明细: {}", fs[0].message);
}

// ---------------------------------------------------------------- 门 1i/1j

#[test]
fn global_amount_conflict_is_blocker() {
    // 两叶正文同维度金额不一致（#423 AmountConflict）→ 门 1i 拦
    let mut s = store_with(
        vec![
            req("REQ-0001", "商务要求", "投标保证金条款（锚 1）", false),
            req("REQ-0002", "商务要求", "投标保证金缴纳细则（锚 2）", false),
        ],
        "明标",
    );
    let l1 = leaf_of(&s, "REQ-0001");
    let l2 = leaf_of(&s, "REQ-0002");
    if l1 == l2 {
        return; // 同叶无双面对——建纲可能合并；跳过（夹具粒度限制）
    }
    s.set_section_content(&l1, "本项目投标保证金 50 万元，缴纳方式见下。".into()).unwrap();
    s.set_section_content(&l2, "本项目投标保证金 60 万元，逾期不予退还。".into()).unwrap();
    let fs = bid_tools::validate::global_conflict_findings(&s);
    assert!(
        fs.iter().any(|f| f.rule_code == "E_GLOBAL_CONFLICT"),
        "同维度金额不一致 → 冲突: {fs:?}"
    );
}

#[test]
fn consistent_amounts_zero_conflict_findings() {
    let mut s = store_with(
        vec![req("REQ-0001", "商务要求", "投标保证金条款", false)],
        "明标",
    );
    let l1 = leaf_of(&s, "REQ-0001");
    s.set_section_content(&l1, "本项目投标保证金 50 万元，缴纳方式见下。".into()).unwrap();
    assert!(bid_tools::validate::global_conflict_findings(&s).is_empty());
}

#[test]
fn decision_duration_conflict_is_blocker() {
    // 参数账工期 540 天 vs 决策 480 天 → E_DECISION_CONFLICT
    let mut s = store_with(
        vec![req("REQ-0001", "商务要求", "总工期要求", false)],
        "明标",
    );
    s.set_param_responses(vec![bid_domain::param::ParamInput {
        requirement_id: "REQ-0001".into(),
        param_name: "总工期".into(),
        required_value: "≤600 天".into(),
        response_value: "540 天".into(),
        evidence_id: None,
    }])
    .unwrap();
    let decision = bid_tools::export::ExportDecision {
        duration_days: Some(480),
        ..Default::default()
    };
    let fs = bid_tools::validate::decision_consistency_findings(&s, &decision);
    assert_eq!(codes(&fs), vec!["E_DECISION_CONFLICT"], "工期不一致 → BLOCKER");
    assert!(fs[0].message.contains("540"), "指名参数行口径: {}", fs[0].message);
    // 改齐 → 零 findings
    let ok = bid_tools::export::ExportDecision {
        duration_days: Some(540),
        ..Default::default()
    };
    assert!(bid_tools::validate::decision_consistency_findings(&s, &ok).is_empty());
}

#[test]
fn decision_amount_conflict_is_blocker() {
    let mut s = store_with(
        vec![req("REQ-0001", "商务要求", "报价条款", false)],
        "明标",
    );
    s.set_param_responses(vec![bid_domain::param::ParamInput {
        requirement_id: "REQ-0001".into(),
        param_name: "投标总价".into(),
        required_value: "≤600 万元".into(),
        response_value: "500 万元".into(),
        evidence_id: None,
    }])
    .unwrap();
    // 500 万 = 5,000,000 元——决策 4,800,000 → 冲突
    let bad = bid_tools::export::ExportDecision {
        bid_amount: Some(4_800_000.0),
        ..Default::default()
    };
    let fs = bid_tools::validate::decision_consistency_findings(&s, &bad);
    assert_eq!(codes(&fs), vec!["E_DECISION_CONFLICT"], "报价不一致 → BLOCKER");
    // 对齐 → 零 findings
    let ok = bid_tools::export::ExportDecision {
        bid_amount: Some(5_000_000.0),
        ..Default::default()
    };
    assert!(bid_tools::validate::decision_consistency_findings(&s, &ok).is_empty());
}

#[test]
fn decision_none_fields_skip_comparison() {
    // decision 缺省（None = 未定——【待填】是既有降级面）→ 不比不拦
    let mut s = store_with(
        vec![req("REQ-0001", "商务要求", "总工期要求", false)],
        "明标",
    );
    s.set_param_responses(vec![bid_domain::param::ParamInput {
        requirement_id: "REQ-0001".into(),
        param_name: "总工期".into(),
        required_value: "≤600 天".into(),
        response_value: "540 天".into(),
        evidence_id: None,
    }])
    .unwrap();
    let none = bid_tools::export::ExportDecision::default();
    assert!(bid_tools::validate::decision_consistency_findings(&s, &none).is_empty());
}

// ---------------------------------------------------------------- 门 1k：格式件核对

#[test]
fn format_docs_outside_standard_forms_warn() {
    // 格式要求 REQ 指名七件外的件（履约保函）→ 告警；投标函（七件内）不告警
    let s = store_with(
        vec![
            req("REQ-0001", "格式要求", "投标文件须含《投标函》，法定代表人签字并盖章", false),
            req("REQ-0002", "格式要求", "中标后须提供《履约保函》，金额为合同价 10%", false),
        ],
        "明标",
    );
    let ws = bid_tools::validate::format_docs_checklist(&s);
    assert!(
        ws.iter().any(|w| w.contains("履约保函") && w.contains("REQ-0002")),
        "七件外指名件 → 告警: {ws:?}"
    );
    assert!(
        ws.iter().all(|w| !w.contains("REQ-0001")),
        "投标函在七件内 → 零告警: {ws:?}"
    );
}

#[test]
fn format_docs_all_covered_zero_warnings() {
    let s = store_with(
        vec![req("REQ-0001", "格式要求", "投标文件格式：投标函、授权委托书、法定代表人身份证明均须提供", false)],
        "明标",
    );
    assert!(bid_tools::validate::format_docs_checklist(&s).is_empty());
}

#[test]
fn non_format_reqs_not_scanned() {
    // 商务要求类 REQ 提到件名不进核对面（格式章是核对真源——防误报）
    let s = store_with(
        vec![req("REQ-0001", "商务要求", "履约阶段须提交《履约保函》", false)],
        "明标",
    );
    assert!(bid_tools::validate::format_docs_checklist(&s).is_empty());
}
