//! #113 全链审计批七（D1）：拆点识别完整性契约——r6b 实锚缺陷面。
//!
//! 全链静态审计（audit/fullchain-defect-inventory-20261125.md D1）实锚：
//! criteria_with_points 9/36——27 条细则零点静默免检，其中两条**实质
//! 评分细则**（REQ-0289 安全管理方案 3 分 / REQ-0286 管理能力 4×1 分）
//! 拆不出任何点 = 评委按点给分面直接失明。根因四层：
//!   1. TRIGGERS 无「包含但不限于」/裸「包含」——REQ-0289 触发词扫描空手；
//!   2. 段长上限 12 字拒 13 字合法枚举项（「设备安装调试的安全保障措施」）；
//!   3. 顿号段跨句含句读 → 整段被拒（第二合法段陪葬）；
//!   4. （N）式子行无抽取路径——REQ-0286 四个「XX管理能力」零提取。
//! 修复契约（先红后绿——本文件先红）：
//!   - 「包含但不限于：A、B、C等」形态 → ≥2 点；
//!   - 13-16 字枚举段 → 合法点（上限 12→16）；
//!   - 顿号段跨句终止符截断后再验（不整段拒）；
//!   - （1）（2）…子行 → 「X的Y」取 Y（能力名词短语）≥2 点；
//!   - 结构标题/无枚举形态 → 仍 0 点（不虚构——回归锁）。

use bid_domain::scoring_coverage::extract_scoring_points;

/// REQ-0289 实锚（r6b db.json 锚摘录原文）——安全管理方案 3 分。
const REQ0289: &str = "安全管理方案与措施 3 投标人针对本项目提供安全管理方案与措施，包含但不限于：设备安装调试的安全保障措施、信息安全保障措施、现场环境保护等方面内容。\n根据所提供的方案内容酌情打分：\n优秀的得3（含）~2（不含）分；\n未提供不得分";

/// REQ-0286 实锚——管理能力 4 分（（1）（2）（3）（4）子行形态）。
const REQ0286: &str = "管理能力 4 （1）投标人具备提供投标产品及服务的质量管理能力（如具有ISO9001质量管理体系证书等）的得1分；\n（2）投标人具备提供投标产品及服务的职业健康安全管理能力（如具有ISO45001职业健康安全管理体系认证证书等）的得1分；\n（3）投标人具备提供投标产品及服务的信息技术服务管理能力（如具有ISO20000信息技术服务管理体系认证证书等）的得1分；\n（4）投标人具备提供投标产品及服务的信息安全管理能力（如具有ISO27001信息安全管理体系认证证书等）的得1分；\n满分4分，未提供的不得分。";

#[test]
fn req0289_baohan_budanxian_yields_two_plus_points() {
    let pts = extract_scoring_points(REQ0289);
    // RED：现行触发词扫描「包含但不限于」空手 + 12 字上限 + 跨句句读整段拒
    assert!(
        pts.len() >= 2,
        "REQ-0289「包含但不限于：A、B、C等」须拆出 ≥2 点，实得 {pts:?}"
    );
    assert!(
        pts.iter().any(|p| p.contains("信息安全保障措施")),
        "「信息安全保障措施」须成点: {pts:?}"
    );
    assert!(
        pts.iter().any(|p| p.contains("现场环境保护")),
        "「现场环境保护」须成点: {pts:?}"
    );
    assert!(
        pts.iter().any(|p| p.contains("安全保障措施")),
        "13 字段「设备安装调试的安全保障措施」（清洗后）须成点: {pts:?}"
    );
}

#[test]
fn req0286_numbered_subrows_yield_capability_points() {
    let pts = extract_scoring_points(REQ0286);
    // RED：（N）式子行无抽取路径——四个能力点零提取
    assert!(
        pts.len() >= 4,
        "REQ-0286（1）-（4）子行须拆出 4 个能力点，实得 {pts:?}"
    );
    for want in ["质量管理能力", "职业健康安全管理能力",
                 "信息技术服务管理能力", "信息安全管理能力"] {
        assert!(
            pts.iter().any(|p| p.contains(want)),
            "「{want}」须成点: {pts:?}"
        );
    }
}

#[test]
fn sixteen_char_enumeration_item_admitted() {
    // 上限 12→16：13-16 字枚举段是真实评标点形态
    let pts = extract_scoring_points("技术方案需包括：系统总体架构设计及集成实施方案、设备材料供应与进场计划");
    assert!(
        pts.iter().any(|p| p.contains("总体架构设计") || p.contains("集成实施方案")),
        "13 字合法枚举段须成点（上限 16）: {pts:?}"
    );
}

#[test]
fn dunhao_segment_crossing_sentence_terminator_truncated() {
    // 顿号段尾跨句（含 。）→ 截断后再验，第二段不陪葬
    let pts = extract_scoring_points("方案应涵盖：信息安全保障措施、现场环境保护。后续句。");
    assert!(
        pts.iter().any(|p| p.contains("现场环境保护")),
        "句读前段「现场环境保护」须成点（跨句截断）: {pts:?}"
    );
    assert!(
        !pts.iter().any(|p| p.contains("后续句")),
        "句后文本不得成点: {pts:?}"
    );
}

#[test]
fn structural_heading_still_yields_no_points() {
    // 回归锁：结构标题类细则（无枚举形态）不虚构点
    assert!(extract_scoring_points("2.1初步评审标准").is_empty());
    assert!(extract_scoring_points("3.4中标候选人推荐原则").is_empty());
    assert!(extract_scoring_points("评委酌情打分，无枚举。").is_empty());
    assert!(extract_scoring_points("").is_empty());
}

#[test]
fn single_numbered_subrow_not_fabricated() {
    // 仅 1 个（N）子行 = 无枚举证据面，不虚构（≥2 才成立）
    let pts = extract_scoring_points("（1）某单项能力的得1分；满分1分。");
    assert!(
        pts.is_empty(),
        "单个（N）子行不构成枚举证据，须零点: {pts:?}"
    );
}
