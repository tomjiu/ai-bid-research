//! dates.rs —— ISO `YYYY-MM-DD` 日期工具（T-1 Evidence 有效期面的地基，issue #11 V3-1）。
//!
//! 仓内既定口径（无 chrono 重依赖——薄壳零冗余纪律）：
//! - 日期 = 10 字符 ISO 字符串，**字典序 == 时间序**（impact.rs `apply_validity`
//!   同口径），比对零换算；
//! - 公历换算 = Howard Hinnant `civil_from_days` 算法（自 bid-mcp/tools.rs 移入
//!   crate 级单一真源——有效期窗口推算属领域逻辑，不该住在 MCP 壳层）。
//!
//! 全部纯函数；`today_ymd` 除外（系统时钟——测试不依赖它，仅 CLI 消费）。

/// `YYYY-MM-DD` 严格解析（10 字符定长；月 1..=12、日不超该月实际月长——
/// 闰年 2 月 29；返回 (年, 月, 日)）。
///
/// #375（A-16）：旧口径只查日域 1..=31，`2026-02-30`/`2026-04-31` 合法入库
/// ——不存在的日期进有效期/截止日字段后，下游 civil 换算产出无意义结果且无告警。
/// 月长校验在此收紧（单一真源，全部调用方同享）。
pub fn parse_ymd(s: &str) -> Option<(i64, u32, u32)> {
    let b = s.as_bytes();
    if b.len() != 10 || b[4] != b'-' || b[7] != b'-' {
        return None;
    }
    let y: i64 = s.get(0..4)?.parse().ok()?;
    let m: u32 = s.get(5..7)?.parse().ok()?;
    let d: u32 = s.get(8..10)?.parse().ok()?;
    if !(1..=12).contains(&m) || d < 1 || d > days_in_month(y, m) {
        return None;
    }
    Some((y, m, d))
}

/// `y` 年 `m` 月的天数（公历；闰年判定：四年一闰、百年不闰、四百年再闰）。
/// 纯函数无 chrono——仓内薄壳零冗余纪律（与 Hinnant 换算同址同口径）。
const fn days_in_month(y: i64, m: u32) -> u32 {
    match m {
        1 | 3 | 5 | 7 | 8 | 10 | 12 => 31,
        4 | 6 | 9 | 11 => 30,
        _ => {
            // 2 月：闰 29、平 28。闰判据与 civil_from_days 的 400 年周期一致
            // （yoe/4 - yoe/100 的展开形态）——保持单一算术口径。
            let leap = (y % 4 == 0 && y % 100 != 0) || y % 400 == 0;
            if leap {
                29
            } else {
                28
            }
        }
    }
}

/// 合法 ISO 日期判定（None = 拒——诚实状态纪律：日期字段要么合法要么缺省，无中间态）。
pub fn is_valid_ymd(s: &str) -> bool {
    parse_ymd(s).is_some()
}

/// 公历 → 天数（Hinnant `days_from_civil`——`civil_from_days` 的逆）。
pub fn days_from_civil(y: i64, m: u32, d: u32) -> i64 {
    let y = if m <= 2 { y - 1 } else { y };
    let era = if y >= 0 { y } else { y - 399 } / 400;
    let yoe = y - era * 400; // [0, 399]
    let mp = if m > 2 { m - 3 } else { m + 9 } as i64; // [0, 11]
    let doy = (153 * mp + 2) / 5 + d as i64 - 1; // [0, 365]
    let doe = yoe * 365 + yoe / 4 - yoe / 100 + doy; // [0, 146096]
    era * 146_097 + doe - 719_468
}

/// 天数 → 公历（Hinnant `civil_from_days`）。
pub fn civil_from_days(z: i64) -> (i64, u32, u32) {
    let z = z + 719_468;
    let era = if z >= 0 { z } else { z - 146_096 } / 146_097;
    let doe = z - era * 146_097;                                  // [0, 146096]
    let yoe = (doe - doe / 1460 + doe / 36_524 - doe / 146_096) / 365; // [0, 399]
    let y = yoe + era * 400;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);            // [0, 365]
    let mp = (5 * doy + 2) / 153;                                 // [0, 11]
    let d = (doy - (153 * mp + 2) / 5 + 1) as u32;                // [1, 31]
    let m = (if mp < 10 { mp + 3 } else { mp - 9 }) as u32;       // [1, 12]
    (if m <= 2 { y + 1 } else { y }, m, d)
}

/// ISO 日期 + N 天（负数回拨；非法输入 → None）。
pub fn add_days(s: &str, days: i64) -> Option<String> {
    let (y, m, d) = parse_ymd(s)?;
    let (y, m, d) = civil_from_days(days_from_civil(y, m, d) + days);
    Some(format!("{y:04}-{m:02}-{d:02}"))
}

