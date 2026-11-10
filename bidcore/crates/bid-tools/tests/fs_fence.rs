//! fs_fence 单元矩阵（#183 导入面 + #189 导出面——组件级围栏的验收测试）。
//!
//! 平台策略：符号链接用例 `#[cfg(unix)]`（本地 Linux 跑）；CI 仅
//! windows-latest，伴生用例「尝试 symlink_dir，ERROR_PRIVILEGE_NOT_HELD 则
//! SKIP」（Windows 无开发者模式的托管 runner 上 symlink 创建被拒——缺权限
//! 不是测试失败）。前缀陷阱 / `..` / 组件级包含是纯 `Path::new` 断言，
//! 全平台跑（fs_fence.rs 内联 #[cfg(test)] 已覆盖 is_inside 矩阵）。

use bid_tools::fs_fence::{resolve_read, resolve_write};

fn tmp_root(tag: &str) -> std::path::PathBuf {
    let d = std::env::temp_dir().join(format!(
        "bid-fence-{tag}-{}-{}",
        std::process::id(),
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_nanos()
    ));
    std::fs::create_dir_all(d.join("sub")).unwrap();
    std::fs::write(d.join("sub/a.docx"), b"fence-a").unwrap();
    std::fs::write(d.join("b.pdf"), b"fence-b").unwrap();
    d
}

fn canon_roots(d: &std::path::Path) -> Vec<std::path::PathBuf> {
    vec![std::fs::canonicalize(d).unwrap()]
}

/// 期望路径的规范化形态——与 `Resolved::absolute()` 对齐。
///
/// 平台坑（CI windows-latest + 本地 Linux 双跑，逐轮实测）：
/// 1. Windows `temp_dir()` 返回 8.3 短名（`RUNNER~1`），`canonicalize`
///    展开长名（`runneradmin`）——期望值必须同样走 canonicalize 展开
/// 2. Windows `canonicalize` 返回 `\\?\C:\...` 扩展长度前缀，而
///    `display_path()` 会剥掉它
/// 3. 路径末尾可能还不存在（如 `no-such-dir/ghost.docx`），不能整体
///    canonicalize
///
/// 做法：从最深一层向上找【已存在】的祖先做 canonicalize，再把剩余段拼回去。
/// 分隔符归一与 `\\?\` 剥除仅 Windows 需要——Unix 上恒等（曾因无条件
/// `/`→`\` 替换把 Linux 路径全盘打碎，本地 3 条同款假红；CI 只有
/// windows-latest 所以没暴露）。
fn exp(p: &std::path::Path) -> std::path::PathBuf {
    /// 剥 \\?\ 前缀 + `/` 归一为 `\`（与 fs_fence::display_path 同规则）；
    /// Unix 恒等（canonicalize 不加前缀，分隔符本来就是 `/`）
    fn display(path: &std::path::Path) -> std::path::PathBuf {
        #[cfg(windows)]
        {
            let s = path.to_string_lossy().replace('/', "\\");
            let out = match s.strip_prefix("\\\\?\\") {
                Some(rest) => rest.to_string(),
                None => s,
            };
            std::path::PathBuf::from(out)
        }
        #[cfg(not(windows))]
        {
            path.to_path_buf()
        }
    }

    // 向上找第一个存在的祖先；不存在的段先收集起来
    let mut tail: Vec<std::ffi::OsString> = Vec::new();
    let mut cur: Option<&std::path::Path> = Some(p);
    let mut ancestor: Option<std::path::PathBuf> = None;
    while let Some(c) = cur {
        if c.exists() {
            ancestor = Some(match std::fs::canonicalize(c) {
                Ok(canon) => display(&canon),
                Err(_) => display(c),
            });
            break;
        }
        if let Some(n) = c.file_name() {
            tail.push(n.to_os_string());
        }
        cur = c.parent();
    }

    match ancestor {
        Some(mut a) => {
            for seg in tail.iter().rev() {
                a.push(seg);
            }
            a
        }
        None => display(p),
    }
}

