//! #179（audit F-5 / PR #172 §4 立项）：补遗与主件的**语义级**冲突识别
//! （同主题异号）。
//!
//! ## 问题
//!
//! 最小面冲突检测（extract 的同 clause_no 异文）检不出「A 件 6.1 控制价
//! 480 万 vs C 补遗『三、招标控制价调整』465 万」——**条款号不同**的两
//! 版本 REQ 共在（摘录逐字落盘），无语义归并即不可见。
//!
//! ## 判据（本模块，纯函数）
//!
//! 补遗侧 REQ × 主件侧 REQ 满足：
//! 1. **同主题**：高价值三字段——控制价（控制价/最高限价同族等价；
//!    **预算不入本主题**——corpus-A 实证同行并存「预算 350 万 + 控制价
//!    480 万」，预算与控制价是可分字段，混配即假冲突）、工期（工期/
//!    服务期/交付期/供货期/完成期限/施工期限——**关键字须两侧字面
//!    一致**，不同字面是不同字段不配对）、保证金（投标保证金/履约
//!    保证金/保证金——同左）；
//! 2. **有值**：主题邻接值（控制价/保证金=金额万元、元直述 ÷10000 归一；
//!    工期=时长，天/日历天/日 ×1、个月 ×30、周 ×7 归一）。**调整语
//!    感知**：文本含前向调整标记（调整为/调整至/改为/变更为/修改为/
//!    更正为）时取标记**之后**的值——corpus-A 实测形态「…控制价「480
//!    万元」调整为「465 万元」」中新值 465 无主题词邻接（朴素取首
//!    匹配=旧值 480，配错对）。取值链：标记后主题邻接值 → 标记后
//!    同型值（调整子句携带主题语境）→ 首个主题邻接值；
//! 3. **值不同**（|a−b| > 1e-6）；
//! 4. **非同号对**：两侧 clause_no 相同的对子归同号异文面（既有检测）
//!    管，本面跳过防双报。
//!
//! ## 纪律（与 #177 同款提示面）
//!
//! - **不自动改写**：语义冲突只登记可见（conflicts[]），终裁（补遗优先）
//!   走 `register_addendum_changes` 的 value_changed **人工显式登记通道**，
//!   人工确认后生效；
//! - 值归一是**比较口径**不是改写口径——摘录原文随条目透出；
//! - 主题字面保守配对（工期≠服务期、投标保证金≠履约保证金、预算∉控制价）
//!   ——宁可漏（提示面）不可误（假冲突诱导错误终裁）。

use bid_domain::Requirement;
use std::sync::OnceLock;

/// 语义冲突条目（extract 响应 conflicts[] 的素材——tools.rs 转 json）。
#[derive(Debug, Clone, PartialEq)]
pub struct SemanticConflict {
    /// 高价值字段主题：控制价 / 工期 / 保证金。
    pub topic: &'static str,
    /// 主件侧 REQ id（终裁登记的 req_id 候选——现行版本口径在主件）。
    pub main_req_id: String,
    /// 补遗侧 REQ id（新版本来源——resolution hint 的素材）。
    pub addendum_req_id: String,
    /// 主件侧值（比较口径：控制价/保证金=万元、工期=归一天数）。
    pub main_value: f64,
    /// 补遗侧值（同上）。
    pub addendum_value: f64,
    /// 主件侧摘录（截断——reason 展示用）。
    pub main_excerpt: String,
    /// 补遗侧摘录（截断）。
    pub addendum_excerpt: String,
    pub main_clause_no: Option<String>,
    pub addendum_clause_no: Option<String>,
    pub main_source: String,
    pub addendum_source: String,
}

/// 主题 + 值（比较口径）——行文本的主题归并。
struct TopicHit {
    topic: &'static str,
    /// 主题命中的字面关键字（工期/保证金面要求两侧一致才配对；控制价族
    /// 控制价/最高限价视为同字段等价）。
    keyword: &'static str,
    value: f64,
}

/// 候选值（匹配起点 + 比较口径值）。
struct ValPos {
    start: usize,
    value: f64,
}

fn excerpt_of(r: &Requirement) -> String {
    r.anchors
        .iter()
        .map(|a| a.excerpt.as_str())
        .collect::<String>()
}

