"""src/extract.pending 模块单元测试（#601 批次 B 第 8 轮）。

覆盖 pending 登记（幂等/双流）、可重放载荷、重试（成功/仍失败/
载荷损坏）与 storage 层 pending CRUD。
"""

import pytest

from src.collect import AnnouncementRecord
from src.extract import (
    AnnouncementExtractor,
    REASON_LLM_ERROR,
    REASON_REJECTED,
    STATUS_RESOLVED,
    build_replay_payload,
    park_raw_failure,
    park_record_failure,
    raw_text_fingerprint,
    retry_pending,
)
from src.llm.client import LLMClient
from src.storage.database import BidDatabase


def _record(bid_id: str = "P-1", **extras) -> AnnouncementRecord:
    """构造记录：标题随 bid_id 变化（避免指纹互撞——指纹只看标题+日期+地区）。"""
    raw = {"bid_id": bid_id, "project_name": f"智慧城市项目-{bid_id}"}
    raw.update(extras)
    return AnnouncementRecord.from_raw(raw)


def _mock_extractor(llm_output) -> AnnouncementExtractor:
    """构造 chat_json 返回固定输出的抽取器。"""
    from unittest.mock import AsyncMock

    client = LLMClient(api_key="k")
    client.chat_json = AsyncMock(return_value=llm_output)
    return AnnouncementExtractor(client)


class TestFingerprintsAndPayload:
    """指纹与载荷面。"""

    def test_raw_text_fingerprint_stable(self):
        """同原文同指纹；空格差异不敏感（strip 口径）。"""
        assert raw_text_fingerprint("公告原文 A") == raw_text_fingerprint("公告原文 A ")
        assert raw_text_fingerprint("公告原文 A") != raw_text_fingerprint("公告原文 B")
        assert len(raw_text_fingerprint("x")) == 12

    def test_replay_payload_roundtrip(self):
        """可重放载荷：from_raw 原样重建记录（字段不丢失）。"""
        record = _record(
            "R-1", 预算金额="300万元", content="公告原文", 评分办法="综合评分法"
        )
        payload = build_replay_payload(record, "公告原文")
        rebuilt = AnnouncementRecord.from_raw(payload)
        assert rebuilt.bid_id == "R-1"
        assert rebuilt.budget == 300.0
        assert rebuilt.extras["评分办法"] == "综合评分法"
        assert rebuilt.extras["content"] == "公告原文"

    def test_replay_payload_without_text(self):
        """无原文时载荷不含 content 键。"""
        payload = build_replay_payload(_record("R-2"), None)
        assert "content" not in payload
        assert payload["bid_id"] == "R-2"


class TestParkFailures:
    """登记面（幂等 + 双流）。"""

    def test_park_record_failure_idempotent(self, tmp_path):
        """同件重复登记 upsert：行数不膨胀，error 更新。"""
        record = _record("F-1", content="原文")
        with BidDatabase(tmp_path / "b.db") as db:
            park_record_failure(
                db, record, REASON_LLM_ERROR, raw_text="原文", error="第一次失败"
            )
            park_record_failure(
                db, record, REASON_LLM_ERROR, raw_text="原文", error="第二次失败"
            )
            stats = db.pending_stats()
            rows = db.list_pending()
        assert stats["pending"] == 1
        assert rows[0]["error"] == "第二次失败"
        assert rows[0]["reason"] == REASON_LLM_ERROR
        assert rows[0]["bid_id"] == "F-1"
        assert rows[0]["raw_text"] == "原文"
        assert rows[0]["payload"]["bid_id"] == "F-1"  # 载荷已反序列化

    def test_park_raw_failure_no_bid_id(self, tmp_path):
        """原文流登记：bid_id 可空，指纹锚原文哈希。"""
        raw = "一份没有抽出编号的公告原文"
        with BidDatabase(tmp_path / "b.db") as db:
            park_raw_failure(
                db,
                raw,
                REASON_REJECTED,
                error="缺招标编号",
                extracted_fields={"region": "浙江省"},
            )
            rows = db.list_pending()
        assert rows[0]["bid_id"] is None
        assert rows[0]["fingerprint"] == raw_text_fingerprint(raw)
        assert rows[0]["payload"]["region"] == "浙江省"  # 部分字段保留
        assert rows[0]["payload"]["content"] == raw

    def test_park_missing_fingerprint_raises(self, tmp_path):
        """指纹为空 → KeyError（登记面硬门）。"""
        with BidDatabase(tmp_path / "b.db") as db, pytest.raises(KeyError):
            db.save_pending("  ", REASON_LLM_ERROR)


