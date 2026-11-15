//! Scoped Word DOC conversion diagnostics and bounded subprocess runner.
use std::path::Path;
use std::process::{Command, Stdio};
use std::time::{Duration, Instant};

const STREAM_TAIL_CHARS: usize = 400;
const TYPED_LINE_CHARS: usize = 400;
const TYPED_MARKER: &str = "BID_WORD_COM_FAIL";

fn tail(text: &str, limit: usize) -> String {
    let start = text
        .char_indices()
        .rev()
        .nth(limit.saturating_sub(1))
        .map_or(0, |(i, _)| i);
    text[start..].to_owned()
}

fn bounded_typed(line: &str) -> String {
    if line.chars().count() <= TYPED_LINE_CHARS {
        return line.to_owned();
    }
    format!(
        "{}…{}",
        line.chars().take(200).collect::<String>(),
        tail(line, 199)
    )
}

fn stream_diagnostics(text: &str) -> String {
    let end = tail(text, STREAM_TAIL_CHARS);
    let typed = text
        .lines()
        .rev()
        .find_map(|line| line.find(TYPED_MARKER).map(|i| bounded_typed(&line[i..])));
    match typed {
        Some(line) if !end.contains(&line) => format!("{line}\n[tail] {end}"),
        _ => end,
    }
}

/// Preserve a bounded typed root line separately from the true Unicode stream tail.
#[must_use]
pub fn word_com_exit_diagnostics(exit_code: Option<i32>, stdout: &str, stderr: &str) -> String {
    format!(
        "Word COM 退出码 {exit_code:?}: stdout: {}；stderr: {}",
        stream_diagnostics(stdout),
        stream_diagnostics(stderr)
    )
}

/// No claim that unrelated or unidentifiable Word processes were cleaned up.
#[must_use]
pub fn word_com_timeout_message(timeout_secs: u64) -> String {
    format!("Word COM 超时（{timeout_secs}s）——仅尝试终止本次 PowerShell 子进程；Word 归属无法确认时不强杀，可能残留")
}

/// The production result gate, shared verbatim with controlled subprocess tests.
/// Exit failure takes precedence even if a valid (possibly stale) artifact exists.
pub fn evaluate_word_com_result(
    exit_code: Option<i32>,
    stdout: &str,
    stderr: &str,
    out_docx: &Path,
) -> Result<(), String> {
    if exit_code != Some(0) {
        return Err(word_com_exit_diagnostics(exit_code, stdout, stderr));
    }
    bid_engine::parse_docx_via_engine(out_docx)
        .map(|_| ())
        .map_err(|error| {
            let error = bounded_typed(&error.to_string());
            format!(
                "Word COM 声称成功（exit 0）但产物缺失或非有效 docx：{error}——{}",
                word_com_exit_diagnostics(exit_code, stdout, stderr)
            )
        })
}

// Regular-file streams avoid pipe deadlocks. Read a fixed snapshot tail, never
// scan to a moving EOF. Generated catch also publishes its bounded typed line.
fn read_diagnostics(path: &Path) -> std::io::Result<String> {
    use std::io::{Read, Seek, SeekFrom};
    let mut file = std::fs::File::open(path)?;
    let size = file.metadata()?.len();
    let start = size.saturating_sub(1600);
    file.seek(SeekFrom::Start(start))?;
    let mut bytes = Vec::with_capacity(1600);
    file.take(size - start).read_to_end(&mut bytes)?;
    Ok(tail(&String::from_utf8_lossy(&bytes), STREAM_TAIL_CHARS))
}

fn read_stderr_diagnostics(path: &Path, typed_path: &Path) -> std::io::Result<String> {
    use std::io::Read;
    let end = read_diagnostics(path)?;
    let mut bytes = Vec::new();
    if let Ok(file) = std::fs::File::open(typed_path) {
        file.take(1600).read_to_end(&mut bytes)?;
    }
    let text = String::from_utf8_lossy(&bytes);
    match text.lines().find(|line| line.starts_with(TYPED_MARKER)) {
        Some(line) if !end.contains(line) => Ok(format!("{}\n[tail] {end}", bounded_typed(line))),
        _ => Ok(end),
    }
}

