//! engines/poppler.rs —— poppler pdftotext 文本层引擎（#200 R2 自 pdf.rs 迁入）。
//!
//! 行为口径与迁移前逐字段一致（零回归）：`pdftotext -layout` 受治执行、
//! `\f` 分页、行块 `PdfLine` + 定位器「第X页 行Y」、summary
//! 「pdf 文本层: N 页 M 行块」。文本层/扫描层的路由裁决（非空白字符
//! ≥16 判有文本层）归 [`super::parse_pdf`] 仲裁器，不在本引擎内。

use crate::engine::{EngineError, EngineStatus, PageText, PdfExtractor};
use crate::guard::{self, RunOutcome, LIMIT_PDFTOTEXT_STDOUT, TIMEOUT_PDFTOTEXT};
use crate::pdf_text::sanitize_line;
use crate::{Block, BlockKind, ParsedFile};
use std::path::Path;

use super::tool_abs_path;

/// poppler pdftotext 文本层引擎。
pub struct PopplerText;

impl PdfExtractor for PopplerText {
    fn name(&self) -> &'static str {
        "poppler"
    }

    fn probe(&self) -> EngineStatus {
        // pdftotext -v 退出码非 0 但能打印版本即视为在位（poppler 惯例）；
        // 「无法启动」与「探测期超时」都算缺件（分类单一真源见 probe_status）。
        let mut c = std::process::Command::new("pdftotext");
        c.arg("-v");
        probe_status(guard::run_limited(c, TIMEOUT_PDFTOTEXT, 64 * 1024))
    }

    fn extract(&self, path: &Path) -> Result<Vec<PageText>, EngineError> {
        let mut text_cmd = std::process::Command::new("pdftotext");
        // B-25：路径经 tool_abs_path 绝对化（纵深防御——见 engines/mod.rs）
        text_cmd.arg("-layout").arg(tool_abs_path(path)).arg("-");
        let text = match guard::run_limited(text_cmd, TIMEOUT_PDFTOTEXT, LIMIT_PDFTOTEXT_STDOUT) {
            RunOutcome::Success { stdout } => stdout,
            // #536/B-24：变体直判（单一真源 run_outcome_to_engine_error）——
            // 消息文本与旧 into_result+map_run_err 链逐字一致，零回归
            other => return Err(run_outcome_to_engine_error(other)),
        };
        // \f 分页保持分段序（含空段——块定位器的页号口径依赖它）
        Ok(text
            .split('\u{c}')
            .enumerate()
            .map(|(pi, seg)| PageText {
                page: pi + 1,
                text: seg.to_string(),
                confidence: 1.0,
                diagnostics: String::new(),
            })
            .collect())
    }
}

/// probe 结论分类（#536/B-24：纯函数化——可平台无关单测）。
///
/// 口径修正：**探测期 Timeout 也判缺件**——旧口径非 Spawn 一律 Ready，
/// 挂起的 pdftotext（杀软钩子/坏安装/资源饥饿）被判在位，主链才撞 60s
/// 超时；探测的意义就是在主链前发现这种坏环境。
/// NonZeroExit/OutputOverflow/Busy 仍判 Ready（poppler -v 惯例退出码非 0
/// 但打印版本；溢出/满载非缺件）。
fn probe_status(out: RunOutcome) -> EngineStatus {
    match out {
        RunOutcome::Spawn { why, .. } => EngineStatus::Missing {
            what: format!("pdftotext 无法启动: {why}"),
            hint: "安装 poppler-utils（Debian/Ubuntu: apt install poppler-utils）".to_string(),
        },
        RunOutcome::Timeout { secs, .. } => EngineStatus::Missing {
            what: format!("pdftotext -v 超时（{secs}s）——工具在 PATH 但响应挂起"),
            hint: "探测期即可复现的坏环境：检查 pdftotext 安装完整性/杀软钩子/系统资源".to_string(),
        },
        _ => EngineStatus::Ready,
    }
}

