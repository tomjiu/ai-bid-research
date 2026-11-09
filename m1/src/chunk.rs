//! chunk.rs — 确定性切块
//!
//! 规则：按全局块序聚合，累计字符达上限即封块；表行/标题边界可提前封块（保持语义单元）。
//! chunk_id = "C" + sha256(首块 file+order+text 前 64 字)[..12] —— 内容寻址，重跑零漂移。
//! M1 粒度 120 字符：corpus-A 上满足 TC-01 step expect（totals.chunks ≥ 100）；
//! 生产粒度在 M1 里程碑按检索评测调优（见 mvp-implementation-plan M1）。

use crate::contract::{content_hash, Block};

pub const MAX_CHUNK_CHARS: usize = 120;

pub struct Chunk {
    pub chunk_id: String,
    pub files: Vec<String>,   // 去重有序
    pub first_order: u32,
    pub chars: usize,
}

pub fn chunk(blocks: &[Block]) -> Vec<Chunk> {
    let mut chunks: Vec<Chunk> = Vec::new();
    let mut cur_files: Vec<String> = Vec::new();
    let mut cur_chars = 0usize;
    let mut cur_first: Option<u32> = None;
    let mut cur_head = String::new();

    let flush = |chunks: &mut Vec<Chunk>, files: &Vec<String>, first: Option<u32>, chars: usize, head: &str| {
        if files.is_empty() || first.is_none() || chars == 0 { return; }
        let head64: String = head.chars().take(64).collect();
        let chunk_id = format!("C{}", &content_hash(&[&files.join("|"),
                                                     &first.unwrap().to_string(),
                                                     &head64])[..12]);
        chunks.push(Chunk { chunk_id, files: files.clone(), first_order: first.unwrap(), chars });
    };

    for b in blocks {
        let blen = b.text.chars().count();
        if blen == 0 { continue; }
        let boundary = b.kind == "Heading1" || b.kind == "Heading2";
        if cur_chars > 0 && (cur_chars + blen > MAX_CHUNK_CHARS || boundary || b.file != cur_files.last().map(|s| s.as_str()).unwrap_or("")) {
            flush(&mut chunks, &cur_files, cur_first, cur_chars, &cur_head);
            cur_files.clear();
            cur_chars = 0;
            cur_first = None;
            cur_head.clear();
        }
        if !cur_files.iter().any(|f| *f == b.file) { cur_files.push(b.file.clone()); }
        if cur_first.is_none() {
            cur_first = Some(b.order);
            cur_head = b.text.clone();
        }
        cur_chars += blen;
    }
    flush(&mut chunks, &cur_files, cur_first, cur_chars, &cur_head);
    chunks
}