/// 前向调整标记（补遗的版本语义——标记之后的值是新版本）。
/// 「调整后控制价」的「调整后」是回指不是前向标记——不入选。
fn adjustment_marker_positions(text: &str) -> Vec<usize> {
    static RE: OnceLock<regex::Regex> = OnceLock::new();
    let re = RE.get_or_init(|| {
        regex::Regex::new(r"(调整为|调整至|改为|变更为|修改为|更正为)").unwrap()
    });
    re.find_iter(text).map(|m| m.end()).collect()
}

/// 调整感知选值（corpus-A 实测形态驱动——见模块文档 §2）：
/// ① 末个前向标记之后的**主题邻接候选**；② 末个标记之后的**同型值**
/// （调整子句携带主题语境：主题词在旧值处，新值不再邻接主题词——
/// 「…控制价「480 万元」调整为「465 万元」」取 465）；③ 无标记/两处
/// 皆无 → 首个主题邻接候选。
fn pick_value(
    cands: &[ValPos],
    text: &str,
    after_marker: &dyn Fn(&str, usize) -> Option<f64>,
) -> Option<f64> {
    if cands.is_empty() {
        return None; // 主题邻接值是主题判定的前提——无候选即无主题
    }
    if let Some(&last) = adjustment_marker_positions(text).last() {
        if let Some(v) = cands.iter().find(|c| c.start >= last) {
            return Some(v.value);
        }
        // ② 标记后同型值（任意起点——调整子句内的新值）
        if let Some(v) = after_marker(text, last) {
            return Some(v);
        }
    }
    cands.first().map(|c| c.value)
}

/// 标记后金额形态（非锚定——首个起点 ≥ from 的万元/元形态；元直述归一 ÷10000）。
fn amount_after(text: &str, from: usize) -> Option<f64> {
    static RE: OnceLock<regex::Regex> = OnceLock::new();
    let re = RE.get_or_init(|| {
        regex::Regex::new(r"(\d[\d,，]*(?:\.\d+)?)\s*(万)?\s*元").unwrap()
    });
    for m in re.find_iter(text) {
        if m.start() < from {
            continue;
        }
        let c = re.captures(m.as_str()).unwrap();
        let raw: f64 = c[1].replace(',', "").replace('，', "").parse().ok()?;
        return Some(if c.get(2).is_some() { raw } else { raw / 10000.0 });
    }
    None
}

/// 标记后时长形态（个月 ×30 / 周 ×7 / 天族 ×1）。
fn duration_after(text: &str, from: usize) -> Option<f64> {
    static RE: OnceLock<regex::Regex> = OnceLock::new();
    let re = RE.get_or_init(|| {
        regex::Regex::new(r"(\d+)\s*(个\s*月|日历天|天|日|周)").unwrap()
    });
    for m in re.find_iter(text) {
        if m.start() < from {
            continue;
        }
        let c = re.captures(m.as_str()).unwrap();
        let n: f64 = c[1].parse().ok()?;
        return Some(match c[2].replace(' ', "").as_str() {
            "个月" => n * 30.0,
            "周" => n * 7.0,
            _ => n,
        });
    }
    None
}

/// 控制价族（控制价/最高限价——同字段两称谓，等价配对；预算∉本主题）。
fn control_price_hit(text: &str) -> Option<TopicHit> {
    static RE: OnceLock<regex::Regex> = OnceLock::new();
    let re = RE.get_or_init(|| {
        regex::Regex::new(
            r"(控制价|最高限价)[^。，；、\n]{0,12}?(\d[\d,，]*(?:\.\d+)?)\s*万?\s*元",
        )
        .unwrap()
    });
    let mut cands: Vec<ValPos> = Vec::new();
    let mut keyword = "控制价";
    for m in re.find_iter(text) {
        let kw_head = &text[m.start()..m.start() + 3];
        if kw_head.starts_with("最高限价") {
            keyword = "最高限价";
        } else {
            keyword = "控制价";
        }
        let c = re.captures(m.as_str()).unwrap();
        let raw: f64 = c[2].replace(',', "").replace('，', "").parse().ok()?;
        let value = if m.as_str().contains('万') {
            raw
        } else {
            raw / 10000.0
        };
        cands.push(ValPos { start: m.start(), value });
    }
    let value = pick_value(&cands, text, &amount_after)?;
    Some(TopicHit { topic: "控制价", keyword, value })
}

