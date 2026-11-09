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
from src.extract.pending import (
    REASON_LLM_ERROR,
    REASON_REJECTED,
    STATUS_PENDING,
    STATUS_RESOLVED,
    STATUS_SKIPPED,
    RetryReport,
    build_replay_payload,
    park_raw_failure,
    park_record_failure,
    raw_text_fingerprint,
    retry_pending,
)
from src.extract.store import (
    STATUS_REJECTED,
    STATUS_STORED,
    BatchStoreResult,
    StoreOutcome,
    apply_extraction,
    apply_extraction_batch,
    apply_extraction_from_raw,
)
from src.extract.validator import (
    REQUIRED_FIELDS,
    RECOMMENDED_FIELDS,
    ValidationResult,
    validate_fields,
)

__all__ = [
    "AnnouncementExtractor",
    "BatchExtractionResult",
    "ExtractionError",
    "ExtractionOutcome",
    "merge_fields",
    "resolve_raw_text",
    "REQUIRED_FIELDS",
    "RECOMMENDED_FIELDS",
    "ValidationResult",
    "validate_fields",
    "BatchStoreResult",
    "StoreOutcome",
    "STATUS_REJECTED",
    "STATUS_STORED",
    "apply_extraction",
    "apply_extraction_batch",
    "apply_extraction_from_raw",
    "REASON_LLM_ERROR",
    "REASON_REJECTED",
    "STATUS_PENDING",
    "STATUS_RESOLVED",
    "STATUS_SKIPPED",
    "RetryReport",
    "build_replay_payload",
    "park_raw_failure",
    "park_record_failure",
    "raw_text_fingerprint",
    "retry_pending",
]
