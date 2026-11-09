"""src/extract.store 模块单元测试（#601 批次 B 第 7 轮）。

离线链路：mock chat_json → 抽取 → 合并 → 校验 → upsert 真库
（tmp_path SQLite）。
"""

import asyncio
from typing import Any, Dict, Optional

import pytest

from src.collect import AnnouncementRecord
from src.extract import (
    AnnouncementExtractor,
    BatchExtractionResult,
    ExtractionOutcome,
    apply_extraction,
    apply_extraction_batch,
    apply_extraction_from_raw,
)
from src.llm.client import LLMClient
from src.storage.database import BidDatabase


def _record(bid_id: str = "T-1", **extras) -> AnnouncementRecord:
    raw = {"bid_id": bid_id, "project_name": "智慧城市项目"}
    raw.update(extras)
    return AnnouncementRecord.from_raw(raw)


def _outcome(
    bid_id: str = "T-1",
    fields: Optional[Dict[str, Any]] = None,
    used_llm: bool = True,
) -> ExtractionOutcome:
    return ExtractionOutcome(
        bid_id=bid_id,
        fields=fields or {},
        raw_text="原文" if used_llm else None,
        used_llm=used_llm,
    )


class TestApplyExtraction:
    """记录流入库。"""

    def test_merge_and_store(self, tmp_path):
        """LLM 补缺字段入库：源字段保留、缺位补齐。"""
        record = _record("M-1")  # 稀疏：只有编号+名称
        outcome = _outcome(
            "M-1",
            fields={
                "budget": 350.0,
                "publish_date": "2026-11-01",
                "region": "浙江省 杭州市",
            },
        )
        with BidDatabase(tmp_path / "b.db") as db:
            result = apply_extraction(db, outcome, record.to_bid_row())
            stored = db.get_bid("M-1")
        assert result.status == "stored"
        assert result.saved == 1
        assert stored["budget"] == 350.0
        assert stored["publish_date"] == "2026-11-01"
        assert stored["project_name"] == "智慧城市项目"
        assert 0.3 < result.hit_rate < 1.0

    def test_extracted_never_overwrites(self, tmp_path):
        """源字段强证据：LLM 幻觉改名不入库。"""
        record = _record("M-2", 预算金额="500万元")
        outcome = _outcome(
            "M-2", fields={"project_name": "幻觉名称", "budget": 1.0}
        )
        with BidDatabase(tmp_path / "b.db") as db:
            apply_extraction(db, outcome, record.to_bid_row())
            stored = db.get_bid("M-2")
        assert stored["project_name"] == "智慧城市项目"
        assert stored["budget"] == 500.0  # 源 500 万不被 LLM 的 1.0 覆盖

    def test_upsert_idempotent(self, tmp_path):
        """同 bid_id 重复入库 upsert 幂等，行数不膨胀。"""
        record = _record("M-3")
        outcome = _outcome("M-3", fields={"budget": 100.0})
        with BidDatabase(tmp_path / "b.db") as db:
            apply_extraction(db, outcome, record.to_bid_row())
            apply_extraction(db, outcome, record.to_bid_row())
            stats = db.stats()
        assert stats["total"] == 1

    def test_passthrough_stored_as_is(self, tmp_path):
        """直通 outcome（used_llm=False）同样入库。"""
        record = _record("M-4", 地区="江苏省 南京市")
        with BidDatabase(tmp_path / "b.db") as db:
            result = apply_extraction(db, _outcome("M-4", used_llm=False), record.to_bid_row())
            stored = db.get_bid("M-4")
        assert result.status == "stored"
        assert result.used_llm is False
        assert stored["region"] == "江苏省 南京市"

    def test_defensive_rejection_on_invalid_merge(self, tmp_path):
        """防御面：合并结果缺必填（此处模拟非记录流形态）→ 拒收不静默。"""
        record_fields = {"bid_id": None, "project_name": "缺编号的合并结果"}
        outcome = _outcome("R-1", fields={})
        with BidDatabase(tmp_path / "b.db") as db:
            result = apply_extraction(db, outcome, record_fields)
            stats = db.stats()
        assert result.status == "rejected"
        assert result.missing_required == ["bid_id"]
        assert stats["total"] == 0


