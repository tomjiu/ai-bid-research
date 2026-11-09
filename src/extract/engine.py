"""抽取引擎（#601 批次 B·R6/R7）——原文 → 结构化载荷。

双模式（#601 任务书）：

* **RuleExtractor**（离线规则基线）——纯正则，无网络依赖；
  CI 冒烟 / 管道演练 / LLM 不可用时的兜底。命中率不追求完备，
  但**抽到的必须是真的**（宁缺毋滥，抽不到置 None）；
* **LLMExtractor**（真实 API）——走 :class:`LLMClient.chat_json` +
  ``PromptTemplates.bid_extraction`` 研究提示词
  （PYTHON-BOUNDARY.md §2：与 Rust 生产提示词分开演进）。

两模式产出统一为「载荷 dict」，经 :func:`validate_extraction`
schema 校验后才可入库——**引擎与校验解耦**，加新模式不改校验。
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Protocol

from src.llm.client import LLMClient, LLMError
from src.llm.prompts import PromptTemplates

from src.extract.schema import (
    ExtractionSchemaError,
    validate_extraction,
)
from src.collect.records import AnnouncementRecord

logger = logging.getLogger("ai-bid-research.extract")

#: 引擎模式名（CLI ``--mode`` 取值）。
EXTRACTION_MODES = ("rule", "api")


# ----------------------------------------------------------------------
# 结果模型
# ----------------------------------------------------------------------


@dataclass
class ExtractionOutcome:
    """单条原文的抽取结果。

    Attributes:
        ok: 抽取 + 校验是否成功。
        record: 成功时的规范记录。
        error: 失败原因（人读，进 raw 暂存面 ``error`` 列）。
        mode: 引擎模式（``rule`` / ``api``）。
        payload_fields: 载荷中非空字段名（诊断面：引擎命中率）。
    """

    ok: bool
    record: Optional[AnnouncementRecord] = None
    error: Optional[str] = None
    mode: str = "rule"
    payload_fields: list = field(default_factory=list)

    @classmethod
    def success(
        cls, record: AnnouncementRecord, mode: str, payload_fields: list
    ) -> "ExtractionOutcome":
        """构造成功结果。"""
        return cls(
            ok=True, record=record, mode=mode, payload_fields=payload_fields
        )

    @classmethod
    def failure(cls, error: str, mode: str) -> "ExtractionOutcome":
        """构造失败结果（原文留 raw 面 pending，等重试）。"""
        return cls(ok=False, error=error, mode=mode)


# ----------------------------------------------------------------------
# 引擎协议
# ----------------------------------------------------------------------


class AnnouncementExtractor(Protocol):
    """抽取引擎协议：原文 → 结构化载荷（未经校验）。"""

    mode: str

    def extract(self, text: str) -> Dict[str, Any]:
        """从公告原文抽取结构化载荷。

        Args:
            text: 公告原文全文。

        Returns:
            载荷字典（字段可缺失，交由 schema 校验裁决）。
        """
        ...  # pragma: no cover


# ----------------------------------------------------------------------
# 规则基线（离线）
# ----------------------------------------------------------------------

#: 「标签：值」形态的字段抽取规则（值截至标点或空白）。
_LABELED_PATTERNS: Dict[str, re.Pattern] = {
    "bid_id": re.compile(
        r"(?:招标编号|项目编号|采购编号|标段编号|公告编号|编号)"
        r"[：:]\s*([A-Za-z0-9\[\]（）()\-—_.]{4,})"
    ),
    "project_name": re.compile(
        r"(?:项目名称|工程名称|采购项目名称|项目)[：:]\s*"
        r"([^\s，,。；;：:]{4,})"
    ),
    "purchaser": re.compile(
        r"(?:采购人|招标人|项目业主|采购单位)(?:[：:]\s*|为)([^\s，,。；:：]{3,})"
    ),
    "agency": re.compile(
        r"(?:采购代理机构|代理机构|招标代理)(?:[：:]\s*|为)([^\s，,。；:：]{3,})"
    ),
    "region": re.compile(
        r"(?:项目所在地|建设地点|项目地点|地[：:]区?)\s*[：:]?\s*"
        r"([^\s，,。；;]{2,10})"
    ),
}

#: 金额规则：标签 + 数字 + 单位（千分位容忍）。
_BUDGET_RE = re.compile(
    r"(?:预算金额|最高限价|采购预算|预算|控制价|投资估算|合同估算价)"
    r"[：:]?\s*(?:人民币)?\s*([0-9][0-9,，.]*)\s*(亿元|万元|亿|万|元|圆)"
)

#: 日期规则（年月日三段，支持 - / 年月日 分隔，可带时间尾部）。
_DATE_RE = re.compile(
    r"(\d{4})\s*[年\-/.]\s*(\d{1,2})\s*[月\-/.]\s*(\d{1,2})\s*日?"
)

#: 截止时间标签。
_DEADLINE_LABEL_RE = re.compile(
    r"(?:投标截止时间|递交(?:投标|响应)?文件截止时间|投标文件递交截止时间"
    r"|报名及递交截止时间|响应文件递交截止时间|截止时间|投标截止)"
)

#: 发布日期标签。
_PUBLISH_LABEL_RE = re.compile(r"(?:发布日期|公告日期|发布时间|公告时间)")

#: 标题尾缀（剥离后即项目名）。
_TITLE_SUFFIX_RE = re.compile(
    r"(?:招标公告|采购公告|竞争性磋商公告|询价公告|中标公告|公告)$"
)

#: 采购类别启发关键词。
_CATEGORY_HINTS = (
    ("工程", ("建设", "施工", "改造", "安装工程", "监理")),
    ("货物", ("设备", "货物", "采购清单", "产品")),
    ("服务", ("服务", "运维", "运营", "咨询", "评估", "租赁")),
)

#: 资格要求小节标签。
_REQUIREMENT_SECTION_RE = re.compile(
    r"(?:资格要求|投标人资格要求|供应商资格要求|资格条件)"
)

#: 小节边界：中文序号标题（「四、」）——阿拉伯「1.」是条目内编号不算新小节。
_SECTION_BOUNDARY_RE = re.compile(
    r"\n\s*(?:[一二三四五六七八九十]+[、.]|(?:资格|招标|投标|开标|评标|公告|联系方式|联系|其他|附)[^\n]{0,6}[：:]?\s*$)",
    re.MULTILINE,
)


class RuleExtractor:
    """离线规则抽取基线（正则，无网络依赖）。

    Attributes:
        mode: 恒为 ``"rule"``。
    """

    mode = "rule"

    def extract(self, text: str) -> Dict[str, Any]:
        """按规则从公告原文抽取载荷。

        Args:
            text: 公告原文全文。

        Returns:
            载荷字典——抽不到的字段**不出现**（而非置空串），
            宁缺毋滥。
        """
        if not text or not text.strip():
            return {}

        payload: Dict[str, Any] = {}

        # ① 标题行 → 项目名（首选「项目名称：」标签，退化用标题行）
        payload["project_name"] = self._extract_project_name(text)

        # ② 标签字段（编号/采购人/代理机构/地区）
        for field_name, pattern in _LABELED_PATTERNS.items():
            if field_name == "project_name" and payload.get("project_name"):
                continue
            match = pattern.search(text)
            if match:
                payload[field_name] = match.group(1).strip()

        # ③ 金额（万元归一在 schema 校验层完成，这里只抓原文值+单位）
        budget = self._extract_budget(text)
        if budget is not None:
            payload["budget"] = budget

        # ④ 日期（截止时间带标签优先；发布日期：标签 > 尾部落款日期）
        deadline = self._extract_labeled_date(text, _DEADLINE_LABEL_RE)
        if deadline:
            payload["deadline"] = deadline
        publish = self._extract_labeled_date(text, _PUBLISH_LABEL_RE)
        if not publish:
            publish = self._footer_date(text, exclude=deadline)
        if publish:
            payload["publish_date"] = publish

        # ⑤ 采购类别（关键词启发，弱证据时省略）
        category = self._extract_category(text)
        if category:
            payload["category"] = category

        # ⑥ 资格要求（小节内含资质/业绩/认证的短句，至多 5 条）
        requirements = self._extract_requirements(text)
        if requirements:
            payload["requirements"] = requirements

        return {k: v for k, v in payload.items() if v}

    # ------------------------------------------------------------------
    # 内部
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_project_name(text: str) -> Optional[str]:
        """项目名：标签值优先，退化取标题行（剥公告尾缀）。"""
        match = _LABELED_PATTERNS["project_name"].search(text)
        if match:
            return match.group(1).strip()
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            title = _TITLE_SUFFIX_RE.sub("", stripped)
            # 标题行应含「项目/采购/招标」类关键词且非纯编号
            if (
                len(title) >= 6
                and re.search(r"[项目采购招标]", title)
                and not re.match(r"^[0-9\.\s]+$", title)
            ):
                return title
        return None

    @staticmethod
    def _extract_budget(text: str) -> Optional[str]:
        """金额：返回「数字+单位」原文串（schema 层归一万元）。"""
        match = _BUDGET_RE.search(text)
        if not match:
            return None
        return f"{match.group(1)}{match.group(2)}"

    @staticmethod
    def _extract_labeled_date(text: str, label_re: re.Pattern) -> Optional[str]:
        """标签之后的第一个日期（标签后 24 字符窗口内）。"""
        for label_match in label_re.finditer(text):
            window = text[label_match.end() : label_match.end() + 24]
            date_match = _DATE_RE.search(window)
            if date_match:
                y, m, d = date_match.groups()
                return f"{y}-{int(m):02d}-{int(d):02d}"
        return None

    @staticmethod
    def _footer_date(text: str, exclude: Optional[str]) -> Optional[str]:
        """尾部落款日期：全文最后一个日期，与截止日相同则视为无据（None）。

        公告惯例：正文末尾单独一行的日期是发布落款——比「全文首个
        日期」可靠（首个常是截止时间）。"""
        dates = _DATE_RE.findall(text)
        if not dates:
            return None
        normalized = [f"{y}-{int(m):02d}-{int(d):02d}" for y, m, d in dates]
        for value in reversed(normalized):
            if value != exclude:
                return value
        return None

    @staticmethod
    def _extract_category(text: str) -> Optional[str]:
        """采购类别启发（货物/服务/工程——按关键词密度）。"""
        scores = {
            name: sum(text.count(kw) for kw in keywords)
            for name, keywords in _CATEGORY_HINTS
        }
        best = max(scores, key=lambda k: scores[k])
        return best if scores[best] >= 2 else None

    @staticmethod
    def _extract_requirements(text: str) -> list:
        """资格要求小节内的资质/业绩/认证短句（≤5 条）。"""
        section = _REQUIREMENT_SECTION_RE.search(text)
        if not section:
            return []
        tail = text[section.end() : section.end() + 600]
        # 小节截止：下一个中文序号小节标题（如「四、」）——
        # 阿拉伯「1.」是条目编号不算新小节
        end = _SECTION_BOUNDARY_RE.search(tail)
        if end:
            tail = tail[: end.start()]
        clauses = [
            clause.strip(" ；;，,。")
            for clause in re.split(r"[；;\n]", tail)
            if re.search(r"(资质|业绩|认证|资格|注册资本|保证金|信用)", clause)
            and 4 <= len(clause.strip()) <= 80
        ]
        return clauses[:5]


# ----------------------------------------------------------------------
# LLM 模式（真实 API）
# ----------------------------------------------------------------------


class LLMExtractor:
    """LLM 抽取引擎（真实 API——DeepSeek 兼容接口）。

    Attributes:
        mode: 恒为 ``"api"``。
        client: 注入的 :class:`LLMClient`（测试可注入桩）。
    """

    mode = "api"

    def __init__(self, client: LLMClient) -> None:
        """初始化。

        Args:
            client: 已配置好的 LLM 客户端（API key 从环境变量读取，
                见 :class:`LLMClient`）。
        """
        self.client = client

    async def extract(self, text: str) -> Dict[str, Any]:
        """LLM 抽取（研究提示词 + JSON mode）。

        Args:
            text: 公告原文全文。

        Returns:
            载荷字典（LLM 输出，未经校验）。

        Raises:
            LLMError: 调用失败或 JSON 无法解析（调用方降级）。
        """
        messages = [
            {"role": "system", "content": PromptTemplates.SYSTEM_ROLE},
            {
                "role": "user",
                "content": PromptTemplates.bid_extraction(text),
            },
        ]
        payload = await self.client.chat_json(messages)
        if not isinstance(payload, dict):
            raise LLMError(f"LLM 返回的不是 JSON 对象: {type(payload).__name__}")
        return payload


# ----------------------------------------------------------------------
# 统一编排：引擎 + schema 校验
# ----------------------------------------------------------------------


def extract_record(
    text: str, extractor: AnnouncementExtractor
) -> ExtractionOutcome:
    """单条抽取全链：引擎载荷 → schema 校验 → 规范记录。

    Args:
        text: 公告原文。
        extractor: 抽取引擎（rule / api / 桩）。

    Returns:
        抽取结果（成功含记录；失败含人读原因——不抛异常，
        调用方据此走 raw 暂存降级）。
    """
    try:
        payload = extractor.extract(text)
    except LLMError as exc:
        return ExtractionOutcome.failure(f"LLM 调用失败: {exc}", extractor.mode)
    except Exception as exc:  # noqa: BLE001——引擎实现异常见底不外泄
        return ExtractionOutcome.failure(
            f"引擎异常: {type(exc).__name__}: {exc}", extractor.mode
        )

    if not payload:
        return ExtractionOutcome.failure(
            "引擎未抽取到任何字段（原文可能非公告或形态过异）",
            extractor.mode,
        )
    try:
        record = validate_extraction(payload)
    except ExtractionSchemaError as exc:
        return ExtractionOutcome.failure(f"schema 校验失败: {exc}", extractor.mode)
    return ExtractionOutcome.success(
        record, extractor.mode, sorted(payload.keys())
    )


async def extract_record_async(
    text: str, extractor: AnnouncementExtractor
) -> ExtractionOutcome:
    """异步版抽取全链（LLM 模式走网络 IO）。"""
    try:
        payload = await extractor.extract(text)
    except LLMError as exc:
        return ExtractionOutcome.failure(f"LLM 调用失败: {exc}", extractor.mode)
    except Exception as exc:  # noqa: BLE001
        return ExtractionOutcome.failure(
            f"引擎异常: {type(exc).__name__}: {exc}", extractor.mode
        )
    if not payload:
        return ExtractionOutcome.failure(
            "引擎未抽取到任何字段（原文可能非公告或形态过异）",
            extractor.mode,
        )
    try:
        record = validate_extraction(payload)
    except ExtractionSchemaError as exc:
        return ExtractionOutcome.failure(f"schema 校验失败: {exc}", extractor.mode)
    return ExtractionOutcome.success(
        record, extractor.mode, sorted(payload.keys())
    )
