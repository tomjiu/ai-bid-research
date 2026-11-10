//! platform_names.rs —— 文件名平台合法性单一真源（#47 R10：跨平台硬化②
//! Windows 保留名与非法字符）。
//!
//! ## 动机（Linux 首跑暴露的假绿模式）
//!
//! 工作区（db.json + 落位文件）设计为跨平台搬运：Linux 壳建的库要在
//! Windows 壳可开、Windows 壳导的件要在 Linux 壳可读。但 Linux 文件系统
//! 对 `CON.docx`、`aux.xlsx`、`招<标>.pdf`、`报告 .docx`（尾随空格）一类
//! 名字**照单全收**——它们一旦落位入库，同一个工作区在 Windows 上打不开
//! （`CON` 是设备名、`< >` 非法、尾随点/空格被 Win32 剥离导致 rel 对不上）。
//! 导入/落位是工作区的唯一入口，**入口拦**：本模块供导入面（域层
//! `BidService::import`，经 fs_fence 的 rel）与壳落位面（`bid.ingest_drop`）
//! 共用同一套裁决——零重实现（与 fs_fence「导入导出同一套」同纪律）。
//!
//! ## 规则口径（Microsoft「Naming Files, Paths, and Namespaces」文档口径，
//! 不越界加严）
//!
//! 对相对路径的**每个组件**（目录段与文件名同样——目录叫 `CON` 一样不可
//! 移植）：
//!
//! 1. **保留设备名**：`CON`、`PRN`、`AUX`、`NUL`、`COM1`~`COM9`、
//!    `LPT1`~`LPT9`（历史半保留 `CLOCK$` 一并收，文档同列）。比较口径 =
//!    名字**到第一个 `.` 为止**的段，大小写不敏感，任意扩展名同罪
//!    （`CON.docx`、`con.tar.gz`、`Con` 全部保留）——这是 Win32 的历史
//!    设备名解析行为；`console.docx`、`auxx.docx`、`com10.docx` 合法。
//! 2. **非法字符**：`< > : " | ? *` 六个 Win32 保留字符 + `0x00-0x1F`
//!    控制字符（`/ \` 是分隔符不会出现在单组件里；`0x7F` 文件系统层面
//!    合法故不拦——不加严）。
//! 3. **尾随点/空格**：Win32 剥离组件尾部的 `.` 和空格（`报告 .docx` 落
//!    Windows 变 `报告.docx`）——rel 对不上账、sha 幂等键错位。文档明言
//!    不要以点/空格结尾。
//!
//! ## 平台语义（AGENTS.md §13 平台门）
//!
//! 本检查**平台中立**：无论跑在哪个壳，都对 rel 施加 Windows 语义——因为
//! 检查对象是「工作区搬到 Windows 后的生存性」，与当前平台无关（与
//! fs_fence 的 `is_inside` Windows 大小写不敏感收敛同理）。平台差异只影响
//! **测试样本的制备**：`CON.docx` 只能在 Unix 上造出来（Windows 侧
//! `fs::write` 直接被 OS 拒）——相关测试在 Windows 侧打 SKIP 横幅（13.2）。

use std::path::{Component, Path};

/// Windows 保留设备名（小写存储；比较用小写折叠）。
const RESERVED: [&str; 22] = [
    "con", "prn", "aux", "nul", "com1", "com2", "com3", "com4", "com5", "com6", "com7", "com8",
    "com9", "lpt1", "lpt2", "lpt3", "lpt4", "lpt5", "lpt6", "lpt7", "lpt8", "clock$",
];

/// Win32 文件名保留字符（单组件内不得出现）。
const ILLEGAL_CHARS: [char; 7] = ['<', '>', ':', '"', '|', '?', '*'];

