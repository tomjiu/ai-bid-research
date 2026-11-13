//! scoring_exclusion.rs —— 评审程序条款排除面（AUD2-HIS-B1，issue #132）。
//!
//! ## 问题（真跑实锤，松岭 65 页 #251 基线件）
//!
//! REQ-0180「2.2 评标委员会启动异常低价投标审查后，……给予相关供应商的
//! 合理时间一般不少于 30 分钟。……」——评审**程序**条款（评委在评审现场
//! 做什么），因「30 分钟」的「30 分」字样被归「评分项」并携带 score=30：
//! - 评分面被污染：9 条带分值 criteria 合计 130 分（真值 100——虚增的
//!   30 分正是被吞掉的分值基数，直接影响 #131 的分值比例配额）；
//! - 无映射 → 门 1h 假拦（评审程序条款没有「响应章节」可言，须豁免才能
//!   导出——审计阶段 3 实锤的单例）。
//!
//! ## 判据（与 #52 `_veto_excluded` 同款可审计形态）
//!
//! 命中 = **评审主体程序动作** ∧ **无分值授予语义**：
//! - 评审主体：评标委员会 / 评审委员会 / 评标工作组；
//! - 程序动作：启动…审查 / 否决 / 复核 / 按…处理 / 要求…解释（说明）/
//!   修正 / 作为…处理；
//! - 守护词（先行短路）：分值授予语义——`得N分`/`每…得`/`满分`/`加N分`/
//!   `扣N分`/`得分`（算式面）。真评分细则哪怕提及评委也带授予语义
//!   （「由评标委员会打分，每具备一项得2.5分」），守护词保它不误伤。
//!
//! 与 [`exclusion_reason`]（veto_lexicon，否决→评分/其他）互不干涉：本面
//! 只作用于 category==评分项 的后置复检（extract_dispatch 统一收口，覆盖
//! 全部分类路径——章节上下文/评分表专路/审查表/强词传播），被排除条款
//! 改判「其他」+ `params["_scoring_excluded"]` 记录原因（下游可追溯）。
//!
//! 确定性纪律：零模型调用、纯词表/正则、同输入同输出。

use regex::Regex;
use std::sync::OnceLock;

/// 评审主体（评标/评审委员会等工作组织——程序动作的施动者）。
fn re_committee() -> &'static Regex {
    static RE: OnceLock<Regex> = OnceLock::new();
    RE.get_or_init(|| Regex::new("评标委员会|评审委员会|评标工作组").unwrap())
}

/// 程序动作动词族（评审现场的过程行为——非对投标文件的内容要求）。
fn re_procedure_verb() -> &'static Regex {
    static RE: OnceLock<Regex> = OnceLock::new();
    RE.get_or_init(|| {
        Regex::new(concat!(
            "启动.{0,20}审查|",
            "启动.{0,20}复核|",
            "否决|复核|重新评审|",
            "按.{0,12}(处理|修正|纠正)|作为.{0,8}(处理|无效)|",
            "要求.{0,24}(解释|说明|澄清|证明)"
        ))
        .unwrap()
    })
}

/// 分值授予语义（守护词——真评分细则的保护面，命中即短路放行）。
///
/// 「N分钟」不是授予语义（分钟排除在 [`score_of`] 代码级判定——本守护
/// 词不匹配分钟形态：`得`/`满分`/`加`/`扣` 后必须跟数值或「分」）。
fn re_score_award() -> &'static Regex {
    static RE: OnceLock<Regex> = OnceLock::new();
    RE.get_or_init(|| {
        Regex::new(concat!(
            "得\\s*\\d|\\d\\s*分[^钟]|每.{0,12}得|满分|满\\s*\\d+\\s*分|",
            "加\\s*\\d+\\s*分|扣\\s*\\d+\\s*分|得分|分值|评审因素所占"
        ))
        .unwrap()
    })
}

/// 评审程序条款排除判定：命中返回排除原因（可审计），未命中 None（放行）。
///
/// 调用方（extract_dispatch 后置复检）只对 category==「评分项」调用；
/// 改判目标「其他」+ `params["_scoring_excluded"]`。
pub fn procedural_exclusion_reason(text: &str) -> Option<&'static str> {
    // 守护：分值授予语义先行短路——真评分细则不进排除面
    if re_score_award().is_match(text) {
        return None;
    }
    if re_committee().is_match(text) && re_procedure_verb().is_match(text) {
        return Some("评审程序条款——评审主体程序动作非评分细则（响应义务属评审现场，非投标文件面）");
    }
    None
}

#[cfg(test)]
mod tests {
    use super::*;

