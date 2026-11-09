//! main.rs — M1 最小流水线 CLI
//!
//! 用法（工作目录 = 仓库根）：
//!   m1 run --scenario TC-01 [--corpus fixtures/corpus-A/files]
//!          [--queries fixtures/queries/exact-25.jsonl] [--out runs/TC-01]
//!   m1 test        # cargo test（状态机守卫 / 幂等 / OCR 规整 单测）

mod canon;
mod chunk;
mod contract;
mod docx;
mod extract;
mod import;
mod run;
mod search;
mod state;
mod xlsx;

use run::RunCfg;
use std::path::PathBuf;

fn main() {
    let args: Vec<String> = std::env::args().skip(1).collect();
    if args.is_empty() {
        eprintln!("用法: m1 run --scenario TC-01|TC-02|TC-07|TC-11 [--corpus DIR] [--queries FILE] [--out DIR] | m1 test");
        std::process::exit(2);
    }
    match args[0].as_str() {
        "run" => {
            let mut scenario = String::new();
            let mut corpus = PathBuf::from("fixtures/corpus-A/files");
            let mut queries = PathBuf::from("fixtures/queries/exact-25.jsonl");
            let mut out: Option<PathBuf> = None;
            let mut i = 1;
            while i < args.len() {
                match args[i].as_str() {
                    "--scenario" => { scenario = args.get(i + 1).cloned().unwrap_or_default(); i += 2; }
                    "--corpus" => { corpus = PathBuf::from(args.get(i + 1).cloned().unwrap_or_default()); i += 2; }
                    "--queries" => { queries = PathBuf::from(args.get(i + 1).cloned().unwrap_or_default()); i += 2; }
                    "--out" => { out = Some(PathBuf::from(args.get(i + 1).cloned().unwrap_or_default())); i += 2; }
                    _ => { eprintln!("未知参数: {}", args[i]); std::process::exit(2); }
                }
            }
            if scenario.is_empty() {
                eprintln!("--scenario 必填（TC-01|TC-02|TC-07|TC-11）");
                std::process::exit(2);
            }
            let out = out.unwrap_or_else(|| PathBuf::from(format!("runs/{}", scenario)));
            let cfg = RunCfg { scenario: scenario.clone(), corpus_files: corpus, queries, out };
            match run::run(&cfg) {
                Ok(code) => std::process::exit(code),
                Err(e) => { eprintln!("[m1] FATAL: {}", e); std::process::exit(1); }
            }
        }
        "test" => {
            // cargo test 不在本二进制内做——提示正确命令
            eprintln!("请在 m1/ 目录执行: cargo test");
            std::process::exit(2);
        }
        other => { eprintln!("未知子命令: {}", other); std::process::exit(2); }
    }
}
