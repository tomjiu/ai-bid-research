//! bid-grade —— corpus-A 判分器（grade.py 的 Rust 移植 + 里程碑范围分级 + 类型化 schema 契约）。
//! 判分纪律：不调模型、不做语义判断；对齐器防伪对齐；核心断言不可跳过；未执行 ≠ 通过。

pub mod align;
pub mod fixtures;
pub mod grade;
pub mod selftest;