// ---------------------------------------------------------------- read 面

/// 验收 A：工作区相对引用解析到围栏内（相对不再按进程 CWD 解析）。
#[test]
fn resolve_read_accepts_inside() {
    let root = tmp_root("rd-in");
    let roots = canon_roots(&root);
    // 相对路径
    let r = resolve_read(&roots, std::path::Path::new("sub/a.docx")).unwrap();
    assert_eq!(r.absolute(), exp(&root.join("sub/a.docx")));
    // 围栏内绝对路径（服务层内部拼接产物同款形态）
    let r = resolve_read(&roots, &root.join("b.pdf")).unwrap();
    assert_eq!(r.absolute(), exp(&root.join("b.pdf")));
    // 围栏内缺失件不是围栏条件（R-01：交给下游逐件失败，不在这里抢答）
    let r = resolve_read(&roots, std::path::Path::new("no-such-dir/ghost.docx")).unwrap();
    assert_eq!(r.absolute(), exp(&root.join("no-such-dir/ghost.docx")));
    let _ = std::fs::remove_dir_all(&root);
}

/// `..` 词法预拒（先于一切磁盘操作——不存在的路径也不给试探机会）。
#[test]
fn resolve_read_rejects_parent_traversal() {
    let root = tmp_root("rd-dot");
    let roots = canon_roots(&root);
    for bad in ["../escape.docx", "sub/../../escape.docx", ".."] {
        let e = resolve_read(&roots, std::path::Path::new(bad)).unwrap_err();
        assert!(matches!(e, bid_domain::ToolError::EUnprocessable { .. }), "{bad}: {e:?}");
        let msg = format!("{e:?}");
        assert!(msg.contains(".."), "{bad} 应报父级逃逸：{msg}");
    }
    // 绝对路径带 .. 同样词法拒（不做「词法归一后可能在围栏内」的宽容）
    let e = resolve_read(
        &roots,
        &std::env::temp_dir().join("../etc/passwd"),
    )
    .unwrap_err();
    assert!(matches!(e, bid_domain::ToolError::EUnprocessable { .. }));
    let _ = std::fs::remove_dir_all(&root);
}

/// 绝对路径越界（围栏外任意本地文件——#183 的数据外泄入口，必须拦）。
#[test]
fn resolve_read_rejects_absolute_outside() {
    let root = tmp_root("rd-out");
    let roots = canon_roots(&root);
    let outside = std::env::temp_dir().join(format!(
        "bid-fence-outside-{}.txt",
        std::process::id()
    ));
    std::fs::write(&outside, b"secret").unwrap();
    let e = resolve_read(&roots, &outside).unwrap_err();
    assert!(matches!(e, bid_domain::ToolError::EUnprocessable { .. }));
    let msg = format!("{e:?}");
    assert!(msg.contains("越界"), "应报越界：{msg}");
    let _ = std::fs::remove_file(&outside);
    let _ = std::fs::remove_dir_all(&root);
}

/// 姊妹目录前缀陷阱（#189 判定 D）：`/tmp/ws-evil` 不得命中 `/tmp/ws`
/// （组件级比较，不是字符串前缀）。
#[test]
fn resolve_read_rejects_sibling_prefix_trap() {
    let root = tmp_root("rd-pfx");
    let evil = root.parent().unwrap().join(format!(
        "{}-evil{}",
        root.file_name().unwrap().to_string_lossy(),
        ""
    ));
    std::fs::create_dir_all(&evil).unwrap();
    std::fs::write(evil.join("x.docx"), b"evil").unwrap();
    let roots = canon_roots(&root);
    let e = resolve_read(&roots, &evil.join("x.docx")).unwrap_err();
    assert!(matches!(e, bid_domain::ToolError::EUnprocessable { .. }));
    let msg = format!("{e:?}");
    assert!(msg.contains("越界"), "前缀陷阱必须按越界拒：{msg}");
    let _ = std::fs::remove_dir_all(&evil);
    let _ = std::fs::remove_dir_all(&root);
}

