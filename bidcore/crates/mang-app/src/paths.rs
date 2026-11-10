//! 路径解析 + 工作区围栏（防 ../ 穿越）。
//!
//! 规则（IPC-CONTRACT §5）：
//!   1. 相对路径 → 以工作区根为基准
//!   2. 绝对路径 → 原样使用
//!   3. canonicalize（文件不存在时 canonicalize 最近的存在祖先，再拼回剩余段）
//!   4. 结果必须位于 canonical 工作区根之下，否则 `outside_workspace`
//!
//! 刻意用「路径组件」比较而不是字符串前缀，避免 `C:\ws2` 被 `C:\ws` 误判为子目录。

use std::path::{Component, Path, PathBuf};

use crate::ipc::IpcError;

/// 拖拽/对话框返回的路径统一成 `\\?\C:\...` → `C:\...`（UI 里更好看）。
pub fn display(p: &Path) -> String {
    let s = p.to_string_lossy();
    if let Some(rest) = s.strip_prefix("\\\\?\\") {
        // UNC：\\?\UNC\server\share → \\server\share
        if let Some(unc) = rest.strip_prefix("UNC\\") {
            return format!("\\\\{unc}");
        }
        return rest.to_string();
    }
    s.into_owned()
}

fn io_err(p: &Path, e: &std::io::Error) -> IpcError {
    let code = match e.kind() {
        std::io::ErrorKind::NotFound => "not_found",
        std::io::ErrorKind::PermissionDenied => "denied",
        _ => "io",
    };
    IpcError::new(code, format!("{}: {e}", display(p)))
}

/// canonicalize；不存在时 canonicalize 最近的存在祖先再拼回剩余组件。
/// `missing_ok` 决定"整条路径不存在"时是否报 not_found。
pub fn canonicalize_lenient(p: &Path, missing_ok: bool) -> Result<PathBuf, IpcError> {
    if let Ok(c) = std::fs::canonicalize(p) {
        return Ok(c);
    }
    // 找最近的存在祖先
    let mut missing: Vec<&std::ffi::OsStr> = Vec::new();
    let mut cur = p;
    loop {
        match cur.parent() {
            Some(parent) => {
                if let Some(name) = cur.file_name() {
                    missing.push(name);
                }
                if let Ok(c) = std::fs::canonicalize(parent) {
                    let mut out = c;
                    for seg in missing.iter().rev() {
                        out.push(seg);
                    }
                    return Ok(out);
                }
                cur = parent;
            }
            None => {
                if missing_ok {
                    // 没有任何存在祖先（Windows 下几乎不会发生）——做一次纯词法规范化
                    return Ok(lexical_normalize(p));
                }
                return Err(IpcError::new(
                    "not_found",
                    format!("{}: 路径不存在", display(p)),
                ));
            }
        }
    }
}

/// 纯词法规范化（不碰磁盘）：消掉 `.`、`..`。
fn lexical_normalize(p: &Path) -> PathBuf {
    let mut out = PathBuf::new();
    for c in p.components() {
        match c {
            Component::CurDir => {}
            Component::ParentDir => {
                out.pop();
            }
            other => out.push(other.as_os_str()),
        }
    }
    out
}

/// 工作区围栏
#[derive(Debug, Clone)]
pub struct Workspace {
    /// canonical 绝对路径（不带 \\?\ 前缀的显示形态）
    root: PathBuf,
}

impl Workspace {
    pub fn new(p: &Path) -> Result<Self, IpcError> {
        let c = std::fs::canonicalize(p)
            .map_err(|e| IpcError::new("not_found", format!("工作区不存在：{}: {e}", display(p))))?;
        if !c.is_dir() {
            return Err(IpcError::new(
                "bad_args",
                format!("工作区不是目录：{}", display(&c)),
            ));
        }
        Ok(Self { root: c })
    }

    /// canonical 根（可能是 \\?\C:\... 形态，仅用于比较）
    pub fn root_canonical(&self) -> &Path {
        &self.root
    }