/// 工期/服务期/交付期等——字面关键字须两侧一致才配对（不同字面=不同字段）。
fn schedule_hit(text: &str) -> Option<TopicHit> {
    static RE: OnceLock<regex::Regex> = OnceLock::new();
    let re = RE.get_or_init(|| {
        regex::Regex::new(
            r"(工期|服务期|交付期|供货期|完成期限|施工期限)[^。，；、\n]{0,10}?(\d+)\s*(个\s*月|日历天|天|日|周)",
        )
        .unwrap()
    });
    let mut cands: Vec<ValPos> = Vec::new();
    let mut keyword = "工期";
    for m in re.find_iter(text) {
        let c = re.captures(m.as_str()).unwrap();
        let kw: &'static str = match &c[1] {
            "工期" => "工期",
            "服务期" => "服务期",
            "交付期" => "交付期",
            "供货期" => "供货期",
            "完成期限" => "完成期限",
            _ => "施工期限",
        };
        keyword = kw;
        let n: f64 = c[2].parse().ok()?;
        let value = match c[3].replace(' ', "").as_str() {
            "个月" => n * 30.0,
            "周" => n * 7.0,
            _ => n,
        };
        cands.push(ValPos { start: m.start(), value });
    }
    let value = pick_value(&cands, text, &duration_after)?;
    Some(TopicHit { topic: "工期", keyword, value })
}

/// 保证金——投标保证金/履约保证金/裸「保证金」须两侧字面一致才配对。
/// 金额限万元形态（元直述长尾保守不配，宁漏勿误）。
fn deposit_hit(text: &str) -> Option<TopicHit> {
    static RE: OnceLock<regex::Regex> = OnceLock::new();
    let re = RE.get_or_init(|| {
        regex::Regex::new(
            r"(投标保证金|履约保证金|保证金)[^。，；、\n]{0,12}?(\d[\d,，]*(?:\.\d+)?)\s*万\s*元",
        )
        .unwrap()
    });
    let mut cands: Vec<ValPos> = Vec::new();
    let mut keyword = "保证金";
    for m in re.find_iter(text) {
        let c = re.captures(m.as_str()).unwrap();
        let kw: &'static str = match &c[1] {
            "投标保证金" => "投标保证金",
            "履约保证金" => "履约保证金",
            _ => "保证金",
        };
        keyword = kw;
        let value: f64 = c[2].replace(',', "").replace('，', "").parse().ok()?;
        cands.push(ValPos { start: m.start(), value });
    }
    let value = pick_value(&cands, text, &amount_after)?;
    Some(TopicHit { topic: "保证金", keyword, value })
}

/// 单 REQ 的主题命中（控制价 → 保证金 → 工期序）。
fn topic_hit_of(r: &Requirement) -> Option<TopicHit> {
    let text = excerpt_of(r);
    if let Some(h) = control_price_hit(&text) {
        return Some(h);
    }
    if let Some(h) = deposit_hit(&text) {
        return Some(h);
    }
    schedule_hit(&text)
}

/// 语义级冲突配对（纯函数）。
///
/// `is_addendum`：文件名 → 是否补遗件（tools.rs 按 kind=补遗 判定后传入）。
/// 主件侧 = 非补遗 REQ；补遗侧 = 补遗 REQ。同 clause_no 对子跳过
/// （同号异文面既有检测的领地——防双报）。
///
/// 值不同（|a−b| > 1e-6）且主题配对成功 → 登记。同 (主题, 补遗 REQ,
/// 主件值) 折叠为一条——折叠时**优先带条款号的主件 REQ**（终裁登记目标
/// 的可定位性：GT CONFLICT-01 的主件面是 6.1 专项条款，不是总则里的
/// 复述行）。
pub fn semantic_conflicts(
    reqs: &[Requirement],
    is_addendum: &dyn Fn(&str) -> bool,
) -> Vec<SemanticConflict> {
    struct Cand<'a> {
        req: &'a Requirement,
        hit: TopicHit,
        addendum: bool,
    }
    let cands: Vec<Cand> = reqs
        .iter()
        .filter_map(|r| {
            let hit = topic_hit_of(r)?;
            let addendum = is_addendum(&r.source_file);
            Some(Cand { req: r, hit, addendum })
        })
        .collect();
    let mut out: Vec<SemanticConflict> = Vec::new();
    for ad in cands.iter().filter(|c| c.addendum) {
        for main in cands.iter().filter(|c| !c.addendum) {
            // 主题 + 字面关键字配对（控制价族两称谓等价；工期/保证金字面一致）
            let topic_ok = ad.hit.topic == main.hit.topic
                && (ad.hit.topic == "控制价" || ad.hit.keyword == main.hit.keyword);
            if !topic_ok {
                continue;
            }
            // 同号对子归同号异文面（既有检测领地——跳过防双报）
            if ad.req.clause_no.is_some() && ad.req.clause_no == main.req.clause_no {
                continue;
            }
            // 值不同才冲突
            if (ad.hit.value - main.hit.value).abs() <= 1e-6 {
                continue;
            }
            // 折叠：同 (主题, 补遗 REQ, 主件值) 一条——带条款号的主件优先
            let existing = out.iter().position(|c| {
                c.topic == ad.hit.topic
                    && c.addendum_req_id == ad.req.id
                    && (c.main_value - main.hit.value).abs() <= 1e-6
            });
            let into_conflict = |main: &Cand| SemanticConflict {
                topic: ad.hit.topic,
                main_req_id: main.req.id.clone(),
                addendum_req_id: ad.req.id.clone(),
                main_value: main.hit.value,
                addendum_value: ad.hit.value,
                main_excerpt: truncate(&excerpt_of(main.req), 60),
                addendum_excerpt: truncate(&excerpt_of(ad.req), 60),
                main_clause_no: main.req.clause_no.clone(),
                addendum_clause_no: ad.req.clause_no.clone(),
                main_source: main.req.source_file.clone(),
                addendum_source: ad.req.source_file.clone(),
            };
            match existing {
                Some(idx) => {
                    let prefer_new =
                        out[idx].main_clause_no.is_none() && main.req.clause_no.is_some();
                    if prefer_new {
                        out[idx] = into_conflict(main);
                    }
                }
                None => out.push(into_conflict(main)),
            }
        }
    }
    out
}

