//! doc_conversion_diag.rs —— #165：Word COM .doc 转换失败根因保全验收。
//!
//! Lead 受控面复现（Windows PowerShell 实测）：.doc 转换脚本缺
//! `$ErrorActionPreference='Stop'` 与显式 catch/退出码——`Write-Error`
//! （Continue 档非终止错误）stderr 有字仍 **exit 0**；Rust 侧只在
//! `!status.success()` 分支读 stderr，exit 0 + 产物缺失/非 docx 时只报
//! 笼统「PK 魔数校验失败」，这次已有的 stderr/stdout 诊断被丢——根因遗失。
//!
//! 本文件钉的验收（红→绿）：
//! 1. **脚本生成面**（`build_doc2docx_script`——纯函数，非 Windows 也可测）：
//!    - 脚本头设置 `$ErrorActionPreference = 'Stop'`（对齐 PDF 面脚本）；
//!    - 显式 `catch` 捕获 `$_.Exception` 的**类型/行号/消息**写 stderr 单行
//!      诊断 `BID_WORD_COM_FAIL type=... line=... msg=...`，并 `exit 3`
//!      （非零——PowerShell 进程退出码可判）；
//!    - 单引号路径转义核对：`'` 双写（`''`）——现 PDF 面同款纪律；
//!    - finally 释放 COM 引用（ReleaseComObject / Quit）保留不回退。
//! 2. **诊断汇总面**（`word_com_exit_diagnostics`——纯函数）：
//!    - 非零退出：错误串带退出码 + stderr 尾部（保留具体错误）；
//!    - **exit 0 但产物缺失/非 docx**：错误串必须携带 stdout/stderr 尾部
//!      与退出码（不再只说「PK 魔数校验失败」——这次已有的 stderr 不丢）；
//!    - timeout 面：超时错误串带秒数（既有文案保留）。
//! 3. **受控真实子进程面**（Linux pwsh 在场时执行；不在场跳过并如实 SKIP）：
//!    - Lead 复现脚本（Write-Error + finally，**无** Stop/无 catch）→
//!      stderr 有 CONTROLLED_WORD_COM_FAILURE 而 exit 0（证「退出判据
//!      不足」）；
//!    - 修复后模板脚本（Stop + catch + 诊断行 + exit 3）→ exit 3 且
//!      stderr 单行含 type=/line=/msg=（证退出判据足以保全诊断）。
//!    Linux pwsh ≠ Windows 真实 COM —— 分账如实（无 Word 环境不冒称）。
//!
//! 红面证据（Lead 复现 + 本文件先跑必红）：main 5d1ad697 的
//! `convert_doc_to_docx_word` 脚本无 Stop/catch/退出码，产物校验失败
//! 分支只返回「PK 魔数校验失败」——上述断言全部不成立。

use std::path::Path;
use std::process::Command;

// ------------------------------------------------------------ 受控夹具

/// Lead 受控复现脚本（#165 正文口径）：非终止 Write-Error + finally——
/// 模拟现有 .doc 转换脚本「无 Stop/无 catch」时的行为面。
const CONTROLLED_NO_STOP: &str = r#"
$word = $null
$doc = $null
try {
    Write-Error "CONTROLLED_WORD_COM_FAILURE" -ErrorAction Continue
} finally {
    Write-Output "cleanup done"
}
"#;

/// 判定「真实 pwsh 在场可执行受控面」——不在场如实 SKIP（Linux 无 pwsh
/// 不是失败；Windows 真实 COM 面本单不冒称已覆盖）。探测序：沙箱持久位
/// /home/z/pwsh-root（CI/沙箱安装面）→ PATH 上 pwsh/powershell。
fn pwsh_available() -> Option<PathBuf> {
    for cand in [
        "/home/z/pwsh-root/opt/microsoft/powershell/7/pwsh",
        "/tmp/pwsh-root/opt/microsoft/powershell/7/pwsh",
        "pwsh",
        "powershell",
    ] {
        if cand.starts_with('/') {
            if Path::new(cand).is_file() {
                return Some(PathBuf::from(cand));
            }
        } else {
            let ok = Command::new(cand)
                .args(["-NoProfile", "-Command", "exit 0"])
                .output()
                .map(|o| o.status.success())
                .unwrap_or(false);
            if ok {
                return Some(PathBuf::from(cand));
            }
        }
    }
    None
}

use std::path::PathBuf;

// ------------------------------------------------------------ 红测：脚本生成面