    /// 给 UI 看的根路径
    pub fn root_display(&self) -> String {
        display(&self.root)
    }

    /// 工作区下的子目录（用于 .mang、.mang/history 等）
    pub fn sub(&self, rel: &str) -> PathBuf {
        self.root.join(rel)
    }

    /// 把请求里的 path 解析成**已 fence 的 canonical 绝对路径**。
    ///
    /// `allow_missing`：目标不必存在（新建文件场景）。
    pub fn resolve(&self, raw: &str, allow_missing: bool) -> Result<PathBuf, IpcError> {
        let raw = raw.trim();
        if raw.is_empty() {
            return Ok(self.root.clone());
        }
        // 允许前端的 "a/b/c" 带斜杠；Windows 也接受 '/'
        let joined: PathBuf = if raw.starts_with("\\\\") || Path::new(raw).is_absolute() {
            PathBuf::from(raw)
        } else {
            let mut acc = self.root.clone();
            for seg in raw.split(['/', '\\']) {
                if seg.is_empty() || seg == "." {
                    continue;
                }
                if seg == ".." {
                    if !acc.pop() {
                        return Err(IpcError::new(
                            "outside_workspace",
                            format!("路径越界：{raw}"),
                        ));
                    }
                } else {
                    acc.push(seg);
                }
            }
            acc
        };

        let canon = canonicalize_lenient(&joined, allow_missing)?;
        if !is_inside(&canon, &self.root) {
            return Err(IpcError::new(
                "outside_workspace",
                format!(
                    "路径越界：{raw} → {} 不在工作区 {} 内",
                    display(&canon),
                    display(&self.root)
                ),
            ));
        }
        Ok(canon)
    }

    /// 把任意绝对路径（对话框/拖拽来的）转成"相对工作区的 rel 路径"；不在工作区内返回 None。
    pub fn rel_of(&self, p: &Path) -> Option<String> {
        let c = std::fs::canonicalize(p).ok()?;
        if !is_inside(&c, &self.root) {
            return None;
        }
        let rel = c.strip_prefix(&self.root).ok()?;
        Some(rel_join(rel))
    }

    /// 绝对路径 → 相对工作区的 rel（允许文件已不存在；越界返回 Err）。
    pub fn rel(&self, raw: &str) -> Result<String, IpcError> {
        let p = std::path::Path::new(raw);
        let cand = if p.is_absolute() { p.to_path_buf() } else { self.root.join(p) };
        let target = std::fs::canonicalize(&cand).or_else(|_| {
            let parent = cand.parent().map(|d| d.to_path_buf()).unwrap_or_else(|| cand.clone());
            let name = cand.file_name().map(|s| s.to_os_string());
            match (std::fs::canonicalize(parent), name) {
                (Ok(d), Some(n)) => Ok(d.join(n)),
                _ => Err(std::io::Error::new(std::io::ErrorKind::NotFound, "not found")),
            }
        });
        let c = target.map_err(|e| IpcError::io(format!("路径不存在：{raw} ({e})")))?;
        if !is_inside(&c, &self.root) {
            return Err(IpcError::denied(format!("路径越界：{raw}")));
        }
        let stripped = c.strip_prefix(&self.root).map_err(|_| IpcError::denied("路径越界"))?;
        Ok(rel_join(stripped))
    }

    /// 传 rel 是否在工作区围栏内（只做词法判断，用于早筛）
    #[allow(dead_code)]
    pub fn rel_is_sane(&self, raw: &str) -> bool {
        !raw.split(['/', '\\']).any(|s| s == "..")
    }
}

/// rel 路径统一用 '/' 分隔（Windows 上也这样给前端）
pub fn rel_join(p: &Path) -> String {
    p.components()
        .filter_map(|c| match c {
            Component::Normal(s) => Some(s.to_string_lossy().into_owned()),
            _ => None,
        })
        .collect::<Vec<_>>()
        .join("/")
}