class TestApplyExtractionFromRaw:
    """原文流入库（无源记录）。"""

    def test_complete_llm_output_stored(self, tmp_path):
        """LLM 抽出全字段（含编号）→ 直接入库。"""
        outcome = _outcome(
            "W-1",
            fields={
                "bid_id": "W-1",
                "project_name": "原文抽取项目",
                "budget": "3,500,000元",  # 校验前已归一的口径见 extractor 测试；
            },                              # store 面吃已归一字段——此处数字面
        )
        outcome.fields["budget"] = 350.0  # 归一后形态
        with BidDatabase(tmp_path / "b.db") as db:
            result = apply_extraction_from_raw(db, outcome)
            stored = db.get_bid("W-1")
        assert result.status == "stored"
        assert stored["budget"] == 350.0
        assert stored["requirements"] == []

    def test_missing_bid_id_rejected(self, tmp_path):
        """原文流缺编号 → 拒收（不合成伪编号）。"""
        outcome = _outcome(
            None, fields={"project_name": "没编号的公告", "budget": 100.0}
        )
        with BidDatabase(tmp_path / "b.db") as db:
            result = apply_extraction_from_raw(db, outcome)
            stats = db.stats()
        assert result.status == "rejected"
        assert result.bid_id is None
        assert result.missing_required == ["bid_id"]
        assert stats["total"] == 0

    def test_missing_project_name_rejected(self, tmp_path):
        """原文流缺项目名 → 拒收。"""
        outcome = _outcome("W-3", fields={"bid_id": "W-3"})
        with BidDatabase(tmp_path / "b.db") as db:
            result = apply_extraction_from_raw(db, outcome)
        assert result.status == "rejected"
        assert result.missing_required == ["project_name"]


class TestApplyExtractionBatch:
    """批量入库。"""

    def test_batch_record_flow(self, tmp_path):
        """批量记录流：outcomes 与源字段一一对应入库。"""
        records = [_record("B-1"), _record("B-2", 预算金额="200万元")]
        batch = BatchExtractionResult(
            outcomes=[
                _outcome("B-1", fields={"budget": 1.0}),  # B-1 补缺
                _outcome("B-2", fields={"region": "广东省"}),  # B-2 补缺
            ]
        )
        with BidDatabase(tmp_path / "b.db") as db:
            result = apply_extraction_batch(
                db, batch, [r.to_bid_row() for r in records]
            )
            stats = db.stats()
            stored2 = db.get_bid("B-2")
        assert result.stored == 2
        assert result.rejected == 0
        assert stats["total"] == 2
        assert stored2["budget"] == 200.0  # 源字段优先
        assert stored2["region"] == "广东省"  # LLM 补缺

    def test_batch_raw_flow(self, tmp_path):
        """批量原文流：一条拒收不殃及整批。"""
        batch = BatchExtractionResult(
            outcomes=[
                _outcome("G-1", fields={"bid_id": "G-1", "project_name": "甲"}),
                _outcome(None, fields={"project_name": "无编号乙"}),
                _outcome("G-3", fields={"bid_id": "G-3", "project_name": "丙"}),
            ]
        )
        with BidDatabase(tmp_path / "b.db") as db:
            result = apply_extraction_batch(db, batch)
            stats = db.stats()
        assert result.stored == 2
        assert result.rejected == 1
        assert stats["total"] == 2

    def test_batch_length_mismatch(self, tmp_path):
        """records_fields 长度不符 → ValueError。"""
        batch = BatchExtractionResult(outcomes=[_outcome("B-9")])
        with BidDatabase(tmp_path / "b.db") as db:
            with pytest.raises(ValueError, match="不一致"):
                apply_extraction_batch(db, batch, [{"bid_id": "x"}, {"bid_id": "y"}])

    def test_batch_llm_used_count(self, tmp_path):
        """llm_used 计数只统计真实 LLM 调用。"""
        batch = BatchExtractionResult(
            outcomes=[
                _outcome("U-1", used_llm=True),
                _outcome("U-2", used_llm=False),
            ]
        )
        with BidDatabase(tmp_path / "b.db") as db:
            result = apply_extraction_batch(db, batch)
        assert result.llm_used == 1


class TestEndToEndOffline:
    """离线端到端：collect 装载 → 抽取 → 入库一条龙。"""

    def test_collect_to_store_chain(self, tmp_path):
        """采集→抽取→入库全链（离线 mock LLM）。"""
        import json

        source = tmp_path / "src"
        source.mkdir()
        (source / "a.json").write_text(
            json.dumps(
                [
                    {
                        "bid_id": "E-1",
                        "project_name": "端到端项目",
                        "content": "预算金额：120万元。发布日期：2026年11月2日。",
                    }
                ],
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        # 采集面
        from src.collect import dedupe_records, load_records

        loaded = load_records(source)
        deduped = dedupe_records(loaded.records)
        assert len(deduped.unique) == 1

        # 抽取面（mock LLM 返回归一前原始形态，验证归一入口一致）
        client = LLMClient(api_key="k")
        client.chat_json = _async_mock(
            {"budget": "120万元", "publish_date": "2026年11月2日", "region": "浙江省"}
        )
        extractor = AnnouncementExtractor(client)
        batch = asyncio.run(extractor.extract_batch(deduped.unique))

        # 入库面
        with BidDatabase(tmp_path / "b.db") as db:
            result = apply_extraction_batch(
                db, batch, [r.to_bid_row() for r in deduped.unique]
            )
            stored = db.get_bid("E-1")
        assert result.stored == 1
        assert batch.outcomes[0].used_llm is True
        assert stored["budget"] == 120.0
        assert stored["publish_date"] == "2026-11-02"
        assert stored["region"] == "浙江省"


def _async_mock(value):
    """构造返回固定值的 AsyncMock。"""
    from unittest.mock import AsyncMock

    return AsyncMock(return_value=value)
