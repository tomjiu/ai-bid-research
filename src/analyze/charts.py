"""ASCII 条形图渲染（非生产链路——仅供研究，见 docs/PYTHON-BOUNDARY.md）。

R64：纯文本可视化——区域分布/月度趋势等「Top N + 计数」数据的
条形图面：

- 字符集两档：``█``（Unicode 块字符，UTF-8 终端）与 ``#``
  （ASCII 回退——GBK/cp936 控制台块字符不可靠时）；
- 自动等宽对齐（标签右对齐 + 条形同宽基准）；
- 零值画 ``·`` 点位（保行对齐，区别于空行）；
- 纯函数，无 I/O——报告/控制台/测试三面复用。
"""

from __future__ import annotations

from typing import List, Optional, Sequence, Tuple

#: Unicode 块字符（UTF-8 终端缺省）
BLOCK_CHAR = "█"
#: ASCII 回退字符
ASCII_CHAR = "#"
#: 零值占位
ZERO_CHAR = "·"


def ascii_bar(
    value: float,
    max_value: float,
    *,
    width: int = 20,
    char: str = BLOCK_CHAR,
) -> str:
    """单条条形（定宽）。

    Args:
        value: 本条数值（≥0；负数按 0）。
        max_value: 全组最大值（比例基准；≤0 时全零处理）。
        width: 条形满宽字符数。
        char: 条形字符（Unicode 块或 ASCII 回退）。

    Returns:
        条形字符串（长度恒等于 ``width``——不足补空格，
        零值画 ``·`` 保持视觉占位）。
    """
    if width <= 0:
        return ""
    if max_value <= 0 or value <= 0:
        return ZERO_CHAR + " " * (width - 1)
    ratio = min(value / max_value, 1.0)
    filled = round(ratio * width)
    filled = max(1, min(filled, width))
    return char * filled + " " * (width - filled)


def render_bars(
    items: Sequence[Tuple[str, float]],
    *,
    width: int = 20,
    char: str = BLOCK_CHAR,
    label_width: Optional[int] = None,
    show_value: bool = True,
) -> List[str]:
    """Top N 条形图（多行文本，每行一条）。

    Args:
        items: ``(标签, 数值)`` 序列（调用方已排序）。
        width: 条形满宽。
        char: 条形字符。
        label_width: 标签列宽（缺省自适应——最长标签宽度）。
        show_value: 行尾附数值。

    Returns:
        行列表（空输入返回空列表）；格式
        ``标签(右对齐) │██████ 12.0``。
    """
    if not items:
        return []
    if label_width is None:
        label_width = max(len(str(label)) for label, _ in items)
    max_value = max((float(v) for _, v in items), default=0.0)
    lines = []
    for label, value in items:
        value = float(value)
        bar = ascii_bar(value, max_value, width=width, char=char)
        row = f"{str(label):>{label_width}} │{bar}"
        if show_value:
            num = f"{value:g}"
            row = f"{row} {num}"
        lines.append(row)
    return lines


def console_bar_char() -> str:
    """按当前控制台编码能力选条形字符（R64 降级面）。

    - UTF-8 / GBK（cp936 含几何块区，``█``=A880、``│``=A9A6）
      → ``█``；
    - ascii / latin-1 类无块字符编码 → ``#``
      （配合 R40 加固：即使判断失误，reconfigure(errors=replace)
      兜底不崩溃，只是美观降级）。
    """
    from src.platform import console_encoding_safe

    return BLOCK_CHAR if console_encoding_safe() else ASCII_CHAR
