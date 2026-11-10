"""采购人画像分析（非生产链路——仅供研究，见 docs/PYTHON-BOUNDARY.md）。

R35：按采购人聚合的描述性画像——谁在买、买多少、买什么领域、
何时活跃。全部为**描述性统计**（无启发式分层、不猜数）：
``purchaser`` 缺失的记录不参与聚合；预算聚合只统计有值样本并在
画像中如实携带样本数（缺失不折零）。
"""

from __future__ import annotations

from typing import Any, Dict, List

from src.analyze.dataset import AnalysisDataset


def buyer_profiles(
    dataset: AnalysisDataset, top_n: int = 5
) -> List[Dict[str, Any]]:
    """采购人画像 Top N（项目数降序，并列按名称排序——确定性）。

    Args:
        dataset: 分析数据集。
        top_n: 返回画像条数上限。

    Returns:
        画像列表（JSON 可序列化），每项含：

        - ``purchaser``：采购人名称（清洗后）；
        - ``project_count``：项目数；
        - ``budget_total`` / ``budget_mean``：预算合计/均值
          （**仅统计有预算样本**；全缺为 ``None``，不折零）；
        - ``budget_sample_count``：有预算的样本数（口径可核对）；
        - ``categories``：类别去重（保持出现序）；
        - ``active_months``：活跃月份（``YYYY-MM`` 去重升序）；
        - ``awarded_count``：已定标记录数（winner 非空）。
    """
    groups: Dict[str, List[Dict[str, Any]]] = {}
    for record in dataset.records:
        purchaser = str(record.get("purchaser") or "").strip()
        if not purchaser:
            continue  # 缺采购人不猜数
        groups.setdefault(purchaser, []).append(record)

    profiles: List[Dict[str, Any]] = []
    for purchaser, records in groups.items():
        budgets = [
            float(r["budget"])
            for r in records
            if r.get("budget") is not None
        ]
        categories: List[str] = []
        for record in records:
            category = str(record.get("category") or "").strip()
            if category and category not in categories:
                categories.append(category)
        months = sorted(
            {
                str(record.get("publish_date"))[:7]
                for record in records
                if record.get("publish_date")
            }
        )
        profiles.append(
            {
                "purchaser": purchaser,
                "project_count": len(records),
                "budget_total": sum(budgets) if budgets else None,
                "budget_mean": (
                    sum(budgets) / len(budgets) if budgets else None
                ),
                "budget_sample_count": len(budgets),
                "categories": categories,
                "active_months": months,
                "awarded_count": sum(
                    1
                    for record in records
                    if str(record.get("winner") or "").strip()
                ),
            }
        )

    profiles.sort(key=lambda profile: (-profile["project_count"], profile["purchaser"]))
    return profiles[:top_n]
