"""研究管道编排（非生产链路——仅供研究，见 docs/PYTHON-BOUNDARY.md）。

collect → extract → analyze → report 四阶段串联为一条命令可完成的
研究管道：每个阶段产出 :class:`StageResult`（状态 + 统计），
单阶段空转/失败不静默——报告与控制台都能看到每阶段发生了什么。
"""

from src.pipeline.runner import (
    STAGE_EMPTY,
    STAGE_OK,
    STAGE_SKIPPED,
    PipelineResult,
    ResearchPipeline,
    StageResult,
)

__all__ = [
    "STAGE_EMPTY",
    "STAGE_OK",
    "STAGE_SKIPPED",
    "PipelineResult",
    "ResearchPipeline",
    "StageResult",
]
