"""近重复公告检测（#601 R79，批 L 数据质量）。

精确去重（:mod:`src.collect.dedupe` 按 bid_id）管不住招投标研究里
最常见的三种「改头换面」：

1. **改包重发**——同一项目调整包件后标题加了个「（二次）」；
2. **多平台转发**——不同站点抓取，bid_id 不同但项目本同名；
3. **标题微调**——去掉地区前缀、改标点、全半角混排。

检测面 = 归一化后的项目名 + 编辑距离容忍（比例自适应，长名容忍
更多编辑步）。聚类用传递闭包（并查集）：A≈B、B≈C ⇒ {A,B,C}。

性能纪律：纯 O(n²) 全对比在万条级不可行——长度预筛（O(1)）+
字符集 Jaccard 快筛（O(len)）先淘汰绝大多数对，编辑距离只对
「长得就像」的对做。设对比预算上限，超限报诚实警告而非死磕。
"""

from __future__ import annotations

import unicodedata
from typing import Any, Dict, List, Optional, Tuple

from src.analyze.dataset import AnalysisDataset

# 归一后名称的展示截断（报告可读性）
_DISPLAY_LEN = 60

# 对比预算（候选对数）：pigeonhole 倒排生成的候选对上限。
# 超限的桶（同模板批量采购的真实形态）被跳过并在结果中
# 如实标注 ``budget_exhausted``——宁报「不完整」不装「完成」。
# 5 万对 × Ukkonen 带限 DP ≈ 纯 Python 数秒——研究交互式耐心上限。
_MAX_PAIR_BUDGET = 50_000


def _to_halfwidth(text: str) -> str:
    """全角→半角（含空格），拉丁统一小写。

    Windows 采集常见全角混排（，（）ＡＢＣ）在此拉平。
    """
    out = []
    for ch in text:
        code = ord(ch)
        if 0xFF01 <= code <= 0xFF5E:  # 全角区
            out.append(chr(code - 0xFEE0))
        elif ch == "\u3000":  # 全角空格
            out.append(" ")
        else:
            out.append(ch)
    return "".join(out)


def normalize_name(name: Any) -> str:
    """项目名归一：比较键（保守——只删噪不改词）。

    步骤：NFKC 折叠 → 全角转半角 → 删空白/标点/符号 → 拉丁小写。
    deliberately 保留全部文字（含中文、数字、字母）——「智慧城市
    一期」≠「智慧城市二期」。
    """
    if not isinstance(name, str) or not name.strip():
        return ""
    text = unicodedata.normalize("NFKC", name)
    text = _to_halfwidth(text)
    kept = []
    for ch in text:
        cat = unicodedata.category(ch)
        if cat[0] in ("P", "Z", "S", "C"):  # 标点/分隔/符号/控制
            continue
        kept.append(ch.lower())
    return "".join(kept)


def levenshtein(a: str, b: str) -> int:
    """经典编辑距离（两行滚动数组，O(min) 空间）。

    公开为模块函数供独立验证（测试直击正确性）。
    """
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    if len(a) < len(b):
        a, b = b, a  # b 为短者——行缓冲最小化
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cost = 0 if ca == cb else 1
            cur.append(
                min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost)
            )
        prev = cur
    return prev[-1]


