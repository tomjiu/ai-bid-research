"""src/extract 编排器测试（#601 批次 B·R8）。

口径：原文装载（目录/单文件/重复幂等/坏文件不殃及）、
run_extraction 全链（成功入库/失败降级/演练模式/limit/on_outcome）、
失败不阻塞管道、重跑幂等。
"""

from __future__ import annotations

import asyncio

import pytest

from src.collect.sources import SourceError
from src.extract.engine import RuleExtractor
from src.extract.runner import (
    load_raw_texts,
    resolve_raw_files,
    run_extraction,
)
from src.storage.database import BidDatabase

from tests.test_extract_engine import SAMPLE_ANNOUNCEMENT

#: 一条无法抽取的普通文本（规则基线抽不出必填字段）。
NON_ANNOUNCEMENT = "今天天气不错，我们去公园散步聊天。\n没有编号也没有结构。"


@pytest.fixture()
def db(tmp_path):
    database = BidDatabase(tmp_path / "t.db")
    yield database
    database.close()


@pytest.fixture()
def src_dir(tmp_path):
    """两好一坏三份原文。"""
    d = tmp_path / "announcements"
    d.mkdir()
    (d / "good1.txt").write_text(SAMPLE_ANNOUNCEMENT, encoding="utf-8")
    (d / "bad.txt").write_text(NON_ANNOUNCEMENT, encoding="utf-8")
    (d / "good2.txt").write_text(
        SAMPLE_ANNOUNCEMENT.replace("HLJ-GC-2026-001", "HLJ-GC-2026-002"),
        encoding="utf-8",
    )
    return d


# ----------------------------------------------------------------------
# 装载段
# ----------------------------------------------------------------------


class TestLoadRawTexts:
    def test_directory_load(self, db, src_dir):
        stats = load_raw_texts(src_dir, db)
        assert stats.files_read == 3
        assert stats.saved == 3
        assert stats.duplicates == 0
        assert stats.failures == []
        assert db.raw_stats() == {"total": 3, "pending": 3, "extracted": 0}

    def test_single_file_load(self, db, tmp_path):
        f = tmp_path / "one.txt"
        f.write_text(SAMPLE_ANNOUNCEMENT, encoding="utf-8")
        stats = load_raw_texts(f, db)
        assert stats.files_read == 1
        assert stats.saved == 1

    def test_reimport_idempotent(self, db, src_dir):
        first = load_raw_texts(src_dir, db)
        second = load_raw_texts(src_dir, db)
        assert first.saved == 3
        assert second.saved == 0
        assert second.duplicates == 3
        assert db.raw_stats()["total"] == 3

    def test_missing_path_raises(self, db, tmp_path):
        with pytest.raises(SourceError, match="不存在"):
            load_raw_texts(tmp_path / "nope", db)

    def test_wrong_suffix_raises(self, db, tmp_path):
        f = tmp_path / "data.json"
        f.write_text("[]", encoding="utf-8")
        with pytest.raises(SourceError, match="不支持的原文文件类型"):
            load_raw_texts(f, db)

    def test_empty_directory_raises(self, db, tmp_path):
        d = tmp_path / "empty"
        d.mkdir()
        with pytest.raises(SourceError, match="无 .txt"):
            load_raw_texts(d, db)

    def test_unreadable_file_isolated(self, db, tmp_path):
        """坏文件（非法 UTF-8）登记失败，好文件照常装载。"""
        d = tmp_path / "mixed"
        d.mkdir()
        (d / "good.txt").write_text(SAMPLE_ANNOUNCEMENT, encoding="utf-8")
        (d / "binary.txt").write_bytes(b"\xff\xfe\x00bad")
        stats = load_raw_texts(d, db)
        assert stats.saved == 1
        assert len(stats.failures) == 1
        assert stats.failures[0]["origin"] == "binary.txt"

    def test_resolve_sorted_deterministic(self, src_dir):
        files = resolve_raw_files(src_dir)
        assert [f.name for f in files] == sorted(
            f.name for f in src_dir.iterdir()
        )


