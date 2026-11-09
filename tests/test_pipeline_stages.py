"""src/pipeline 阶段函数测试（#601 批次 D·R16）。"""

from __future__ import annotations

import json

import pytest

from src.collect.records import AnnouncementRecord
from src.pipeline.stages import (
    classify_against_db,
    run_collect_stage,
    run_extract_stage,
)
from src.storage.database import BidDatabase

from tests.test_extract_engine import SAMPLE_ANNOUNCEMENT


@pytest.fixture()
def db(tmp_path):
    database = BidDatabase(tmp_path / "t.db")
    yield database
    database.close()


@pytest.fixture()
def ann_dir(tmp_path):
    d = tmp_path / "ann"
    d.mkdir()
    (d / "a.json").write_text(
        json.dumps(
            [
                {"bid_id": "N-1", "project_name": "全新项目一", "budget": 100},
                {"bid_id": "N-2", "project_name": "全新项目二", "budget": 200},
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return d


class TestClassifyAgainstDb:
    def make_record(self, **overrides):
        data = {
            "bid_id": "X-1",
            "project_name": "某个项目",
            "publish_date": "2026-01-01",
            "region": "北京市",
        }
        data.update(overrides)
        return AnnouncementRecord.from_raw(data)

    def test_all_new_on_empty_db(self, db):
        records = [
            self.make_record(
                bid_id=f"X-{i}", project_name=f"不同的项目{i}"
            )
            for i in range(3)
        ]
        classified = classify_against_db(records, db)
        assert len(classified["new"]) == 3
        assert classified["update"] == []
        assert classified["skip"] == []

    def test_bid_id_hit_is_update(self, db):
        db.save_bid({"bid_id": "X-1", "project_name": "旧名"})
        classified = classify_against_db([self.make_record()], db)
        assert classified["update"] == [classified["update"][0]]
        assert len(classified["update"]) == 1
        assert classified["new"] == []

    def test_url_hit_different_bid_is_skip(self, db):
        db.save_bid(
            {
                "bid_id": "OLD-1",
                "project_name": "某个项目",
                "publish_date": "2026-01-01",
                "region": "北京市",
                "source_url": "https://e.com/n/1",
            }
        )
        classified = classify_against_db(
            [self.make_record(bid_id="NEW-9", source_url="https://e.com/n/1?utm=x")],
            db,
        )
        assert len(classified["skip"]) == 1
        assert classified["new"] == []

    def test_fingerprint_hit_different_bid_is_skip(self, db):
        db.save_bid(
            {
                "bid_id": "OLD-1",
                "project_name": "某个项目",
                "publish_date": "2026-01-01",
                "region": "北京市",
            }
        )
        classified = classify_against_db(
            [self.make_record(bid_id="NEW-9")], db
        )
        assert len(classified["skip"]) == 1

    def test_intra_batch_new_registered_to_watermark(self, db):
        """同批次内重复件：先 new 后 skip（水位即时更新）。"""
        classified = classify_against_db(
            [
                self.make_record(bid_id="A-1"),
                self.make_record(bid_id="A-1-dup"),  # 同指纹不同编号
            ],
            db,
        )
        assert len(classified["new"]) == 1
        assert len(classified["skip"]) == 1


class TestCollectStage:
    def test_collect_new_records(self, db, ann_dir):
        result = run_collect_stage(db, ann_dir)
        assert result.ok
        assert result.error is None
        assert result.name == "collect"
        assert result.summary["new"] == 2
        assert result.summary["saved"] == 2
        assert db.count_bids() == 2

    def test_collect_incremental_second_run_zero_new(self, db, ann_dir):
        """增量：同源跑两遍，第二遍零新增零保存。"""
        run_collect_stage(db, ann_dir)
        result = run_collect_stage(db, ann_dir)
        assert result.ok
        assert result.summary["new"] == 0
        # 注意：bid_id 命中 → update 分类（upsert 仍执行）
        assert result.summary["update"] == 2
        assert db.count_bids() == 2

    def test_collect_unreadable_source_stage_error(self, db, tmp_path):
        result = run_collect_stage(db, tmp_path / "nope")
        assert result.ok is False
        assert "源不可读" in result.error

    def test_collect_full_mode(self, db, ann_dir):
        """incremental=False：批内去重后全量 upsert。"""
        result = run_collect_stage(db, ann_dir, incremental=False)
        assert result.ok
        assert result.summary["saved"] == 2
        assert result.summary["skip_duplicate"] == 0

    def test_stage_timing_recorded(self, db, ann_dir):
        result = run_collect_stage(db, ann_dir)
        assert result.duration_ms >= 0
        assert result.to_dict()["name"] == "collect"


class TestExtractStage:
    def test_extract_stage_full(self, db, tmp_path):
        raw = tmp_path / "raw"
        raw.mkdir()
        (raw / "n1.txt").write_text(SAMPLE_ANNOUNCEMENT, encoding="utf-8")
        result = run_extract_stage(db, raw)
        assert result.ok
        assert result.summary["files_read"] == 1
        assert result.summary["saved"] == 1
        assert result.summary["extracted"] == 1
        assert db.get_bid("HLJ-GC-2026-001") is not None

    def test_extract_stage_no_source_retries_pending(self, db):
        raw_id = db.save_raw("bad.txt", "普通文本无结构")
        result = run_extract_stage(db, None)
        assert result.ok
        assert result.summary["processed"] == 1
        assert result.summary["failed"] == 1
        # 失败保持 pending
        assert db.pending_raws()[0]["id"] == raw_id

    def test_extract_stage_bad_source(self, db, tmp_path):
        result = run_extract_stage(db, tmp_path / "missing")
        assert result.ok is False
        assert "原文源不可读" in result.error

    def test_extract_stage_rerun_zero_processed(self, db, tmp_path):
        raw = tmp_path / "raw"
        raw.mkdir()
        (raw / "n1.txt").write_text(SAMPLE_ANNOUNCEMENT, encoding="utf-8")
        run_extract_stage(db, raw)
        result = run_extract_stage(db, raw)  # 内容指纹幂等
        assert result.summary["processed"] == 0
