"""P6.8 证据引用补齐修复轮的执行位置契约（批十一——P6.6/P6.7 契约同族）。

r7 实锚（artifacts/realagent-113-v3-20261126-r7 metrics.evidence_citation）：
    cited=[EV-0063, EV-0065] uncited=[EV-0064]——营业执照全文 0 援引。

根因双层：
    ①绑定面缺口：P4 绑定循环只绑 quals[0]/perfs[0]——EV-0064（第二个
    qualification 件）注册后从未绑定任何 REQ 组；不绑定即不进任何节的
    per-section 素材面（draft.rs bound_evidence_ids），且起草器剔除
    「不在已知集」的引用——LLM 写了 [EV-0064] 也会被剥掉。
    ②引用面无修复轮：P6.5（blocker）/P6.6（评分点）/P6.7（REQ 引用）
    之后唯独 EV 引用无修复面——evidence_citation 只在 P9.5 落盘登记。

契约（源级结构断言——驱动脚本无法离线单跑，结构即行为）：
    1. P6.8 修复轮在 P6.7 之后、首个全稿 validate_bid_document 之前
       （Drafting 态内——E_STATE 纪律）；
    2. 判据是**文档级零援引**（registered − 各节 cited_evs 并集）——
       不做「每节必须援引」的过度收紧（引擎口径：uncited_evs 是信息面）；
    3. P4 绑定必须全量（所有 qualification/performance EV 各绑其组）；
    4. 重起草指令带完整保留栈：评分点（P6.6 收口）+ REQ 引用（P6.7
       收口）+ 已援引 EV——整节重起草换全文，缺哪层即洗哪层；
    5. repair 留痕 kind="ev-cite" 独立（不污染 P6.6/P6.7 计数）；
    6. ≥2 轮不收敛切逐 EV 援引段兜底；5 轮上限耗尽如实登记。
"""
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
import realagent_evidence  # noqa: E402

DRIVER = REPO / "scripts" / "run_real_llm_path.py"


def _src() -> str:
    return DRIVER.read_text(encoding="utf-8")


def _p68_block(s: str) -> str:
    m = re.search(r"# ---- P6\.8 证据引用补齐修复轮", s)
    assert m, "P6.8 修复轮代码块缺失（批十一面被误删？）"
    m_val = re.search(r'must\(\s*"validate_bid_document"', s)
    end = m_val.start() if m_val else len(s)
    return s[m.start():end]


def test_p68_before_first_full_validate():
    """契约 1：P6.8 在首个全稿 validate 之前（否则 E_STATE 必崩）。"""
    s = _src()
    m_p68 = re.search(r"# ---- P6\.8 证据引用补齐修复轮", s)
    m_val = re.search(r'must\(\s*"validate_bid_document"', s)
    assert m_p68, "P6.8 修复轮代码块缺失"
    assert m_val, "validate_bid_document 调用缺失"
    assert m_p68.start() < m_val.start(), (
        "P6.8 修复轮位于首个全稿 validate 之后——状态机不放行整节重起草"
        "（E_STATE，v3 SEC-0028 崩溃同款）。"
    )


def test_p68_after_p67_before_p65():
    """契约 1 附：P6.8 在 P6.7 之后、P6.5 之前（全在 Drafting 态）。"""
    s = _src()
    m_p67 = re.search(r"# ---- P6\.7 uncovered-REQ 引用补齐修复轮", s)
    m_p68 = re.search(r"# ---- P6\.8 证据引用补齐修复轮", s)
    m_p65 = re.search(r"# ---- P6\.5 BLOCKER 修复轮", s)
    assert m_p67 and m_p68 and m_p65
    assert m_p67.start() < m_p68.start() < m_p65.start(), (
        "P6.8 必须位于 P6.7 之后、P6.5 之前——三者都在 Drafting 态，"
        "P6.5 之后即撞 E_STATE。"
    )


