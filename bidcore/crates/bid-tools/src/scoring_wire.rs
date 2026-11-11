//! scoring_wire.rs —— 评分树与章节映射的联结装配（#170 方案 A + #224 多对多）。
//!
//! 定位：`export/score` 消费面的**单一真源**——从 `DomainStore` 装配
//! [`bid_domain::scoring::SectionScorer`]（含派生 params.section 联结、
//! 「第X章」章号归一定位、#224 持久化映射账本并入）。
//! 原住 bid-mcp/tools.rs（score_section/score_document/check_bid_quality
//! 私有辅助）；#88 门 1h（unmapped 评分项门）需要同一真源——导出门在
//! bid-tools 层，依赖方向决定本模块下沉至此（迁移零语义变化）。

///
/// 返回 (scorer, 联结后首现序 items)——items 供 by_item/target 的全量
/// 「第X章」章号归一（#170 方案 A）：中文/阿拉伯数字统一为数值——
/// 「第8章」「第八章」「第 8 章」→ 8。中文数字支持到千（真实招标文件
/// 章节数域：水利标书最多见「第 24 章」，千位余量足够）。非章序数
/// （「第1页」「第2行」）因后随字符非「章」不会误触。
pub fn chapter_no_of(text: &str) -> Option<u32> {
    const CN: &[(char, u32)] = &[
        ('零', 0), ('〇', 0), ('两', 2),
        ('一', 1), ('二', 2), ('三', 3), ('四', 4), ('五', 5),
        ('六', 6), ('七', 7), ('八', 8), ('九', 9),
        ('十', 10), ('百', 100), ('千', 1000),
    ];
    let cs: Vec<char> = text.chars().collect();
    let mut i = 0usize;
    while i < cs.len() {
        if cs[i] != '第' {
            i += 1;
            continue;
        }
        // 收集「第」与「章」之间的数字串（中文/阿拉伯分别累计）
        let mut j = i + 1;
        let mut has_cn = false;
        let mut arabic = String::new();
        while j < cs.len() {
            let c = cs[j];
            if c.is_ascii_digit() || ('０'..='９').contains(&c) {
                arabic.push(c);
                j += 1;
            } else if CN.iter().any(|(cn, _)| *cn == c) {
                has_cn = true;
                j += 1;
            } else if c.is_whitespace() {
                // 章号边缘/内部的空白跳过（实测形态「第 8 章」——塔里木件）。
                // 「第 1 页」类不受影响：'页' 非 '章'，整段判 None。
                j += 1;
            } else {
                break;
            }
        }
        let parsed = if j < cs.len() && cs[j] == '章' && j > i + 1 {
            if !arabic.is_empty() && !has_cn {
                // 阿拉伯段：「第 8 章」「第24章」
                arabic.parse::<u32>().ok()
            } else if has_cn {
                // 中文数字段 [i+1, j)：乘法加法累计（「二十四」=24、「一百零八」=108）
                let mut total: u32 = 0;
                let mut current: u32 = 0;
                for &c in &cs[i + 1..j] {
                    let v = CN.iter().find(|(cn, _)| *cn == c).map(|(_, v)| *v).unwrap_or(0);
                    match v {
                        10 | 100 | 1000 => {
                            // 十/百/千：单位——current 为 0 时按 1（「十」=10）
                            total += current.max(1) * v;
                            current = 0;
                        }
                        _ => current = current * 10 + v,
                    }
                }
                Some(total + current)
            } else {
                None
            }
        } else {
            None
        };
        if let Some(no) = parsed {
            return Some(no);
        }
        i += 1;
    }
    None
}

/// 节点子树的首片叶（DFS 首现序——确定性）。自身无子即自身是叶。
fn first_leaf_under<'a>(
    store: &'a bid_domain::DomainStore,
    root: &str,
) -> Option<&'a str> {
    let children_of = |id: &str| -> Vec<&bid_domain::outline::OutlineNode> {
        store
            .sections()
            .iter()
            .filter(|n| n.parent_id.as_deref() == Some(id))
            .collect()
    };
    let mut stack = vec![root.to_string()];
    while let Some(id) = stack.pop() {
        let kids = children_of(&id);
        if kids.is_empty() {
            // 自身是叶（根 id 在 sections 里存在性由调用方保证——不在则 None）
            if store.sections().iter().any(|n| n.id == id) {
                return Some(store.sections().iter().find(|n| n.id == id)?.id.as_str());
            }
            return None;
        }
        // DFS 首序：子节点逆序入栈（pop 时正序）
        for k in kids.into_iter().rev() {
            stack.push(k.id.clone());
        }
    }
    None
}

