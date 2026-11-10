"""领域对比面（#601 批次 F 第 28 轮）。

研究问题：「智慧城市 vs 政务云，哪边更值得投研究精力？」——
把多个领域的分析 payload 并排成对照表，指标差异一眼可见。
与单领域报告共用批次 C 的全部分析面，只是排版维度变化。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

from src.analyze.report_data import build_analysis_payload


def build_comparison_payload(
    db_path, keywords: Sequence[str], *, days: Optional[int] = None
) -> Dict[str, Any]:
    """构建多领域对照 payload。

    Args:
        db_path: 研究工作区路径（或已开 BidDatabase——走 load_dataset 双形态）。
        keywords: 领域关键词列表（2 个及以上）。
        days: 时间窗口（可空）。

    Returns:
        ``{"keywords": [...], "days": days, "generated_at": ...,
        "segments": {关键词: payload}}``。

    Raises:
        ValueError: keywords 少于 2 个或含空串。
    """
    from src.analyze.dataset import load_dataset

    cleaned = [k.strip() for k in keywords if k and k.strip()]
    if len(cleaned) < 2:
        raise ValueError(f"对比至少需要 2 个领域关键词，收到 {len(cleaned)} 个")
    if len(set(cleaned)) != len(cleaned):
        raise ValueError(f"对比关键词不得重复: {cleaned}")

    segments: Dict[str, Any] = {}
    generated_at = None
    for keyword in cleaned:
        dataset = load_dataset(db_path, keyword=keyword, days=days)
        payload = build_analysis_payload(dataset, keyword=keyword, days=days)
        generated_at = generated_at or payload["generated_at"]
        segments[keyword] = payload
    return {
        "keywords": cleaned,
        "days": days,
        "generated_at": generated_at,
        "segments": segments,
    }


#: 对照表指标行定义：(指标名, 取值函数(payload), 格式)。
_METRIC_ROWS: Tuple[Tuple[str, Any], ...] = (
    ("记录数", lambda p: p["record_count"], "int"),
    (
        "预算中位(万)",
        lambda p: p["budget"]["median"],
        "money",
    ),
    ("预算均值(万)", lambda p: p["budget"]["mean"], "money"),
    ("预算 P75(万)", lambda p: p["budget"]["p75"], "money"),
    (
        "发布密度(条/月)",
        lambda p: p["density"]["monthly_rate"],
        "rate1",
    ),
    ("密度层级", lambda p: p["density"]["density_level"], "text"),
    (
        "定标率",
        lambda p: p["density"]["award_rate"],
        "pct",
    ),
    (
        "采购集中度 top3",
        lambda p: p["density"]["purchaser_top3_share"],
        "pct",
    ),
    (
        "字段完整度",
        lambda p: p["complete_rate"],
        "pct",
    ),
)


def _fmt(value: Any, kind: str) -> str:
    """按指标类型格式化（None → ——不猜数）。"""
    if value is None:
        return "——"
    if kind == "money":
        return f"{value:,.1f}"
    if kind == "pct":
        return f"{value * 100:.1f}%"
    if kind == "rate1":
        return f"{value:.1f}"
    if kind == "int":
        return str(value)
    return str(value)


def render_comparison_markdown(payload: Dict[str, Any]) -> str:
    """把对照 payload 渲染为并排 Markdown 对照报告。

    Args:
        payload: :func:`build_comparison_payload` 产物。

    Returns:
        Markdown 文本（含对照表 + 各领域最缺字段 + 口径说明）。
    """
    keywords: List[str] = payload["keywords"]
    days = payload.get("days")
    lines: List[str] = [
        f"# 领域对照报告：{' vs '.join(keywords)}",
        "",
        f"- 时间窗口：{'近 ' + str(days) + ' 天' if days else '不限'}",
        f"- 生成时间：{payload.get('generated_at')}",
        "",
        "## 指标对照",
        "",
        "| 指标 | " + " | ".join(keywords) + " |",
        "|" + "|".join([" --- " for _ in range(len(keywords) + 1)]) + "|",
    ]
    for name, getter, kind in _METRIC_ROWS:
        cells = [
            _fmt(getter(payload["segments"][k]), kind) for k in keywords
        ]
        lines.append(f"| {name} | " + " | ".join(cells) + " |")

    lines += ["", "## 各领域最缺字段（补采行动面）", ""]
    for keyword in keywords:
        segment = payload["segments"][keyword]
        quality = segment.get("field_quality") or {}
        missing = quality.get("most_missing") or []
        lines.append(
            f"- **{keyword}**："
            + ("、".join(missing) if missing else "无明显系统性缺口")
        )

    lines += [
        "",
        "## 口径说明",
        "",
        "- 研究工具离线对照报告（PYTHON-BOUNDARY 非生产口径）。",
        "- 密度/集中度为启发式估算；预算单位统一万元。",
        "- 关键词过滤与 ``db --query`` 同口径（项目名/要求 LIKE 命中）。",
        "",
    ]
    return "\n".join(lines)