def test_p68_doc_level_never_cited_criterion():
    """契约 2：判据是文档级零援引（registered − cited_evs 并集），非每节。"""
    block = _p68_block(_src())
    assert "cited_evs" in block, "P6.8 未消费 sections[].cited_evs"
    assert re.search(r"never_cited", block), "P6.8 缺文档级零援引判据变量"
    assert "每节" not in block.split("引擎口径注记")[-1][:50] or "信息面" in block, (
        "P6.8 应有引擎口径注记（uncited_evs 是信息面——不做每节必须援引的过度收紧）"
    )


def test_p4_binds_all_qual_and_perf_evs():
    """契约 3：P4 绑定全量——所有 qualification/performance EV 各绑其组
    （r7 根因：只绑 quals[0]，EV-0064 永不绑定）。"""
    s = _src()
    m_p4 = re.search(r"# ---- P4 证据登记", s)
    m_p4b = re.search(r"# ---- 审核门", s)
    assert m_p4 and m_p4b
    block = s[m_p4.start():m_p4b.start()]
    assert "for ev in quals" in block or re.search(
        r"\[(ev, \"qual\") for ev in quals", block), (
        "P4 绑定未遍历全部 qualification EV——EV-0064 注册后不绑定，"
        "不进素材面且引用被起草器剥掉（r7 零援引根因）。"
    )
    assert "for ev in perfs" in block or re.search(
        r"\[(ev, \"perf\") for ev in perfs", block), (
        "P4 绑定未遍历全部 performance EV。"
    )


def test_p68_full_retention_stack():
    """契约 4：P6.8 重起草指令带完整保留栈（评分点 + REQ + EV）——
    整节重起草换全文，缺哪层保留即洗哪层已收口面。
    批#221：指令尾抽为可测函数——行为断言（非源码字符串搜索）。"""
    block = _p68_block(_src())
    assert "p68_repair_instruction_tail" in block, (
        "P6.8 指令尾未接线可测函数——保留栈无法离线行为测试。"
    )
    # 行为断言：三层保留栈真在指令尾产出（活体数据真流进指令）
    tail = realagent_evidence.p68_repair_instruction_tail(
        ["EV-0064"], [], ["EV-0063"], [], ["REQ-0001"],
        ["合同内容页数"], ["培训方案"])
    for face, marker in (
            ("已援引证据保留纪律", "EV-0063"),
            ("已覆盖 REQ 保留纪律", "REQ-0001"),
            ("已命中点保留纪律", "培训方案")):
        assert face in tail and marker in tail, (
            f"P6.8 指令尾丢「{face}」——对应已收口面会被洗掉"
            f"（r6b 回退家族）。"
        )
    assert "证据援引补齐纪律" in tail and "EV-0064" in tail, (
        "P6.8 尾缺零援引 EV 补齐注入（批十一面回退）。"
    )


def test_p68_repair_kind_isolated():
    """契约 5：repair 留痕 kind="ev-cite" 独立——不污染 P6.6/P6.7 计数。"""
    block = _p68_block(_src())
    assert re.search(r'kind.*=.*"ev-cite"|kind": "ev-cite"', block), (
        'P6.8 repair 留痕缺 kind="ev-cite"——复用别家 kind 会污染非收敛计数。'
    )


def test_p68_stuck_fallback_and_round_cap():
    """契约 6：≥2 轮不收敛切逐 EV 援引段兜底（ev_statement_hint）+
    5 轮上限耗尽如实登记。批#221：行为断言升级。"""
    block = _p68_block(_src())
    tail = realagent_evidence.p68_repair_instruction_tail(
        [], ["EV-0064"], [], [], [], [], [])
    assert "逐证据援引段兜底纪律" in tail and "EV-0064" in tail, (
        "P6.8 无逐 EV 援引段兜底——织入正文不收敛无兜底路径。"
    )
    assert re.search(r"ev_round\s*>\s*5", block), "P6.8 缺轮次上限"
    assert "如实登记" in block, "耗尽必须如实登记（不豁免不装绿）"