/// 单组件（目录段或文件名）的 Windows 合法性裁决。
///
/// 返回 `Some(reason)` = 不可移植（附分账用稳定 reason 码）；`None` = 合法。
/// reason 码进 IPC 分账与契约文案，三值稳定：
/// - `windows_reserved_device_name`：保留设备名（`CON.docx` 形态族）
/// - `windows_illegal_char`：保留字符或控制字符
/// - `windows_trailing_dot_or_space`：尾部点/空格（Win32 剥离面）
pub fn windows_illegal_reason(name: &str) -> Option<&'static str> {
    // 空组件交给上游（fence/落位面的空名守卫）——不在这里抢答
    if name.is_empty() {
        return None;
    }
    // ① 保留设备名：到第一个 `.` 为止的段（Win32 设备名解析口径）
    let stem = name.split('.').next().unwrap_or(name);
    if RESERVED.contains(&stem.to_lowercase().as_str()) {
        return Some("windows_reserved_device_name");
    }
    // ② 非法字符：六个保留字符 + 控制字符（0x00-0x1F）
    if name.chars().any(|c| ILLEGAL_CHARS.contains(&c) || (c as u32) < 0x20) {
        return Some("windows_illegal_char");
    }
    // ③ 尾随点/空格：Win32 剥离（NTFS 允许创建但 Win32 API 拿不到原名）
    if name.ends_with('.') || name.ends_with(' ') {
        return Some("windows_trailing_dot_or_space");
    }
    None
}

