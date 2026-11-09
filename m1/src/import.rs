//! import.rs — 按扩展名分派的导入层 + PDF 文本层/扫描件（OCR）通道
//!
//! 外部引擎依赖（版本钉死，m1/README 记录）：
//!   - poppler-utils：pdftotext -layout（文本层）、pdfimages -png（扫描件原图抽取）
//!   - tesseract 5.5.0 + chi_sim（tessdata_fast，m1/tessdata 内容寻址提交）
//! OCR 确定性：OMP_THREAD_LIMIT=1 + LC_ALL=C.UTF-8 + 固定 tessdata。

use crate::canon::canon_ocr_line;
use crate::contract::{Block, ParseReport};
use std::io::Read;
use std::path::{Path, PathBuf};
use std::process::Command;

pub struct ImportOutcome {
    pub blocks: Vec<Block>,
    pub report: ParseReport,
    pub sha256: String,
}

pub fn sha256_file(p: &Path) -> String {
    let mut f = std::fs::File::open(p).expect("open file");
    let mut buf = Vec::new();
    f.read_to_end(&mut buf).expect("read file");
    crate::contract::content_hash(&[&String::from_utf8_lossy(&buf)])
        .chars().take(64).collect::<String>()
}

/// 不可信文件内容不得直接进错误信息（截断 + 转义）
fn safe_name(s: &str) -> String {
    s.chars().take(40).collect()
}

pub fn import_file(path: &Path, file_name: &str, order_start: u32) -> ImportOutcome {
    let ext = path.extension().and_then(|e| e.to_str()).unwrap_or("").to_ascii_lowercase();
    let sha = sha256_file(path);
    let mut blocks = Vec::new();
    let mut kind = "unknown".to_string();
    let mut failures: Vec<String> = Vec::new();

    match ext.as_str() {
        "docx" => {
            match crate::docx::parse(path, file_name, order_start) {
                Ok(b) => { kind = "docx".into(); blocks = b; }
                Err(e) => failures.push(format!("docx parse: {}", safe_name(&e))),
            }
        }
        "xlsx" => {
            match crate::xlsx::parse(path, file_name, order_start) {
                Ok(b) => { kind = "xlsx".into(); blocks = b; }
                Err(e) => failures.push(format!("xlsx parse: {}", safe_name(&e))),
            }
        }
        "pdf" => {
            match parse_pdf(path, file_name, order_start) {
                (b, k, f) => { blocks = b; kind = k; failures = f; }
            }
        }
        other => failures.push(format!("unsupported extension: {}", other)),
    }

    let paras = blocks.iter().filter(|b| b.kind == "Para" || b.kind == "Heading").count();
    let rows = blocks.iter().filter(|b| b.kind.ends_with("Row")).count();
    let chars: usize = blocks.iter().map(|b| b.text.chars().count()).sum();
    let pages = blocks.iter().map(|b| b.page).max().unwrap_or(1);
    let ocr_blocks = if kind == "pdf-scan(ocr)" {
        Some(blocks.iter().filter(|b| b.kind == "OcrLine").count() as u32)
    } else { None };
    let report = ParseReport {
        file: file_name.to_string(),
        kind,
        blocks: blocks.len(),
        paras,
        tables: 0,
        rows,
        chars,
        pages,
        ocr_blocks,
        failures,
    };
    ImportOutcome { blocks, report, sha256: sha }
}

