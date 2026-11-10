"""分析报告数据组装与渲染（#601 批次 C 第 14 轮）。

把批次 C 各分析面（预算/区域/趋势/关键词/密度）组装成单一
payload 并渲染为**纯数据** Markdown 报告——不走 LLM、离线可
复现（LLM 叙述报告由 ``generate_competition_report`` 面
承担，两者互补：数据报告管「可核对的数」，LLM 报告管「叙述」）。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.analyze.dataset import AnalysisDataset
from src.analyze.agencies import agency_profiles
from src.analyze.buyers import buyer_profiles
from src.analyze.categories import category_distribution
from src.analyze.cooccurrence import keyword_cooccurrence
from src.analyze.outliers import budget_outliers
from src.analyze.platforms import platform_source_distribution
from src.analyze.regions import province_distribution
from src.analyze.relationships import purchaser_supplier_pairs
from src.analyze.rolling import rolling_comparison
from src.analyze.suppliers import supplier_profiles
from src.analyze.density import competition_density, concentration_trend
from src.analyze.duplicates import find_duplicate_clusters, render_duplicates_markdown
from src.analyze.quality import field_quality, semantic_health, render_semantic_health_markdown
from src.analyze.windows import response_windows
from src.analyze.keywords import (
    common_bigrams,
    keyword_frequency,
    keyword_monthly_trend,
)
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
    # duplicates 先算一次：十六节渲染与二十一节跨平台信号共用
    # （同一数据同一簇——两处各自重算既浪费又有口径漂移风险）
    duplicates = find_duplicate_clusters(dataset)
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
        "supplier_profiles": supplier_profiles(dataset),
        "budget_outliers": budget_outliers(dataset),
        "keyword_cooccurrence": keyword_cooccurrence(dataset),
        "province_distribution": province_distribution(dataset),
        "rolling_comparison": rolling_comparison(dataset),
        "purchaser_supplier_pairs": purchaser_supplier_pairs(dataset),
        "budget_region_crosstab": budget_region_crosstab(dataset),
        "keyword_trends": keyword_monthly_trend(dataset),
        "concentration_trend": concentration_trend(dataset),
        "duplicates": duplicates,
        "semantic_health": semantic_health(dataset),
        "response_windows": response_windows(dataset),
        "agency_profiles": agency_profiles(dataset),
        "category_distribution": category_distribution(dataset),
        "platform_distribution": platform_source_distribution(
            dataset, duplicate_clusters=duplicates
        ),
    }


def _fmt_money(value: Optional[float]) -> str:
    """金额格式化（None → ——；大数带千分位）。"""
    if value is None:
        return "——"
    return f"{value:,.1f}"


def _signed(value: Optional[float]) -> str:
    """带符号数值渲染（环比差专用）：None → ——，正数显式 +。"""
    if value is None:
        return "——"
    return f"{value:+g}"


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


def _slugify_heading(heading: str) -> str:
    """Markdown 锚点 slug（GitHub 风格近似——中文保留、空白折叠）。

    GitHub 锚点规则对中文报告：小写 ASCII、去标点、空白→连字符、
    中文原样保留。研究面 HTML 导出（export_html）自建锚点，
    此 slug 仅服务 GitHub/兼容渲染器预览。
    """
    slug = []
    for ch in heading.strip().lower():
        if ch.isalnum() or "\u4e00" <= ch <= "\u9fff":
            slug.append(ch)
        elif ch.isspace():
            slug.append("-")
        # 标点丢弃
    return "".join(slug) or "section"


def build_toc(markdown_text: str, *, max_depth: int = 3) -> str:
    """从已渲染 Markdown 提取标题生成目录（R63）。

    Args:
        markdown_text: 完整报告 Markdown。
        max_depth: 收录标题层级（缺省 3——## 节 + ### 子节；
            报告面最深即 ###）。

    Returns:
        目录块（``## 目录`` + 锚点列表）；无标题返回空串。
    """
    entries = []
    in_code_block = False
    for line in markdown_text.splitlines():
        if line.strip().startswith("```"):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue
        stripped = line.lstrip()
        if not stripped.startswith("#"):
            continue
        level = len(stripped) - len(stripped.lstrip("#"))
        if level < 2 or level > max_depth:
            continue
        title = stripped[level:].strip()
        if title == "目录":
            continue  # 防 TOC 自引用
        indent = "  " * (level - 2)
        entries.append(f"{indent}- [{title}](#{_slugify_heading(title)})")
    if not entries:
        return ""
    return "\n".join(["## 目录", "", *entries, ""])


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
        rolling = payload.get("rolling_comparison") or {}
        if rolling and not rolling.get("skipped_reason"):
            cur, prev, delta = (
                rolling["current"],
                rolling["previous"],
                rolling["delta"],
            )
            sections += [
                "### 窗口对照（近 "
                + str(len(cur["months"]))
                + " 个月 vs 再前同宽）",
                "",
                _render_table(
                    ["指标", "当前窗口", "前一窗口", "环比差"],
                    [
                        [
                            "项目数",
                            str(cur["project_count"]),
                            str(prev["project_count"]),
                            _signed(delta["project_count"]),
                        ],
                        [
                            "平均预算(万)",
                            _fmt_money(cur["budget_mean"]),
                            _fmt_money(prev["budget_mean"]),
                            _signed(delta["budget_mean"]),
                        ],
                        [
                            "定标数",
                            str(cur["awarded_count"]),
                            str(prev["awarded_count"]),
                            _signed(delta["awarded_count"]),
                        ],
                    ],
                ),
                "",
                "注：环比差 = 当前 − 前值；预算均值只计有值样本；月份不足两倍窗口时本块不展示。",
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

    trends = payload.get("keyword_trends") or {}
    if trends:
        months_union = sorted(
            {month for slot in trends.values() for month in slot["months"]}
        )
        headers = ["领域词", "首次出现"] + months_union + ["合计"]
        rows = [
            [term, str(slot["first_seen"])]
            + [str(slot["months"].get(month, 0)) for month in months_union]
            + [str(slot["total"])]
            for term, slot in trends.items()
        ]
        sections += [
            "## 十、术语演化（领域词月度命中趋势）",
            "",
            _render_table(headers, rows),
            "",
            "注：无发布日期的记录不参与本节；首次出现为该词首个命中月份——**新兴领域信号，供人工复核**。",
            "",
        ]

    concentration = payload.get("concentration_trend") or {}
    months = concentration.get("months") or []
    # 趋势面需 ≥2 个时间点才有对照意义（单月无演化可看，六节已覆盖全局密度）
    if len(months) >= 2:
        rows = [
            [
                slot["month"],
                str(slot["projects"]),
                str(slot["purchasers"]),
                str(round(slot["hhi"], 0)) if slot["hhi"] is not None else "——",
                _fmt_pct(slot["award_rate"]),
            ]
            for slot in months
        ]
        sections += [
            "## 十一、集中度月度趋势（估算）",
            "",
            _render_table(
                ["月份", "项目数", "采购人数", "HHI(0-10000)", "定标率"], rows
            ),
            "",
            "注：HHI 按当月采购人分布估算（口径同六节）；无发布日期记录不参与；单月数据无趋势对照不展示本节。",
            "",
        ]

    suppliers = payload.get("supplier_profiles") or []
    if suppliers:
        rows = [
            [
                profile["winner"],
                str(profile["award_count"]),
                _fmt_money(profile["budget_total"]),
                _fmt_money(profile["budget_mean"]),
                str(profile["purchaser_count"]),
                "、".join(profile["categories"]) or "——",
            ]
            for profile in suppliers
        ]
        sections += [
            "## 十二、供应商画像（中标数 Top）",
            "",
            _render_table(
                ["供应商", "中标数", "所中项目预算合计(万)", "平均预算(万)", "买方数", "领域"],
                rows,
            ),
 "",
            "注：预算为**项目预算口径**（库内无中标合同额字段）；未定标/流标记录不参与本节；买方数 = 所中项目采购人去重数。",
            "",
        ]
        pairs = payload.get("purchaser_supplier_pairs") or []
        if pairs:
            pair_rows = [
                [
                    p["purchaser"],
                    p["winner"],
                    str(p["repeat_count"]),
                    _fmt_money(p["budget_total"]),
                    "、".join(p["months"]),
                ]
                for p in pairs
            ]
            sections += [
                "### 重复合作关系（同采购人 × 同供应商 ≥ 2 次）",
                "",
                _render_table(
                    ["采购人", "供应商", "合作次数", "预算合计(万)", "合作月份"],
                    pair_rows,
                ),
                "",
                "注：重复中标是**合作信号**不是违规认定；单次合作对不展示；月份为公告月口径。",
                "",
            ]

    outliers = payload.get("budget_outliers") or {}
    if outliers and not outliers.get("skipped_reason"):
        rows = [
            ["疑似高价（超上围栏）", o["project_name"], _fmt_money(o["budget"])]
            for o in outliers["high"]
        ] + [
            ["疑似低价（低于下围栏）", o["project_name"], _fmt_money(o["budget"])]
            for o in outliers["low"]
        ]
        fence = (
            f"样本 {outliers['sample_count']} 个；"
            f"Q1={_fmt_money(outliers['q1'])} / 中位={_fmt_money(outliers['median'])} / "
            f"Q3={_fmt_money(outliers['q3'])}；"
            f"围栏 [{_fmt_money(outliers['lower_fence'])}, "
            f"{_fmt_money(outliers['upper_fence'])}]"
        )
        sections += [
            "## 十三、预算离群标记（IQR）",
            "",
            fence,
            "",
            (
                _render_table(["类别", "项目", "预算(万)"], rows)
                if rows
                else "本口径下无离群样本。"
            ),
            "",
            "注：离群是**统计标记**不是数据错误；低价离群常见于万元/元口径混录，高价离群常见于打包标，均需人工复核。",
            "",
        ]

    cooc = payload.get("keyword_cooccurrence") or []
    if cooc:
        rows = [
            [
                " × ".join(entry["pair"]),
                str(entry["count"]),
                "；".join(entry["sample_projects"]),
            ]
            for entry in cooc
        ]
        sections += [
            "## 十四、领域词共现（同项目结伴出现）",
            "",
            _render_table(["词对", "共现数", "示例项目"], rows),
            "",
            "注：共现 ≠ 因果，仅刻画「一起被提及」；共现数 < 2 的孤例词对不展示（无信号）。",
            "",
        ]

    province = payload.get("province_distribution") or {}
    prov_dist = province.get("distribution") or {}
    if prov_dist:
        rows = [[name, str(count)] for name, count in prov_dist.items()]
        sections += [
            "## 十五、省级归一分布（混杂口径折叠）",
            "",
            _render_table(["省级区域", "项目数"], rows),
            "",
            (
                f"解析成功 {province['parsed_count']} 条 / "
                f"无法定位省级 {province['unknown_count']} 条"
                "（裸市名/空区域不猜数，不计入本节）。"
            ),
            "",
        ]

    # 第十六节：近重复（有簇才有行动面；无簇一句带过也保留节——
    # 研究者需要看到「查过了且干净」的明示，而非留白猜测）
    duplicates = payload.get("duplicates") or {}
    if count >= 2 and duplicates.get("total"):
        sections += [
            render_duplicates_markdown(duplicates, ordinal="十六").rstrip("\n"),
            "",
        ]

    # 第十七节：语义质量（clean 与否统一走 render——单点文案防漂移）
    semantic = payload.get("semantic_health") or {}
    if count and semantic.get("records"):
        sections += [
            render_semantic_health_markdown(
                semantic, ordinal="十七"
            ).rstrip("\n"),
            "",
        ]

    # 第十八节：响应窗口（发布→截止）——deadline 字段首次进分析面
    windows = payload.get("response_windows") or {}
    if windows.get("sample_count"):
        line = windows["short_window_days"]
        rows = [
            ["有效样本 / 缺日期 / 倒挂", (
                f"{windows['sample_count']} / {windows['missing_count']}"
                f" / {windows['invalid_count']}"
            )],
            ["中位（天）", str(windows["median_days"])],
            ["P25 / P75（天）", (
                f"{windows['p25_days']} / {windows['p75_days']}"
            )],
            ["最短 / 最长（天）", (
                f"{windows['min_days']} / {windows['max_days']}"
            )],
            [f"短窗（< {line} 日）", (
                f"{windows['short_window_count']} 条"
                f"（占有效样本 {_fmt_pct(windows['short_window_rate'])}）"
            )],
        ]
        sections += [
            "## 十八、响应窗口期（发布→截止，天）",
            "",
            _render_table(["指标", "值"], rows),
            "",
        ]
        if windows.get("short_window_examples"):
            example_rows = [
                [
                    example["project_name"],
                    str(example["window_days"]),
                    example["region"] or "——",
                    example["publish_date"],
                    example["deadline"],
                ]
                for example in windows["short_window_examples"]
            ]
            sections += [
                f"### 最紧迫短窗 Top {len(example_rows)}（供人工复核）",
                "",
                _render_table(
                    ["项目", "窗口(天)", "区域", "发布日", "截止日"],
                    example_rows,
                ),
                "",
            ]
        sections += [
            "注：短窗是**研究提示非违规认定**——法定最短 20 日的起算点是",
            "「招标文件开始发出之日」，本节以公告发布日近似（**偏短估计**）；",
            "竞争性磋商/询价等采购方式法定期限更短。截止早于发布的倒挂",
            "记录是数据问题（十七节揭示），不进本节分布。",
            "",
        ]

    # 第十九节：代理机构画像（agency 字段首次进分析面——与八节
    # 采购人/十二节供应商三位对偶）
    agencies = payload.get("agency_profiles") or []
    if agencies:
        rows = [
            [
                profile["agency"],
                str(profile["project_count"]),
                _fmt_money(profile["budget_total"]),
                _fmt_money(profile["budget_mean"]),
                str(profile["purchaser_count"]),
                "、".join(profile["categories"]) or "——",
            ]
            for profile in agencies
        ]
        sections += [
            "## 十九、代理机构画像（代理项目数 Top）",
            "",
            _render_table(
                ["代理机构", "项目数", "代理项目预算合计(万)", "平均预算(万)", "合作采购人数", "领域"],
                rows,
            ),
            "",
            "注：无代理记录（采购人自采等）不参与聚合；预算口径只计有值样本（样本数见 payload budget_sample_count），缺失不折零。",
            "",
        ]

    # 第二十节：品类分布（category 字段首次进分析面——抽取面
    # 自由文本，精确匹配归并不做词表归一）
    categories = payload.get("category_distribution") or {}
    if categories.get("filled_count"):
        cat_rows = [
            [
                entry["category"],
                str(entry["count"]),
                _fmt_money(entry["budget_total"]),
                _fmt_money(entry["budget_mean"]),
                str(entry["budget_sample_count"]),
                str(entry["awarded_count"]),
            ]
            for entry in categories["categories"]
        ]
        distinct = categories["distinct_count"]
        shown = len(categories["categories"])
        overflow = f"（仅列 Top {shown} / 共 {distinct} 类）" if shown < distinct else ""
        # filled_count>0 保证 filled_rate 非 None（分母非零）
        missing_rate = 1 - categories["filled_rate"]
        sections += [
            "## 二十、品类分布",
            "",
            _render_table(
                ["品类", "项目数", "预算合计(万)", "平均预算(万)", "预算样本数", "定标数"],
                cat_rows,
            ),
            "",
            f"注：品类为抽取面自由文本，清洗后**精确匹配**归并（近义不折叠——映射由研究者判断）；"
            f"填充 {_fmt_pct(categories['filled_rate'])}（缺 {_fmt_pct(missing_rate)}，七节填充率已揭示）{overflow}。",
            "",
        ]

    # 第二十一节：平台来源（source_url 字段首次进分析面）——
    # 发布平台分布 + 与十六节簇交叉的跨平台转发实证
    platforms = payload.get("platform_distribution") or {}
    if platforms.get("sample_count"):
        platform_rows = [
            [
                entry["platform"],
                str(entry["count"]),
                _fmt_money(entry["budget_total"]),
                _fmt_money(entry["budget_mean"]),
                entry["latest_date"] or "——",
            ]
            for entry in platforms["platforms"]
        ]
        sections += [
            "## 二十一、平台来源分布",
            "",
            _render_table(
                ["发布平台", "项目数", "预算合计(万)", "平均预算(万)", "最近发布"],
                platform_rows,
            ),
            "",
            f"注：域名归一（小写、去首 www.，其余子域保留）；"
            f"无可用 URL {platforms['missing_count']} 条如实计缺。",
            "",
        ]
        multi = platforms.get("multi_platform") or {}
        if multi.get("clusters"):
            multi_rows = [
                [
                    str(example["size"]),
                    example["normalized"] or "（空）",
                    "、".join(example["platforms"]),
                ]
                for example in multi["examples"]
            ]
            sections += [
                f"### 跨平台转发信号（{multi['clusters']} 簇 / 涉及 {multi['records']} 条）",
                "",
                _render_table(
                    ["簇大小", "归一后项目名", "平台跨度"], multi_rows
                ),
                "",
                "注：同一近重复簇（十六节）成员出现在 ≥2 个平台——多平台转发的**实证**（非猜测）；簇内缺 URL 成员不参与判定。",
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
    body = "\n".join(sections)
    # R63：目录注入（标题块后）——15 节长报告可导航
    toc = build_toc(body)
    if toc:
        lines = body.split("\n")
        # 标题元信息块（# 标题 + 空行 + 摘要列表）后、首个 ## 节前插入
        first_section = next(
            (i for i, ln in enumerate(lines) if ln.startswith("## ")), None
        )
        if first_section:
            lines.insert(first_section, toc.rstrip("\n"))
            lines.insert(first_section + 1, "")
            body = "\n".join(lines)
    return body