/// 今天（**本地日历日**——R15，#47 平台区分⑧口径修正；系统时钟，测试不
/// 依赖它，仅 CLI/展示/台账消费）。
///
/// **为什么是本地不是 UTC**：消费方全是业务日历日——投标截止过去警告
/// （`BID_DEADLINE_PAST`）、性能台账 created_at、评标基准日/开标日缺省。
/// 旧口径 epoch 直除 86400 = UTC 日：东八区本地 00:00-07:59 之间取到
/// **昨天**——截止日刚过的警告漏报一天、台账日期整体前置一档。本地日历日
/// 与用户在 UI 日历控件里选的是同一天（JS `new Date()` 即本地）。
///
/// 实现：chrono `Local` 只提供 **UTC 偏移秒**（iana-time-zone：Unix 读
/// TZ 环境变量//etc/localtime，Windows 读注册表——双平台标准路径）；日期
/// 换算仍走本 crate 的 `civil_from_days`（单一算术真源，chrono 不进日期
/// 数学）。偏移的换算面 [`ymd_at_utc_offset`] 是纯函数（测试锁边界瞬点）。
pub fn today_ymd() -> String {
    let secs = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_secs() as i64)
        .unwrap_or(0);
    let offset = chrono::Local::now().offset().local_minus_utc() as i64;
    ymd_at_utc_offset(secs, offset)
}

/// 今天（UTC 日——确定性对照面；业务消费一律 [`today_ymd`]，本函数仅供
/// 测试对照与诊断）。
pub fn today_ymd_utc() -> String {
    let secs = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_secs() as i64)
        .unwrap_or(0);
    ymd_at_utc_offset(secs, 0)
}

