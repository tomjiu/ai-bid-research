"""抽取质量评估面（#601 批次 E·R22）——字段命中率。

把抽取器（规则基线 / LLM / 桩）在**带 gold 标注的语料**上跑一遍，
逐字段比对命中情况，产出：

* 每用例的逐字段命中明细（expected / actual / hit）；
* 每字段的命中率（hits/total——分母只计 gold 中**标注了该字段**的用例，
  未标注不算未命中——诚实分母）；
* 总体命中率（全部标注字段的命中占比）与抽取失败用例数。

匹配语义（按字段类型）：

* ``bid_id`` / ``category`` / 日期字段：归一后**全等**；
* ``budget``：万元口径 float 全等（gold 直接标万元数值）；
* ``project_name`` / ``region`` / ``purchaser`` / ``agency``：**包含**
  （gold 标关键词，抽取值可能带前后缀——研究面关注是否抽到了主体）；
* ``requirements``：gold 每个关键词都应在抽取列表的某一条中出现
  （包含-任一）。

gold 标注形态（``fixtures/announcements/gold-extraction.json``）::

    {
      "file.txt": {"ok": true, "fields": {"bid_id": "X-1", ...}},
      "noise.txt": {"ok": false, "fields": {}}   // 预期抽取失败
    }
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.extract.engine import AnnouncementExtractor, extract_record

#: 包含语义匹配的字段（gold 标关键词）。
_CONTAINS_FIELDS = frozenset(
    {"project_name", "region", "purchaser", "agency"}
)


@dataclass
class FieldEvaluation:
    """单字段比对结果。

    Attributes:
        field: 字段名。
        expected: gold 标注值。
        actual: 抽取实际值（规范化后）。
        hit: 是否命中。
    """

    field: str
    expected: Any
    actual: Any
    hit: bool


@dataclass
class CaseEvaluation:
    """单用例评估结果。

    Attributes:
        name: 用例名（gold 键，通常为文件名）。
        expected_ok: gold 是否预期抽取成功。
        actual_ok: 实际抽取是否成功。
        fields: 逐字段比对明细。
    """

    name: str
    expected_ok: bool
    actual_ok: bool
    fields: List[FieldEvaluation] = field(default_factory=list)

    @property
    def verdict_ok(self) -> bool:
        """用例级判定：成功/失败预期一致且全部标注字段命中。"""
        if self.expected_ok != self.actual_ok:
            return False
        return all(f.hit for f in self.fields)

    @property
    def hit_count(self) -> int:
        """命中的标注字段数。"""
        return sum(1 for f in self.fields if f.hit)


@dataclass
class EvalReport:
    """评估报告。

    Attributes:
        cases: 逐用例结果（gold 键序）。
        extractor_mode: 引擎模式名。
    """

    cases: List[CaseEvaluation] = field(default_factory=list)
    extractor_mode: str = "rule"

    @property
    def total_fields(self) -> int:
        """gold 标注字段总数（分母——未标注字段不计）。"""
        return sum(len(case.fields) for case in self.cases)

    @property
    def hit_fields(self) -> int:
        """命中的标注字段数。"""
        return sum(case.hit_count for case in self.cases)

    @property
    def overall_hit_rate(self) -> Optional[float]:
        """总体字段命中率（0-1；零标注为 ``None``）。"""
        if self.total_fields == 0:
            return None
        return self.hit_fields / self.total_fields

    @property
    def failure_mismatches(self) -> List[CaseEvaluation]:
        """成功/失败预期不一致的用例。"""
        return [
            case
            for case in self.cases
            if case.expected_ok != case.actual_ok
        ]

    def field_hit_rates(self) -> Dict[str, Dict[str, int]]:
        """每字段命中率（分母 = 标注了该字段的用例数）。"""
        stats: Dict[str, Dict[str, int]] = {}
        for case in self.cases:
            for fe in case.fields:
                bucket = stats.setdefault(
                    fe.field, {"hits": 0, "total": 0}
                )
                bucket["total"] += 1
                if fe.hit:
                    bucket["hits"] += 1
        return stats

    def format_summary(self) -> str:
        """人读摘要（CLI / 日志）。"""
        rate = self.overall_hit_rate
        rate_text = f"{rate * 100:.1f}%" if rate is not None else "—"
        lines = [
            f"抽取质量评估（{self.extractor_mode}）："
            f"字段命中率 {rate_text}"
            f"（{self.hit_fields}/{self.total_fields}）"
        ]
        for fname, bucket in sorted(self.field_hit_rates().items()):
            lines.append(
                f"  {fname}: {bucket['hits']}/{bucket['total']}"
            )
        mismatches = self.failure_mismatches
        if mismatches:
            lines.append(
                f"  成功/失败预期不一致："
                f"{', '.join(c.name for c in mismatches)}"
            )
        return "\n".join(lines)


# ----------------------------------------------------------------------
# 比对语义
# ----------------------------------------------------------------------


def _field_matches(field_name: str, expected: Any, actual: Any) -> bool:
    """按字段语义比对 gold 与抽取值。

    Args:
        field_name: 字段名。
        expected: gold 标注值。
        actual: 抽取实际值（规范化后）。

    Returns:
        是否命中。
    """
    if expected is None:
        return actual is None
    if actual is None:
        return False
    if field_name in _CONTAINS_FIELDS:
        return str(expected) in str(actual)
    if field_name == "budget":
        try:
            return float(expected) == float(actual)
        except (TypeError, ValueError):
            return False
    if field_name == "requirements":
        # gold 每个关键词都应出现在抽取列表的某一条中
        if not isinstance(expected, list):
            expected = [expected]
        actual_list = actual if isinstance(actual, list) else [actual]
        return all(
            any(str(keyword) in str(item) for item in actual_list)
            for keyword in expected
        )
    # bid_id / category / 日期：全等（剥空白）
    return str(expected).strip() == str(actual).strip()


# ----------------------------------------------------------------------
# 评估入口
# ----------------------------------------------------------------------


def load_gold(gold_path: Path) -> Dict[str, Dict[str, Any]]:
    """读取 gold 标注文件。

    Args:
        gold_path: gold JSON 路径。

    Returns:
        ``{用例名: {"ok": bool, "fields": {...}}}``。

    Raises:
        ValueError: JSON 损坏或形态非法。
    """
    data = json.loads(gold_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"gold 标注必须是对象: {gold_path}")
    for name, case in data.items():
        if not isinstance(case, dict) or "ok" not in case:
            raise ValueError(
                f"gold 用例 {name!r} 缺 'ok' 键或形态非法"
            )
    return data


def evaluate_extractor(
    extractor: AnnouncementExtractor,
    gold: Dict[str, Dict[str, Any]],
    texts: Dict[str, str],
) -> EvalReport:
    """在 gold 语料上评估抽取器。

    Args:
        extractor: 抽取引擎（rule / api / 桩）。
        gold: gold 标注（``load_gold`` 产物）。
        texts: 用例名 → 公告原文（键应覆盖 gold 的键）。

    Returns:
        评估报告。
    """
    report = EvalReport(extractor_mode=getattr(extractor, "mode", "unknown"))
    for name, annotation in gold.items():
        text = texts.get(name)
        if text is None:
            # 语料缺失：登记为空用例（actual_ok=False——无法评估）
            report.cases.append(
                CaseEvaluation(
                    name=name,
                    expected_ok=bool(annotation.get("ok")),
                    actual_ok=False,
                    fields=[],
                )
            )
            continue
        outcome = extract_record(text, extractor)
        case = CaseEvaluation(
            name=name,
            expected_ok=bool(annotation.get("ok")),
            actual_ok=outcome.ok,
        )
        if outcome.ok:
            for field_name, expected in (annotation.get("fields") or {}).items():
                actual = getattr(outcome.record, field_name, None)
                case.fields.append(
                    FieldEvaluation(
                        field=field_name,
                        expected=expected,
                        actual=actual,
                        hit=_field_matches(field_name, expected, actual),
                    )
                )
        report.cases.append(case)
    return report