/// 基名跨平台可移植性守卫（R10，#47 平台区分③ / R8 注释预留的硬化项）。
///
/// **两侧同拒**（不是 cfg 分支）：Linux 允许 `CON.docx`、`报告?.pdf` 这类
/// 名字，但项目库（db.json 的 upload_ref / 文件本体）要跨平台迁移——在
/// Linux 落库的保留名文件拷到 Windows 即失效/无法创建。守卫放在**壳侧
/// 入口**（ingest_drop 落位 / import_files 的 upload_ref 与 filename），
/// 域层/工具面零改动（分层不重复）。判据（Windows 文件系统规则）：
///
/// 1. 保留基名（不分大小写，含带扩展形态）：`CON PRN AUX NUL COM1-9 LPT1-9`
///    ——`CON.docx` 的主干 `CON` 同样保留（Win32 CreateFile 语义）；
/// 2. 非法字符：`< > : " | ? *` 与 ASCII 控制符（0x00-0x1F、0x7F）；
///    `/` 与 `\` 是**基名内**的路径分隔符，同样拒（基名不该含分隔符——
///    分隔符归一在 `normalize_upload_ref`，两守卫互补不重叠）；
/// 3. 尾部空格或点：Windows 剥尾点/空格后实际创建的文件名与记录键
///    不一致（幂等 sha 检查会错位）——拒。
///
/// 返回 Err(原因) 供调用方组装分账/错误文案；合法名返回 Ok(())。
/// 全角冒号 `：`、CJK 标点均合法（不在禁集）。
pub fn guard_portable_basename(name: &str) -> Result<(), String> {
    if name.is_empty() {
        return Err("基名为空".into());
    }
    // 1) 保留名：主干（第一个 '.' 前）不分大小写匹配
    let stem = name.split('.').next().unwrap_or("");
    let upper = stem.to_ascii_uppercase();
    let reserved = matches!(
        upper.as_str(),
        "CON" | "PRN" | "AUX" | "NUL"
            | "COM1" | "COM2" | "COM3" | "COM4" | "COM5" | "COM6" | "COM7" | "COM8" | "COM9"
            | "LPT1" | "LPT2" | "LPT3" | "LPT4" | "LPT5" | "LPT6" | "LPT7" | "LPT8" | "LPT9"
    );
    if reserved {
        return Err(format!(
            "Windows 保留设备名（CON/PRN/AUX/NUL/COM1-9/LPT1-9，不分大小写、带扩展同样保留）：{name}"
        ));
    }
    // 2) 非法字符：Win32 命名规则 + 路径分隔符 + 控制字符
    if let Some(bad) = name.chars().find(|&c| {
        matches!(c, '<' | '>' | ':' | '"' | '|' | '?' | '*' | '/' | '\\')
            || (c as u32) < 0x20
            || c as u32 == 0x7f
    }) {
        return Err(format!("含 Windows 非法字符 {bad:?}（<>:\"|?*/\\ 与控制符）：{name}"));
    }
    // 3) 尾部空格/点
    if name.ends_with(' ') || name.ends_with('.') {
        return Err(format!("基名以空格或点结尾（Windows 会剥掉导致落位名与记录键错位）：{name}"));
    }
    Ok(())
}

/// 字符串 NFC 归一（R13，#47 平台区分⑥——macOS NFD 互操作）。
///
/// macOS（HFS+ 时代/Finder 默认）文件名是 **NFD 分解形态**（é = e +
/// U+0301 组合符）；Linux/NTFS 字节精确存储。同一文件名两种形态是
/// **不同字节串**：落位/占位/幂等键直接比对会「视觉同名却两份」。
/// 落位名与占位键统一 **NFC**（合成形态——Windows 生态主流；CJK 与
/// ASCII 两种形态字节相同，不受影响）。**引用键（upload_ref）不归一**——
/// 它要匹配磁盘上的真实文件名，归一后反而找不到（文件本体是 NFD 存的）。
pub fn nfc(s: &str) -> String {
    use unicode_normalization::UnicodeNormalization;
    s.nfc().collect()
}

