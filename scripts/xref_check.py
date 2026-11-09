#!/usr/bin/env python3
"""xref_check.py — 跨文档一致性检查器（verification-plan §2.4）

以 research/risk-register.md 追溯矩阵为单一真源，机器检查：
  C1  风险登记表 R-* 集合 == 追溯矩阵 R-* 集合（双向）
  C2  追溯矩阵引用的 TC-* 在 test-plan 用例矩阵中存在
  C3  test-plan 每个用例至少被追溯矩阵一行引用（无孤用例）
  C4  TC↔R 双向对齐：test-plan TC-X 风险映射含 R-Y ⟺ 矩阵 R-Y 行含 TC-X
      （v2 修正过的 R-11→TC-12 / R-14→TC-11 即此类错误的回归闸门）
  C5  文档内引用的 AD-* 在 architecture-decision 中有定义
  C6  MCP 契约包含 8 个约定工具章节（结构自检）
  C7  （若夹具存在）expected-transitions 引用的状态名 ⊆ domain-model 枚举；
      TC-01~TC-12 每用例有转换文件
  C8  追溯矩阵"测试结果"列只允许验证状态词典取值

用法：
  python3 scripts/xref_check.py                 # 常规检查，退出码 0/1
  python3 scripts/xref_check.py --inject        # 自测：注入 3 个历史错误，断言全部被捕获
  python3 scripts/xref_check.py --json          # 输出 JSON 报告
"""
from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DOCS = REPO / "docs"
RESEARCH = REPO / "research"
FIXTURES = REPO / "fixtures"

# C6 的约定工具面（bid-mcp-contract.md 章节锚）
MCP_TOOLS = [
    "create_bid_project",
    "import_tender_files",
    "extract_requirements",
    "get_compliance_matrix",
    "search_evidence",
    "draft_response_section",
    "validate_bid_document",
    "export_bid_document",
]
# C8 验证状态词典（risk-register 追溯矩阵"测试结果"列允许值；PARTIAL=部分已验——v1.0 起
# V1 四段验证引入：对应链路的一段已自动验证，其余待后续阶段，细节入矩阵下方注记块）
RESULT_VOCAB = {"待执行", "TESTED", "VERIFIED_SOURCE", "DESIGN_ASSUMPTION", "PENDING", "PARTIAL", "通过", "FAIL", "WAIVED"}
# 宇宙断言（R2 审计 P0-4/5）：期望的风险集与用例集——双表一致删除/解析归零在此处硬失败
EXPECTED_R = {f"R-{i:02d}" for i in range(1, 18)}  # 受控扩展：R-16/R-17（M1.7 真实链执行轮新增）
EXPECTED_TC = {f"TC-{i:02d}" for i in range(1, 13)}
PROJECT_STATES = [
    "DRAFT", "FILES_IMPORTED", "REQUIREMENTS_EXTRACTED", "MATRIX_READY",
    "EVIDENCE_BOUND", "DRAFTING", "VALIDATING", "REVIEWING",
    "READY_TO_EXPORT", "EXPORTED",
]
SECTION_STATES = ["PENDING", "OUTLINING", "DRAFTING", "DRAFTED", "VALIDATING", "REVISING", "ACCEPTED"]
DIRTY_FLAG = "DIRTY"


@dataclass
class Report:
    errors: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    checks: list = field(default_factory=list)

    def err(self, code: str, msg: str):
        self.errors.append(f"[{code}] {msg}")

    def warn(self, code: str, msg: str):
        self.warnings.append(f"[{code}] {msg}")

    def ok(self, name: str, detail: str = ""):
        self.checks.append(f"{name}: OK" + (f" ({detail})" if detail else ""))


def _section(text: str, start_marker: str, end_markers: list[str]) -> str:
    """截取 markdown 两个标题之间的区域。"""
    lines = text.splitlines()
    out, inside = [], False
    for line in lines:
        if not inside and start_marker in line:
            inside = True
            continue
        if inside and any(m in line for m in end_markers):
            break
        if inside:
            out.append(line)
    return "\n".join(out)


