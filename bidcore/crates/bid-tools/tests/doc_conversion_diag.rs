//! #166: actual generated script, COM-free shims and shared production gate.
//! No Office or soffice activation. Real .doc conversion is not proved here.
use bid_tools::service::{
    build_doc2docx_script, evaluate_word_com_result, run_doc2docx_script,
    word_com_exit_diagnostics, word_com_timeout_message,
};
use std::path::{Path, PathBuf};
use std::process::Command;
fn powershell() -> Option<PathBuf> {
    for c in ["powershell", "pwsh"] {
        if Command::new(c)
            .args(["-NoProfile", "-Command", "exit 0"])
            .output()
            .is_ok_and(|o| o.status.success())
        {
            return Some(c.into());
        }
    }
    eprintln!("SKIP: doc_conversion_diag subprocess\nreason: ENV_MISSING: PowerShell\nremedy: provide PowerShell; Office not required");
    None
}
struct Fixture(PathBuf);
impl Fixture {
    fn new(name: &str) -> Self {
        let nonce = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        let p = std::env::temp_dir().join(format!("bid166-{name}-{}-{nonce}", std::process::id()));
        std::fs::create_dir(&p).unwrap();
        Self(p)
    }
    fn valid_docx(&self) -> PathBuf {
        let p = self.0.join("fixture.docx");
        docx_rs::Docx::new()
            .add_paragraph(
                docx_rs::Paragraph::new().add_run(docx_rs::Run::new().add_text("真实 OOXML 标书")),
            )
            .build()
            .pack(std::fs::File::create(&p).unwrap())
            .unwrap();
        p
    }
}
impl Drop for Fixture {
    fn drop(&mut self) {
        let _ = std::fs::remove_dir_all(&self.0);
    }
}
fn literal(s: &str) -> String {
    format!("'{}'", s.replace('\'', "''"))
}
fn shim(mode: &str, doc: &str, out: &Path, valid: &Path, cleanup: &Path) -> String {
    format!("$script:mode={}\n$script:expectedDoc={}\n$script:expectedOut={}\n$script:valid={}\n$script:cleanup={}\n",literal(mode),literal(doc),literal(&out.display().to_string()),literal(&valid.display().to_string()),literal(&cleanup.display().to_string())) + r#"
function New-Object {
 param([string]$ComObject)
 if ($ComObject -ne 'Word.Application') { throw 'Unexpected COM request' }
 [Console]::Out.WriteLine(('前' * 900) + "`nSTDOUT 尾😀`nlast stdout")
 if ($script:mode -eq 'create_fail') { throw [System.InvalidOperationException]::new("CONTROLLED_ROOT`r`nUnicode 根因`nFINAL_REASON") }
 if ($script:mode -eq 'timeout') { Start-Sleep -Seconds 30 }
 $document=[pscustomobject]@{}
 $document | Add-Member ScriptMethod SaveAs2 {
  param($path,$format)
  if ($path -cne $script:expectedOut -or $format -ne 16) { throw 'OUTPUT_LITERAL_MISMATCH' }
  if ($script:mode -eq 'save_fail') { throw [System.InvalidOperationException]::new("SAVE_ROOT`r`n保存根因`nSAVE_FINAL") }
  if ($script:mode -eq 'missing') { [Console]::Error.WriteLine("MISSING_STDERR 尾😀`nlast stderr"); return }
  if ($script:mode -eq 'invalid') { [System.IO.File]::WriteAllText($path,'NOT_DOCX'); [Console]::Error.WriteLine('INVALID_STDERR'); return }
  if ($script:mode -eq 'pk_only') { [System.IO.File]::WriteAllBytes($path,[byte[]](80,75,3,4,0,0)); [Console]::Error.WriteLine('PK_ONLY_STDERR'); return }
  [System.IO.File]::WriteAllBytes($path,[System.IO.File]::ReadAllBytes($script:valid))
 }
 $document | Add-Member ScriptMethod Close { param($save); [System.IO.File]::AppendAllText($script:cleanup,'close;') }
 $documents=[pscustomobject]@{ Document=$document }
 $documents | Add-Member ScriptMethod Open {
  param($path,$confirm,$readOnly)
  if ($path -cne $script:expectedDoc -or $confirm -ne $false -or $readOnly -ne $true) { throw 'INPUT_LITERAL_MISMATCH' }
  if ($script:mode -eq 'open_fail') { throw [System.InvalidOperationException]::new("OPEN_ROOT`r`n打开根因`nOPEN_FINAL") }
  return $this.Document
 }
 $word=[pscustomobject]@{ Visible=$true; DisplayAlerts=1; Documents=$documents }
 $word | Add-Member ScriptMethod Quit { [System.IO.File]::AppendAllText($script:cleanup,'quit;') }
 return $word
}
"#
}
#[test]
fn red_doc2docx_script_has_stop_catch_typed_diag_and_exit() {
    let script = build_doc2docx_script("/t/it's 投's 标.doc", "/t/o'ut.docx");
    for s in [
        "$ErrorActionPreference = 'Stop'",
        "catch {",
        "BID_WORD_COM_FAIL",
        "Exception.GetType().FullName",
        "InvocationInfo.ScriptLineNumber",
        "exit 3",
        "ReleaseComObject",
        "$word.Quit()",
        "$doc.Close(0)",
    ] {
        assert!(script.contains(s), "missing {s}: {script}");
    }
    assert!(script.contains("Open('/t/it''s 投''s 标.doc'"));
    assert!(script.contains("SaveAs2('/t/o''ut.docx', 16)"));
}
#[test]
fn red_diag_nonzero_exit_keeps_code_and_stderr() {
    let msg = word_com_exit_diagnostics(
        Some(3),
        "stdout-tail",
        "BID_WORD_COM_FAIL type=System.Runtime.InteropServices.COMException line=9 msg=Open 失败",
    );
    assert!(msg.contains("Some(3)") && msg.contains("COMException") && msg.contains("Open 失败"));
}
#[test]
fn red_diag_exit0_invalid_artifact_carries_stdout_stderr_and_code() {
    let f = Fixture::new("exit0");
    let msg = evaluate_word_com_result(
        Some(0),
        "stdout-tail",
        "stderr-tail",
        &f.0.join("missing.docx"),
    )
    .unwrap_err();
    assert!(msg.contains("exit 0") && msg.contains("stdout-tail") && msg.contains("stderr-tail"));
}
#[test]
fn red_long_streams_keep_typed_line_and_unicode_tail() {
    let typed = "BID_WORD_COM_FAIL type=System.InvalidOperationException line=42 msg=ROOT_CAUSE";
    let stdout = format!("{}\nSTDOUT 尾😀\nlast stdout", "前".repeat(900));
    let stderr = format!(
        "{}\n{typed}\n{}\nSTDERR 尾😀\nlast stderr",
        "初".repeat(900),
        "中".repeat(900)
    );
    let msg = word_com_exit_diagnostics(Some(3), &stdout, &stderr);
    assert!(
        msg.contains(typed),
        "typed root must survive long streams: {msg}"
    );
    assert!(
        msg.contains("STDOUT 尾😀\nlast stdout"),
        "stdout tail lost: {msg}"
    );
    assert!(
        msg.contains("STDERR 尾😀\nlast stderr"),
        "stderr tail lost: {msg}"
    );
    assert!(msg.chars().count() <= 1400, "diagnostics must be bounded");
}
#[test]
fn red_timeout_does_not_claim_unverified_word_cleanup() {
    let msg = word_com_timeout_message(30);
    assert!(msg.contains("超时") && msg.contains("30"));
    assert!(!msg.contains("已清理残留"));
}
#[test]
fn controlled_fixed_script_exits_nonzero_with_typed_diag() {
    let Some(ps) = powershell() else {
        return;
    };
    let f = Fixture::new("typed");
    let out = f.0.join("out.docx");
    let script = shim(
        "create_fail",
        "input.doc",
        &out,
        &f.valid_docx(),
        &f.0.join("cleanup"),
    ) + &build_doc2docx_script("input.doc", &out.display().to_string());
    let ps1 = f.0.join("generated.ps1");
    let mut bytes = vec![0xef, 0xbb, 0xbf];
    bytes.extend_from_slice(script.as_bytes());
    std::fs::write(&ps1, bytes).unwrap();
    let o = Command::new(&ps)
        .args(["-NoProfile", "-NonInteractive", "-File"])
        .arg(&ps1)
        .output()
        .unwrap();
    let stderr = String::from_utf8_lossy(&o.stderr);
    assert_eq!(o.status.code(), Some(3));
    assert_eq!(
        stderr.lines().count(),
        1,
        "typed diagnosis must be one physical line: {stderr}"
    );
    assert!(
        stderr.contains("type=System.InvalidOperationException")
            && stderr.contains("line=")
            && stderr.contains("msg=")
    );
    assert!(
        stderr.contains("CONTROLLED_ROOT\\r\\nUnicode 根因\\nFINAL_REASON"),
        "{stderr}"
    );
    let msg = evaluate_word_com_result(
        o.status.code(),
        &String::from_utf8_lossy(&o.stdout),
        &stderr,
        &out,
    )
    .unwrap_err();
    assert!(
        msg.contains("CONTROLLED_ROOT")
            && msg.contains("FINAL_REASON")
            && msg.contains("STDOUT 尾😀\nlast stdout")
    );
}
#[test]
fn controlled_generated_script_and_production_runner_cover_result_matrix() {
    let Some(ps) = powershell() else {
        return;
    };
    for mode in [
        "create_fail",
        "open_fail",
        "save_fail",
        "missing",
        "invalid",
        "pk_only",
        "valid",
    ] {
        let f = Fixture::new(mode);
        let out = f.0.join("o'ut;$` 标😀.docx");
        let input = "C:/it's 投's;$`\n标.doc";
        let cleanup = f.0.join("cleanup");
        let script = shim(mode, input, &out, &f.valid_docx(), &cleanup)
            + &build_doc2docx_script(input, &out.display().to_string());
        let result = run_doc2docx_script(&ps, &script, &out, 10);
        if mode == "valid" {
            result.unwrap();
        } else {
            let msg = result.unwrap_err();
            assert!(msg.contains("STDOUT 尾😀\nlast stdout"), "{mode}: {msg}");
            if mode.ends_with("fail") {
                assert!(
                    msg.contains("Some(3)")
                        && msg.contains("BID_WORD_COM_FAIL")
                        && msg.contains("ROOT")
                        && msg.contains("FINAL"),
                    "{mode}: {msg}"
                );
            } else {
                assert!(
                    msg.contains("exit 0") && msg.contains("STDERR"),
                    "{mode}: {msg}"
                );
            }
        }
        if mode == "open_fail" {
            assert_eq!(std::fs::read_to_string(&cleanup).unwrap(), "quit;");
        }
        if ["save_fail", "missing", "invalid", "pk_only", "valid"].contains(&mode) {
            assert_eq!(
                std::fs::read_to_string(&cleanup).unwrap(),
                "close;quit;",
                "finally cleans invocation references"
            );
        }
    }
}
#[test]
fn shared_evaluator_rejects_invalid_ooxml_and_nonzero_even_with_valid_artifact() {
    let f = Fixture::new("gate");
    let valid = f.valid_docx();
    assert!(evaluate_word_com_result(Some(0), "", "", &valid).is_ok());
    let root = "BID_WORD_COM_FAIL type=System.Exception line=9 msg=ROOT_FAILURE";
    for code in [Some(3), None] {
        assert!(evaluate_word_com_result(code, "out", root, &valid)
            .unwrap_err()
            .contains(root));
    }
    let bad = f.0.join("other.docx");
    let mut z = zip::ZipWriter::new(std::fs::File::create(&bad).unwrap());
    z.start_file("unrelated.txt", zip::write::SimpleFileOptions::default())
        .unwrap();
    std::io::Write::write_all(&mut z, b"not OOXML").unwrap();
    z.finish().unwrap();
    assert!(
        evaluate_word_com_result(Some(0), "out-root", "err-root", &bad)
            .unwrap_err()
            .contains("err-root")
    );
}
#[test]
fn controlled_timeout_is_bounded_and_does_not_kill_other_child() {
    let Some(ps) = powershell() else {
        return;
    };
    let f = Fixture::new("timeout");
    let out = f.0.join("out.docx");
    let script = shim(
        "timeout",
        "in.doc",
        &out,
        &f.valid_docx(),
        &f.0.join("cleanup"),
    ) + &build_doc2docx_script("in.doc", &out.display().to_string());
    let mut sentinel = Command::new(&ps)
        .args([
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            "Start-Sleep -Seconds 30",
        ])
        .spawn()
        .unwrap();
    let start = std::time::Instant::now();
    let result = run_doc2docx_script(&ps, &script, &out, 1);
    let elapsed = start.elapsed();
    let alive = sentinel.try_wait().unwrap().is_none();
    sentinel.kill().unwrap();
    sentinel.wait().unwrap();
    let msg = result.unwrap_err();
    assert!(
        elapsed < std::time::Duration::from_secs(5),
        "cleanup exceeded bound: {elapsed:?}"
    );
    assert!(alive, "unrelated child must stay alive");
    assert!(
        msg.contains("超时（1s）")
            && msg.contains("本次 PowerShell 子进程退出已确认")
            && msg.contains("可能残留")
    );
}
#[test]
fn controlled_verbose_logs_preserve_typed_line_and_tail_without_pipe_deadlock() {
    let Some(ps) = powershell() else {
        return;
    };
    let f = Fixture::new("verbose");
    let out = f.0.join("out.docx");
    let mut script = shim(
        "create_fail",
        "in.doc",
        &out,
        &f.valid_docx(),
        &f.0.join("cleanup"),
    );
    script += &build_doc2docx_script("in.doc", &out.display().to_string()).replace(
        "} finally {",
        r#"} finally {
 [Console]::Error.WriteLine(('中' * 90000) + "`nSTDERR 尾😀`nlast stderr")
"#,
    );
    let msg = run_doc2docx_script(&ps, &script, &out, 10).unwrap_err();
    assert!(
        msg.contains("CONTROLLED_ROOT") && msg.contains("FINAL_REASON"),
        "{msg}"
    );
    assert!(
        msg.contains("STDERR 尾😀\nlast stderr") && msg.contains("STDOUT 尾😀\nlast stdout"),
        "{msg}"
    );
    assert!(msg.chars().count() < 1400);
}