fn stop_owned_child(child: &mut std::process::Child) -> String {
    let kill = child.kill();
    let deadline = Instant::now() + Duration::from_secs(2);
    loop {
        match child.try_wait() {
            Ok(Some(_)) => return "本次 PowerShell 子进程退出已确认".into(),
            Ok(None) if Instant::now() < deadline => std::thread::sleep(Duration::from_millis(20)),
            _ => return format!("本次 PowerShell 子进程退出未确认（kill={kill:?}）"),
        }
    }
}

struct InvocationFiles(std::path::PathBuf);
impl Drop for InvocationFiles {
    fn drop(&mut self) {
        let _ = std::fs::remove_dir_all(&self.0);
    }
}

/// Execute a generated script with bounded owned-child cleanup. Tests prepend
/// a COM-free shim to this same script; production supplies no shim.
#[doc(hidden)]
pub fn run_doc2docx_script(
    powershell: &Path,
    script: &str,
    out_docx: &Path,
    timeout_secs: u64,
) -> Result<(), String> {
    let nonce = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map_err(|e| e.to_string())?
        .as_nanos();
    let dir = std::env::temp_dir().join(format!("bid-doc2docx-{}-{nonce}", std::process::id()));
    std::fs::create_dir(&dir).map_err(|e| format!("临时目录创建失败: {e}"))?;
    let files = InvocationFiles(dir);
    let script_path = files.0.join("convert.ps1");
    let stdout_path = files.0.join("stdout.log");
    let stderr_path = files.0.join("stderr.log");
    let typed_path = files.0.join("typed.log");
    let mut bytes = vec![0xef, 0xbb, 0xbf];
    bytes.extend_from_slice(script.as_bytes());
    std::fs::write(&script_path, bytes).map_err(|e| format!("脚本写入失败: {e}"))?;
    let stdout = std::fs::File::create(&stdout_path).map_err(|e| e.to_string())?;
    let stderr = std::fs::File::create(&stderr_path).map_err(|e| e.to_string())?;
    let mut child = Command::new(powershell)
        .env("BID_DOC2DOCX_TYPED_DIAG", &typed_path)
        .args([
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
        ])
        .arg(&script_path)
        .stdout(Stdio::from(stdout))
        .stderr(Stdio::from(stderr))
        .spawn()
        .map_err(|e| format!("powershell 启动失败: {e}"))?;
    let deadline = Instant::now() + Duration::from_secs(timeout_secs);
    let status = loop {
        match child.try_wait() {
            Ok(Some(status)) => break status,
            Ok(None) if Instant::now() < deadline => std::thread::sleep(Duration::from_millis(20)),
            poll => {
                let cleanup = stop_owned_child(&mut child);
                let stdout =
                    read_diagnostics(&stdout_path).unwrap_or_else(|e| format!("输出读取失败: {e}"));
                let stderr = read_stderr_diagnostics(&stderr_path, &typed_path)
                    .unwrap_or_else(|e| format!("输出读取失败: {e}"));
                let reason = match poll {
                    Err(error) => format!("轮询 powershell 失败: {error}"),
                    _ => word_com_timeout_message(timeout_secs),
                };
                return Err(format!(
                    "{reason}；{cleanup}；{}",
                    word_com_exit_diagnostics(None, &stdout, &stderr)
                ));
            }
        }
    };
    let stdout =
        read_diagnostics(&stdout_path).map_err(|e| format!("收集 powershell stdout 失败: {e}"))?;
    let stderr = read_stderr_diagnostics(&stderr_path, &typed_path)
        .map_err(|e| format!("收集 powershell stderr 失败: {e}"))?;
    evaluate_word_com_result(status.code(), &stdout, &stderr, out_docx)
}
