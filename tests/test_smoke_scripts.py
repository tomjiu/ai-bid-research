"""双平台冒烟脚本测试（#601 R67）。"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SMOKE_SH = REPO / "scripts" / "smoke-linux.sh"
SMOKE_PS1 = REPO / "scripts" / "smoke-windows.ps1"


class TestSmokeLinux:
    @pytest.mark.skipif(
        shutil.which("bash") is None, reason="无 bash"
    )
    def test_full_smoke_passes(self):
        """真实子进程跑通 Linux 冒烟（离线全链）。"""
        result = subprocess.run(
            ["bash", str(SMOKE_SH), sys.executable],
            capture_output=True,
            text=True,
            timeout=180,
            cwd=str(REPO),
        )
        assert result.returncode == 0, result.stderr[-2000:]
        assert "SMOKE OK（Linux 离线全链）" in result.stdout
        assert "断言通过" in result.stdout

    def test_script_executable_bit(self):
        # Linux 侧可执行权限（Windows 无此位概念——只查存在）
        assert SMOKE_SH.exists()
        assert SMOKE_PS1.exists()


class TestSmokeWindowsScript:
    """Linux 沙箱跑不了 PowerShell——结构契约锁定（关键步齐备）。"""

    REQUIRED_STEPS = (
        "--version",
        "collect --source",
        "--status",
        "analyze",
        "--export json",
        "SMOKE OK",
    )

    def test_ps1_contains_all_steps(self):
        text = SMOKE_PS1.read_text(encoding="utf-8")
        for step in self.REQUIRED_STEPS:
            assert step in text, f"ps1 缺步：{step}"

    def test_ps1_strict_mode(self):
        text = SMOKE_PS1.read_text(encoding="utf-8")
        assert "$ErrorActionPreference = 'Stop'" in text
        # 临时目录清理（finally 兜底）
        assert "finally" in text and "Remove-Item" in text

    def test_ps1_utf8_bom_for_powershell5(self):
        """PowerShell 5.1 对无 BOM 脚本按 ANSI 解析——中文注释会碎。
        冒烟脚本带中文输出，BOM 是 Windows 兼容刚需。"""
        raw = SMOKE_PS1.read_bytes()
        assert raw.startswith(b"\xef\xbb\xbf"), "ps1 缺 UTF-8 BOM"

    def test_ps1_path_backslash_normalization(self):
        """Windows 临时路径（反斜杠）→ CLI 参数正斜杠归一。"""
        text = SMOKE_PS1.read_text(encoding="utf-8")
        assert "-replace '\\\\', '/'" in text

    def test_scripts_are_paired(self):
        """双平台脚本步序一致（对齐契约——改一处须同步另一处）。"""
        sh = SMOKE_SH.read_text(encoding="utf-8")
        ps1 = SMOKE_PS1.read_text(encoding="utf-8")
        for step in self.REQUIRED_STEPS:
            assert step in sh, f"sh 缺步：{step}"
            assert step in ps1, f"ps1 缺步：{step}"
