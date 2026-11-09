"""公告结构化抽取器（#601 批次 B）。

设计说明
--------
研究管道里一条公告记录可能只有稀疏字段（bid_id + 项目名），
正文要点（预算/日期/地区/资格要求…）在公告原文里。抽取器把
``原文 → LLM → 结构化字段``：

- **双模式**：

  - 直通模式（离线）：记录无原文或无 LLM 客户端 →
    :attr:`ExtractionOutcome.used_llm` 为 ``False``，fields 为
    记录既有字段的规范形态——离线可测，也是「结构化源不需要 LLM」
    的正确语义（不是失败）；
  - LLM 模式：原文 + ``PromptTemplates.bid_extraction`` →
    :meth:`LLMClient.chat_json`（三层正则兜底在 client 内）→
    输出经 ``src.collect.normalize`` 同套口径归一（与采集面
    一致，杜绝两套形态漂移）。

- **合并策略（LLM 补全不覆盖）**：源记录已有的结构化字段是
  采集面确认过的**强证据**，LLM 抽取只**补缺**（``merge_fields``）。
  LLM 幻觉不会污染既有字段——研究面宁可少信模型。

- **失败降级**：LLM 不可用 / 输出非 JSON / 输出非对象 →
  :class:`ExtractionError` 由调用方决定记 pending（批次 B 后续
  轮次的 raw 面登记），抽取器本身不吞错。

抽取走 ``chat_json`` 逐条顺序调用（客户端内已有信号量与限流），
批量接口 ``extract_batch`` 只做逐条编队与异常隔离——单条失败
不中断整批（失败项以 ``ExtractionError`` 形态登记在
``failures``，供调用方落 pending 面再处理）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.collect.normalize import (
    clean_text,
    normalize_budget,
    normalize_date,
    normalize_requirements,
)
from src.collect.records import AnnouncementRecord
from src.llm.prompts import PromptTemplates

#: 记录上可能携带公告原文的 extras 键（按序探测）。
_RAW_TEXT_KEYS = ("content", "公告原文", "text", "正文", "原文")

#: LLM 抽取输出的合法字段（与 PromptTemplates.bid_extraction 口径一致）。
_EXTRACTABLE_FIELDS = (
    "project_name",
    "bid_id",
    "budget",
    "publish_date",
    "deadline",
    "region",
    "purchaser",
    "agency",
    "category",
    "requirements",
)

#: 直通模式告警文案。
_WARN_NO_TEXT = "无公告原文——跳过 LLM 抽取（结构化源直通）"
_WARN_NO_CLIENT = "未配置 LLM 客户端——离线直通（不调用任何 API）"


class ExtractionError(ValueError):
    """公告抽取失败（LLM 输出不可用）。"""

    def __init__(self, bid_id: str, message: str) -> None:
        super().__init__(f"[{bid_id}] 抽取失败: {message}")
        self.bid_id = bid_id
        self.message = message


@dataclass
class ExtractionOutcome:
    """单条公告的抽取结果。

    Attributes:
        bid_id: 来源记录的招标编号（身份锚点）。
        fields: 抽取出的结构化字段（已归一）。
        raw_text: 送入 LLM 的公告原文（直通模式为 ``None``）。
        used_llm: 是否发生了真实 LLM 调用。
        warnings: 过程告警（缺原文/无客户端/字段降级）。
    """

    bid_id: str
    fields: Dict[str, Any] = field(default_factory=dict)
    raw_text: Optional[str] = None
    used_llm: bool = False
    warnings: List[str] = field(default_factory=list)


@dataclass
class BatchExtractionResult:
    """一批公告的抽取结果（异常隔离）。

    Attributes:
        outcomes: 成功的抽取结果。
        failures: 失败明细列表（``bid_id`` / ``error``）。
    """

    outcomes: List[ExtractionOutcome] = field(default_factory=list)
    failures: List[Dict[str, str]] = field(default_factory=list)

    @property
    def total(self) -> int:
        """成功 + 失败条数。"""
        return len(self.outcomes) + len(self.failures)


def resolve_raw_text(
    record: AnnouncementRecord, explicit: Optional[str] = None
) -> Optional[str]:
    """解析公告原文（显式参数 > extras 常见键）。

    Args:
        record: 规范化记录。
        explicit: 显式传入的原文（优先级最高）。

    Returns:
        公告原文；无原文返回 ``None``。
    """
    if explicit and explicit.strip():
        return explicit
    for key in _RAW_TEXT_KEYS:
        value = record.extras.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return None


class AnnouncementExtractor:
    """公告结构化抽取器（直通/LLM 双模式）。

    Attributes:
        client: LLM 客户端；``None`` 表示离线直通模式。
    """

    def __init__(self, client: Optional[Any] = None) -> None:
        """初始化抽取器。

        Args:
            client: :class:`~src.llm.client.LLMClient` 实例（须实现
                ``await chat_json(messages) -> Any``）；``None`` 为
                离线直通模式（永不发起网络调用）。
        """
        self.client = client

    async def extract(
        self,
        record: AnnouncementRecord,
        raw_text: Optional[str] = None,
    ) -> ExtractionOutcome:
        """抽取单条公告的结构化字段。

        Args:
            record: 规范化记录。
            raw_text: 公告原文（缺省时探测 record.extras 的
                ``content``/``公告原文``/``text``/``正文``/``原文`` 键）。

        Returns:
            抽取结果（直通模式 used_llm=False）。

        Raises:
            ExtractionError: LLM 模式下输出不可用（非 JSON/非对象/
                网络重试耗尽——底层 LLMError 会包一层成 ExtractionError）。
        """
        text = resolve_raw_text(record, raw_text)
        if text is None:
            return self._passthrough(record, [_WARN_NO_TEXT])
        if self.client is None:
            return self._passthrough(record, [_WARN_NO_CLIENT])

        prompt = PromptTemplates.bid_extraction(text)
        try:
            result = await self.client.chat_json(
                [
                    {"role": "system", "content": PromptTemplates.SYSTEM_ROLE},
                    {"role": "user", "content": prompt},
                ]
            )
        except Exception as exc:  # LLMError / 网络 / 解析——统一降级口径
            raise ExtractionError(record.bid_id, f"LLM 调用失败: {exc}") from exc

        if not isinstance(result, dict):
            raise ExtractionError(
                record.bid_id,
                f"LLM 输出须为 JSON 对象，实际为 {type(result).__name__}",
            )

        fields, warnings = self._normalize_llm_fields(result)
        return ExtractionOutcome(
            bid_id=record.bid_id,
            fields=fields,
            raw_text=text,
            used_llm=True,
            warnings=warnings,
        )

    async def extract_batch(
        self,
        records: List[AnnouncementRecord],
        raw_texts: Optional[List[Optional[str]]] = None,
    ) -> BatchExtractionResult:
        """批量抽取（逐条顺序，异常隔离——单条失败不中断整批）。

        Args:
            records: 规范化记录列表。
            raw_texts: 与 records 等长的原文列表（可含 ``None``）；
                缺省时逐条探测 extras。

        Returns:
            批量结果（outcomes + failures）。

        Raises:
            ValueError: raw_texts 长度与 records 不一致时。
        """
        if raw_texts is not None and len(raw_texts) != len(records):
            raise ValueError(
                f"raw_texts 长度 {len(raw_texts)} 与 records "
                f"长度 {len(records)} 不一致"
            )
        result = BatchExtractionResult()
        for index, record in enumerate(records):
            text = raw_texts[index] if raw_texts is not None else None
            try:
                result.outcomes.append(await self.extract(record, text))
            except ExtractionError as exc:
                result.failures.append(
                    {"bid_id": record.bid_id, "error": exc.message}
                )
        return result

    # ------------------------------------------------------------------
    # 内部
    # ------------------------------------------------------------------

    def _passthrough(
        self, record: AnnouncementRecord, warnings: List[str]
    ) -> ExtractionOutcome:
        """直通模式：记录既有字段即结果（已是规范形态）。"""
        return ExtractionOutcome(
            bid_id=record.bid_id,
            fields=record.to_bid_row(),
            used_llm=False,
            warnings=warnings,
        )

    @staticmethod
    def _normalize_llm_fields(payload: Dict[str, Any]) -> tuple:
        """LLM 输出归一：字段白名单 + 类型/形态清洗。

        Returns:
            (归一后字段字典, 告警列表) 二元组——与采集面同套口径。
        """
        fields: Dict[str, Any] = {}
        warnings: List[str] = []

        for name in _EXTRACTABLE_FIELDS:
            if name not in payload:
                continue
            value = payload.get(name)

            if name == "budget":
                number, warn = normalize_budget(value)
                fields["budget"] = number
                if warn:
                    warnings.append(f"budget: {warn}（已置 None）")
            elif name in ("publish_date", "deadline"):
                date, warn = normalize_date(value)
                fields[name] = date
                if warn:
                    warnings.append(f"{name}: {warn}（已置 None）")
            elif name == "requirements":
                fields["requirements"] = normalize_requirements(value)
            else:
                # 纯文本字段（project_name/bid_id/region/purchaser/
                # agency/category）：清洗即可
                cleaned = clean_text(value)
                fields[name] = cleaned or None

        return fields, warnings


def merge_fields(
    record_fields: Dict[str, Any], extracted: Dict[str, Any]
) -> Dict[str, Any]:
    """合并策略「LLM 补全不覆盖」：源字段是强证据，抽取只填缺。

    Args:
        record_fields: 源记录字段（规范形态，如
            :meth:`AnnouncementRecord.to_bid_row` 输出）。
        extracted: LLM 抽取字段（已归一）。

    Returns:
        合并后字段字典（副本，不修改入参）。
    """
    merged = dict(record_fields)
    for key, value in extracted.items():
        existing = merged.get(key)
        # 空值（None/空串/空列表）视为缺——LLM 可补
        if existing is None or existing == "" or existing == []:
            if value is not None and value != "" and value != []:
                merged[key] = value
    return merged
