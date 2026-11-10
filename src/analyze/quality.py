"""字段级数据质量评估（#601 批次 E 第 23 轮）。

记录级命中率（:mod:`src.extract.validator`）回答「这条记录好不好」；
**字段级**质量回答「管道系统性缺什么」——agency 只填 10% 说明
采集面/提示词要针对性加强，这不是单条记录的锅。

产出研究行动面：报告里的「数据质量」节直接告诉研究者
**下一步该补采什么**。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.analyze.dataset import AnalysisDataset
from src.extract.validator import ALL_FIELDS, is_filled


def field_quality(dataset: AnalysisDataset) -> Dict[str, Any]:
    """字段级填充率统计（系统性缺口面）。

    Args:
        dataset: 分析数据集。

    Returns:
        ``{"records": N, "fields": {字段: {"filled": n, "rate": r}},
        "overall": 平均填充率, "most_missing": [字段名…]}``
        ——``most_missing`` 按缺失率降序，前 5 个（研究行动面）。
    """
    count = len(dataset)
    if count == 0:
        return {
            "records": 0,
            "fields": {},
            "overall": None,
            "most_missing": [],
        }

    filled_counts: Dict[str, int] = {name: 0 for name in ALL_FIELDS}
    for record in dataset.records:
        for name in ALL_FIELDS:
            if is_filled(record.get(name)):
                filled_counts[name] += 1

    fields: Dict[str, Dict[str, Any]] = {}
    for name in ALL_FIELDS:
        fields[name] = {
            "filled": filled_counts[name],
            "rate": filled_counts[name] / count,
        }

    overall = sum(f["rate"] for f in fields.values()) / len(ALL_FIELDS)
    # 缺失行动面：填充率升序取前 5（rate < 1 才进清单）
    most_missing: List[str] = [
        name
        for name, _ in sorted(
            fields.items(), key=lambda kv: (kv[1]["rate"], kv[0])
        )
        if fields[name]["rate"] < 1.0
    ][:5]

    return {
        "records": count,
        "fields": fields,
        "overall": overall,
        "most_missing": most_missing,
    }


# ----------------------------------------------------------------------
# 语义质量（R81）：字段填上了，但值合不合逻辑？
# ----------------------------------------------------------------------

# 单位错位启发线（万元）：50 亿元以上单项目预算在政府采购里极罕见，
# 大概率是「元」被当「万元」导入（数值放大 1 万倍）。
_OVERSIZED_BUDGET_WAN = 500_000.0

# 招投标电子化分水岭：早于此的日期多为解析错位（年份截断/错位）。
_ANCIENT_CUTOVER = "2015-01-01"

# 每类问题的明细上限（报告可读性——全量计数照给，明细给前 5）
_ISSUE_DETAIL_LIMIT = 5


def _first_issue_key(record: Dict[str, Any]) -> str:
    """问题明细的定位键（bid_id 缺失时退化为名称摘要）。"""
    bid = record.get("bid_id")
    if bid:
        return str(bid)
    name = record.get("project_name") or ""
    return f"（无ID）{name[:20]}"


def semantic_health(dataset: AnalysisDataset, *, today: str = "") -> Dict[str, Any]:
    """数值/逻辑语义审计——填充率之外的第二道质量面。

    覆盖四类「填了但可疑」：

    1. **预算语义**：负数（绕过归一直导）、零预算、超大
       （>50 亿元——单位错位信号）；
    2. **日期逻辑**：发布晚于截止、未来发布（时钟/解析错）、
       远古发布（<2015——电子化前日期多为解析错位）；
    3. **标识完整性**：bid_id 缺失、project_name 缺失；
    4. **标识唯一性**：bid_id 重复（库层 UNIQUE 挡不住
       ``--import`` 拼接源或外部审计场景）。

    Args:
        dataset: 分析数据集。
        today: 「未来发布」判定的基准日（YYYY-MM-DD；缺省用
            数据集生成时刻——测试可注入固定值）。

    Returns:
        ``{"records": N, "issues": {类: {"count": n, "items": [...]}},
        "health_score": 0-100, "clean": bool}``——score 为加权
        问题率折算（100 = 全净），clean = 无任何问题。
    """
    from collections import Counter

    records = dataset.records
    total = len(records)
    base: Dict[str, Any] = {
        "records": total,
        "issues": {},
        "health_score": 100,
        "clean": True,
    }
    if total == 0:
        return base

    if not today:
        today = (dataset.generated_at or "")[:10]

    def _add(kind: str, record: Dict[str, Any], detail: str = "") -> None:
        slot = base["issues"].setdefault(
            kind, {"count": 0, "items": []}
        )
        slot["count"] += 1
        if len(slot["items"]) < _ISSUE_DETAIL_LIMIT:
            item = {"ref": _first_issue_key(record)}
            if detail:
                item["detail"] = detail
            slot["items"].append(item)

    id_counter: Counter = Counter()
    for r in records:
        bid = r.get("bid_id")
        if not bid or not str(bid).strip():
            _add("missing_bid_id", r)
        else:
            id_counter[str(bid)] += 1

        if not (r.get("project_name") or "").strip():
            _add("missing_project_name", r)

        budget = r.get("budget")
        if budget is not None:
            try:
                value = float(budget)
            except (TypeError, ValueError):
                _add("budget_invalid", r, f"非数值: {budget!r}")
            else:
                if value < 0:
                    _add("budget_negative", r, f"{value}")
                elif value == 0:
                    _add("budget_zero", r)
                elif value > _OVERSIZED_BUDGET_WAN:
                    _add("budget_oversized", r, f"{value:,.0f} 万（疑单位错位）")

        publish = (r.get("publish_date") or "")[:10]
        deadline = (r.get("deadline") or "")[:10]
        if publish and len(publish) == 10:
            if today and publish > today:
                _add("future_publish", r, publish)
            if publish < _ANCIENT_CUTOVER:
                _add("ancient_publish", r, publish)
            if deadline and len(deadline) == 10 and publish > deadline:
                _add("publish_after_deadline", r, f"{publish} > {deadline}")

    for bid, cnt in id_counter.items():
        if cnt > 1:
            slot = base["issues"].setdefault(
                "duplicate_bid_id", {"count": 0, "items": []}
            )
            slot["count"] += cnt - 1  # 重复份数（首份合法）
            if len(slot["items"]) < _ISSUE_DETAIL_LIMIT:
                slot["items"].append({"ref": bid, "detail": f"{cnt} 次"})

    # 健康分：类权重（标识 > 日期逻辑 > 预算语义）按问题记录占比扣减
    weights = {
        "missing_bid_id": 0.30,
        "duplicate_bid_id": 0.30,
        "missing_project_name": 0.20,
        "publish_after_deadline": 0.15,
        "future_publish": 0.10,
        "ancient_publish": 0.10,
        "budget_negative": 0.15,
        "budget_oversized": 0.15,
        "budget_invalid": 0.15,
        "budget_zero": 0.05,
    }
    penalty = 0.0
    for kind, slot in base["issues"].items():
        penalty += weights.get(kind, 0.10) * min(
            1.0, slot["count"] / total
        )
    base["health_score"] = max(0, round(100 * (1 - penalty)))
    base["clean"] = not base["issues"]
    return base


def render_semantic_health_markdown(
    payload: Dict[str, Any], *, ordinal: Optional[str] = None
) -> str:
    """语义质量节 Markdown（analyze 报告第十七节 / data-quality 命令复用）。"""
    title = (
        f"## {ordinal}、语义质量审计" if ordinal else "## 语义质量审计"
    )
    lines: List[str] = [title, ""]
    total = payload.get("records", 0)
    if total == 0:
        lines.append("数据集为空，无可审计内容。")
        return "\n".join(lines) + "\n"

    score = payload.get("health_score", 100)
    issues = payload.get("issues") or {}
    if not issues:
        lines.append(
            f"全库 {total} 条记录通过四类语义审计"
            "（预算/日期/标识完整/标识唯一）——无异常。"
        )
        return "\n".join(lines) + "\n"

    lines.append(
        f"健康分 **{score}/100**——"
        f"{len(issues)} 类问题（详见下表；明细前 5 条/类，"
        "全量计数见 count 列）。"
    )
    lines.append("")
    lines.append("| 问题类 | 条数 | 明细（前 5） |")
    lines.append("| --- | --- | --- |")
    kind_labels = {
        "missing_bid_id": "bid_id 缺失",
        "duplicate_bid_id": "bid_id 重复",
        "missing_project_name": "项目名缺失",
        "publish_after_deadline": "发布晚于截止",
        "future_publish": "未来发布日",
        "ancient_publish": "远古发布日（<2015）",
        "budget_negative": "预算为负",
        "budget_zero": "零预算",
        "budget_oversized": "预算超大（疑单位错位）",
        "budget_invalid": "预算非数值",
    }
    for kind in sorted(issues, key=lambda k: -issues[k]["count"]):
        slot = issues[kind]
        details = "；".join(
            it["ref"] + (f"（{it.get('detail')}）" if it.get("detail") else "")
            for it in slot["items"]
        )
        lines.append(
            f"| {kind_labels.get(kind, kind)} | {slot['count']} | {details} |"
        )
    lines.append("")
    lines.append(
        "> 预算超大阈值 50 亿元（万元口径）——超线多为「元」误作"
        "「万元」导入；远古/未来日期多为解析错位，建议回查源文件。"
    )
    return "\n".join(lines) + "\n"