/// 符号链接逃逸（unix）：围栏内 symlink 段指向围栏外 → 拒。
#[test]
#[cfg(unix)]
fn resolve_read_rejects_symlink_escape() {
    let root = tmp_root("rd-sym");
    let outside = std::env::temp_dir().join(format!(
        "bid-fence-outside-dir-{}",
        std::process::id()
    ));
    std::fs::create_dir_all(&outside).unwrap();
    std::fs::write(outside.join("secret.pdf"), b"secret").unwrap();
    std::os::unix::fs::symlink(&outside, root.join("link")).unwrap();
    let roots = canon_roots(&root);

    // 段本身是 symlink（即使 canonicalize 后落在围栏外——canonicalize 已经
    // 解析掉 symlink，越界在此拦）
    let e = resolve_read(&roots, std::path::Path::new("link/secret.pdf")).unwrap_err();
    assert!(matches!(e, bid_domain::ToolError::EUnprocessable { .. }), "{e:?}");

    // 指向围栏内的 symlink 也拒（canonicalize 会把它洗白成 /ws/real/x——
    // 逐段 symlink 检查在用户拼写面拦下，围栏内不允许 symlink，策略从严）
    std::fs::create_dir_all(root.join("real")).unwrap();
    std::fs::write(root.join("real/y.docx"), b"y").unwrap();
    std::os::unix::fs::symlink("real", root.join("inlink")).unwrap();
    let e = resolve_read(&roots, std::path::Path::new("inlink/y.docx")).unwrap_err();
    assert!(matches!(e, bid_domain::ToolError::EUnprocessable { .. }));
    let msg = format!("{e:?}");
    assert!(msg.contains("符号链接"), "应报符号链接段：{msg}");

    let _ = std::fs::remove_dir_all(&outside);
    let _ = std::fs::remove_dir_all(&root);
}

/// Windows 伴生用例：尝试建 symlink；无开发者模式权限（ERROR_PRIVILEGE_NOT_HELD）
/// 则 SKIP（CI 托管 runner 常态——缺权限不是测试失败）。
#[test]
#[cfg(windows)]
fn resolve_read_rejects_symlink_escape_windows() {
    let root = tmp_root("rd-symw");
    let outside = std::env::temp_dir().join(format!("bid-fence-outside-w-{}", std::process::id()));
    std::fs::create_dir_all(&outside).unwrap();
    std::fs::write(outside.join("secret.pdf"), b"secret").unwrap();
    match std::os::windows::fs::symlink_dir(&outside, root.join("link")) {
        Ok(()) => {
            let roots = canon_roots(&root);
            let e = resolve_read(&roots, std::path::Path::new("link/secret.pdf")).unwrap_err();
            assert!(matches!(e, bid_domain::ToolError::EUnprocessable { .. }), "{e:?}");
        }
        Err(e) if e.raw_os_error() == Some(1314) => {
            eprintln!("[SKIP] symlink 创建被拒（ERROR_PRIVILEGE_NOT_HELD）：{e}");
        }
        Err(e) => panic!("symlink_dir 意外失败：{e}"),
    }
    let _ = std::fs::remove_dir_all(&outside);
    let _ = std::fs::remove_dir_all(&root);
}

// ---------------------------------------------------------------- write 面

/// 写面：目标文件可不存在（lenient canonicalize 最近存在祖先 + 拼回剩余段）。
#[test]
fn resolve_write_accepts_new_leaf() {
    let root = tmp_root("wr-in");
    let roots = canon_roots(&root);
    let r = resolve_write(&roots, std::path::Path::new("out/deep/标书.docx")).unwrap();
    assert_eq!(r.absolute(), exp(&root.join("out/deep/标书.docx")));
    // 已存在的目标原样过
    let r = resolve_write(&roots, std::path::Path::new("b.pdf")).unwrap();
    assert_eq!(r.absolute(), exp(&root.join("b.pdf")));
    let _ = std::fs::remove_dir_all(&root);
}

