"""src/extract schema 校验 + raw 暂存面测试（#601 批次 B·R5）。"""

from __future__ import annotations

import pytest

from src.extract.schema import (
    ExtractionSchemaError,
    validate_extraction,
    summarize_validation,
)
from src.storage.database import BidDatabase


# ----------------------------------------------------------------------
# schema 校验
# ----------------------------------------------------------------------


class TestValidateExtraction:
    def test_valid_payload_returns_record(self):
        record = validate_extraction(
            {
                "bid_id": "ZJ-2026-010",
                "project_name": "智慧城市二期",
                "budget": 1500,
                "publish_date": "2026-03-05",
                "requirements": ["ISO9001 认证"],
            }
        )
        assert record.bid_id == "ZJ-2026-010"
        assert record.budget == 1500.0
        assert record.publish_date == "2026-03-05"

    def test_non_dict_raises(self):
        with pytest.raises(ExtractionSchemaError, match="JSON 对象"):
            validate_extraction(["bid_id", "X"])

    def test_string_payload_raises(self):
        with pytest.raises(ExtractionSchemaError, match="JSON 对象"):
            validate_extraction("不是对象")

    def test_empty_dict_raises(self):
        with pytest.raises(ExtractionSchemaError, match="空对象"):
            validate_extraction({})

    def test_missing_bid_id_raises_with_field(self):
        with pytest.raises(ExtractionSchemaError) as exc_info:
            validate_extraction({"project_name": "只有名称"})
        assert exc_info.value.field == "bid_id"
        assert "bid_id" in str(exc_info.value)

    def test_missing_project_name_raises_with_field(self):
        with pytest.raises(ExtractionSchemaError) as exc_info:
            validate_extraction({"bid_id": "X-1"})
        assert exc_info.value.field == "project_name"

    def test_null_required_field_raises(self):
        with pytest.raises(ExtractionSchemaError, match="bid_id"):
            validate_extraction(
                {"bid_id": None, "project_name": "名称"}
            )

    def test_chinese_alias_keys_accepted(self):
        """LLM 偶发输出中文键——别名表兜住。"""
        record = validate_extraction(
            {
                "招标编号": "HW-2026-001",
                "项目名称": "数据中心采购",
                "预算金额": "1,200万元",
                "发布日期": "2026年3月1日",
            }
        )
        assert record.bid_id == "HW-2026-001"
        assert record.budget == 1200.0
        assert record.publish_date == "2026-03-01"

    def test_budget_string_normalized(self):
        record = validate_extraction(
            {
                "bid_id": "X-1",
                "project_name": "P",
                "budget": "3.5亿",
            }
        )
        assert record.budget == 35000.0

    def test_bad_date_degrades_to_none_with_warning(self):
        """日期解析失败 → None + warning（不抛——LLM 输出常含噪声日期）。"""
        record = validate_extraction(
            {
                "bid_id": "X-1",
                "project_name": "P",
                "publish_date": "详见公告正文",
            }
        )
        assert record.publish_date is None
        assert any("publish_date" in w for w in record.warnings)

    def test_bad_budget_degrades_to_none_with_warning(self):
        record = validate_extraction(
            {"bid_id": "X-1", "project_name": "P", "budget": "面议"}
        )
        assert record.budget is None
        assert any("budget" in w for w in record.warnings)

    def test_unknown_fields_go_to_extras(self):
        record = validate_extraction(
            {
                "bid_id": "X-1",
                "project_name": "P",
                "risk_notes": "多条采购包",
            }
        )
        assert record.extras.get("risk_notes") == "多条采购包"

    def test_requirements_scalar_wrapped(self):
        record = validate_extraction(
            {"bid_id": "X-1", "project_name": "P", "requirements": "ISO9001"}
        )
        assert record.requirements == ["ISO9001"]

    def test_roundtrip_to_database(self):
        """校验产物直接可入库（幂等回写路径）。"""
        record = validate_extraction(
            {
                "bid_id": "RT-001",
                "project_name": "闭环验证项目",
                "budget": "800万元",
            }
        )
        with BidDatabase(":memory:") as db:
            assert db.save_bid(record.to_bid_row()) == 1
            fetched = db.get_bid("RT-001")
            assert fetched["budget"] == 800.0


# ----------------------------------------------------------------------
# 校验摘要
# ----------------------------------------------------------------------


