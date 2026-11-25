"""P6.6 细则覆盖修复轮的执行位置契约（v3 实弹 E_STATE 崩溃的回归锁）。

v3 实弹实锚（realagent-113-v3-20261124 首跑）：
    [P6.5] 零 blocker（修复 2 节次）
    [P6.6] 细则覆盖修复轮 1: 2 点未命中 → 2 叶定向重起草
    AssertionError: [scoring-repair:SEC-0028]
      {"code": "E_STATE", "what": "当前状态 VALIDATING 不允许调用 draft_response_section"}

根因（引擎设计非 bug，驱动位置是 bug）：
    - bid-tools/service.rs（#243）：validate_bid_document **全稿校验通过**
      即推进 Drafting → Validating（失败留在原态可修订重试）；
    - bid-domain/src/lib.rs allowed_tools()：Validating 态白名单**不含**
      draft_response_section（写作工具不重开——复核期修复走
      rewrite_section_partial/reopen_section 等窄通道，均不适配整节
      重起草语义）；
    - 批三把 P6.6 放在 P6.5 收口之后 = 放在「零 blocker 的那次
      validate」之后——状态已推进 Validating，整节重起草被合法拒绝。

契约（源级结构断言——驱动脚本无法离线单跑，结构即行为）：
    1. P6.6 修复轮必须出现在**首个**全稿 validate_bid_document 调用之前
       （Drafting 态内完成评分点重起草）；
    2. P6.5 修复指令必须携带本节映射评分点（scoring_points_hint +
       POINTS_MAP）—— blocker 重起草换全文，不带点会洗掉 P6.6 已命中的
       细则覆盖（覆盖不回退纪律）。
"""
import re
from pathlib import Path

DRIVER = Path(__file__).resolve().parent.parent / "scripts" / "run_real_llm_path.py"


def _src() -> str:
    return DRIVER.read_text(encoding="utf-8")


def test_p66_before_first_full_validate():
    """契约 1：P6.6 在首个全稿 validate 之前（否则 E_STATE 必崩）。"""
    s = _src()
    m_p66 = re.search(r"# ---- P6\.6 细则覆盖修复轮", s)
    m_val = re.search(r'must\(\s*"validate_bid_document"', s)
    assert m_p66, "P6.6 细则覆盖修复轮代码块缺失（批三面被误删？）"
    assert m_val, "validate_bid_document 调用缺失"
    assert m_p66.start() < m_val.start(), (
        "P6.6 细则覆盖修复轮位于首个全稿 validate 之后——首个通过的全稿"
        "校验已把项目推进 VALIDATING（#243），draft_response_section 将被"
        "状态机拒绝（E_STATE，v3 实弹 SEC-0028 崩溃同款）。修复轮必须"
        "前置到 Drafting 态内执行。"
    )


def test_p66_block_calls_draft():
    """契约 1 附：P6.6 块内是整节重起草（draft_response_section）。"""
    s = _src()
    m_p66 = re.search(r"# ---- P6\.6 细则覆盖修复轮", s)
    m_p65 = re.search(r"# ---- P6\.5 BLOCKER 修复轮", s)
    m_end = re.search(r"# ---- P7", s)
    block = s[m_p66.start(): (m_end.start() if m_end else len(s))]
    assert "draft_response_section" in block, "P6.6 块内无 draft_response_section"
    # 移动后 P6.6 与 P6.5 的相对位置：P6.6 在 P6.5 之前（都在 Drafting 态）
    assert m_p66.start() < m_p65.start(), (
        "P6.6 应整体位于 P6.5 之前（P6.5 首个零 blocker validate 同样会"
        "推进 VALIDATING——P6.6 在其后即崩）。"
    )


def test_p65_split_conflict_repairable():
    """契约 3：非规范键的节内分项金额冲突必须可定向修复（v3-r2 实锚）。

    v3-r2 实弹（realagent-113-v3-20261124-r2）：
        E_AMOUNT_CONFLICT@SEC-0012: 金额冲突：服务部分报价
          在 SEC-0012=46365 与 SEC-0012=89635
        E_AMOUNT_CONFLICT@SEC-0012: 金额冲突：设备部分报价
          在 SEC-0012=100000 与 SEC-0012=4710365
    ——LLM 发明具体分项数且节内自相矛盾；旧规划器因 kind 不在 CANON
    判「不可定向修复」→ 诚实报红退出。修复口径 = v2 复审通过的成品面：
    不写具体分项数值、只声明分项纪律（480万/46,000 canonical 照常）。
    """
    s = _src()
    m_p65 = re.search(r"# ---- P6\.5 BLOCKER 修复轮", s)
    m_p7 = re.search(r"# ---- P7", s)
    assert m_p65 and m_p7
    block = s[m_p65.start(): m_p7.start()]
    # 1) repair_instruction 带 no_split 通道
    assert re.search(r"def repair_instruction\(floor, ban_money, no_split", block), (
        "repair_instruction 缺 no_split 形参——节内分项冲突无法定向修复"
        "（v3-r2 SEC-0012 报红实锚）。"
    )
    # 2) 规划器把「有 pairs 无 kind」路由到重起草而非 unrepairable
    assert re.search(r"if pairs and not kind", block), (
        "E_AMOUNT_CONFLICT 分支缺「pairs and not kind」前置路由——非规范键"
        "冲突仍会掉进不可定向修复。"
    )
    # 3) NO_SPLIT 指令禁止具体分项数值（v2 复审通过的成品口径）
    m_ns = re.search(r"NO_SPLIT = \(", block)
    assert m_ns, "NO_SPLIT 指令常量缺失"
    ns_text = block[m_ns.start(): m_ns.start() + 500]
    assert "分项" in ns_text and ("不写" in ns_text or "不得" in ns_text), (
        "NO_SPLIT 指令未禁止具体分项数值。"
    )
    # 4) 重起草调用处传 no_split
    assert re.search(
        r'repair_instruction\(\s*e\["floor"\],\s*e\["ban"\],', block), (
        "P6.5 调用处未传 no_split——分项冲突修复指令不会生效。"
    )


