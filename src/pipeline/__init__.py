"""管道面（#601 批次 D）——collect→extract→analyze→report 串联编排。

非生产链路——仅供研究，与 Rust bid 链路的边界见 docs/PYTHON-BOUNDARY.md。
一条命令从公告源到研究报告：``python main.py pipeline --announcements …``
"""

from src.pipeline.stages import (
    StageResult,
    classify_against_db,
    run_collect_stage,
    run_extract_stage,
)

__all__ = [
    "StageResult",
    "classify_against_db",
    "run_collect_stage",
    "run_extract_stage",
]
