"""公告记录规范化模型（采集面核心数据结构）。

设计说明
--------
异构来源（不同网站的 JSON 导出、人工整理的 JSONL、采集器落盘件）
字段名与字段形态不一（``招标编号`` vs ``bid_id``；``350万元`` vs
``3500000元`` vs ``1.2亿``；日期 ``2026/11/9`` vs ``2026年11月9日``）。
``AnnouncementRecord`` 是进入管道的**唯一规范化入口**：

- 字段名别名归一（中文常见命名 → 规范名）；
- 字段值清洗（金额统一为「万元」、日期统一为 ``YYYY-MM-DD``、
  地区空白折叠、requirements 切分为列表）；
- 必填校验（``bid_id`` + ``project_name``），失败抛
  :class:`RecordValidationError` 并携带字段级明细；
- 未知字段不丢弃，保留在 :attr:`AnnouncementRecord.extras`
  （研究面可追溯，入库时忽略——bids 表列固定）；
- :meth:`AnnouncementRecord.fingerprint` 产出「标题+日期+地区」指纹，
  供去重面（同件多源防重复入库）使用。

金额单位约定：入库列 ``budget`` 一律为**万元**（float）——与
``src/storage`` 既有测试基线（``budget: 350.0``）一致，不做隐式换算。
"""

from __future__ import annotations

import hashlib
from typing import Any, Dict, List, Optional

from src.collect.normalize import (
    clean_text as _clean_text,
    normalize_budget as _normalize_budget,
    normalize_date as _normalize_date,
    normalize_requirements as _normalize_requirements,
)
#: 规范字段名 ← 来源别名（小写比较；别名命中即映射到规范名）。
#: 规范名集合与 ``src/storage.database._BID_COLUMNS`` 对齐。
_FIELD_ALIASES: Dict[str, str] = {
    # 规范名
    "bid_id": "bid_id",
    "project_name": "project_name",
    "region": "region",
    "budget": "budget",
    "publish_date": "publish_date",
    "deadline": "deadline",
    "category": "category",
    "purchaser": "purchaser",
    "agency": "agency",
    "winner": "winner",
    "source_url": "source_url",
    "requirements": "requirements",
    # 中文常见命名
    "招标编号": "bid_id",
    "编号": "bid_id",
    "项目名称": "project_name",
    "项目": "project_name",
    "地区": "region",
    "区域": "region",
    "预算金额": "budget",
    "预算": "budget",
    "金额": "budget",
    "发布日期": "publish_date",
    "公告日期": "publish_date",
    "截止时间": "deadline",
    "投标截止": "deadline",
    "类别": "category",
    "采购人": "purchaser",
    "招标人": "purchaser",
    "代理机构": "agency",
    "中标人": "winner",
    "链接": "source_url",
    "公告链接": "source_url",
    "资格要求": "requirements",
    "资格条件": "requirements",
}


class RecordValidationError(ValueError):
    """公告记录校验失败。

    Attributes:
        field: 违规字段名。
        reason: 人读原因。
    """

    def __init__(self, field: str, reason: str) -> None:
        super().__init__(f"字段「{field}」校验失败: {reason}")
        self.field = field
        self.reason = reason


