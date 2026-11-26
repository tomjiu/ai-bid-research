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
    """P5b 初始起草指令（canonical 口径注入版——修复方向②落地 + 批四身份锚）。

    审计实锚（realagent-113-20261122 成品对照主文件 ground truth）：
    - 段121/171/261 三处大写幻觉（玖拾陆万/肆拾捌万/捌万）均为无源
      数字自由发挥——正源是「肆万陆仟圆整￥46000」（须知前附表 3.5.1）；
    - 段55 把主文件 1.8 条最高投标限价（设备 4,810,365/服务 136,000）
      原样抄成自己分项报价且分项和 ≠ 总报价；
    - 段301 履约保证金「合同金额 10%」无源费率。

    批四实锚（v3-r3 成品 770 段全文人工通读 + ground truth 反查——
    「身份锚定缺失」型幻觉，比金额漂移更深一层）：
    - 项目名张冠李戴×3：业绩材料项目名「智慧园区弱电工程」被当作本项目名
      （正名「淮安本地视频能力平台建设」全文仅 2 次且都在 REQ 引用里）；
    - 业绩虚构细节：一份合成业绩写成两份（250万+180万凑430万、合同
      日期、范围全编）——为凑资格线「累计不低于200万」虚构达标数；
    - 分项无源凑数：设备 4,710,365/服务 89,635（恰好凑和=480万过
      「分项和=总价」门——门拦不住凑数幻觉，须指令层禁写）；
    - 投标函抬头写「验收#113-真实LLM起草」（验收项目名泄漏进正式文书）；
    - 24小时/30日等时限无源挪用；联合体/组织形式/备选方案正文正反声明。

    → 首稿即注入统一口径 + 项目身份锚 + 无源数字禁令，比 P6.5 门后
    修复省一轮真实 LLM 重起草（预防优于检出-修复）。
    """
    return (
        "按招标文件逐项响应，突出同类业绩与实施方案；引用只准用列出的 REQ/EV 编号。"
        # ---- 批四：项目身份锚（防张冠李戴/抬头写错/业绩虚构）----
        "【项目身份（正文必须锁定，不得改写或自由发挥）】"
        "本项目为「中国电信股份有限公司淮安分公司2026年淮安本地视频能力平台"
        "建设采购项目」（招标编号 JSCGXM202610210082001001），"
        "招标人为中国电信股份有限公司淮安分公司，投标函等格式件抬头必须"
        "写招标人全称；"
        "业绩材料中的项目名（如「智慧园区弱电工程」）是过往业绩项目名，"
        "不得将其当作本项目名称或本项目范围描述；"
        "业绩响应只能按 EV 证据件实述（仅一件类似业绩合同-智慧园区弱电"
        "工程），不得虚构业绩合同份数、金额、签订日期或累计金额去凑"
        "资格线，资格线达标与否按证据实况如实表述；"
        # ---- 批六③：业绩实载口径硬注入（r5 段18 实锚——凑线/日期矛盾根治面）
        # 禁令挡不住 LLM 编具体值（r5 把资格线值 200 万写成业绩金额、把窗口期"
        # 虚写进日期断言）；唯一根治面是把证据件实载口径直接注入——抄对而非禁止编错。
        "业绩实载口径（EV-0065 类似业绩合同，以证据件为准）：合同金额"
        " 260 万元、签订日期 2023-05-20——正文表述业绩金额/签订日期必须"
        "与此口径一致；不得把资格线数值（累计不低于 200 万）当作业绩金额"
        "写入（那是资格门槛不是实绩）；证据签订日期不在资格窗口"
        "（2023-10-01 起）内的，按证据实况如实表述，不得虚写窗口内日期；"
        "业绩一览表金额/日期栏与正文口径必须一致（不得正文有数而表【待填】）；"
        "本次投标为独立投标（非联合体，不接受联合体投标）；本项目由招标人"
        "委托招标代理机构（中邮通建设咨询有限公司）组织招标；"
        "不递交备选投标方案（投标人须知前附表未另行允许）。"
        # ---- 金额工期口径（v2 批已锚）----
        "全文金额与工期口径统一（与招标文件须知前附表正源一致）："
        "投标总报价 4,800,000 元（肆佰捌拾万元整），"
        "分项报价之和必须等于投标总报价，"
        "不得把最高投标限价当作本方分项报价；"
        "投标保证金 46,000 元（肆万陆仟圆整）；"
        # 批七 D5（#113 全链审计——r6b SEC-0018/0043 实锚）：大写近形
        # 错字「肆万陆仌」（仌≠仟）→ 中文解析 40006 → E_AMOUNT_CONFLICT
        # 假 BLOCKER。规范字表硬注入：仟/佰/拾是规范大写位字，近形错字
        # （仌/什/阡）禁止。
        "大写金额用规范位字（仟/佰/拾/万），逐字核对不得写近形错字"
        "（仌不是仟、什不是拾）——大写错一字即金额冲突废标级拦门；"
        "工期 37 日历天；投标有效期 90 天。"
        "分项报价（设备部分/服务部分报价）一律不写具体数值，"
        "只作「分项报价之和等于投标总报价」的纪律声明；"
        "履约保证金按招标文件原文表述（金额见前附表），不写具体数值。"
        # ---- 无源数字禁令（v2 批已锚 + 批四扩面）----
        "除上述口径外，任何金额、费率或百分比数字必须有招标文件条款依据，"
        "不得引入无源数字；任何时限数字（小时数/日数）亦须有条款依据，"
        "不得自创响应时限或挪用其他条款时限。"
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

    批六②（r5 审读 C4）：证据型评分点（证书/演示/样机/检测报告/
    获奖证明类——依赖外部证据件的点）追加证据响应纪律——r5 实测 P9
    34/39 缺的 5 点全是此类：正文无对应证据件可引时 LLM 静默跳过。
    指令要求：台账有该类证据件 → 按 EV 编号显式引用；没有 → 如实
    【待补】声明（评委按点给分，静默跳过 = 该点零分且暴露材料缺口）。
    """
    pts = [p for p in (points or []) if p]
    if not pts:
        return ""
    enumerated = "；".join(f"（{i}）{p}" for i, p in enumerate(pts, 1))
    base = (
        "评分细则响应纪律（#113 审计批三）：本节对应招标文件评分细则点，"
        "正文须逐点显式响应——每点单独成段或列表项，保留该点关键术语"
        "原文（评委按点给分，未逐点响应=该点扣分）。需逐点响应的细则点："
        + enumerated
    )
    # 批六②：证据型点检测（证书/演示/样机/检测报告/获奖/证明类关键词）。
    evidence_keywords = (
        "证书", "演示", "样机", "检测报告", "获奖", "认证", "证明文件",
    )
    hits = [p for p in pts if any(k in p for k in evidence_keywords)]
    if not hits:
        return base
    return base + (
        "证据响应纪律（#113 审计批六②）：上述评分点中「"
        + "、".join(hits)
        + "」属证据型评分点——正文必须显式声明证据处置：台账有对应证据件"
          "的按 EV 编号显式引用（如 [EV-0063]）；无对应证据件的如实写明"
          "【待补：待供应商补充该证据件】（声明材料缺口），不得静默跳过"
          "或空泛套话应付——评委按点给分，静默跳过 = 该点零分。"
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


def section_points_for_repair(coverage_data: dict[str, Any]) -> dict[str, dict[str, list[str]]]:
    """check_scoring_coverage 响应 → 每映射叶的**全量**评分点（批七 D3）。

    P6.6 修复轮实锚缺陷（r6b：SEC-0028 覆盖 7→8→31 回退）：重起草指令
    只注入未命中点 → 模型重写把已命中点丢了。本函数按叶聚合该叶承载的
    全部细则点并分「missing/hit」两栏——修复指令双注入：未命中点逐点
    补齐 + 已命中点关键术语保留（防回退）。

    返回 {sec: {"missing": [点…], "hit": [点…]}}；无点叶不出现在键位。
    """
    criteria = coverage_data.get("criteria") or []
    out: dict[str, dict[str, list[str]]] = {}
    for c in criteria:
        pts = c.get("points") or []
        if not pts:
            continue
        for sec in (c.get("mapped_sections") or []):
            slot = out.setdefault(sec, {"missing": [], "hit": []})
            for p in pts:
                point = p.get("point") or ""
                if not point:
                    continue
                if p.get("hit_section") is None:
                    if point not in slot["missing"]:
                        slot["missing"].append(point)
                else:
                    if point not in slot["hit"]:
                        slot["hit"].append(point)
    return out


def retained_points_hint(hit_points: list[str]) -> str:
    """已命中点保留纪律段（批七 D3——防回退注入面）。

    重起草丢已命中点 = 覆盖回退（r6b 实锚 7→8→31）；指令显式点名须
    保留关键术语原文的已命中点——字面命中口径下丢词 = 丢点。
    """
    pts = [p for p in (hit_points or []) if p]
    if not pts:
        return ""
    enumerated = "；".join(f"（{i}）{p}" for i, p in enumerate(pts, 1))
    return (
        "已命中点保留纪律（#113 全链审计批七）：本节已有评分细则点在正文中"
        "命中——重起草后以下各点关键术语必须原文保留（丢词即丢分）："
        + enumerated
        + "。重起草只增不删：新增未命中点响应，不改写/删除已命中点对应段。"
    )


def point_table_hint(all_points: list[str]) -> str:
    """评分细则逐点响应对照表兜底指令段（批九——r6 实弹终验实锚）。

    r6 实锚：P6.6「逐点织入正文」五轮不收敛——残余三点
    （合同内容页/合同金额页/所提供人员2026年3月份）每轮注入仍被
    LLM 重写丢词，且整节重写两次触发覆盖回退（49→21 / 49→46）。
    投标实务正路 = 评分办法逐点响应对照表：表格「评分细则点」列
    逐字复述点原文（一字不差）——字面命中口径下结构性保证覆盖，
    复制入表对 LLM 是远弱于织入正文的指令（复制类任务）。
    """
    pts = [p for p in (all_points or []) if p]
    if not pts:
        return ""
    enumerated = "；".join(f"（{i}）{p}" for i, p in enumerate(pts, 1))
    return (
        "评分细则逐点响应对照表纪律（#113 审计批九）：本节正文照常撰写，"
        "并在节末追加「评分细则逐点响应对照表」作为收口要件——表格两列："
        "第一列「评分细则点」，第二列「我方响应」。第一列必须逐字复述"
        "下列各点原文（一字不差，评委按点给分，对照表即逐点响应载体）；"
        "第二列写响应承诺与对应材料出处："
        + enumerated
    )


def req_citation_hint(uncovered_reqs: list[str]) -> str:
    """未覆盖 REQ 逐条补引用指令段（批十 P6.7——候补面落地）。

    r7 实锚：real 生成器 prompt 已含 REQ 清单与引用规则（llm.rs 系统规则
    2/3 + 素材面逐条「要求条款」），LLM 对低显著度样板条款（1.8.1 不得
    存在情形 / 1.9 货物原产地 / 1.10 投标费用 / 1.11 保密 / 2.2 踏勘
    现场等——r7 共 10 条）仍丢 [REQ-xxxx] 标注。指令逐条点名未覆盖
    REQ，要求「针对 [REQ-xxxx]（类别）……」形态逐条显式响应。
    """
    reqs = [r for r in (uncovered_reqs or []) if r]
    if not reqs:
        return ""
    enumerated = "、".join(f"[{r}]" for r in reqs)
    return (
        "REQ 引用补齐纪律（#113 审计批十）：本节绑定条款中以下 REQ 在"
        "正文未被显式引用：" + enumerated + "。重起草须对上述每条 REQ 单独"
        "成段显式响应——段落首「针对 [REQ-xxxx]（类别）要求，我方响应：……」"
        "编号逐字写入正文（引擎按 [REQ-xxxx] 字面引用判覆盖，语义等价"
        "表述不识别；缺引用 = 该条款无响应面，审校按未回应处理）；"
        "不得合并多条款省略编号。"
    )


def retained_req_citation_hint(covered_reqs: list[str]) -> str:
    """已覆盖 REQ 引用保留纪律段（批十 P6.7——批七 D3 对偶面）。

    整节重起草换全文——已覆盖 REQ 的显式引用必须点名保留（只增不删），
    否则修复 A 缺口洗掉 B 覆盖（P6.6 覆盖回退 r6b 7→8→31 同族）。
    """
    reqs = [r for r in (covered_reqs or []) if r]
    if not reqs:
        return ""
    enumerated = "、".join(f"[{r}]" for r in reqs)
    return (
        "已覆盖 REQ 保留纪律（#113 审计批十）：本节正文已显式引用下列"
        "REQ——重起草后仍须逐条保留引用与对应响应段（只增不删：新增"
        "未覆盖 REQ 的响应段，不改写/删除已覆盖 REQ 的既有段）："
        + enumerated
    )


def req_response_list_hint(uncovered_reqs: list[str]) -> str:
    """逐 REQ 显式响应段兜底指令段（批十 P6.7——批九 G1 对偶）。

    织入正文 ≥2 轮不收敛（LLM 对低显著度条款反复丢引用）→ 逐 REQ
    响应段兜底：每条 REQ 各写一段「针对 [REQ-xxxx]（类别）要求，我方
    响应：……」——段落首编号逐字写入是字面引用口径下的结构性保证
    （同 P6.6 对照表兜底的「复制类指令远弱于织入正文」机理）。
    """
    reqs = [r for r in (uncovered_reqs or []) if r]
    if not reqs:
        return ""
    enumerated = "、".join(f"[{r}]" for r in reqs)
    return (
        "逐 REQ 显式响应段兜底纪律（#113 审计批十）：本节前轮织入正文"
        "未收敛，本轮改逐 REQ 响应段形态收口。对下列每条 REQ 各写一段"
        "「针对 [REQ-xxxx]（类别）要求，我方响应：……」的独立段落："
        + enumerated + "。段落首编号逐字写入，不得合并省略编号，"
        "不得以概述性段落笼统带过——缺段落即缺响应面。"
    )


def ev_citation_hint(uncited_evs: list[str]) -> str:
    """零援引 EV 补齐指令段（批十一 P6.8——r7 实锚 EV-0064 营业执照）。

    r7 实锚：P9.5 证据引用 2/3——EV-0064 注册后全文 0 援引。引擎口径
    注记：uncited_evs 是信息面（绑定集内未援引——非全部证据都必须在每
    节援引）；本 hint 的判据是**文档级零援引**（全档没有任何一节援引过
    它——审阅面关注项口径），不做每节必须援引的过度收紧。
    """
    evs = [e for e in (uncited_evs or []) if e]
    if not evs:
        return ""
    enumerated = "、".join(f"[{e}]" for e in evs)
    return (
        "证据援引补齐纪律（#113 审计批十一）：本标书已注册证据件 "
        + enumerated + " 在全部正文中未被援引过（零援引）——重起草须在本节"
        "为其各写显式援引表述：写明证据编号与证据名称（如「[EV-0064]"
        "（营业执照）：本方持有该证据并已登记台账，作为本项资格的佐证」），"
        "编号逐字写入正文；不得静默跳过（注册而零援引 = 证据件形同虚设，"
        "审阅按无佐证处理）。"
    )


def retained_ev_citation_hint(cited_evs: list[str]) -> str:
    """已援引 EV 保留纪律段（批十一 P6.8——r7 实锚 EV-0063 ×21 次援引）。

    整节重起草换全文——已援引 EV 的引用必须点名保留（只增不删），
    否则修复 EV-0064 洗掉 EV-0063（与 P6.6/P6.7 保留纪律同族）。
    """
    evs = [e for e in (cited_evs or []) if e]
    if not evs:
        return ""
    enumerated = "、".join(f"[{e}]" for e in evs)
    return (
        "已援引证据保留纪律（#113 审计批十一）：本节正文已显式援引下列"
        "证据件——重起草后仍须逐条保留援引表述与对应佐证段（只增不删："
        "新增零援引证据的援引段，不改写/删除已援引证据的既有佐证段）："
        + enumerated
    )


def ev_statement_hint(uncited_evs: list[str]) -> str:
    """逐 EV 援引段兜底指令段（批十一 P6.8——P6.7 响应段兜底对偶）。

    织入正文 ≥2 轮不收敛（LLM 对援引反复丢编号）→ 逐 EV 援引段兜底：
    每条零援引 EV 各写一段独立佐证段——编号逐字写入是字面援引口径下
    的结构性保证（同 P6.6 对照表/P6.7 响应段兜底的「复制类指令远弱于
    织入正文」机理）。
    """
    evs = [e for e in (uncited_evs or []) if e]
    if not evs:
        return ""
    enumerated = "、".join(f"[{e}]" for e in evs)
    return (
        "逐证据援引段兜底纪律（#113 审计批十一）：本节前轮织入正文未收敛，"
        "本轮改逐证据独立佐证段形态收口。对下列每条证据各写一段「[EV-xxxx]"
        "（证据名称）：本方持有该证据并已登记台账，作为对应资格/业绩要求的"
        "佐证」的独立段落：" + enumerated + "。段落首编号逐字写入，不得合并"
        "省略编号，不得以概述性段落笼统带过——缺段落即缺佐证面。"
    )


# ---------------------------------------------------------------- 批#221


def p65_retention_payload(pts_hint, pts_hit, uncovered_reqs, covered_reqs, cited_evs):
    """P6.5 blocker 重起草指令的补齐/保留尾（#221——指令组装抽为可测函数）。

    Lead 独立审查实锚（issue #221）：P6.5 是修复链**最后**一个整节重写入口
    （其后无任何轮次再兜底），指令只带评分点/REQ 双注入而缺**活体已援引
    EV 的显式保留**——P6.8 刚收口的证据引用会被链末 blocker 重起草洗掉。

    入参全部取**活体** check_bid_quality / check_scoring_coverage 面：
    pts_hint = 本节全量点（missing+hit，驱动侧含 POINTS_MAP 兜底解析）；
    pts_hit = 当前已命中点（保留面）；uncovered/covered_reqs = REQ 面；
    cited_evs = 本节当前已援引 EV（保留面——只增不删）。
    """
    return (scoring_points_hint(pts_hint)
            + retained_points_hint(pts_hit)
            + req_citation_hint(uncovered_reqs)
            + retained_req_citation_hint(covered_reqs)
            # 批#221 修复：链末重写入口的 EV 保留——P6.8 收口面不随行
            # 即被洗掉（Lead 顺序回退登记）。cited_evs 同源 q_r 活体响应。
            + retained_ev_citation_hint(cited_evs))


def p66_repair_instruction_tail(pts_missing, pts_hit, covered_reqs, cited_evs, stuck):
    """P6.6 细则覆盖修复轮指令尾（#221——REQ/EV 保留补齐 + 抽为可测函数）。

    P6.6 同为整节重写入口：REQ/评分点洗掉有 P6.7/P6.6 自愈轮次兜底，
    但 EV 节级已援引洗掉**不**触发 P6.8 重收口（P6.8 判据是文档级
    零援引——别节仍援引即不复活本节）。故 P6.6 指令尾必须携带
    REQ/EV 保留纪律；补齐面（REQ 织入）仍归 P6.7（不前置抢跑）。
    stuck ≥ 2 切对照表兜底（批九 G1，点原文列逐字复述）。
    """
    if stuck >= 2:
        core = (point_table_hint(list(pts_missing) + list(pts_hit))
                + retained_points_hint(pts_hit))
        closer = (" 本节前轮逐点织入正文未收敛——对照表兜底重起草："
                  "表第一列逐字复述点原文（一字不差），正文照常撰写"
                  "不少于 600 字。")
    else:
        core = (scoring_points_hint(pts_missing)
                + retained_points_hint(pts_hit))
        closer = (" 本节当前版本未逐点命中上述评分细则——重起草逐点"
                  "补齐，正文不少于 600 字。")
    return (core
            # 批#221 修复：REQ/EV 保留随行（REQ 补齐仍归 P6.7 轮次）。
            + retained_req_citation_hint(covered_reqs)
            + retained_ev_citation_hint(cited_evs)
            + closer)


def p67_repair_instruction_tail(uncovered_reqs, covered_reqs, pts_missing,
                                pts_hit, cited_evs, stuck):
    """P6.7 REQ 引用补齐修复轮指令尾（#221——EV 保留补齐 + 抽为可测函数）。

    P6.7 整节重写洗掉的节级 EV 援引不触发 P6.8 重收口（判据文档级
    零援引）——cited_evs 保留纪律（只增不删）必须随行。评分点双注入
    为批十一残余修（P6.6 收口防洗）。
    stuck ≥ 2 切逐 REQ 响应段兜底（批九 G1 对偶）。
    """
    if stuck >= 2:
        head = req_response_list_hint(uncovered_reqs)
        closer = (" 本节前轮逐条织入未收敛——逐 REQ 响应段兜底"
                  "重起草，正文照常不少于 600 字。")
    else:
        head = req_citation_hint(uncovered_reqs)
        closer = (" 本节当前版本未逐条引用上述 REQ——重起草逐条"
                  "补引用，正文不少于 600 字。")
    return (head
            + retained_req_citation_hint(covered_reqs)
            + scoring_points_hint(pts_missing)
            + retained_points_hint(pts_hit)
            # 批#221 修复：EV 保留随行——节级已援引洗掉不触发 P6.8
            # 重收口（判据文档级零援引）。
            + retained_ev_citation_hint(cited_evs)
            + closer)


def p68_repair_instruction_tail(fresh_evs, stuck_evs, cited_evs, uncovered_reqs,
                                covered_reqs, pts_missing, pts_hit):
    """P6.8 证据引用补齐修复轮指令尾（批十一全栈——#221 抽为可测函数）。

    完整保留栈样板（评分点 + REQ + EV 三层补齐/保留）——P6.5/P6.6/
    P6.7 的保留补齐即按此对齐；P6.5 保留回归门的定向修复指令亦
    复用本尾（全栈注入——修复本身不得引入新回退）。
    """
    return (ev_citation_hint(fresh_evs)
            + ev_statement_hint(stuck_evs)
            + retained_ev_citation_hint(cited_evs)
            + req_citation_hint(uncovered_reqs)
            + retained_req_citation_hint(covered_reqs)
            + scoring_points_hint(pts_missing)
            + retained_points_hint(pts_hit)
            + " 本节重起草补齐上述零援引证据的显式援引，正文不少于 600 字。")


def retain_gate_repair_instruction(fresh_evs, unc_reqs, cov_reqs, cited_evs,
                                   pts_missing, pts_hit):
    """批十三：保留回归门定向修复指令——p68 全栈 + 点对照表。

    r8 实锚（realagent-113-v3-20261126-r8）：P6.6 表模式收口 52/52 后
    被 P6.7 织入式重写洗掉 7 点（「功能证明需充分」×4 等短碎片点——
    r6 家族织入不收敛形态）——门修复必须带表列逐字复述的结构性载体
    （批九 G1：复制类指令远弱于织入正文），否则门修复本身对短碎片点
    不收敛（有界两轮耗尽即假终局）。EV/REQ/点补齐 + 保留全栈随行
    （修复本身不得引入新回退）。
    """
    return (p68_repair_instruction_tail(
                fresh_evs, [], cited_evs, unc_reqs, cov_reqs, pts_missing, pts_hit)
            + point_table_hint(list(pts_missing) + list(pts_hit)))


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
    cwp = cov.get("criteria_with_points") or 0
    ctt = cov.get("criteria_total") or 0
    lines.append(f"| 细则覆盖 | criteria {ctt} · 拆点细则 "
                 f"{cwp} · points {cov.get('points_total')} · "
                 f"covered {cov.get('points_covered')} · ratio {ratio_s}——无枚举形态细则 "
                 f"{ctt - cwp} 条不拆点不虚构"
                 f"（批七 D4 诚实面：P9 分母仅拆点细则） |")
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
