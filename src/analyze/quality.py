"""字段级数据质量评估（#601 批次 E 第 23 轮）。

记录级命中率（:mod:`src.extract.validator`）回答「这条记录好不好」；
**字段级**质量回答「管道系统性缺什么」——agency 只填 10% 说明
采集面/提示词要针对性加强，这不是单条记录的锅。

产出研究行动面：报告里的「数据质量」节直接告诉研究者
**下一步该补采什么**。
"""

from __future__ import annotations

from typing import Any, Dict, List

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
