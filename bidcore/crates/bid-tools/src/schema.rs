//! db.json / trace.jsonl 运行产物契约（单一真源 = 本文件 serde 类型）。
//!
//! **这是跨语言兼容问题的解法**：判分器（bid-grade）依赖本 crate 的类型反序列化运行产物——
//! 后端与判分器共享同一组编译期类型，schema 漂移在编译期即被捕获，无需 docstring 约定。
//! 字段口径与 scripts/grade.py docstring 冻结的 v0 契约对齐；M2+ 面以 Option 显式占位。

use serde::{Deserialize, Serialize};
use std::collections::HashMap;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RunDb {
    pub scenario: String,   // "TC-01" | "TC-02" | ... | "full"
    pub milestone: String,  // "M1" | "M2" | ...
    pub project: ProjectInfo,
    pub files: Vec<FileInfo>,
    pub totals: Totals,
    pub parse: ParseInfo,
    pub requirements: Vec<ReqInfo>,
    /// M2+：矩阵（G3）。M1 运行留空。
    pub matrix: Vec<serde_json::Value>,
    /// M2+：引用覆盖（G4）。M1 运行留空。
    pub citation: Option<CitationInfo>,
    /// M4+：审校发现（G6）。M1 运行留空。
    pub findings: Vec<FindingInfo>,
    pub exact: Option<ExactInfo>,
    pub conflicts: Vec<serde_json::Value>,
    pub idempotency: Option<IdempotencyInfo>,
    pub sections: Vec<SectionInfo>,
    pub recheck: HashMap<String, String>,
    pub export: Option<serde_json::Value>,
    pub resume_plan: Option<serde_json::Value>,
    pub stability: Option<StabilityInfo>,
    pub last_tool_result: LastToolResult,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProjectInfo {
    pub status: String,
    pub content_version: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FileInfo {
    pub name: String,
    pub kind: String,
    pub sha256: String,
    pub pages: usize,
    pub tables: usize,
    pub chunks: usize,
    pub ocr_blocks: usize,
    pub parse_status: String, // ok | ocr_required | failed
    pub parse_summary: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Totals {
    pub files: usize,
    pub chunks: usize,
    pub parse_failed: usize,
    pub ocr_required: usize,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ParseInfo {
    pub missing_sequence: Vec<MissingSeq>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MissingSeq {
    pub file_id: String,
    pub prefix: String,
    pub expected: String,
    pub found: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ReqInfo {
    pub req_id: String,
    /// 自报 GT 覆盖（反标记纪律：语料无标记时为空——召回只认判分器对齐器）
    pub gt_ids: Vec<String>,
    pub category: String,
    pub clause_no: Option<String>,
    pub anchors: Vec<AnchorInfo>,
    pub params: HashMap<String, serde_json::Value>,
    pub source_file: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AnchorInfo {
    pub file: String,
    pub kind: String,
    pub locator: String,
    pub excerpt: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CitationInfo {
    pub unanchored_claims: u64,
    pub coverage: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FindingInfo {
    pub rule_code: String,
    pub kind: String,
    pub severity: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ExactInfo {
    pub hits: usize,
    pub per_query: Vec<PerQuery>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PerQuery {
    pub query_id: String,
    pub hit: bool,
    pub hit_text: String,
    pub hit_file: String,
    pub repeats_consistent: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct IdempotencyInfo {
    pub files_before: u64,
    pub files_after: u64,
    pub totals_before: u64,
    pub totals_after: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SectionInfo {
    pub id: String,
    pub status: String,
    pub dirty: bool,
    pub last_model: Option<String>,
    pub rerun_count: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StabilityInfo {
    pub repeat_consistent: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LastToolResult {
    pub error: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TraceEntry {
    pub tool: String,
    pub ok: bool,
    pub error: Option<String>,
    pub project_version: u64,
    pub note: String,
}
