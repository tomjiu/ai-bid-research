"""批四指令层契约（r3 成品人工通读发现的「身份锚定缺失」型幻觉根治）。

审读实锚（realagent-113-v3-20261124-r3 成品 770 段全文通读 + 主文件 ground truth 反查）：
  A类事实硬伤：项目名张冠李戴×3（业绩项目名当本项目名）、业绩虚构细节
  （一份写成两份 250万+180万凑430万）、分项无源凑数（4,710,365/89,635）、
  履约写死46,000、投标函抬头写「验收#113-真实LLM起草」、24小时无源挪用；
  B类自相矛盾：联合体（4正1错）、招标组织形式（委托vs自行）、备选方案
  （允许vs禁止）、延长有效期答复（书面vs无需）；
  C类：评分细则关键术语39点正文0命中（SEC-0028/0029五轮重起草仍通用模板文）。

根因：INITIAL_INSTR 只锚金额工期口径，未锚**项目身份**——LLM 靠上下文
自由发挥项目名/招标人/业绩细节/分项数。
"""
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import realagent_evidence as ev

INSTR = ev.initial_instructions()

PROJECT_NAME = "淮安本地视频能力平台"
TENDERER = "中国电信股份有限公司淮安分公司"


def test_identity_anchor_project_name():
    """A1：指令必须锚定本项目真实名称（防业绩项目名张冠李戴）。"""
    assert PROJECT_NAME in INSTR, "指令缺项目名锚——成品把业绩项目名当本项目名×3"
    assert TENDERER in INSTR, "指令缺招标人锚——投标函抬头写错实锚"


def test_identity_anchor_anti_confusion():
    """A1附：明示禁止把业绩材料项目名当作本项目名。"""
    assert "不得" in INSTR and "业绩" in INSTR and "项目名" in INSTR, (
        "缺业绩项目名禁令（张冠李戴根治面）"
    )


def test_performance_truth_discipline():
    """A2：业绩如实引用纪律（不得虚构份数/金额/日期/累计数）。"""
    assert re.search(r"业绩.{0,30}（只能|不得虚构|如实）|（只能|如实）.{0,30}业绩", INSTR) or (
        "如实" in INSTR and "业绩" in INSTR
    ), "缺业绩如实纪律——成品虚构两份业绩凑430万实锚"


def test_split_value_ban():
    """A3：分项具体数值禁令（含分项/履约/时限全口径）。"""
    assert "分项" in INSTR, "缺分项禁令——成品 4,710,365/89,635 无源凑数实锚"
    # 履约保证金「见前附表」无数禁写（段333 实锚）
    assert "履约" in INSTR, "缺履约保证金无数禁写纪律"


def test_global_consistency_locks():
    """B：全局一致性口径锁定（联合体/组织形式/备选方案）。"""
    for kw in ("联合体", "备选"):
        assert kw in INSTR, f"缺「{kw}」一致性锁——成品该主题正反声明自相矛盾实锚"


def test_scoring_points_keyword_discipline():
    """C：评分点关键术语原词保留纪律（39点0命中根治面）。"""
    hint = ev.scoring_points_hint(["投标人拟为本项目配备的技术负责人须具备信息系统管理师证书"])
    assert "原词" in hint or "保留" in hint or "字面" in hint, (
        "scoring_points_hint 缺关键术语原词保留纪律——五轮重起草仍0命中的根因之一"
    )