#[test]
fn controlled_no_stop_script_stderr_nonzero_silent_exit0() {
    let Some(ps) = powershell() else {
        return;
    };
    let output = Command::new(&ps).args(["-NoProfile", "-NonInteractive", "-Command", "try { Write-Error 'CONTROLLED_WORD_COM_FAILURE' -ErrorAction Continue } finally { Write-Output 'cleanup done' }"]).output().unwrap();
    assert_eq!(output.status.code(), Some(0));
    assert!(String::from_utf8_lossy(&output.stderr).contains("CONTROLLED_WORD_COM_FAILURE"));
    let fixture = Fixture::new("continue");
    let error = evaluate_word_com_result(
        output.status.code(),
        &String::from_utf8_lossy(&output.stdout),
        &String::from_utf8_lossy(&output.stderr),
        &fixture.0.join("missing.docx"),
    )
    .unwrap_err();
    assert!(error.contains("CONTROLLED_WORD_COM_FAILURE") && error.contains("cleanup done"));
}

#[test]
fn controlled_long_catch_is_single_line_bounded_and_preserves_unicode_tail() {
    let Some(ps) = powershell() else {
        return;
    };
    let f = Fixture::new("long-catch");
    let out = f.0.join("out.docx");
    let script = shim(
        "create_fail",
        "in.doc",
        &out,
        &f.valid_docx(),
        &f.0.join("cleanup"),
    );
    // Replace the shim throw only: production catch is executed unchanged.
    let script = script.replace(
        r#"throw [System.InvalidOperationException]::new("CONTROLLED_ROOT`r`nUnicode 根因`nFINAL_REASON")"#,
        r#"throw [System.InvalidOperationException]::new(('😀' * 700) + "`r`nFINAL_尾😀`nlast reason")"#,
    ) + &build_doc2docx_script("in.doc", &out.display().to_string());
    let ps1 = f.0.join("generated.ps1");
    let mut bytes = vec![0xef, 0xbb, 0xbf];
    bytes.extend_from_slice(script.as_bytes());
    std::fs::write(&ps1, bytes).unwrap();
    let output = Command::new(&ps)
        .args(["-NoProfile", "-NonInteractive", "-File"])
        .arg(&ps1)
        .output()
        .unwrap();
    let stderr = String::from_utf8_lossy(&output.stderr);
    assert_eq!(output.status.code(), Some(3));
    assert_eq!(stderr.lines().count(), 1);
    assert!(stderr.chars().count() <= 402, "{stderr}");
    assert!(
        !stderr.contains('\u{fffd}'),
        "must not split surrogate pairs: {stderr}"
    );
    assert!(
        stderr.contains("type=System.InvalidOperationException")
            && stderr.contains("FINAL_尾😀\\nlast reason"),
        "{stderr}"
    );
}