/// 写面：`..` 与绝对越界同拒（含前缀陷阱）。
#[test]
fn resolve_write_rejects_parent_traversal_and_outside() {
    let root = tmp_root("wr-out");
    let roots = canon_roots(&root);
    let e = resolve_write(&roots, std::path::Path::new("../evil.docx")).unwrap_err();
    assert!(matches!(e, bid_domain::ToolError::EUnprocessable { .. }));
    let outside = std::env::temp_dir().join(format!("bid-fence-w-out-{}.docx", std::process::id()));
    let e = resolve_write(&roots, &outside).unwrap_err();
    assert!(matches!(e, bid_domain::ToolError::EUnprocessable { .. }));
    let msg = format!("{e:?}");
    assert!(msg.contains("越界"), "应报越界：{msg}");
    // 前缀陷阱：c:/bid/work-evil 不得当成 c:/bid/work 之内（#189 核心修法）
    let evil = root.parent().unwrap().join(format!(
        "{}-evil2",
        root.file_name().unwrap().to_string_lossy()
    ));
    let e = resolve_write(&roots, &evil.join("x.docx")).unwrap_err();
    assert!(matches!(e, bid_domain::ToolError::EUnprocessable { .. }));
    let _ = std::fs::remove_dir_all(&root);
}

/// 写面符号链接逃逸（unix）：`out/link/x.docx`（link→外部目录）必须拦下——
/// 一路畅通就到 export.rs 的 File::create + rename（#189 的任意写入口）。
#[test]
#[cfg(unix)]
fn resolve_write_rejects_symlink_escape() {
    let root = tmp_root("wr-sym");
    let outside = std::env::temp_dir().join(format!(
        "bid-fence-w-outside-{}",
        std::process::id()
    ));
    std::fs::create_dir_all(&outside).unwrap();
    std::fs::create_dir_all(root.join("out")).unwrap();
    std::os::unix::fs::symlink(&outside, root.join("out/link")).unwrap();
    let roots = canon_roots(&root);

    let e = resolve_write(&roots, std::path::Path::new("out/link/x.docx")).unwrap_err();
    assert!(matches!(e, bid_domain::ToolError::EUnprocessable { .. }), "{e:?}");
    let msg = format!("{e:?}");
    assert!(
        msg.contains("符号链接") || msg.contains("越界"),
        "symlink 逃逸必须拒（canonicalize 越界或逐段 symlink 检查任一命中）：{msg}"
    );
    // 落地证据：不在围栏外产出任何文件位（resolve_write 只做校验，不建文件——
    // 这里断言校验本身就拦了请求）
    assert!(!outside.join("x.docx").exists());

    // 指向围栏内的 symlink 段同样拒（写面同策略）
    std::os::unix::fs::symlink(".", root.join("out/self")).unwrap();
    let e = resolve_write(&roots, std::path::Path::new("out/self/y.docx")).unwrap_err();
    assert!(matches!(e, bid_domain::ToolError::EUnprocessable { .. }));

    let _ = std::fs::remove_dir_all(&outside);
    let _ = std::fs::remove_dir_all(&root);
}

/// Windows 伴生用例（写面 symlink，权限缺失则 SKIP）。
#[test]
#[cfg(windows)]
fn resolve_write_rejects_symlink_escape_windows() {
    let root = tmp_root("wr-symw");
    let outside = std::env::temp_dir().join(format!("bid-fence-w-outside-w-{}", std::process::id()));
    std::fs::create_dir_all(&outside).unwrap();
    std::fs::create_dir_all(root.join("out")).unwrap();
    match std::os::windows::fs::symlink_dir(&outside, root.join("out/link")) {
        Ok(()) => {
            let roots = canon_roots(&root);
            let e = resolve_write(&roots, std::path::Path::new("out/link/x.docx")).unwrap_err();
            assert!(matches!(e, bid_domain::ToolError::EUnprocessable { .. }), "{e:?}");
        }
        Err(e) if e.raw_os_error() == Some(1314) => {
            eprintln!("[SKIP] symlink 创建被拒（ERROR_PRIVILEGE_NOT_HELD）：{e}");
        }
        Err(e) => panic!("symlink_dir 意外失败：{e}"),
    }
    let _ = std::fs::remove_dir_all(&outside);
    let _ = std::fs::remove_dir_all(&root);
}