/// Windows MAX_PATH 预检（R12，#47 平台区分⑤）。
///
/// 传统 Win32 路径上限 260 字符（含 NUL 终止——字符串本体最长 259）。
/// 超限路径在未启用 `LongPathsEnabled`（注册表，默认关）+ 清单未声明
/// `longPathAware` 的进程里**创建即失败**（ERROR_PATH_NOT_FOUND）。
/// 壳侧在**写路径**（ingest_drop 落位 / import_files 记录 upload_ref）
/// 预检：Linux 上虽能创建超长路径，但项目库拷到 Windows 即失效——
/// 与 R10 保留名守卫同一跨平台可迁移性口径（双平台同拒，非 cfg）。
///
/// 边界：`len() > 259` 拒（260 含 NUL）；`\\?\` 前缀形态（>32K 上限）
/// 由宿主对话框直出时天然绕开本守卫的常规形态——壳侧拼接的路径永远
/// 是常规形态。
pub fn guard_windows_max_path(full: &str) -> Result<(), String> {
    if full.chars().count() > 259 {
        return Err(format!(
            "路径超 Windows MAX_PATH（{} 字符 > 259）：{full}…——缩短文件名/目录层级，或在 Windows 启用 LongPathsEnabled",
            full.chars().count()
        ));
    }
    Ok(())
}

/// a 是否在 b 之内（按路径组件比较，大小写不敏感——Windows 语义）
pub fn is_inside(a: &Path, b: &Path) -> bool {
    let norm = |p: &Path| -> Vec<String> {
        p.components()
            .map(|c| c.as_os_str().to_string_lossy().to_lowercase())
            .collect()
    };
    let av = norm(a);
    let bv = norm(b);
    if bv.len() > av.len() {
        return false;
    }
    av[..bv.len()] == bv[..]
}

/// 字符串基名——双分隔符（`/` 与 `\`）取最后非空段（R14，#47 平台
/// 区分⑦：混合分隔符矩阵）。
///
/// **为什么不用 `Path::file_name`**：std `Path` 按**本平台**分隔符解析——
/// `Path::new("a\\b.docx")` 在 Unix 上把整串当基名（`\` 不是 Unix 分隔
/// 符），在 Windows 上返回 `b.docx`。同一存库/传输字符串（recent 台账
/// 的 path、import 的 filename 回退）在两平台会得出不同答案——跨平台
/// 字符串数据必须用本助手（与 web-ui `baseName` 同口径，两侧同答）。
/// **真实本机路径**（read_dir 条目、落位产物）仍用 `Path::file_name`
/// （平台原生形态，天然正确）。
///
/// 语义：`资料\技术标.docx` → `技术标.docx`；尾分隔符取最后**非空**段
/// （`E:\w\` → `w`——目录形态的显示名）；全分隔符/空串回退整串原样
/// （调用方自行裁决）。**与 R10 守卫的口径分野**：守卫取「最后一段的
/// 字面值」（尾分隔符形态得空串 → 拒「基名为空」，不猜意图——严格面）；
/// 本助手是显示回退面（宽松面），两者刻意不同。
pub fn str_basename(s: &str) -> &str {
    s.rsplit(['/', '\\'])
        .find(|seg| !seg.is_empty())
        .unwrap_or(s)
}

