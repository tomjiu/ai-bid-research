//! 反标记回声对齐器（v0.3 口径的 Rust 移植 + OCR 噪声归一化）。
//!
//! 纪律：召回判定只认对齐器——条款号双因子（clause_no + 佐证）/ 锚点互含（长度约束）/
//! 唯一参数值。自报 gt_id 无法对齐的计入 unverified 不计召回。
//! 归一化升级（v0.4）：锚点互含比较在 N2 归一空间（NFKC + 去空白 + 去标点）进行——
//! OCR 通道的标点噪声（；↔，↔; ）不得再造成假阴性；长度约束同样在归一空间计量。

use crate::fixtures::{GtRequirement, GtAnchor};
use bid_parse::{norm_n1, norm_n2};
use bid_tools::schema::ReqInfo;
use serde_json::Value;
use std::collections::{HashMap, HashSet};

/// 值→GT 集合中的模糊值（跨多 GT 共享 → 不参与参数对齐）。
pub fn ambiguous_values(gts: &[GtRequirement]) -> HashSet<String> {
    let mut m: HashMap<String, HashSet<String>> = HashMap::new();
    for gt in gts {
        if let Some(p) = gt.params.as_object() {
            for v in p.values() {
                if let Some(key) = param_key(v) {
                    m.entry(key).or_default().insert(gt.gt_id.clone());
                }
            }
        }
    }
    m.into_iter().filter(|(_, s)| s.len() > 1).map(|(k, _)| k).collect()
}

/// 参数值参与对齐的准入：字符串 ≥6 字符（归一后）或数值 ≥10000。
fn param_key(v: &Value) -> Option<String> {
    match v {
        Value::String(s) => {
            let n = norm_n1(s);
            if n.chars().count() >= 6 {
                Some(n)
            } else {
                None
            }
        }
        Value::Number(x) => x.as_f64().filter(|f| f.abs() >= 10_000.0).map(|f| f.to_string()),
        _ => None,
    }
}

fn gt_param_values(gt: &GtRequirement, amb: &HashSet<String>) -> HashSet<String> {
    let mut out = HashSet::new();
    if let Some(p) = gt.params.as_object() {
        for v in p.values() {
            if let Some(k) = param_key(v) {
                if !amb.contains(&k) {
                    out.insert(k);
                }
            }
        }
    }
    out
}

fn req_param_values(req: &ReqInfo, amb: &HashSet<String>) -> HashSet<String> {
    let mut out = HashSet::new();
    for v in req.params.values() {
        if let Some(k) = param_key(v) {
            if !amb.contains(&k) {
                out.insert(k);
            }
        }
    }
    out
}

fn gt_clause_nos(gt: &GtRequirement) -> Vec<String> {
    match &gt.clause_no {
        Some(Value::String(s)) => vec![s.clone()],
        Some(Value::Array(a)) => a.iter().filter_map(|x| x.as_str().map(String::from)).collect(),
        _ => vec![],
    }
}

/// 单条 REQ 对齐到的 GT 集合（确定性三通道）。
pub fn aligned_gt_ids(req: &ReqInfo, gts: &[GtRequirement], amb: &HashSet<String>) -> HashSet<String> {
    let mut ids = HashSet::new();
    let req_clauses: Vec<String> = match &req.clause_no {
        Some(c) => vec![c.clone()],
        None => vec![],
    };
    let req_vals = req_param_values(req, amb);
    let has_corroboration = !req.anchors.is_empty() || !req_vals.is_empty();
    for gt in gts {
        // 通道①：条款号双因子
        if !req_clauses.is_empty()
            && gt_clause_nos(gt).iter().any(|c| req_clauses.contains(c))
            && has_corroboration
        {
            ids.insert(gt.gt_id.clone());
            continue;
        }
        // 通道②：锚点互含（N2 归一空间 + 长度约束）
        let mut hit = false;
        for ga in &gt.anchors {
            let gex = norm_n2(&ga.excerpt);
            if gex.chars().count() < 8 {
                continue; // GT 摘录过短不参与（防碎片命中）
            }
            for a in &req.anchors {
                let ex = norm_n2(&a.excerpt);
                if ex.is_empty() {
                    continue;
                }
                if ex.contains(&gex) && ex.chars().count() <= 3 * gex.chars().count() {
                    hit = true; // GT ⊆ REQ 且 REQ 不超 3×（防全文锚点）
                } else if gex.contains(&ex) && ex.chars().count() >= 8 {
                    hit = true; // REQ ⊆ GT（防碎片锚点）
                }
                if hit {
                    break;
                }
            }
            if hit {
                break;
            }
        }
        // 通道③：唯一参数值相等
        if !hit {
            let gt_vals = gt_param_values(gt, amb);
            if gt_vals.intersection(&req_vals).next().is_some() {
                hit = true;
            }
        }
        if hit {
            ids.insert(gt.gt_id.clone());
        }
    }
    ids
}

/// GT 覆盖的锚点聚合数（TC-01 GT-07 双锚点口径：所有对齐到该 GT 的 REQ 锚点总数）。
pub fn aggregate_anchors(gt_id: &str, reqs: &[ReqInfo], gts: &[GtRequirement],
                         amb: &HashSet<String>) -> usize {
    reqs.iter()
        .filter(|r| aligned_gt_ids(r, gts, amb).contains(gt_id))
        .map(|r| r.anchors.len())
        .sum()
}

/// 反推工具：供自测构造（GT 锚点形态）。
pub fn gt_anchor_excerpt(gt: &GtRequirement, idx: usize) -> Option<&GtAnchor> {
    gt.anchors.get(idx)
}
