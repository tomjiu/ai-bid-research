//! contract.rs — db.json / trace.jsonl / blocks.jsonl 的冻结契约结构（grade.py M1 契约）
//!
//! 纪律（与 scripts/grade.py docstring 逐字段对齐）：
//! - M1 能诚实产出的字段全部产出；M2/M3/M4 范围字段（matrix/citation/findings/conflicts/
//!   sections 内容/export/recheck/resume_plan）**一律不出现**——判分器按缺字段诚实 FAIL，
//!   不得造假绿。
//! - 不允许任何时间戳/随机值进入输出（REQ-ID/chunk_id 全部内容寻址）——双跑字节一致。
//! - REQ 不自报 gt_ids（诚实管道不知道 ground truth）——召回判定只依赖判分器对齐器。

use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};

// ---------------------------------------------------------------- 内容寻址 ID
pub fn content_hash(parts: &[&str]) -> String {
    let mut h = Sha256::new();
    for p in parts {
        h.update(p.as_bytes());
        h.update([0x1f]); // 分隔符防拼接歧义
    }
    format!("{:x}", h.finalize())
}

// ---------------------------------------------------------------- blocks.jsonl
#[derive(Serialize, Deserialize, Clone, Debug)]
pub struct Block {
    pub file: String,    // 相对 corpus 名："A-招标文件.docx" / "evidence/EV-01-营业执照.pdf"
    pub kind: String,    // Para | Heading | TableRow | TableCell | XlsxRow | PdfLine | OcrLine
    pub locator: String, // 确定性定位："第三章 投标人须知 > 二、投标人资格要求 #p5 / p.2"
    pub page: u32,       // 0 = 非分页格式（docx 按分页符估算）
    pub text: String,
    pub order: u32,      // 全局导入顺序（搜索确定性 tie-breaker）
}

// ---------------------------------------------------------------- per-file 解析报告（V1-a 证据）
#[derive(Serialize, Clone, Debug)]
pub struct ParseReport {
    pub file: String,
    pub kind: String, // docx | pdf-text | xlsx | pdf-scan(ocr) | unknown
    pub blocks: usize,
    pub paras: usize,
    pub tables: usize,
    pub rows: usize,
    pub chars: usize,
    pub pages: u32,
    pub ocr_blocks: Option<u32>,
    pub failures: Vec<String>,
}

// ---------------------------------------------------------------- db.json 字段结构
#[derive(Serialize, Clone, Debug)]
pub struct Anchor {
    pub file: String,
    pub kind: String,
    pub locator: String,
    pub excerpt: String,
}

#[derive(Serialize, Clone, Debug)]
pub struct Req {
    pub req_id: String, // REQ-<内容哈希前 10 位>（clause_no+首锚点）——重跑零漂移
    pub gt_ids: Vec<String>, // 恒空：召回只认判分器对齐器（反标记回声纪律）
    pub category: String, // 六类封闭枚举
    pub clause_no: String,
    pub anchors: Vec<Anchor>,
    pub params: serde_json::Map<String, serde_json::Value>,
}

#[derive(Serialize, Clone, Debug)]
pub struct FileStat {
    pub name: String,
    pub parse_status: String, // ok | ocr_required | failed
    #[serde(skip_serializing_if = "Option::is_none")]
    pub ocr_blocks: Option<u32>,
}

#[derive(Serialize, Clone, Debug)]
pub struct QueryHit {
    pub query_id: String,
    pub hit: bool,
    pub hit_text: String,
    pub hit_file: String,
    pub block_order: u32,
    pub coverage: f64,
}

// ---------------------------------------------------------------- trace.jsonl
#[derive(Serialize, Clone, Debug)]
pub struct TraceEntry {
    pub seq: u32,
    pub tool: String,
    pub args: serde_json::Value,
    pub result: serde_json::Value,
}