class AnnouncementRecord:
    """规范化后的招标公告记录。

    Attributes:
        bid_id: 招标编号（必填，非空字符串）。
        project_name: 项目名称（必填，非空字符串）。
        region: 地区（空白折叠后）。
        budget: 预算金额，单位万元（``None`` 表示未知/面议）。
        publish_date: 发布日期（``YYYY-MM-DD`` 或 ``None``）。
        deadline: 投标截止日期（``YYYY-MM-DD`` 或 ``None``）。
        category: 类别。
        purchaser: 采购人/招标人。
        agency: 代理机构。
        winner: 中标人（未开标为 ``None``）。
        source_url: 公告链接。
        requirements: 资格要求列表（自由文本摘要，与
            ``docs/PYTHON-BOUNDARY.md`` §3 schema 对齐）。
        extras: 别名归一后仍未识别的来源字段（研究面保留，不入库）。
        warnings: 清洗过程产生的告警（如金额无法解析→置 None）。
    """

    __slots__ = (
        "bid_id",
        "project_name",
        "region",
        "budget",
        "publish_date",
        "deadline",
        "category",
        "purchaser",
        "agency",
        "winner",
        "source_url",
        "requirements",
        "extras",
        "warnings",
    )

    def __init__(
        self,
        bid_id: str,
        project_name: str,
        *,
        region: Optional[str] = None,
        budget: Optional[float] = None,
        publish_date: Optional[str] = None,
        deadline: Optional[str] = None,
        category: Optional[str] = None,
        purchaser: Optional[str] = None,
        agency: Optional[str] = None,
        winner: Optional[str] = None,
        source_url: Optional[str] = None,
        requirements: Optional[List[str]] = None,
        extras: Optional[Dict[str, Any]] = None,
        warnings: Optional[List[str]] = None,
    ) -> None:
        self.bid_id = bid_id
        self.project_name = project_name
        self.region = region
        self.budget = budget
        self.publish_date = publish_date
        self.deadline = deadline
        self.category = category
        self.purchaser = purchaser
        self.agency = agency
        self.winner = winner
        self.source_url = source_url
        self.requirements = requirements or []
        self.extras = extras or {}
        self.warnings = warnings or []

    # ------------------------------------------------------------------
    # 构造：raw dict → 规范记录
    # ------------------------------------------------------------------

    @classmethod
    def from_raw(cls, raw: Dict[str, Any]) -> "AnnouncementRecord":
        """从异构来源字典构造规范化记录。

        Args:
            raw: 来源载荷字典（键可为中文别名或规范名）。

        Returns:
            规范化记录实例。

        Raises:
            RecordValidationError: ``bid_id`` / ``project_name`` 缺失或为空。
            TypeError: ``raw`` 不是字典时。
        """
        if not isinstance(raw, dict):
            raise TypeError(f"公告载荷须为字典，实际为 {type(raw).__name__}")

        canonical: Dict[str, Any] = {}
        extras: Dict[str, Any] = {}
        for key, value in raw.items():
            mapped = _FIELD_ALIASES.get(str(key).strip().lower())
            if mapped is None:
                # 大小写归一后再试一次（如 SourceURL / BUDGET）
                mapped = _FIELD_ALIASES.get(str(key).strip())
            if mapped is None:
                extras[str(key)] = value
            else:
                canonical[mapped] = value

        warnings: List[str] = []

        bid_id = _clean_text(canonical.get("bid_id"))
        if not bid_id:
            raise RecordValidationError(
                "bid_id", "缺少必填字段（或别名：招标编号/编号）"
            )
        project_name = _clean_text(canonical.get("project_name"))
        if not project_name:
            raise RecordValidationError(
                "project_name", "缺少必填字段（或别名：项目名称/项目）"
            )

        region = _clean_text(canonical.get("region")) or None

        budget_raw = canonical.get("budget")
        budget, warn = _normalize_budget(budget_raw)
        if warn:
            warnings.append(f"budget: {warn}（原值已置 None）")

        publish_date, p_warn = _normalize_date(canonical.get("publish_date"))
        if p_warn:
            warnings.append(f"publish_date: {p_warn}（原值已置 None）")
        deadline, d_warn = _normalize_date(canonical.get("deadline"))
        if d_warn:
            warnings.append(f"deadline: {d_warn}（原值已置 None）")

        requirements = _normalize_requirements(canonical.get("requirements"))

        return cls(
            bid_id=bid_id,
            project_name=project_name,
            region=region,
            budget=budget,
            publish_date=publish_date,
            deadline=deadline,
            category=_clean_text(canonical.get("category")) or None,
            purchaser=_clean_text(canonical.get("purchaser")) or None,
            agency=_clean_text(canonical.get("agency")) or None,
            winner=_clean_text(canonical.get("winner")) or None,
            source_url=_clean_text(canonical.get("source_url")) or None,
            requirements=requirements,
            extras=extras,
            warnings=warnings,
        )

    # ------------------------------------------------------------------
    # 导出
    # ------------------------------------------------------------------

    def to_bid_row(self) -> Dict[str, Any]:
        """转换为 ``BidDatabase.save_bid`` 兼容的行字典。

        Returns:
            含 ``bid_id`` / ``project_name`` 必填键与全部可选列的字典；
            ``requirements`` 为列表（save_bid 内部序列化为 JSON 文本）。
            :attr:`extras` 不导出（bids 表列固定，研究面保留于记录对象）。
        """
        return {
            "bid_id": self.bid_id,
            "project_name": self.project_name,
            "region": self.region,
            "budget": self.budget,
            "publish_date": self.publish_date,
            "deadline": self.deadline,
            "category": self.category,
            "purchaser": self.purchaser,
            "agency": self.agency,
            "winner": self.winner,
            "source_url": self.source_url,
            "requirements": list(self.requirements),
        }

    def fingerprint(self) -> str:
        """生成「标题+发布日期+地区」指纹（去重面用）。

        同一公告经不同来源收录（bid_id 拼写不一）时，指纹一致；
        标题/日期/地区任一实质变化则指纹变化。12 位十六进制。

        Returns:
            sha256 十六进制指纹（前 12 位）。
        """
        material = "|".join(
            (
                self.project_name.strip(),
                self.publish_date or "",
                (self.region or "").strip(),
            )
        )
        return hashlib.sha256(material.encode("utf-8")).hexdigest()[:12]
