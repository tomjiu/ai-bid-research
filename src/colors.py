"""控制台 ANSI 颜色面（跨平台，#601 R65）。

纪律：

- **NO_COLOR 规范**（https://no-color.org）：环境变量 ``NO_COLOR``
  非空 → 全局关色（优先于一切探测）；
- 非 tty（重定向/管道）→ 关色（输出进文件不带转义噪音）；
- ``CI`` 环境变量常见于无 tty 但支持色的环境——**不特殊放行**
  （研究面取保守口径，颜色只在确证终端能力时启用）；
- Windows：传统控制台不识 ANSI——经 ``ctypes`` 调
  ``SetConsoleMode`` 开 ``ENABLE_VIRTUAL_TERMINAL_PROCESSING``
  （VT，Win10 1511+），失败则关色；Windows Terminal
  （``WT_SESSION``）/ ANSICON / ``TERM`` 已设的环境天然可用；
- 颜色只是**展示层**：所有输出文本在不支持色的环境语义完整。
"""

from __future__ import annotations

import os
import sys
from typing import Optional

#: ANSI 码表（研究面用到的最小集）
RESET = "\033[0m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BOLD = "\033[1m"
DIM = "\033[2m"

# Windows VT 开关（kernel32）
_ENABLE_VT = 0x0004
# GetConsoleMode 成功句柄上的 VT 位
_VT_ENABLED = 0x0004


def _windows_vt_enabled(stream) -> bool:
    """尽力为 Windows 传统控制台开 VT 模式（一次性，幂等）。

    返回 True = VT 可用（本函数或此前已开启）；False = 不支持
    （旧版 Windows / 非 conhost 句柄）——调用方应关色。
    """
    try:
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        handle = stream.fileno() if hasattr(stream, "fileno") else -1
        if handle == -1:
            return False
        console = wintypes.HANDLE(handle)
        mode = wintypes.DWORD()
        if not kernel32.GetConsoleMode(console, ctypes.byref(mode)):
            return False
        if mode.value & _VT_ENABLED:
            return True  # 已开（如 Windows Terminal）
        new_mode = wintypes.DWORD(mode.value | _ENABLE_VT)
        if not kernel32.SetConsoleMode(console, new_mode):
            return False
        # 开成功后回读确认（部分旧驱动静默忽略）
        if not kernel32.GetConsoleMode(console, ctypes.byref(mode)):
            return False
        return bool(mode.value & _VT_ENABLED)
    except (OSError, ValueError, ImportError, AttributeError):
        return False


def supports_color(
    stream=None, *, env: Optional[dict] = None
) -> bool:
    """流是否应对其启用 ANSI 颜色。

    Args:
        stream: 目标流（缺省 ``sys.stdout``）。
        env: 环境变量映射（测试注入；缺省 ``os.environ``）。

    判定序（短路）：

    1. ``NO_COLOR`` 非空 → False（规范最高优先）；
    2. 流非 tty → False；
    3. ``TERM`` == "dumb" → False；
    4. Windows：``WT_SESSION``/``ANSICON``/``ConEmuANSI`` 任一
       已设，或 VT 模式开启成功 → True，否则 False；
    5. 其他平台 → True。
    """
    if stream is None:
        stream = sys.stdout
    env = os.environ if env is None else env
    if env.get("NO_COLOR"):
        return False
    if not hasattr(stream, "isatty") or not stream.isatty():
        return False
    if env.get("TERM") == "dumb":
        return False
    if sys.platform == "win32":
        if any(
            env.get(name)
            for name in ("WT_SESSION", "ANSICON", "ConEmuANSI")
        ):
            return True
        return _windows_vt_enabled(stream)
    return True


def colorize(text: str, code: str, *, enabled: bool) -> str:
    """按启用态包装 ANSI 码（禁用时原样返回）。"""
    if not enabled:
        return text
    return f"{code}{text}{RESET}"


class ColorPrinter:
    """带启用态判定的打印助手（main 入口一次性构建）。

    用法::

        cp = ColorPrinter(sys.stderr)
        cp.err("数据库不存在")   # 红（支持时）
        cp.ok("已入库 12 条")    # 绿
    """

    def __init__(self, stream=None, *, env=None):
        self.stream = stream if stream is not None else sys.stdout
        # env 注入口：测试可绕过宿主环境（CI 常设 NO_COLOR）
        self.enabled = supports_color(self.stream, env=env)

    def _emit(self, text: str, code: str) -> None:
        print(colorize(text, code, enabled=self.enabled),
              file=self.stream)

    def err(self, text: str) -> None:
        self._emit(text, RED)

    def ok(self, text: str) -> None:
        self._emit(text, GREEN)

    def warn(self, text: str) -> None:
        self._emit(text, YELLOW)

    def bold(self, text: str) -> None:
        self._emit(text, BOLD)
