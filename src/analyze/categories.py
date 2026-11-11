"""品类分布分析（非生产链路——仅供研究，见 docs/PYTHON-BOUNDARY.md）。

R97：``category`` 字段首次进分析面——公告品类构成、各品类预算
规模与定标情况。``category`` 是抽取面（LLM 补全）产出的**自由
文本**，本节只做首尾空白清洗后的**精确匹配**归并——不做词表
归一（「信息化」与「信息技术」是否同义应由研究者判断，研究面
不臆造映射）；全部为**描述性统计**：缺失不折零、预算只计有值
样本并如实携带样本数。
"""

from __future__ import annotations

from typing import Any, Dict, List

from src.analyze.dataset import AnalysisDataset


def category_distribution(
    dataset: AnalysisDataset, top_n: int = 10
) -> Dict[str, Any]:
    """品类分布（清洗后精确匹配归并，计数降序）。

    Args:
        dataset: 分析数据集。
        top_n: 返回品类条数上限（``distinct_count`` 不受限——
            总类别数如实携带）。

    Returns:
        JSON 可序列化的分布字典：

        - ``filled_count`` / ``filled_rate`` / ``missing_count``：
          有品类 / 占比 / 缺失（三数口径可核对：filled+missing
          = 总记录数）；
        - ``distinct_count``：去重品类总数（截断前）；
        - ``categories``：Top N 品类（计数降序、并列按名——确定性），
          每项含品类名/项目数/预算合计/均值（**有值样本口径**，
          全缺为 ``None``）/预算样本数/定标数。
    """
    groups: Dict[str, List[Dict[str, Any]]] = {}
    missing = 0
    for record in dataset.records:
        category = str(record.get("category") or "").strip()
        if not category:
            missing += 1
            continue  # 缺品类不猜数
        groups.setdefault(category, []).append(record)

    filled = sum(len(rows) for rows in groups.values())
    entries: List[Dict[str, Any]] = []
    for category, records in groups.items():
        budgets = [
            float(r["budget"])
            for r in records
            if r.get("budget") is not None
        ]
        entries.append(
            {
                "category": category,
                "count": len(records),
                "budget_total": sum(budgets) if budgets else None,
                "budget_mean": (
                    sum(budgets) / len(budgets) if budgets else None
                ),
                "budget_sample_count": len(budgets),
                "awarded_count": sum(
                    1
                    for record in records
                    if str(record.get("winner") or "").strip()
                ),
            }
        )

    entries.sort(key=lambda entry: (-entry["count"], entry["category"]))
    return {
        "filled_count": filled,
        "filled_rate": (filled / len(dataset)) if len(dataset) else None,
        "missing_count": missing,
        "distinct_count": len(entries),
        "categories": entries[:top_n],
    }
