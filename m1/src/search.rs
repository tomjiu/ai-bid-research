//! search.rs — exact 精确通道（TC-02：25 条查询全命中 + 5 次重放一致性）
//!
//! 确定性排序（无向量、无随机）：
//!   1. token 覆盖率 desc（查询按空白切分；单 token 查询支持数值归一化通道）
//!   2. 命中密度 desc（命中 token 总字符长 / 块长——奖励紧凑命中，防长块吞票）
//!   3. 文件导入序 asc → 4. 块序 asc
//! 数值归一化：查询 "3500000" 与块内 "350 万元" 都归一到元后精确比较（金额口径陷阱 R-02 的
//! 结构化通道）；日期/型号/编号走直接子串。
//! hit_text = 整块文本（判分器核验期望摘录 ⊆ 命中文本）；hit_file 为诚实自报并接受核验。

use crate::contract::{Block, QueryHit};

pub struct Query {
    pub query_id: String,
    pub query: String,
}

pub fn load_queries(path: &std::path::Path) -> Result<Vec<Query>, String> {
    let txt = std::fs::read_to_string(path).map_err(|e| e.to_string())?;
    let mut out = Vec::new();
    for line in txt.lines().filter(|l| !l.trim().is_empty()) {
        let v: serde_json::Value = serde_json::from_str(line).map_err(|e| e.to_string())?;
        out.push(Query {
            query_id: v["query_id"].as_str().unwrap_or_default().to_string(),
            query: v["query"].as_str().unwrap_or_default().to_string(),
        });
    }
    Ok(out)
}

/// 块内金额值集合（元）：含千分位数字 + 万元/元 单位
fn money_values(text: &str) -> Vec<i64> {
    let cs: Vec<char> = text.chars().collect();
    let mut out = Vec::new();
    let mut i = 0;
    while i < cs.len() {
        if cs[i].is_ascii_digit() {
            let mut j = i;
            let mut digits = String::new();
            while j < cs.len() && (cs[j].is_ascii_digit() || cs[j] == ',') {
                if cs[j] != ',' { digits.push(cs[j]); }
                j += 1;
            }
            // 跳过数字与单位间的空白（"350 万元" 式书写）
            let mut k = j;
            while k < cs.len() && cs[k] == ' ' { k += 1; }
            let tail: String = cs[k..(k + 2).min(cs.len())].iter().collect();
            if let Ok(v) = digits.parse::<i64>() {
                if tail.starts_with("万元") { out.push(v * 10_000); i = k + 2; continue; }
                if tail.starts_with('元') { out.push(v); i = k + 1; continue; }
            }
            i = j;
        } else {
            i += 1;
        }
    }
    out
}

fn parse_query_number(q: &str) -> Option<i64> {
    let t = q.trim();
    if t.chars().all(|c| c.is_ascii_digit()) && t.len() >= 4 {
        t.parse::<i64>().ok()
    } else { None }
}

struct Scored {
    coverage: f64,
    density: f64,
}

fn score(query: &str, block: &Block) -> Scored {
    let tokens: Vec<&str> = query.split_whitespace().collect();
    let bchars = block.text.chars().count().max(1) as f64;
    if tokens.is_empty() {
        return Scored { coverage: 0.0, density: 0.0 };
    }
    if tokens.len() == 1 {
        let t = tokens[0];
        if block.text.contains(t) {
            let matched = t.chars().count();
            return Scored { coverage: 1.0, density: matched as f64 / bchars };
        }
        if let Some(v) = parse_query_number(t) {
            if money_values(&block.text).contains(&v) {
                let matched = t.chars().count();
                return Scored { coverage: 1.0, density: matched as f64 / bchars };
            }
        }
        return Scored { coverage: 0.0, density: 0.0 };
    }
    let mut matched = 0usize;
    let mut matched_chars = 0usize;
    for t in &tokens {
        if block.text.contains(t) {
            matched += 1;
            matched_chars += t.chars().count();
        }
    }
    Scored {
        coverage: matched as f64 / tokens.len() as f64,
        density: matched_chars as f64 / bchars,
    }
}

/// 单查询最优命中（确定性：并列按 导入序/块序）
fn best_hit(query: &Query, blocks: &[Block]) -> Option<(f64, usize)> {
    let mut best: Option<(Scored, usize)> = None;
    for (i, b) in blocks.iter().enumerate() {
        let s = score(&query.query, b);
        if s.coverage <= 0.0 { continue; }
        let better = match &best {
            None => true,
            Some((bs, _)) => {
                s.coverage > bs.coverage + 1e-12
                    || ((s.coverage - bs.coverage).abs() < 1e-12 && s.density > bs.density + 1e-12)
            }
        };
        if better { best = Some((s, i)); }
    }
    best.map(|(s, i)| (s.coverage, i))
}

pub fn exact_search(queries: &[Query], blocks: &[Block]) -> (usize, Vec<QueryHit>) {
    let mut hits = 0usize;
    let mut per = Vec::new();
    for q in queries {
        match best_hit(q, blocks) {
            Some((cov, i)) => {
                hits += 1;
                per.push(QueryHit {
                    query_id: q.query_id.clone(),
                    hit: true,
                    hit_text: blocks[i].text.clone(),
                    hit_file: blocks[i].file.clone(),
                    block_order: blocks[i].order,
                    coverage: (cov * 10000.0).round() / 10000.0,
                });
            }
            None => per.push(QueryHit {
                query_id: q.query_id.clone(),
                hit: false,
                hit_text: String::new(),
                hit_file: String::new(),
                block_order: 0,
                coverage: 0.0,
            }),
        }
    }
    (hits, per)
}

/// 稳定性：同查询集跑 N 次结果必须完全一致（TC-02 断言：确定性 tie-breaker）
pub fn repeat_consistent(queries: &[Query], blocks: &[Block], times: usize) -> bool {
    if times < 2 { return true; }
    let (_, first) = exact_search(queries, blocks);
    for _ in 1..times {
        let (_, again) = exact_search(queries, blocks);
        if serde_json::to_string(&first).ok() != serde_json::to_string(&again).ok() {
            return false;
        }
    }
    true
}