/// 相对路径整段裁决：返回首个非法组件（`Some((段名, reason))`）。
///
/// 只查相对段（fs_fence 的 rel / 落位名）：`Component::Normal` 逐段过
/// [`windows_illegal_reason`]；`CurDir`（`.`）无名字语义跳过；
/// `ParentDir`（`..`）是穿越面，归 fs_fence 词法预拒管，不在这里重复
/// 裁决（零重实现）；Prefix/RootDir 是机器本地形态（工作区搬走后不存在），
/// 不是可移植性面，跳过。
pub fn first_windows_illegal_component(rel: &Path) -> Option<(String, &'static str)> {
    for c in rel.components() {
        if let Component::Normal(seg) = c {
            let s = seg.to_string_lossy().into_owned();
            if let Some(reason) = windows_illegal_reason(&s) {
                return Some((s, reason));
            }
        }
    }
    None
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::path::Path;

    // ── 保留设备名族（口径：到第一个 `.` 的段、大小写不敏感、任意扩展名） ──

    #[test]
    fn reserved_device_names_rejected_all_forms() {
        // 全 22 个裸名
        for r in RESERVED {
            assert_eq!(
                windows_illegal_reason(r),
                Some("windows_reserved_device_name"),
                "裸名 {r} 应保留"
            );
        }
        // 大写/混合大小写
        assert_eq!(
            windows_illegal_reason("CON.docx"),
            Some("windows_reserved_device_name")
        );
        assert_eq!(
            windows_illegal_reason("Nul"),
            Some("windows_reserved_device_name")
        );
        assert_eq!(
            windows_illegal_reason("com3.tar.gz"),
            Some("windows_reserved_device_name")
        );
        // 多段扩展名：第一个 `.` 前是 com3 即保留（Win32 解析口径）
        assert_eq!(
            windows_illegal_reason("LPT1.v2.pdf"),
            Some("windows_reserved_device_name")
        );
    }

    #[test]
    fn reserved_prefix_lookalikes_pass() {
        // 相似但不同的名字合法——不为过测试放宽，也不越界加严：
        // console / auxx / com10 / lpt0 都不在保留表
        assert_eq!(windows_illegal_reason("console.docx"), None);
        assert_eq!(windows_illegal_reason("auxiliary.xlsx"), None);
        assert_eq!(windows_illegal_reason("com10.docx"), None);
        assert_eq!(windows_illegal_reason("cong.docx"), None);
        // 中文/常规名照常合法
        assert_eq!(windows_illegal_reason("招标文件.docx"), None);
        assert_eq!(windows_illegal_reason("第1章 技术方案.pdf"), None);
        assert_eq!(windows_illegal_reason("CON-2.docx"), None, "冲突后缀形态（-2）不保留");
        assert_eq!(windows_illegal_reason("NUL備份.docx"), None, "保留名嵌在其他字符中不是保留名");
    }

    // ── 非法字符面 ──

    #[test]
    fn illegal_chars_rejected() {
        assert_eq!(
            windows_illegal_reason("招<标>.docx"),
            Some("windows_illegal_char")
        );
        assert_eq!(
            windows_illegal_reason("报告:final.docx"),
            Some("windows_illegal_char")
        );
        assert_eq!(
            windows_illegal_reason("a|b.docx"),
            Some("windows_illegal_char")
        );
        assert_eq!(
            windows_illegal_reason("问?号.pdf"),
            Some("windows_illegal_char")
        );
        assert_eq!(
            windows_illegal_reason("星*号.pdf"),
            Some("windows_illegal_char")
        );
        assert_eq!(
            windows_illegal_reason("引\"号.pdf"),
            Some("windows_illegal_char")
        );
        // 控制字符（0x00-0x1F——Rust 源内用 \u 转义，不引原始字节）
        assert_eq!(
            windows_illegal_reason("a\u{01}b.docx"),
            Some("windows_illegal_char")
        );
        assert_eq!(
            windows_illegal_reason("a\u{1F}.docx"),
            Some("windows_illegal_char")
        );
        // 0x7F（DEL）文件系统层面合法——不越界加严
        assert_eq!(windows_illegal_reason("a\u{7F}.docx"), None);
        // 合法标点不受波及
        assert_eq!(windows_illegal_reason("投标(2026)-最终版.docx"), None);
        assert_eq!(windows_illegal_reason("1+1=2.docx"), None);
        assert_eq!(windows_illegal_reason("百分之%.docx"), None);
    }

    // ── 尾随点/空格面 ──

    #[test]
    fn trailing_dot_or_space_rejected() {
        assert_eq!(
            windows_illegal_reason("报告.docx."),
            Some("windows_trailing_dot_or_space")
        );
        assert_eq!(
            windows_illegal_reason("报告 "),
            Some("windows_trailing_dot_or_space")
        );
        assert_eq!(
            windows_illegal_reason("报告.docx "),
            Some("windows_trailing_dot_or_space")
        );
        // 内部点/空格合法（只有**尾随**才被 Win32 剥离）
        assert_eq!(windows_illegal_reason("技术标 v2.docx"), None);
        assert_eq!(windows_illegal_reason("2026.11.10-纪要.docx"), None);
    }

    // ── 整段路径裁决 ──

    #[test]
    fn rel_path_first_offender_reported() {
        // 首个非法段胜出（目录段与文件名同样受检）
        let (seg, reason) = first_windows_illegal_component(Path::new("CON/招标文件.docx"))
            .expect("目录段 CON 应命中");
        assert_eq!(seg, "CON");
        assert_eq!(reason, "windows_reserved_device_name");
        let (seg, _) = first_windows_illegal_component(Path::new("子目录/NUL.xlsx"))
            .expect("文件名 NUL.xlsx 应命中");
        assert_eq!(seg, "NUL.xlsx");
        // 越靠前的段越先报
        let (seg, _) = first_windows_illegal_component(Path::new("a/PRN/b<x>.docx"))
            .expect("PRN 段应先命中");
        assert_eq!(seg, "PRN");
        // 全合法
        assert_eq!(
            first_windows_illegal_component(Path::new("子目录/招标文件.docx")),
            None
        );
        // CurDir 段无名字语义（归一后不该出现，出现也不误报）
        assert_eq!(
            first_windows_illegal_component(Path::new("./子目录/招标文件.docx")),
            None
        );
        // ParentDir 是穿越面，归 fs_fence 词法预拒——本模块不重复裁决
        assert_eq!(
            first_windows_illegal_component(Path::new("../CON.docx")),
            Some(("CON.docx".to_string(), "windows_reserved_device_name"))
        );
    }
}