def levenshtein_within(a: str, b: str, tol: int) -> bool:
    """编辑距离是否 ≤ ``tol``（Ukkonen 带限 DP + 行早停）。
    与 :func:`levenshtein` 判定严格等价，但只计算 ``|i−j| ≤ tol``
    对角带内的格子（带外对齐本身已超预算）——成本
    ``O(len·(2·tol+1))``，tol≤3 的研究场景下比全 DP 快 3-4 倍；
    行内最小值超 tol 时提前返回 False（无路可救）。
    """
    if a == b:
        return True
    la, lb = len(a), len(b)
    if abs(la - lb) > tol:
        return False
    if not a or not b:
        return True  # 某侧空且长度差 ≤ tol——距离=长度差 ≤ tol
    if lb > la:  # b 为短者（列方向带宽最小）
        a, b, la, lb = b, a, lb, la
    INF = tol + 1
    # 第 0 行：d[0][j] = j（仅 band 内有效）
    prev = [j if j <= tol else INF for j in range(lb + 1)]
    for i in range(1, la + 1):
        lo = max(1, i - tol)
        hi = min(lb, i + tol)
        cur = [INF] * (lb + 1)
        if lo == 1:
            cur[0] = i if i <= tol else INF
        ca = a[i - 1]
        row_min = INF
        for j in range(lo, hi + 1):
            cost = 0 if ca == b[j - 1] else 1
            v = prev[j] + 1
            alt = cur[j - 1] + 1
            if alt < v:
                v = alt
            alt = prev[j - 1] + cost
            if alt < v:
                v = alt
            cur[j] = v
            if v < row_min:
                row_min = v
        if row_min > tol:
            return False  # 本行 band 内全超限——无路可救
        prev = cur
    return prev[lb] <= tol


def _pigeonhole_blocks(name: str, tol: int, max_ratio: float) -> List[str]:
    """pigeonhole 分块（候选生成的数学完备性锚点）。

    命题：若 a 与某 b 的编辑距离 e ≤ tol_pair（对内较长侧
    比例预算），则 a 分 ``n`` 块后至少一块在 b 中原样存在
    （e 次编辑至多改动 e 块，n ≥ e+1 即有一块幸免）。

    tol_pair 由较长名决定，最长可比 tol（本名预算）多
    ``(tol+1)·r/(1-r)`` 步——分块数按通用式放大保证覆盖
    （默认 r=0.12 下即 tol+2 块，与直觉一致）。
    """
    n = int((tol + 1) / (1 - max_ratio)) + 1
    if n >= len(name):
        return []  # 名太短块数≥字符数——退化为全名匹配（by_name 已覆盖）
    size, extra = divmod(len(name), n)
    blocks: List[str] = []
    start = 0
    for k in range(n):
        end = start + size + (1 if k < extra else 0)
        blocks.append(name[start:end])
        start = end
    return blocks


def charset_distance_bound(sa: frozenset, sb: frozenset) -> int:
    """字符集对称差给出的编辑距离**下界**（O(集合) 快筛）。

    数学依据：a 中出现而 b 中不出现的每个字符，至少需要一次
    替换或删除才能变成 b；替换一次可同时消掉两侧各一个独有
    字符——故 ``levenshtein(a,b) ≥ max(|sa−sb|, |sb−sa|)``。

    相比 Jaccard 启发式（批量采购同模板名「字符高度重叠但
    编辑距离远」时全部放行），这是可证明的否决条件。
    """
    if not sa or not sb:
        return 0  # 空集不参与（调用方已过滤空名）
    return max(len(sa - sb), len(sb - sa))


def is_similar(
    norm_a: str,
    norm_b: str,
    max_ratio: float = 0.12,
) -> bool:
    """归一名是否近重复（比例自适应编辑距离）。

    Args:
        norm_a/norm_b: ``normalize_name`` 产物（调用方保证已归一）。
        max_ratio: 允许的编辑距离占较长名长度的比例。0.12 意味
            20 字名容忍 2 步编辑（加「二次」+标点即命中）。

    双重 O(len) 预筛按序否决：长度差（编辑距离 ≥ 长度差）→
    字符集对称差（编辑距离 ≥ max(|sa−sb|, |sb−sa|)）——都过
    了才进 Levenshtein 精算。
    """
    if not norm_a or not norm_b:
        return False
    if norm_a == norm_b:
        return True
    longer = max(len(norm_a), len(norm_b))
    tol = int(longer * max_ratio)
    if tol < 1:
        return False
    if abs(len(norm_a) - len(norm_b)) > tol:
        return False  # 长度差已超预算——编辑距离必超
    if charset_distance_bound(frozenset(norm_a), frozenset(norm_b)) > tol:
        return False  # 独有字符太多——替换/删除步数必超预算
    return levenshtein_within(norm_a, norm_b, tol)


