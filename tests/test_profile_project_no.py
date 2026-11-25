#!/usr/bin/env python3
"""批六（r5 通读审读 A4 根治）：驱动 profile.project_no 不得用内部虚构编号。

r5 成品段643（投标函正文）实锤泄漏：
    「根据贵方项目编号为 HA-2026-BID-001 的 中国电信…招标文件」
HA-2026-BID-001 在主文件 0 命中（真编号 JSCGXM202610210082001001 主文件×3、
成品其他 22 处正确）——泄漏源是台架本身：run_real_llm_path.py PROFILE 把
内部虚构编号当 project_no 传给 LLM，投标函模板行「项目编号为__」照抄。

契约（源级结构检查——driver 是带顶层副作用的脚本，不可 import）：
1. PROFILE["project_no"] 必须等于主文件正源编号 JSCGXM202610210082001001；
2. 不得再出现 HA-2026-BID-001 作为 project_no 取值（closeout_real_test.py
   的测试夹具用例不在此约束内）。
"""
import re
from pathlib import Path

DRIVER = (Path(__file__).resolve().parent.parent / "scripts"
          / "run_real_llm_path.py")


def _profile_source() -> str:
    src = DRIVER.read_text(encoding="utf-8")
    m = re.search(r"^PROFILE\s*=\s*\{(.*?)^\}", src, re.S | re.M)
    assert m, "run_real_llm_path.py 中未找到 PROFILE 块"
    return m.group(1)


def test_profile_project_no_is_real_tender_no():
    src = _profile_source()
    m = re.search(r'"project_no"\s*:\s*"([^"]+)"', src)
    assert m, "PROFILE 缺 project_no 字段（投标函编号行将无锚）"
    assert m.group(1) == "JSCGXM202610210082001001", (
        f'project_no={m.group(1)!r} 不是主文件正源编号'
        "（主文件×3 命中 JSCGXM202610210082001001）——"
        "内部编号会经 profile 泄漏进投标函（r5 段643 实锤）"
    )


def test_profile_project_no_not_internal_id():
    src = _profile_source()
    m = re.search(r'"project_no"\s*:\s*"([^"]+)"', src)
    assert m and m.group(1) != "HA-2026-BID-001", (
        "project_no 仍为内部虚构编号 HA-2026-BID-001"
        "（主文件 0 命中——r5 段643 已实锤泄漏）"
    )
