"""抽取编排（#601 批次 B·R8）——原文装载 → 逐条抽取 → 入库/降级。

管道形态（与采集面 ``collect`` 同构的三段式）::

    装载段   load_raw_texts(source, db)   .txt 文件/目录 → raw 暂存面
             （内容指纹幂等——重复导入不重复占位）
    抽取段   run_extraction(db, extractor) pending → 载荷 → schema 校验
    落库段   成功 → bids 表幂等 upsert + raw 标 extracted
             失败 → raw 保持 pending + error 留档（不阻塞后续条目）

设计纪律：

* **失败不阻塞管道**——单条失败只登记，批次继续（#601 任务书）；
* **幂等可重入**——同一批原文跑两遍，第二遍零新增（内容指纹 +
  pending 状态过滤 + bids upsert 三重幂等）；
* **诚实统计**——成功/失败/跳过逐类计数，失败明细逐条可打印。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional, Union

from src.collect.sources import SourceError
from src.extract.engine import (
    AnnouncementExtractor,
    extract_record,
    extract_record_async,
)
from src.storage.database import BidDatabase

logger = logging.getLogger("ai-bid-research.extract")

#: raw 原文源支持的扩展名。
_RAW_SOURCE_SUFFIXES = frozenset({".txt"})


# ----------------------------------------------------------------------
# 装载段
# ----------------------------------------------------------------------


@dataclass
class RawLoadStats:
    """原文装载统计。

    Attributes:
        files_read: 读取的文件数。
        saved: 新入暂存面的条数（内容指纹去重后）。
        duplicates: 内容已存在被跳过的条数。
        failures: 读失败明细（文件级：不可读/编码错）。
    """

    files_read: int = 0
    saved: int = 0
    duplicates: int = 0
    failures: List[Dict[str, str]] = field(default_factory=list)


def resolve_raw_files(source: Union[str, Path]) -> List[Path]:
    """解析 raw 原文源为文件清单（目录源按文件名排序）。

    Args:
        source: ``.txt`` 文件或包含 ``.txt`` 的目录。

    Returns:
        排序后的文件路径列表。

    Raises:
        SourceError: 路径不存在 / 目录无 .txt / 扩展名不支持。
    """
    path = Path(source)
    if not path.exists():
        raise SourceError(f"原文源路径不存在: {path}")
    if path.is_dir():
        files = sorted(
            p for p in path.iterdir() if p.suffix.lower() in _RAW_SOURCE_SUFFIXES
        )
        if not files:
            raise SourceError(f"目录内无 .txt 原文文件: {path}")
        return files
    if path.suffix.lower() not in _RAW_SOURCE_SUFFIXES:
        raise SourceError(
            f"不支持的原文文件类型: {path.suffix or '(无扩展名)'}"
            f"（支持 {'/'.join(sorted(_RAW_SOURCE_SUFFIXES))}）"
        )
    return [path]


def load_raw_texts(
    source: Union[str, Path], db: BidDatabase
) -> RawLoadStats:
    """把公告原文文件装载进 raw 暂存面。

    Args:
        source: ``.txt`` 文件或目录。
        db: 目标数据库（raw_announcements 面）。

    Returns:
        装载统计（新入/重复跳过/失败明细）。
    """
    stats = RawLoadStats()
    for path in resolve_raw_files(source):
        stats.files_read += 1
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            stats.failures.append(
                {"origin": path.name, "error": f"读取失败: {exc}"}
            )
            continue
        if db.has_raw_content(content):
            stats.duplicates += 1
            continue
        db.save_raw(path.name, content)
        stats.saved += 1
    return stats


# ----------------------------------------------------------------------
# 抽取段 + 落库段
# ----------------------------------------------------------------------


@dataclass
class ExtractRunStats:
    """一次抽取运行的统计。

    Attributes:
        mode: 引擎模式（rule / api）。
        processed: 处理的 pending 条数。
        extracted: 抽取成功并入库条数。
        failed: 失败条数（原文保持 pending，error 已留档）。
        failures: 失败明细（``source`` / ``error``）。
    """

    mode: str = "rule"
    processed: int = 0
    extracted: int = 0
    failed: int = 0
    failures: List[Dict[str, str]] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """是否零失败（CLI 退出码用）。"""
        return self.failed == 0


async def run_extraction(
    db: BidDatabase,
    extractor: AnnouncementExtractor,
    *,
    limit: Optional[int] = None,
    dry_run: bool = False,
    on_outcome: Optional[Callable] = None,
) -> ExtractRunStats:
    """处理全部 pending 原文：抽取 → 校验 → 入库/降级。

    Args:
        db: 数据库（读 pending、写 bids、标记 raw 状态）。
        extractor: 抽取引擎（rule / api）。
        limit: 最多处理条数；``None`` 表示全部 pending。
        dry_run: 演练模式——只抽取与打印，不写库不改状态。
        on_outcome: 每条结果的回调 ``fn(raw_item, outcome)``
            （CLI 逐条打印用）。

    Returns:
        运行统计。
    """
    pending = db.pending_raws(limit=limit)
    stats = ExtractRunStats(mode=getattr(extractor, "mode", "unknown"))

    for item in pending:
        stats.processed += 1
        if stats.mode == "api":
            outcome = await extract_record_async(item["content"], extractor)
        else:
            outcome = extract_record(item["content"], extractor)

        if on_outcome is not None:
            on_outcome(item, outcome)

        if outcome.ok:
            if not dry_run:
                db.save_bid(outcome.record.to_bid_row())
                db.mark_raw_extracted(item["id"], outcome.record.bid_id)
            stats.extracted += 1
            logger.info(
                "抽取成功 %s → %s（%s）",
                item["source"],
                outcome.record.bid_id,
                stats.mode,
            )
        else:
            if not dry_run:
                db.mark_raw_failed(item["id"], outcome.error or "未知原因")
            stats.failed += 1
            stats.failures.append(
                {"source": item["source"], "error": outcome.error or ""}
            )
            logger.warning(
                "抽取失败 %s: %s", item["source"], outcome.error
            )
    return stats