# ----------------------------------------------------------------------
# 抽取运行段
# ----------------------------------------------------------------------


class TestRunExtraction:
    def test_full_flow_success_and_failure(self, db, src_dir):
        """两好一坏：好件入库、坏件保持 pending 不阻塞。"""
        load_raw_texts(src_dir, db)
        stats = asyncio.run(run_extraction(db, RuleExtractor()))
        assert stats.processed == 3
        assert stats.extracted == 2
        assert stats.failed == 1
        assert stats.ok is False
        # bids 表两条
        assert db.count_bids() == 2
        assert db.get_bid("HLJ-GC-2026-001") is not None
        assert db.get_bid("HLJ-GC-2026-002") is not None
        # raw 面：2 extracted + 1 pending（失败留档）
        raw_stats = db.raw_stats()
        assert raw_stats == {"total": 3, "pending": 1, "extracted": 2}
        pending = db.pending_raws()
        assert pending[0]["source"] == "bad.txt"

    def test_failure_error_recorded(self, db, src_dir):
        load_raw_texts(src_dir, db)
        stats = asyncio.run(run_extraction(db, RuleExtractor()))
        assert stats.failures[0]["source"] == "bad.txt"
        assert stats.failures[0]["error"]  # 非空原因

    def test_dry_run_changes_nothing(self, db, src_dir):
        load_raw_texts(src_dir, db)
        stats = asyncio.run(
            run_extraction(db, RuleExtractor(), dry_run=True)
        )
        assert stats.extracted == 2  # 统计照常
        assert db.count_bids() == 0  # 但不写库
        assert db.raw_stats() == {"total": 3, "pending": 3, "extracted": 0}

    def test_limit(self, db, src_dir):
        """limit=2：只处理 id 最小的两条（bad.txt 字母序在前）——
        bad 失败保持 pending，good1 成功，good2 未处理仍 pending。"""
        load_raw_texts(src_dir, db)
        stats = asyncio.run(run_extraction(db, RuleExtractor(), limit=2))
        assert stats.processed == 2
        assert stats.extracted == 1
        assert stats.failed == 1
        assert db.raw_stats()["pending"] == 2

    def test_rerun_idempotent(self, db, src_dir):
        """重跑：已 extracted 的不再处理，只重试 pending 失败件。"""
        load_raw_texts(src_dir, db)
        first = asyncio.run(run_extraction(db, RuleExtractor()))
        second = asyncio.run(run_extraction(db, RuleExtractor()))
        assert first.extracted == 2
        assert second.processed == 1  # 只剩坏件重试
        assert second.extracted == 0
        assert second.failed == 1
        # bids 不重复（upsert + 状态过滤双保险）
        assert db.count_bids() == 2

    def test_on_outcome_callback(self, db, src_dir):
        load_raw_texts(src_dir, db)
        seen = []
        asyncio.run(
            run_extraction(
                db,
                RuleExtractor(),
                on_outcome=lambda item, outcome: seen.append(
                    (item["source"], outcome.ok)
                ),
            )
        )
        assert len(seen) == 3
        assert sum(1 for _, ok in seen if ok) == 2

    def test_empty_pending_noop(self, db):
        stats = asyncio.run(run_extraction(db, RuleExtractor()))
        assert stats.processed == 0
        assert stats.ok is True

    def test_extracted_record_fields(self, db, src_dir):
        """入库记录的字段质量：金额归一/日期归一/要求列表。"""
        load_raw_texts(src_dir, db)
        asyncio.run(run_extraction(db, RuleExtractor()))
        bid = db.get_bid("HLJ-GC-2026-001")
        assert bid["budget"] == 1200.0
        assert bid["publish_date"] == "2026-03-01"
        assert bid["deadline"] == "2026-03-20"
        assert isinstance(bid["requirements"], list)
        assert bid["requirements"]
