"""跨平台检测工具面（#601 R39）。

背景：CLI 在 Linux（CI/研究机）与 Windows（业务机）双平台运行，
历史上散落的平台假设（路径长度、大小写敏感性、控制台编码）没有
统一入口。本模块提供**唯一权威**的平台检测面，供 storage/collect/
report 各层复用；测试通过 monkeypatch ``sys.platform`` 覆盖两平台。

约定：
- 判定只读 ``sys.platform``（``win32`` / ``linux`` / ``darwin``），
  不触碰 ``os.name``——两者在目标平台上一致且前者粒度更细；
- 所有函数**纯函数化**（无 I/O、无全局可变状态），便于单测。
"""

from __future__ import annotations

import sys
from pathlib import Path, PureWindowsPath
from typing import Final

#: Windows 默认 MAX_PATH（含终止符 260；长路径注册表开关不在此判定内）
_WINDOWS_MAX_PATH: Final[int] = 260
#: Linux 常见 PATH_MAX
_LINUX_PATH_MAX: Final[int] = 4096


def is_windows() -> bool:
    """当前进程是否运行在 Windows。"""
    return sys.platform == "win32"


def is_linux() -> bool:
    """当前进程是否运行在 Linux。"""
    return sys.platform.startswith("linux")


def is_macos() -> bool:
    """当前进程是否运行在 macOS。"""
    return sys.platform == "darwin"


def platform_label() -> str:
    """人读平台标签（日志/报告元信息用）。

    >>> platform_label() in ("windows", "linux", "macos", "other")
    True
    """
    if is_windows():
        return "windows"
    if is_linux():
        return "linux"
    if is_macos():
        return "macos"
    return "other"


def max_path_length() -> int:
    """当前平台单一路径分量的保守长度上限。

    - Windows：260（MAX_PATH，未启用长路径注册表开关时的硬顶）；
    - 其他：4096（Linux PATH_MAX 常见值）。

    注意：这是**保守值**。Windows 启用 ``LongPathsEnabled`` 后可超，
    但检测注册表超出纯函数边界，故统一按保守值防护。
    """
    return _WINDOWS_MAX_PATH if is_windows() else _LINUX_PATH_MAX


def path_too_long(path: Path | str) -> bool:
    """路径是否超出当前平台保守长度上限。

    绝对路径展开后再判定（相对路径在深目录下拼接后才超限）。
    """
    resolved = Path(path).absolute()
    return len(str(resolved)) >= max_path_length()


def filesystem_case_sensitive() -> bool:
    """目标文件系统大小写敏感性的平台级启发式。

    - Windows（NTFS 按挂载可大小写不敏感，业务默认如此）→ False；
    - Linux/macOS 常规卷 → True。

    这是**平台启发式**而非卷级探测；调用方若需精确判定，
    应以本函数为缺省再做卷级实测覆盖。
    """
    return not is_windows()


def normalize_path_key(path: Path | str) -> str:
    """路径的去重键：大小写不敏感平台统一小写并规范分隔符。

    用途：同一路径在不同来源（CLI 参数/配置文件/注册表）可能
    写成 ``Data\\Bids.DB`` 或 ``data/bids.db``——在不敏感平台上
    两者指向同一文件，去重键必须折叠；敏感平台保持原样。
    """
    text = str(path)
    if is_windows() or PureWindowsPath(text).is_absolute():
        # 仅对 Windows 语义路径折叠大小写与反斜杠
        if "\\" in text or PureWindowsPath(text).is_absolute():
            return text.replace("\\", "/").lower()
    return text.replace("\\", "/")


def console_encoding_safe() -> bool:
    """当前 stdout 是否能安全输出非 ASCII（中文）文本。

    Windows 传统控制台代码页（GBK/cp936）打印部分 Unicode 字符
    会抛 ``UnicodeEncodeError``；utf-8 代码页或重定向到文件时安全。
    Linux 终端/locale 缺省安全（Python 3.7+ UTF-8 模式回退）。
    """
    stream = sys.stdout
    encoding = getattr(stream, "encoding", None) or ""
    norm = encoding.lower().replace("-", "")
    if norm in ("utf8", "utf8mb4", ""):
        return True
    try:
        "招标公告测试".encode(encoding)
    except (LookupError, UnicodeEncodeError):
        return False
    return True
