"""长任务进度指示（#601 R68）。

设计：

- **tty**：行内刷新（``\\r`` 回车 + 覆写 + flush）——不刷屏；
- **非 tty**（管道/重定向/CI 日志）：完全静默——输出流被收集时
  覆写字符是噪声；每 25% 打一条 DEBUG 日志供 --verbose 排障；
- ``finish()`` 收尾换行 + 摘要，未开始（零步）不输出任何东西。
"""

from __future__ import annotations

import logging
import sys
from typing import Optional, TextIO

logger = logging.getLogger("ai-bid-research.progress")


class ProgressPrinter:
    """抽取/采集等批任务的进度面。

    用法::

        progress = ProgressPrinter(total=len(records), label="抽取")
        for i, record in enumerate(records, 1):
            ...  # 干活
            progress.step(i, detail=record.bid_id)
        progress.finish(summary="完成 12 条")
    """

    def __init__(
        self,
        total: int,
        *,
        label: str = "处理",
        stream: Optional[TextIO] = None,
    ) -> None:
        self.total = max(int(total), 0)
        self.label = label
        self.stream = stream if stream is not None else sys.stdout
        self.enabled = (
            self.total > 0
            and hasattr(self.stream, "isatty")
            and self.stream.isatty()
        )
        self._last_logged = 0
        self._steps = 0

    def step(self, current: int, detail: str = "") -> None:
        """推进到 ``current/total``（detail 为当前条目标识）。"""
        self._steps = current
        if self.enabled:
            shown = min(current, self.total)
            line = f"\r{self.label}中 {shown}/{self.total}"
            if detail:
                line += f" · {detail}"
            try:
                self.stream.write(line)
                self.stream.flush()
            except (OSError, ValueError):
                pass  # 流关闭——进度是展示层，绝不反噬主流程
            return
        # 非 tty：每 25% 一条 DEBUG（--verbose 可见）
        if self.total and current * 4 // self.total > self._last_logged:
            self._last_logged = current * 4 // self.total
            logger.debug(
                "%s进度 %d/%d", self.label, current, self.total
            )

    def finish(self, summary: str = "") -> None:
        """收尾：tty 上换行（终端提示符不粘行）+ 可选摘要。"""
        if not self._steps:
            return  # 一步没走——零输出
        if self.enabled:
            try:
                self.stream.write("\r" + " " * 40 + "\r")  # 清残留
                if summary:
                    self.stream.write(f"{summary}\n")
                else:
                    self.stream.write("\n")
                self.stream.flush()
            except (OSError, ValueError):
                pass
