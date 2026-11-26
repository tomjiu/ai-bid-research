"""test_realagent_evidence.py —— #113 审计修复批二：证据明细落盘 + 口径注入。

审计实锤（2026-11-24 机器审计报告评论 5954 后续深挖）：

- 缺口②根因：validate_bid_document 响应 sections[].uncovered_reqs 与
  check_scoring_coverage 响应 criteria[].points[] 逐点明细**机器已有**，
  驱动只留 summary——realagent-metrics.json 只剩总数（uncovered_req_total=9
  无明细、P9 1/39 哪条命中哪条缺零留痕）。
- 修复方向②未落地：CANON 口径只在 P6.5 修复环兜底，P5b 初始起草
  instructions 无 canonical 数字——三处大写幻觉（96 万/48 万/8 万）本可
  在首稿预防。
- REPORT.md 手写漂移类：fe9d7ca 手写「含 13 节次修复决策日志」而 state
  实为 decisions=[]（审计缺口①）；tool-call-log.json 驱动写了但归档漏收、
  文件表未列。REPORT 底稿应从机器单一真源（metrics/state/实际文件清单）
  生成，人只改叙事。

本测试锁四件事：口径注入指令、未覆盖 REQ 明细聚合、未命中细则点聚合、
REPORT.md 机器底稿（含真实文件表与实留决策数——不写手声称数字）。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import realagent_evidence  # noqa: E402


# ---------------------------------------------------------------- 口径注入


class TestInitialInstructions:
    def test_含四口径正源数字_防首稿幻觉(self):
        """P5b 初始指令必须带 canonical 口径——审计实锚的三个幻觉
        （96 万/48 万/8 万）都是「无源数字自由发挥」产物。"""
        instr = realagent_evidence.initial_instructions()
        assert "4,800,000" in instr          # 投标总报价（PROFILE）
        assert "46,000" in instr             # 投标保证金（须知前附表 3.5.1 正源）
        assert "37" in instr                 # 工期（PROFILE 日历天）
        assert "90" in instr                 # 投标有效期（前附表）

    def test_含分项和约束_防段55类抄限价(self):
        """段55 实锤：把最高投标限价抄成分项报价且分项和≠总报价。
        初始指令必须显式约束「分项之和必须等于总报价」。"""
        instr = realagent_evidence.initial_instructions()
        assert "分项" in instr
        assert "等于" in instr
        assert "限价" in instr  # 显式禁令：不得把限价当本方报价

    def test_含引用纪律与响应面要求_不弱于原指令(self):
        """原指令的引用纪律（只准用列出的 REQ/EV 编号）与响应面要求
        不得因注入口径而弱化。"""
        instr = realagent_evidence.initial_instructions()
        assert "REQ" in instr and "EV" in instr
        assert "逐项响应" in instr

    def test_含无源数字禁令_防费率类幻觉(self):
        """段301 实锤：履约保证金「合同金额 10%」无源费率。初始指令
        必须禁止引入无条款依据的费率/百分比。"""
        instr = realagent_evidence.initial_instructions()
        assert "无源" in instr or "依据" in instr


# ------------------------------------------------------- 未覆盖 REQ 明细聚合


class TestAggregateUncoveredReqs:
    def test_逐章明细聚合并带节归属(self):
        """validate 响应 sections[].uncovered_reqs → 顶层明细（审计缺口②：
        total=9 无明细）。"""
        d = {
            "summary": {"uncovered_req_total": 3},
            "sections": [
                {"section_id": "SEC-0002", "uncovered_reqs": ["REQ-0001", "REQ-0002"]},
                {"section_id": "SEC-0005", "uncovered_reqs": ["REQ-0009"]},
                {"section_id": "SEC-0007", "uncovered_reqs": []},
            ],
        }
        got = realagent_evidence.aggregate_uncovered_reqs(d)
        assert got["total"] == 3
        assert got["ids"] == ["REQ-0001", "REQ-0002", "REQ-0009"]
        by_sec = {r["section_id"]: r["uncovered_reqs"] for r in got["by_section"]}
        assert by_sec["SEC-0002"] == ["REQ-0001", "REQ-0002"]

    def test_空响应零明细不炸(self):
        got = realagent_evidence.aggregate_uncovered_reqs({"summary": {}})
        assert got["total"] == 0 and got["ids"] == [] and got["by_section"] == []

    def test_与summary总数交叉校验不一致如实报(self):
        """机器两处口径不一致时不能静默——如实报 mismatch（审计纪律）。"""
        d = {
            "summary": {"uncovered_req_total": 5},
            "sections": [{"section_id": "SEC-0002", "uncovered_reqs": ["REQ-0001"]}],
        }
        got = realagent_evidence.aggregate_uncovered_reqs(d)
        assert got["total"] == 1  # 明细面为准
        assert got["summary_reported"] == 5  # summary 声称值留痕
        assert got["mismatch"] is True


# ------------------------------------------------------- 未命中细则点聚合


class TestAggregateUncoveredPoints:
    def test_逐点明细带细则id与均分扣分(self):
        """coverage 响应 criteria[].points[]{point, hit_section} → 未命中点
        明细（P9 弱正 1/39：哪 38 条缺零留痕——审校素材）。扣分按均分
        分摊（max_score/points）——与 coverage 工具 criteria 级口径一致。"""
        d = {
            "summary": {"points_total": 4, "points_covered": 1},
            "criteria": [
                {"criterion_id": "SC-0001", "max_score": 5.0,
                 "points": [{"point": "同类业绩", "hit_section": "SEC-0040"},
                            {"point": "项目团队", "hit_section": None}]},
                {"criterion_id": "SC-0002", "max_score": 3.0,
                 "points": [{"point": "售后方案", "hit_section": None},
                            {"point": "培训计划", "hit_section": None}]},
            ],
        }
        got = realagent_evidence.aggregate_uncovered_points(d)
        assert got["points_total"] == 4
        assert got["points_covered"] == 1
        assert len(got["uncovered"]) == 3
        sc1 = next(u for u in got["uncovered"] if u["criterion_id"] == "SC-0001")
        assert sc1["point"] == "项目团队"
        assert sc1["max_score"] == 2.5  # 5.0 / 2 点均分
        sc2 = [u for u in got["uncovered"] if u["criterion_id"] == "SC-0002"]
        assert sc2[0]["max_score"] == 1.5  # 3.0 / 2 点均分

    def test_空criteria零命中如实(self):
        got = realagent_evidence.aggregate_uncovered_points(
            {"summary": {"points_total": 0, "points_covered": 0}, "criteria": []})
        assert got["uncovered"] == [] and got["points_total"] == 0


# ------------------------------------------------------- REPORT.md 机器底稿


class TestBuildReportMd:
    def _metrics(self):
        return {
            "project_id": "PRJ-0001", "main_file": "A-telecom-huaian-主文件.docx",
            "req_total": 380, "leaves": 48,
            "validate": {"char_total": 49103, "char_target": 48000,
                         "char_deviation_pct": 2.3, "uncovered_req_total": 9},
            "export": {"size": 257039, "chapters_written": 48,
                       "sha256": "f4af0262" + "a" * 56},
            "scoring_coverage": {"criteria_total": 36, "points_total": 39,
                                 "points_covered": 1, "coverage_ratio": 0.0256},
            "llm_usage": {"calls": 87, "total_tokens": 117194},
            "elapsed_s": 7300, "resume_rounds": 9,
        }

    def _state(self):
        return {"scoring_mapping": {"unmapped_before": 36, "unmapped_after": 0,
                                     "decisions": [{"req_id": f"SC-{i:04d}"} for i in range(36)]},
                "repair": [{"round": 1, "sid": "SEC-0002"}]}

    def test_文件表来自实际目录_tool_call_log不漏(self, tmp_path):
        """fe9d7ca 归档漏收 tool-call-log.json、文件表未列——底稿文件表
        必须取实际文件清单（存在什么列什么）。"""
        (tmp_path / "realagent-metrics.json").write_text("{}", encoding="utf-8")
        (tmp_path / "tool-call-log.json").write_text("[]", encoding="utf-8")
        (tmp_path / "投标文件-realagent-113.docx").write_bytes(b"PK fake")
        md = realagent_evidence.build_report_md(
            self._metrics(), self._state(), str(tmp_path))
        assert "tool-call-log.json" in md
        assert "realagent-metrics.json" in md
        assert "投标文件-realagent-113.docx" in md
        assert "driver-state.json" not in md  # 不在场的文件不列（不写期望态）

    def test_决策数取实留不取手写声称(self):
        """审计缺口①类：手写 REPORT 声称 13 决策而 state 实留空。底稿的
        决策数必须等于 state 实际长度。"""
        md = realagent_evidence.build_report_md(
            self._metrics(), self._state(), "/nonexistent-dir")
        assert "映射决策 36" in md       # scoring_mapping.decisions 实留 36
        assert "修复决策 1 节次" in md    # repair 实留 1
        empty_state = {"scoring_mapping": {"decisions": []}, "repair": []}
        md2 = realagent_evidence.build_report_md(
            self._metrics(), empty_state, "/nonexistent-dir")
        assert "映射决策 0" in md2
        assert "修复决策 0 节次" in md2

    def test_机器已知数与metrics一致(self):
        md = realagent_evidence.build_report_md(
            self._metrics(), self._state(), "/nonexistent-dir")
        assert "49,103" in md       # 字数（千分位）
        assert "87" in md and "117,194" in md        # 用量
        assert "2.6%" in md          # 覆盖率
        assert "9 轮" in md                            # resume 轮次（诚实口径）

    def test_人工半边不代填_条件3恒待人工(self):
        """不代人工关单纪律：REPORT 底稿不得写「人工审校 ✅」类绿面。"""
        md = realagent_evidence.build_report_md(
            self._metrics(), self._state(), "/nonexistent-dir")
        assert "⛔" in md or "未满足" in md
        assert "待人工" in md

    def test_不覆盖已存在的手写REPORT_防洗史(self, tmp_path):
        """封存包不回改：若 OUT 已有 REPORT.md（手写叙事），底稿写
        REPORT.generated.md——不覆盖既有文件（洗史防线）。"""
        hand = tmp_path / "REPORT.md"
        hand.write_text("手写叙事原稿", encoding="utf-8")
        target = realagent_evidence.report_target(str(tmp_path))
        assert target != str(hand)
        assert "generated" in Path(target).name
        # 无既有 REPORT.md 时落正式名（首次跑批即机器底稿）
        empty_dir = tmp_path / "fresh"
        empty_dir.mkdir()
        assert realagent_evidence.report_target(str(empty_dir)).endswith("REPORT.md")


# ---------------------------------------------------------------- 批三


class TestEvidenceCitationHint:
    """P5b 证据引用指令（EV-0064 未引用根治面）。"""

    def test_列全证据编号与名称_指令可执行(self):
        hint = realagent_evidence.evidence_citation_hint([
            ("EV-0063", "qualification", "电子与智能化工程专业承包二级资质证书"),
            ("EV-0064", "qualification", "营业执照"),
            ("EV-0065", "performance", "类似业绩合同-智慧园区弱电工程"),
        ])
        for ev in ("EV-0063", "EV-0064", "EV-0065"):
            assert ev in hint
        assert "营业执照" in hint and "类似业绩合同" in hint
        assert "证据引用纪律" in hint
        assert "[EV-0063]" in hint          # 给出可照抄的引用形态示例

    def test_空证据零指令不炸(self):
        assert realagent_evidence.evidence_citation_hint([]) == ""


class TestLeafPointsMap:
    """check_scoring_coverage → 叶→评分点归集（P9 0/39 根治面）。"""

    def test_按映射叶归集评分点(self):
        cov = {"criteria": [
            {"criterion_id": "REQ-0290",
             "mapped_sections": ["SEC-0028", "SEC-0029"],
             "points": [{"point": "培训计划"}, {"point": "培训人员分配"},
                        {"point": "培训达到的效果预期"}]},
            {"criterion_id": "REQ-0291",
             "mapped_sections": ["SEC-0028"],
             "points": [{"point": "应急响应策略"}, {"point": "网络故障预案"}]},
        ]}
        m = realagent_evidence.leaf_points_map(cov)
        assert m["SEC-0028"] == ["培训计划", "培训人员分配", "培训达到的效果预期",
                                 "应急响应策略", "网络故障预案"]
        assert m["SEC-0029"] == ["培训计划", "培训人员分配", "培训达到的效果预期"]

    def test_无映射或无点的criteria跳过(self):
        cov = {"criteria": [
            {"criterion_id": "R1", "mapped_sections": [], "points": [{"point": "x"}]},
            {"criterion_id": "R2", "mapped_sections": ["SEC-1"], "points": []},
            {"criterion_id": "R3", "mapped_sections": ["SEC-1"], "points": [{"point": None}]},
        ]}
        assert realagent_evidence.leaf_points_map(cov) == {}

    def test_空响应空map(self):
        assert realagent_evidence.leaf_points_map({}) == {}
        assert realagent_evidence.leaf_points_map({"criteria": []}) == {}


class TestScoringPointsHint:
    """单叶评分点逐点响应指令段。"""

    def test_逐点编号列出并带响应纪律(self):
        hint = realagent_evidence.scoring_points_hint(["培训计划", "应急响应策略"])
        assert "（1）培训计划" in hint
        assert "（2）应急响应策略" in hint
        assert "逐点显式响应" in hint
        assert "关键术语" in hint              # 字面命中口径的务实解法提示

    def test_空点零指令不炸(self):
        assert realagent_evidence.scoring_points_hint([]) == ""
        assert realagent_evidence.scoring_points_hint(["", None]) == ""


# ---------------------------------------------------------------- 批六②③


class TestBatch6EvidenceFacts:
    """批六③（r5 审读 A2/A3 实锚）：业绩实载口径注入——比禁令更硬的根治面。

    r5 成品段18：业绩合同金额写 200 万（证据件 EV-0065 实载 260 万——
    200 恰为资格线值，凑线幻觉新形态）；同时声称「签订日期在
    2023-10-01 至公告发布之间」（证据件实载 2023-05-20，在窗口外）——
    日期断言与所引证据件直接矛盾。禁令挡不住 LLM 编具体值：唯一根治面
    是把证据件实载口径直接注入指令（抄对，而不是被禁止编错）。
    """

    def test_业绩金额实载口径_260万注入(self):
        instr = realagent_evidence.initial_instructions()
        assert "260" in instr and "万" in instr, (
            "业绩证据件 EV-0065 实载金额（260 万）必须注入指令——LLM 抄对"
        )

    def test_业绩签订日期实载口径_2023_05_20注入(self):
        instr = realagent_evidence.initial_instructions()
        assert "2023-05-20" in instr, "证据件实载签订日期必须注入（防日期断言与证据矛盾）"

    def test_资格线值禁当业绩值_显式禁令(self):
        instr = realagent_evidence.initial_instructions()
        assert "资格线" in instr
        assert "200 万" in instr or "200万" in instr, (
            "禁令必须点名资格线数值形态（r5 段18 把资格线值写成业绩值）"
        )


class TestBatch6ScoringEvidencePoints:
    """批六②（r5 审读 C4 实锚）：证据型评分点响应纪律增强。

    r5 实测 P9 34/39：缺的 5 点全是「依赖外部证据件的点」（信息系统
    管理师证书/演示/样机/检测报告类）——正文无从引用对应证据（台账无
    该类证据件）时 LLM 直接跳过。指令增强：证据型点要么按 EV 编号显式
    引用，要么如实声明【待补】——不静默跳过。
    """

    def test_证据型评分点_追加证据响应纪律子句(self):
        hint = realagent_evidence.scoring_points_hint(
            ["技术负责人须具备信息系统管理师证书", "提供设备检测报告"]
        )
        assert "证书" in hint
        assert "证据" in hint
        assert "EV" in hint or "【待补】" in hint, (
            "证据型点必须引导按 EV 引用或如实【待补】——不静默跳过"
        )

    def test_非证据型点_不追加证据段_保持原有形态(self):
        hint = realagent_evidence.scoring_points_hint(["培训计划", "应急响应策略"])
        assert "（1）培训计划" in hint
        assert "（2）应急响应策略" in hint

    def test_空点行为不变(self):
        assert realagent_evidence.scoring_points_hint([]) == ""
        assert realagent_evidence.scoring_points_hint(["", None]) == ""


class TestBatch7SectionRepairFullPoints:
    """批七（#113 全链审计 D3）：P6.6 修复轮防回退契约。

    实锚缺陷：r6b SEC-0028 修复轮覆盖 7→8→31 回退——重起草指令只注入
    未命中点，模型重写把已命中点丢了。契约：按叶聚合全量点（missing/hit
    双栏）+ 已命中点保留纪律注入段。
    """

    COV = {
        "criteria": [
            {"criterion_id": "REQ-A", "mapped_sections": ["SEC-0028"],
             "points": [
                 {"point": "应急响应策略", "hit_section": None},
                 {"point": "网络故障预案", "hit_section": None},
             ]},
            {"criterion_id": "REQ-B", "mapped_sections": ["SEC-0028"],
             "points": [
                 {"point": "培训计划", "hit_section": "SEC-0028"},
                 {"point": "电源故障预案", "hit_section": None},
             ]},
            {"criterion_id": "REQ-C", "mapped_sections": ["SEC-0031"],
             "points": [
                 {"point": "进度计划", "hit_section": "SEC-0031"},
             ]},
        ],
        "summary": {"points_total": 5, "points_covered": 2},
    }

    def test_全量点按叶分栏_含已命中(self):
        out = realagent_evidence.section_points_for_repair(self.COV)
        sec = out.get("SEC-0028")
        assert sec is not None, f"SEC-0028 须在键位: {out.keys()}"
        assert set(sec["missing"]) == {"应急响应策略", "网络故障预案", "电源故障预案"}
        assert sec["hit"] == ["培训计划"], "已命中点必须入 hit 栏（D3 防回退）"

    def test_全命中叶仍入键位_hit_only(self):
        out = realagent_evidence.section_points_for_repair(self.COV)
        assert out.get("SEC-0031") == {"missing": [], "hit": ["进度计划"]}

    def test_跨叶聚合不串门(self):
        out = realagent_evidence.section_points_for_repair(self.COV)
        assert "SEC-0028" in out and "SEC-0031" in out and len(out) == 2

    def test_保留纪律段_点名已命中点_只增不删(self):
        hint = realagent_evidence.retained_points_hint(["培训计划", "进度计划"])
        assert "培训计划" in hint and "进度计划" in hint
        assert "保留" in hint and "只增不删" in hint
        assert realagent_evidence.retained_points_hint([]) == ""

    def test_空响应_空字典(self):
        assert realagent_evidence.section_points_for_repair({}) == {}
        assert realagent_evidence.section_points_for_repair({"criteria": []}) == {}


# ------------------------------------------------- 批九 G1：P6.6 对照表兜底

class TestPointTableHint:
    """批九（#113 r6 实弹终验实锚）：P6.6 五轮「逐点织入正文」对短碎片点
    不收敛——r6b 收口 49/52，残余三点（合同内容页/合同金额页/所提供人员
    2026年3月份）五轮注入 LLM 反复丢词，且整节重写造成覆盖震荡
    （49→21 / 49→46 各一次）。投标实务正路是「评分细则逐点响应对照表」：
    表格点原文列逐字复述细则点——字面命中口径下结构性保证覆盖，且表格
    逐字复述对 LLM 是远比织入正文更弱的指令（复制类指令）。
    """

    def test_全量点逐字入表_含逐字复述纪律(self):
        hint = realagent_evidence.point_table_hint(
            ["合同内容页", "合同金额页", "所提供人员2026年3月份"])
        for p in ("合同内容页", "合同金额页", "所提供人员2026年3月份"):
            assert p in hint, f"点原文必须逐字出现在指令中: {p}"
        assert "逐字" in hint and "一字不差" in hint, "必须点名逐字复述纪律"
        assert "对照表" in hint, "必须是对照表形态指令"
        assert "两列" in hint, "必须是两列表（点原文 | 我方响应）"

    def test_空点空指令不炸(self):
        assert realagent_evidence.point_table_hint([]) == ""
        assert realagent_evidence.point_table_hint(None) == ""

    def test_指令声明追加而非替换_防洗正文(self):
        """对照表是节末追加件——指令必须声明正文照常撰写，防 LLM 把
        全节缩写成一张表（篇幅门会红）。"""
        hint = realagent_evidence.point_table_hint(["培训计划"])
        assert "追加" in hint and ("正文" in hint), "须声明节末追加 + 正文照常"


# ------------------------------------------------- 批十 P6.7：uncovered-REQ 引用补齐

class TestReqCitationHint:
    """批十（#113 P6.7 候补面落地）：r7 实锚——real 生成器 prompt 已含
    REQ 清单与引用规则（llm.rs 系统规则 2/3 + 素材面逐条「要求条款」），
    LLM 对低显著度样板条款（1.8.1 不得存在情形 / 1.9 货物原产地 / 1.10
    投标费用 / 1.11 保密 / 2.2 踏勘现场等——r7 SEC-0035×8/SEC-0040×1/
    SEC-0062×1 共 10 条）仍丢 [REQ-xxxx] 标注。P6.5 修 blocker、P6.6 修
    评分点，唯独 REQ 引用无修复面——P6.7 同款定向重起草指令注入。
    """

    def test_未覆盖REQ逐条列出_显式引用纪律(self):
        hint = realagent_evidence.req_citation_hint(
            ["REQ-0138", "REQ-0142", "REQ-0363"])
        for rid in ("REQ-0138", "REQ-0142", "REQ-0363"):
            assert rid in hint, f"未覆盖 REQ 必须逐条出现在指令中: {rid}"
        assert "针对 [REQ-" in hint, "必须点名「针对 [REQ-xxxx]」显式引用形态"
        assert "未" in hint and "引用" in hint

    def test_空清单空指令不炸(self):
        assert realagent_evidence.req_citation_hint([]) == ""
        assert realagent_evidence.req_citation_hint(None) == ""

    def test_已覆盖REQ保留纪律_只增不删(self):
        """retained 同款（批七 D3 对偶）：整节重起草换全文——已覆盖 REQ
        的显式引用必须点名保留，否则修复 A 缺口洗掉 B 覆盖。"""
        hint = realagent_evidence.retained_req_citation_hint(
            ["REQ-0058", "REQ-0099"])
        for rid in ("REQ-0058", "REQ-0099"):
            assert rid in hint, f"已覆盖 REQ 必须逐条点名保留: {rid}"
        assert "只增不删" in hint or ("保留" in hint and "不得" in hint), (
            "必须声明只增不删纪律"
        )
        assert realagent_evidence.retained_req_citation_hint([]) == ""

    def test_逐REQ响应段兜底_编号逐字写入(self):
        """批九 G1 对偶：织入正文不收敛（≥2 轮）→ 逐 REQ 显式响应段
        兜底形态——段落首「针对 [REQ-xxxx]（类别）要求」编号逐字写入，
        字面引用口径下结构性保证。"""
        hint = realagent_evidence.req_response_list_hint(
            ["REQ-0138", "REQ-0154"])
        for rid in ("REQ-0138", "REQ-0154"):
            assert rid in hint, f"兜底指令必须逐条列出 REQ: {rid}"
        assert "逐" in hint and ("段落" in hint or "一段" in hint), (
            "必须是逐 REQ 独立成段的形态指令"
        )
        assert "不得合并" in hint, "必须禁止合并省略编号（合并即丢引用）"
        assert realagent_evidence.req_response_list_hint([]) == ""
