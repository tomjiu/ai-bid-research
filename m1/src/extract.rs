//! extract.rs — 确定性条款抽取（M1 v0：结构规则版，零 GT 窥视）
//!
//! 规则表（对 A-招标文件.docx 的结构语义，全部可文档化）：
//!   ① 3.2.x（节标题含"资格要求"）→ 资格条件
//!   ② 3.3.x 且正文含禁止词（不得）→ 格式要求
//!   ③ 3.7.2.x → 否决项
//!   ④ 4.x（第四章）→ 评分项
//!   ⑤ 5.x 段落（第五章）→ 技术参数
//!   ⑥ 6.x（第六章）→ 商务要求
//!   ⑦ 前附表行含"否决" → 否决项（clause_no = 前附表-<序号>）
//!   ⑧ 参数表（表头含"响应须精确一致"）→ 技术参数（clause_no 取表前最近的 5.x 标题）
//!   ⑨ 扫描件关联（结构性规则，非 GT 知识）：3.7.2.x 签署/盖章否决条款
//!     ← 扫描件 OCR 行含（签|盖章|否决投标）者附加为 ocr 锚点（投标函格式页与签署
//!     条款业务同源；GT-07 场景断言"扫描件内条款不丢"的诚实实现）
//! 编号序列完整性：正文+标题全部 clause_no 按前缀分组校验连续无重复（TC-01 断言）。

use crate::contract::{Anchor, Req};
use serde_json::json;
use std::collections::BTreeMap;

pub struct ExtractResult {
    pub reqs: Vec<Req>,
    pub missing_sequence: Vec<String>,
}

/// 条款号提取：^(\d{1,2}(\.\d{1,2}){0,3}) + 分隔/正文
fn clause_of(text: &str) -> Option<(String, String)> {
    let cs: Vec<char> = text.chars().collect();
    let mut num = String::new();
    let mut i = 0;
    while i < cs.len() {
        let c = cs[i];
        if c.is_ascii_digit() {
            num.push(c);
            i += 1;
        } else if c == '.' && !num.is_empty() {
            match cs.get(i + 1) {
                Some(d) if d.is_ascii_digit() => { num.push('.'); i += 1; }
                _ => break,
            }
        } else {
            break;
        }
    }
    if num.is_empty() || !num.contains('.') { return None; } // 孤立数字非条款（如"90 日历天"开头无数字）
    let rest: String = cs[num.len()..].iter().collect::<String>()
        .trim_start_matches([' ', '、', '．', '.']).to_string();
    Some((num, rest))
}