/// 多根围栏：fs_root 覆盖面（如测试夹具根）+ 隐式工作区根——两个根内都放行，
/// 两个根外都拒（导入导出同一套判定）。
#[test]
fn multi_root_read_and_write() {
    let root_a = tmp_root("multi-a");
    let root_b = tmp_root("multi-b");
    let roots = vec![
        std::fs::canonicalize(&root_a).unwrap(),
        std::fs::canonicalize(&root_b).unwrap(),
    ];
    // a 内读
    assert!(resolve_read(&roots, std::path::Path::new("sub/a.docx")).is_ok());
    // b 内绝对写（相对锚定 roots[0]，跨根用绝对）
    let r = resolve_write(&roots, &root_b.join("new/deep.docx")).unwrap();
    assert_eq!(r.absolute(), exp(&root_b.join("new/deep.docx")));
    // 越界仍拒
    let outside = std::env::temp_dir().join(format!("bid-fence-multi-out-{}.docx", std::process::id()));
    assert!(resolve_read(&roots, &outside).is_err());
    assert!(resolve_write(&roots, &outside).is_err());
    let _ = std::fs::remove_dir_all(&root_a);
    let _ = std::fs::remove_dir_all(&root_b);
}

/// 空根清单 → 响亮拒（纯内存态未声明根——错误信息指路 BID_WS）。
#[test]
fn empty_roots_rejected_with_guidance() {
    let e = resolve_read(&[], std::path::Path::new("a.docx")).unwrap_err();
    assert!(matches!(e, bid_domain::ToolError::EUnprocessable { .. }));
    let msg = format!("{e:?}");
    assert!(msg.contains("BID_WS"), "应指路 BID_WS：{msg}");
    let e = resolve_write(&[], std::path::Path::new("a.docx")).unwrap_err();
    assert!(matches!(e, bid_domain::ToolError::EUnprocessable { .. }));
}

// ── R14（#47 跨平台硬化⑦）：混合分隔符矩阵 ────────────────────────────
//
// 面：MCP 直调（import_tender_files / 导出 output_path）不经壳侧 R9 归一，
// 原始混合分隔符形态直接进围栏。三层矩阵：
//   1. 共享不变量（无 cfg，两平台同断言）：**任何形态都不逃逸围栏**——
//      Ok 则解析结果必在根内；Err 则必是 EUnprocessable（词法/越界/不可
//      解析拒）。围栏的安全语义平台无关；
//   2. cfg 双分支对照（AGENTS.md §13）：解析**形态**两平台不同——Unix 把
//      `\` 当普通字符（单段字面名）；Windows 当分隔符（真子目录/词法拒
//      `..`）。两侧各自锁定确定行为；
//   3. UNC 形态（`\\srv\sh\x` / `//srv/sh/x`）：两侧都拒（词法门或
//      canonicalize 后不在根内——不是本工作区的引用没有放行语义）。