class _UnionFind:
    """并查集（路径压缩 + 按秩合并）——传递闭包聚类。"""

    def __init__(self, n: int) -> None:
        self._parent = list(range(n))
        self._rank = [0] * n

    def find(self, x: int) -> int:
        root = x
        while self._parent[root] != root:
            root = self._parent[root]
        while self._parent[x] != root:  # 路径压缩
            self._parent[x], x = root, self._parent[x]
        return root

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return
        if self._rank[ra] < self._rank[rb]:
            ra, rb = rb, ra
        self._parent[rb] = ra
        if self._rank[ra] == self._rank[rb]:
            self._rank[ra] += 1


def find_duplicate_clusters(
    dataset: AnalysisDataset,
    max_ratio: float = 0.12,
) -> Dict[str, Any]:
    """近重复公告聚类。

    Args:
        dataset: 分析数据集。
        max_ratio: 编辑距离容忍比例（见 :func:`is_similar`）。

    Returns:
        ``{"total": N, "clusters": [...], "records_in_clusters": n,
        "duplicate_rate": r, "budget_exhausted": bool}``；
        每个 cluster 为 ``{"size": n, "normalized": str,
        "members": [{"bid_id", "project_name"}…]}``——按 size 降序、
        代表名升序（稳定的研究阅读序）。
    """
    records = dataset.records
    total = len(records)
    empty: Dict[str, Any] = {
        "total": total,
        "clusters": [],
        "records_in_clusters": 0,
        "duplicate_rate": 0.0,
        "budget_exhausted": False,
    }
    if total < 2:
        return empty

    # 归一 + 带下标（空名不参与——无比较锚点，报告里另计）
    indexed: List[Tuple[int, str]] = [
        (i, normalize_name(r.get("project_name")))
        for i, r in enumerate(records)
    ]
    candidates = [(i, n) for i, n in indexed if n]
    # 下标 → 归一名的直查表（候选精算用）
    candidates_by_index = {i: n for i, n in candidates}

    # 完全同名直配对（零编辑距离——最常见形态，先并入再近邻比对）
    uf = _UnionFind(total)
    by_name: Dict[str, List[int]] = {}
    for i, n in candidates:
        by_name.setdefault(n, []).append(i)
    for idxs in by_name.values():
        for other in idxs[1:]:
            uf.union(idxs[0], other)

    # pigeonhole 候选生成：块倒排（替代滑窗全对比）。
    # 真实库（名各异的公告）块桶小 → 候选极少；同模板批量采购名
    # （「某某市第N号…」——招投标真实形态）中段块桶爆炸 →
    # 预算截断 + budget_exhausted 诚实标注，不无限精算。
    pairs_seen = 0
    budget_exhausted = False
    pair_set: set = set()
    buckets: Dict[str, List[int]] = {}
    for i, n in candidates:
        tol_i = int(len(n) * max_ratio)
        if tol_i < 1:
            continue  # 短名（tol=0）只全同匹配——by_name 已覆盖
        for blk in _pigeonhole_blocks(n, tol_i, max_ratio):
            buckets.setdefault(blk, []).append(i)
    for members in buckets.values():
        if len(members) < 2:
            continue
        count = len(members) * (len(members) - 1) // 2
        if pairs_seen + count > _MAX_PAIR_BUDGET:
            # 桶爆炸（同模板名）——跳过整桶并如实声明
            budget_exhausted = True
            continue
        pairs_seen += count
        for ai in range(len(members)):
            for bi in range(ai + 1, len(members)):
                pair_set.add((members[ai], members[bi]))

    # 候选对精算（内联预筛——charset 预计算免每对重复建 set）
    charset_cache = {i: frozenset(n) for i, n in candidates}
    for i, j in pair_set:
        na = candidates_by_index[i]
        nb = candidates_by_index[j]
        tol = int(max(len(na), len(nb)) * max_ratio)
        if tol < 1 or abs(len(na) - len(nb)) > tol:
            continue  # O(1) 长度否决
        ca = charset_cache[i]
        cb = charset_cache[j]
        if max(len(ca - cb), len(cb - ca)) > tol:
            continue  # O(集合) 字符集下界否决
        if levenshtein_within(na, nb, tol):
            uf.union(i, j)

    # 收簇：只保留 size ≥ 2
    clusters: Dict[int, List[int]] = {}
    for i, _ in candidates:
        root = uf.find(i)
        clusters.setdefault(root, []).append(i)
    multi = [idxs for idxs in clusters.values() if len(idxs) >= 2]

    rendered: List[Dict[str, Any]] = []
    for idxs in multi:
        members = [
            {
                "bid_id": records[i].get("bid_id"),
                "project_name": records[i].get("project_name"),
            }
            for i in sorted(idxs)
        ]
        norm = normalize_name(records[idxs[0]].get("project_name"))
        rendered.append(
            {
                "size": len(idxs),
                "normalized": norm[:_DISPLAY_LEN],
                "members": members,
            }
        )
    rendered.sort(key=lambda c: (-c["size"], c["normalized"]))

    in_clusters = sum(c["size"] for c in rendered)
    return {
        "total": total,
        "clusters": rendered,
        "records_in_clusters": in_clusters,
        "duplicate_rate": in_clusters / total,
        "budget_exhausted": budget_exhausted,
    }