/// 读路径时的 IO 错误 → typed error
pub fn map_io(p: &Path, e: &std::io::Error) -> IpcError {
    io_err(p, e)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn tmpws(tag: &str) -> (PathBuf, Workspace) {
        let dir = std::env::temp_dir().join(format!(
            "mang-test-{tag}-{}-{}",
            std::process::id(),
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        std::fs::create_dir_all(dir.join("sub")).unwrap();
        std::fs::write(dir.join("sub/a.md"), "hi").unwrap();
        std::fs::write(dir.join("b.txt"), "b").unwrap();
        let ws = Workspace::new(&dir).unwrap();
        (dir, ws)
    }

    #[test]
    fn resolves_inside() {
        let (dir, ws) = tmpws("inside");
        let p = ws.resolve("sub/a.md", false).unwrap();
        assert!(p.ends_with("a.md"));
        let p2 = ws.resolve("sub\\a.md", false).unwrap();
        assert_eq!(p, p2);
        let p3 = ws.resolve("b.txt", false).unwrap();
        assert!(p3.ends_with("b.txt"));
        assert_eq!(ws.rel_of(&p3).as_deref(), Some("b.txt"));
        let _ = std::fs::remove_dir_all(dir);
    }

    #[test]
    fn blocks_traversal() {
        let (dir, ws) = tmpws("escape");
        let e = ws.resolve("../x.txt", false).unwrap_err();
        assert_eq!(e.code, "outside_workspace");
        let e = ws.resolve("..\\..\\Windows\\win.ini", false).unwrap_err();
        assert_eq!(e.code, "outside_workspace");
        // 绝对路径越界同样拦
        let outside = std::env::temp_dir().join("mang-guard-outside.txt");
        let e = ws.resolve(&outside.to_string_lossy(), true).unwrap_err();
        assert_eq!(e.code, "outside_workspace");
        let _ = std::fs::remove_dir_all(dir);
    }

    #[test]
    fn sibling_prefix_not_inside() {
        // #405：is_inside 是「大小写不敏感——Windows 语义」（见其文档注释）；
        // C:\ 反斜杠串在 Linux 是单组件且无大小写折叠，两条断言只在
        // Windows 有意义（此前 mang-app 在 Linux 不可构建，从未暴露）。
        // 非 Windows 打 SKIP 横幅后跳过（AGENTS.md 13.1/13.2 平台门
        // 口径）——不是删测试，也不是放宽断言；Windows CI 上照旧真跑。
        if !cfg!(windows) {
            eprintln!(
                "SKIP: sibling_prefix_not_inside\n\
                 reason: ENV_MISSING: Windows-only 路径语义（大小写不敏感折叠）\n\
                 补救: 在 Windows（CI runner）上真跑本断言"
            );
            return;
        }
        // C:\ws2 不能被当成 C:\ws 的子目录
        assert!(!is_inside(Path::new("C:\\ws2\\x"), Path::new("C:\\ws")));
        assert!(is_inside(Path::new("C:\\WS\\x"), Path::new("C:\\ws")));
    }

    #[test]
    fn allows_missing_leaf() {
        let (dir, ws) = tmpws("missing");
        let p = ws.resolve("new/dir/file.md", true).unwrap();
        assert!(p.ends_with("file.md"));
        let _ = std::fs::remove_dir_all(dir);
    }

    /// R2（#47 平台区分①）：盘符形态（`C:/…`）的平台归类——两侧都断言
    /// 「本平台的正确语义」，不是把一侧放宽成另一侧的期望：
    ///   · Windows：`C:/x` 是绝对路径 → 越界 `outside_workspace`
    ///   · Unix：`C:` 是普通目录名 → 围栏内相对解析（落在 ws/C:/x）
    /// 与 selftest「盘符形态平台语义」项同口径（单测面 + 集成面）。
    #[test]
    fn drive_letter_form_platform_semantics() {
        let (dir, ws) = tmpws("drive-form");
        if cfg!(windows) {
            let e = ws.resolve("C:/Windows/win.ini", true).unwrap_err();
            assert_eq!(e.code, "outside_workspace");
        } else {
            let p = ws.resolve("C:/Windows/win.ini", true).unwrap();
            assert!(
                p.starts_with(dir.join("C:")),
                "Unix 上 C: 应按普通目录名围栏内解析，实际：{}",
                display(&p)
            );
        }
        let _ = std::fs::remove_dir_all(dir);
    }

    /// R10（#47 平台区分③）：基名跨平台守卫——表驱动，双平台同拒
    /// （守卫本身不是 cfg 分支；两侧跑同一断言集）
    #[test]
    fn guard_portable_basename_table() {
        // 合法名（含中文/全角标点/多位点/大写扩展——全部 Ok）
        for ok in [
            "招标文件.docx",
            "技术标 - 最终版.pdf",
            "报价单.v2.xlsx",
            "图纸目录.ods",
            "Q&A 汇总.docx",
            "说明：格式要求.docx",      // 全角冒号合法（半角 : 才拒）
            "CONCEPT 概念设计.docx",   // CON 开头但主干是 CONCEPT——不误伤
            "com.docx",                // 小写 com 是普通名（COM1-9 才保留）
        ] {
            assert!(guard_portable_basename(ok).is_ok(), "合法名被误拒：{ok}");
        }
        // 保留设备名（不分大小写、带扩展同样保留）
        for bad in [
            "CON", "con.docx", "NUL.pdf", "Aux", "aUx.xlsx",
            "COM1", "com9.docx", "LPT1", "lpt7.pdf",
        ] {
            assert!(guard_portable_basename(bad).is_err(), "保留名漏拒：{bad}");
        }
        // 非法字符（含基名内分隔符与控制符）
        for bad in [
            "报告<终稿>.docx", "计划|变更.pdf", "问?号.docx",
            "星*号.docx", "半角:冒号.docx", "引\"号.docx",
            "斜/杠.docx", "反\\斜.docx", "a\u{0007}b.docx",
        ] {
            assert!(guard_portable_basename(bad).is_err(), "非法字符漏拒：{bad}");
        }
        // 尾部空格/点 + 空名
        for bad in ["REPORT.", "报告 .docx ", ""] {
            assert!(guard_portable_basename(bad).is_err(), "形态漏拒：{bad:?}");
        }
    }

    /// R13（#47 平台区分⑥）：NFC 归一——NFD→NFC 幂等；CJK/ASCII 不动；
    /// 占位键（nfc + lowercase）双形态同键
    #[test]
    fn nfc_normalization_forms() {
        let nfc_e: String = "\u{00e9}".to_string();                 // é 单码点（合成）
        let nfd_e: String = "\u{0065}\u{0301}".to_string();        // e + 组合锐音符
        assert_ne!(nfc_e, nfd_e, "前提：两形态字节不同（同一文件名两串）");
        assert_eq!(nfc(&nfd_e), nfc_e, "NFD 输入归一到 NFC");
        assert_eq!(nfc(&nfc_e), nfc_e, "NFC 输入幂等");
        assert_eq!(nfc("招标文件.docx"), "招标文件.docx", "CJK 不受影响");
        assert_eq!(nfc("plain-ASCII.docx"), "plain-ASCII.docx", "ASCII 不受影响");
        // 占位键：NFC 大写 vs NFD 小写 → 同键（NFC 先归一再 lowercase）
        let key_a = format!("{}", nfc(&nfd_e).to_lowercase());
        let key_b = format!("{}", nfc(&"\u{00c9}".to_string()).to_lowercase());
        assert_eq!(key_a, key_b, "占位键 = nfc(name).to_lowercase()——双形态同键");
    }

    /// R12（#47 平台区分⑤）：MAX_PATH 边界——259 过 / 260 拒
    /// （260 含 NUL 终止，字符串本体上限 259）
    #[test]
    fn guard_windows_max_path_boundary() {
        let ok: String = "a".repeat(259);
        assert!(guard_windows_max_path(&ok).is_ok(), "259 字符恰在上限内");
        let bad: String = "a".repeat(260);
        let e = guard_windows_max_path(&bad).unwrap_err();
        assert!(e.contains("MAX_PATH"), "错误文案带原因：{e}");
        assert!(guard_windows_max_path("").is_ok());
        // CJK 计字符不计字节（Windows 路径上限是 UTF-16 码元——CJK 每
        // 字符占 1 码元，与 chars().count() 一致；代理对场景忽略——
        // 域内文件名不含增补平面字符，实测口径以字符数为准）
        let cjk_ok: String = "标".repeat(259);
        assert!(guard_windows_max_path(&cjk_ok).is_ok(), "259 个 CJK 字符同样在限内");
        let cjk_bad: String = "标".repeat(260);
        assert!(guard_windows_max_path(&cjk_bad).is_err());
    }

    /// R14（#47 平台区分⑦）：`str_basename` 金样矩阵——双分隔符全位置
    /// （表驱动，纯字符串面：两平台同答，无 cfg）
    #[test]
    fn str_basename_dual_separator_matrix() {
        let cases: &[(&str, &str)] = &[
            // 双分隔符取最后段（两形态同答）
            ("a\\b.docx", "b.docx"),
            ("a/b.docx", "b.docx"),
            // 混合分隔符（一个串里两种——Windows 拷来的形态）
            ("a\\b/c.docx", "c.docx"),
            ("a/b\\c.docx", "c.docx"),
            ("资料\\第一章\\技术标.docx", "技术标.docx"),
            ("资料/第一章\\技术标.docx", "技术标.docx"),
            // 盘符 / UNC 形态
            ("C:\\ws\\x.docx", "x.docx"),
            ("C:/ws/x.docx", "x.docx"),
            ("\\\\srv\\share\\x.docx", "x.docx"),
            ("//srv/share/x.docx", "x.docx"),
            // 尾分隔符：取最后非空段（目录形态的显示名）
            ("E:\\w\\", "w"),
            ("资料/", "资料"),
            // 连续分隔符：跳空段
            ("a\\\\b.docx", "b.docx"),
            ("a//b.docx", "b.docx"),
            ("a\\/b.docx", "b.docx"),
            // 无分隔符：整串即基名
            ("plain.md", "plain.md"),
            ("招标文件.docx", "招标文件.docx"),
            // 回退面：全分隔符/空串 → 原样（调用方裁决）
            ("\\\\", "\\\\"),
            ("", ""),
        ];
        for (raw, want) in cases {
            assert_eq!(str_basename(raw), *want, "str_basename({raw:?})");
        }
    }

    /// R14 cfg 双分支对照（AGENTS.md §13 平台门）：**std `Path::file_name`
    /// 按平台解析分隔符——同一输入两平台答案不同**（对照组，如实锁定；
    /// 分歧只在**纯反斜杠**形态：混合串 `a\b/c.docx` 两侧都按 `/` 切出
    /// `c.docx`，不构成分歧）；`str_basename` 双分隔符——两平台同答
    /// （修复面，断言无条件跑）。Unix 真跑本分支；Windows 分支在
    /// Windows CI 跑（本沙箱未验证——如实报告）。
    #[test]
    fn path_file_name_diverges_but_str_basename_is_platform_stable() {
        let pure = "a\\b.docx";
        #[cfg(unix)]
        {
            // Unix：`\` 不是分隔符——file_name 把整串当基名（平台分歧面）
            assert_eq!(
                std::path::Path::new(pure).file_name().unwrap().to_string_lossy(),
                pure,
                "对照组：std 在 Unix 的行为（分歧存在才是本测试的前提）"
            );
        }
        #[cfg(windows)]
        {
            // Windows：`\` 是分隔符——file_name 取最后段
            assert_eq!(
                std::path::Path::new(pure).file_name().unwrap().to_string_lossy(),
                "b.docx",
                "对照组：std 在 Windows 的行为"
            );
        }
        // 修复面：双分隔符助手两侧同答（无 cfg——这正是它存在的意义）
        assert_eq!(str_basename(pure), "b.docx");
        // 混合分隔符形态：std 两平台同答（按 `/` 切）+ 助手同答（按双切）
        assert_eq!(str_basename("a\\b/c.docx"), "c.docx");
        assert_eq!(str_basename("a/b\\c.docx"), "c.docx");
        // R13 交互：组合字符随段走、不拆段（基名面与 NFC 面正交——分层
        // 不越界；`\` 是本助手的分隔符，组合字符紧贴所属段原样保留）
        assert_eq!(str_basename("a\\cafe\u{0301}招标.docx"), "cafe\u{0301}招标.docx");
    }
}