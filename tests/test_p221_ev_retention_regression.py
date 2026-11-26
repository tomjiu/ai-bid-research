"""#221 顺序行为回归——P6.8 收口后 P6.5 整节重写的证据引用回退复现与阻断。

Lead 独立审查登记（issue #221，2026-11-26）：
    PR#220 head=adde269 的 P6.5 blocker 整节重起草指令（918–933 行）带
    评分点/REQ 显式保留而无**活体已援引 EV 的显式保留**——P6.8 刚收口
    的证据引用会被链末重写洗掉。源码已证实；本文件用确定性替身把
    「顺序行为反例」钉成红绿回归。

复现口径（#221 派工二.1——强制走 P6.8 收口 → P6 校验 → P6.5 blocker
整节重写路径）：
    1. 顺序断言（源级相位锚）：P6.8 → P6 校验（首个全稿 validate）→
       基线捕获 → P6.5 重写 → 保留回归门 → validate:final；
    2. WashStub（最坏情形替身，**只作回归证据，不冒充真实 LLM 效果**）：
       整节重起草换全文——「已援引证据保留纪律」未点名保留的 EV，重写
       后正文不再援引（r6b 覆盖回退 7→8→31 / r7 EV-0064 零援引同族最坏
       形态的确定性建模）。REQ/评分点保留同型；
    3. 指令内容行为断言：p65/p66/p67/p68 四个指令尾函数（#221 抽为
       可测函数）在活体形状数据下必须产出完整保留栈（活体数据真流进
       指令——不是只出现函数名）；
    4. P6.5 保留回归门（issue 任务 3）：每轮修复体后、下轮 validate 前
       （结构即行为——驱动脚本无法离线单跑）；两轮定向修复未收口 =
       regression-unresolved.json + exit 1（不装绿）。
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


def _block(s: str, start_pat: str, end_pat: str) -> str:
    """块截取：起点模式到**下一相位边界**（Lead 指出的误满足面——
    旧的「首个 validate」右界把 P6.8 块整个包进 P6.7 块，存在性字符串
    断言可被 P6.8 的字符串满足）。"""
    m = re.search(start_pat, s)
    assert m, f"起点 {start_pat} 缺失（相位被误删？）"
    end = re.search(end_pat, s)
    return s[m.start(): end.start() if end else len(s)]


# ---- 活体形状数据（check_bid_quality / check_scoring_coverage 响应形状）----
LIVE_EV_CITED = ["EV-0063", "EV-0064", "EV-0065"]   # P6.8 收口后节级已援引
LIVE_REQ_COV = ["REQ-0001", "REQ-0002"]
LIVE_PTS_MISSING = ["合同内容页数"]
LIVE_PTS_HIT = ["培训方案", "应急响应策略"]


class WashStub:
    """最坏情形重写替身（#221——确定性，只作回归证据，不冒充真实 LLM）。

    策略：整节重起草换全文——EV/REQ 只有被指令中**专用指令段**
    （补齐/保留/兑底枚举）点名的才在重写产物中存活；静态 EV_HINT
    清单（通用纪律，r7 实锚：全文列了 3 件 EV-0064 仍零援引）不
    视为存活依据。r6b 覆盖回退 7→8→31 / r7 EV-0064 零援引同族
    最坏形态的确定性建模。真实效果由 r8 实弹验证（#221 派工四）。
    """

    EV_PROLOGUES = ("证据援引补齐纪律", "已援引证据保留纪律", "逐证据援引段兑底纪律")
    REQ_PROLOGUES = ("REQ 引用补齐纪律", "已覆盖 REQ 保留纪律",
                     "逐 REQ 显式响应段兑底纪律")

    @staticmethod
    def _directive_ids(instruction: str, prologues) -> set:
        """按专用指令段拆分（段 = 序言起点到下一序言/串尾），提取段内
        枚举实体 ID——联合枚举「、[EV-…]」与单实体枚举同判。"""
        bounds = []
        for pro in prologues:
            start = 0
            while True:
                i = instruction.find(pro, start)
                if i < 0:
                    break
                bounds.append(i)
                start = i + 1
        ids = set()
        bounds.sort()
        for j, b in enumerate(bounds):
            seg_end = bounds[j + 1] if j + 1 < len(bounds) else len(instruction)
            ids |= set(re.findall(r"\[([A-Z]{2,3}-\d+)\]", instruction[b:seg_end]))
        return ids

    @classmethod
    def kept_evs(cls, instruction: str, before: set) -> set:
        return {ev for ev in before
                if ev in cls._directive_ids(instruction, cls.EV_PROLOGUES)}

    @classmethod
    def kept_reqs(cls, instruction: str, before: set) -> set:
        return {r for r in before
                if r in cls._directive_ids(instruction, cls.REQ_PROLOGUES)}


# ================================================== 一、顺序反例（复现）


def test_p65_washes_ev_citations_after_p68_closeout():
    """#221 复现核心（红）：P6.8 收口（3 EV 全援引）→ P6 校验 blocker →
    P6.5 整节重写——最坏情形替身下 EV 援引集合在最后一次重写后回退。"""
    before = set(LIVE_EV_CITED)
    payload = realagent_evidence.p65_retention_payload(
        LIVE_PTS_MISSING + LIVE_PTS_HIT, LIVE_PTS_HIT, [], LIVE_REQ_COV,
        LIVE_EV_CITED)
    after = WashStub.kept_evs(payload, before)
    assert after == before, (
        f"P6.5 重写指令未点名保留活体 cited_evs（{sorted(before)} → "
        f"{sorted(after)}）——链末 blocker 重写是 EV 引用回退入口，"
        "P6.8 收口被洗掉（#221 Lead 登记的顺序回退）。"
    )


def test_p65_washes_req_citations_after_p68_closeout():
    """#221 复现（REQ 面）：P6.5 重写指令必须点名保留已覆盖 REQ——
    批十已修（retained_req_citation_hint），本测红绿锁住不回退。"""
    before = set(LIVE_REQ_COV)
    payload = realagent_evidence.p65_retention_payload(
        LIVE_PTS_MISSING + LIVE_PTS_HIT, LIVE_PTS_HIT, [], LIVE_REQ_COV,
        LIVE_EV_CITED)
    after = WashStub.kept_reqs(payload, before)
    assert after == before, (
        f"P6.5 重写指令未点名保留已覆盖 REQ（{sorted(before)} → "
        f"{sorted(after)}）——批十 REQ 保留面回退。"
    )


def test_driver_phase_order_p68_validate_baseline_p65_gate():
    """顺序断言（源级相位锚）：P6.8 → P6 校验（首个全稿 validate）→
    基线捕获 → P6.5 重写 → 保留回归门 → validate:final——门必须在
    零 blocker validate（推进 VALIDATING 的那次）之前收口。"""
    s = _src()
    pos = {
        "P6.8": s.find("# ---- P6.8 证据引用补齐修复轮"),
        "P6 校验": s.find("    # ---- P6 校验 ----"),
        "基线捕获": s.find("批#221：P6.5 前基线捕获"),
        "P6.5": s.find("# ---- P6.5 BLOCKER 修复轮"),
        "保留回归门": s.find("批#221 保留回归门"),
        "validate:final": s.find('"validate:final"'),
    }
    for k, v in pos.items():
        assert v >= 0, f"相位缺失：{k}（#221 面被误删？）"
    order = ["P6.8", "P6 校验", "基线捕获", "P6.5", "保留回归门", "validate:final"]
    seq = [pos[k] for k in order]
    assert seq == sorted(seq), (
        f"相位顺序破坏：{dict(zip(order, seq))}——保留回归门必须在零 "
        "blocker validate（推进 VALIDATING 的那次）之前收口。"
    )


# ================================================== 二、全入口保留栈


def test_p66_tail_retains_req_and_ev():
    """#221「避免只补单点」：P6.6 重写指令尾必须带 REQ/EV 保留——
    节级已援引 EV 洗掉不触发 P6.8 重收口（其判据是文档级零援引）。"""
    for stuck in (1, 2):
        tail = realagent_evidence.p66_repair_instruction_tail(
            LIVE_PTS_MISSING, LIVE_PTS_HIT, LIVE_REQ_COV, LIVE_EV_CITED, stuck)
        assert WashStub.kept_evs(tail, set(LIVE_EV_CITED)) == set(LIVE_EV_CITED), (
            f"P6.6 指令尾（stuck={stuck}）未点名保留活体 cited_evs——"
            "P6.6 重写是 EV 引用回退入口（文档级判据管不住节级洗掉）。"
        )
        assert WashStub.kept_reqs(tail, set(LIVE_REQ_COV)) == set(LIVE_REQ_COV), (
            f"P6.6 指令尾（stuck={stuck}）未点名保留已覆盖 REQ。"
        )


def test_p67_tail_retains_ev():
    """#221「避免只补单点」：P6.7 重写指令尾必须带 EV 保留（REQ/点
    已有——批十/批十一），常规与响应段兜底两分支同检。"""
    for stuck in (1, 2):
        tail = realagent_evidence.p67_repair_instruction_tail(
            [], LIVE_REQ_COV, LIVE_PTS_MISSING, LIVE_PTS_HIT, LIVE_EV_CITED,
            stuck)
        assert WashStub.kept_evs(tail, set(LIVE_EV_CITED)) == set(LIVE_EV_CITED), (
            f"P6.7 指令尾（stuck={stuck}）未点名保留活体 cited_evs——"
            "P6.7 重写是 EV 引用回退入口。"
        )
        assert WashStub.kept_reqs(tail, set(LIVE_REQ_COV)) == set(LIVE_REQ_COV), (
            f"P6.7 指令尾（stuck={stuck}）REQ 保留面回退（批十面被洗）。"
        )


def test_p68_tail_full_retention_stack():
    """P6.8 全栈样板回归锁：EV/REQ/点三层补齐 + 保留全在。"""
    tail = realagent_evidence.p68_repair_instruction_tail(
        ["EV-0064"], ["EV-0064"], LIVE_EV_CITED, [], LIVE_REQ_COV,
        LIVE_PTS_MISSING, LIVE_PTS_HIT)
    assert WashStub.kept_evs(tail, set(LIVE_EV_CITED)) == set(LIVE_EV_CITED)
    assert WashStub.kept_reqs(tail, set(LIVE_REQ_COV)) == set(LIVE_REQ_COV)
    assert "证据援引补齐纪律" in tail or "逐证据援引段兜底纪律" in tail, (
        "P6.8 尾缺零援引 EV 补齐注入（批十一面回退）。"
    )


def test_p65_tail_retains_points():
    """P6.5 指令尾点保留面（批八 G2）红绿锁——活体已命中点入指令。"""
    payload = realagent_evidence.p65_retention_payload(
        LIVE_PTS_MISSING + LIVE_PTS_HIT, LIVE_PTS_HIT, [], LIVE_REQ_COV,
        LIVE_EV_CITED)
    for pt in LIVE_PTS_HIT:
        assert pt in payload, f"P6.5 指令尾丢已命中评分点「{pt}」（回退入口）"


# ================================================== 三、活体数据流（指令内容）


def test_live_ids_flow_into_all_tails():
    """指令内容行为断言：活体面传入的 EV/REQ/点编号必须真流进指令文本
    （证明驱动器从活体工具响应取数注入——非静态缓存）。"""
    p65 = realagent_evidence.p65_retention_payload(
        LIVE_PTS_MISSING, LIVE_PTS_HIT, ["REQ-0009"], LIVE_REQ_COV,
        ["EV-0063"])
    for x in ["EV-0063", "REQ-0001", "REQ-0009", "培训方案", "合同内容页数"]:
        assert x in p65, f"P6.5 指令尾未携带活体面数据 {x}"

    p66 = realagent_evidence.p66_repair_instruction_tail(
        LIVE_PTS_MISSING, LIVE_PTS_HIT, ["REQ-0007"], ["EV-0065"], 1)
    for x in ["REQ-0007", "EV-0065", "应急响应策略"]:
        assert x in p66, f"P6.6 指令尾未携带活体面数据 {x}"

    p67 = realagent_evidence.p67_repair_instruction_tail(
        ["REQ-0031"], ["REQ-0032"], LIVE_PTS_MISSING, LIVE_PTS_HIT,
        ["EV-0064"], 2)
    for x in ["REQ-0031", "REQ-0032", "EV-0064", "合同内容页数"]:
        assert x in p67, f"P6.7 指令尾未携带活体面数据 {x}"

    p68 = realagent_evidence.p68_repair_instruction_tail(
        ["EV-0064"], [], ["EV-0063"], ["REQ-0005"], ["REQ-0006"],
        LIVE_PTS_MISSING, LIVE_PTS_HIT)
    for x in ["EV-0064", "EV-0063", "REQ-0005", "REQ-0006", "培训方案"]:
        assert x in p68, f"P6.8 指令尾未携带活体面数据 {x}"


# ================================================== 四、驱动器接线（源级）


def test_p66_block_live_quality_and_tail():
    """P6.6 块：每轮活体 check_bid_quality（q-p66 面）+ 指令尾接线。"""
    block = _block(_src(), r"# ---- P6\.6 细则覆盖修复轮", r"# ---- P6\.7 ")
    assert "check_bid_quality" in block, (
        "P6.6 未每轮取活体 REQ/EV 面——保留纪律建立在静态/过期面上。"
    )
    assert "q-p66" in block, "P6.6 缺 q-p66 上下文标识（活体调用不可辨）"
    assert "p66_repair_instruction_tail" in block, "P6.6 指令尾未接线"
    assert "cited_evs" in block, "P6.6 未消费活体 cited_evs"


def test_p67_block_tail_with_cited_evs():
    """P6.7 块：指令尾接线且传入活体 cited_evs。"""
    block = _block(_src(), r"# ---- P6\.7 uncovered-REQ", r"# ---- P6\.8 ")
    assert "p67_repair_instruction_tail" in block, "P6.7 指令尾未接线"
    assert 's.get("cited_evs")' in block, "P6.7 未把活体 cited_evs 传进指令尾"


def test_p68_block_tail_wired():
    """P6.8 块：指令尾接线（全栈样板函数化，防后续改动漏层）。"""
    block = _block(_src(), r"# ---- P6\.8 证据引用补齐修复轮",
                   r"# ---- P6 校验 ----")
    assert "p68_repair_instruction_tail" in block, "P6.8 指令尾未接线"


def test_p65_block_tail_with_cited_evs():
    """P6.5 块：指令尾接线且传入活体 cited_evs（q_r 同一响应，零额外
    工具调用）。"""
    block = _block(_src(), r"# ---- P6\.5 BLOCKER 修复轮", r"# ---- P7")
    assert "p65_retention_payload" in block, "P6.5 指令尾未接线"
    assert 'get("cited_evs")' in block, "P6.5 未把活体 cited_evs 传进指令尾"
    assert "q-p65" in block, "P6.5 缺每轮活体 quality 调用（q-p65）"


# ================================================== 五、保留回归门（任务 3）


def test_gate_structure_bounded_and_honest_fail():
    """P6.5 保留回归门（#221 任务 3——结构即行为）：每轮修复体后过门、
    两轮定向修复有界、未收口 regression-unresolved.json + exit 1 不装绿。"""
    block = _block(_src(), r"# ---- P6\.5 BLOCKER 修复轮", r"# ---- P7")
    assert "for gate_round in (1, 2)" in block, (
        "保留回归门缺两轮有界循环——修复无界即轮次耗尽假终局。"
    )
    assert "regression-unresolved.json" in block, (
        "保留回归门未收口时缺落盘件——回退只在日志里出现即被标成已收口"
        "（#221 任务 3 点名的「不能只在 P9 落日志后标成已收口」）。"
    )
    assert "sys.exit(1)" in block, "门未收口必须如实报红退出（exit 1）"
    assert '"retain-gate"' in block, (
        '门修复留痕缺独立 kind="retain-gate"——污染 P6.6/P6.7/P6.8 '
        "非收敛计数（kind 隔离纪律）。"
    )
    # 门比较三面：丢 REQ / 丢 EV / 评分点覆盖数
    for face in ("lost_reqs", "lost_evs", "lost_pts"):
        assert face in block, f"门缺 {face} 面（三面集合验证不齐）"


def test_gate_runs_before_state_advancing_validate():
    """门位置契约：修复体后、下轮 validate 前（Drafting 态内合法重写）——
    validate:final 在门之后（终验前所有回退已收口或已诚实报红）。"""
    s = _src()
    gate = s.find("批#221 保留回归门")
    val_final = s.find('"validate:final"')
    assert 0 <= gate < val_final, (
        "保留回归门必须在 validate:final 之前——零 blocker validate 推进 "
        "VALIDATING 后 draft_response_section 被 E_STATE 拒绝（#243 家族）。"
    )


def test_gate_uses_full_stack_tail():
    """门定向修复指令复用 p68 全栈尾——修复本身不得引入新回退
    （全栈注入），fresh_evs 取活体 uncited_evs ∩ lost_evs。"""
    block = _block(_src(), r"# ---- P6\.5 BLOCKER 修复轮", r"# ---- P7")
    assert block.count("p68_repair_instruction_tail") >= 1, (
        "保留回归门未复用 p68 全栈指令尾（门定向修复是链末的链末——"
        "必须全栈注入，修复本身不得引入新回退）。"
    )
    assert "lost_evs & set(s_.get(\"uncited_evs\")" in block, (
        "门 fresh_evs 未取活体 uncited_evs ∩ lost_evs（文档级复活定位）。"
    )
