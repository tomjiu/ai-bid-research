"""分析数据集加载器（#601 批次 C 第 10 轮）。

设计说明
--------
分析面只吃**一种**输入：从研究工作区（bids 表）读出的记录列表，
包装成 :class:`AnalysisDataset`（只读视图 + 派生访问器）：

- ``keyword`` / ``days`` 过滤与 ``db --query`` 同口径（研究复现性）；
- 派生访问器（:attr:`budgets` / :attr:`publish_dates` /
  :attr:`awarded_records`）给统计函数提供**已清洗**的序列——
  预算只取非空、日期已解析失败剔除，空数据集直接给空列表，
  统计函数不必重复做防御；
- ``complete_rate``（12 字段平均命中率）是**数据质量**指标：
  采集/抽取质量在分析面可见（低命中率的统计结论要打折看）。

不引第三方（pandas 等）：数据规模是研究级（万条以下），
标准库排序/分组足够，还避免 CI 依赖面膨胀。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from src.storage.database import BidDatabase


def _parse_date(value: Any) -> Optional[datetime]:
    """解析 YYYY-MM-DD 日期；失败返回 None（防御——入库前已归一）。"""
    if not value:
        return None
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d")
    except (ValueError, TypeError):
        return None


@dataclass
class AnalysisDataset:
    """分析数据集（研究记录的只读视图）。

    Attributes:
        records: bids 行字典列表（query_bids 产物形态）。
        keyword: 加载时使用的关键词过滤（``None`` = 全量）。
        days: 加载时使用的时间窗口（``None`` = 不限）。
        generated_at: 数据集生成时刻（ISO 字符串——报告可追溯）。
    """

    records: List[Dict[str, Any]] = field(default_factory=list)
    keyword: Optional[str] = None
    days: Optional[int] = None
    generated_at: str = field(
        default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )

    # ------------------------------------------------------------------
    # 基本视图
    # ------------------------------------------------------------------

    def __len__(self) -> int:
        """记录条数。"""
        return len(self.records)

    @property
    def is_empty(self) -> bool:
        """数据集是否为空（空集统计无意义，调用方应提示）。"""
        return not self.records

    @property
    def awarded_records(self) -> List[Dict[str, Any]]:
        """已定中标人的记录（竞争结果面）。"""
        return [
            r
            for r in self.records
            if r.get("winner") and str(r.get("winner")).strip()
        ]

    @property
    def award_rate(self) -> Optional[float]:
        """开标率：已定标比例；空数据集为 None。"""
        if self.is_empty:
            return None
        return len(self.awarded_records) / len(self.records)

    @property
    def budgets(self) -> List[float]:
        """非空预算序列（万元）。"""
        values = []
        for record in self.records:
            budget = record.get("budget")
            if isinstance(budget, (int, float)) and not isinstance(budget, bool):
                values.append(float(budget))
        return values

    @property
    def publish_dates(self) -> List[datetime]:
        """可解析的发布日期序列（升序去 None）。"""
        dates = [
            d
            for d in (_parse_date(r.get("publish_date")) for r in self.records)
            if d is not None
        ]
        return sorted(dates)

    @property
    def complete_rate(self) -> Optional[float]:
        """平均字段命中率（12 规范字段口径，数据质量指标）。"""
        if self.is_empty:
            return None
        from src.extract.validator import validate_fields

        total = sum(validate_fields(r).hit_rate for r in self.records)
        return total / len(self.records)


def load_dataset(
    db_or_path: Union[BidDatabase, str, Path],
    *,
    keyword: Optional[str] = None,
    days: Optional[int] = None,
    limit: int = 1000,
) -> AnalysisDataset:
    """从研究工作区加载分析数据集。

    Args:
        db_or_path: 已打开的 :class:`BidDatabase` 或数据库路径。
        keyword: 关键词过滤（与 ``db --query`` 同口径）。
        days: 时间窗口（天）。
        limit: 记录上限（默认 1000——研究面防呆，防误全表百万级扫描）。

    Returns:
        分析数据集（可能为空——调用方按 ``is_empty`` 分支）。
    """
    if isinstance(db_or_path, BidDatabase):
        rows = db_or_path.query_bids(keyword=keyword, days=days, limit=limit)
        return AnalysisDataset(records=rows, keyword=keyword, days=days)

    path = Path(db_or_path)
    if not path.exists():
        # 路径不存在 → 空数据集（分析面不替调用方决定报错形态）
        return AnalysisDataset(records=[], keyword=keyword, days=days)
    with BidDatabase(path) as db:
        rows = db.query_bids(keyword=keyword, days=days, limit=limit)
    return AnalysisDataset(records=rows, keyword=keyword, days=days)
