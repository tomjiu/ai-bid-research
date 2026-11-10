"""--version 版本面测试（#601 R66）。"""

import subprocess
import sys

import pytest


class TestVersionBanner:
    def test_banner_contains_version_and_env(self):
        from src.version import __version__, version_banner

        banner = version_banner()
        assert __version__ in banner
        assert "python" in banner
        assert sys.platform in banner

    def test_version_is_semver(self):
        from src.version import __version__

        parts = __version__.split(".")
        assert len(parts) == 3 and all(p.isdigit() for p in parts)

    def test_cli_version_flag(self, capsys):
        import main as main_mod
        from src.version import __version__

        with pytest.raises(SystemExit) as ei:
            main_mod.main(["--version"])
        assert ei.value.code == 0
        out = capsys.readouterr().out
        assert f"ai-bid-research {__version__}" in out

    def test_cli_version_subprocess(self):
        """真实进程面：python main.py --version 退出 0。"""
        result = subprocess.run(
            [sys.executable, "main.py", "--version"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0
        assert "ai-bid-research" in result.stdout