class TestSummarizeValidation:
    def test_summary_shape(self):
        record = validate_extraction(
            {
                "bid_id": "S-001",
                "project_name": "摘要验证",
                "budget": "面议",
                "publish_date": "2026-01-01",
            }
        )
        summary = summarize_validation(record)
        assert summary["ok"] is True
        assert summary["bid_id"] == "S-001"
        assert "budget" in summary["warnings"][0] or any(
            "budget" in w for w in summary["warnings"]
        )
        assert "publish_date" in summary["filled_fields"]
        assert "region" in summary["missing_fields"]

    def test_summary_extras_listed(self):
        record = validate_extraction(
            {
                "bid_id": "S-002",
                "project_name": "P",
                "extra_note": "whatever",
            }
        )
        summary = summarize_validation(record)
        assert summary["extras"] == ["extra_note"]


# ----------------------------------------------------------------------
# raw 暂存面（storage 层）
# ----------------------------------------------------------------------


class TestRawAnnouncements:
    def test_save_raw_returns_id(self, tmp_path):
        with BidDatabase(tmp_path / "t.db") as db:
            raw_id = db.save_raw("a.txt", "公告原文内容")
            assert raw_id >= 1

    def test_save_raw_idempotent_by_content(self, tmp_path):
        with BidDatabase(tmp_path / "t.db") as db:
            first = db.save_raw("a.txt", "同样内容")
            second = db.save_raw("b.txt", "同样内容")
            assert first == second
            assert db.raw_stats()["total"] == 1

    def test_has_raw_content(self, tmp_path):
        with BidDatabase(tmp_path / "t.db") as db:
            assert db.has_raw_content("某公告") is False
            db.save_raw("a.txt", "某公告")
            assert db.has_raw_content("某公告") is True

    def test_pending_flow_extracted(self, tmp_path):
        with BidDatabase(tmp_path / "t.db") as db:
            raw_id = db.save_raw("a.txt", "待抽取")
            db.mark_raw_extracted(raw_id, "BID-1")
            assert db.pending_raws() == []
            stats = db.raw_stats()
            assert stats == {"total": 1, "pending": 0, "extracted": 1}

    def test_mark_failed_keeps_pending_for_retry(self, tmp_path):
        """失败降级：状态保持 pending + error 留档，重试不丢。"""
        with BidDatabase(tmp_path / "t.db") as db:
            raw_id = db.save_raw("a.txt", "坏公告")
            db.mark_raw_failed(raw_id, "LLM 不可用（超时）")
            pending = db.pending_raws()
            assert len(pending) == 1
            assert pending[0]["attempts"] == 1
            stats = db.raw_stats()
            assert stats["pending"] == 1

    def test_retry_then_success(self, tmp_path):
        with BidDatabase(tmp_path / "t.db") as db:
            raw_id = db.save_raw("a.txt", "先失败后成功")
            db.mark_raw_failed(raw_id, "JSON 损坏")
            db.mark_raw_extracted(raw_id, "BID-2")
            stats = db.raw_stats()
            assert stats == {"total": 1, "pending": 0, "extracted": 1}
            # attempts 累计 2（一次失败 + 一次成功）
            assert db.pending_raws() == []

    def test_pending_limit(self, tmp_path):
        with BidDatabase(tmp_path / "t.db") as db:
            for i in range(5):
                db.save_raw(f"f{i}.txt", f"公告{i}")
            assert len(db.pending_raws(limit=3)) == 3
            assert len(db.pending_raws()) == 5

    def test_pending_order_stable(self, tmp_path):
        with BidDatabase(tmp_path / "t.db") as db:
            for i in range(3):
                db.save_raw(f"f{i}.txt", f"公告{i}")
            ids = [r["id"] for r in db.pending_raws()]
            assert ids == sorted(ids)

    def test_raw_stats_empty(self, tmp_path):
        with BidDatabase(tmp_path / "t.db") as db:
            assert db.raw_stats() == {"total": 0, "pending": 0, "extracted": 0}

    def test_extracted_then_reimport_same_content_no_pending(self, tmp_path):
        """已抽取的原文再次导入：内容指纹幂等，不回 pending。"""
        with BidDatabase(tmp_path / "t.db") as db:
            raw_id = db.save_raw("a.txt", "一次性公告")
            db.mark_raw_extracted(raw_id, "B-1")
            again = db.save_raw("a-again.txt", "一次性公告")
            assert again == raw_id
            assert db.pending_raws() == []
