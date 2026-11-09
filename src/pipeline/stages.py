"""管道阶段模型与阶段函数（#601 批次 D·R16）。

四个阶段（与 #601 任务书对齐）::

    collect   结构化源（JSON/JSONL）装载→规范化→去重→入库
    extract   原文源（.txt）装载→raw 暂存→抽取→入库/降级
    analyze   数据集→五维统计
    report    统计→确定性 Markdown→（可选 HTML）

每个阶段是**独立可测的函数**（入参 db + 阶段参数，出参
:class:`StageResult`）——Pipeline 编排器只做串联与计时，
不藏业务逻辑。阶段失败不中断后续阶段（analyze/report 不依赖
前面阶段的**当次**产出，只依赖库内数据——失败降级语义）。
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.collect import dedupe_records, load_records
from src.collect.dedupe import normalize_source_url
from src.collect.records import AnnouncementRecord
from src.collect.sources import SourceError
from src.extract import RuleExtractor, load_raw_texts, run_extraction
from src.extract.runner import resolve_raw_files
from src.storage.database import BidDatabase


# ----------------------------------------------------------------------
# 阶段结果模型
# ----------------------------------------------------------------------


@dataclass
class StageResult:
    """单阶段执行结果。

    Attributes:
        name: 阶段名（collect / extract / analyze / report）。
        ok: 阶段是否成功（语义见各阶段函数 docstring——
            「成功」= 阶段自身无错误；数据级失败计入 summary）。
        duration_ms: 阶段耗时（毫秒）。
        summary: 阶段统计（键随阶段而异，见各函数 docstring）。
        error: 阶段级错误（源不可读等）；``None`` 表示无阶段级错误。
    """

    name: str
    ok: bool
    duration_ms: int = 0
    summary: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """序列化形态（pipeline_runs 表留档用）。"""
        return {
            "name": self.name,
            "ok": self.ok,
            "duration_ms": self.duration_ms,
            "summary": self.summary,
            "error": self.error,
        }


def _timed_stage(name: str):
    """阶段计时装饰器（同步阶段函数用）。

    Args:
        name: 阶段名。

    Returns:
        装饰器——被包装函数返回 ``(ok, summary, error)`` 三元组，
        装饰后返回 :class:`StageResult`（含耗时）。
    """

    def decorator(func):
        def wrapper(*args, **kwargs) -> StageResult:
            start = time.monotonic()
            ok, summary, error = func(*args, **kwargs)
            return StageResult(
                name=name,
                ok=ok,
                duration_ms=int((time.monotonic() - start) * 1000),
                summary=summary,
                error=error,
            )

        return wrapper

    return decorator


# ----------------------------------------------------------------------
# 水位：collect 增量分类（只处理新增）
# ----------------------------------------------------------------------


def classify_against_db(
    records: List[AnnouncementRecord], db: BidDatabase
) -> Dict[str, List[AnnouncementRecord]]:
    """把批次记录按 DB 水位分类（增量 collect 的判定面）。

    Args:
        records: 已规范化的批次记录。
        db: 已打开的数据库（水位 = 库内全部记录的
            bid_id/归一 URL/指纹三个键集合）。

    Returns:
        ``{"new": [...], "update": [...], "skip": [...]}``——
        ``new``：三键全未命中（全新公告，入库）；
        ``update``：bid_id 命中库内记录（公告更新/重采，upsert）；
        ``skip``：URL/指纹命中且 bid_id 不同（同件多源，跳过）。
    """
    known_bid_ids = set()
    known_urls = set()
    known_fingerprints = set()
    for row in db.iter_all():
        known_bid_ids.add((row.get("bid_id") or "").strip().upper())
        url = normalize_source_url(row.get("source_url"))
        if url:
            known_urls.add(url)
        record = AnnouncementRecord.from_raw(row)
        known_fingerprints.add(record.fingerprint())

    classified: Dict[str, List[AnnouncementRecord]] = {
        "new": [],
        "update": [],
        "skip": [],
    }
    for record in records:
        if record.bid_id.strip().upper() in known_bid_ids:
            classified["update"].append(record)
            continue
        url = normalize_source_url(record.source_url)
        if url and url in known_urls:
            classified["skip"].append(record)
            continue
        if record.fingerprint() in known_fingerprints:
            classified["skip"].append(record)
            continue
        classified["new"].append(record)
        # 新记录立即计入水位——同批次内后续同件也判 skip
        known_bid_ids.add(record.bid_id.strip().upper())
        if url:
            known_urls.add(url)
        known_fingerprints.add(record.fingerprint())
    return classified


# ----------------------------------------------------------------------
# 阶段函数
# ----------------------------------------------------------------------


@_timed_stage("collect")
def run_collect_stage(
    db: BidDatabase,
    source: Any,
    *,
    incremental: bool = True,
) -> tuple:
    """collect 阶段：结构化源装载 → 去重 → 入库。

    Args:
        db: 目标数据库。
        source: 公告源路径（.json/.jsonl 文件或目录）。
        incremental: ``True``（默认）时按 DB 水位只入新增
            （new 入库 + update upsert + skip 丢弃）；
            ``False`` 时全量 upsert（批内去重后）。

    Returns:
        ``(ok, summary, error)``——ok=阶段无错误（数据级失败
        记录在 summary["load_failures"]，不视为阶段失败）。
    """
    try:
        loaded = load_records(source, skip_invalid=True)
    except (SourceError, ValueError) as exc:
        return False, {"files_read": 0}, f"源不可读: {exc}"

    if incremental:
        classified = classify_against_db(loaded.records, db)
        saved = db.import_bids(
            [r.to_bid_row() for r in classified["new"] + classified["update"]]
        )
        summary = {
            "files_read": loaded.files_read,
            "loaded": len(loaded.records),
            "load_failures": len(loaded.failures),
            "new": len(classified["new"]),
            "update": len(classified["update"]),
            "skip_duplicate": len(classified["skip"]),
            "saved": saved,
        }
        return True, summary, None

    deduped = dedupe_records(loaded.records)
    saved = db.import_bids([r.to_bid_row() for r in deduped.unique])
    summary = {
        "files_read": loaded.files_read,
        "loaded": len(loaded.records),
        "load_failures": len(loaded.failures),
        "new": saved,
        "update": 0,
        "skip_duplicate": deduped.removed,
        "saved": saved,
    }
    return True, summary, None


@_timed_stage("extract")
def run_extract_stage(
    db: BidDatabase,
    source: Optional[Any],
    extractor: Any = None,
    *,
    limit: Optional[int] = None,
) -> tuple:
    """extract 阶段：原文装载 → pending 抽取 → 入库/降级。

    Args:
        db: 目标数据库。
        source: 原文源（.txt 文件或目录）；``None`` 时只重试库内 pending。
        extractor: 抽取引擎；缺省 :class:`RuleExtractor`。
        limit: 最多处理 pending 条数。

    Returns:
        ``(ok, summary, error)``——ok=阶段无错误（单条抽取失败
        保持 pending 可重试，计入 summary["failed"]，不是阶段失败）。
    """
    import asyncio

    load_summary = {"files_read": 0, "saved": 0, "duplicates": 0}
    if source is not None:
        try:
            resolve_raw_files(source)
        except SourceError as exc:
            return False, load_summary, f"原文源不可读: {exc}"
        load_stats = load_raw_texts(source, db)
        load_summary = {
            "files_read": load_stats.files_read,
            "saved": load_stats.saved,
            "duplicates": load_stats.duplicates,
            "load_failures": len(load_stats.failures),
        }

    engine = extractor or RuleExtractor()
    run_stats = asyncio.run(run_extraction(db, engine, limit=limit))
    summary = {
        **load_summary,
        "processed": run_stats.processed,
        "extracted": run_stats.extracted,
        "failed": run_stats.failed,
    }
    return True, summary, None