def test_p65_repair_instruction_carries_points():
    """契约 2：P6.5 修复指令携带本节评分点（覆盖不回退）。"""
    s = _src()
    m_p65 = re.search(r"# ---- P6\.5 BLOCKER 修复轮", s)
    # 新序：P5b → P6.6 → P6 → P6.5 → P7'——P6.5 块的右界是 P7' 门
    m_p7 = re.search(r"# ---- P7", s)
    assert m_p65 and m_p7
    block = s[m_p65.start(): m_p7.start()]
    assert "scoring_points_hint" in block and "POINTS_MAP" in block, (
        "P6.5 修复指令未携带本节映射评分点——blocker 整节重起草会换掉"
        "P6.6 已命中的细则覆盖（正文换全文，点不随行即丢）。"
    )
    # 指令拼装处必须真把 hint 接进 instructions（不是只出现标识符）
    m = re.search(
        r'"instructions":\s*repair_instruction\(e\["floor"\],\s*e\["ban"\]\)'
        r"\s*\+\s*EV_HINT", block)
    assert not m, (
        "P6.5 instructions 仍为裸 repair_instruction+EV_HINT——"
        "需追加 scoring_points_hint(POINTS_MAP…)"
    )


def test_p65_repair_carries_retention_discipline():
    """契约 4（批八 G2——D3 修复不完整的另一半入口）：

    P6.5 blocker 整节重起草换全文时只注入 scoring_points_hint（补齐面）
    而缺 retained_points_hint（已命中点保留纪律）——P6.6 收敛的覆盖
    仍会被 P6.5 洗掉（r6b SEC-0028 覆盖 7→8→31 回退的入口之一）。
    批七 D3 只修了 P6.6 入口；P6.5 必须同款双注入：
    1. 每轮修复前取当前覆盖面（check_scoring_coverage）算 hit/missing；
    2. 重起草指令 = 全量点补齐（scoring_points_hint）+ 已命中点
       保留纪律（retained_points_hint，只增不删）。
    """
    s = _src()
    m_p65 = re.search(r"# ---- P6\.5 BLOCKER 修复轮", s)
    m_p7 = re.search(r"# ---- P7", s)
    assert m_p65 and m_p7
    block = s[m_p65.start(): m_p7.start()]
    assert "retained_points_hint" in block, (
        "P6.5 修复指令缺 retained_points_hint（已命中点保留纪律）——"
        "批七 D3 只修了 P6.6 入口，P6.5 整节重起草仍是覆盖回退入口"
        "（换全文时模型可丢已命中点，r6b SEC-0028 回退同族）。"
    )
    # 每轮取当前 hit 面（不是静态 POINTS_MAP——P6.5 多轮间覆盖会漂移）
    assert "section_points_for_repair" in block, (
        "P6.5 未用 section_points_for_repair 取当前 hit/missing 面——"
        "保留纪律必须基于轮内最新覆盖，静态表会把已丢点误列为保留项。"
    )


def test_p65_cap_direction_blocker_has_directed_discipline():
    """契约 5（批八 G3——方向门 blocker 无定向修复口径）：

    E_BID_CAP_DIRECTION 掉进 P6.5 兜底分支（floor=500）——而
    repair_instruction 不携带 finding 消息（why 只进日志不进指令），
    重起草指令无任何方向纪律 → 模型自然复述「报价高于限价将被否决」
    规则句即再犯（句级三要素共现判 BLOCKER，引述句不放行），轮次
    耗尽 = 假终局（如实报红退出但成品不可用）。r6b SEC-0015 实锚
    正是此 blocker。修：规划器加定向分支（cap_dir 旗标），重起草
    指令注入 CAP_DIR_DISCIPLINE（合规口径「未超过/不高于限价」，
    含规则复述句禁写纪律）。
    """
    s = _src()
    m_p65 = re.search(r"# ---- P6\.5 BLOCKER 修复轮", s)
    m_p7 = re.search(r"# ---- P7", s)
    assert m_p65 and m_p7
    block = s[m_p65.start(): m_p7.start()]
    assert 'code == "E_BID_CAP_DIRECTION"' in block, (
        "P6.5 规划器无 E_BID_CAP_DIRECTION 定向分支——方向门 blocker 走"
        "兜底 floor=500 重起草，无方向口径指令，规则复述句再犯无解。"
    )
    assert "CAP_DIR_DISCIPLINE" in block, (
        "P6.5 缺 CAP_DIR_DISCIPLINE 常量/注入——方向门 blocker 的重起草"
        "必须教模型合规口径（未超过/不高于限价，含规则复述句禁写纪律）。"
    )
    m = re.search(r'CAP_DIR_DISCIPLINE if e\.get\("cap_dir"\)', block)
    assert m, (
        "重起草指令拼装处未按 cap_dir 旗标注入 CAP_DIR_DISCIPLINE——"
        "定向分支置旗而不注入指令 = 修复不生效。"
    )


