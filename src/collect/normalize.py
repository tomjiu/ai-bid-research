"""字段归一化公共函数（采集/抽取面共用）。

从 ``records.py`` 提升为公共模块（#601 批次 B）——抽取面
（LLM 输出的字段校验/归一）与采集面共用同一套清洗口径，
避免两处各自实现导致入库形态漂移。
"""

from __future__ import annotations

import re
from typing import Any, List, Optional, Tuple

#: 日期归一可接受形态：``2026-11-09`` / ``2026/11/9`` / ``2026.11.9`` /
#: ``2026年11月9日`` / ``2026-11-09 14:30[:00]``（取日期面）。
_DATE_PATTERNS = (
    re.compile(r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})"),
    re.compile(r"(\d{4})年(\d{1,2})月(\d{1,2})日"),
)

#: requirements 切分符（全角/半角分号与换行）。
_REQ_SPLIT_RE = re.compile(r"[;；\n]+")

#: 金额归一各形态正则（去千分位后匹配）。
_BUDGET_RE = re.compile(r"(\d+(?:\.\d+)?)[亿万]?元?")


def clean_text(value: Any) -> str:
    """文本清洗：None→空串；折叠内部空白并去首尾空白。

    Args:
        value: 原始值（任意类型，None/非字符串都容忍）。

    Returns:
        清洗后的字符串。
    """
    if value is None:
        return ""
    text = str(value)
    return re.sub(r"\s+", " ", text).strip()


def normalize_budget(value: Any) -> Tuple[Optional[float], Optional[str]]:
    """金额归一为万元（float）。

    接受形态::

        350 / 350.5            → 数值型，单位约定为万元
        "350" / "350.5"        → 数值字符串，单位约定为万元
        "350万" / "350万元"     → 万元
        "3,500,000元" / "3500000元" → 元 → ÷10000 归一为万元
        "1.2亿" / "1.2亿元"     → 亿元 → ×10000 归一为万元
        None / "" / "面议" / 其他不可解析 → (None, 告警)

    Args:
        value: 原始金额（数字或字符串）。

    Returns:
        (万元数值或 None, 告警消息或 None) 二元组。
    """
    if value is None:
        return None, None
    if isinstance(value, bool):
        return None, f"不可解析的金额类型: {type(value).__name__}"
    if isinstance(value, (int, float)):
        result = float(value)
        return (result, None) if result >= 0 else (None, f"金额为负: {result}")

    text = str(value).strip()
    if not text:
        return None, None

    # 去千分位逗号
    plain = text.replace(",", "").replace("，", "")

    match = _BUDGET_RE.fullmatch(plain)
    if not match:
        return None, f"金额无法解析: {text!r}"

    number = float(match.group(1))
    if "亿" in plain:
        number *= 10000.0
    elif "万" not in plain and plain.endswith("元"):
        number /= 10000.0
    if number < 0:
        return None, f"金额为负: {text!r}"
    return number, None


def normalize_date(value: Any) -> Tuple[Optional[str], Optional[str]]:
    """日期归一为 ``YYYY-MM-DD``。

    Args:
        value: 原始日期（字符串或 None）。

    Returns:
        (归一日期字符串或 None, 告警消息或 None) 二元组。
        空值→(None, None)（日期本就可缺）；非空但不可解析→告警。
    """
    if value is None:
        return None, None
    text = str(value).strip()
    if not text:
        return None, None
    for pattern in _DATE_PATTERNS:
        match = pattern.search(text)
        if match:
            year, month, day = (int(g) for g in match.groups())
            try:
                normalized = f"{year:04d}-{month:02d}-{day:02d}"
            except (ValueError, TypeError):
                return None, f"日期超出范围: {text!r}"
            if not (1 <= month <= 12 and 1 <= day <= 31):
                return None, f"日期月/日非法: {text!r}"
            return normalized, None
    return None, f"日期无法解析: {text!r}"


def normalize_requirements(value: Any) -> List[str]:
    """requirements 归一为字符串列表。

    - 列表 → 逐条清洗，去空项；
    - 字符串 → 按分号/换行切分；
    - None → 空列表；
    - 其他类型 → 单元素列表（str() 归一）。
    """
    if value is None:
        return []
    if isinstance(value, list):
        return [
            item.strip() for item in (str(v) for v in value) if item.strip()
        ]
    if isinstance(value, str):
        return [part.strip() for part in _REQ_SPLIT_RE.split(value) if part.strip()]
    return [str(value).strip()] if str(value).strip() else []
