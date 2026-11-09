//! bid.rs —— 标书数据面 IPC（#313 批 A：`bid.state` / `bid.outline`；
//! 批 B：`bid.matrix`；批 C：`bid.quality` / `bid.score`；批 D：`bid.coverage`）。
//!
//! 架构（原认领计划 2026-11-07T02:34Z 的批次切片，issue #313）：
//!   * [`state`]  —— 经 `bid_mcp::dispatch_with` 走真实工具面
//!     （`get_bid_project_state`），外加项目元信息与快速统计
//!     （DomainStore 只读直算）；
//!   * [`outline`] —— DomainStore 直读章节树（MCP 工具面无此只读视图——
//!     认领计划明示的直读面）；
//!   * [`matrix`] —— 经 `bid_mcp::dispatch_with` 走真实工具面
//!     （`get_compliance_matrix`，#313 批 B），壳内循工具的 cursor 分页
//!     聚合全量后一次返回（行形状原样透传）；
//!   * [`quality`] / [`score`]（批 C）—— 同样经 `dispatch_with` 走真实
//!     工具面（`check_bid_quality` / `score_document`），工具输出原样放
//!     `quality` / `score` 键；工具面 `E_STATE`（项目未到 MatrixReady+ /
//!     无章节树）透传为壳侧 `state` 错误码——UI 按码分支成「尚未开放」
//!     引导卡而非故障横幅。
//!   * [`coverage`] —— 经 `bid_mcp::dispatch_with` 走真实工具面
//!     （`get_coverage_report`，#313 批 D），外加壳侧三态分账汇总与
//!     ★条款覆盖逐文件聚合（`get_star_coverage`，#285）。

//!
//! 服务缓存（`Ctx.bid`，进程内单份）：按「工作区根 + db.json 指纹
//! （mtime+size）」绑定——切换工作区（workspace.open）或外部进程
//! （bid-mcp-stdio / Agent）改写 db.json 后，下一条命令自动重开。
//! **无 db.json → 干净的 `not_found`**：不经 `BidService::open`（它会在
//! 任意目录里凭空创建 `.mang/approval.key`——查看状态不应留副作用）。
//!
//! 批 C（bid.quality / bid.score / 自评面板）与批 D（bid.coverage / 覆盖报告
//! 面板）均已交付，同样经 dispatch_with 走真实工具面。
//!
//! 批 C 范围纪律：`bid.score` 不透传价格推演入参（bid_price / method
//! 等）——报价试算走既有 `score_price` 工具；未报价时 `score.price`
//! 为 null（诚实显示，不伪缺 0）。

use std::collections::HashMap;
use std::path::PathBuf;
use std::sync::{Mutex, MutexGuard};

use serde_json::{json, Value};

use crate::ipc::{self, Args, IpcError};
use crate::paths::{self, Workspace};

use bid_domain::outline::{OutlineNode, SectionStatus, CHARS_PER_PAGE};

/// 服务缓存条目（字段仅本模块可见；ipc.rs 只持有 `Mutex<Option<CachedService>>`）。
pub struct CachedService {
    root: PathBuf,
    db_mtime_ms: u64,
    db_len: u64,
    svc: bid_tools::service::BidService,
}

/// StoreIoError → IpcError（坏 db.json 响亮，不静默）。
fn map_store_err(e: bid_tools::store_io::StoreIoError) -> IpcError {
    match e {
        bid_tools::store_io::StoreIoError::Corrupt(what) => {
            IpcError::bad_json(format!("db.json 损坏，拒绝加载：{what}"))
        }
        other => IpcError::io(format!("打开标书工作区失败：{other}")),
    }
}

/// ToolError（bid-mcp 工具面）→ IpcError（E_NOTFOUND → not_found 是「无项目」
/// 主路径；E_STATE → `state` 是「项目未到工具状态窗」主路径——#313 批 C/D
/// 起 UI 需要区分「尚未开放」与「故障」，壳不复制状态窗，code 即单一真源）。
fn map_tool_err(e: bid_mcp::ToolError) -> IpcError {
    match e {
        bid_mcp::ToolError::ENotFound { what } => IpcError::not_found(what),
        bid_mcp::ToolError::EState { what } => IpcError::state(what),
        bid_mcp::ToolError::EUnprocessable { what } => IpcError::bad_args(what),
        bid_mcp::ToolError::EState { what } => IpcError::new("state", what),
        other => IpcError::io(format!("工具面应答失败：{other}")),
    }
}

/// ToolError（bid-domain 只读面）→ IpcError。与工具面是两个类型
///（store.project() 返回域层 ToolError）——分开映射，不做 trait 双关。
/// 域层 ToolError 无 Display（只有 code()），用 Debug 面。
fn map_domain_err(e: bid_domain::ToolError) -> IpcError {
    match e {
        bid_domain::ToolError::ENotFound { what } => IpcError::not_found(what),
        other => IpcError::io(format!("域层读取失败：{}（{other:?}）", other.code())),
    }
}

/// 取当前工作区的服务态（缓存命中直接用；根变了 / db.json 变了 → 重开）。
/// 无 db.json → not_found（且不落任何副作用）。
fn ensure_locked<'a>(
    cache: &'a mut Option<CachedService>,
    ws: &Workspace,
) -> Result<&'a mut bid_tools::service::BidService, IpcError> {
    let root = ws.root_canonical().to_path_buf();
    let db = root.join("db.json");
    let meta = std::fs::metadata(&db).map_err(|e| {
        if e.kind() == std::io::ErrorKind::NotFound {
            IpcError::not_found(format!(
                "当前工作区没有 db.json（尚未创建标书项目）：{}",
                ws.root_display()
            ))
        } else {
            IpcError::io(format!("读取 db.json 元信息失败：{e}"))
        }
    })?;
    let (mtime_ms, db_len) = (ipc::mtime_ms(&meta), meta.len());
    let fresh = match cache {
        Some(c) => c.root == root && c.db_mtime_ms == mtime_ms && c.db_len == db_len,
        None => false,
    };
    if !fresh {
        let svc =
            bid_tools::service::BidService::open(&root).map_err(map_store_err)?;
        *cache = Some(CachedService { root, db_mtime_ms: mtime_ms, db_len, svc });
    }
    Ok(&mut cache.as_mut().expect("上面刚放入").svc)
}

// ---------------------------------------------------------------- 统计共用面

/// children 映射（parent_id → 子节点下标表）。sections 上限数百，O(N) 建表。
fn children_map(sections: &[OutlineNode]) -> HashMap<String, Vec<usize>> {
    let mut m: HashMap<String, Vec<usize>> = HashMap::new();
    for (i, n) in sections.iter().enumerate() {
        if let Some(p) = &n.parent_id {
            m.entry(p.clone()).or_default().push(i);
        }
    }
    m
}

/// 每节实际字数（叶 = content 字符数；结构节点 = 后代叶之和——与
/// target_chars「父 = 子配额和」同一口径，进度条才可比）。
fn actual_chars_map(sections: &[OutlineNode]) -> HashMap<String, u64> {
    let children = children_map(sections);
    let mut out: HashMap<String, u64> = HashMap::with_capacity(sections.len());
    fn fill(
        idx: usize,
        sections: &[OutlineNode],
        children: &HashMap<String, Vec<usize>>,
        out: &mut HashMap<String, u64>,
    ) -> u64 {
        // 深度 ≤ 4（outline 规格 level 1..=4），递归栈安全
        let n = &sections[idx];
        let total = match children.get(&n.id) {
            Some(kids) => kids
                .iter()
                .map(|&k| fill(k, sections, children, out))
                .sum(),
            None => n.content.as_ref().map(|c| c.chars().count() as u64).unwrap_or(0),
        };
        out.insert(n.id.clone(), total);
        total
    }
    for (i, n) in sections.iter().enumerate() {
        if n.parent_id.is_none() {
            fill(i, sections, &children, &mut out);
        }
    }
    // 防御：parent_id 挂到不存在节点的孤儿（validate_outline 会拒，但读面
    // 不赌写入面永远干净）——漏算不如直算
    for n in sections {
        if !out.contains_key(&n.id) {
            let v = n.content.as_ref().map(|c| c.chars().count() as u64).unwrap_or(0);
            out.insert(n.id.clone(), v);
        }
    }
    out
}

/// 章节统计（bid.state 的 quick_stats 与 bid.outline 的 stats 同源——
/// 两处口径永远一致，UI 不做二次猜）。
fn section_stats(sections: &[OutlineNode]) -> Value {
    let children = children_map(sections);
    let actual = actual_chars_map(sections);
    let mut leaf = 0u64;
    let mut drafted = 0u64;
    let mut accepted = 0u64;
    let mut failed = 0u64;
    let mut dirty = 0u64;
    let mut target_total = 0u64;
    let mut actual_total = 0u64;
    for n in sections {
        let is_leaf = !children.contains_key(&n.id);
        if is_leaf {
            leaf += 1;
            target_total += u64::from(n.target_chars);
            actual_total += actual.get(&n.id).copied().unwrap_or(0);
        }
        if n.status.is_drafted() {
            drafted += 1;
        }
        if n.status == SectionStatus::Accepted {
            accepted += 1;
        }
        if n.status == SectionStatus::Failed {
            failed += 1;
        }
        if n.dirty {
            dirty += 1;
        }
    }
    let pages = if CHARS_PER_PAGE > 0 {
        actual_total.div_ceil(u64::from(CHARS_PER_PAGE))
    } else {
        0
    };
    json!({
        "sections": sections.len(),
        "sections_leaf": leaf,
        "sections_drafted": drafted,
        "sections_accepted": accepted,
        "sections_failed": failed,
        "sections_dirty": dirty,
        "target_total_chars": target_total,
        "actual_total_chars": actual_total,
        "pages_estimate": pages,
    })
}

// ---------------------------------------------------------------- 命令

