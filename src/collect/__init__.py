"""公告采集面（非生产链路——仅供研究，见 docs/PYTHON-BOUNDARY.md）。

职责：把异构来源的招标公告载荷规范化为统一记录，供抽取/入库/分析消费。
本包默认离线工作（本地文件源），不内置生产级网络爬虫。
"""

from src.collect.dedupe import DedupeResult, dedupe_records, normalize_source_url
from src.collect.records import AnnouncementRecord, RecordValidationError
from src.collect.sources import LoadResult, SourceError, load_records

__all__ = [
    "AnnouncementRecord",
    "RecordValidationError",
    "LoadResult",
    "SourceError",
    "load_records",
    "DedupeResult",
    "dedupe_records",
    "normalize_source_url",
]
