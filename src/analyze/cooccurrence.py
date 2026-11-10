"""领域词共现分析（非生产链路——仅供研究，见 docs/PYTHON-BOUNDARY.md）。

R50：同一项目里哪些领域词**结伴出现**——「智慧城市 + 大数据」
「安防 + 等保」这类组合信号比单词频更能刻画领域交叉：

- 匹配文本面与 keywords.py 同口径（项目名 + 资格要求）；
- 只统计共现计数 ≥ ``min_count`` 的词对（缺省 2——孤例无信号）；
- 词对按 (count 降序, 词对名升序) 排序——确定性；
- 全部为**描述性统计**：共现 ≠ 因果，仅刻画「一起被提及」。
"""

from __future__ import annotations

from collections import Counter
from itertools import combinations
from typing import Any, Dict, List

from src.analyze.dataset import AnalysisDataset
from src.analyze.keywords import DEFAULT_LEXICON, _match_text


def keyword_cooccurrence(
    dataset: AnalysisDataset,
    *,
    lexicon: tuple = DEFAULT_LEXICON,
    top_n: int = 12,
    min_count: int = 2,
) -> List[Dict[str, Any]]:
    """领域词共现 Top N（共现计数降序，并列按词对名——确定性）。

    Args:
        dataset: 分析数据集。
        lexicon: 参与共现的领域词表。
        top_n: 返回条数上限。
        min_count: 词对最低共现数（低于此值不输出——孤例无信号）。

    Returns:
        共现条目列表，每项含：

        - ``pair``：词对（二元列表，字典序）；
        - ``count``：同记录共现数；
        - ``sample_projects``：示例项目名（最多 3 个，出现序）。
    """
    pair_counts: Counter = Counter()
    samples: Dict[tuple, List[str]] = {}

    terms = sorted({t for t in lexicon if t})
    for record in dataset.records:
        text = _match_text(record)
        if not text:
            continue
        hits = [t for t in terms if t in text]
        for a, b in combinations(hits, 2):
            pair_counts[(a, b)] += 1
            bucket = samples.setdefault((a, b), [])
            name = str(record.get("project_name") or "(未命名)")
            if len(bucket) < 3 and name not in bucket:
                bucket.append(name)

    entries: List[Dict[str, Any]] = []
    for (a, b), count in pair_counts.items():
        if count < min_count:
            continue
        entries.append(
            {
                "pair": [a, b],
                "count": count,
                "sample_projects": samples[(a, b)],
            }
        )
    entries.sort(key=lambda e: (-e["count"], e["pair"]))
    return entries[:top_n]