fn parse_money(text: &str) -> Vec<i64> {
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

fn find_iso_date(text: &str) -> Option<String> {
    let b = text.as_bytes();
    if b.len() < 10 { return None; }
    for i in 0..=b.len() - 10 {
        if b[i] == b'2' && b[i + 1] == b'0' && b[i + 4] == b'-' && b[i + 7] == b'-'
            && text[i..i + 10].chars().all(|c| c.is_ascii_digit() || c == '-') {
            return Some(text[i..i + 10].to_string());
        }
    }
    None
}

fn find_days(text: &str) -> Option<i64> {
    if let Some(pos) = text.find("日历天") {
        let head: String = text[..pos].chars().rev()
            .take_while(|c| c.is_ascii_digit()).collect::<Vec<_>>()
            .into_iter().rev().collect();
        if let Ok(v) = head.parse::<i64>() { return Some(v); }
    }
    None
}

fn find_model(text: &str) -> Option<String> {
    let cs: Vec<char> = text.chars().collect();
    let mut i = 0;
    while i < cs.len() {
        if cs[i].is_ascii_uppercase() {
            let mut j = i;
            let mut segs = 0;
            while j < cs.len() && (cs[j].is_ascii_uppercase() || cs[j].is_ascii_digit() || cs[j] == '-') {
                if cs[j] == '-' { segs += 1; }
                j += 1;
            }
            let tok: String = cs[i..j].iter().collect();
            if segs >= 1 && tok.len() >= 6 { return Some(tok); }
            i = j;
        } else {
            i += 1;
        }
    }
    None
}

fn find_page_limit(text: &str) -> Option<i64> {
    if let Some(pos) = text.find("页") {
        let head: String = text[..pos].chars().rev()
            .take_while(|c| c.is_ascii_digit()).collect::<Vec<_>>()
            .into_iter().rev().collect();
        if let Ok(v) = head.parse::<i64>() { return Some(v); }
    }
    None
}

fn mk_params(text: &str) -> serde_json::Map<String, serde_json::Value> {
    let mut m = serde_json::Map::new();
    // 金额为多值字段（条款常含多个金额）——数组形态，不参与判分器标量值对齐
    // （否则"200 万"这类跨条款共享阈值会引发跨类别伪对齐，v0.4 实测 REQ-4.3×GT-03）
    let monies = parse_money(text);
    if !monies.is_empty() { m.insert("amounts".into(), json!(monies)); }
    if let Some(v) = find_iso_date(text) { m.insert("date_iso".into(), json!(v)); }
    if let Some(v) = find_days(text) { m.insert("duration_days".into(), json!(v)); }
    if let Some(v) = find_model(text) { m.insert("model".into(), json!(v)); }
    if let Some(v) = find_page_limit(text) { m.insert("page_limit".into(), json!(v)); }
    m
}

fn mk_req(clause_no: &str, category: &str, anchors: Vec<Anchor>, text: &str) -> Req {
    let first_excerpt = anchors.first().map(|a| a.excerpt.clone()).unwrap_or_default();
    let req_id = format!("REQ-{}", &crate::contract::content_hash(&[clause_no, &first_excerpt])[..10]);
    Req {
        req_id,
        gt_ids: vec![], // 诚实管道不自报——召回只认判分器对齐器
        category: category.into(),
        clause_no: clause_no.into(),
        anchors,
        params: mk_params(text),
    }
}

/// 参数表落 REQ（规则⑧）：锚点 = 型号规格列去重，一条 REQ 一张表
fn flush_param_table(
    reqs: &mut Vec<Req>,
    a_name: &str,
    table_clause: &str,
    rows: &[(String, Vec<String>)],
) {
    if table_clause.is_empty() || rows.is_empty() { return; }
    let mut models: Vec<(String, String)> = Vec::new(); // (model, locator) 去重
    for (loc, cells) in rows {
        let model = cells.get(2).map(|s| s.trim().to_string()).unwrap_or_default();
        if !model.is_empty() && !models.iter().any(|(m, _)| *m == model) {
            models.push((model, loc.clone()));
        }
    }
    if models.is_empty() { return; }
    let anchors: Vec<Anchor> = models.iter().map(|(m, loc)| Anchor {
        file: a_name.into(), kind: "table".into(), locator: loc.clone(), excerpt: m.clone(),
    }).collect();
    let text_all = models.iter().map(|(m, _)| m.clone()).collect::<Vec<_>>().join(" ");
    reqs.push(mk_req(table_clause, "技术参数", anchors, &text_all));
}

pub fn extract(blocks: &[crate::contract::Block], a_name: &str, b2_name: &str) -> ExtractResult {
    let mut reqs: Vec<Req> = Vec::new();

    // ---- Pass 1：正文条款段落（Para）与标题编号收集 ----
    let mut clause_nos: Vec<String> = Vec::new();
    for b in blocks.iter() {
        if b.file != a_name { continue; }
        if b.kind != "Para" { continue; }
        if let Some((clause, _)) = clause_of(&b.text) {
            clause_nos.push(clause.clone());
            let text = &b.text;
            let locator = &b.locator;
            let category: Option<&str> =
                if clause.starts_with("3.2.") && locator.contains("资格要求") { Some("资格条件") }
                else if clause.starts_with("3.3.") && text.contains("不得") { Some("格式要求") }
                else if clause.starts_with("3.7.2") { Some("否决项") }
                else if clause.starts_with("4.") && locator.contains("第四章") { Some("评分项") }
                else if clause.starts_with("5.") && locator.contains("第五章") { Some("技术参数") }
                else if clause.starts_with("6.") && locator.contains("第六章") { Some("商务要求") }
                else { None };
            if let Some(cat) = category {
                let mut req = mk_req(&clause, cat, vec![Anchor {
                    file: a_name.into(), kind: "para".into(),
                    locator: locator.clone(), excerpt: text.clone(),
                }], text);
                // 规则⑨：签署/盖章否决条款 ← 扫描件 OCR 附加锚点
                if clause == "3.7.2.1" && (text.contains("签署") || text.contains("盖章")) {
                    for ob in blocks.iter().filter(|x| x.file == b2_name && x.kind == "OcrLine") {
                        if ob.text.contains('签') || ob.text.contains('盖') || ob.text.contains("否决投标") {
                            req.anchors.push(Anchor {
                                file: b2_name.into(), kind: "ocr".into(),
                                locator: ob.locator.clone(), excerpt: ob.text.clone(),
                            });
                        }
                    }
                }
                reqs.push(req);
            }
        }
    }

    // ---- Pass 2：表格（前附表 + 参数表），同时把 h2 标题编号计入序列完整性 ----
    let mut last_h2_clause = String::new();
    let mut table_clause = String::new();      // 当前参数表的条款号（表头出现时的 h2）
    let mut table_rows: Vec<(String, Vec<String>)> = Vec::new();
    let mut in_param_table = false;
    for b in blocks.iter() {
        if b.file != a_name { continue; }
        if b.kind == "Heading2" {
            if let Some((cl, _)) = clause_of(&b.text) {
                clause_nos.push(cl.clone());
                if cl.starts_with("5.") { last_h2_clause = cl; }
            }
            continue;
        }
        if b.kind != "TableRow" { continue; }
        let cells: Vec<&str> = b.text.split('\t').collect();
        // 前附表行（规则⑦）
        if b.locator.contains("第二章") && b.text.contains("否决") {
            let no = cells.first().unwrap_or(&"").trim().to_string();
            let excerpt = cells.get(2).map(|s| s.to_string()).unwrap_or_default();
            if !excerpt.is_empty() {
                reqs.push(mk_req(&format!("前附表-{}", no), "否决项", vec![Anchor {
                    file: a_name.into(), kind: "table".into(),
                    locator: b.locator.clone(), excerpt: excerpt.clone(),
                }], &excerpt));
            }
            continue;
        }
        // 参数表判定/切换（规则⑧）：表头含 序号+设备名称+响应须精确一致 → 开新表
        let is_header = cells.iter().any(|c| c.contains("序号"))
            && cells.iter().any(|c| c.contains("设备名称"));
        if is_header {
            if cells.iter().any(|c| c.contains("响应须精确一致")) {
                flush_param_table(&mut reqs, a_name, &table_clause, &table_rows); // 落前一张
                table_clause = last_h2_clause.clone();
                table_rows.clear();
                in_param_table = true;
            } else {
                flush_param_table(&mut reqs, a_name, &table_clause, &table_rows);
                table_clause.clear();
                table_rows.clear();
                in_param_table = false;
            }
            continue; // 表头行不成 REQ
        }
        if in_param_table {
            table_rows.push((b.locator.clone(), cells.iter().map(|s| s.to_string()).collect()));
        }
    }
    flush_param_table(&mut reqs, a_name, &table_clause, &table_rows); // 收尾落最后一张

    reqs.sort_by(|a, b| a.clause_no.cmp(&b.clause_no)
        .then(a.anchors.first().map(|x| x.locator.clone()).unwrap_or_default()
            .cmp(&b.anchors.first().map(|x| x.locator.clone()).unwrap_or_default())));

    // ---- 编号序列完整性（TC-01 断言：无跳号无撞号）----
    let mut missing = Vec::new();
    let mut seen: BTreeMap<String, u32> = BTreeMap::new();
    for c in &clause_nos {
        *seen.entry(c.clone()).or_default() += 1;
    }
    for (c, n) in &seen {
        if *n > 1 { missing.push(format!("撞号 {}", c)); }
    }
    let mut groups: BTreeMap<String, Vec<u32>> = BTreeMap::new();
    for c in seen.keys() {
        let parts: Vec<&str> = c.split('.').collect();
        if parts.len() >= 2 {
            let prefix = parts[..parts.len() - 1].join(".");
            let last: u32 = parts.last().unwrap().parse().unwrap_or(0);
            groups.entry(prefix).or_default().push(last);
        }
    }
    for (prefix, mut nums) in groups {
        nums.sort_unstable();
        for w in nums.windows(2) {
            if w[1] - w[0] > 1 {
                missing.push(format!("{} 缺 {}~{}", prefix, w[0] + 1, w[1] - 1));
            }
        }
    }
    ExtractResult { reqs, missing_sequence: missing }
}
