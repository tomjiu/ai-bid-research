#!/usr/bin/env python3
"""realagent_evidence.py —— run_real_llm_path 的证据明细层（#113 审计修复批二）。

背景（2026-11-24 机器审计报告评论 5954 + 后续深挖实锤）：

1. **明细在机器、总数在证据包**：validate_bid_document 响应的
   sections[].uncovered_reqs 与 check_scoring_coverage 响应的
   criteria[].points[]{point, hit_section} 逐点明细**引擎已经算出**，
   驱动只落 summary——realagent-metrics.json 只剩
   uncovered_req_total=9 无明细、P9 1/39 哪条命中哪条缺零留痕
   （审计缺口②与「审校素材缺位」的同一根因）。
2. **口径注入只在修复环**：CANON（总报价/保证金/工期）只喂 P6.5
   修复指令，P5b 初始起草 instructions 无 canonical 数字——三处大写
   幻觉（96 万/48 万/8 万）与段55 抄限价都是首稿自由发挥产物，
   修复方向②（canonical 随 PROFILE 注入起草上下文）未落地。
3. **REPORT.md 手写漂移类**：fe9d7ca 手写「含 13 节次修复决策日志」
   而 state 实为 decisions=[]（审计缺口①，状态层已另修）；同批
   tool-call-log.json 驱动写了但归档漏收、REPORT 文件表未列。底稿
   应从机器单一真源（metrics/state/实际文件清单）生成，人只改叙事。

纯函数无副作用（IO 只读），tests 直测。驱动侧落盘仍走
realagent_state.py（原子写）。
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any


def initial_instructions() -> str:
    """P5b 初始起草指令（canonical 口径注入版——修复方向②落地）。

    审计实锚（realagent-113-20261122 成品对照主文件 ground truth）：
    - 段121/171/261 三处大写幻觉（玖拾陆万/肆拾捌万/捌万）均为无源
      数字自由发挥——正源是「肆万陆仟圆整￥46000」（须知前附表 3.5.1）；
    - 段55 把主文件 1.8 条最高投标限价（设备 4,810,365/服务 136,000）
      原样抄成自己分项报价且分项和 ≠ 总报价；
    - 段301 履约保证金「合同金额 10%」无源费率。

    → 首稿即注入统一口径 + 无源数字禁令，比 P6.5 门后修复省一轮
    真实 LLM 重起草（预防优于检出-修复）。
    """
    return (
        "按招标文件逐项响应，突出同类业绩与实施方案；引用只准用列出的 REQ/EV 编号。"
        "全文金额与工期口径统一（与招标文件须知前附表正源一致）："
        "投标总报价 4,800,000 元（肆佰捌拾万元整），"
        "分项报价之和必须等于投标总报价，"
        "不得把最高投标限价当作本方分项报价；"
        "投标保证金 46,000 元（肆万陆仟圆整）；"
        "工期 37 日历天；投标有效期 90 天。"
        "除上述口径外，任何金额、费率或百分比数字必须有招标文件条款依据，"
        "不得引入无源数字。"
    )


# ---------------------------------------------------------------- 批三


def evidence_citation_hint(evidence: list[tuple[str, str, str]]) -> str:
    """P5b 证据引用指令段（#113 审计批三——EV 未引用根治面）。

    v2 实锚（realagent-113-v2-20261124）：3 件注册证据仅 EV-0063（18 次）
    与 EV-0065（1 次）被正文按 ID 引用，EV-0064（营业执照）0 次——
    「真实模型实际调用证据」维度弱通过未根治（v1 换件发生：v1 是
    EV-0065 未用）。注入显式证据清单 + 引用纪律：资格/主体资格类响应
    必须按 EV 编号引用对应证据件（评标时证据不引用=形式分流失）。
    """
    if not evidence:
        return ""
    lines = ["；".join(f"{ev}（{title}）" for ev, _, title in evidence)]
    return (
        "证据引用纪律（#113 审计批三）：本标书已注册证据件 "
        + "、".join(lines)
        + "。凡响应资格条件/主体资格/同类业绩类 REQ，正文必须按证据编号"
          "显式引用对应证据（如 [EV-0063]），并在表述中写明证据名称与"
          "对应关系；证据是评分与符合性判定的实体依据，未引用=该维度"
          "零分险。"
    )


def leaf_points_map(coverage_data: dict[str, Any]) -> dict[str, list[str]]:
    """check_scoring_coverage 响应 → 叶 → 待响应评分点清单（批三 P9 根治面）。

    v2 实锚：细则覆盖 0/39——起草指令从未见过 39 个评分点原文，正文
    自然无从逐点命中。按 criteria[].mapped_sections 把 points[].point
    归到映射叶（P4.6 已逐项映射——36 项决策在场），供 P5b 每叶定向
    注入与 P6.6 定向重起草。
    """
    mapping: dict[str, list[str]] = {}
    for c in coverage_data.get("criteria") or []:
        if not isinstance(c, dict):
            continue
        sids = c.get("mapped_sections") or []
        pts = [p.get("point") for p in (c.get("points") or [])
               if isinstance(p, dict) and p.get("point")]
        if not sids or not pts:
            continue
        for sid in sids:
            mapping.setdefault(sid, []).extend(pts)
    return mapping


def scoring_points_hint(points: list[str]) -> str:
    """单叶评分细则点逐点响应指令段（批三——闭门条件 2 机器面）。

    评分细则点（评标办法中评委按点给分的 point 原文）逐点显式响应是
    投标实务正路；指令要求每点单独成段/列表项、保留要点关键词（字面
    命中口径下「语义等价表述不识别」是引擎已知边界——务实解法是
    响应文本保留关键术语，而非教引擎做语义匹配）。
    """
    pts = [p for p in (points or []) if p]
    if not pts:
        return ""
    enumerated = "；".join(f"（{i}）{p}" for i, p in enumerate(pts, 1))
    return (
        "评分细则响应纪律（#113 审计批三）：本节对应招标文件评分细则点，"
        "正文须逐点显式响应——每点单独成段或列表项，保留该点关键术语"
        "原文（评委按点给分，未逐点响应=该点扣分）。需逐点响应的细则点："
        + enumerated
    )


def aggregate_uncovered_reqs(validate_data: dict[str, Any]) -> dict[str, Any]:
    """validate_bid_document 响应 → 未覆盖 REQ 明细（审计缺口②落盘面）。

    sections[].uncovered_reqs 是引擎已算出的逐章明细；本函数聚合成
    顶层清单（ids + by_section），并与 summary.uncovered_req_total 交叉
    校验——不一致时 mismatch=True 如实留痕（明细面为准，summary 声称值
    另存 summary_reported——审计纪律：机器两处口径不一致不能静默）。
    """
    sections = validate_data.get("sections") or []
    ids: list[str] = []
    by_section: list[dict[str, Any]] = []
    for sec in sections:
        if not isinstance(sec, dict):
            continue
        uc = sec.get("uncovered_reqs") or []
        if not uc:
            continue
        by_section.append({
            "section_id": sec.get("section_id"),
            "uncovered_reqs": list(uc),
        })
        ids.extend(uc)
    reported = (validate_data.get("summary") or {}).get("uncovered_req_total")
    return {
        "total": len(ids),
        "ids": ids,
        "by_section": by_section,
        "summary_reported": reported,
        "mismatch": reported is not None and reported != len(ids),
    }


def aggregate_uncovered_points(coverage_data: dict[str, Any]) -> dict[str, Any]:
    """check_scoring_coverage 响应 → 未命中细则点明细（P9 弱正留痕面）。

    criteria[].points[]{point, hit_section} 中 hit_section=None 的点即
    「写了正文但没逐字命中该细则点」——P9 1/39 弱正的审校素材。每点
    max_score 按均分分摊（criterion max_score / points 数）——与 coverage
    工具 criteria 级口径一致（uncovered 分率 × max）。
    """
    criteria = coverage_data.get("criteria") or []
    uncovered: list[dict[str, Any]] = []
    for c in criteria:
        if not isinstance(c, dict):
            continue
        pts = c.get("points") or []
        if not pts:
            continue
        share = (c.get("max_score") or 0.0) / len(pts)
        for p in pts:
            if isinstance(p, dict) and p.get("hit_section") is None:
                uncovered.append({
                    "criterion_id": c.get("criterion_id"),
                    "point": p.get("point"),
                    "max_score": round(share, 2),
                })
    summary = coverage_data.get("summary") or {}
    return {
        "points_total": summary.get("points_total", 0),
        "points_covered": summary.get("points_covered", 0),
        "uncovered": uncovered,
    }


def report_target(out_dir: str) -> str:
    """REPORT 底稿目标路径：OUT 无 REPORT.md → REPORT.md（首跑即机器底稿）；
    已有（手写叙事/封存包）→ REPORT.generated.md——**不覆盖既有文件**
    （封存不回改 / 洗史防线）。"""
    primary = os.path.join(out_dir, "REPORT.md")
    if not os.path.exists(primary):
        return primary
    return os.path.join(out_dir, "REPORT.generated.md")


def _fmt_thousands(n: Any) -> str:
    try:
        return f"{int(n):,}"
    except (TypeError, ValueError):
        return str(n)


def build_report_md(
    metrics: dict[str, Any],
    state: dict[str, Any],
    out_dir: str,
) -> str:
    """REPORT.md 机器底稿（防手写漂移：fe9d7ca 教训）。

    全部数字取机器单一真源：metrics（字数/覆盖/用量/导出/耗时口径）与
    state（映射决策/修复决策**实留**长度——不写手声称数字）；文件表取
    out_dir 实际文件清单（存在什么列什么——tool-call-log.json 不再漏收）。
    人工半边（条件 3/5）恒标 ⛔ 待人工——不代人工关单纪律。
    """
    val = metrics.get("validate") or {}
    exp = metrics.get("export") or {}
    cov = metrics.get("scoring_coverage") or {}
    usage = metrics.get("llm_usage") or {}
    decisions = len(((state.get("scoring_mapping") or {}).get("decisions")) or [])
    repairs = len(state.get("repair") or [])
    rounds = metrics.get("resume_rounds") or 0
    ratio = cov.get("coverage_ratio")
    ratio_s = f"{ratio * 100:.1f}%" if isinstance(ratio, (int, float)) else "—"

    files = sorted(
        f.name for f in Path(out_dir).iterdir()
        if f.is_file() and f.name != "REPORT.generated.md"
    ) if os.path.isdir(out_dir) else []

    lines: list[str] = []
    lines.append("# realagent 证据包（#113 真实 LLM 通路）——机器底稿")
    lines.append("")
    lines.append("> 本文件由 run_real_llm_path 末尾自动生成（#113 审计修复批二）：")
    lines.append("> 数字全部取 metrics/driver-state 实测，防手写漂移；叙事段与人工判读")
    lines.append("> 由人工在其上修改（机器底稿是起点不是终稿）。")
    lines.append("")
    lines.append("## 链路")
    lines.append("")
    lines.append("| 相位 | 结果（实测） |")
    lines.append("|---|---|")
    lines.append(f"| 主件/REQ | {metrics.get('main_file')} · REQ {metrics.get('req_total')} · 叶 {metrics.get('leaves')} |")
    lines.append(f"| 起草/校验 | drafted {val.get('drafted', '—')} · blocker {val.get('blocker', 0)} · 字数 "
                 f"{_fmt_thousands(val.get('char_total'))}/{_fmt_thousands(val.get('char_target'))}"
                 f"（偏差 {val.get('char_deviation_pct')}%） |")
    lines.append(f"| 修复决策 | 映射决策 {decisions} · 修复决策 {repairs} 节次（state 实留） |")
    lines.append(f"| 导出 | {exp.get('size')} B · {exp.get('chapters_written')} 章 · sha256 {str(exp.get('sha256'))[:16]}… |")
    lines.append(f"| 细则覆盖 | criteria {cov.get('criteria_total')} · points {cov.get('points_total')} · "
                 f"covered {cov.get('points_covered')} · ratio {ratio_s} |")
    lines.append("")
    lines.append("## LLM 用量（llm-usage.json）")
    lines.append("")
    lines.append(f"{usage.get('calls')} calls / {_fmt_thousands(usage.get('total_tokens'))} tokens"
                 f"（模型 {metrics.get('model', 'glm-4-plus')}；断点续跑 {rounds} 轮，"
                 f"累计耗时 {metrics.get('elapsed_s')}s——resume 累计口径）")
    lines.append("")
    lines.append("## 文件（实际清单）")
    lines.append("")
    if files:
        lines.append("| 文件 |")
        lines.append("|---|")
        for name in files:
            lines.append(f"| {name} |")
    else:
        lines.append("（目录不在场——归档时以实际 OUT 为准）")
    lines.append("")
    lines.append("## 诚实边界（#113 闭门五条件——人工半边不代填）")
    lines.append("")
    lines.append("1. 真实语料真实 LLM 起草：以 generator_summary（metrics.export）为准")
    lines.append("2. 语义覆盖 > 0：以 P9 ratio 为准（字面口径局限如实登记）")
    lines.append("3. **人工审校批准：⛔ 未满足——模型审校 ≠ 人工批准（#169 口径），待人工**")
    lines.append("4. P8 导出链通：以 export sha256/size 为准")
    lines.append("5. #115 收官入口：以 acceptance_closeout 接线状态为准（未接线即 ⛔）")
    lines.append("")
    lines.append("**结论：条件 3/5 人工半边未满足前保持 open——不关单（假绿零容忍）。**")
    lines.append("")
    return "\n".join(lines)