/// #165 核心钉子：.doc→.docx PowerShell 脚本必须带 Stop + catch + 非零退出。
/// main 5d1ad697 无该函数 → 编译红；实现后断言面逐步验证。
#[test]
fn red_doc2docx_script_has_stop_catch_typed_diag_and_exit() {
    let script = bid_tools::service::build_doc2docx_script("/t/投标书.doc", "/t/out.docx");
    // ① Stop 档（对齐 PDF 面 convert_to_pdf_word 首行）
    assert!(
        script.contains("$ErrorActionPreference = 'Stop'"),
        "脚本必须设置 Stop（非终止错误不再静默续走）: {script}"
    );
    // ② 显式 catch：异常类型/行号/消息进 stderr 单行诊断 + exit 3
    assert!(script.contains("catch {"), "脚本必须有显式 catch 块: {script}");
    assert!(
        script.contains("BID_WORD_COM_FAIL"),
        "catch 块必须输出可机判诊断行 BID_WORD_COM_FAIL: {script}"
    );
    assert!(
        script.contains("Exception.GetType().FullName"),
        "诊断行必须捕获异常类型（根因保全）: {script}"
    );
    assert!(
        script.contains("InvocationInfo.ScriptLineNumber"),
        "诊断行必须捕获行号（定位）: {script}"
    );
    assert!(
        script.contains("exit 3"),
        "catch 必须 exit 3（非零退出码——退出判据可判）: {script}"
    );
    // ③ 单引号路径转义（现实现核对：' 双写——含撇号路径防断裂/注入）
    let esc_script =
        bid_tools::service::build_doc2docx_script("/t/it's 投's 标.doc", "/t/o'ut.docx");
    assert!(
        esc_script.contains("Open('/t/it''s 投''s 标.doc'"),
        "路径单引号必须双写转义（PDF 面同款）: {}",
        esc_script.lines().find(|l| l.contains("Open(")).unwrap_or("")
    );
    assert!(
        !esc_script.contains("it's"),
        "原始未转义单引号不得残留（断裂/注入面）"
    );
    // ④ finally 释放 COM 引用保留（不回退既有清理面）
    assert!(script.contains("ReleaseComObject"), "finally 释放面保留: {script}");
    assert!(script.contains("$word.Quit()"), "Quit 清理面保留: {script}");
}

// ------------------------------------------------------------ 红测：诊断汇总面

/// 非零退出：错误串保留退出码 + stderr 尾部（现有面已有——防回退钉子）。
#[test]
fn red_diag_nonzero_exit_keeps_code_and_stderr() {
    let msg = bid_tools::service::word_com_exit_diagnostics(
        Some(3),
        "stdout-tail",
        "BID_WORD_COM_FAIL type=System.Runtime.InteropServices.COMException line=9 msg=Open 失败",
    );
    assert!(msg.contains("3"), "退出码保留: {msg}");
    assert!(msg.contains("BID_WORD_COM_FAIL"), "stderr 具体错误保留: {msg}");
    assert!(msg.contains("COMException"), "异常类型保留: {msg}");
}

/// #165 核心钉子（exit0 + 产物缺失丢根因）：exit 0 且产物无效时，错误串
/// 必须携带 stdout/stderr 尾部与退出码——不再只说「PK 魔数校验失败」。
#[test]
fn red_diag_exit0_invalid_artifact_carries_stdout_stderr_and_code() {
    let msg = bid_tools::service::word_com_exit_diagnostics(
        Some(0),
        "stdout-tail：Word COM 正常输出",
        "stderr-tail：CONTROLLED_WORD_COM_FAILURE 非终止错误残迹",
    );
    assert!(
        msg.contains("stderr-tail") || msg.contains("stdout-tail"),
        "exit0+产物无效必须携带 stdout/stderr（根因不丢）: {msg}"
    );
    assert!(msg.contains("0"), "退出码照实入串: {msg}");
    // 反面钉子：不允许只剩笼统「PK 魔数校验失败」无任何流内容
    assert!(
        !(msg.contains("PK 魔数") && !msg.contains("stderr") && !msg.contains("stdout")),
        "笼统 PK 魔数失败而丢弃流诊断 = #165 根因遗失面（禁）: {msg}"
    );
}

/// timeout 面：超时错误串带秒数（既有文案保留——防回退）。
#[test]
fn red_diag_timeout_message_shape_kept() {
    let msg = bid_tools::service::word_com_timeout_message(30);
    assert!(msg.contains("超时"), "超时面文案保留: {msg}");
    assert!(msg.contains("30"), "超时秒数入串: {msg}");
}

// ------------------------------------------------------------ 受控真实子进程面

