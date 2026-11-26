"""P6.7 uncovered-REQ 引用补齐修复轮的执行位置契约（批十——P6.6 契约同族）。

r7 实锚（artifacts/realagent-113-v3-20261126-r7）：
    [P9.6] 未覆盖 REQ 明细: 10 条（mismatch=False）
      SEC-0035×8（1.8.1 不得存在情形/1.9 货物原产地/1.10 投标费用/
      1.11 保密/2.2 踏勘现场等样板条款）/ SEC-0040×1 / SEC-0062×1

根因（非 prompt 缺口——llm.rs 系统规则 2/3 与素材面已含 REQ 清单
及引用规则）：
    - LLM 对低显著度样板条款丢 [REQ-xxxx] 引用标注；
    - 驱动器有 P6.5（blocker）/P6.6（评分点）两条修复轮，唯独
      REQ 引用无修复面——uncovered_reqs 只在 P9.6 落盘登记，从不修复。

契约（源级结构断言——驱动脚本无法离线单跑，结构即行为）：
    1. P6.7 修复轮必须出现在**首个**全稿 validate_bid_document 调用之前
       （Drafting 态内完成 REQ 引用补齐——E_STATE 纪律，同 P6.6 教训
       v3 首跑 SEC-0028 崩溃实锚）；
    2. 修复面必须取自**活体** check_bid_quality（sections[].uncovered_reqs
       /covered_reqs），不得用静态缓存——多轮间覆盖会漂移（批七 D3 教训）；
    3. repair 留痕 kind 必须独立（"req-cite"——不得复用 "scoring"，否则
       污染 P6.6 sid_stuck 非收敛计数，断点续跑误切对照表兜底）；
    4. ≥2 轮未收敛必须切逐 REQ 显式响应段兜底（批九 G1 对偶——织入
       正文对低显著度条款不收敛，段落首编号逐字写入是结构性保证）；
    5. 两个分支都必须双注入：req_citation_hint/req_response_list_hint
       + retained_req_citation_hint（已覆盖保留纪律，只增不删）。
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


def _p67_block(s: str) -> str:
    m = re.search(r"# ---- P6\.7 uncovered-REQ 引用补齐修复轮", s)
    assert m, "P6.7 修复轮代码块缺失（批十面被误删？）"
    # 块右界 = 下一相位边界（批#221 Lead 指定修正：旧「首个 validate」
    # 右界把 P6.8 块整个包进来——存在性字符串断言可被 P6.8 的字符串
    # 误满足，测试盲区）。
    m_next = re.search(r"# ---- P6\.8 证据引用补齐修复轮", s)
    end = m_next.start() if m_next else len(s)
    return s[m.start():end]


def test_p67_before_first_full_validate():
    """契约 1：P6.7 在首个全稿 validate 之前（否则 E_STATE 必崩）。"""
    s = _src()
    m_p67 = re.search(r"# ---- P6\.7 uncovered-REQ 引用补齐修复轮", s)
    m_val = re.search(r'must\(\s*"validate_bid_document"', s)
    assert m_p67, "P6.7 修复轮代码块缺失"
    assert m_val, "validate_bid_document 调用缺失"
    assert m_p67.start() < m_val.start(), (
        "P6.7 修复轮位于首个全稿 validate 之后——首个通过的全稿校验已把"
        "项目推进 VALIDATING（#243），draft_response_section 将被状态机"
        "拒绝（E_STATE，v3 实弹 SEC-0028 崩溃同款）。修复轮必须前置到"
        "Drafting 态内执行。"
    )


def test_p67_after_p66_and_before_p65():
    """契约 1 附：P6.7 在 P6.6 之后、P6.5 之前（三者都在 Drafting 态，
    顺序 = 评分点收口 → REQ 引用收口 → blocker 修复。"""
    s = _src()
    m_p66 = re.search(r"# ---- P6\.6 细则覆盖修复轮", s)
    m_p67 = re.search(r"# ---- P6\.7 uncovered-REQ 引用补齐修复轮", s)
    m_p65 = re.search(r"# ---- P6\.5 BLOCKER 修复轮", s)
    assert m_p66 and m_p67 and m_p65
    assert m_p66.start() < m_p67.start() < m_p65.start(), (
        "P6.7 必须位于 P6.6 之后、P6.5 之前——P6.5 首个零 blocker"
        "validate 同样推进 VALIDATING，P6.7 在其后即崩。"
    )


def test_p67_block_calls_draft_and_live_quality():
    """契约 1/2：块内是整节重起草 + 活体 check_bid_quality 取面。"""
    block = _p67_block(_src())
    assert "draft_response_section" in block, "P6.7 块内无 draft_response_section"
    assert "check_bid_quality" in block, (
        "P6.7 未用 check_bid_quality 取活体未覆盖面——静态缓存会把轮间"
        "漂移的覆盖误判（批七 D3 教训）。"
    )
    assert "uncovered_reqs" in block, "P6.7 未消费 sections[].uncovered_reqs"
    assert "covered_reqs" in block, "P6.7 未消费 sections[].covered_reqs（保留面）"


def test_p67_repair_kind_isolated_from_scoring():
    """契约 3：repair 留痕 kind="req-cite" 独立——不得混入 P6.6 的
    sid_stuck 计数（kind="scoring" 预载——混用会让 P6.6 误判非收敛切表）。"""
    block = _p67_block(_src())
    assert re.search(r'kind.*=.*"req-cite"|kind": "req-cite"', block), (
        'P6.7 repair 留痕缺 kind="req-cite"——复用 scoring 会污染 P6.6 '
        "非收敛计数（断点续跑误切对照表兜底）。"
    )


def test_p67_stuck_fallback_to_response_list():
    """契约 4：≥2 轮未收敛切逐 REQ 响应段兜底（req_response_list_hint）——
    批九 G1 对偶：织入正文对低显著度条款不收敛，段落首编号逐字写入是
    字面引用的结构性保证。批#221：指令尾抽为可测函数——行为断言。"""
    block = _p67_block(_src())
    assert "p67_repair_instruction_tail" in block, (
        "P6.7 指令尾未接线可测函数——兜底/保留栈无法离线行为测试。"
    )
    # 行为断言：stuck≥2 切响应段兜底；stuck=1 织入补引用
    tail_fb = realagent_evidence.p67_repair_instruction_tail(
        ["REQ-0031"], ["REQ-0032"], [], [], ["EV-0063"], 2)
    assert "逐 REQ 显式响应段兜底纪律" in tail_fb and "REQ-0031" in tail_fb, (
        "≥2 轮未收敛无逐 REQ 响应段兜底——残余缺口将永远如实登记。"
    )
    tail_norm = realagent_evidence.p67_repair_instruction_tail(
        ["REQ-0031"], [], [], [], [], 1)
    assert "REQ 引用补齐纪律" in tail_norm, "stuck=1 应为织入补引用形态。"