/// 治理五分类 → 引擎错误三分类（#536/B-24：变体直判取代旧 map_run_err 的
/// contains 字符串分类——guard.rs 消息措辞演进不再静默改变错误类别；
/// 消息文本与旧链**逐字一致**，零回归）。
fn run_outcome_to_engine_error(out: RunOutcome) -> EngineError {
    match out {
        // 「无法启动」= 环境缺件
        RunOutcome::Spawn { program, why } => EngineError::EnvMissing {
            engine: "poppler",
            detail: format!("{program} 无法启动: {why}"),
            hint: "安装 poppler-utils".to_string(),
        },
        // 非零退出 = 文件面
        RunOutcome::NonZeroExit { program, code, stderr_head } => EngineError::FileBroken {
            engine: "poppler",
            detail: format!("{program} 退出码 {code:?}: {stderr_head}"),
        },
        // 超时/溢出/满载 = 治理拒绝（消息复用 into_result 的治理文案——单一真源）
        other => EngineError::Governed {
            engine: "poppler",
            detail: other
                .into_result()
                .expect_err("非 Success 变体必为 Err（guard.rs 契约）"),
        },
    }
}

/// 文本层行块装配（自旧 pdf::parse 文本层分支逐字段迁入——零回归）。
pub(super) fn text_layer_parsed(pages: &[PageText]) -> ParsedFile {
    let mut blocks: Vec<Block> = Vec::new();
    // #324（R-12/B-04）：表格行计数在折叠前判定——原实现先 collapse_spaces
    // 再 filter(text.contains("  "))，折叠后双空格恒假 → tables 恒 0（死指标）。
    // 判定移入行循环、折叠前（cleaned 保留了 -layout 列对齐多空格）。
    let mut tables = 0usize;
    // 页数口径：非空分段数（pdftotext 末页后常带尾随 \f）
    let page_count = pages
        .iter()
        .filter(|p| !p.text.trim().is_empty())
        .count()
        .max(1);
    for pt in pages {
        let mut line_no = 0usize;
        for line in pt.text.lines() {
            let l = line.trim();
            let cleaned = sanitize_line(l);
            if cleaned.is_empty() {
                continue;
            }
            line_no += 1;
            // 折叠前判定（本函数内块全为 PdfLine，kind 过滤等价省略）
            if cleaned.contains("  ") {
                tables += 1;
            }
            blocks.push(Block {
                idx: blocks.len(),
                kind: BlockKind::PdfLine,
                locator: format!("第{}页 行{}", pt.page, line_no),
                text: collapse_spaces(&cleaned),
                cells: vec![],
            });
        }
    }
    let n_blocks = blocks.len();
    ParsedFile {
        name: String::new(),
        sha256: String::new(),
        pages: page_count,
        tables,
        has_text_layer: true,
        ocr_blocks: 0,
        blocks,
        parse_summary: format!("pdf 文本层: {page_count} 页 {n_blocks} 行块"),
        components: vec![],
    }
}

/// 空白折叠（自 pdf.rs 迁入，未改动）。
pub(super) fn collapse_spaces(s: &str) -> String {
    let mut out = String::new();
    let mut prev_space = false;
    for c in s.chars() {
        if c.is_whitespace() {
            if !prev_space && !out.is_empty() {
                out.push(' ');
                prev_space = true;
            }
        } else {
            out.push(c);
            prev_space = false;
        }
    }
    out.trim_end().to_string()
}

/// 真实页数探测（pdfinfo——poppler 家族工具，自 tesseract.rs 收编为单一真源，
/// #424 混合路由的尾随空段判伪也消费）。
///
/// 探测失败返回 None（调用方各自决策：整档 OCR 路径走门值回退，
/// 混合路由保守不剔除尾随空段）。
pub(super) fn probe_pdf_pages(path: &Path) -> Option<usize> {
    let mut c = std::process::Command::new("pdfinfo");
    // B-25：路径经 tool_abs_path 绝对化（纵深防御——见 engines/mod.rs）；
    // #424 自 tesseract.rs 收编为单一真源时保留该加固
    c.arg(tool_abs_path(path));
    let out = guard::run_limited(c, TIMEOUT_PDFTOTEXT, 64 * 1024);
    if !out.is_success() {
        return None;
    }
    if let RunOutcome::Success { stdout } = out {
        for line in stdout.lines() {
            if let Some(rest) = line.strip_prefix("Pages:") {
                if let Ok(n) = rest.trim().parse::<usize>() {
                    return Some(n);
                }
            }
        }
    }
    None
}