class TestStoragePendingCRUD:
    """storage 层 pending CRUD。"""

    def test_list_pending_status_filter(self, tmp_path):
        """list 按状态过滤。"""
        record = _record("C-1")
        with BidDatabase(tmp_path / "b.db") as db:
            park_record_failure(db, record, REASON_LLM_ERROR)
            park_record_failure(db, _record("C-2"), REASON_REJECTED)
            db.update_pending_status(
                _record("C-2").fingerprint(), STATUS_RESOLVED
            )
            assert len(db.list_pending()) == 1
            assert len(db.list_pending(status=STATUS_RESOLVED)) == 1

    def test_pending_stats_by_reason(self, tmp_path):
        """统计按 reason 分组。"""
        with BidDatabase(tmp_path / "b.db") as db:
            park_record_failure(db, _record("S-1"), REASON_LLM_ERROR)
            park_record_failure(db, _record("S-2"), REASON_LLM_ERROR)
            park_record_failure(db, _record("S-3"), REASON_REJECTED)
            stats = db.pending_stats()
        assert stats["pending"] == 3
        assert stats["by_reason"] == {REASON_LLM_ERROR: 2, REASON_REJECTED: 1}

    def test_update_missing_fingerprint_noop(self, tmp_path):
        """更新不存在的指纹 → 0 行受影响。"""
        with BidDatabase(tmp_path / "b.db") as db:
            assert db.update_pending_status("nope", STATUS_RESOLVED) == 0

    def test_corrupted_payload_tolerated(self, tmp_path):
        """损坏 payload JSON 不炸 list_pending（回退 None）。"""
        with BidDatabase(tmp_path / "b.db") as db:
            db.save_pending(
                "fp-x", REASON_REJECTED, payload=None
            )
            db._conn.execute(
                "UPDATE pending_announcements SET payload = '{broken'"
                " WHERE fingerprint = 'fp-x'"
            )
            db._conn.commit()
            rows = db.list_pending()
        assert rows[0]["payload"] is None


class TestRetryPending:
    """重试面。"""

    def test_retry_record_flow_success(self, tmp_path):
        """记录流重试成功：入库 + resolved。"""
        record = _record("T-1", content="项目预算 300万元")
        with BidDatabase(tmp_path / "b.db") as db:
            park_record_failure(
                db, record, REASON_LLM_ERROR, raw_text="项目预算 300万元",
                error="LLM 超时",
            )
            extractor = _mock_extractor(
                {"bid_id": "T-1", "budget": "300万元", "region": "浙江省"}
            )
            report = retry_pending(db, extractor)
            stats = db.pending_stats()
            stored = db.get_bid("T-1")
        assert report.attempted == 1
        assert report.resolved == 1
        assert report.still_pending == 0
        assert stats["resolved"] == 1
        assert stats["pending"] == 0
        assert stored["budget"] == 300.0

    def test_retry_raw_flow_success(self, tmp_path):
        """原文流重试成功：LLM 抽出编号 → 入库 + resolved。"""
        raw = "招标编号：W-9 的公告原文"
        with BidDatabase(tmp_path / "b.db") as db:
            park_raw_failure(db, raw, REASON_REJECTED, error="缺编号")
            extractor = _mock_extractor(
                {"bid_id": "W-9", "project_name": "原文流项目", "budget": 88.0}
            )
            report = retry_pending(db, extractor)
            stored = db.get_bid("W-9")
        assert report.resolved == 1
        assert stored["project_name"] == "原文流项目"
        assert stored["budget"] == 88.0

    def test_retry_still_missing_bid_id(self, tmp_path):
        """原文流重试仍缺编号 → 保持 pending，error 更新。"""
        raw = "还是没有编号的公告"
        with BidDatabase(tmp_path / "b.db") as db:
            park_raw_failure(db, raw, REASON_REJECTED, error="缺编号")
            extractor = _mock_extractor({"project_name": "只有名字"})
            report = retry_pending(db, extractor)
            stats = db.pending_stats()
        assert report.still_pending == 1
        assert stats["pending"] == 1

    def test_retry_llm_failure_keeps_pending(self, tmp_path):
        """LLM 重试又失败 → 保持 pending，error 更新为本次失败。"""
        from unittest.mock import AsyncMock

        record = _record("T-2", content="原文")
        with BidDatabase(tmp_path / "b.db") as db:
            park_record_failure(
                db, record, REASON_LLM_ERROR, raw_text="原文", error="第一次"
            )
            client = LLMClient(api_key="k")
            client.chat_json = AsyncMock(side_effect=RuntimeError("又超时"))
            report = retry_pending(db, AnnouncementExtractor(client))
            rows = db.list_pending()
        assert report.still_pending == 1
        assert "又超时" in rows[0]["error"]

    def test_retry_corrupted_payload_reported(self, tmp_path):
        """记录流载荷损坏 → skipped_rebuild 登记，不炸。"""
        record = _record("T-3")
        with BidDatabase(tmp_path / "b.db") as db:
            park_record_failure(db, record, REASON_LLM_ERROR)
            db._conn.execute(
                "UPDATE pending_announcements SET payload = '{broken'"
                " WHERE bid_id = 'T-3'"
            )
            db._conn.commit()
            extractor = _mock_extractor({"bid_id": "T-3"})
            report = retry_pending(db, extractor)
            stats = db.pending_stats()
        assert report.skipped_rebuild == 1
        assert stats["pending"] == 1  # 保持 pending 等人工处理

    def test_retry_limit(self, tmp_path):
        """limit 限制重试条数。"""
        with BidDatabase(tmp_path / "b.db") as db:
            for i in range(5):
                park_record_failure(
                    db, _record(f"L-{i}", content=f"原文{i}"), REASON_LLM_ERROR
                )
            extractor = _mock_extractor({"bid_id": "L-x"})
            report = retry_pending(db, extractor, limit=2)
        assert report.attempted == 2

    def test_retry_empty_pending(self, tmp_path):
        """空 pending 面 → 零尝试零失败。"""
        with BidDatabase(tmp_path / "b.db") as db:
            report = retry_pending(db, _mock_extractor({}))
        assert report.attempted == 0
        assert report.details == []
