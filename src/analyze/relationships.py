"""采购人-供应商合作关系（非生产链路——仅供研究）。

R53：同一「采购人 × 供应商」对的**重复中标**——研究面关心的
信号（合作粘性/复购关系），全部描述性统计：

- 只统计重复对（≥ ``min_repeat`` 次，缺省 2——单次合作无
  「重复」语义）；
- 预算为项目预算口径（库内无合同额），有值样本单独计数；
- 双侧名称缺失任一即跳过（关系需要两端都在）。
"""

from __future__ import annotations

from typing import Any, Dict, List

from src.analyze.dataset import AnalysisDataset


def purchaser_supplier_pairs(
    dataset: AnalysisDataset,
    *,
    top_n: int = 10,
    min_repeat: int = 2,
) -> List[Dict[str, Any]]:
    """重复合作的采购人-供应商对 Top N（重复数降序，并列按对名）。

    Returns:
        条目列表，每项含：

        - ``purchaser`` / ``winner``：对的两端（清洗后名称）；
        - ``repeat_count``：该对合作次数（双方都在的记录数）；
        - ``budget_total`` / ``budget_sample_count``：所涉项目预算
          合计与有值样本数（缺失不折零）；
        - ``months``：合作月份去重升序（公告月口径）。
    """
    groups: Dict[tuple, List[Dict[str, Any]]] = {}
    for record in dataset.records:
        purchaser = str(record.get("purchaser") or "").strip()
        winner = str(record.get("winner") or "").strip()
        if not purchaser or not winner:
            continue  # 关系两端必须都在
        groups.setdefault((purchaser, winner), []).append(record)

    entries: List[Dict[str, Any]] = []
    for (purchaser, winner), records in groups.items():
        if len(records) < min_repeat:
            continue
        budgets = [
            float(r["budget"])
            for r in records
            if r.get("budget") is not None
        ]
        months = sorted(
            {
                str(r.get("publish_date"))[:7]
                for r in records
                if r.get("publish_date")
            }
        )
        entries.append(
            {
                "purchaser": purchaser,
                "winner": winner,
                "repeat_count": len(records),
                "budget_total": sum(budgets) if budgets else None,
                "budget_sample_count": len(budgets),
                "months": months,
            }
        )

    entries.sort(
        key=lambda e: (-e["repeat_count"], e["purchaser"], e["winner"])
    )
    return entries[:top_n]
