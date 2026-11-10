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
from pathlib import Path
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

    规则：
    - Windows 进程内：一律小写（本机 FS 大小写不敏感是业务缺省）；
    - 其他平台：仅盘符样式路径（``C:/...``，跨平台配置迁移场景）
      折叠，POSIX 路径保持原样（大小写敏感）。
    """
    text = str(path).replace("\\", "/")
    if is_windows():
        return text.lower()
    if len(text) >= 2 and text[0].isalpha() and text[1] == ":":
        return text.lower()
    return text


def console_encoding_safe() -> bool:
    """当前 stdout 是否能**确认**安全输出非 ASCII（中文）文本。

    Windows 传统控制台代码页（GBK/cp936）打印部分 Unicode 字符
    会抛 ``UnicodeEncodeError``；utf-8 代码页或重定向到文件时安全。
    Linux 终端/locale 缺省安全（Python 3.7+ UTF-8 模式回退）。

    语义：**未验证即不安全**——编码属性缺失或无法确认时返回
    False，调用方应做降级加固而非放任崩溃。
    """
    stream = sys.stdout
    encoding = getattr(stream, "encoding", None) or ""
    norm = encoding.lower().replace("-", "")
    if norm in ("utf8", "utf8mb4"):
        return True
    try:
        "招标公告测试".encode(encoding)
    except (LookupError, UnicodeEncodeError):
        return False
    return True


def _stream_can_encode_chinese(stream: object) -> bool:
    """流是否能无损编码中文与常用报告符号（方框图线等）。"""
    encoding = getattr(stream, "encoding", None) or ""
    try:
        "招标公告 ▏█ 壹贰叁".encode(encoding)
    except (LookupError, UnicodeEncodeError):
        return False
    return True


def configure_console_safe() -> list[str]:
    """控制台输出加固（#601 R40）——跨平台「不崩溃」保证。

    场景：Windows 传统控制台代码页（GBK/cp936/ascii）打印报告中的
    方框图线（█▏）、生僻字或 emoji 时抛 ``UnicodeEncodeError`` 导致
    CLI 中途崩溃。本函数对 stdout/stderr 做**就地降级**：

    - 编码无法覆盖中文/制表符号的流：``reconfigure(errors="replace")``
      （坏字符变 ``?``，绝不上抛）；Windows 上进一步尝试切 UTF-8
      代码页（失败静默——仅当代码页可切时受益）；
    - UTF-8 流（Linux 缺省 / 已重定向文件）：零改动。

    返回采取的动作清单（空列表 = 无需加固），供 ``--verbose`` 与测试
    断言使用。
    """
    actions: list[str] = []
    for name in ("stdout", "stderr"):
        stream = getattr(sys, name, None)
        if stream is None or not hasattr(stream, "reconfigure"):
            continue
        if _stream_can_encode_chinese(stream):
            continue
        try:
            stream.reconfigure(errors="replace")
            actions.append(f"{name}:errors=replace")
        except (ValueError, OSError):
            # 非常规流（已 detach/关闭）——跳过，打印侧自行兜底
            continue
    return actions


class PathTooLongError(OSError):
    """路径超出当前平台保守长度上限（Windows MAX_PATH 常见触发）。"""

    def __init__(self, path: Path, limit: int):
        self.path = path
        self.limit = limit
        super().__init__(
            f"路径过长（{len(str(path))} ≥ {limit} 字符）：{path}\n"
            f"缓解方式：① 缩短 --output-dir（移到浅目录，如 C:\\work）；"
            f"② Windows 启用长路径支持"
            f"（注册表 LongPathsEnabled=1 后重启）；"
            f"③ 缩短关键词过滤词。"
        )


def ensure_writable_path(path: Path | str) -> Path:
    """写入前防护（#601 R44）——平台长度上限先行校验。

    Windows 未启用长路径时 ``open()`` 对 >260 路径抛出的
    ``FileNotFoundError``（而非 ``OSError``）极具误导性——看似
    「目录不存在」，实为长度超限。本函数在写前给出**可行动**的
    专用错误；Linux（PATH_MAX 4096）实质放行。
    """
    resolved = Path(path).absolute()
    if path_too_long(resolved):
        raise PathTooLongError(resolved, max_path_length())
    return resolved


def write_text_lf(path: Path | str, content: str, *, encoding: str = "utf-8") -> Path:
    """平台无关的 LF 行尾写盘（#601 R45）。

    Windows 文本模式缺省把 ``\\n`` 翻译成 ``\\r\\n``——报告/JSONL
    产物字节随平台漂移，破坏「同一命令同一产物」的确定性契约
    （golden 对比、二进制 diff、git 噪音全受累）。本函数以
    ``newline="\\n"`` 钉死不翻译，两平台字节一致。

    返回写入的路径（便于链式引用）。
    """
    target = Path(path)
    with open(target, "w", encoding=encoding, newline="\n") as fh:
        fh.write(content)
    return target


def read_text_universal(path: Path | str, *, encoding: str = "utf-8") -> str:
    """平台/来源无关读取（R45 配套）——CRLF/LF/CR 全归一为 LF。

    旧版 Windows 工具导出的 CRLF 文件与新 LF 产物在读取面
    同语义（``\\r\\n`` → ``\\n``），下游行级解析不再双分支。
    """
    text = Path(path).read_text(encoding=encoding)
    if "\r\n" in text:
        text = text.replace("\r\n", "\n")
    if "\r" in text:
        text = text.replace("\r", "\n")
    return text


#: Windows 文件名非法字符（Linux 仅 / 与 \0，从严处理两平台通吃）
_ILLEGAL_FS_CHARS = '<>:"/\\|?*'
#: Windows 保留设备名（大小写不敏感；带扩展名也不能用）
_WINDOWS_RESERVED = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}
#: 单文件名分量长度上限（两平台文件系统通用安全值）
_MAX_COMPONENT_LEN = 200


def sanitize_filename(name: str, *, max_length: int = _MAX_COMPONENT_LEN) -> str:
    """清洗为两平台合法文件名分量（#601 R46）。

    处理顺序（每步结果供下一步，最终恒非空）：

    1. 非法字符 ``< > : " / \\ | ? *`` → ``_``
       （现有 ``\\w`` 类清洗已覆盖大部分，此处**显式**列出——
       Linux 合法的 ``:`` 在 Windows 盘符语义下致命）；
    2. 控制字符（``\\x00-\\x1f``）与空白（空格/制表——shell
       引号友好的历史契约）→ ``_``；
    3. 去尾部点与下划线（Windows 静默剥离尾点/尾空格导致
       「看起来创建了实则换了名」的历史坑；空格已在第 2 步
       折叠为 ``_``）；
    4. Windows 保留设备名（``CON``/``NUL``/``COM1``…）：尾部加
       ``_``（``CON`` → ``CON_``，语义保真且立即可用）；
    5. 长度截断（保尾不保头——扩展名语义在尾部），空结果兜底
       ``sanitized``。
    """
    out = name
    for ch in _ILLEGAL_FS_CHARS:
        out = out.replace(ch, "_")
    # 原文层先剥尾点/尾空格（Windows 磁盘静默剥离规则）——
    # 必须先于空白折叠，否则折叠出的 _ 挡住剥离
    out = out.rstrip(". ")
    out = "".join(
        "_" if ord(c) < 0x20 or c.isspace() else c for c in out
    )
    stem = out.split(".")[0] if "." in out else out
    if stem.upper() in _WINDOWS_RESERVED:
        out = out + "_"
    if len(out) > max_length:
        out = out[-max_length:]
    return out or "sanitized"