// ---------------------------------------------------------------- #536（B-24）分类单测
#[cfg(test)]
mod classify_tests {
    use super::*;

    fn spawn() -> RunOutcome {
        RunOutcome::Spawn { program: "pdftotext".into(), why: "No such file".into() }
    }
    fn timeout() -> RunOutcome {
        RunOutcome::Timeout { program: "pdftotext".into(), secs: 60 }
    }
    fn overflow() -> RunOutcome {
        RunOutcome::OutputOverflow { program: "pdftotext".into(), limit: 65_536 }
    }
    fn nonzero() -> RunOutcome {
        RunOutcome::NonZeroExit { program: "pdftotext".into(), code: Some(99), stderr_head: "Syntax Error".into() }
    }
    fn busy() -> RunOutcome {
        RunOutcome::Busy { program: "pdftotext".into() }
    }

    // ---- probe_status：B-24 核心——Timeout 判缺件（旧口径误判 Ready）
    #[test]
    fn probe_spawn_missing_with_original_text() {
        match probe_status(spawn()) {
            EngineStatus::Missing { what, hint } => {
                assert!(what.starts_with("pdftotext 无法启动: "), "文案零变化: {what}");
                assert!(hint.contains("poppler-utils"), "{hint}");
            }
            other => panic!("Spawn 应判 Missing: {other:?}"),
        }
    }

    #[test]
    fn probe_timeout_missing_not_ready() {
        match probe_status(timeout()) {
            EngineStatus::Missing { what, hint } => {
                assert!(what.contains("超时"), "{what}");
                assert!(what.contains("挂起"), "要能读懂是环境问题: {what}");
                assert!(!hint.is_empty());
            }
            other => panic!("探测期 Timeout 应判 Missing（B-24：挂起的工具不是在位）: {other:?}"),
        }
    }

    #[test]
    fn probe_nonzero_overflow_busy_stay_ready() {
        // poppler -v 惯例退出码非 0 但打印版本；溢出/满载非缺件
        assert_eq!(probe_status(nonzero()), EngineStatus::Ready);
        assert_eq!(probe_status(overflow()), EngineStatus::Ready);
        assert_eq!(probe_status(busy()), EngineStatus::Ready);
    }

    // ---- run_outcome_to_engine_error：三档分类与消息文本逐字对齐旧链
    #[test]
    fn extract_spawn_env_missing_text_unchanged() {
        match run_outcome_to_engine_error(spawn()) {
            EngineError::EnvMissing { engine, detail, hint } => {
                assert_eq!(engine, "poppler");
                assert_eq!(detail, "pdftotext 无法启动: No such file");
                assert_eq!(hint, "安装 poppler-utils");
            }
            other => panic!("{other:?}"),
        }
    }

    #[test]
    fn extract_nonzero_file_broken_text_unchanged() {
        match run_outcome_to_engine_error(nonzero()) {
            EngineError::FileBroken { engine, detail } => {
                assert_eq!(engine, "poppler");
                // 旧链：into_result 的 "{program} 退出码 {code:?}: {stderr_head}"
                assert_eq!(detail, "pdftotext 退出码 Some(99): Syntax Error");
            }
            other => panic!("{other:?}"),
        }
    }

    #[test]
    fn extract_governed_family_text_unchanged() {
        // 超时/溢出/满载 → Governed，detail 复用 into_result 治理文案（单一真源）
        match run_outcome_to_engine_error(timeout()) {
            EngineError::Governed { engine, detail } => {
                assert_eq!(engine, "poppler");
                assert_eq!(detail, "子进程超时被杀（pdftotext 60s）");
            }
            other => panic!("{other:?}"),
        }
        match run_outcome_to_engine_error(overflow()) {
            EngineError::Governed { detail, .. } => {
                assert_eq!(detail, "子进程输出超限（pdftotext > 65536 字节）");
            }
            other => panic!("{other:?}"),
        }
        match run_outcome_to_engine_error(busy()) {
            EngineError::Governed { detail, .. } => {
                assert_eq!(detail, "解析子进程并发满载（pdftotext），请重试");
            }
            other => panic!("{other:?}"),
        }
    }
}
