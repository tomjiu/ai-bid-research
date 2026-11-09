"""公告抽取面（非生产链路——仅供研究，见 docs/PYTHON-BOUNDARY.md）。

把公告原文（或稀疏结构化记录）经 LLM 抽取为结构化字段；
离线直通与真实 LLM 双模式，失败降级不阻塞管道。
"""

from src.extract.extractor import (
    AnnouncementExtractor,
    BatchExtractionResult,
    ExtractionError,
    ExtractionOutcome,
    merge_fields,
    resolve_raw_text,
)

__all__ = [
    "AnnouncementExtractor",
    "BatchExtractionResult",
    "ExtractionError",
    "ExtractionOutcome",
    "merge_fields",
    "resolve_raw_text",
]