    /// REQ-0180 原文（松岭 65 页真跑锚文本，节选关键句）——必须命中。
    #[test]
    fn catches_songling_req0180() {
        let t = "2.2评标委员会启动异常低价投标审查后，属于前述第1项⾄第4项情形的，应当要求相关投标⼈在评审现场合理的时间内对投标价格作出解释，提供项⽬具体成本测算等与报价合理性相关的书⾯说明及必要的证明材料，包括但不限于原材料成本、⼈⼯成本、制造费⽤等，给予相关供应商的合理时间⼀般不少于30分钟。其中，属于第3项情形，供应商已随投标⽂件⼀并提交相关书⾯说明及必要的证明材料的，在评审现场可不再重复提交。评标委员会依据专业经验，参考同类项⽬中标（成交）价格、类似产品市场价格⽔平、⾏业⼈⼯费⽤标准、国家有关部⻔指导⾏业协会发布的⾏业平均成本等情况，对报价合理性进⾏判断。投标⼈不能提供书⾯说明、证明材料，或者提供的书⾯说明、证明材料不能证明其报价合理性的，评标委员会应当将其作为⽆效投标处理。";
        assert!(procedural_exclusion_reason(t).is_some());
    }

    /// 2.1 程序开启句（评审委员会应当启动…审查程序）——必须命中。
    #[test]
    fn catches_procedure_opener() {
        let t = "根据《关于推动解决政府采购异常低价问题的通知》（财库〔2026〕2号）等相关规定，政府采购评审中出现下列情形之⼀的，评审委员会应当启动异常低价投标（响应）审查程序：";
        assert!(procedural_exclusion_reason(t).is_some());
    }

    /// 审查表结果句（应评标委员会要求证明报价合理性）——程序面，命中。
    /// 松岭真跑实锄：锚文本是跨行碎片段（「报价合理性够应评标委员会要求…
    /// 证明其报价合理性的。」），程序动词需在碎片内可判。
    #[test]
    fn catches_review_table_row() {
        let t = "报价合理，或报价不合理启动异常低价投标审查程序后，能够应评标委员会要求在规定时间内证明其报价合理性的。";
        assert!(procedural_exclusion_reason(t).is_some());
        // 碎片形态（真跑锚文本原样——无「启动…审查」上下文，靠委员会+要求…证明）
        let frag = "报价合理性够应评标委员会要求在规定时间内证明其报价合理性的。";
        assert!(procedural_exclusion_reason(frag).is_some());
    }

    /// 真评分细则（服务方案 25 分）——不得误伤。
    #[test]
    fn keeps_real_criterion_service() {
        let t = "服务方案（25分 技术评审）：1.根据本项目的具体情况，供应商需提供详细、完善、合理可行的服务方案，包含：①整体服务方案（对本项目建设、运行维护服务方案）；以上内容每具备一项得2.5分，满分25分。";
        assert!(procedural_exclusion_reason(t).is_none());
    }

    /// 真评分细则（价格算式）——「得分」「评审因素所占」守护词保它。
    #[test]
    fn keeps_real_criterion_price_formula() {
        let t = "价格评审（10分 价格评审）：F1指价格项评审因素得分＝（评标基准价/投标报价）×100×价格项评审因素所占的权重（注：满足招标文件要求且投标价格最低的投标报价为评标基准价）";
        assert!(procedural_exclusion_reason(t).is_none());
    }

    /// 「由评标委员会打分」+ 授予语义——评委在场也不误伤（守护词优先）。
    #[test]
    fn keeps_committee_scored_criterion() {
        let t = "保密工作（10分 技术评审）：由评标委员会对供应商的保密措施方案打分，以上内容每具备一项得5分。";
        assert!(procedural_exclusion_reason(t).is_none());
    }

    /// 无评审主体、无程序动作的普通条款——不进排除面（None）。
    #[test]
    fn keeps_plain_clause() {
        assert!(procedural_exclusion_reason("开标⼀览表（报价表）内容与投标⽂件中相应内容不⼀致的，以开标⼀览表（报价表）为准；").is_none());
        assert!(procedural_exclusion_reason("同时出现两种以上不⼀致的，按照前款规定的顺序修正。").is_none());
    }

    /// 「30分钟」不是分值授予语义——守护词不吞分钟形态。
    #[test]
    fn minute_form_is_not_award() {
        assert!(!re_score_award().is_match("给予相关供应商的合理时间⼀般不少于30分钟。"));
        assert!(!re_score_award().is_match("解密时间从开标时间起 60 分钟内完成。"));
    }
}
