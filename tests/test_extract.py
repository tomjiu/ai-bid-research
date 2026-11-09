"""src/extract 模块单元测试（#601 批次 B 第 5 轮）。

AsyncMock 替换 chat_json——不发真实网络请求；覆盖直通/LLM 双模式、
归一、合并策略与批量异常隔离。
"""

import asyncio
from unittest.mock import AsyncMock

import pytest

from src.collect import AnnouncementRecord
from src.extract import (
    AnnouncementExtractor,
    ExtractionError,
    ExtractionOutcome,
    merge_fields,
    resolve_raw_text,
)
from src.llm.client import LLMClient


def _record(bid_id: str = "X-1", **extras) -> AnnouncementRecord:
    """构造带原文 extras 的记录。"""
    raw = {"bid_id": bid_id, "project_name": "智慧城市项目"}
    raw.update(extras)
    return AnnouncementRecord.from_raw(raw)


def _mock_client(llm_output) -> LLMClient:
    """构造 chat_json 返回固定输出的 mock 客户端。"""
    client = LLMClient(api_key="test-key")
    client.chat_json = AsyncMock(return_value=llm_output)
    return client


RAW = "项目名称：智慧城市项目。预算金额：3,500,000元。"


class TestResolveRawText:
    """原文探测。"""

    def test_explicit_wins(self):
        """显式参数优先于 extras。"""
        record = _record(content="extras 原文")
        assert resolve_raw_text(record, "显式原文") == "显式原文"

    @pytest.mark.parametrize(
        "key", ["content", "公告原文", "text", "正文", "原文"]
    )
    def test_extras_keys_probed_in_order(self, key):
        """五个常见键都能探测到。"""
        record = _record(**{key: "来自 extras 的原文"})
        assert resolve_raw_text(record) == "来自 extras 的原文"

    def test_none_when_absent(self):
        """无原文 → None。"""
        assert resolve_raw_text(_record()) is None

    def test_blank_is_none(self):
        """空白原文视为无。"""
        record = _record(content="   ")
        assert resolve_raw_text(record) is None


class TestPassthroughMode:
    """直通模式（离线）。"""

    def test_no_text_passthrough(self):
        """无原文 → 直通 + 告警。"""
        extractor = AnnouncementExtractor(client=_mock_client({}))
        outcome = asyncio.run(extractor.extract(_record()))
        assert outcome.used_llm is False
        assert outcome.fields["bid_id"] == "X-1"
        assert "无公告原文" in outcome.warnings[0]

    def test_no_client_passthrough(self):
        """有原文但无客户端 → 离线直通，绝不调 API。"""
        record = _record(content=RAW)
        outcome = asyncio.run(AnnouncementExtractor().extract(record))
        assert outcome.used_llm is False
        assert "未配置 LLM 客户端" in outcome.warnings[0]
        assert outcome.raw_text is None  # 直通不回填原文


class TestLLMMode:
    """LLM 抽取模式。"""

    def test_extract_happy_path(self):
        """LLM 输出经归一进 fields。"""
        record = _record(content=RAW)
        client = _mock_client(
            {
                "project_name": "智慧城市项目",
                "bid_id": "X-1",
                "budget": "3,500,000元",  # → 350.0 万元
                "publish_date": "2026年11月1日",  # → 2026-11-01
                "region": "浙江省 杭州市",
                "requirements": "ISO9001；近三年业绩2项",
                "unknown_field": "不认识的字段应该被丢弃",
            }
        )
        outcome = asyncio.run(AnnouncementExtractor(client).extract(record))
        assert outcome.used_llm is True
        assert outcome.raw_text == RAW
        assert outcome.fields["budget"] == 350.0
        assert outcome.fields["publish_date"] == "2026-11-01"
        assert outcome.fields["region"] == "浙江省 杭州市"
        assert outcome.fields["requirements"] == ["ISO9001", "近三年业绩2项"]
        assert "unknown_field" not in outcome.fields
        client.chat_json.assert_awaited_once()

    def test_extract_prompt_carries_raw_text(self):
        """送入 LLM 的 user 消息含原文（提示词模板契约）。"""
        record = _record(content=RAW)
        client = _mock_client({"bid_id": "X-1"})
        asyncio.run(AnnouncementExtractor(client).extract(record))
        messages = client.chat_json.await_args.args[0]
        assert any(RAW in m["content"] for m in messages)
        assert any(m["role"] == "system" for m in messages)

    def test_llm_non_dict_output_raises(self):
        """LLM 输出非对象（如数组）→ ExtractionError。"""
        record = _record(content=RAW)
        client = _mock_client(["not", "a", "dict"])
        with pytest.raises(ExtractionError, match="JSON 对象"):
            asyncio.run(AnnouncementExtractor(client).extract(record))

    def test_llm_call_failure_wrapped(self):
        """底层 LLMError 包装为 ExtractionError（不裸抛）。"""
        record = _record(content=RAW)
        client = LLMClient(api_key="k")
        client.chat_json = AsyncMock(side_effect=RuntimeError("3 次重试失败"))
        with pytest.raises(ExtractionError, match="LLM 调用失败"):
            asyncio.run(AnnouncementExtractor(client).extract(record))

    def test_unparseable_budget_degrades_with_warning(self):
        """LLM 给的预算不可解析 → None + 告警（不炸）。"""
        record = _record(content=RAW)
        client = _mock_client({"bid_id": "X-1", "budget": "面议"})
        outcome = asyncio.run(AnnouncementExtractor(client).extract(record))
        assert outcome.fields["budget"] is None
        assert any("budget" in w for w in outcome.warnings)

    def test_empty_text_fields_become_none(self):
        """LLM 空串字段 → None（空值语义统一）。"""
        record = _record(content=RAW)
        client = _mock_client({"bid_id": "X-1", "purchaser": "  "})
        outcome = asyncio.run(AnnouncementExtractor(client).extract(record))
        assert outcome.fields["purchaser"] is None