// ---------------------------------------------------------------- PDF 通道
fn parse_pdf(path: &Path, file_name: &str, order_start: u32)
    -> (Vec<Block>, String, Vec<String>) {
    let mut failures = Vec::new();
    // 通道 1：文本层（poppler pdftotext）——三通道梯（#562 CI 实证收口）：
    //   a) stdout + LC_ALL=C.UTF-8 + -layout（原主通道，确定性优先）
    //   b) 临时文件出文 + 继承环境 + -layout（躲「管道/locale-stdout」面：
    //      ubuntu-26.04 runner 实测 B1-设备清单.pdf 报 failed 而 Debian 13
    //      同件三通道全通——失败面未见退出码，先用通道分离把可自愈面自愈）
    //   c) stdout + 继承环境 + 无 -layout（原始序兜底）
    // 判定：任一通道 exit 0 且文本 ≥20 字符即采用（首中即停——同一输入
    // 选道确定）；全通道未命中 → 把全部尝试结果记入 failures 后走 OCR
    // 通道（扫描件语义不变：真无文本层的 PDF 三通道都空，OCR 照常接管；
    // 中选通道的前置失败不记——parse_status 以「最终是否拿到文本」为准，
    // 回退中选不算失败）。
    let mut text: Option<String> = None;
    let mut attempt_errors: Vec<String> = Vec::new();
    for (mode, use_layout, to_file, pin_locale) in [
        ("stdout+lc_all+layout", true, false, true),
        ("file+env+layout", true, true, false),
        ("stdout+env+raw", false, false, false),
    ] {
        let mut cmd = Command::new("pdftotext");
        if use_layout {
            cmd.arg("-layout");
        }
        cmd.arg("-enc").arg("UTF-8").arg(path);
        let tmp_out = if to_file {
            let t = std::env::temp_dir().join(format!(
                "m1-pdftotext-{}-{}.txt", std::process::id(), order_start));
            cmd.arg(&t);
            Some(t)
        } else {
            cmd.arg("-");
            None
        };
        if pin_locale {
            cmd.env("LC_ALL", "C.UTF-8");
        }
        let out = cmd.output();
        let got: Result<String, String> = match out {
            Ok(o) if o.status.success() => Ok(match &tmp_out {
                Some(t) => std::fs::read_to_string(t).unwrap_or_default(),
                None => String::from_utf8_lossy(&o.stdout).to_string(),
            }),
            Ok(o) => Err(format!("pdftotext({mode}) exit {}", o.status)),
            Err(e) => Err(format!("pdftotext({mode}) spawn: {}", e)),
        };
        if let Some(t) = &tmp_out {
            let _ = std::fs::remove_file(t); // 临时出文清理（best-effort）
        }
        match got {
            Ok(g) if g.trim().chars().count() >= 20 => {
                text = Some(g);
                attempt_errors.clear(); // 回退中选：前置失败不记（见上方判定注释）
                break;
            }
            Ok(_) => {} // exit 0 但空文本（扫描件常态）——不记错，续试下一通道
            Err(e) => attempt_errors.push(e),
        }
    }
    failures.extend(attempt_errors);
    let text = text.unwrap_or_default();
    let tlen = text.trim().chars().count();
    if tlen >= 20 {
        // 文本层有效 → 逐行成块（页以 \f 分界）
        let mut blocks = Vec::new();
        let mut order = order_start;
        for (pi, page) in text.split('\u{c}').enumerate() {
            for line in page.lines() {
                let t = line.trim();
                if t.is_empty() { continue; }
                blocks.push(Block {
                    file: file_name.into(),
                    kind: "PdfLine".into(),
                    locator: format!("p{} line", pi + 1),
                    page: (pi + 1) as u32,
                    text: t.to_string(),
                    order,
                });
                order += 1;
            }
        }
        return (blocks, "pdf-text".into(), failures);
    }

    // 通道 2：扫描件（无文本层）→ pdfimages 抽原图 → tesseract OCR → 规整
    match ocr_pdf(path, file_name, order_start) {
        Ok((blocks, _ocr_count)) => (blocks, "pdf-scan(ocr)".into(), failures),
        Err(e) => {
            failures.push(format!("ocr: {}", safe_name(&e.to_string())));
            (Vec::new(), "pdf-scan(ocr)".into(), failures)
        }
    }
}

/// tessdata 解析（确定性优先级）：仓内 m1/tessdata（内容寻址提交）→ M1_TESSDATA 环境变量 → 系统默认
pub fn resolve_tessdata() -> std::path::PathBuf {
    if let Ok(p) = std::env::var("M1_TESSDATA") {
        let pb = std::path::PathBuf::from(p);
        if pb.join("chi_sim.traineddata").exists() { return pb; }
    }
    let mut dir = std::env::current_exe().ok();
    for _ in 0..5 {
        if let Some(d) = dir.clone() {
            for cand in ["tessdata", "m1/tessdata"] {
                let p = d.join(cand);
                if p.join("chi_sim.traineddata").exists() { return p; }
            }
        }
        dir = dir.and_then(|d| d.parent().map(|x| x.to_path_buf()));
    }
    std::path::PathBuf::from("tessdata") // 兜底：交由 tesseract 自行解析（会在 CI 中显式暴露）
}

fn ocr_pdf(path: &Path, file_name: &str, order_start: u32)
    -> std::io::Result<(Vec<Block>, u32)> {
    let tmp = std::env::temp_dir().join(format!("m1-ocr-{}", std::process::id()));
    std::fs::create_dir_all(&tmp)?;
    let prefix = tmp.join("img");
    let st = Command::new("pdfimages")
        .arg("-png").arg(path).arg(&prefix)
        .env("LC_ALL", "C.UTF-8")
        .output()?; // pdfimages 输出 img-000.png ...
    if !st.status.success() {
        return Err(std::io::Error::new(std::io::ErrorKind::Other,
                                      format!("pdfimages exit {}", st.status)));
    }
    let mut imgs: Vec<PathBuf> = std::fs::read_dir(&tmp)?
        .filter_map(|e| e.ok().map(|e| e.path()))
        .filter(|p| p.extension().map(|x| x == "png").unwrap_or(false))
        .collect();
    imgs.sort(); // img-000 < img-001：页序确定性

    let mut blocks = Vec::new();
    let mut order = order_start;
    let tessdata = resolve_tessdata();
    for (pi, img) in imgs.iter().enumerate() {
        let out = Command::new("tesseract")
            .arg(img).arg("stdout")
            .arg("-l").arg("chi_sim")
            .arg("--tessdata-dir").arg(&tessdata)
            .arg("--psm").arg("6")
            .env("LC_ALL", "C.UTF-8")
            .env("OMP_THREAD_LIMIT", "1")
            .output()?;
        if !out.status.success() {
            return Err(std::io::Error::new(std::io::ErrorKind::Other,
                                          format!("tesseract exit {}", out.status)));
        }
        let raw = String::from_utf8_lossy(&out.stdout).to_string();
        for line in raw.lines() {
            let t = canon_ocr_line(line.trim());
            if t.is_empty() { continue; }
            blocks.push(Block {
                file: file_name.into(),
                kind: "OcrLine".into(),
                locator: format!("p{} ocr line", pi + 1),
                page: (pi + 1) as u32,
                text: t,
                order,
            });
            order += 1;
        }
    }
    let count = blocks.len() as u32;
    let _ = std::fs::remove_dir_all(&tmp); // 用后即清
    Ok((blocks, count))
}
