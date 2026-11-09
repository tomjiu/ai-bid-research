"""分析数据集（#601 批次 C·R10）——db → 记录列表 + 过滤面。

设计纪律（#601 任务书「数据集加载（db → 记录列表，纯标准库）」）：

* **纯标准库**——不引 LLM/网络/第三方依赖，离线可测；
* **口径显式**——每条记录都是 ``BidDatabase`` 行字典（``requirements``
  已反序列化为列表）；统计面对 ``None`` 字段的处理逐项声明，不静默；
* **过滤在内存**——数据集规模是研究工作区量级（千条级），
  ``iter_all`` 分块拉全量后内存过滤，避免 SQL 条件与分析口径分裂。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, Dict, Iterable, List, Optional

from src.storage.database import BidDatabase

#: 项目名称检索的默认关键词表（关键词频次统计用，见 stats.py）。
DEFAULT_DOMAIN_KEYWORDS: tuple = (
    "智慧城市",
    "政务云",
    "数据中心",
    "网络安全",
    "安防",
    "运维",
    "信息化",
    "数字化",
    "平台",
    "系统",
    "设备",
    "软件",
    "服务",
    "工程",
    "咨询",
    "监理",
)


def load_dataset(
    db: BidDatabase,
    *,
    keyword: Optional[str] = None,
    days: Optional[int] = None,
    region: Optional[str] = None,
) -> BidDataset:
    """从数据库装载分析数据集（可带过滤条件）。

    Args:
        db: 已打开的数据库。
        keyword: 项目名/编号包含关键词（大小写不敏感）。
        days: 只保留近 N 天（基于 ``publish_date``）发布的记录。
        region: 地区包含匹配（如 ``杭州`` 命中 ``浙江省杭州市``）。

    Returns:
        过滤后的数据集。
    """
    records = list(db.iter_all())
    return BidDataset(
        filter_records(records, keyword=keyword, days=days, region=region)
    )


def filter_records(
    records: Iterable[Dict[str, Any]],
    *,
    keyword: Optional[str] = None,
    days: Optional[int] = None,
    region: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """内存过滤记录列表（三个维度正交可叠加）。

    Args:
        records: 记录字典迭代器。
        keyword: 项目名/编号子串匹配（大小写不敏感；空串不过滤）。
        days: 近 N 天窗口（``publish_date`` 为空或无法解析的记录
            **不保留**——时间窗内的结论不能混入无日期样本）。
        region: 地区子串匹配。

    Returns:
        过滤后的记录列表（保持原顺序）。
    """
    result: List[Dict[str, Any]] = []
    cutoff = (
        (date.today() - timedelta(days=days)).isoformat() if days else None
    )
    for record in records:
        if keyword:
            hay = f"{record.get('project_name') or ''} {record.get('bid_id') or ''}"
            if keyword.lower() not in hay.lower():
                continue
        if cutoff is not None:
            publish = record.get("publish_date") or ""
            if not publish or publish < cutoff:
                continue
        if region:
            if region not in (record.get("region") or ""):
                continue
        result.append(record)
    return result


@dataclass
class BidDataset:
    """分析数据集：记录列表 + 便捷视图。

    Attributes:
        records: 记录字典列表（ bids 表行形态）。
    """

    records: List[Dict[str, Any]] = field(default_factory=list)

    # ------------------------------------------------------------------
    # 计数视图
    # ------------------------------------------------------------------

    @property
    def total(self) -> int:
        """记录总数。"""
        return len(self.records)

    @property
    def awarded(self) -> int:
        """已定中标人的记录数（``winner`` 非空）。"""
        return sum(
            1
            for r in self.records
            if r.get("winner")
        )

    @property
    def award_rate(self) -> Optional[float]:
        """中标率（awarded/total；空集为 ``None``）。"""
        if not self.records:
            return None
        return self.awarded / self.total

    @property
    def with_budget(self) -> int:
        """预算金额非空的记录数。"""
        return sum(1 for r in self.records if r.get("budget") is not None)

    @property
    def with_date(self) -> int:
        """发布日期非空的记录数。"""
        return sum(1 for r in self.records if r.get("publish_date"))

    # ------------------------------------------------------------------
    # 值视图
    # ------------------------------------------------------------------

    @property
    def budget_values(self) -> List[float]:
        """预算金额列表（万元；仅非空样本，保持记录顺序）。"""
        return [
            float(r["budget"]) for r in self.records if r.get("budget") is not None
        ]

    @property
    def budget_total(self) -> float:
        """预算总额（万元；空样本集为 0）。"""
        return sum(self.budget_values)

    def winners(self) -> List[str]:
        """中标人列表（去重保持首次出现顺序）。"""
        seen: Dict[str, None] = {}
        for r in self.records:
            winner = r.get("winner")
            if winner:
                seen.setdefault(winner, None)
        return list(seen)

    def months(self) -> List[str]:
        """发布月份键列表（``YYYY-MM``，升序去重）。"""
        seen = {
            (r.get("publish_date") or "")[:7]
            for r in self.records
            if r.get("publish_date")
        }
        return sorted(m for m in seen if len(m) == 7)

    def regions(self) -> List[str]:
        """地区列表（去重保持首次出现顺序；空地区不计）。"""
        seen: Dict[str, None] = {}
        for r in self.records:
            region = r.get("region")
            if region:
                seen.setdefault(region, None)
        return list(seen)