/// `bid.state` —— 项目状态 / 门审 / 快速统计（只读）。
///
/// 主体经 `bid_mcp::dispatch_with(get_bid_project_state)` 走真实工具面
/// （与 bid-mcp-stdio 同一套裁决代码——方案 A 直链），工具输出原样放
/// `state` 键；`project` / `quick_stats` 是 DomainStore 只读直算的补充面。
pub fn state(
    ws: &Workspace,
    cache: &Mutex<Option<CachedService>>,
    _a: &Args,
) -> Result<Value, IpcError> {
    let mut guard = lock(cache);
    let svc = ensure_locked(&mut guard, ws)?;
    let reply = bid_mcp::dispatch_with(
        svc,
        bid_mcp::ToolCall {
            tool: "get_bid_project_state".to_string(),
            args: Value::Null,
        },
    );
    let tool_state = match reply {
        bid_mcp::ToolReply::Ok(out) => out.result,
        bid_mcp::ToolReply::Err { error, .. } => return Err(map_tool_err(error)),
    };
    let store = svc.store();
    let project = store.project().map_err(map_domain_err)?;
    // quick_stats：章节面（section_stats）+ 条款/证据计数，同源同口径
    let mut quick = section_stats(store.sections());
    let qo = quick
        .as_object_mut()
        .expect("section_stats 恒为对象");
    qo.insert("requirements".into(), json!(store.requirements().len()));
    qo.insert("evidence".into(), json!(store.evidences().len()));
    qo.insert(
        "evidence_bindings".into(),
        json!(store.evidence_bindings().len()),
    );
    Ok(json!({
        "present": true,
        "workspace": ws.root_display(),
        "db": paths::display(&ws.root_canonical().join("db.json")),
        "project": {
            "id": project.id,
            "name": project.name,
            "code": project.code,
            "mode": project.mode,
            "status": project.status.as_str(),
        },
        "state": tool_state,
        "quick_stats": quick,
    }))
}

/// `bid.outline` —— 章节树（只读，MCP 无此工具——DomainStore 直读）。
///
/// 节点按 `order` 升序（文档序）；`actual_chars` 叶 = 正文字符数、
/// 结构节点 = 后代叶之和；`chapter_file`（相对工作区、`/` 分隔）在
/// `chapters/{id}.json` 真实存在时才给——UI 用它 fs.read 跳转详情。
pub fn outline(
    ws: &Workspace,
    cache: &Mutex<Option<CachedService>>,
    _a: &Args,
) -> Result<Value, IpcError> {
    let mut guard = lock(cache);
    let svc = ensure_locked(&mut guard, ws)?;
    let store = svc.store();
    let project = store.project().map_err(map_domain_err)?;
    let sections = store.sections();
    let children = children_map(sections);
    let actual = actual_chars_map(sections);
    let chapters_dir = ws.root_canonical().join("chapters");
    let mut ordered: Vec<&OutlineNode> = sections.iter().collect();
    ordered.sort_by_key(|n| n.order);
    let nodes: Vec<Value> = ordered
        .iter()
        .map(|n| {
            let is_leaf = !children.contains_key(&n.id);
            let chapter_file = if is_leaf && chapters_dir.join(format!("{}.json", n.id)).is_file() {
                Value::String(format!("chapters/{}.json", n.id))
            } else {
                Value::Null
            };
            json!({
                "id": n.id,
                "parent_id": n.parent_id.clone(),
                "title": n.title,
                "level": n.level,
                "order": n.order,
                "status": n.status.as_str(),
                "dirty": n.dirty,
                "target_chars": n.target_chars,
                "actual_chars": actual.get(&n.id).copied().unwrap_or(0),
                "req_count": n.requirement_ids.len(),
                "is_leaf": is_leaf,
                "has_content": n.content.is_some(),
                "content_attempt": n.content_attempt,
                "chapter_file": chapter_file,
            })
        })
        .collect();
    Ok(json!({
        "present": true,
        "workspace": ws.root_display(),
        "project": {
            "id": project.id,
            "name": project.name,
            "status": project.status.as_str(),
        },
        "nodes": nodes,
        "stats": section_stats(sections),
    }))
}

/// `bid.matrix` —— 合规矩阵全量（只读，#313 批 B）。
///
/// 主体经 `bid_mcp::dispatch_with(get_compliance_matrix)` 走真实工具面
/// （与 bid-mcp-stdio 同一套裁决代码——方案 A 直链）。工具面按 S-4 游标
/// 分页（limit ≤1000、游标绑过滤器指纹与数据版本 #406/C-14）——本壳是
/// 同进程调用方，循 `next_cursor` 把全量页聚合后**一次返回**，行形状
/// 原样透传不二次加工；UI 面的 blocking 筛选 / 状态与类别筛选 / 分页 /
/// 导出都在全量行上做，徽章计数与表格才同一真源。聚合护栏 200 页
/// （200k 行——真实量级 12k；超限响亮拒绝，不静默截断）。
///
/// `summary.by_status` 五态计数、`blocking` / `mandatory` / `substantive` /
/// `evidence_missing` 计数在聚合行上现算；`star_summary`（★实质性条款
/// 统计）与 `warnings` 取工具面输出原样。无 db.json → 干净 `not_found`，
/// 服务缓存语义同 [`state`] / [`outline`]。
pub fn matrix(
    ws: &Workspace,
    cache: &Mutex<Option<CachedService>>,
    _a: &Args,
) -> Result<Value, IpcError> {
    let mut guard = lock(cache);
    let svc = ensure_locked(&mut guard, ws)?;
    // 项目元信息先取（owned）——后面的工具循环要 &mut svc
    let (project_id, project_name, project_status) = {
        let p = svc.store().project().map_err(map_domain_err)?;
        (p.id.clone(), p.name.clone(), p.status.as_str().to_string())
    };

    const PAGE_LIMIT: u64 = 1000; // 工具面契约上限（cursor.rs LIMIT_MAX）
    const PAGE_GUARD: u32 = 200; // 聚合护栏：200 × 1000 行
    let mut rows: Vec<Value> = Vec::new();
    let mut total = 0u64;
    let mut star_summary = Value::Null;
    let mut warnings: Vec<Value> = Vec::new();
    let mut project_version = 0u64;
    let mut pages = 0u32;
    let mut cursor: Option<String> = None;
    loop {
        let mut args = json!({ "project_id": project_id, "limit": PAGE_LIMIT });
        if let Some(c) = cursor.as_deref() {
            args["cursor"] = json!(c);
        }
        let reply = bid_mcp::dispatch_with(
            svc,
            bid_mcp::ToolCall {
                tool: "get_compliance_matrix".to_string(),
                args,
            },
        );
        let out = match reply {
            bid_mcp::ToolReply::Ok(out) => out.result,
            bid_mcp::ToolReply::Err { error, .. } => return Err(map_tool_err(error)),
        };
        pages += 1;
        if let Some(v) = out.get("rows").and_then(|r| r.as_array()) {
            rows.extend(v.iter().cloned());
        }
        // 末页为准（无过滤时各页同值）；条件赋值——不用哑初值据位
        if let Some(t) = out.get("total").and_then(|t| t.as_u64()) {
            total = t;
        }
        if let Some(s) = out.get("star_summary") {
            if !s.is_null() {
                star_summary = s.clone();
            }
        }
        if let Some(w) = out.get("warnings").and_then(|w| w.as_array()) {
            warnings = w.clone();
        }
        if let Some(v) = out.get("project_version").and_then(|v| v.as_u64()) {
            project_version = v;
        }
        match out.get("next_cursor").and_then(|c| c.as_str()) {
            Some(nc) if !nc.is_empty() => cursor = Some(nc.to_string()),
            _ => break,
        }
        if pages >= PAGE_GUARD {
            return Err(IpcError::io(format!(
                "合规矩阵聚合超过护栏（{PAGE_GUARD} 页 × {PAGE_LIMIT} 行）——\
                 拒绝静默截断，请上报数据规模"
            )));
        }
    }

    // 统计摘要：五态恒在（0 兜底——UI 徽章不赌键在场）；blocking/mandatory/
    // substantive/evidence_missing 与行字段同一判定面（工具面输出，不另写
    // 一套字面量）。
    let mut status_counts: HashMap<&str, u64> = HashMap::new();
    let (mut blocking, mut mandatory, mut substantive, mut evidence_missing) =
        (0u64, 0u64, 0u64, 0u64);
    for r in &rows {
        let st = r.get("status").and_then(|s| s.as_str()).unwrap_or("");
        *status_counts.entry(st).or_insert(0) += 1;
        if r.get("blocking").and_then(|b| b.as_bool()) == Some(true) {
            blocking += 1;
        }
        if r.get("requirement")
            .and_then(|q| q.get("mandatory"))
            .and_then(|b| b.as_bool())
            == Some(true)
        {
            mandatory += 1;
        }
        if r.get("substantive").and_then(|b| b.as_bool()) == Some(true) {
            substantive += 1;
        }
        if r.get("evidence_missing").and_then(|b| b.as_bool()) == Some(true) {
            evidence_missing += 1;
        }
    }
    let mut by_status = serde_json::Map::new();
    for st in bid_domain::matrix::ResponseStatus::ALL {
        by_status.insert(
            st.as_str().to_string(),
            json!(status_counts.get(st.as_str()).copied().unwrap_or(0)),
        );
    }

    Ok(json!({
        "present": true,
        "workspace": ws.root_display(),
        "project": {
            "id": project_id,
            "name": project_name,
            "status": project_status,
        },
        "rows": rows,
        "total": total,
        "summary": {
            "by_status": Value::Object(by_status),
            "blocking": blocking,
            "mandatory": mandatory,
            "substantive": substantive,
            "evidence_missing": evidence_missing,
        },
        "star_summary": star_summary,
        "warnings": warnings,
        "project_version": project_version,
        "fetched_pages": pages,
    }))
}