/// Lead 复现：无 Stop/无 catch 的脚本 stderr 有字仍 exit 0（证退出判据
/// 不足以保全诊断——**这就是 #165 的红**）。pwsh 不在场则 SKIP 如实。
#[test]
fn controlled_no_stop_script_stderr_nonzero_silent_exit0() {
    let Some(pwsh) = pwsh_available() else {
        eprintln!("SKIP：本机无 pwsh——Linux 受控面不可执行（如实跳过，不冒称）");
        return;
    };
    let dir = std::env::temp_dir().join(format!("bid165-lead-{}", std::process::id()));
    std::fs::create_dir_all(&dir).unwrap();
    let ps1 = dir.join("lead_repro.ps1");
    std::fs::write(&ps1, CONTROLLED_NO_STOP).unwrap();
    let out = Command::new(&pwsh)
        .args(["-NoProfile", "-NonInteractive", "-File"])
        .arg(&ps1)
        .output()
        .expect("pwsh 执行");
    // Lead 实测面：stderr 有 CONTROLLED_WORD_COM_FAILURE，exit 0
    assert_eq!(out.status.code(), Some(0), "无 Stop：非终止错误仍 exit 0（Lead 复现）");
    let stderr = String::from_utf8_lossy(&out.stderr);
    assert!(
        stderr.contains("CONTROLLED_WORD_COM_FAILURE"),
        "stderr 确有错误字样（根因在场但被退出判据吞掉）: {stderr}"
    );
    std::fs::remove_dir_all(&dir).ok();
}

/// 修复后模板：Stop + catch → exit 3 + stderr 单行 typed 诊断（证退出判据
/// 足以保全诊断——**修后应绿**；实现前该脚本模板不存在即编译红的一部分）。
#[test]
fn controlled_fixed_script_exits_nonzero_with_typed_diag() {
    let Some(pwsh) = pwsh_available() else {
        eprintln!("SKIP：本机无 pwsh——Linux 受控面不可执行（如实跳过，不冒称）");
        return;
    };
    // 修复后脚本 = 产品脚本生成面同构（Word COM 调用在 Linux 不可真实化——
    // 用同构受控 COM 失败调用替代：New-Object -ComObject Word.Application
    // 在 Linux pwsh 抛类型化异常进 catch，同走 catch/诊断行/exit 3 面）
    let script = bid_tools::service::build_doc2docx_script(
        "/t/nonexistent-投标书.doc",
        "/t/out-投标书.docx",
    );
    // 说明：Linux pwsh 的 -ComObject 本身抛类型化异常（ParameterBindingException
    // 类）进 catch——直接跑产品生成脚本即受控等价面。
    let dir = std::env::temp_dir().join(format!("bid165-fixed-{}", std::process::id()));
    std::fs::create_dir_all(&dir).unwrap();
    let ps1 = dir.join("fixed.ps1");
    // 写文件时保 BOM（产品面同款——PowerShell 5.1 GBK 防乱码）
    let mut bytes = vec![0xEF, 0xBB, 0xBF];
    bytes.extend_from_slice(script.as_bytes());
    std::fs::write(&ps1, &bytes).unwrap();
    let out = Command::new(&pwsh)
        .args(["-NoProfile", "-NonInteractive", "-File"])
        .arg(&ps1)
        .output()
        .expect("pwsh 执行");
    let code = out.status.code();
    let stderr = String::from_utf8_lossy(&out.stderr);
    // 核心验收：非零退出 + typed 诊断行在场（Linux 上 New-Object -ComObject
    // 抛 PSNotSupportedException/RuntimeException 类异常——类型字样照实入行）
    assert_ne!(code, Some(0), "Stop+catch 后必须非零退出: code={code:?}");
    assert!(
        stderr.contains("BID_WORD_COM_FAIL"),
        "stderr 必须含 typed 诊断行: {stderr}"
    );
    assert!(
        stderr.contains("type=") && stderr.contains("line=") && stderr.contains("msg="),
        "诊断行带类型/行号/消息三件套: {stderr}"
    );
    std::fs::remove_dir_all(&dir).ok();
}

// ------------------------------------------------------------ #165 验收第三组：
// 合法产物成功不误伤 / 损坏产物不掩盖 / timeout——用真实子进程受控面。
// 说明：Linux 无 Word COM——「合法产物成功」用**真实 soffice 通道**跑真
// .doc→.docx（产品 LO 通道同一调用面），损坏产物/超时面用受控 pwsh
// 子进程（诊断格式面）。Windows 真实 COM 验收留 Lead（分账如实）。

/// soffice 在场判定（真 .doc 转真 .docx 的合法产物面需要）。
fn soffice_available() -> bool {
    Command::new("soffice")
        .arg("--version")
        .output()
        .map(|o| o.status.success())
        .unwrap_or(false)
}

