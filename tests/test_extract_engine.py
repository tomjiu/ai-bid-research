"""src/extract 引擎测试（#601 批次 B·R6/R7）。

口径：规则基线抽取命中率（宁缺毋滥）、LLM 模式桩注入、
extract_record 全链（引擎→校验→结果）与失败降级。
异步路径统一 ``asyncio.run`` 驱动于同步测试内（仓内口径，
无 pytest-asyncio 依赖）。
"""

from __future__ import annotations

import asyncio

import pytest

from src.extract.engine import (
    ExtractionOutcome,
    LLMExtractor,
    RuleExtractor,
    extract_record,
    extract_record_async,
)
from src.extract.schema import ExtractionSchemaError
from src.llm.client import LLMError

#: 典型政采公告样例（规则基线的目标形态）。
SAMPLE_ANNOUNCEMENT = """黑龙江省哈尔滨市智慧城市一期建设项目招标公告

招标编号：HLJ-GC-2026-001

一、招标条件
本项目黑龙江省哈尔滨市智慧城市一期建设项目已由市发改委批准，
采购人为哈尔滨市大数据局，采购代理机构为黑龙江省招标有限公司，
资金来源为财政资金。

二、项目概况
建设地点：黑龙江省哈尔滨市
预算金额：1200万元
服务期：合同签订后 12 个月。

三、投标人资格要求
1. 具有独立法人资格，提供有效营业执照；
2. 具备 ISO9001 质量管理体系认证；
3. 近三年（2023-2025）完成类似业绩不少于 2 项；
4. 本项目不接受联合体投标。

四、投标截止时间
投标截止时间：2026年3月20日10时00分（北京时间）。

2026年3月1日
"""


class TestRuleExtractor:
    def test_bid_id_labeled(self):
        payload = RuleExtractor().extract(SAMPLE_ANNOUNCEMENT)
        assert payload["bid_id"] == "HLJ-GC-2026-001"

    def test_project_name_from_label(self):
        payload = RuleExtractor().extract(SAMPLE_ANNOUNCEMENT)
        assert "智慧城市一期建设项目" in payload["project_name"]

    def test_budget_with_unit(self):
        payload = RuleExtractor().extract(SAMPLE_ANNOUNCEMENT)
        assert payload["budget"] == "1200万元"

    def test_deadline_labeled_date(self):
        payload = RuleExtractor().extract(SAMPLE_ANNOUNCEMENT)
        assert payload["deadline"] == "2026-03-20"

    def test_publish_date_first_date(self):
        payload = RuleExtractor().extract(SAMPLE_ANNOUNCEMENT)
        assert payload["publish_date"] == "2026-03-01"

    def test_purchaser_labeled(self):
        payload = RuleExtractor().extract(SAMPLE_ANNOUNCEMENT)
        assert "大数据局" in payload["purchaser"]

    def test_agency_labeled(self):
        payload = RuleExtractor().extract(SAMPLE_ANNOUNCEMENT)
        assert "招标有限公司" in payload["agency"]

    def test_region_labeled(self):
        payload = RuleExtractor().extract(SAMPLE_ANNOUNCEMENT)
        assert "哈尔滨市" in payload["region"]

    def test_requirements_extracted(self):
        payload = RuleExtractor().extract(SAMPLE_ANNOUNCEMENT)
        joined = " ".join(payload["requirements"])
        assert "ISO9001" in joined
        assert "业绩" in joined

    def test_empty_text_returns_empty(self):
        assert RuleExtractor().extract("") == {}
        assert RuleExtractor().extract("   \n  ") == {}

    def test_non_announcement_extracts_little(self):
        """非公告文本：宁缺毋滥——抽不到就不硬凑。"""
        payload = RuleExtractor().extract(
            "今天天气不错。\n我们去公园散步，聊了聊最近的新闻。"
        )
        assert payload == {} or "bid_id" not in payload

    def test_budget_yi_unit(self):
        text = "预算金额：1.5亿\n项目名称：某轨道交通工程"
        payload = RuleExtractor().extract(text)
        assert payload["budget"] == "1.5亿"

    def test_project_name_from_title_line(self):
        """无「项目名称：」标签时退化取标题行（剥公告尾缀）。"""
        text = "某某市政务云平台采购项目招标公告\n招标编号：ZW-2026-9"
        payload = RuleExtractor().extract(text)
        assert payload["project_name"] == "某某市政务云平台采购项目"

    def test_full_payload_passes_schema(self):
        """规则载荷过 schema 校验（批 B 全链的地基）。"""
        outcome = extract_record(SAMPLE_ANNOUNCEMENT, RuleExtractor())
        assert outcome.ok, outcome.error
        record = outcome.record
        assert record.bid_id == "HLJ-GC-2026-001"
        assert record.budget == 1200.0  # 万元归一
        assert record.deadline == "2026-03-20"
        assert record.publish_date == "2026-03-01"


