"""关键词频次分析（#601 批次 C 第 12 轮）。

双模式（零第三方依赖——研究工具链 CI 面不膨胀）：

1. **领域词表匹配**（keyword_frequency）：内置招标领域种子词表
   （可扩展），在项目名+资格要求文本上计数，并带**预算关联**
   （该关键词命中项目的预算合计/均值——研究面核心问题之一：
   「智慧城市这个领域总盘子多大」）；
2. **Bigram 发现模式**（common_bigrams）：字符二元组频次——
   找词表**没覆盖**的新领域词（发现面），带停用粒过滤
   （的/与/及等助词、项目/工程等泛词不构成领域信号）。

口径：大小写不敏感（英文型号如 GIS/CRM）；匹配按**子串包含**
（「智慧城市」命 中「智慧城市一期」），一词多项只计一次
（去重后计数——「智慧城市」出现 3 个不同项目 = count 3）。
"""

from __future__ import annotations

from collections import Counter
from typing import Dict, Iterable, List, Optional, Set

from src.analyze.dataset import AnalysisDataset

#: 领域种子词表（按需扩展——研究面口径，非完备词表）。
DEFAULT_LEXICON: tuple = (
    # 数字化/平台类
    "智慧城市", "智慧园区", "智慧交通", "智慧医疗", "智慧教育",
    "智慧水务", "智慧城管", "智慧农业",
    "政务云", "数据中心", "数字政府", "数字化转型", "城市大脑",
    "一体化平台", "大数据", "人工智能", "区块链", "物联网",
    # 行业面
    "安防", "校园", "医疗", "水利", "交通", "电力", "环保",
    "农业农村", "应急", "消防", "气象", "司法",
    # 工程类
    "改造", "扩建", "新建", "装修", "市政", "管网", "道路",
    # 服务类
    "运维", "咨询", "监理", "测绘", "审计", "评估", "规划",
    "系统集成", "软件开发", "信息化", "网络安全", "等保",
)

#: bigram 停用字符（助词/数字——含任一即弃）。
_STOP_CHARS = set("的与和及等对在为予以了把被从到上下一二三四五")

#: bigram 停用二元组（泛词——构成不了领域信号）。
_STOP_BIGRAMS = {
    "项目", "工程", "采购", "招标", "投标", "公告", "服务",
    "建设", "内容", "有关", "及其", "建设", "单位", "要求",
}


def _match_text(record: Dict) -> str:
    """取记录的匹配文本面：项目名 + 资格要求。"""
    parts: List[str] = []
    name = record.get("project_name")
    if name:
        parts.append(str(name))
    requirements = record.get("requirements")
    if isinstance(requirements, list):
        parts.extend(str(item) for item in requirements)
    elif requirements:
        parts.append(str(requirements))
    return " ".join(parts)


def keyword_frequency(
    dataset: AnalysisDataset,
    *,
    lexicon: Optional[Iterable[str]] = None,
    extra_terms: Optional[Iterable[str]] = None,
) -> Dict[str, Dict[str, Optional[float]]]:
    """领域词表频次 + 预算关联。

    Args:
        dataset: 分析数据集。
        lexicon: 完整替换词表（``None`` = 内置种子词表）。
        extra_terms: 追加词（与词表并集——常用扩展口）。

    Returns:
        ``{关键词: {"count", "budget_total", "budget_mean"}}``
        ——count 为命中项目数（一词一项只计一次）；
        预算关联只统计有预算的命中项；无预算命中则 None。
        只返回命中词（count ≥ 1），按 count 降序。
    """
    terms: Set[str] = set(lexicon if lexicon is not None else DEFAULT_LEXICON)
    if extra_terms:
        terms.update(extra_terms)

    hits: Dict[str, Dict[str, Optional[float]]] = {}
    for record in dataset.records:
        text = _match_text(record)
        if not text:
            continue
        haystack = text.lower()
        budget = record.get("budget")
        budget_value = (
            float(budget)
            if isinstance(budget, (int, float)) and not isinstance(budget, bool)
            else None
        )
        for term in terms:
            if term.lower() in haystack:
                slot = hits.setdefault(
                    term, {"count": 0, "budget_total": 0.0, "budget_known": 0}
                )
                slot["count"] += 1
                if budget_value is not None:
                    slot["budget_total"] += budget_value
                    slot["budget_known"] += 1

    result: Dict[str, Dict[str, Optional[float]]] = {}
    for term, slot in hits.items():
        known = slot["budget_known"]
        result[term] = {
            "count": slot["count"],
            "budget_total": slot["budget_total"] if known else None,
            "budget_mean": (
                slot["budget_total"] / known if known else None
            ),
        }
    return dict(
        sorted(result.items(), key=lambda kv: (-kv[1]["count"], kv[0]))
    )


def common_bigrams(
    dataset: AnalysisDataset, *, top: int = 20
) -> Dict[str, int]:
    """Bigram 发现模式（词表未覆盖新词的发现面）。

    Args:
        dataset: 分析数据集。
        top: 返回前 N 个高频 bigram。

    Returns:
        ``{bigram: 频次}``（降序）——已过滤助词/泛词；
        仅从项目名提取（公告正文太长会淹没信号）。
    """
    counter: Counter = Counter()
    for record in dataset.records:
        name = str(record.get("project_name") or "")
        for i in range(len(name) - 1):
            gram = name[i : i + 2]
            if gram in _STOP_BIGRAMS:
                continue
            if any(ch in _STOP_CHARS for ch in gram):
                continue
            counter[gram] += 1
    items = sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))
    return dict(items[:top])


def keyword_monthly_trend(
    dataset: AnalysisDataset,
    *,
    top_n: int = 5,
    lexicon: Optional[Iterable[str]] = None,
    extra_terms: Optional[Iterable[str]] = None,
) -> Dict[str, Dict[str, object]]:
    """领域词月度命中趋势（术语演化信号，R37）。

    Args:
        dataset: 分析数据集。
        top_n: 返回词数上限（总命中数降序，并列按词名——确定性）。
        lexicon: 完整替换词表（``None`` = 内置种子词表）。
        extra_terms: 追加词（与词表并集——常用扩展口）。

    Returns:
        ``{词: {"months": {YYYY-MM: 命中数}, "first_seen": 月,
        "last_seen": 月, "total": 总命中数}}``——按 total 降序；
        一词一项只计一次（同 :func:`keyword_frequency` 口径）；
        **无发布日期的记录不参与**（演化面需时间轴，口径明示）；
        无命中返回 ``{}``（不猜数）。
    """
    terms: Set[str] = set(lexicon if lexicon is not None else DEFAULT_LEXICON)
    if extra_terms:
        terms.update(extra_terms)

    monthly: Dict[str, Dict[str, int]] = {}
    for record in dataset.records:
        date_value = record.get("publish_date")
        if not date_value:
            continue  # 无日期不参与演化面
        month = str(date_value)[:7]
        text = _match_text(record)
        if not text:
            continue
        haystack = text.lower()
        for term in terms:
            if term.lower() in haystack:
                term_months = monthly.setdefault(term, {})
                term_months[month] = term_months.get(month, 0) + 1

    if not monthly:
        return {}

    ordered = sorted(
        monthly.items(),
        key=lambda kv: (-sum(kv[1].values()), kv[0]),
    )[:top_n]
    result: Dict[str, Dict[str, object]] = {}
    for term, months in ordered:
        sorted_months = dict(sorted(months.items()))
        result[term] = {
            "months": sorted_months,
            "first_seen": next(iter(sorted_months)),
            "last_seen": next(reversed(sorted_months)),
            "total": sum(months.values()),
        }
    return result