/// epoch 秒 + UTC 偏移秒 → 本地日历日（纯函数：`(secs + offset) / 86400`
/// 后走 [`civil_from_days`]——`div_euclid` 对负秒（1970 前）同样正确）。
pub fn ymd_at_utc_offset(secs: i64, offset_secs: i64) -> String {
    let (y, m, d) = civil_from_days((secs + offset_secs).div_euclid(86_400));
    format!("{y:04}-{m:02}-{d:02}")
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parse_ymd_strict_domain() {
        assert_eq!(parse_ymd("2026-11-15"), Some((2026, 11, 15)));
        // #375（A-16）：月长校验在位——2 月没有 30 日、小月没有 31 日
        assert_eq!(parse_ymd("2026-02-30"), None, "2 月无 30 日（月长收紧）");
        assert_eq!(parse_ymd("2026-13-01"), None, "月 13 拒");
        assert_eq!(parse_ymd("2026-00-01"), None, "月 0 拒");
        assert_eq!(parse_ymd("2026-01-32"), None, "日 32 拒");
        assert_eq!(parse_ymd("2026-01-00"), None, "日 0 拒");
        assert_eq!(parse_ymd("2026/01/01"), None, "非连字符拒");
        assert_eq!(parse_ymd("2026-1-01"), None, "非定长拒");
        assert_eq!(parse_ymd(""), None);
        assert_eq!(parse_ymd("2026-11-15T00:00"), None, "带时间后缀拒（前缀口径已废弃）");
    }

    /// #375（A-16）月长校验边界：闰/平年 2 月、大小月、恰好月长日。
    #[test]
    fn parse_ymd_month_length_edges() {
        // 闰年 2-29 过：普通闰 / 世纪闰（400 年再闰）
        assert_eq!(parse_ymd("2024-02-29"), Some((2024, 2, 29)), "普通闰年");
        assert_eq!(parse_ymd("2000-02-29"), Some((2000, 2, 29)), "世纪闰年（400 再闰）");
        // 平年 2-29 拒：普通平 / 世纪不闰（百年不闰）
        assert_eq!(parse_ymd("2026-02-29"), None, "普通平年 2-29 拒");
        assert_eq!(parse_ymd("2100-02-29"), None, "百年不闰");
        assert_eq!(parse_ymd("1900-02-29"), None, "百年不闰（1900）");
        // 闰年 2-30 仍拒（月长 29 封顶）
        assert_eq!(parse_ymd("2024-02-30"), None, "闰年 2 月上限 29");
        // 小月 31 拒、30 过；大月 31 过
        for (m, last) in [(4, 30), (6, 30), (9, 30), (11, 30)] {
            assert_eq!(parse_ymd(&format!("2026-{m:02}-31")), None, "{m} 月无 31 日");
            assert_eq!(
                parse_ymd(&format!("2026-{m:02}-{last:02}")),
                Some((2026, m, last)),
                "{m} 月末合法"
            );
        }
        assert_eq!(parse_ymd("2026-01-31"), Some((2026, 1, 31)), "大月末合法");
        assert_eq!(parse_ymd("2026-02-28"), Some((2026, 2, 28)), "平年 2 月末合法");
        // 12 个月全月长对照（2026 平年）
        let expect = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
        for (idx, days) in expect.iter().enumerate() {
            let m = idx as u32 + 1;
            assert_eq!(
                parse_ymd(&format!("2026-{m:02}-{days:02}")),
                Some((2026, m, *days as u32)),
                "{m} 月第 {days} 日合法"
            );
            assert_eq!(
                parse_ymd(&format!("2026-{m:02}-{}", days + 1)),
                None,
                "{m} 月第 {} 日拒（超月长）",
                days + 1
            );
        }
    }

    /// Hinnant 换算往返全等 + 已知锚点（1970-01-01 = epoch 0 天）。
    #[test]
    fn civil_days_roundtrip_and_epoch_anchor() {
        assert_eq!(days_from_civil(1970, 1, 1), 0, "epoch 锚点");
        assert_eq!(civil_from_days(0), (1970, 1, 1));
        // 闰年锚点
        assert_eq!(days_from_civil(2000, 3, 1), days_from_civil(2000, 2, 29) + 1, "2000 闰");
        assert_eq!(days_from_civil(2100, 3, 1), days_from_civil(2100, 2, 28) + 1, "2100 非闰（百年不闰）");
        // 往返（注意：非闰年的 2-29 不存在——归一化到 3-1 属正常行为，测试用真闰年）
        for (y, m, d) in [(1900, 1, 1), (2026, 11, 15), (2024, 2, 29), (9999, 12, 31)] {
            let back = civil_from_days(days_from_civil(y, m, d));
            assert_eq!(back, (y, m, d), "往返全等");
        }
    }

    #[test]
    fn add_days_cross_month_and_year() {
        assert_eq!(add_days("2026-11-15", 12).unwrap(), "2026-11-27");
        assert_eq!(add_days("2026-11-15", -15).unwrap(), "2026-10-31", "跨月回拨");
        assert_eq!(add_days("2026-12-31", 1).unwrap(), "2027-01-01", "跨年");
        assert_eq!(add_days("2024-02-28", 1).unwrap(), "2024-02-29", "闰日");
        assert_eq!(add_days("bad", 1), None);
    }

    /// R15（#47 平台区分⑧）：偏移换算矩阵——同一 epoch 瞬点在不同 UTC 偏移
    /// 下的日历日（纯函数锁边界；东八区本地 0-8 点取昨天的根因就是这层）。
    #[test]
    fn ymd_at_utc_offset_matrix() {
        // 2024-11-09T16:00:00Z：UTC 日 11-09；+8h（北京 11-10 00:00 整）翻日
        let secs = 1_731_168_000i64;
        assert_eq!(ymd_at_utc_offset(secs, 0), "2024-11-09");
        assert_eq!(ymd_at_utc_offset(secs, 8 * 3600), "2024-11-10", "东八区翻日（本地 00:00）");
        // 前一秒：北京仍是 11-09 23:59:59
        assert_eq!(ymd_at_utc_offset(secs - 1, 8 * 3600), "2024-11-09");
        // 西五区（纽约冬令）：本地 11-09 11:00，与 UTC 同日
        assert_eq!(ymd_at_utc_offset(secs, -5 * 3600), "2024-11-09");
        // UTC 日界本身：2024-11-10T00:00:00Z 前 1 秒 UTC 仍 11-09
        assert_eq!(ymd_at_utc_offset(secs + 8 * 3600 - 1, 0), "2024-11-09");
        assert_eq!(ymd_at_utc_offset(secs + 8 * 3600, 0), "2024-11-10");
        // 十二时区（UTC+12）同瞬点已是 11-10 04:00；十四时区（基里巴斯 +14）11-10 06:00
        assert_eq!(ymd_at_utc_offset(secs, 12 * 3600), "2024-11-10");
        assert_eq!(ymd_at_utc_offset(secs, 14 * 3600), "2024-11-10");
        // 负偏移大值（UTC-11）：11-09 05:00
        assert_eq!(ymd_at_utc_offset(secs, -11 * 3600), "2024-11-09");
        // 1970 前的负秒（div_euclid 向下取整——1969-12-31T23:00Z 在 +1h 下回 1970-01-01）
        assert_eq!(ymd_at_utc_offset(-3600, 0), "1969-12-31");
        assert_eq!(ymd_at_utc_offset(-3600, 3600), "1970-01-01");
        // 半小时偏移（印度 +5:30 / 尼泊尔 +5:45）不落整点也不炸
        assert_eq!(ymd_at_utc_offset(secs, 5 * 3600 + 1800), "2024-11-09");
        assert_eq!(ymd_at_utc_offset(secs + 8 * 3600 - 1, 5 * 3600 + 2700), "2024-11-10");
    }

    /// R15：today_ymd（本地）/ today_ymd_utc（UTC）一致性健全性——任何时区
    /// 的机器上两者至多差 1 天（时区偏移 ≤ ±14h < 24h；超出即换算坏了）。
    /// 两个 today 都是合法公历日（parse_ymd 单一真源复验）。
    #[test]
    fn today_ymd_local_vs_utc_sanity() {
        let local = today_ymd();
        let utc = today_ymd_utc();
        let (ly, lm, ld) = parse_ymd(&local).expect("本地 today 是合法公历日");
        let (uy, um, ud) = parse_ymd(&utc).expect("UTC today 是合法公历日");
        let delta =
            (days_from_civil(ly, lm, ld) - days_from_civil(uy, um, ud)).abs();
        assert!(delta <= 1, "本地/UTC 日历日相差 {delta} 天（>1 = 偏移换算坏）：local={local} utc={utc}");
    }
}