# ----------------------------------------------------------------------
# LLM 模式（桩注入）
# ----------------------------------------------------------------------


class FakeChatJsonClient:
    """LLMClient 桩：返回预设载荷（测试不碰网络）。"""

    def __init__(self, payload=None, error=None):
        self.payload = payload
        self.error = error
        self.calls = []

    async def chat_json(self, messages, **kwargs):
        self.calls.append(messages)
        if self.error:
            raise LLMError(self.error)
        return self.payload


class TestLLMExtractor:
    def test_success_flow(self):
        fake = FakeChatJsonClient(
            payload={
                "bid_id": "LLM-001",
                "project_name": "LLM 抽取项目",
                "budget": 500,
                "publish_date": "2026-02-01",
            }
        )
        extractor = LLMExtractor(fake)
        payload = asyncio.run(extractor.extract("公告原文"))
        assert payload["bid_id"] == "LLM-001"

    def test_async_success(self):
        fake = FakeChatJsonClient(
            payload={"bid_id": "LLM-002", "project_name": "异步抽取"}
        )
        outcome = asyncio.run(
            extract_record_async("公告原文", LLMExtractor(fake))
        )
        assert outcome.ok
        assert outcome.record.bid_id == "LLM-002"
        assert outcome.mode == "api"

    def test_llm_failure_degrades(self):
        """LLM 网络失败 → 失败结果（不抛），原文留 raw 面。"""
        fake = FakeChatJsonClient(error="连接超时")
        outcome = asyncio.run(
            extract_record_async("公告原文", LLMExtractor(fake))
        )
        assert outcome.ok is False
        assert "LLM 调用失败" in outcome.error

    def test_llm_non_dict_payload(self):
        fake = FakeChatJsonClient(payload=["不是对象"])
        outcome = asyncio.run(
            extract_record_async("公告原文", LLMExtractor(fake))
        )
        assert outcome.ok is False
        assert "schema 校验失败" in outcome.error or "JSON 对象" in outcome.error

    def test_llm_missing_required(self):
        fake = FakeChatJsonClient(payload={"budget": 100})
        outcome = asyncio.run(
            extract_record_async("公告原文", LLMExtractor(fake))
        )
        assert outcome.ok is False
        assert "bid_id" in outcome.error


# ----------------------------------------------------------------------
# extract_record 全链（同步 + 规则模式）
# ----------------------------------------------------------------------


class TestExtractRecord:
    def test_rule_mode_success(self):
        outcome = extract_record(SAMPLE_ANNOUNCEMENT, RuleExtractor())
        assert outcome.ok
        assert outcome.mode == "rule"
        assert "bid_id" in outcome.payload_fields

    def test_empty_text_failure(self):
        outcome = extract_record("", RuleExtractor())
        assert outcome.ok is False
        assert "未抽取到任何字段" in outcome.error

    def test_non_announcement_failure(self):
        outcome = extract_record(
            "这是一段普通文本，没有任何结构。", RuleExtractor()
        )
        assert outcome.ok is False

    def test_engine_exception_contained(self):
        class BoomExtractor:
            mode = "boom"

            def extract(self, text):
                raise RuntimeError("引擎内部爆炸")

        outcome = extract_record("任意", BoomExtractor())
        assert outcome.ok is False
        assert "引擎异常" in outcome.error
        assert "RuntimeError" in outcome.error

    def test_outcome_dataclass_shape(self):
        success = ExtractionOutcome.success(None, "rule", ["bid_id"])
        failure = ExtractionOutcome.failure("原因", "rule")
        assert success.ok and success.record is None
        assert not failure.ok and failure.error == "原因"