fn truncate(s: &str, max: usize) -> String {
    if s.chars().count() <= max {
        s.to_string()
    } else {
        s.chars().take(max).collect::<String>() + "…"
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use bid_domain::{Anchor, Requirement};
    use std::collections::HashMap;

    fn req(id: &str, source: &str, clause: Option<&str>, text: &str) -> Requirement {
        Requirement {
            id: id.into(),
            category: "商务要求".into(),
            clause_no: clause.map(str::to_string),
            anchors: vec![Anchor {
                file: source.into(),
                kind: "para".into(),
                locator: "测试章/块".into(),
                excerpt: text.into(),
                block_idx: None,
                page: None,
                line: None,
            }],
            params: HashMap::new(),
            source_file: source.into(),
        }
    }

    /// 验收核心形态（GT CONFLICT-01 同构）：同主题异号 → 检出。
    #[test]
    fn control_price_same_topic_different_clause_detected() {
        let reqs = vec![
            req("REQ-0001", "A-招标文件.docx", Some("6.1"), "招标控制价为人民币 480 万元（含税）。"),
            req("REQ-0121", "C-补遗文件01.docx", Some("三"), "三、招标控制价调整：调整为人民币 465 万元（含税）。"),
        ];
        let is_ad = |n: &str| n.contains("补遗");
        let cs = semantic_conflicts(&reqs, &is_ad);
        assert_eq!(cs.len(), 1, "GT CONFLICT-01 形态必须检出: {cs:?}");
        let c = &cs[0];
        assert_eq!(c.topic, "控制价");
        assert_eq!(c.main_req_id, "REQ-0001");
        assert_eq!(c.addendum_req_id, "REQ-0121");
        assert!((c.main_value - 480.0).abs() < 1e-6);
        assert!((c.addendum_value - 465.0).abs() < 1e-6);
        assert_eq!(c.addendum_source, "C-补遗文件01.docx");
    }

    /// 调整语感知（corpus-A 实测形态）：补遗「…控制价「480 万元」调整为
    /// 「465 万元」」——新值 465 **无主题词邻接**（朴素取首匹配=旧值 480），
    /// 调整子句携带主题语境，取标记后同型值 465。
    #[test]
    fn adjustment_marker_picks_new_value_without_topic_word_adjacency() {
        let reqs = vec![
            req("REQ-0045", "A-招标文件.docx", Some("6.1"), "6.1 招标控制价：本项目招标控制价为人民币 480 万元（含税）。"),
            req("REQ-0121", "C-补遗文件01.docx", None,
                "原招标文件第一章、第六章所列招标控制价「人民币 480 万元（含税）」调整为「人民币 465 万元（含税）」，投标报价超过调整后控制价的作否决投标处理。"),
        ];
        let is_ad = |n: &str| n.contains("补遗");
        let cs = semantic_conflicts(&reqs, &is_ad);
        assert_eq!(cs.len(), 1);
        assert!(
            (cs[0].addendum_value - 465.0).abs() < 1e-6,
            "调整语感知取新值 465（非旧值 480；「调整后」回指不误当选标记）"
        );
        assert!((cs[0].main_value - 480.0).abs() < 1e-6);
    }

    /// 工期调整语感知：「工期由 90 天调整为 60 天」取 60（标记后同型时长）。
    #[test]
    fn schedule_adjustment_picks_new_duration() {
        let reqs = vec![
            req("REQ-0001", "A-招标文件.docx", Some("7.1"), "工期要求：90 日历天。"),
            req("REQ-0121", "C-补遗文件01.docx", Some("四"), "工期由 90 天调整为 60 天。"),
        ];
        let is_ad = |n: &str| n.contains("补遗");
        let cs = semantic_conflicts(&reqs, &is_ad);
        assert_eq!(cs.len(), 1);
        assert!((cs[0].addendum_value - 60.0).abs() < 1e-6, "调整后新工期 60 天");
        assert!((cs[0].main_value - 90.0).abs() < 1e-6);
    }

    /// 预算 ∉ 控制价主题（corpus-A 实证：同行「预算 350 万 + 控制价 480 万」
    /// 并存——预算与控制价是可分字段，混配即 350-vs-480 假冲突）。
    #[test]
    fn budget_is_not_control_price_topic() {
        let hit = control_price_hit("本项目预算金额：设备采购预算 350 万元（含税）；最高限价（招标控制价）：人民币 480 万元（含税）").unwrap();
        assert!((hit.value - 480.0).abs() < 1e-6, "控制价主题取 480 非预算 350");
    }

    /// 折叠偏好：主件同值多 REQ（总则复述 + 专项条款）→ 取带条款号者。
    #[test]
    fn collapse_prefers_main_with_clause_no() {
        let reqs = vec![
            req("REQ-0001", "A-招标文件.docx", None, "最高限价（招标控制价）：人民币 480 万元（含税）。"),
            req("REQ-0045", "A-招标文件.docx", Some("6.1"), "6.1 招标控制价为人民币 480 万元（含税）。"),
            req("REQ-0121", "C-补遗文件01.docx", None, "招标控制价调整为 465 万元。"),
        ];
        let is_ad = |n: &str| n.contains("补遗");
        let cs = semantic_conflicts(&reqs, &is_ad);
        assert_eq!(cs.len(), 1, "同 (主题, 补遗, 主件值) 折叠为一条");
        assert_eq!(cs[0].main_req_id, "REQ-0045", "带条款号的主件优先（终裁可定位）");
        assert_eq!(cs[0].main_clause_no.as_deref(), Some("6.1"));
    }

    /// 同号对子归同号异文面（既有检测领地）——语义面跳过防双报。
    #[test]
    fn same_clause_pair_is_left_to_existing_face() {
        let reqs = vec![
            req("REQ-0001", "A-招标文件.docx", Some("3.1.1"), "投标保证金为人民币 9 万元。"),
            req("REQ-0009", "澄清修改文件-3.1.1.docx", Some("3.1.1"), "投标保证金调整为人民币 12 万元。"),
        ];
        let is_ad = |n: &str| n.contains("澄清");
        assert!(
            semantic_conflicts(&reqs, &is_ad).is_empty(),
            "同号对子（3.1.1）归同号异文面——语义面不双报"
        );
    }

    /// 同主题同值 → 非冲突（补遗复述主件值是常见良性形态）。
    #[test]
    fn same_value_no_conflict() {
        let reqs = vec![
            req("REQ-0001", "A-招标文件.docx", Some("6.1"), "招标控制价为人民币 480 万元。"),
            req("REQ-0121", "C-补遗文件01.docx", Some("三"), "招标控制价仍为 480 万元，特此确认。"),
        ];
        let is_ad = |n: &str| n.contains("补遗");
        assert!(semantic_conflicts(&reqs, &is_ad).is_empty());
    }

    /// 工期单位归一：90 日历天 vs 3 个月（×30=90）→ 归一后同值非冲突。
    #[test]
    fn schedule_unit_normalization_same_value_not_conflict() {
        let reqs = vec![
            req("REQ-0001", "A-招标文件.docx", Some("7.1"), "工期要求：90 日历天。"),
            req("REQ-0121", "C-补遗文件01.docx", Some("四"), "工期调整为 3 个月。"),
        ];
        let is_ad = |n: &str| n.contains("补遗");
        assert!(
            semantic_conflicts(&reqs, &is_ad).is_empty(),
            "90 日历天 = 3 个月（归一口径）——同值非冲突"
        );
    }

    /// 工期面：字面一致 + 值不同 → 检出。
    #[test]
    fn schedule_same_keyword_different_value_detected() {
        let reqs = vec![
            req("REQ-0001", "A-招标文件.docx", Some("7.1"), "工期要求：90 日历天。"),
            req("REQ-0121", "C-补遗文件01.docx", Some("四"), "工期缩短为 60 天。"),
        ];
        let is_ad = |n: &str| n.contains("补遗");
        let cs = semantic_conflicts(&reqs, &is_ad);
        assert_eq!(cs.len(), 1);
        assert_eq!(cs[0].topic, "工期");
        assert!((cs[0].main_value - 90.0).abs() < 1e-6);
        assert!((cs[0].addendum_value - 60.0).abs() < 1e-6);
    }

    /// 工期面：字面不同（工期×服务期）→ 不配对（不同字段——保守纪律）。
    #[test]
    fn schedule_different_keyword_no_pairing() {
        let reqs = vec![
            req("REQ-0001", "A-招标文件.docx", Some("7.1"), "工期要求：90 日历天。"),
            req("REQ-0121", "C-补遗文件01.docx", Some("四"), "服务期调整为 12 个月。"),
        ];
        let is_ad = |n: &str| n.contains("补遗");
        assert!(
            semantic_conflicts(&reqs, &is_ad).is_empty(),
            "工期×服务期是不同字段——保守不配对"
        );
    }

    /// 保证金面：投标保证金×履约保证金（字面不同）→ 不配对。
    #[test]
    fn deposit_different_kind_no_pairing() {
        let reqs = vec![
            req("REQ-0001", "A-招标文件.docx", Some("6.2"), "投标保证金：人民币 9 万元。"),
            req("REQ-0121", "C-补遗文件01.docx", Some("五"), "履约保证金为合同金额的 10%。"),
        ];
        let is_ad = |n: &str| n.contains("补遗");
        assert!(semantic_conflicts(&reqs, &is_ad).is_empty());
    }

    /// 保证金面：同字面不同值 → 检出。
    #[test]
    fn deposit_same_keyword_different_value_detected() {
        let reqs = vec![
            req("REQ-0001", "A-招标文件.docx", Some("6.2"), "投标保证金：人民币 9 万元。"),
            req("REQ-0121", "C-补遗文件01.docx", Some("五"), "投标保证金调整为人民币 12 万元。"),
        ];
        let is_ad = |n: &str| n.contains("补遗");
        let cs = semantic_conflicts(&reqs, &is_ad);
        assert_eq!(cs.len(), 1);
        assert_eq!(cs[0].topic, "保证金");
        assert!((cs[0].main_value - 9.0).abs() < 1e-6);
        assert!((cs[0].addendum_value - 12.0).abs() < 1e-6);
    }

    /// 非补遗对子（两主件）→ 不在语义冲突面（版本冲突的语义是补遗 vs 主件）。
    #[test]
    fn two_main_files_no_conflict() {
        let reqs = vec![
            req("REQ-0001", "A-招标文件.docx", Some("6.1"), "招标控制价为人民币 480 万元。"),
            req("REQ-0005", "B-技术规范书.docx", None, "控制价为人民币 465 万元。"),
        ];
        let is_ad = |_: &str| false;
        assert!(semantic_conflicts(&reqs, &is_ad).is_empty());
    }

    /// 元直述单位归一：4800000 元 = 480 万元。
    #[test]
    fn yuan_direct_statement_normalized_to_wan() {
        let reqs = vec![
            req("REQ-0001", "A-招标文件.docx", Some("6.1"), "本招标项目控制价 4800000 元。"),
            req("REQ-0121", "C-补遗文件01.docx", Some("三"), "三、招标控制价调整为 465 万元。"),
        ];
        let is_ad = |n: &str| n.contains("补遗");
        let cs = semantic_conflicts(&reqs, &is_ad);
        assert_eq!(cs.len(), 1);
        assert!((cs[0].main_value - 480.0).abs() < 1e-6, "元直述归一到万元");
        assert!((cs[0].addendum_value - 465.0).abs() < 1e-6);
    }
}