/// 逃代（derive_scoring_items 首现序，确定性；HashMap 索引无序不可逃代）。
pub fn build_scorer(
    store: &bid_domain::DomainStore,
) -> (
    bid_domain::scoring::SectionScorer,
    Vec<bid_domain::scoring::ScoringItem>,
    // #224 追溯面：**生效**账本映射键集 (req_id, section_id)。账本行与派生
    // params.section 同节时被去重（派生赢、账本行 inert 不入 mappings）——
    // 报告只认生效来源：同节 inert 行的 source/anchor/evidence 不得误归因
    // 给派生映射（Lead 审查 2：键集区分「账本生效」与「派生」两路）。
    std::collections::HashSet<(String, String)>,
) {
    let parents: std::collections::HashSet<&str> = store
        .sections()
        .iter()
        .filter_map(|n| n.parent_id.as_deref())
        .collect();
    let mut leaf_of: std::collections::HashMap<&str, &str> = std::collections::HashMap::new();
    for n in store.sections() {
        if !parents.contains(n.id.as_str()) {
            for rid in &n.requirement_ids {
                leaf_of.insert(rid.as_str(), n.id.as_str());
            }
        }
    }
    // #170 方案 A（联结侧）：评分项不进正文（#126）→ leaf_of 反查对评分项
    // 永不命中（老路径保留——对正文类目 REQ 仍有效）。新增评审表章引用联结：
    // params.section_title（bid-parse 从评审表行文本登记的「第X章…」引用）
    // → 章号归一定位「被引用章的正文叶」——「详见第X章」的语义是第X章的
    // **内容**，而大纲是类目重组（技术参数/商务要求…横跨物理章），故匹配
    // 面取两路（先后优先）：
    //   ① 锚在该章的正文 REQ 所住的叶（leaf_of 反查——语义最准：被评内容
    //      就是那一章的条款）；
    //   ② 大纲节点 title 自带章号（「其他」类目按章分组的形态）→ 子树首叶。
    // 两路都取首现序（确定性可重放）。「评分项按章节自评」由此恢复；无引用
    // 的评分项维持 section=None（数据缺引用时不虚构映射——score_section 对
    // 该条恒空是诚实行为）。
    let chapter_leaf: std::collections::HashMap<u32, &str> = {
        let mut m: std::collections::HashMap<u32, &str> = std::collections::HashMap::new();
        for r in store.requirements() {
            // 只认正文类目：否决/资格的 REQ 住「资格与响应」响应叶——那是
            // 「对条款的应答」的家，不是「被评内容」的家（评分项引用第X章
            // 指的是该章的内容条款）。
            if !bid_domain::outline::is_body_category(&r.category) {
                continue;
            }
            let Some(leaf) = leaf_of.get(r.id.as_str()) else {
                continue;
            };
            for a in &r.anchors {
                for seg in a.locator.split(['>', '＞']) {
                    if let Some(no) = chapter_no_of(seg.trim()) {
                        m.entry(no).or_insert(leaf);
                        break;
                    }
                }
            }
        }
        for n in store.sections() {
            if let Some(no) = chapter_no_of(&n.title) {
                if let Some(leaf) = first_leaf_under(store, &n.id) {
                    m.entry(no).or_insert(leaf);
                }
            }
        }
        m
    };
    let mut reqs = store.requirements().to_vec();
    for r in &mut reqs {
        if r.category == "评分项" && r.params.get("section").is_none() {
            if let Some(sec) = leaf_of.get(r.id.as_str()) {
                r.params.insert("section".into(), serde_json::json!(sec));
            } else if let Some(title) = r.params.get("section_title").and_then(|v| v.as_str()) {
                if let Some(no) = chapter_no_of(title) {
                    if let Some(sec) = chapter_leaf.get(&no) {
                        r.params.insert("section".into(), serde_json::json!(sec));
                    }
                }
            }
        }
    }
    // 项目专名锚（B3 ProjectContext 同源——具体性判定的锚词面）
    let terms = crate::quality::ProjectContext::from_store(store).scorer_terms();
    let mut items = bid_domain::scoring::derive_scoring_items(&reqs);
    let mut tree = bid_domain::scoring::derive_scoring_tree(&reqs);
    // #224 多对多：并入持久化映射（AgentSubmitted/Manual——账本在
    // store.scoring_mappings()，联结进 items/tree.index 两份视图）。
    // 同 (req, section) 键与 params.section 重合时跳过（params 单值 share
    // 恒 1.0——同章重合以账本 share 为准的语义留给后续显式覆写面，本步
    // 保守去重防双重计入）。
    let persistent: Vec<(String, bid_domain::scoring::SectionMapping)> = store
        .scoring_mappings()
        .iter()
        .map(|m| {
            (
                m.scoring_req_id.clone(),
                bid_domain::scoring::SectionMapping {
                    section_id: m.section_id.clone(),
                    weight_share: m.weight_share,
                },
            )
        })
        .collect();
    let apply = |item: &mut bid_domain::scoring::ScoringItem,
                 persistent: &[(String, bid_domain::scoring::SectionMapping)],
                 ledger_effective: &mut std::collections::HashSet<(String, String)>| {
        for (req_id, m) in persistent {
            if *req_id == item.requirement_id
                && !item.mappings.iter().any(|x| x.section_id == m.section_id)
            {
                item.mappings.push(m.clone());
                // 只有真正进 mappings 的账本行才是生效映射（同节被派生
                // 去重的 inert 行不算）——报告归因的判定面。
                ledger_effective.insert((req_id.clone(), m.section_id.clone()));
            }
        }
    };
    let mut ledger_effective: std::collections::HashSet<(String, String)> =
        std::collections::HashSet::new();
    for it in &mut items {
        apply(it, &persistent, &mut ledger_effective);
    }
    for (_, item) in tree.index.iter_mut() {
        apply(item, &persistent, &mut ledger_effective);
    }
    (
        bid_domain::scoring::SectionScorer::new(tree, terms),
        items,
        ledger_effective,
    )
}