/// `bid.quality` —— 质量覆盖度检查（只读；#313 批 C）。
///
/// 主体经 `bid_mcp::dispatch_with(check_bid_quality)` 走真实工具面
/// （与 bid-mcp-stdio 同源裁决），工具输出原样放 `quality` 键——
/// summary（起草/失败/未覆盖条款/带外/无锚/查重/字数偏离）、
/// needs_human、submission_readiness（#241 两分账：导出可过而提交
/// 未就绪是合法状态）、sections 逐章明细、global_conflicts（#423
/// 金额/工期/术语/承诺跨章冲突）、negative_deviations（A-07 负偏离）、
/// artifact（报告落盘位置）与 warnings。
///
/// 拒绝面：无 db.json → `not_found`；项目未到 MatrixReady+（或无章节
/// 树）→ `state`（工具面 E_STATE 原文透传，如
/// 「REQUIREMENTS_EXTRACTED 态无章节树——先建纲再查质量」）。
pub fn quality(
    ws: &Workspace,
    cache: &Mutex<Option<CachedService>>,
    _a: &Args,
) -> Result<Value, IpcError> {
    let mut guard = lock(cache);
    let svc = ensure_locked(&mut guard, ws)?;
    let meta = project_meta(svc)?;
    let reply = bid_mcp::dispatch_with(
        svc,
        bid_mcp::ToolCall {
            tool: "check_bid_quality".to_string(),
            args: json!({ "project_id": meta.0 }),
        },
    );
    let tool_out = match reply {
        bid_mcp::ToolReply::Ok(out) => out.result,
        bid_mcp::ToolReply::Err { error, .. } => return Err(map_tool_err(error)),
    };
    Ok(json!({
        "present": true,
        "workspace": ws.root_display(),
        "project": meta.1,
        "quality": tool_out,
    }))
}

/// `bid.score` —— 全文档规则自评（只读；#313 批 C）。
///
/// 主体经 `bid_mcp::dispatch_with(score_document)` 走真实工具面，
/// 工具输出原样放 `score` 键——`diagnostic_only`/`result_kind`
/// （#186 语义降级：规则诊断非评标模拟——UI 必须原样展示）、
/// technical/commercial/price/total/target/gap、by_item 逐项明细
/// （estimated/tier/coverage/contributions/rule_checkpoints）、
/// mappings（#224 双向追溯）与 unmapped_scoring_items。
///
/// 价格面：本命令不带价格推演入参（范围纪律见模块头）——未报价时
/// `score.price` 为 null，UI 显示「价格分不计」。
///
/// 拒绝面与 `bid.quality` 同：`not_found` / `state`。
pub fn score(
    ws: &Workspace,
    cache: &Mutex<Option<CachedService>>,
    _a: &Args,
) -> Result<Value, IpcError> {
    let mut guard = lock(cache);
    let svc = ensure_locked(&mut guard, ws)?;
    let meta = project_meta(svc)?;
    let reply = bid_mcp::dispatch_with(
        svc,
        bid_mcp::ToolCall {
            tool: "score_document".to_string(),
            args: json!({ "project_id": meta.0 }),
        },
    );
    let tool_out = match reply {
        bid_mcp::ToolReply::Ok(out) => out.result,
        bid_mcp::ToolReply::Err { error, .. } => return Err(map_tool_err(error)),
    };
    Ok(json!({
        "present": true,
        "workspace": ws.root_display(),
        "project": meta.1,
        "score": tool_out,
    }))
}

// ---------------------------------------------------------------- #603 批 A：治理面（人工决策驾驶舱）

/// 五门读面元数据（展示序 = 三主门门序 → 两补遗门）。`note` 是门语义的
/// 一句话口径（UI 副标题）；过门**裁决**（状态窗/门序/幂等）零重实现——
/// 全在域层 record_review，本表只驱动读面展示。
const GATE_META: [(bid_domain::review::Gate, &str, &str); 5] = [
    (
        bid_domain::review::Gate::MatrixApproval,
        "矩阵定稿门",
        "门序第一：条款响应矩阵定稿（MATRIX_READY+ 可过）",
    ),
    (
        bid_domain::review::Gate::OutlineApproval,
        "大纲定稿门",
        "门序第二：章节树定稿（前置：矩阵门已过）",
    ),
    (
        bid_domain::review::Gate::PreExportConfirm,
        "导出前确认门",
        "门序第三：导出前置确认（前置：前两门均过）",
    ),
    (
        bid_domain::review::Gate::AddendumWaiver,
        "补遗逐件确认门",
        "L3 人工出口（#131/#379——逐件路径不再写本门）",
    ),
    (
        bid_domain::review::Gate::NoAddendumConfirmed,
        "无补遗全局确认门",
        "#379 拆门——「本项目无补遗」全局显式确认",
    ),
];

/// 写面门名解析——与工具面 parse_gate 同一合法值集（三主门 + addendum_
/// waiver；no_addendum_confirmed 走 record_addendum_waiver 的
/// confirm_no_addendum 路径，#603 批 C 接线）。壳侧只做入参早拒，
/// 语义裁决仍全在工具/域层。
fn gate_from_str(s: &str) -> Result<bid_domain::review::Gate, IpcError> {
    use bid_domain::review::Gate;
    match s {
        "matrix_approval" => Ok(Gate::MatrixApproval),
        "outline_approval" => Ok(Gate::OutlineApproval),
        "pre_export_confirm" => Ok(Gate::PreExportConfirm),
        "addendum_waiver" => Ok(Gate::AddendumWaiver),
        other => Err(IpcError::bad_args(format!(
            "gate 非法：{other}（合法值：matrix_approval|outline_approval|pre_export_confirm|addendum_waiver）"
        ))),
    }
}

/// GatePassRecord → json（读面形状与工具面 agent_waivers_json 同键同序——
/// 单一真源防两处漂移；latest_pass 复用同一序列化）。
fn gate_pass_json(p: Option<&bid_domain::review::GatePassRecord>) -> Value {
    match p {
        None => Value::Null,
        Some(p) => json!({
            "gate": p.gate.as_str(),
            "actor": p.actor_id,
            "actor_type": p.actor_type.as_str(),
            "method": p.method,
            "human_confirmed": p.human_confirmed,
            "at": p.at,
            "reason": p.reason,
        }),
    }
}

/// `bid.gates` —— 审核门台账（只读；#603 批 A）。
///
/// DomainStore 直读（`bid.outline` 先例——MCP 工具面无此整面视图）：
/// 五门 approved 状态（`gate_approved` 同源）、每门最新过门记录
/// （`latest_gate_pass`——追认后最新条翻 human 的判据位）、agent 豁免
/// 清单（`agent_gate_passes`——human_confirmed=false 的门，导出警告与
/// 追认清单素材）、`human_review_complete`（空账本或全 human → true）、
/// reviews 裁决历史（倒序——REV/FND/RT 派生的审计面）。
///
/// 读面**无状态窗**：任何项目阶段都可看门态（早期态「三门都未过」本身
/// 就是有效信息）；写面（[`gate_pass`]）才有域层状态窗裁决。
pub fn gates(
    ws: &Workspace,
    cache: &Mutex<Option<CachedService>>,
    _a: &Args,
) -> Result<Value, IpcError> {
    let mut guard = lock(cache);
    let svc = ensure_locked(&mut guard, ws)?;
    let store = svc.store();
    let project = store.project().map_err(map_domain_err)?;
    let gates: Vec<Value> = GATE_META
        .iter()
        .map(|(g, title, note)| {
            json!({
                "gate": g.as_str(),
                "title": title,
                "note": note,
                "approved": store.gate_approved(*g),
                "latest_pass": gate_pass_json(store.latest_gate_pass(*g)),
            })
        })
        .collect();
    let agent_waivers: Vec<Value> = store
        .agent_gate_passes()
        .iter()
        .map(|p| gate_pass_json(Some(*p)))
        .collect();
    let reviews: Vec<Value> = store
        .reviews()
        .iter()
        .rev()
        .map(|rv| {
            json!({
                "id": rv.id,
                "gate": rv.gate.as_str(),
                "decision": rv.decision.as_str(),
                "reviewer": rv.reviewer,
                "actor": rv.principal.as_ref().map(|p| json!({
                    "actor_id": p.actor_id,
                    "actor_type": p.actor_type.as_str(),
                    "authentication_method": p.authentication_method,
                })),
                "findings": rv.findings,
                "at": rv.at,
                "reviewed_content_digest": rv.reviewed_content_digest,
            })
        })
        .collect();
    Ok(json!({
        "present": true,
        "workspace": ws.root_display(),
        "project": {
            "id": project.id,
            "name": project.name,
            "status": project.status.as_str(),
        },
        "gates": gates,
        "human_review_complete": store.human_review_complete(),
        "agent_waivers": agent_waivers,
        "reviews": reviews,
    }))
}