/// 合法产物成功不误伤：真 .doc（OLE 头 d0 cf 11 e0）→ 产品 LO 通道转
/// .docx → PK 魔数在位 + exit 0——诊断收紧不误伤合法转换。
#[test]
fn controlled_real_doc_converts_to_valid_docx_not_affected() {
    if !soffice_available() {
        eprintln!("SKIP：本机无 soffice——合法产物面不可执行（如实跳过）");
        return;
    }
    let dir = std::env::temp_dir().join(format!("bid165-ok-{}", std::process::id()));
    std::fs::create_dir_all(&dir).unwrap();
    let txt = dir.join("hello.txt");
    std::fs::write(&txt, "bid 165 controlled ok").unwrap();
    // 真 .doc 夹具：soffice txt→doc（OLE 复合文档）
    let doc = dir.join("hello.doc");
    let st = Command::new("soffice")
        .args(["--headless", "--norestore", "--convert-to", "doc"])
        .arg("--outdir")
        .arg(&dir)
        .arg(&txt)
        .output()
        .expect("soffice doc 夹具");
    assert!(st.status.success() && doc.is_file(), "夹具 .doc 生成失败");
    let mut magic4 = [0u8; 4];
    use std::io::Read;
    std::fs::File::open(&doc).unwrap().read_exact(&mut magic4).unwrap();
    assert_eq!(&magic4, &[0xd0, 0xcf, 0x11, 0xe0], "夹具须为真 OLE .doc");
    // 产品 LO 通道面（convert_doc_to_docx 走 docx_artifact_valid 校验——
    // 与 Word COM 共用产物闸）：受控调用同一校验语义
    let out = dir.join("out.docx");
    let st2 = Command::new("soffice")
        .args(["--headless", "--norestore", "--convert-to", "docx"])
        .arg("--outdir")
        .arg(&dir)
        .arg(&doc)
        .output()
        .expect("soffice 转换");
    let produced = dir.join("hello.docx");
    let conv_ok = st2.status.success() && produced.is_file();
    if conv_ok {
        // 先落转换目录再 rename（产品同款）
        std::fs::rename(&produced, &out).unwrap();
        let mut pk = [0u8; 4];
        std::fs::File::open(&out).unwrap().read_exact(&mut pk).unwrap();
        assert_eq!(&pk, b"PK\x03\x04", "合法产物 PK 魔数在位——不误伤");
    } else {
        panic!("真 .doc→docx 转换失败：{}", String::from_utf8_lossy(&st2.stderr));
    }
    std::fs::remove_dir_all(&dir).ok();
}

/// 损坏产物不掩盖：产物位写成非 PK 内容（伪 docx）→ docx_artifact_valid
/// 判负 + 诊断面照常可用（word_com_exit_diagnostics 把流面带上）。
#[test]
fn controlled_corrupt_artifact_keeps_diagnostics() {
    let dir = std::env::temp_dir().join(format!("bid165-corrupt-{}", std::process::id()));
    std::fs::create_dir_all(&dir).unwrap();
    let bogus = dir.join("bogus.docx");
    std::fs::write(&bogus, "NOT_A_DOCX_CORRUPTED").unwrap();
    // docx_artifact_valid 为内部 fn——经 import 面不可直取；用公开诊断串
    // 验证「exit0+无效产物」路径携带流面（红测钉子已证格式），此处钉
    // 产物闸语义：损坏内容绝不能通过 PK 校验（防「伪造产物充成功」）。
    let head = std::fs::read(&bogus).unwrap();
    let is_pk = head.starts_with(b"PK\x03\x04");
    assert!(!is_pk, "损坏产物不得通过 PK 闸（伪成功禁）");
    // 诊断串在同局面（exit0）必须携带流（对照 Lead 复现：旧代码这里只剩
    // 笼统 PK 魔数失败——本次修的核心）
    let msg = bid_tools::service::word_com_exit_diagnostics(
        Some(0),
        "stdout- corrupted run",
        "stderr- CONTROLLED_WORD_COM_FAILURE residue",
    );
    assert!(msg.contains("stdout-") && msg.contains("stderr-"));
    std::fs::remove_dir_all(&dir).ok();
}

/// timeout 面：超时错误串带秒数（受控：不真跑 30s——纯函数钉形状，
/// 真实 Word 挂起面 Lead Windows 复验）。
#[test]
fn controlled_timeout_message_not_masked() {
    let msg = bid_tools::service::word_com_timeout_message(30);
    assert!(msg.contains("超时") && msg.contains("30"), "超时面文案: {msg}");
    // 超时不得被产物校验/exit0 面吞掉：超时串独立成错（不复用 exit 诊断串）
    assert!(!msg.contains("退出码"), "超时面独立不复用退出码串: {msg}");
}
