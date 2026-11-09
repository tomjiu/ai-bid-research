"""装载后去重面（#601 批次 A 第 3 轮）。

设计说明
--------
同一公告会以多种形态重复出现在源里：

1. **同 bid_id**：两个源文件都收录了 ``ZJ-2026-001``（bid_id 是
   bids 表唯一键，直判最强）；
2. **同链接**：source_url 相同（同一公告页被不同批次采集）；
3. **同指纹**：bid_id 拼写不一（``A-1`` vs ``A-1-备选``）但
   标题+日期+地区一致——:meth:`AnnouncementRecord.fingerprint` 收口。

去重顺序按证据强度递减：bid_id → source_url（归一后）→ fingerprint。
**保留先到者**（keep-first）：目录源按文件名排序装载，故「先到」
确定性可复现；后到者登记进 duplicates（含原因与保留者 bid_id），
不静默丢弃——研究面可核对每次去重判定。

source_url 归一规则（比较用，不改写记录原值）：

- 去首尾空白；
- scheme/host 小写归一（``HTTPS://Example.COM/x`` ≡ ``https://example.com/x``）；
- 去尾部斜杠（``/a/`` ≡ ``/a``）；
- 去 ``utm_*`` 跟踪参数（同页不同渠道参数视为同页）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from src.collect.records import AnnouncementRecord


@dataclass
class DedupeResult:
    """一次去重的结果。

    Attributes:
        unique: 去重后待入库的记录（保持先到顺序）。
        duplicates: 被判重复的明细列表，每项含
            ``bid_id`` / ``reason``（``bid_id``|``source_url``|``fingerprint``）
            / ``duplicate_of``（保留者的 bid_id）。
        by_bid_id: 同 bid_id 判重的条数。
        by_source_url: 同链接判重的条数。
        by_fingerprint: 同指纹判重的条数。
    """

    unique: List[AnnouncementRecord] = field(default_factory=list)
    duplicates: List[Dict[str, str]] = field(default_factory=list)
    by_bid_id: int = 0
    by_source_url: int = 0
    by_fingerprint: int = 0

    @property
    def removed(self) -> int:
        """被去除的重复条数。"""
        return len(self.duplicates)


def normalize_source_url(url: Optional[str]) -> Optional[str]:
    """归一 source_url 供比较（不改写记录原值）。

    Args:
        url: 原始链接（可为 ``None``）。

    Returns:
        归一化链接；空值/无 host 的非 URL 文本返回 ``None``
        （视为「无链接证据」，不参与链接判重）。
    """
    if not url or not url.strip():
        return None
    try:
        parts = urlsplit(url.strip())
    except ValueError:
        return None
    if not parts.netloc:
        # 非绝对 URL（相对路径/纯文本）——不构成链接证据
        return None
    # 保留 utm_* 之外的业务参数（id=1 是路径语义的一部分）
    kept_params = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if not key.lower().startswith("utm_")
    ]
    path = parts.path.rstrip("/") or ""
    return urlunsplit(
        (
            parts.scheme.lower() or "http",
            parts.netloc.lower(),
            path,
            urlencode(kept_params),
            "",
        )
    )


def dedupe_records(
    records: List[AnnouncementRecord],
) -> DedupeResult:
    """对一批规范化记录去重（keep-first，顺序敏感）。

    Args:
        records: 已规范化的记录列表（建议按装载顺序——目录源
            文件名排序保证确定性）。

    Returns:
        去重结果（unique / duplicates 明细 / 分类计数）。
    """
    result = DedupeResult()
    seen_bid_ids: Dict[str, str] = {}
    seen_urls: Dict[str, str] = {}
    seen_fingerprints: Dict[str, str] = {}

    for record in records:
        # 证据强度 1：bid_id（大小写/空白不敏感）
        bid_key = record.bid_id.strip().upper()
        kept = seen_bid_ids.get(bid_key)
        if kept is not None:
            result.by_bid_id += 1
            result.duplicates.append(
                {
                    "bid_id": record.bid_id,
                    "reason": "bid_id",
                    "duplicate_of": kept,
                }
            )
            continue

        # 证据强度 2：归一化 source_url
        url_key = normalize_source_url(record.source_url)
        if url_key is not None:
            kept = seen_urls.get(url_key)
            if kept is not None:
                result.by_source_url += 1
                result.duplicates.append(
                    {
                        "bid_id": record.bid_id,
                        "reason": "source_url",
                        "duplicate_of": kept,
                    }
                )
                continue
        else:
            url_key = None

        # 证据强度 3：标题+日期+地区指纹
        fp_key = record.fingerprint()
        kept = seen_fingerprints.get(fp_key)
        if kept is not None:
            result.by_fingerprint += 1
            result.duplicates.append(
                {
                    "bid_id": record.bid_id,
                    "reason": "fingerprint",
                    "duplicate_of": kept,
                }
            )
            continue

        # 新记录——登记三类证据键后收编
        result.unique.append(record)
        seen_bid_ids[bid_key] = record.bid_id
        if url_key is not None:
            seen_urls[url_key] = record.bid_id
        seen_fingerprints[fp_key] = record.bid_id
    return result