/// `bid.gate_pass` —— 人工过门（写面；#603 批 A——治理面写面首发）。
///
/// 流程（#182 宿主签发面——**不进 MCP 工具表，Agent 拿不到**）：
/// 壳内真人经 UI 确认（门/裁决/理由/发现）→ 壳用服务态密钥签 receipt
/// （scope 绑本门；#323 内容绑定当前章节树摘要——签发后章节被改 →
/// 域层 ContentDrifted 拒，不假成功）→ 经
/// `dispatch_with(record_review_gate)` 走真实工具面落账（与 bid-mcp-stdio
/// 同源裁决：状态窗/门序/幂等/追认全在域层）→ 工具输出原样放 `gate_pass`
/// 键（receipt 回执 / gates_approved / agent_waivers /
/// human_review_complete / status）。
///
/// 参数：`gate`（见 [`gate_from_str`]）、`decision`（APPROVED|REJECTED——
/// 工具面双形态解析）、`findings`（可选数组 `[{severity, code, message,
/// section_id?}]`——Rejected 必须含 ≥1 BLOCKER，域层裁决）、`reason`
/// （human 路径可选）、`actor_id`（宿主身份命名，缺省 `shell-operator`）、
/// `project_version`（可选 CAS——乐观并发保护）。
///
/// 拒绝面：无 db.json → `not_found`；项目未到状态窗 / 门序未满足 /
/// Rejected 无 BLOCKER / receipt 过期漂移 → 工具面 E_STATE /
/// E_UNPROCESSABLE 原文透传（`state` / `bad_args` 码——UI 按码分支引导，
/// 不假成功）。
pub fn gate_pass(
    ws: &Workspace,
    cache: &Mutex<Option<CachedService>>,
    a: &Args,
) -> Result<Value, IpcError> {
    let gate_str = a.req_str("gate")?.to_string();
    let gate = gate_from_str(&gate_str)?;
    let decision = a.req_str("decision")?.to_string();
    let reason = a.str("reason")?.map(str::to_string);
    let findings = a.get("findings").cloned().unwrap_or_else(|| json!([]));
    let actor_id = a
        .str("actor_id")?
        .filter(|s| !s.trim().is_empty())
        .map(str::to_string)
        .unwrap_or_else(|| "shell-operator".to_string());
    let project_version = a.u64("project_version")?;

    let mut guard = lock(cache);
    let svc = ensure_locked(&mut guard, ws)?;
    let (project_id, project) = project_meta(svc)?;
    // #182 宿主签发面：scope 绑本门（A 门 receipt 过不了 B 门）。
    let scope = bid_mcp::review_gate_scope(gate);
    let receipt = svc.issue_approval_receipt(&actor_id, &scope);
    let mut args = json!({
        "project_id": project_id,
        "gate": gate_str,
        "decision": decision,
        "receipt": receipt,
        "findings": findings,
    });
    if let Some(r) = reason {
        args["reason"] = json!(r);
    }
    if let Some(v) = project_version {
        args["project_version"] = json!(v);
    }
    let reply = bid_mcp::dispatch_with(
        svc,
        bid_mcp::ToolCall {
            tool: "record_review_gate".to_string(),
            args,
        },
    );
    let tool_out = match reply {
        bid_mcp::ToolReply::Ok(out) => out.result,
        bid_mcp::ToolReply::Err { error, .. } => return Err(map_tool_err(error)),
    };
    Ok(json!({
        "present": true,
        "workspace": ws.root_display(),
        "project": project,
        "gate_pass": tool_out,
    }))
}

/// 项目元信息（id 先取出供工具路由；返回 (id, 元信息 json)）——
/// 借用面：先取后放，`dispatch_with` 要 `&mut BidService`。
fn project_meta(
    svc: &bid_tools::service::BidService,
) -> Result<(String, Value), IpcError> {
    let store = svc.store();
    let p = store.project().map_err(map_domain_err)?;
    Ok((
        p.id.clone(),
        json!({
            "id": p.id,
            "name": p.name,
            "status": p.status.as_str(),
        }),
    ))
}
/// `bid.coverage` —— 覆盖报告（只读，#313 批 D）。
///
/// 主体经 `bid_mcp::dispatch_with(get_coverage_report)` 走真实工具面
/// （与 bid-mcp-stdio 同源裁决——方案 A 直链），工具输出原样放 `coverage`
/// 键。壳侧 `summary` 在工具输出上现算**三态分账**（#244 口径——每个块
/// 必居其一）：
///   * `judged_blocks`（A 已判定）= covered_blocks − Σ files[].excluded_blocks
///     （工具面 `covered_blocks` 是 A+B 合计——域层 CoverageReport 语义，
///     见 bid-domain/src/coverage.rs；排除数只在逐文件层，壳侧聚合）；
///   * `excluded_blocks`（B 已排除）= Σ files[].excluded_blocks；
///   * `unjudged_blocks`（C 未判定）= 工具面顶层计数原样。
/// `by_verdict` 同样逐文件聚合（requirement / review_table / noise / rule …
/// ——BTreeMap 键序稳定，断言可依赖）。
///
/// ★条款覆盖（面板规格「★条款覆盖 N/M」）：循 `get_star_coverage`
/// （#285 逐文件只读面）对 `coverage.files[]` 逐件调用后聚合
/// star_truth / star_captured / star_missing——口径三级恒等式
/// star_total = declarations + star_truth = declarations + captured + missing
/// （工具面契约）。**逐块明细不进本响应**（captured/missing 各 ≤100 条/
/// 文件，全量回显会吃爆 IPC——明细走 bid-mcp 工具面，面板只显计数与
/// next 引导）。
///
/// 无 db.json → 干净 `not_found`；DRAFT 态（未导入文件）工具面 E_STATE
/// 透传为壳侧 `state` 错误码（契约 §3.3——UI 分支出「尚未开放」卡而非
/// 错误横幅）。服务缓存语义同 [`state`] / [`outline`] / [`matrix`]。
pub fn coverage(
    ws: &Workspace,
    cache: &Mutex<Option<CachedService>>,
    _a: &Args,
) -> Result<Value, IpcError> {
    let mut guard = lock(cache);
    let svc = ensure_locked(&mut guard, ws)?;
    // 项目元信息先取（owned）——后面的工具循环要 &mut svc
    let (project_id, project_name, project_status) = {
        let p = svc.store().project().map_err(map_domain_err)?;
        (p.id.clone(), p.name.clone(), p.status.as_str().to_string())
    };

    // 主体：get_coverage_report（真实工具面，方案 A 直链）
    let reply = bid_mcp::dispatch_with(
        svc,
        bid_mcp::ToolCall {
            tool: "get_coverage_report".to_string(),
            args: json!({ "project_id": project_id }),
        },
    );
    let cov = match reply {
        bid_mcp::ToolReply::Ok(out) => out.result,
        bid_mcp::ToolReply::Err { error, .. } => return Err(map_tool_err(error)),
    };

    // 三态分账 + by_verdict 聚合（在工具输出上现算——单一真源，
    // 与批 B summary 同款纪律：不另写一套判定字面量）
    let files = cov
        .get("files")
        .and_then(|f| f.as_array())
        .cloned()
        .unwrap_or_default();
    let mut excluded_total = 0u64;
    let mut by_verdict: std::collections::BTreeMap<String, u64> =
        std::collections::BTreeMap::new();
    for f in &files {
        excluded_total += f
            .get("excluded_blocks")
            .and_then(|v| v.as_u64())
            .unwrap_or(0);
        if let Some(bv) = f.get("by_verdict").and_then(|v| v.as_object()) {
            for (k, v) in bv {
                *by_verdict.entry(k.clone()).or_insert(0) += v.as_u64().unwrap_or(0);
            }
        }
    }
    let covered_total = cov.get("covered_blocks").and_then(|v| v.as_u64()).unwrap_or(0);
    // A 态 = covered − excluded（covered 是 A+B 合计）；饱和减防御脏数据
    let judged_total = covered_total.saturating_sub(excluded_total);
    let by_verdict_obj: serde_json::Map<String, Value> = by_verdict
        .into_iter()
        .map(|(k, v)| (k, json!(v)))
        .collect();

    // ★条款覆盖：逐文件 get_star_coverage 聚合（#285 只读面——只取计数，
    // 逐块明细留在 bid-mcp 工具面，响应不膨胀）
    let mut star_files: Vec<Value> = Vec::with_capacity(files.len());
    let (mut s_total, mut s_decl, mut s_truth, mut s_capt, mut s_miss) =
        (0u64, 0u64, 0u64, 0u64, 0u64);
    for f in &files {
        let fid = match f.get("file_id").and_then(|v| v.as_str()) {
            Some(id) => id.to_string(),
            None => continue,
        };
        let reply = bid_mcp::dispatch_with(
            svc,
            bid_mcp::ToolCall {
                tool: "get_star_coverage".to_string(),
                args: json!({ "project_id": project_id, "file_id": fid }),
            },
        );
        let out = match reply {
            bid_mcp::ToolReply::Ok(out) => out.result,
            bid_mcp::ToolReply::Err { error, .. } => return Err(map_tool_err(error)),
        };
        let cnt = |k: &str| out.get(k).and_then(|v| v.as_u64()).unwrap_or(0);
        s_total += cnt("star_total");
        s_decl += cnt("declarations");
        s_truth += cnt("star_truth");
        s_capt += cnt("star_captured");
        s_miss += cnt("star_missing");
        star_files.push(json!({
            "file_id": fid,
            "file_name": out.get("file_name").cloned().unwrap_or(Value::Null),
            "star_total": cnt("star_total"),
            "declarations": cnt("declarations"),
            "star_truth": cnt("star_truth"),
            "star_captured": cnt("star_captured"),
            "star_missing": cnt("star_missing"),
            "next": out.get("next").cloned().unwrap_or(Value::Null),
        }));
    }

    Ok(json!({
        "present": true,
        "workspace": ws.root_display(),
        "project": {
            "id": project_id,
            "name": project_name,
            "status": project_status,
        },
        "coverage": cov,
        "summary": {
            "total_blocks": cov.get("total_blocks").cloned().unwrap_or(json!(0)),
            "judged_blocks": judged_total,
            "excluded_blocks": excluded_total,
            "unjudged_blocks": cov.get("unjudged_blocks").cloned().unwrap_or(json!(0)),
            "uncovered_range_count": cov
                .get("uncovered_range_count")
                .cloned()
                .unwrap_or(json!(0)),
            "complete": cov.get("complete").cloned().unwrap_or(Value::Null),
            "by_verdict": Value::Object(by_verdict_obj),
        },
        "star": {
            "files": star_files,
            "total": {
                "star_total": s_total,
                "declarations": s_decl,
                "star_truth": s_truth,
                "star_captured": s_capt,
                "star_missing": s_miss,
            },
        },
    }))
}


/// 锁毒化不复位（与 ipc.rs `Ctx::ws` 同口径）。
fn lock(cache: &Mutex<Option<CachedService>>) -> MutexGuard<'_, Option<CachedService>> {
    cache.lock().unwrap_or_else(|e| e.into_inner())
}

// ---------------------------------------------------------------- 测试

#[cfg(test)]
mod tests {
    use super::*;

    use bid_domain::{ProjectStatus, Requirement};

    use crate::ipc::Ctx;
    use crate::test_support::workspace_files_guard;

    /// 叶 1 正文（字数断言都用 chars().count() 现算——不手数字符）
    const LEAF1_CONTENT: &str = "本节对招标文件第 3.2 条逐项应答，参数见表 1-1。";

