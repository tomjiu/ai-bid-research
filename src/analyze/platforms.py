"""平台来源分析（非生产链路——仅供研究，见 docs/PYTHON-BOUNDARY.md）。

R98：``source_url`` 字段首次进分析面——公告来自哪些发布平台、
各平台的规模与预算量级，以及与近重复簇交叉的**跨平台转发信号**
（同一簇成员出现在不同平台 = 多平台转发/改包重发的实证）。

域名归一口径（保守、可解释）：

- 无 scheme 的输入（``www.ccgp.gov.cn/x``）防御性补 ``http://``
  再解析——研究语料常见裸域名形态；
- netloc 小写、去首 ``www.``（同一站点）；**其余子域保留**
  （``zfcg.czt.zj.gov.cn`` 与 ``czt.zj.gov.cn`` 是不同入口）；
- 解析不出域名、或域名**不含点**的（空串/纯路径/纯中文/
  无点内网名）计 ``missing`` 不猜数——urlparse 不校验字符集，
  纯中文也能解析出 netloc，点号是研究面可解释的最小域名特征。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from src.analyze.dataset import AnalysisDataset


def normalize_platform(url: Any) -> Optional[str]:
    """URL → 平台域名（None = 非可用 URL）。

    Args:
        url: 原始 source_url 值（任意类型——防御式清洗）。

    Returns:
        归一域名（小写、去首 ``www.``，**须含点**——研究面
        最小域名特征，纯中文/无点内网名返回 ``None``），
        解析失败返回 ``None``。
    """
    if url is None:
        return None
    text = str(url).strip()
    if not text:
        return None
    if "://" not in text:
        text = "http://" + text  # 裸域名防御性补 scheme
    try:
        netloc = urlparse(text).netloc
    except ValueError:
        return None
    netloc = netloc.strip().lower()
    if not netloc or "." not in netloc:
        return None  # 无点：不是可解释的域名形态（不猜数）
    if netloc.startswith("www."):
        netloc = netloc[4:]
    return netloc or None


def platform_source_distribution(
    dataset: AnalysisDataset,
    *,
    duplicate_clusters: Optional[Dict[str, Any]] = None,
    top_n: int = 10,
) -> Dict[str, Any]:
    """平台来源分布（可选跨平台转发信号——与十六节近重复簇交叉）。

    Args:
        dataset: 分析数据集。
        duplicate_clusters: :func:`find_duplicate_clusters` 产物
            （可空——不传则 ``multi_platform`` 面为空）。
        top_n: 平台条目上限（``distinct_count`` 不受限）。

    Returns:
        JSON 可序列化的分布字典：

        - ``sample_count`` / ``missing_count``：有/无可用 URL
          （两数之和 = 总记录数，口径可核对）；
        - ``distinct_count``：去重平台总数（截断前）；
        - ``platforms``：Top N（计数降序、并列按名——确定性），
          每项含平台域名/项目数/预算合计与均值（**有值样本
          口径**）/预算样本数/最近发布日；
        - ``multi_platform``：跨平台转发信号（仅当传入簇且存在
          跨平台簇）：``{"clusters": n, "records": n,
          "examples": [{size, normalized, platforms}…]}``——
          examples 按簇大小降序、并列按归一名（Top 5）。
    """
    groups: Dict[str, List[Dict[str, Any]]] = {}
    missing = 0
    for record in dataset.records:
        platform = normalize_platform(record.get("source_url"))
        if platform is None:
            missing += 1
            continue
        groups.setdefault(platform, []).append(record)

    sample = sum(len(rows) for rows in groups.values())
    entries: List[Dict[str, Any]] = []
    for platform, records in groups.items():
        budgets = [
            float(r["budget"])
            for r in records
            if r.get("budget") is not None
        ]
        dates = [
            str(r.get("publish_date"))[:10]
            for r in records
            if r.get("publish_date")
        ]
        entries.append(
            {
                "platform": platform,
                "count": len(records),
                "budget_total": sum(budgets) if budgets else None,
                "budget_mean": (
                    sum(budgets) / len(budgets) if budgets else None
                ),
                "budget_sample_count": len(budgets),
                "latest_date": max(dates) if dates else None,
            }
        )
    entries.sort(key=lambda entry: (-entry["count"], entry["platform"]))

    result: Dict[str, Any] = {
        "sample_count": sample,
        "missing_count": missing,
        "distinct_count": len(entries),
        "platforms": entries[:top_n],
        "multi_platform": _multi_platform_signal(duplicate_clusters),
    }
    return result


def _multi_platform_signal(
    duplicate_clusters: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """近重复簇的平台跨度统计（簇成员 URL 域名 ≥2 视为跨平台）。

    成员缺 URL / 域名不可解析的不参与平台判定——只有单平台或
    无平台的簇不算跨平台（不猜「可能还有别处转发」）。
    """
    empty = {"clusters": 0, "records": 0, "examples": []}
    if not duplicate_clusters:
        return empty
    examples: List[Dict[str, Any]] = []
    records_total = 0
    for cluster in duplicate_clusters.get("clusters") or []:
        platforms = sorted(
            {
                platform
                for member in cluster.get("members") or []
                if (platform := normalize_platform(member.get("source_url")))
            }
        )
        if len(platforms) < 2:
            continue  # 单平台/无平台簇：不算跨平台（不猜数）
        records_total += cluster.get("size", len(cluster.get("members") or []))
        examples.append(
            {
                "size": cluster.get("size"),
                "normalized": cluster.get("normalized"),
                "platforms": platforms,
            }
        )
    examples.sort(
        key=lambda item: (-(item["size"] or 0), item["normalized"] or "")
    )
    return {
        "clusters": len(examples),
        "records": records_total,
        "examples": examples[:5],
    }