class TestBatchExtraction:
    """批量抽取异常隔离。"""

    def test_batch_mixed_success_failure(self):
        """单条失败不中断整批，failures 登记。"""
        records = [_record("A-1", content=RAW), _record("A-2", content=RAW)]
        client = _mock_client({"bid_id": "ok"})
        client.chat_json = AsyncMock(
            side_effect=[{"bid_id": "A-1"}, RuntimeError("网络断")]
        )
        result = asyncio.run(
            AnnouncementExtractor(client).extract_batch(records)
        )
        assert [o.bid_id for o in result.outcomes] == ["A-1"]
        assert result.failures == [{"bid_id": "A-2", "error": "LLM 调用失败: 网络断"}]
        assert result.total == 2

    def test_batch_passthrough_all(self):
        """全直通批（无原文）零 API 调用。"""
        client = _mock_client({})
        records = [_record("P-1"), _record("P-2"), _record("P-3")]
        result = asyncio.run(
            AnnouncementExtractor(client).extract_batch(records)
        )
        assert len(result.outcomes) == 3
        assert result.failures == []
        client.chat_json.assert_not_awaited()

    def test_batch_raw_texts_length_mismatch(self):
        """raw_texts 长度不符 → ValueError。"""
        records = [_record("P-1")]
        with pytest.raises(ValueError, match="不一致"):
            asyncio.run(
                AnnouncementExtractor().extract_batch(records, [None, None])
            )


class TestMergeFields:
    """「LLM 补全不覆盖」合并策略。"""

    def test_extracted_fills_gaps_only(self):
        """源字段是强证据——LLM 只填缺，不覆盖。"""
        record_fields = {
            "bid_id": "M-1",
            "project_name": "源记录项目名",
            "budget": None,
            "region": "",
            "requirements": [],
        }
        extracted = {
            "project_name": "LLM 想改名（幻觉）",
            "budget": 500.0,
            "region": "浙江省 杭州市",
            "requirements": ["ISO9001"],
        }
        merged = merge_fields(record_fields, extracted)
        assert merged["project_name"] == "源记录项目名"  # 不被覆盖
        assert merged["budget"] == 500.0  # 补缺
        assert merged["region"] == "浙江省 杭州市"
        assert merged["requirements"] == ["ISO9001"]

    def test_merge_does_not_mutate_inputs(self):
        """合并不修改入参字典。"""
        record_fields = {"bid_id": "M-2", "budget": None}
        extracted = {"budget": 100.0}
        merge_fields(record_fields, extracted)
        assert record_fields["budget"] is None
        assert extracted["budget"] == 100.0

    def test_llm_none_values_do_not_overwrite(self):
        """LLM 给 None 不清空源值（缺省无意义）。"""
        merged = merge_fields(
            {"budget": 300.0}, {"budget": None, "region": None}
        )
        assert merged["budget"] == 300.0
        assert "region" not in merged


class TestOutcomeDataclass:
    """ExtractionOutcome 数据面。"""

    def test_defaults(self):
        """默认值可用（零字段构造）。"""
        outcome = ExtractionOutcome(bid_id="D-1")
        assert outcome.fields == {}
        assert outcome.raw_text is None
        assert outcome.used_llm is False
        assert outcome.warnings == []