# ------------------------------------------------- 批九 G1：对照表兜底契约

def test_p66_对照表兜底_历史非收敛叶第二轮起切表模式():
    """契约 4（批九）：P6.6 逐点织入正文五轮不收敛（r6 实锚 49/52，
    残余三点为短碎片点；且整节重写两次覆盖回退 49→21/49→46）——
    历史非收敛叶（含跨 invocation 的 repair 留痕）≥2 轮未收敛必须切
    「逐点响应对照表」模式（point_table_hint——点原文列逐字复述，
    字面覆盖结构性保证）。"""
    s = _src()
    m_p66 = re.search(r"# ---- P6\.6 细则覆盖修复轮", s)
    m_end = re.search(r"# ---- P6\.5 BLOCKER 修复轮", s)
    assert m_p66 and m_end, "P6.6/P6.5 代码块缺失"
    block = s[m_p66.start():m_end.start()]
    assert "point_table_hint" in block, (
        "P6.6 块无对照表兜底（point_table_hint）——短碎片点织入正文"
        "不收敛无兜底路径，P9 残余缺口将永远如实登记。"
    )
    assert re.search(r'sid_stuck', block), (
        "P6.6 块无叶级非收敛计数（sid_stuck）——无法判别哪叶该切表模式。"
    )
    assert re.search(r'kind.*==.*"scoring"|kind.*==.*\'scoring\'', block), (
        "P6.6 块无历史 stuck 预载（从 repair 留痕 kind=scoring 计数）——"
        "断点续跑后非收敛叶首轮仍浪费一次织入正文 LLM 调用。"
    )
    assert re.search(r'stuck\s*>=\s*2', block), (
        "对照表兜底阈值必须 ≥2（首轮织入正文仍要给一次机会——投标"
        "正文织入是首选形态，表格是兜底形态）。"
    )


def test_p66_对照表兜底_表模式仍保留retained防回退():
    """契约 5（批九）：对照表兜底分支必须同时携带 retained_points_hint
    （已命中点保留纪律）——表格是覆盖载体，但正文重写仍可能洗掉已命中
    点（r6 实锚 49→21 回退形态），双注入纪律在表模式不豁免。"""
    s = _src()
    m_p66 = re.search(r"# ---- P6\.6 细则覆盖修复轮", s)
    m_end = re.search(r"# ---- P6\.5 BLOCKER 修复轮", s)
    block = s[m_p66.start():m_end.start()]
    # 表模式分支：instr 组装行内两个 hint 共存
    m_tab = re.search(r"point_table_hint.*?\n", block)
    assert m_tab, "point_table_hint 调用缺失"
    # 找到含 point_table_hint 的 instr 组装块，其内必须也有 retained_points_hint
    seg = block[block.find("point_table_hint") - 200:block.find("point_table_hint") + 600]
    assert "retained_points_hint" in seg, (
        "对照表分支未同时注入 retained_points_hint——表模式丢防回退纪律"
        "（r6 实锚覆盖回退 49→21 同型风险）。"
    )


def test_resume_对已完成EXPORTED项目幂等收口不撞状态门():
    """契约 6（批九 G2——r6 实弹终验后实锚）：EXIT=0 全链完成后项目处于
    EXPORTED 终态——状态机（#243 家族）不放行 draft_response_section。
    对已完成项目重跑驱动器，P6.6 直撞 E_STATE 抛 traceback（EXIT=1，
    留崩溃假象）= 驱动器 UX 缺陷非引擎缺陷。resume 分支必须先查项目
    状态：EXPORTED → 如实报告已完成 + 幂等退出 0。"""
    s = _src()
    m_resume = re.search(r"\[resume\] 续跑", s)
    assert m_resume, "resume 分支缺失"
    # resume 分支（含其后 40 行）必须含 EXPORTED 终态幂等收口
    seg = s[m_resume.start() - 800:m_resume.start() + 1200]
    assert "EXPORTED" in seg and "sys.exit(0)" in seg, (
        "resume 分支无 EXPORTED 终态幂等收口——对已完成项目重跑会在 "
        "P6.6 撞 E_STATE 抛 traceback（EXIT=1 崩溃假象，r6 实锚）。"
    )
