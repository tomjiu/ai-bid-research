"""分析报告数据组装与渲染（#601 批次 C 第 14 轮）。

把批次 C 各分析面（预算/区域/趋势/关键词/密度）组装成单一
payload 并渲染为**纯数据** Markdown 报告——不走 LLM、离线可
复现（LLM 叙述报告由 ``generate_competition_report`` 面
承担，两者互补：数据报告管「可核对的数」，LLM 报告管「叙述」）。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.analyze.dataset import AnalysisDataset
from src.analyze.buyers import buyer_profiles
from src.analyze.density import competition_density
from src.analyze.quality import field_quality
from src.analyze.keywords import common_bigrams, keyword_frequency
from src.analyze.stats import (
    budget_region_crosstab,
    budget_summary,
    date_range,
    monthly_trend,
    region_distribution,
)


def build_analysis_payload(
    dataset: AnalysisDataset,
    *,
    keyword: Optional[str] = None,
    days: Optional[int] = None,
) -> Dict[str, Any]:
    """组装全部分析面为单一 payload。

    Args:
        dataset: 分析数据集。
        keyword: 报告口径的关键词（可空 = 全量）。
        days: 报告口径的时间窗口（可空 = 不限）。

    Returns:
        JSON 可序列化的分析 payload。
    """
    return {
        "keyword": keyword,
        "days": days,
        "generated_at": dataset.generated_at,
        "record_count": len(dataset),
        "complete_rate": dataset.complete_rate,
        "budget": budget_summary(dataset),
        "region": region_distribution(dataset, top=10),
        "trend": monthly_trend(dataset),
        "date_range": date_range(dataset),
        "keywords": dict(list(keyword_frequency(dataset).items())[:15]),
        "bigrams": common_bigrams(dataset, top=10),
        "density": competition_density(dataset),
        "field_quality": field_quality(dataset),
        "buyer_profiles": buyer_profiles(dataset),
        "budget_region_crosstab": budget_region_crosstab(dataset),
    }


def _fmt_money(value: Optional[float]) -> str:
    """金额格式化（None → ——；大数带千分位）。"""
    if value is None:
        return "——"
    return f"{value:,.1f}"


def _fmt_pct(value: Optional[float]) -> str:
    """比率格式化（None → ——；0-1 转 %）。"""
    if value is None:
        return "——"
    return f"{value * 100:.1f}%"


def _render_table(headers: List[str], rows: List[List[str]]) -> str:
    """渲染 Markdown 表格。"""
    lines = [
        "| " + " | ".join(headers) + " |",
        "|" + "|".join([" --- " for _ in headers]) + "|",
    ]
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def render_analysis_markdown(payload: Dict[str, Any]) -> str:
    """把分析 payload 渲染为 Markdown（纯数据报告）。

    Args:
        payload: :func:`build_analysis_payload` 产物。

    Returns:
        Markdown 文本。
    """
    keyword = payload.get("keyword")
    title_scope = f"「{keyword}」" if keyword else "全量数据"
    count = payload.get("record_count", 0)

    sections: List[str] = [
        f"# 领域数据分析报告：{title_scope}",
        "",
        f"- 记录数：**{count} 条**",
        f"- 时间窗口：{'近 ' + str(payload['days']) + ' 天' if payload.get('days') else '不限'}",
        f"- 数据区间：{payload['date_range'].get('earliest') or '——'}"
        f" 至 {payload['date_range'].get('latest') or '——'}",
        f"- 数据完整度：{_fmt_pct(payload.get('complete_rate'))}（12 字段口径）",
        f"- 生成时间：{payload.get('generated_at')}",
        "",
    ]

    if count == 0:
        sections += [
            "## 数据缺口",
            "",
            "数据集为空（关键词无命中或窗口内无记录）。",
            "请先通过 ``collect`` / ``extract`` 入库公告数据。",
            "",
        ]
        return "\n".join(sections)

    budget = payload["budget"]
    sections += [
        "## 一、预算分布（万元）",
        "",
        _render_table(
            ["指标", "值"],
            [
                ["有效样本数", str(budget["count"])],
                ["合计", _fmt_money(budget["total"])],
                ["最小 / 最大", f"{_fmt_money(budget['min'])} / {_fmt_money(budget['max'])}"],
                ["均值 / 中位", f"{_fmt_money(budget['mean'])} / {_fmt_money(budget['median'])}"],
                ["P25 / P75", f"{_fmt_money(budget['p25'])} / {_fmt_money(budget['p75'])}"],
                ["P90", _fmt_money(budget["p90"])],
            ],
        ),
        "",
    ]

    region = payload["region"]
    # 只有「未知」桶 = 没有区域信号（数据缺口不伪装成分布）——跳节
    if region and not (len(region) == 1 and "未知" in region):
        sections += [
            "## 二、区域分布",
            "",
            _render_table(
                ["区域", "项目数"],
                [[str(k), str(v)] for k, v in region.items()],
            ),
            "",
        ]

    trend = payload["trend"]
    if trend:
        sections += [
            "## 三、月度发布趋势",
            "",
            _render_table(
                ["月份", "发布数"],
                [[str(k), str(v)] for k, v in trend.items()],
            ),
            "",
        ]

    keywords = payload["keywords"]
    if keywords:
        rows = [
            [
                term,
                str(slot["count"]),
                _fmt_money(slot["budget_total"]),
                _fmt_money(slot["budget_mean"]),
            ]
            for term, slot in keywords.items()
        ]
        sections += [
            "## 四、领域关键词（词表命中 Top）",
            "",
            _render_table(["领域词", "命中项目数", "预算合计(万)", "平均预算(万)"], rows),
            "",
        ]

    bigrams = payload["bigrams"]
    if bigrams:
        sections += [
            "## 五、新词发现（二元组频次——词表外领域信号）",
            "",
            "、".join(f"{gram}（{n}）" for gram, n in bigrams.items()),
            "",
        ]

    density = payload["density"]
    sections += [
        "## 六、竞争密度（估算）",
        "",
        f"- 发布密度：**{density['monthly_rate'] and round(density['monthly_rate'], 1) or '——'} 条/月**"
        f"（跨度 {density['span_months'] or '——'} 个月，层级：**{density['density_level']}**）",
        f"- 采购人集中度：top3 占 {_fmt_pct(density['purchaser_top3_share'])}，"
        f"HHI {round(density['purchaser_hhi'], 0) if density['purchaser_hhi'] is not None else '——'}"
        "（0-10000，越高越集中）",
        f"- 定标率：{_fmt_pct(density['award_rate'])}；"
        f"中标人 top3 占 {_fmt_pct(density['winner_top3_share'])}",
        "",
    ]

    quality = payload.get("field_quality") or {}
    if quality.get("most_missing"):
        rows = [
            [
                name,
                _fmt_pct(quality["fields"][name]["rate"]),
                f"{quality['fields'][name]['filled']}/{quality['records']}",
            ]
            for name in quality["most_missing"]
        ]
        sections += [
            "## 七、数据质量（系统性缺口——下一步补采行动面）",
            "",
            _render_table(["最缺字段", "填充率", "已填/总数"], rows),
            "",
            f"整体字段填充率：{_fmt_pct(quality.get('overall'))}",
            "",
        ]

    buyers = payload.get("buyer_profiles") or []
    if buyers:
        rows = [
            [
                profile["purchaser"],
                str(profile["project_count"]),
                _fmt_money(profile["budget_total"]),
                _fmt_money(profile["budget_mean"]),
                str(len(profile["active_months"])),
                "、".join(profile["categories"]) or "——",
            ]
            for profile in buyers
        ]
        sections += [
            "## 八、采购人画像（项目数 Top）",
            "",
            _render_table(
                ["采购人", "项目数", "预算合计(万)", "平均预算(万)", "活跃月份数", "领域"],
                rows,
            ),
            "",
            "注：预算口径只计有值样本（样本数见 payload budget_sample_count），缺失不折零。",
            "",
        ]

    crosstab = payload.get("budget_region_crosstab") or {}
    # 只有「未知」区域 = 无区域信号（同二节跳节口径）
    if crosstab and not (len(crosstab) == 1 and "未知" in crosstab):
        first_buckets = next(iter(crosstab.values()))
        headers = ["区域"] + list(first_buckets.keys()) + ["合计"]
        rows = []
        for region, buckets in crosstab.items():
            rows.append(
                [region]
                + [str(count) for count in buckets.values()]
                + [str(sum(buckets.values()))]
            )
        totals = [
            str(sum(row[label] for row in crosstab.values()))
            for label in first_buckets
        ]
        rows.append(
            ["合计"] + totals + [str(sum(map(sum, (b.values() for b in crosstab.values()))))]
        )
        sections += [
            "## 九、预算 × 区域交叉（计数矩阵，万元分桶）",
            "",
            _render_table(headers, rows),
            "",
            "注：分桶为研究经验口径（左闭右开，末桶无上界）；「预算未知」为数据缺口如实可见。",
            "",
        ]

    sections += [
        "## 口径说明",
        "",
        "- 本报告为研究工具**离线数据报告**（PYTHON-BOUNDARY 非生产口径）。",
        "- 密度分层与集中度是**启发式估算**，投标决策需结合公告原文复核。",
        "- 预算单位统一为万元（采集/抽取面归一口径）。",
        "",
    ]
    return "\n".join(sections)