def render_duplicates_markdown(
    payload: Dict[str, Any], *, ordinal: Optional[str] = None
) -> str:
    """近重复节 Markdown（analyze 报告第十六节）。

    Args:
        payload: :func:`find_duplicate_clusters` 产物。
        ordinal: 节序号（如 ``"十六"``）——嵌入标题保持报告
            节序一致；缺省为独立渲染（无编号）。

    超预算时首行如实声明（对比不完整，结论保守），不静默吞。
    """
    title = (
        f"## {ordinal}、近重复公告检测" if ordinal else "## 近重复公告检测"
    )
    lines: List[str] = [title, ""]
    total = payload.get("total", 0)
    if not payload.get("clusters"):
        lines.append(
            f"全库 {total} 条公告未检出近重复（同名或编辑距离近似）——"
            "样本独立性好。"
        )
        if payload.get("budget_exhausted"):
            lines.append("")
            lines.append(
                "> 注意：对比预算耗尽，本结论仅覆盖部分两两比对，"
                "建议缩小数据范围复核。"
            )
        return "\n".join(lines) + "\n"

    rate = payload.get("duplicate_rate", 0.0)
    lines.append(
        f"检出 {len(payload['clusters'])} 组近重复公告，涉及 "
        f"{payload['records_in_clusters']}/{total} 条"
        f"（占比 {rate:.1%}）——多源于改包重发/多平台转发，"
        "统计分析前建议按簇去重或加权。"
    )
    lines.append("")
    lines.append("| 簇大小 | 归一后项目名 | 成员 bid_id |")
    lines.append("| --- | --- | --- |")
    for cluster in payload["clusters"][:10]:  # 表格前 10 簇，防报告爆炸
        ids = "<br>".join(
            str(m["bid_id"]) if m["bid_id"] else "（无 ID）"
            for m in cluster["members"]
        )
        name = cluster["normalized"] or "（空）"
        lines.append(f"| {cluster['size']} | {name} | {ids} |")
    rest = len(payload["clusters"]) - 10
    if rest > 0:
        lines.append("")
        lines.append(f"…另有 {rest} 组小簇，详见 JSON 导出。")
    if payload.get("budget_exhausted"):
        lines.append("")
        lines.append(
            "> 注意：对比预算耗尽，上述结果仅覆盖部分两两比对。"
        )
    return "\n".join(lines) + "\n"
