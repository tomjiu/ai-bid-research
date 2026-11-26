"""批五：驱动 PROFILE 必须传 project_name（投标函抬头泄漏根治）。

实锚（r3/r4 成品段701/702/732）：投标函等格式件抬头写「致：验收#113-
真实LLM起草 招标人」——引擎 export.rs 416-421 在 profile.project_name
缺位时 fallback 内部项目名并打警告「应核对招标文件官方项目名」（引擎
诚实登记在案）；驱动 PROFILE 从未传 project_name → 格式件抬头泄漏
验收项目名。

修复：PROFILE 增 project_name 键（正名+招标人），引擎即取正名。
"""
from pathlib import Path
import re

DRIVER = Path(__file__).resolve().parent.parent / "scripts" / "run_real_llm_path.py"


def test_profile_carries_project_name():
    s = DRIVER.read_text(encoding="utf-8")
    m = re.search(r"PROFILE = \{(.*?)\}", s, re.S)
    assert m, "PROFILE 定义缺失"
    block = m.group(1)
    assert '"project_name"' in block, (
        "PROFILE 未传 project_name——格式件抬头 fallback 内部项目名"
        "「验收#113-真实LLM起草」（r3/r4 实锚），引擎警告已登记此缺位。"
    )
    assert "淮安本地视频能力平台" in block, "project_name 须为招标文件正名"


def test_create_project_internal_name_unaffected():
    """内部项目名（验收跑批标识）仍用于 create_bid_project——不与 export 正名混淆。"""
    s = DRIVER.read_text(encoding="utf-8")
    assert "验收#113-真实LLM起草" in s, "内部项目名标识被误删（断点续跑 state 键匹配依赖）"