def test_p67_both_branches_carry_retained():
    """契约 5：两分支双注入 retained_req_citation_hint（已覆盖 REQ 保留
    纪律）——整节重起草换全文，不点名保留即修复 A 洗掉 B（批七 D3 对偶）。
    批#221：行为断言——两分支真产出保留纪律文本。"""
    for stuck in (1, 2):
        tail = realagent_evidence.p67_repair_instruction_tail(
            ["REQ-0031"], ["REQ-0032", "REQ-0033"], [], [], [], stuck)
        assert "已覆盖 REQ 保留纪律" in tail, (
            f"stuck={stuck} 分支丢已覆盖 REQ 保留纪律——保留纪律只挂单"
            "分支，另一分支仍是回退入口。"
        )
        for req in ("REQ-0032", "REQ-0033"):
            assert req in tail, f"stuck={stuck} 分支保留段未点名 {req}"


def test_p67_round_cap_and_honest_exit():
    """契约附：轮次上限 + 耗尽如实登记（不豁免不装绿——假绿零容忍）。"""
    block = _p67_block(_src())
    assert re.search(r"rq_round\s*>\s*5", block), "P6.7 缺轮次上限（5 轮对齐 P6.6）"
    assert "如实登记" in block, "耗尽时必须如实登记剩余缺口"


