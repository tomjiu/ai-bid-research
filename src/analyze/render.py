"""统计结果渲染（#601 批次 C·R14）——五维统计 → 确定性 Markdown。

离线路径（无 LLM）：``compute_stats`` 的输出直接渲染为研究快照
（PYTHON-BOUNDARY.md：Markdown/HTML 研究快照不回流生产链路）。

对接 :class:`ReportGenerator`：
``ReportGenerator.save_analysis_report(markdown, title)`` 复用既有
``_save_report``（时间戳命名/非法字符清洗）与 ``export_html``
（带样式独立 HTML）——分析报告与 LLM 报告同一输出面。
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from src.report.generator import ReportGenerator


def _fmt_wan(value: Optional[float]) -> str:
    """万元金额格式化（None → 「—」，整数省小数）。"""
    if value is None:
        return "—"
    if float(value) == int(value):
        return f"{int(value):,}"
    return f"{value:,.2f}"


def _fmt_pct(value: Optional[float]) -> str:
    """百分比格式化（None → 「—」）。"""
    return "—" if value is None else f"{value}%"


def format_stats_markdown(
    stats: Dict[str, Any], *, title: str = "招标数据分析报告"
) -> str:
    """把 :func:`compute_stats` 的输出渲染为 Markdown 报告。

    Args:
        stats: 五维统计汇总（``compute_stats`` 产物）。
        title: 报告标题。

    Returns:
        Markdown 文本（确定性渲染——同一输入同一输出，
        无 LLM 参与结论生成）。
    """
    overview = stats.get("overview", {})
    budget = stats.get("budget", {})
    regions = stats.get("regions", {})
    trend = stats.get("trend", {})
    keywords = stats.get("keywords", {})
    competition = stats.get("competition", {})

    lines: list = []
    lines.append(f"# {title}")
    lines.append("")
    lines.append(f"- 生成时间：{stats.get('generated_at', '—')}")
    lines.append(
        f"- 样本面：共 {overview.get('total', 0)} 条项目，"
        f"其中 {overview.get('awarded', 0)} 条已定标"
        f"（{_fmt_pct(overview.get('award_rate_pct'))}），"
        f"预算字段覆盖 {overview.get('with_budget', 0)} 条，"
        f"日期字段覆盖 {overview.get('with_date', 0)} 条"
    )
    lines.append(
        f"- 预算总额：{_fmt_wan(overview.get('budget_total_wan'))} 万元"
    )
    lines.append("")
    lines.append("---")
    lines.append("")

    # ① 金额分布
    lines.append("## 一、金额分布（万元）")
    lines.append("")
    if budget.get("count"):
        lines.append("| 指标 | 值 |")
        lines.append("|---|---|")
        for label, key in (
            ("样本数", "count"),
            ("总额", "total"),
            ("均值", "mean"),
            ("最小值", "min"),
            ("P25", "p25"),
            ("中位数", "median"),
            ("P75", "p75"),
            ("最大值", "max"),
        ):
            value = budget.get(key)
            shown = str(value) if key == "count" else _fmt_wan(value)
            lines.append(f"| {label} | {shown} |")
    else:
        lines.append("*无预算样本（budget 字段全空）。*")
    lines.append("")

    # ② 区域分布
    lines.append("## 二、区域分布")
    lines.append("")
    region_rows = regions.get("regions", [])
    if region_rows:
        lines.append("| 地区 | 项目数 | 预算合计（万元） | 已定标 |")
        lines.append("|---|---|---|---|")
        for row in region_rows:
            lines.append(
                f"| {row['name']} | {row['count']} | "
                f"{_fmt_wan(row['budget_total'])} | {row['awarded']} |"
            )
    else:
        lines.append("*无地区样本（region 字段全空）。*")
    if regions.get("unique_regions"):
        lines.append("")
        lines.append(
            f"共 {regions['unique_regions']} 个不同地区；"
            f"另有 {regions.get('unknown_count', 0)} 条样本地区未知。"
        )
    lines.append("")

    # ③ 月度趋势
    lines.append("## 三、月度趋势")
    lines.append("")
    month_rows = trend.get("months", [])
    if month_rows:
        lines.append("| 月份 | 项目数 | 预算合计（万元） |")
        lines.append("|---|---|---|")
        for row in month_rows:
            lines.append(
                f"| {row['month']} | {row['count']} | "
                f"{_fmt_wan(row['budget_total'])} |"
            )
        if trend.get("mom_change") is not None:
            lines.append("")
            direction = "上升" if trend["mom_change"] >= 0 else "下降"
            lines.append(
                f"最近一月项目数环比{direction} "
                f"{abs(trend['mom_change'])}%。"
            )
    else:
        lines.append("*无日期样本——趋势不可计算。*")
    lines.append("")

    # ④ 关键词频次
    lines.append("## 四、关键词频次（项目名命中）")
    lines.append("")
    keyword_rows = keywords.get("keywords", [])
    if keyword_rows:
        lines.append("| 关键词 | 命中项目数 | 占比 |")
        lines.append("|---|---|---|")
        for row in keyword_rows:
            lines.append(
                f"| {row['keyword']} | {row['count']} | "
                f"{_fmt_pct(row['share'])} |"
            )
    else:
        lines.append("*领域词表零命中。*")
    if keywords.get("unmatched"):
        lines.append("")
        lines.append(
            f"另有 {keywords['unmatched']} 条项目未命中任何领域关键词。"
        )
    lines.append("")

    # ⑤ 竞争密度
    lines.append("## 五、竞争密度")
    lines.append("")
    lines.append(f"- 已定标样本：{competition.get('awarded', 0)} 条")
    lines.append(
        f"- 独立中标人：{competition.get('unique_winners', 0)} 家"
    )
    lines.append(
        f"- 集中度：CR1 = {_fmt_pct(competition.get('cr1'))}，"
        f"CR3 = {_fmt_pct(competition.get('cr3'))}，"
        f"HHI = {competition.get('hhi') if competition.get('hhi') is not None else '—'}"
    )
    lines.append(
        f"- 平均预算：{_fmt_wan(competition.get('avg_budget'))} 万元"
    )
    winner_rows = competition.get("top_winners", [])
    if winner_rows:
        lines.append("")
        lines.append("| 中标人 | 中标数 | 份额 |")
        lines.append("|---|---|---|")
        for row in winner_rows:
            lines.append(
                f"| {row['name']} | {row['count']} | "
                f"{_fmt_pct(row['share'])} |"
            )
    lines.append("")

    # 口径脚注
    lines.append("---")
    lines.append("")
    lines.append("### 口径说明")
    lines.append("")
    lines.append("- 金额分位仅计预算非空样本；分位数为线性插值（inclusive）。")
    lines.append("- 月度趋势仅计发布日期非空样本；环比基于最近两个整月。")
    lines.append("- 集中度（CR1/CR3/HHI）以已定标样本为分母；无定标样本时为「—」。")
    lines.append("- 本报告为离线确定性统计（无 LLM 参与），结论可由原始数据复算。")
    lines.append("")
    return "\n".join(lines)


def save_analysis_report(
    generator: ReportGenerator,
    markdown: str,
    *,
    prefix: str = "analysis",
    html: bool = False,
) -> Dict[str, str]:
    """经 :class:`ReportGenerator` 保存分析报告（复用既有输出面）。

    Args:
        generator: 报告生成器（提供输出目录与 HTML 导出）。
        markdown: ``format_stats_markdown`` 产物。
        prefix: 文件名前缀。
        html: 是否同时导出 HTML。

    Returns:
        ``{"markdown": 路径, "html": 路径或空串}``。
    """
    md_path = generator._save_report(markdown, prefix=prefix)  # noqa: SLF001
    result = {"markdown": str(md_path), "html": ""}
    if html:
        html_path = generator.export_html(md_path)
        result["html"] = str(html_path)
    return result
