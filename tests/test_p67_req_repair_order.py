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
from pathlib import Path

DRIVER = Path(__file__).resolve().parent.parent / "scripts" / "run_real_llm_path.py"


def _src() -> str:
    return DRIVER.read_text(encoding="utf-8")


def _p67_block(s: str) -> str:
    m = re.search(r"# ---- P6\.7 uncovered-REQ 引用补齐修复轮", s)
    assert m, "P6.7 修复轮代码块缺失（批十面被误删？）"
    # 块右界：首个全稿 validate 或 P6.5 块头（P6.7 在两者之前）
    m_val = re.search(r'must\(\s*"validate_bid_document"', s)
    end = m_val.start() if m_val else len(s)
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
    字面引用的结构性保证。"""
    block = _p67_block(_src())
    assert "req_response_list_hint" in block, (
        "P6.7 无逐 REQ 响应段兜底（req_response_list_hint）——织入正文"
        "不收敛无兜底路径，残余缺口将永远如实登记。"
    )
    assert re.search(r"stuck\s*>=\s*2", block), (
        "兜底切换阈值必须 ≥2（首轮织入正文仍要给机会，响应段是兜底形态）。"
    )


def test_p67_both_branches_carry_retained():
    """契约 5：两分支双注入 retained_req_citation_hint（已覆盖 REQ 保留
    纪律）——整节重起草换全文，不点名保留即修复 A 洗掉 B（批七 D3 对偶）。"""
    block = _p67_block(_src())
    assert "retained_req_citation_hint" in block, (
        "P6.7 缺 retained_req_citation_hint——整节重起草是已覆盖 REQ 的"
        "回退入口（换全文时模型可丢既有引用）。"
    )
    # 常规分支（req_citation_hint）与兜底分支（req_response_list_hint）
    # 的组装段内都必须同时出现 retained
    for anchor, tag in (("req_citation_hint", "常规分支"),
                        ("req_response_list_hint", "兜底分支")):
        i = block.find(anchor)
        seg = block[max(0, i - 100): i + 700]
        assert "retained_req_citation_hint" in seg, (
            f"{tag}（{anchor}）组装段未同时注入 retained_req_citation_hint"
            "——保留纪律只挂单分支，另一分支仍是回退入口。"
        )


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
    ——不能凑合用 validate 数据）。"""
    s = _src()
    m_p65 = re.search(r"# ---- P6\.5 BLOCKER 修复轮", s)
    m_p7 = re.search(r"# ---- P7", s)
    assert m_p65 and m_p7
    block = s[m_p65.start(): m_p7.start()]
    assert "retained_req_citation_hint" in block, (
        "P6.5 修复指令缺 retained_req_citation_hint——blocker 重起草换全文"
        "是 REQ 引用回退入口，P6.7 收口会被洗掉。"
    )
    assert "req_citation_hint" in block, (
        "P6.5 修复指令缺 req_citation_hint——blocker 重起草造成的未覆盖"
        "REQ 无法在该轮内顺手补齐。"
    )
    assert "check_bid_quality" in block, (
        "P6.5 未每轮取活体 check_bid_quality 的 REQ 面——validate 响应无"
        "sections[].covered_reqs，静态/错源数据会把保留纪律建立在过期面上。"
    )