def parse_risk_register(text: str) -> dict:
    """返回 {risk_table: {R-ID: 验证方法列}, matrix: {R-ID: (设计, 模块, 用例, 结果, 残余)}}
    登记表与追溯矩阵用章节边界严格分离，避免列污染。"""
    risk_table, matrix = {}, {}
    # 风险登记表：从“## 风险登记表”到“## 处置优先级”
    reg_section = _section(text, "## 风险登记表", ["## 处置优先级"])
    for line in reg_section.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) == 6 and re.fullmatch(r"R-\d{2}", cells[0]):
            risk_table[cells[0]] = cells[-1]  # 验证方法列
    # 追溯矩阵：从“## 追溯矩阵”到“**审计问题”
    mx_section = _section(text, "## 追溯矩阵", ["**审计问题"])
    for line in mx_section.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) == 6 and re.fullmatch(r"R-\d{2}", cells[0]):
            matrix[cells[0]] = (cells[1], cells[2], cells[3], cells[4], cells[5])
    return {"risk_table": risk_table, "matrix": matrix}


def parse_test_plan(text: str) -> dict:
    """返回 {tc_id: 风险映射列原始文本}（§2 用例矩阵，4 列；首列含 TC 编号+用例名）"""
    tc = {}
    section = _section(text, "## 2. 测试用例矩阵", ["## 3."])
    for line in section.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) == 4:
            m = re.match(r"(TC-\d{2})\b", cells[0])
            if m:
                tc[m.group(1)] = cells[3]
    return tc


def extract_ids(text: str, pattern: str) -> set:
    return set(re.findall(pattern, text))