def test_p65_repair_carries_req_citation_retention():
    """契约 6（批十——批八 G2 对偶）：P6.5 blocker 整节重起草同样是 REQ
    引用回退入口——换全文不带引用纪律会把 P6.7 收口洗掉（同 scoring 面
    r6b 7→8→31 回退家族）。指令必须双注入 req_citation_hint（未覆盖
    补齐）+ retained_req_citation_hint（已覆盖保留），且每轮取活体
    check_bid_quality 的 REQ 面（validate 响应无 sections[].covered_reqs
    ——不能凑合用 validate 数据）。批#221：行为断言升级。"""
    s = _src()
    m_p65 = re.search(r"# ---- P6\.5 BLOCKER 修复轮", s)
    m_p7 = re.search(r"# ---- P7", s)
    assert m_p65 and m_p7
    block = s[m_p65.start(): m_p7.start()]
    assert "p65_retention_payload" in block, (
        "P6.5 修复指令未接线 p65_retention_payload——blocker 重起草换全文"
        "是 REQ 引用回退入口，P6.7 收口会被洗掉。"
    )
    assert "check_bid_quality" in block, (
        "P6.5 未每轮取活体 check_bid_quality 的 REQ 面——validate 响应无"
        "sections[].covered_reqs，静态/错源数据会把保留纪律建立在过期面上。"
    )
    # 行为断言：REQ 补齐 + 保留双注入真在指令尾产出
    payload = realagent_evidence.p65_retention_payload(
        [], [], ["REQ-0009"], ["REQ-0001"], [])
    assert "REQ 引用补齐纪律" in payload and "REQ-0009" in payload, (
        "P6.5 指令尾缺 REQ 补齐注入——重起草造成的未覆盖 REQ 无法顺手补齐。"
    )
    assert "已覆盖 REQ 保留纪律" in payload and "REQ-0001" in payload, (
        "P6.5 指令尾缺已覆盖 REQ 保留——P6.7 收口被链末重写洗掉。"
    )


def test_p67_repair_carries_points_retention():
    """契约 7（批十一——批十自审残余）：P6.7 整节重起草换全文时只带
    REQ 面双注入而缺评分点保留——P6.6 收口（52/52）会被洗掉（r6b
    7→8→31 覆盖回退同族；批七 D3 修了 P6.5 入口、批八 G2 修了另一半，
    P6.7 是同型的第三个入口）。批#221：行为断言升级。"""
    s = _src()
    m_p67 = re.search(r"# ---- P6\.7 uncovered-REQ 引用补齐修复轮", s)
    m_p65 = re.search(r"# ---- P6\.5 BLOCKER 修复轮", s)
    assert m_p67 and m_p65
    block = s[m_p67.start(): m_p65.start()]
    assert "p67_repair_instruction_tail" in block, (
        "P6.7 指令尾未接线可测函数——评分点保留面无法行为测试。"
    )
    assert "check_scoring_coverage" in block, (
        "P6.7 未取活体覆盖面——静态/过期面会把保留纪律建立在漂移数据上。"
    )
    # 行为断言：评分点补齐 + 保留双注入真在指令尾产出
    tail = realagent_evidence.p67_repair_instruction_tail(
        [], [], ["合同内容页数"], ["培训方案"], [], 1)
    assert "评分细则响应纪律" in tail and "合同内容页数" in tail, (
        "P6.7 指令尾缺评分点补齐注入——丢掉的命中点无法在本轮内补回"
        "（P6.6 已过序，不会重来）。"
    )
    assert "已命中点保留纪律" in tail and "培训方案" in tail, (
        "P6.7 指令尾缺已命中点保留——P6.6 收口（52/52）被洗掉"
        "（r6b 回退同族第三入口）。"
    )