/// 共享不变量：混合分隔符任何形态不逃逸围栏（Ok 必在根内 / Err 必是
/// EUnprocessable——两平台跑同一断言集）。
#[test]
fn mixed_separator_never_escapes_fence() {
    let root = tmp_root("mx-esc");
    let roots = canon_roots(&root);
    let mixed_forms = [
        "sub\\a.docx",
        "sub\\..\\a.docx",
        "..\\escape.docx",
        "a\\..\\b\\c.docx",
        "\\\\srv\\sh\\x.docx",
        "//srv\\sh\\x.docx",
    ];
    for form in mixed_forms {
        match resolve_read(&roots, std::path::Path::new(form)) {
            Ok(r) => assert!(
                bid_tools::fs_fence::is_inside(&r.absolute(), &roots[0]),
                "{form}: 解析结果必须在围栏内（绝不逃逸）：{}",
                r.absolute().display()
            ),
            Err(e) => assert!(
                matches!(e, bid_domain::ToolError::EUnprocessable { .. }),
                "{form}: 拒绝必须是 EUnprocessable（词法/越界），实际：{e:?}"
            ),
        }
    }
    // 写面同规（输出路径混合形态同样不逃逸）
    match resolve_write(&roots, std::path::Path::new("out\\x.docx")) {
        Ok(r) => assert!(
            bid_tools::fs_fence::is_inside(&r.absolute(), &roots[0]),
            "写面解析结果必须在围栏内：{}",
            r.absolute().display()
        ),
        Err(e) => assert!(
            matches!(e, bid_domain::ToolError::EUnprocessable { .. }),
            "写面拒绝必须是 EUnprocessable：{e:?}"
        ),
    }
    let _ = std::fs::remove_dir_all(&root);
}

/// cfg 双分支对照（Unix 侧）：`\` 是普通字符——`sub\a.docx` 是**单段字面
/// 名**（不会进 sub/ 子目录）；`sub\..\a.docx` 的 `..` 不是分量（词法门
/// 不拒），但字面名穿不透围栏（canonicalize 锚定在根内的字面路径）。
/// 下游（sha256_file）按「不可读」逐件失败——不是逃逸，是怪名。
#[test]
#[cfg(unix)]
fn mixed_separator_unix_backslash_is_literal_character() {
    let root = tmp_root("mx-u");
    let roots = canon_roots(&root);
    let r = resolve_read(&roots, std::path::Path::new("sub\\a.docx")).unwrap();
    assert_eq!(
        r.absolute(),
        exp(&root.join("sub\\a.docx")),
        "Unix：整串是单段字面名（落在根下，不进 sub/）"
    );
    let r = resolve_read(&roots, std::path::Path::new("sub\\..\\a.docx")).unwrap();
    assert_eq!(
        r.absolute(),
        exp(&root.join("sub\\..\\a.docx")),
        "Unix：`..` 在字面名内不是分量——词法门不拒，但也穿不透"
    );
    // UNC 反斜杠形态：词法非绝对（Unix 无 \\ 前缀语义）→ 锚定根内单段名
    let r = resolve_read(&roots, std::path::Path::new("\\\\srv\\sh\\x.docx")).unwrap();
    assert!(
        bid_tools::fs_fence::is_inside(&r.absolute(), &roots[0]),
        "Unix：UNC 形态锚定为根内字面名"
    );
    let _ = std::fs::remove_dir_all(&root);
}

/// cfg 双分支对照（Windows 侧）：`\` 是分隔符——`sub\a.docx` 进真子目录；
/// `sub\..\a.docx` 的 `..` 是分量 → 词法预拒（与 `sub/../a.docx` 同罪）。
#[test]
#[cfg(windows)]
fn mixed_separator_windows_backslash_is_separator() {
    let root = tmp_root("mx-w");
    let roots = canon_roots(&root);
    let r = resolve_read(&roots, std::path::Path::new("sub\\a.docx")).unwrap();
    assert_eq!(
        r.absolute(),
        exp(&root.join("sub").join("a.docx")),
        "Windows：反斜杠分隔——解析进 sub/ 子目录"
    );
    let e = resolve_read(&roots, std::path::Path::new("sub\\..\\a.docx")).unwrap_err();
    assert!(
        matches!(e, bid_domain::ToolError::EUnprocessable { .. }),
        "Windows：`..` 分量词法拒：{e:?}"
    );
    let _ = std::fs::remove_dir_all(&root);
}