def run_checks(rr_text: str, tp_text: str, ad_text: str, mcp_text: str,
               dm_text: str, report: Report) -> dict:
    rr = parse_risk_register(rr_text)
    tp = parse_test_plan(tp_text)
    matrix, risk_table = rr["matrix"], rr["risk_table"]

    # ---- C1: R 集合双向一致 + 宇宙断言（防双表一致删除/解析归零真空绿）----
    if not risk_table or not matrix:
        report.err("C1", f"解析归零：登记表 {len(risk_table)} 行 / 矩阵 {len(matrix)} 行——文档结构变更导致解析器失明")
    only_table = set(risk_table) - set(matrix)
    only_matrix = set(matrix) - set(risk_table)
    if only_table:
        report.err("C1", f"风险登记表有而追溯矩阵缺：{sorted(only_table)}")
    if only_matrix:
        report.err("C1", f"追溯矩阵有而风险登记表缺：{sorted(only_matrix)}")
    missing_r = EXPECTED_R - set(risk_table)
    extra_r = set(risk_table) - EXPECTED_R
    if missing_r:
        report.err("C1", f"期望风险集缺行（双表一致删除也会被宇宙断言抓住）：{sorted(missing_r)}")
    if extra_r:
        report.err("C1", f"出现期望外的新风险 ID（需同步 EXPECTED_R 与全部文档）：{sorted(extra_r)}")
    if not only_table and not only_matrix and not missing_r and not extra_r:
        report.ok("C1 双向 R 集合一致 + 宇宙断言", f"{len(matrix)} 项风险 == 期望集")

    # ---- C2/C4: TC 存在性 + 双向对齐 ----
    tp_tcs = set(tp)
    if not tp_tcs:
        report.err("C2", "test-plan 用例矩阵解析归零——表格结构变更导致解析器失明")
    if tp_tcs != EXPECTED_TC:
        if EXPECTED_TC - tp_tcs:
            report.err("C2", f"test-plan 缺期望用例：{sorted(EXPECTED_TC - tp_tcs)}")
        if tp_tcs - EXPECTED_TC:
            report.err("C2", f"test-plan 出现期望外用例（需同步 EXPECTED_TC）：{sorted(tp_tcs - EXPECTED_TC)}")
    matrix_tc_refs: dict[str, set] = {}  # TC -> {R}
    for rid, (_d, _m, tcs, _res, _rem) in matrix.items():
        for tc in re.findall(r"TC-\d{2}", tcs):
            matrix_tc_refs.setdefault(tc, set()).add(rid)
            if tc not in tp_tcs:
                report.err("C2", f"矩阵 {rid} 行引用 {tc}，但 test-plan 无此用例")
    # C3: 无孤用例
    orphan = tp_tcs - set(matrix_tc_refs)
    if orphan:
        report.err("C3", f"test-plan 用例未被追溯矩阵任何行引用：{sorted(orphan)}")
    else:
        report.ok("C3 用例全覆盖", f"{len(tp_tcs)} 个用例")
    # C4: 双向对齐
    for tc, mapping in sorted(tp.items()):
        tp_rs = set(re.findall(r"R-\d{2}", mapping))
        mx_rs = matrix_tc_refs.get(tc, set())
        miss_in_matrix = tp_rs - mx_rs
        miss_in_tp = mx_rs - tp_rs
        if miss_in_matrix:
            report.err("C4", f"{tc} 风险映射含 {sorted(miss_in_matrix)}，但矩阵对应行未列 {tc}（矩阵行缺用例回链）")
        if miss_in_tp:
            report.err("C4", f"矩阵 {sorted(miss_in_tp)} 行列有 {tc}，但 test-plan {tc} 风险映射未含该风险（test-plan 缺风险回链）")
    if not [e for e in report.errors if e.startswith("[C4]")]:
        report.ok("C4 TC↔R 双向对齐", f"{len(tp)} 用例 × {len(matrix)} 风险")

    # ---- C4b: 登记表验证方法列 ↔ 矩阵测试用例列 同风险 TC 集合一致
    # （v2 历史错误 R-11→TC-09 / R-14→TC-06、TC-07 均发生在此列，必须单独对齐）
    for rid in sorted(set(risk_table) & set(matrix)):
        reg_tcs = set(re.findall(r"TC-\d{2}", risk_table[rid]))
        mx_tcs = set(re.findall(r"TC-\d{2}", matrix[rid][2]))
        if reg_tcs != mx_tcs:
            report.err("C4b", f"{rid} 登记表验证方法列 TC={sorted(reg_tcs)} ≠ 矩阵测试用例列 TC={sorted(mx_tcs)}")
    if not [e for e in report.errors if e.startswith("[C4b]")]:
        report.ok("C4b 登记表↔矩阵验证用例一致")

    # ---- C5: AD 引用存在性 ----
    ad_defs = set(re.findall(r"^## (AD-\d{2})", ad_text, re.M))
    ad_refs = extract_ids(rr_text + tp_text, r"AD-\d{2}") | extract_ids(
        (RESEARCH / "verification-plan.md").read_text(encoding="utf-8") if (RESEARCH / "verification-plan.md").exists() else "", r"AD-\d{2}")
    dangling = ad_refs - ad_defs
    if dangling:
        report.err("C5", f"引用了未定义的 {sorted(dangling)}")
    else:
        report.ok("C5 AD 引用闭合", f"{len(ad_defs)} 条决策")

    # ---- C6: MCP 工具章节 ----
    missing_tools = [t for t in MCP_TOOLS if not re.search(rf"^## \d+\. {re.escape(t)}\b", mcp_text, re.M)]
    if missing_tools:
        report.err("C6", f"MCP 契约缺工具章节：{missing_tools}")
    else:
        report.ok("C6 MCP 契约 8 工具章节齐全")

    # ---- C8: 矩阵测试结果列取值（词典外取值即错误，非警告——R2 P1-5）----
    for rid, (_d, _m, _t, res, _rem) in matrix.items():
        if res and res not in RESULT_VOCAB:
            report.err("C8", f"矩阵 {rid} 测试结果列非词典取值：'{res}'（词典：{sorted(RESULT_VOCAB)}）")
    if not [e for e in report.errors if e.startswith("[C8]")]:
        report.ok("C8 测试结果列词典合规")

    # ---- C7: expected-transitions 状态与覆盖 ----
    et_dir = FIXTURES / "corpus-A" / "expected-transitions"
    if et_dir.exists():
        files = sorted(et_dir.glob("*.json"))
        et_tcs = {f.stem for f in files}
        if et_tcs != EXPECTED_TC:
            if EXPECTED_TC - et_tcs:
                report.err("C7", f"expected-transitions 缺用例文件：{sorted(EXPECTED_TC - et_tcs)}")
            if et_tcs - EXPECTED_TC:
                report.err("C7", f"expected-transitions 出现期望外用例文件（需同步 EXPECTED_TC）：{sorted(et_tcs - EXPECTED_TC)}")
        allowed = set(PROJECT_STATES) | set(SECTION_STATES) | {DIRTY_FLAG, "E_STATE"}
        for f in files:
            data = json.loads(f.read_text(encoding="utf-8"))
            blob = json.dumps(data, ensure_ascii=False)
            for st in set(re.findall(r"\b[A-Z_]{4,}\b", blob)):
                if st in ("BLOCKER", "MAJOR", "MINOR", "OPEN", "RESOLVED", "WAIVED", "DETERMINISTIC",
                          "MODEL", "PENDING", "MISSING", "DIRTY", "EXPIRED", "ELIGIBLE", "NOT_ELIGIBLE",
                          "NOOP", "PASS", "FAIL", "TODO", "IDEMPOTENT", "NOTES", "CONFLICT"):
                    continue
                if st not in allowed and st.startswith(tuple("PV")) is False and st not in ("GT", "EV", "REQ", "CMP", "SEC", "DOC"):
                    # 仅告警：业务断言词（如 eligible）不阻断
                    report.warn("C7", f"{f.name} 出现未登记状态词 '{st}'（若为断言谓词可忽略）")
        if not report.errors:
            report.ok("C7 expected-transitions 覆盖 TC-01~TC-12", f"{len(files)} 个文件")
    else:
        report.warn("C7", "expected-transitions 目录不存在（夹具未生成？）")
    return {"matrix": matrix, "tp": tp}


