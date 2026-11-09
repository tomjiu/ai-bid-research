"""公告记录健全性规则（非生产链路——仅供研究，见 docs/PYTHON-BOUNDARY.md）。

R33：跨字段健全性检查——**告警不拒收**（区别于必填校验的拒收面）。
研究数据质量信号：可疑记录带告警入库（``AnnouncementRecord.warnings``），
CLI / 报告面可见，供人工复核排序。

规则全部为**启发式口径**：命中 ≠ 错误（日期倒挂可能是补遗更正，
零预算可能是真面议）——研究面宁可多提示、不冒充判定。
"""

from __future__ import annotations

from datetime import date as _date, datetime
from typing import List, Optional, Union

from src.collect.records import AnnouncementRecord

#: 投标窗口（发布→截止）超过该天数视为可疑长周期（研究经验值）。
MAX_WINDOW_DAYS = 365


def _as_date(value: Optional[str]) -> Optional[_date]:
    """``YYYY-MM-DD`` 字符串 → date（None/不可解析 → None）。"""
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def _resolve_today(
    today: Union[None, str, _date],
) -> Optional[_date]:
    """解析 today 注入值（None → 系统当前日期；str 严格解析）。"""
    if today is None:
        return _date.today()
    if isinstance(today, str):
        parsed = _as_date(today)
        if parsed is None:
            raise ValueError(f"today 须为 YYYY-MM-DD 或 date，实际为 {today!r}")
        return parsed
    return today


def sanity_warnings(
    record: AnnouncementRecord,
    *,
    today: Union[None, str, _date] = None,
) -> List[str]:
    """对规范化记录做跨字段健全性检查（纯函数，不修改记录）。

    规则（全部启发式，告警不拒收）：

    1. **日期倒挂**：``publish_date`` 晚于 ``deadline``（大概率录入错误，
       也可能是补遗更正——告警供复核）；
    2. **可疑长周期**：投标窗口（发布→截止）超过 :data:`MAX_WINDOW_DAYS`
       天；
    3. **未来发布**：``publish_date`` 晚于 today（日期口径可疑——
       源站补录/时区错位常见）；
    4. **零预算**：``budget == 0``（万元 0——疑似未填或口径错误）。

    Args:
        record: 已规范化记录。
        today: 「今天」基准（``date`` / ``YYYY-MM-DD`` 字符串 /
            ``None``=系统当前日期）——注入以保证测试确定性。

    Returns:
        告警消息列表（空列表 = 全部规则未命中）。

    Raises:
        ValueError: ``today`` 为字符串但不可解析。
    """
    warnings: List[str] = []

    publish = _as_date(record.publish_date)
    deadline = _as_date(record.deadline)
    if publish is not None and deadline is not None:
        if publish > deadline:
            warnings.append(
                f"日期倒挂：发布 {record.publish_date}"
                f" 晚于截止 {record.deadline}"
            )
        elif (deadline - publish).days > MAX_WINDOW_DAYS:
            warnings.append(
                f"投标周期 {(deadline - publish).days} 天"
                f" 超过 {MAX_WINDOW_DAYS} 天（可疑长周期）"
            )

    base = _resolve_today(today)
    if publish is not None and base is not None and publish > base:
        warnings.append(
            f"发布日期在未来：{record.publish_date} 晚于 {base.isoformat()}"
        )

    if record.budget == 0:
        warnings.append("预算为 0（疑似未填/口径错误，单位万元）")

    return warnings


def apply_sanity_checks(
    record: AnnouncementRecord,
    *,
    today: Union[None, str, _date] = None,
) -> List[str]:
    """执行健全性检查并把告警并入 ``record.warnings``。

    Args:
        record: 已规范化记录（就地扩展 warnings）。
        today: 同 :func:`sanity_warnings`。

    Returns:
        新增的告警列表（未命中为空列表）。
    """
    new_warnings = sanity_warnings(record, today=today)
    if new_warnings:
        record.warnings.extend(new_warnings)
    return new_warnings
