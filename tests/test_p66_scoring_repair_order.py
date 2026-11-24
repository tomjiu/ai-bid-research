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