def inject_historical_errors(rr_text: str, tp_text: str) -> tuple[str, str]:
    """自测：注入 v2 之前的三处真实历史错误，检查器必须全部捕获。"""
    # 错误1：R-11 验证方法 TC-12 → TC-09（原误标）
    rr_text = rr_text.replace("TC-12 暗标导出（v2 修正记录见文首变更说明）", "TC-09 暗标导出")
    # 错误2：R-14 验证方法 TC-11 → TC-06/TC-07（原误标）
    rr_text = rr_text.replace("TC-11 状态机越级防护（v2 修正记录见文首变更说明）", "TC-06、TC-07 状态机越级防护")
    # 错误3：test-plan TC-08 风险映射 R-05 → Q8（原 Q 编号直引）
    tp_text = re.sub(r"(\| TC-08 换模型恢复 \|[^|]+\|[^|]+\|) R-05[^|]*\|", r"\1 Q8 |", tp_text)
    return rr_text, tp_text


def main() -> int:
    args = sys.argv[1:]
    do_inject = "--inject" in args
    as_json = "--json" in args

    paths = {
        "rr": RESEARCH / "risk-register.md",
        "tp": RESEARCH / "test-plan.md",
        "ad": DOCS / "architecture-decision.md",
        "mcp": DOCS / "bid-mcp-contract.md",
        "dm": DOCS / "bid-domain-model.md",
    }
    texts = {k: p.read_text(encoding="utf-8") for k, p in paths.items()}
    missing = [str(p) for p in paths.values() if not p.exists()]
    if missing:
        print(f"FATAL: 缺文档 {missing}", file=sys.stderr)
        return 2

    if do_inject:
        texts["rr"], texts["tp"] = inject_historical_errors(texts["rr"], texts["tp"])
        print("== 自测模式：已注入 3 处历史错误（R-11→TC-09 / R-14→TC-06、TC-07 / TC-08→Q8）==")

    report = Report()
    run_checks(texts["rr"], texts["tp"], texts["ad"], texts["mcp"], texts["dm"], report)

    if as_json:
        print(json.dumps({"errors": report.errors, "warnings": report.warnings,
                          "checks": report.checks}, ensure_ascii=False, indent=2))
    else:
        for c in report.checks:
            print("  ✓", c)
        for w in report.warnings:
            print("  ⚠", w)
        for e in report.errors:
            print("  ✗", e)
        print(f"\n结论：{len(report.checks)} 项通过 / {len(report.warnings)} 警告 / {len(report.errors)} 错误")

    if do_inject:
        # 注入模式下必须捕获全部三类错误（C4 ≥1 + C4b ≥2）
        c4 = [e for e in report.errors if e.startswith("[C4]")]
        c4b = [e for e in report.errors if e.startswith("[C4b]")]
        if len(c4) >= 1 and len(c4b) >= 2:
            print(f"自测通过：注入错误全部被捕获（C4×{len(c4)} + C4b×{len(c4b)}）")
            return 0
        print(f"自测失败：期望 C4≥1 且 C4b≥2，实际 C4={len(c4)} C4b={len(c4b)}")
        return 1

    return 0 if not report.errors else 1


if __name__ == "__main__":
    sys.exit(main())