    fn tmp_ws(tag: &str) -> (std::path::PathBuf, Workspace) {
        let d = std::env::temp_dir().join(format!(
            "mang-bid-313-{tag}-{}-{}",
            std::process::id(),
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        std::fs::create_dir_all(&d).unwrap();
        let ws = Workspace::new(&d).unwrap();
        (d, ws)
    }

    fn req(id: &str, category: &str, excerpt: &str) -> Requirement {
        // 每条 REQ 独立锚点：requirement_hash = sha256(file|locator|excerpt)——
        // 空锚点的两条 REQ 同哈希，set_requirements 会「同位覆盖」只剩一条
        Requirement {
            id: id.to_string(),
            category: category.to_string(),
            clause_no: None,
            anchors: vec![bid_domain::Anchor {
                file: "A-招标文件.docx".to_string(),
                kind: "para".to_string(),
                locator: format!("第三章 3.2/{id}"),
                excerpt: excerpt.to_string(),
                ..bid_domain::Anchor::default()
            }],
            params: HashMap::new(),
            source_file: "A-招标文件.docx".to_string(),
        }
    }

    fn node(
        id: &str,
        parent: Option<&str>,
        title: &str,
        level: u8,
        order: u32,
        reqs: &[&str],
        target: u32,
    ) -> OutlineNode {
        OutlineNode {
            id: id.to_string(),
            parent_id: parent.map(str::to_string),
            title: title.to_string(),
            level,
            order,
            requirement_ids: reqs.iter().map(|s| s.to_string()).collect(),
            target_chars: target,
            status: SectionStatus::Pending,
            dirty: false,
            content: None,
            content_attempt: 0,
        }
    }

    /// 建一个最小真实项目（直接走 bid-tools 服务面——与 MCP 写路径同源）：
    /// 1 章 + 2 叶；叶 1 起草到 DRAFTED，叶 2 留 PENDING；chapters/ 留 1 份。
    fn seed_project(dir: &std::path::Path) {
        let mut svc = bid_tools::service::BidService::open(dir).unwrap();
        svc.create_project("演示水厂项目", "PRJ-TEST", "明标", "ext-313-a").unwrap();
        let store = svc.store_mut();
        store
            .advance_project_status(ProjectStatus::FilesImported)
            .unwrap();
        store
            .set_requirements(vec![
                req("REQ-0001", "技术参数", "投标人须提供 2000 路并发能力"),
                req("REQ-0002", "资格条件", "投标人须具备电子与智能化二级资质"),
            ])
            .unwrap();
        store
            .set_outline(vec![
                // 父节点 requirement_ids = 子并集（validate_outline 要求每节点 ≥1）
                node("SEC-T01", None, "第一章 技术方案", 1, 1, &["REQ-0001", "REQ-0002"], 15_000),
                node("SEC-T02", Some("SEC-T01"), "1.1 工艺参数响应", 2, 2, &["REQ-0001"], 6_000),
                node("SEC-T03", Some("SEC-T01"), "1.2 资格证明", 2, 3, &["REQ-0002"], 9_000),
            ])
            .unwrap();
        // 叶 1：Pending → Outlining → Drafting →（内容）→ Drafted
        for to in [SectionStatus::Outlining, SectionStatus::Drafting] {
            store.advance_section_status("SEC-T02", to).unwrap();
        }
        store
            .set_section_content("SEC-T02", LEAF1_CONTENT.to_string())
            .unwrap();
        store.advance_section_status("SEC-T02", SectionStatus::Drafted).unwrap();
        svc.checkpoint().unwrap();
        // chapters/ 面板跳转锚：真实存在的章节文件（详情面 fs.read 的目标）
        std::fs::create_dir_all(dir.join("chapters")).unwrap();
        std::fs::write(
            dir.join("chapters").join("SEC-T02.json"),
            format!(
                r#"{{"section_id":"SEC-T02","content":{},"char_count":{},"attempt":1,"citations":[],"updated_at":1793000000}}"#,
                serde_json::to_string(LEAF1_CONTENT).unwrap(),
                LEAF1_CONTENT.chars().count()
            ),
        )
        .unwrap();
    }

    /// 走公开 IPC 面（parse → Ctx::dispatch）——与 selftest 同口径，
    /// 不碰模块私有 exec。
    fn call(ctx: &Ctx, cmd: &str) -> Value {
        let text = serde_json::to_string(&json!({ "id": "t", "cmd": cmd })).unwrap();
        let req = crate::ipc::parse(&text).unwrap();
        ctx.dispatch(&req)
    }
    fn ok_of(frame: &Value) -> &Value {
        frame.get("result").unwrap_or(&Value::Null)
    }
    fn err_code_of(frame: &Value) -> String {
        frame.get("code").and_then(|c| c.as_str()).unwrap_or("").to_string()
    }

    #[test]
    fn state_and_outline_clean_not_found_without_db() {
        let (dir, _ws) = tmp_ws("nodb");
        let ctx = Ctx::new(Workspace::new(&dir).unwrap(), PathBuf::new());
        for cmd in ["bid.state", "bid.outline", "bid.matrix", "bid.coverage"] {
            let frame = call(&ctx, cmd);
            assert_eq!(frame["ok"], json!(false), "{cmd} 无 db.json 应干净 not_found：{frame}");
            assert_eq!(err_code_of(&frame), "not_found");
            assert!(
                frame["message"].as_str().unwrap_or("").contains("db.json"),
                "文案要指向缺 db.json：{frame}"
            );
        }
        // 干净 = 零副作用：不许凭空长出 .mang/（BidService::open 会建 approval.key）
        assert!(!dir.join(".mang").exists(), "查看状态不得在工作区留副作用");
        let _ = std::fs::remove_dir_all(dir);
    }

    #[test]
    fn state_and_outline_read_real_project() {
        let (dir, ws) = tmp_ws("real");
        seed_project(&dir);
        let ctx = Ctx::new(ws.clone(), PathBuf::new());

        let frame = call(&ctx, "bid.state");
        assert_eq!(frame["ok"], json!(true), "{frame}");
        let s = ok_of(&frame).clone();
        assert_eq!(s["present"], json!(true));
        assert_eq!(s["project"]["name"], "演示水厂项目");
        assert_eq!(s["project"]["status"], "REQUIREMENTS_EXTRACTED");
        // 工具面主体（get_bid_project_state 原样透传）
        assert_eq!(s["state"]["status"], "REQUIREMENTS_EXTRACTED");
        assert!(s["state"]["allowed_next_tools"].is_array());
        // 快速统计
        assert_eq!(s["quick_stats"]["requirements"], 2);
        assert_eq!(s["quick_stats"]["sections"], 3);
        assert_eq!(s["quick_stats"]["sections_leaf"], 2);
        assert_eq!(s["quick_stats"]["sections_drafted"], 1);
        assert_eq!(s["quick_stats"]["target_total_chars"], 15_000); // 叶配额和
        let expect_chars = LEAF1_CONTENT.chars().count() as u64;
        assert_eq!(s["quick_stats"]["actual_total_chars"], expect_chars);
        assert!(s["quick_stats"]["pages_estimate"].as_u64().unwrap() >= 1);

        let frame = call(&ctx, "bid.outline");
        assert_eq!(frame["ok"], json!(true), "{frame}");
        let o = ok_of(&frame).clone();
        assert_eq!(o["present"], json!(true));
        let nodes = o["nodes"].as_array().unwrap();
        assert_eq!(nodes.len(), 3);
        assert_eq!(nodes[0]["id"], "SEC-T01"); // 文档序
        assert_eq!(nodes[0]["is_leaf"], json!(false));
        assert_eq!(nodes[0]["actual_chars"], expect_chars); // 父 = 子叶之和
        assert_eq!(nodes[1]["id"], "SEC-T02");
        assert_eq!(nodes[1]["status"], "DRAFTED");
        assert_eq!(nodes[1]["actual_chars"], expect_chars);
        assert_eq!(
            nodes[1]["chapter_file"], "chapters/SEC-T02.json",
            "真实存在的章节文件才回 chapter_file"
        );
        assert_eq!(nodes[2]["id"], "SEC-T03");
        assert_eq!(nodes[2]["status"], "PENDING");
        assert_eq!(nodes[2]["actual_chars"], 0);
        assert_eq!(nodes[2]["chapter_file"], Value::Null);
        assert_eq!(o["stats"]["sections_drafted"], 1);
        let _ = std::fs::remove_dir_all(dir);
    }

    #[test]
    fn cache_reopens_when_db_json_changes() {
        let (dir, ws) = tmp_ws("refresh");
        seed_project(&dir);
        let ctx = Ctx::new(ws.clone(), PathBuf::new());
        let s1 = ok_of(&call(&ctx, "bid.state")).clone();
        assert_eq!(s1["quick_stats"]["requirements"], 2);
        // 外部进程（bid-mcp-stdio / Agent）改写 db.json：加一条 REQ
        let mut svc = bid_tools::service::BidService::open(&dir).unwrap();
        let store = svc.store_mut();
        store
            .set_requirements(vec![req("REQ-0003", "商务要求", "质保期不少于三年")])
            .unwrap();
        svc.checkpoint().unwrap();
        // 缓存按 db.json 指纹自动重开——UI 无需重启
        let s2 = ok_of(&call(&ctx, "bid.state")).clone();
        assert_eq!(s2["quick_stats"]["requirements"], 3, "db.json 变更后缓存必须重开");
        let _ = std::fs::remove_dir_all(dir);
    }

    #[test]
    fn cache_rebinds_after_workspace_switch() {
        // open_workspace 写全局 last-workspace.json——持 crate 级共享锁（#383）
        let _guard = workspace_files_guard();
        let (dir_a, _a) = tmp_ws("wsa");
        let (dir_b, _b) = tmp_ws("wsb");
        seed_project(&dir_a);
        let mut svc = bid_tools::service::BidService::open(&dir_b).unwrap();
        svc.create_project("另一个项目", "PRJ-B", "暗标", "ext-313-b").unwrap();
        drop(svc);
        let ctx = Ctx::new(Workspace::new(&dir_a).unwrap(), PathBuf::new());
        let s1 = ok_of(&call(&ctx, "bid.state")).clone();
        assert_eq!(s1["project"]["name"], "演示水厂项目");
        // 切工作区（#194）：服务缓存随根重绑
        ctx.open_workspace(dir_b.to_string_lossy().as_ref()).unwrap();
        let s2 = ok_of(&call(&ctx, "bid.state")).clone();
        assert_eq!(s2["project"]["name"], "另一个项目");
        let _ = std::fs::remove_dir_all(dir_a);
        let _ = std::fs::remove_dir_all(dir_b);
    }

    /// #313 批 B：真实项目的矩阵读取与统计口径。
    ///
    /// 种子面（seed_project）：REQ-0001（技术参数）归属叶 SEC-T02 已写正文
    /// → RESPONDED（#241 正文实写路径），但 excerpt 含「提供」→ 证据要求面
    /// 词面命中且无在绑 → evidence_missing=true——正文响应与证据缺口同真，
    /// 正是 #241「文本事实与合规事实分账」的正交体现；REQ-0002（资格条件
    /// →必选）叶 SEC-T03 未写 → NOT_RESPONDED + blocking（类别面证据要求）。
    #[test]
    fn matrix_reads_real_project() {
        let (dir, ws) = tmp_ws("mx");
        seed_project(&dir);
        let ctx = Ctx::new(ws.clone(), PathBuf::new());
        let frame = call(&ctx, "bid.matrix");
        assert_eq!(frame["ok"], json!(true), "{frame}");
        let m = ok_of(&frame).clone();
        assert_eq!(m["present"], json!(true));
        assert_eq!(m["project"]["name"], "演示水厂项目");
        let rows = m["rows"].as_array().expect("rows 恒为数组");
        assert_eq!(rows.len(), 2);
        assert_eq!(m["total"], 2);
        // 行形状原样透传（工具面 CMP 序 + 行字段）
        let r1 = &rows[0];
        assert_eq!(r1["requirement"]["id"], "REQ-0001");
        assert_eq!(r1["status"], "RESPONDED", "叶已写正文 → RESPONDED（#241）：{r1}");
        assert_eq!(r1["draft_section_id"], "SEC-T02");
        assert_eq!(r1["blocking"], json!(false));
        assert!(
            r1["requirement"]["statement"].as_str().unwrap_or("").contains("2000 路"),
            "条款摘录来自锚点 excerpt：{r1}"
        );
        // #241 正交标记：正文已响应（文本事实）但 excerpt 含「提供」→ 证据
        // 要求面词面命中且无在绑 → 证据缺口（合规事实）——两列各自可查
        assert_eq!(r1["evidence_required"], json!(true), "「须提供」命中证据要求词面：{r1}");
        assert_eq!(r1["evidence_missing"], json!(true), "已响应但缺证据——#241 分账同真：{r1}");
        let r2 = &rows[1];
        assert_eq!(r2["requirement"]["id"], "REQ-0002");
        assert_eq!(r2["status"], "NOT_RESPONDED");
        assert_eq!(r2["requirement"]["mandatory"], json!(true), "资格条件 → 必选：{r2}");
        assert_eq!(r2["blocking"], json!(true), "必选未响应 → 阻断：{r2}");
        assert_eq!(r2["evidence_required"], json!(true), "资格条件 → 证据要求面（类别面）：{r2}");
        assert_eq!(r2["evidence_missing"], json!(true), "要求证据且无在绑 → 缺口：{r2}");
        // 统计摘要与行字段同一判定面
        assert_eq!(m["summary"]["by_status"]["RESPONDED"], 1);
        assert_eq!(m["summary"]["by_status"]["NOT_RESPONDED"], 1);
        assert_eq!(m["summary"]["by_status"]["PARTIAL"], 0);
        assert_eq!(m["summary"]["blocking"], 1);
        assert_eq!(m["summary"]["mandatory"], 1);
        assert_eq!(m["summary"]["evidence_missing"], 2, "两条各由词面/类别面命中");
        // ★实质性统计口原样透传（无 ★ 标记 → total=0、responded_share=null 非 0/0 假象）
        assert_eq!(m["star_summary"]["total"], 0);
        assert_eq!(m["star_summary"]["responded_share"], Value::Null);
        assert_eq!(m["fetched_pages"], 1);
        assert!(m["warnings"].as_array().map(|w| w.is_empty()).unwrap_or(false), "非空条款集无警告");
        assert!(m["project_version"].as_u64().unwrap_or(0) >= 1);
        let _ = std::fs::remove_dir_all(dir);
    }

    /// #313 批 B：工具面 S-4 游标分页的壳内聚合——1005 条跨两页
    /// （limit=1000 是工具面契约上限），fetched_pages/行数/统计都要对账。
    /// 矩阵不依赖大纲（只读工具任何阶段可调——无大纲时全部 NOT_RESPONDED）。
    #[test]
    fn matrix_aggregates_tool_pagination() {
        let (dir, ws) = tmp_ws("mxpage");
        let mut svc = bid_tools::service::BidService::open(&dir).unwrap();
        svc.create_project("分页矩阵项目", "PRJ-PG", "明标", "ext-313-pg").unwrap();
        svc.store_mut()
            .advance_project_status(bid_domain::ProjectStatus::FilesImported)
            .unwrap();
        let cats = ["技术参数", "资格条件", "商务要求"];
        let reqs: Vec<Requirement> = (1..=1005)
            .map(|i| req(&format!("REQ-P{i:04}"), cats[i % 3], &format!("分页种子条款 {i} 号要求")))
            .collect();
        svc.store_mut().set_requirements(reqs).unwrap();
        svc.checkpoint().unwrap();
        drop(svc);

        let ctx = Ctx::new(ws.clone(), PathBuf::new());
        let frame = call(&ctx, "bid.matrix");
        assert_eq!(frame["ok"], json!(true), "{frame}");
        let m = ok_of(&frame).clone();
        let rows = m["rows"].as_array().expect("rows 恒为数组");
        assert_eq!(rows.len(), 1005, "跨页聚合不得丢行：fetched_pages={}", m["fetched_pages"]);
        assert_eq!(m["fetched_pages"], 2, "1005 条 × limit 1000 → 恰两页");
        assert_eq!(m["total"], 1005);
        assert_eq!(m["summary"]["by_status"]["NOT_RESPONDED"], 1005);
        // 资格条件占 1/3（i%3==1）→ 335 条必选全部未响应 → 全阻断
        assert_eq!(m["summary"]["mandatory"], 335);
        assert_eq!(m["summary"]["blocking"], 335);
        // 行序 = 条款集位置序（CMP-0001..N 派生的确定性稳定序——分页安全前提）
        assert_eq!(rows[0]["requirement"]["id"], "REQ-P0001");
        assert_eq!(rows[1004]["requirement"]["id"], "REQ-P1005");
        let _ = std::fs::remove_dir_all(dir);
    }


    // ---------------------------------------------------------------- #313 批 C

    /// 建一个「矩阵就绪」项目：一条技术参数 REQ + 一条评分项 REQ
    /// （params.score = 20 → score.by_item 的驱动面），经
    /// `prepare_outline_and_matrix` 推到 MATRIX_READY（质量/自评工具的
    /// 状态窗下沿——起草前即可查进度，与 MCP 工具测试同款服务面调用）。
    fn seed_matrix_ready_project(dir: &std::path::Path) {
        let mut scoring_params: HashMap<String, Value> = HashMap::new();
        scoring_params.insert("score".to_string(), json!(20.0));
        let mut svc = bid_tools::service::BidService::open(dir).unwrap();
        svc.create_project("矩阵就绪项目", "PRJ-MR", "明标", "ext-313-c").unwrap();
        let store = svc.store_mut();
        store.advance_project_status(ProjectStatus::FilesImported).unwrap();
        let mut reqs = vec![
            req("REQ-0001", "技术参数", "投标人须提供 2000 路并发能力"),
            Requirement {
                params: scoring_params,
                ..req("REQ-0002", "评分项", "技术方案完整性、先进性、可行性优者得 20 分")
            },
        ];
        store.set_requirements(std::mem::take(&mut reqs)).unwrap();
        svc.prepare_outline_and_matrix(bid_domain::outline::OutlineSpec {
            target_total_chars: 400,
            max_reqs_per_leaf: 2,
        })
        .unwrap();
    }

    #[test]
    fn quality_and_score_clean_not_found_without_db() {
        let (dir, _ws) = tmp_ws("nodb-c");
        let ctx = Ctx::new(Workspace::new(&dir).unwrap(), PathBuf::new());
        for cmd in ["bid.quality", "bid.score"] {
            let frame = call(&ctx, cmd);
            assert_eq!(frame["ok"], json!(false), "{cmd} 无 db.json 应干净 not_found：{frame}");
            assert_eq!(err_code_of(&frame), "not_found");
        }
        assert!(!dir.join(".mang").exists(), "查看自评不得在工作区留副作用");
        let _ = std::fs::remove_dir_all(dir);
    }

    #[test]
    fn quality_and_score_reject_early_state_with_state_code() {
        // seed_project 停在 REQUIREMENTS_EXTRACTED（未建矩阵）——两工具
        // 的状态窗都是 MatrixReady+ → E_STATE 透传为壳侧 `state` 码
        //（UI 据此显示「先建纲再查质量」引导，而非故障横幅）。
        let (dir, _ws) = tmp_ws("early");
        seed_project(&dir);
        let ctx = Ctx::new(Workspace::new(&dir).unwrap(), PathBuf::new());
        for cmd in ["bid.quality", "bid.score"] {
            let frame = call(&ctx, cmd);
            assert_eq!(frame["ok"], json!(false), "{cmd} 早态应拒绝：{frame}");
            assert_eq!(err_code_of(&frame), "state", "{cmd} E_STATE 必须映射为 state 码：{frame}");
            let msg = frame["message"].as_str().unwrap_or("");
            assert!(
                msg.contains("先建纲") || msg.contains("态"),
                "{cmd} 拒绝文案要指向状态前置：{frame}"
            );
        }
        let _ = std::fs::remove_dir_all(dir);
    }

    #[test]
    fn quality_and_score_read_after_matrix_ready() {
        let (dir, _ws) = tmp_ws("matrix-ready");
        seed_matrix_ready_project(&dir);
        let ctx = Ctx::new(Workspace::new(&dir).unwrap(), PathBuf::new());

        let frame = call(&ctx, "bid.quality");
        assert_eq!(frame["ok"], json!(true), "{frame}");
        let q = ok_of(&frame).clone();
        assert_eq!(q["present"], json!(true));
        assert_eq!(q["project"]["name"], "矩阵就绪项目");
        assert_eq!(q["project"]["status"], "MATRIX_READY");
        let ql = &q["quality"];
        // 工具输出原样透传（summary / submission_readiness / sections 三面在场）
        assert!(ql["summary"]["total"].as_u64().unwrap_or(0) >= 1, "章节树在场：{ql}");
        assert!(ql["submission_readiness"].is_object(), "#241 两分账面在场：{ql}");
        assert!(ql["sections"].as_array().is_some_and(|a| !a.is_empty()));
        // 未起草 → 全 PENDING；「未覆盖」只对有正文的章计数（quality.rs
        // 语义：没正文就没有「未回应」可言）——此处应为 0 而非 2
        assert_eq!(ql["summary"]["drafted"], 0);
        assert_eq!(ql["summary"]["pending"], ql["summary"]["total"]);
        assert_eq!(ql["summary"]["uncovered_req_total"], 0);

        let frame = call(&ctx, "bid.score");
        assert_eq!(frame["ok"], json!(true), "{frame}");
        let s = ok_of(&frame).clone();
        assert_eq!(s["present"], json!(true));
        let sc = &s["score"];
        // #186 语义降级标记必须原样在场（UI 徽章直接消费）
        assert_eq!(sc["diagnostic_only"], json!(true));
        assert_eq!(sc["result_kind"], "rule_heuristic");
        // 评分项 REQ（params.score=20）→ by_item 1 行，未起草 → estimated 0
        let items = sc["by_item"].as_array().cloned().unwrap_or_default();
        assert_eq!(items.len(), 1, "评分项 REQ 恰一行：{sc}");
        assert_eq!(items[0]["item_id"], "REQ-0002");
        assert_eq!(items[0]["max"], json!(20.0));
        assert_eq!(items[0]["estimated"], 0.0);
        assert_eq!(items[0]["tier"], "未覆盖");
        assert_eq!(sc["target"], json!(20.0));
        assert_eq!(sc["total"], 0.0);
        // 价格面：无报价 → null（诚实显示，不伪装 0）
        assert_eq!(sc["price"], Value::Null);
        let _ = std::fs::remove_dir_all(dir);
    }

    // ---------------------------------------------------------------- #603 批 A：治理面

    /// 走公开 IPC 面的带参调用（gate_pass 用——参数顶层平铺，与壳协议
    /// 同形：{id, cmd, gate, decision, …}）。
    fn call_args(ctx: &Ctx, cmd: &str, body: Value) -> Value {
        let mut full = json!({ "id": "t", "cmd": cmd });
        if let (Some(dst), Some(src)) = (full.as_object_mut(), body.as_object()) {
            for (k, v) in src {
                dst.insert(k.clone(), v.clone());
            }
        }
        let text = serde_json::to_string(&full).unwrap();
        let req = crate::ipc::parse(&text).unwrap();
        ctx.dispatch(&req)
    }

    #[test]
    fn gates_clean_not_found_without_db() {
        let (dir, _ws) = tmp_ws("nodb-603");
        let ctx = Ctx::new(Workspace::new(&dir).unwrap(), PathBuf::new());
        for cmd in ["bid.gates"] {
            let frame = call(&ctx, cmd);
            assert_eq!(frame["ok"], json!(false), "{cmd} 无 db.json 应干净 not_found：{frame}");
            assert_eq!(err_code_of(&frame), "not_found");
        }
        // 写面同款（合法入参也 not_found——不落副作用）
        let frame = call_args(
            &ctx,
            "bid.gate_pass",
            json!({ "gate": "matrix_approval", "decision": "APPROVED" }),
        );
        assert_eq!(frame["ok"], json!(false), "{frame}");
        assert_eq!(err_code_of(&frame), "not_found");
        assert!(!dir.join(".mang").exists(), "查门/过门不得在工作区留副作用");
        let _ = std::fs::remove_dir_all(dir);
    }

    /// 读面无状态窗：早期态（REQUIREMENTS_EXTRACTED）门台账可见（三门全
    /// 未过 + 空账本 human_review_complete=true——「没有门被 agent 过」无从
    /// 警告）；写面有状态窗：matrix 门在 MATRIX_READY 前被域层 E_STATE 拒，
    /// 透传为壳侧 `state` 码。
    #[test]
    fn gates_readable_early_state_but_pass_needs_matrix_ready() {
        let (dir, _ws) = tmp_ws("early-603");
        seed_project(&dir);
        let ctx = Ctx::new(Workspace::new(&dir).unwrap(), PathBuf::new());
        let frame = call(&ctx, "bid.gates");
        assert_eq!(frame["ok"], json!(true), "{frame}");
        let g = ok_of(&frame).clone();
        assert_eq!(g["present"], json!(true));
        let gates = g["gates"].as_array().expect("gates 恒为数组");
        assert_eq!(gates.len(), 5, "五门恒在场（读面不筛）：{gates:#?}");
        assert_eq!(gates[0]["gate"], "matrix_approval");
        assert_eq!(gates[0]["approved"], json!(false));
        assert_eq!(gates[0]["latest_pass"], Value::Null);
        assert_eq!(g["human_review_complete"], json!(true), "空账本无从警告");
        assert_eq!(g["agent_waivers"].as_array().map(Vec::len), Some(0));
        assert_eq!(g["reviews"].as_array().map(Vec::len), Some(0));

        // 写面：矩阵门需要 MATRIX_READY+（域层 E_STATE → 壳侧 state 码）
        let frame = call_args(
            &ctx,
            "bid.gate_pass",
            json!({ "gate": "matrix_approval", "decision": "APPROVED" }),
        );
        assert_eq!(frame["ok"], json!(false), "早态过门应拒：{frame}");
        assert_eq!(err_code_of(&frame), "state", "E_STATE 透传为 state 码：{frame}");
        let _ = std::fs::remove_dir_all(dir);
    }

    /// 写面全链：宿主签发 receipt（#182）→ 工具面落账 → 门序推进 →
    /// 追认语义（human_confirmed）→ Rejected+BLOCKER 派生 RT →
    /// 拒绝面（门序跳跃 / Rejected 无 BLOCKER / 非法门名）。
    #[test]
    fn gate_pass_full_flow_with_host_receipt() {
        let (dir, _ws) = tmp_ws("flow-603");
        seed_matrix_ready_project(&dir);
        let ctx = Ctx::new(Workspace::new(&dir).unwrap(), PathBuf::new());

        // ① 门序跳跃：pre_export 先过 → 域层 E_STATE（前置门未过）
        let frame = call_args(
            &ctx,
            "bid.gate_pass",
            json!({ "gate": "pre_export_confirm", "decision": "APPROVED" }),
        );
        assert_eq!(frame["ok"], json!(false), "{frame}");
        assert_eq!(err_code_of(&frame), "state", "门序强制透传：{frame}");
        assert!(
            frame["message"].as_str().unwrap_or("").contains("前置门"),
            "门序拒绝文案要指向前置门：{frame}"
        );

        // ② matrix 门 APPROVED（宿主签发 receipt——human 路径）
        let frame = call_args(
            &ctx,
            "bid.gate_pass",
            json!({ "gate": "matrix_approval", "decision": "APPROVED", "actor_id": "reviewer-zhang" }),
        );
        assert_eq!(frame["ok"], json!(true), "{frame}");
        let gp = ok_of(&frame)["gate_pass"].clone();
        assert_eq!(gp["receipt"]["gate"], "matrix_approval");
        assert_eq!(gp["receipt"]["decision"], "APPROVED");
        assert_eq!(gp["receipt"]["actor"]["actor_id"], "reviewer-zhang");
        assert_eq!(gp["receipt"]["actor"]["actor_type"], "human");
        assert_eq!(gp["receipt"]["method"], "human_receipt", "#182 人类签域验签路径：{gp}");
        assert_eq!(gp["receipt"]["human_confirmed"], json!(true));
        assert!(
            gp["gates_approved"].as_array().unwrap().iter()
                .any(|v| v == "matrix_approval"),
            "gates_approved 同源回显：{gp}"
        );

        // ③ 读面对账：matrix 门已过 + latest_pass 审计四要素
        let frame = call(&ctx, "bid.gates");
        assert_eq!(frame["ok"], json!(true), "{frame}");
        let g = ok_of(&frame).clone();
        let gates = g["gates"].as_array().unwrap().clone();
        assert_eq!(gates[0]["approved"], json!(true));
        assert_eq!(gates[0]["latest_pass"]["actor"], "reviewer-zhang");
        assert_eq!(gates[0]["latest_pass"]["method"], "human_receipt");
        assert_eq!(gates[0]["latest_pass"]["human_confirmed"], json!(true));
        assert_eq!(gates[1]["approved"], json!(false), "outline 门未过");
        assert_eq!(g["human_review_complete"], json!(true), "全 human 过门 → 无警告");

        // ④ outline 门过 → pre_export 拒审（带 BLOCKER finding → RT 派生）
        let frame = call_args(
            &ctx,
            "bid.gate_pass",
            json!({ "gate": "outline_approval", "decision": "APPROVED" }),
        );
        assert_eq!(frame["ok"], json!(true), "缺省 actor_id=shell-operator：{frame}");
        assert_eq!(
            ok_of(&frame)["gate_pass"]["receipt"]["actor"]["actor_id"],
            "shell-operator"
        );
        let frame = call_args(
            &ctx,
            "bid.gate_pass",
            json!({
                "gate": "pre_export_confirm",
                "decision": "REJECTED",
                "findings": [
                    { "severity": "BLOCKER", "code": "EXPORT-GUARD-1", "message": "证据缺口 3 项未清——导出前必须补齐" }
                ]
            }),
        );
        assert_eq!(frame["ok"], json!(true), "拒审是合法裁决（过程记录）：{frame}");
        let gp = ok_of(&frame)["gate_pass"].clone();
        let rts = gp["receipt"]["spawned_rt_ids"].as_array().cloned().unwrap_or_default();
        assert_eq!(rts.len(), 1, "BLOCKER 强制派生 RT（结构保证）：{gp}");
        assert_eq!(gp["receipt"]["decision"], "REJECTED");

        // ⑤ Rejected 无 BLOCKER → 域层拒绝（诚实状态——Warning 不构成拒审依据）
        let frame = call_args(
            &ctx,
            "bid.gate_pass",
            json!({
                "gate": "pre_export_confirm",
                "decision": "REJECTED",
                "findings": [
                    { "severity": "WARNING", "code": "W-1", "message": "字数偏离预警" }
                ]
            }),
        );
        assert_eq!(frame["ok"], json!(false), "{frame}");
        assert_eq!(err_code_of(&frame), "bad_args", "E_UNPROCESSABLE → bad_args 码：{frame}");
        assert!(
            frame["message"].as_str().unwrap_or("").contains("BLOCKER"),
            "拒绝文案要指向 BLOCKER 前置：{frame}"
        );

        // ⑥ 非法门名 → 壳侧入参早拒（不进工具面）
        let frame = call_args(
            &ctx,
            "bid.gate_pass",
            json!({ "gate": "no_addendum_confirmed", "decision": "APPROVED" }),
        );
        assert_eq!(frame["ok"], json!(false), "{frame}");
        assert_eq!(err_code_of(&frame), "bad_args");
        assert!(
            frame["message"].as_str().unwrap_or("").contains("合法值"),
            "早拒文案要列出合法值：{frame}"
        );

        // ⑦ 裁决历史（reviews）：REV 记录含 APPROVED 与 REJECTED，receipt
        //    的 reviewer 是 human: 派生（legacy 回显面）
        let frame = call(&ctx, "bid.gates");
        let g = ok_of(&frame).clone();
        let reviews = g["reviews"].as_array().unwrap().clone();
        assert!(reviews.len() >= 3, "matrix/outline/pre_export 三次记审全落账：{reviews:#?}");
        assert_eq!(reviews[0]["gate"], "pre_export_confirm", "倒序（最新在前）");
        assert_eq!(reviews[0]["decision"], "REJECTED");
        assert!(reviews[0]["actor"]["actor_id"].is_string(), "#182 可信身份回显在场");
        assert!(reviews.iter().any(|r| r["decision"] == "APPROVED" && r["gate"] == "matrix_approval"));
        let _ = std::fs::remove_dir_all(dir);
    }

    /// #313 批 D：DRAFT 态（建项未导入）——工具面 E_STATE 透传为壳侧
    /// `state` 码（契约 §3.3——UI 分支出「尚未开放」卡而非错误横幅）。
    #[test]
    fn coverage_state_gate_before_import() {
        let (dir, _ws) = tmp_ws("covdraft");
        {
            let mut svc = bid_tools::service::BidService::open(&dir).unwrap();
            svc.create_project("未导入项目", "PRJ-CD", "明标", "ext-313-cd")
                .unwrap();
            svc.checkpoint().unwrap();
        }
        let ctx = Ctx::new(Workspace::new(&dir).unwrap(), PathBuf::new());
        let frame = call(&ctx, "bid.coverage");
        assert_eq!(frame["ok"], json!(false), "{frame}");
        assert_eq!(
            err_code_of(&frame), "state",
            "DRAFT 态应透传工具面 E_STATE 为壳侧 state 码：{frame}"
        );
        let _ = std::fs::remove_dir_all(dir);
    }

    /// #313 批 D：真件链（corpus-A 主文件导入 + 部分标记）——三态分账 /
    /// by_verdict 聚合 / ★聚合恒等式 / 跨实例持久化恢复。fixture 缺位
    /// 时跳过（与 bid-mcp coverage_tools.rs 同款守卫——CI 真件跑全量）。
    #[test]
    fn coverage_reads_real_imported_file() {
        // #600 CI 修复：CARGO_MANIFEST_DIR 拼 ../../../fixtures 得到的路径**字面**
        // 含 `..`——而 import_tender_files 的逃逸防护会拒绝含父级逃逸的路径
        // （E_UNPROCESSABLE）。canonicalize 把 `..` 解析成绝对规范路径后
        // 再交给工具面（文件系统层面同一个位置，但字面不再有 `..`）。
        let fixtures = std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .join("../../../fixtures/corpus-A/files")
            .canonicalize()
            .unwrap_or_else(|e| panic!("fixtures 目录不存在或不可解析：{e}"));
        let main = fixtures.join("A-招标文件.docx");
        if !main.is_file() {
            eprintln!("SKIP：fixture 缺位（{}）——真件面留给 CI", main.display());
            return;
        }
        let (dir, _ws) = tmp_ws("covreal");
        // 种子：真实导入（与 MCP 写路径同源——工具面 import_tender_files
        // + submit_block_marks），再用独立实例走公开 IPC 面
        let file_id;
        {
            let mut svc = bid_tools::service::BidService::open(&dir)
                .unwrap()
                .with_fs_root(&fixtures);
            let (pid, _) = svc
                .create_project("覆盖测试项目", "PRJ-CV", "明标", "ext-313-cv")
                .unwrap();
            let import = bid_mcp::dispatch_with(
                &mut svc,
                bid_mcp::ToolCall {
                    tool: "import_tender_files".to_string(),
                    args: json!({ "project_id": pid, "files": [{
                        "upload_ref": main.to_string_lossy(),
                        "filename": "A-招标文件.docx",
                        "kind": "招标文件"
                    }] }),
                },
            );
            let out = match import {
                bid_mcp::ToolReply::Ok(out) => out.result,
                bid_mcp::ToolReply::Err { error, .. } => panic!("导入失败：{error}"),
            };
            file_id = out["file_ids"][0]
                .as_str()
                .expect("file_ids[0] 恒在")
                .to_string();
            // 部分标记：0-9 noise（B 态）/ 10-19 requirement（A 态）
            // ——三态分账有非零 A/B 态可断言（0 标记时 covered=0 不可分辨）
            let marks = bid_mcp::dispatch_with(
                &mut svc,
                bid_mcp::ToolCall {
                    tool: "submit_block_marks".to_string(),
                    args: json!({ "project_id": pid, "file_id": file_id,
                        "marks": [
                            { "from": 0, "to": 9, "verdict": "noise",
                              "reason": "测试种子：页眉目录噪音" },
                            { "from": 10, "to": 19, "verdict": "requirement",
                              "reason": "测试种子：技术参数段" }
                        ] }),
                },
            );
            match marks {
                bid_mcp::ToolReply::Ok(_) => {}
                bid_mcp::ToolReply::Err { error, .. } => panic!("标记失败：{error}"),
            }
            svc.checkpoint().unwrap();
        }
        // 公开 IPC 面（ctx 服务实例与种子实例独立——跨实例持久化恢复面）
        let ctx = Ctx::new(Workspace::new(&dir).unwrap(), PathBuf::new());
        let frame = call(&ctx, "bid.coverage");
        assert_eq!(frame["ok"], json!(true), "{frame}");
        let c = ok_of(&frame).clone();
        assert_eq!(c["present"], json!(true));
        assert_eq!(c["project"]["name"], "覆盖测试项目");
        // 工具输出原样透传（主体面）
        let cov = &c["coverage"];
        let total = cov["total_blocks"].as_u64().expect("total_blocks 恒在");
        assert!(total > 0, "真件链应有块（corpus-A 主文件 182 块量级）");
        let files = cov["files"].as_array().expect("files 恒为数组");
        assert_eq!(files.len(), 1);
        assert_eq!(files[0]["file_id"], json!(file_id));
        // 三态分账（#244）：A 判定 + B 排除 + C 未判定 = total（探针实测口径）
        let s = &c["summary"];
        let (a, b, cc) = (
            s["judged_blocks"].as_u64().expect("judged_blocks 恒在"),
            s["excluded_blocks"].as_u64().expect("excluded_blocks 恒在"),
            s["unjudged_blocks"].as_u64().expect("unjudged_blocks 恒在"),
        );
        assert_eq!((a, b), (10, 10), "种子标记 10 noise + 10 requirement：{s}");
        assert_eq!(a + b + cc, total, "三态分账不漏不重：{s}（total={total}）");
        assert_eq!(s["total_blocks"], json!(total));
        assert_eq!(s["complete"], json!(false));
        assert!(cc > 0, "只标了 20 块——C 态应非零");
        // by_verdict 聚合（BTreeMap 键序——断言可依赖）
        assert_eq!(s["by_verdict"]["noise"], json!(10));
        assert_eq!(s["by_verdict"]["requirement"], json!(10));
        // ★面：corpus-A 主文件无真值★ → 全零；恒等式仍成立（不赌具体件）
        let st = &c["star"];
        let sf = st["files"].as_array().expect("star.files 恒为数组");
        assert_eq!(sf.len(), 1);
        assert_eq!(sf[0]["file_name"], "A-招标文件.docx");
        let t = &st["total"];
        assert_eq!(
            t["star_truth"].as_u64().unwrap(),
            t["star_captured"].as_u64().unwrap() + t["star_missing"].as_u64().unwrap(),
            "★口径恒等式：truth = captured + missing"
        );
        assert_eq!(
            t["star_total"].as_u64().unwrap(),
            t["declarations"].as_u64().unwrap() + t["star_truth"].as_u64().unwrap(),
            "★口径恒等式：total = declarations + truth"
        );
        let _ = std::fs::remove_dir_all(dir);
    }

}
