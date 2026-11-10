"""供应商画像分析（非生产链路——仅供研究，见 docs/PYTHON-BOUNDARY.md）。

R47：按中标人聚合的描述性画像——谁在赢、赢了多少标、从谁手里
赢、在哪些领域赢。与采购人画像（buyers.py）对偶，全部为
**描述性统计**：

- ``winner`` 缺失（未定标/流标）的记录不参与聚合——「未定标」
  不是供应商的属性，混入即口径污染；
- 预算聚合只统计有值样本并携带样本数（缺失不折零）；
- 中标「金额」口径注意：库内 ``budget`` 是**项目预算**而非
  **中标合同额**，画像如实按预算口径呈现并在字段名上明示。
"""

from __future__ import annotations

from typing import Any, Dict, List

from src.analyze.dataset import AnalysisDataset


def supplier_profiles(
    dataset: AnalysisDataset, top_n: int = 5
) -> List[Dict[str, Any]]:
    """供应商画像 Top N（中标数降序，并列按名称排序——确定性）。

    Args:
        dataset: 分析数据集。
        top_n: 返回画像条数上限。

    Returns:
        画像列表（JSON 可序列化），每项含：

        - ``winner``：供应商名称（清洗后）；
        - ``award_count``：中标项目数；
        - ``budget_total`` / ``budget_mean``：所中项目预算合计/均值
          （仅统计有预算样本；全缺为 ``None``——预算≠合同额）；
        - ``budget_sample_count``：有预算样本数（口径可核对）；
        - ``purchasers``：买方（采购人）去重列表（出现序）；
        - ``purchaser_count``：买方数量；
        - ``categories``：类别去重（出现序）；
        - ``active_months``：中标项目的公告月份（``YYYY-MM``
          升序——注意是公告月非定标月，定标日期不在库内字段）。
    """
    groups: Dict[str, List[Dict[str, Any]]] = {}
    for record in dataset.records:
        winner = str(record.get("winner") or "").strip()
        if not winner:
            continue  # 未定标/流标不属于任何供应商
        groups.setdefault(winner, []).append(record)

    profiles: List[Dict[str, Any]] = []
    for winner, records in groups.items():
        budgets = [
            float(r["budget"])
            for r in records
            if r.get("budget") is not None
        ]
        purchasers: List[str] = []
        for record in records:
            purchaser = str(record.get("purchaser") or "").strip()
            if purchaser and purchaser not in purchasers:
                purchasers.append(purchaser)
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
                "winner": winner,
                "award_count": len(records),
                "budget_total": sum(budgets) if budgets else None,
                "budget_mean": (
                    sum(budgets) / len(budgets) if budgets else None
                ),
                "budget_sample_count": len(budgets),
                "purchasers": purchasers,
                "purchaser_count": len(purchasers),
                "categories": categories,
                "active_months": months,
            }
        )

    profiles.sort(key=lambda p: (-p["award_count"], p["winner"]))
    return profiles[:top_n]
