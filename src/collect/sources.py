"""本地源读取器（JSON / JSONL 三形态，#601 批次 A）。

设计说明
--------
采集面的默认源是**本地文件**（离线可测，PYTHON-BOUNDARY 研究面定性）：

- ``.json`` 文件：JSON 数组（每元素一条公告）或单 JSON 对象；
- ``.jsonl`` 文件：每行一个 JSON 对象（行式流式形态，空行容忍）；
- 目录源：收集全部 ``*.json`` / ``*.jsonl``，按文件名排序（确定性——
  同一批文件两次运行产出顺序一致，研究可复现）。

失败语义（对照 AGENTS「不静默吞错」纪律）：

- 单条/单文件损坏**不中断整批**（缺一行坏数据就丢整目录不可接受）；
- 但失败必须**计数并逐条登记**在 :attr:`LoadResult.failures`
  （origin 携带文件名与 jsonl 行号），调用方决定打印/入库；
- ``skip_invalid=False`` 时第一条失败即抛——严格模式供断言用。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Union

from src.collect.records import AnnouncementRecord

#: 目录源收集的扩展名（小写比较）。
_SOURCE_SUFFIXES = (".json", ".jsonl")


class SourceError(ValueError):
    """源不可读（路径不存在 / 类型不支持）。"""


@dataclass
class LoadResult:
    """一次源装载的结果。

    Attributes:
        records: 成功规范化的记录列表。
        failures: 失败明细列表，每项为
            ``(origin, message)``——origin 形如 ``file.jsonl:3``。
        files_read: 实际读取的文件数。
    """

    records: List[AnnouncementRecord] = field(default_factory=list)
    failures: List[Dict[str, str]] = field(default_factory=list)
    files_read: int = 0

    @property
    def total(self) -> int:
        """成功 + 失败的总条数（源装载吞吐面）。"""
        return len(self.records) + len(self.failures)

    def add_failure(self, origin: str, message: str) -> None:
        """登记一条失败（不静默——必须可被调用方打印/汇总）。"""
        self.failures.append({"origin": origin, "error": message})


# ----------------------------------------------------------------------
# 路径解析
# ----------------------------------------------------------------------

def resolve_source_files(source: Union[str, Path]) -> List[Path]:
    """把源路径解析为待读文件清单。

    Args:
        source: 文件或目录路径。

    Returns:
        排序后的文件路径列表（目录源按文件名排序保证确定性）。

    Raises:
        SourceError: 路径不存在，或目录内无 ``.json``/``.jsonl`` 文件，
            或文件扩展名不支持。
    """
    path = Path(source)
    if not path.exists():
        raise SourceError(f"源路径不存在: {path}")
    if path.is_dir():
        files = sorted(
            p for p in path.iterdir() if p.suffix.lower() in _SOURCE_SUFFIXES
        )
        if not files:
            raise SourceError(f"目录内无 .json/.jsonl 源文件: {path}")
        return files
    if path.suffix.lower() not in _SOURCE_SUFFIXES:
        raise SourceError(
            f"不支持的源文件类型: {path.suffix or '(无扩展名)'}"
            f"（支持 {'/'.join(_SOURCE_SUFFIXES)}）"
        )
    return [path]


# ----------------------------------------------------------------------
# 文件读取
# ----------------------------------------------------------------------

def _read_json_payload(path: Path) -> List[Dict[str, Any]]:
    """读取 JSON 载荷：数组 → 元素列表；单对象 → 单元素列表。

    Returns:
        载荷字典列表。

    Raises:
        ValueError: JSON 语法损坏，或顶层不是数组/对象。
    """
    text = path.read_text(encoding="utf-8")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON 语法错误: {exc}") from exc
    if isinstance(payload, list):
        if any(not isinstance(item, dict) for item in payload):
            raise ValueError("JSON 数组含非对象元素")
        return payload
    if isinstance(payload, dict):
        return [payload]
    raise ValueError(f"JSON 顶层须为数组或对象，实际为 {type(payload).__name__}")


def _read_jsonl_items(path: Path) -> tuple:
    """读取 JSONL 载荷（行级粒度：坏行不殃及好行）。

    Returns:
        (items, line_errors) 二元组：

        - items: ``(行号, 载荷字典)`` 列表（好行）；
        - line_errors: ``(行号, 错误消息)`` 列表（坏行）。

    Raises:
        ValueError: 文件为空（零非空行——区别于「有坏行」，
            全空文件大概率是截断/损坏，登记为文件级失败）。
    """
    items: List[tuple] = []
    line_errors: List[tuple] = []
    for lineno, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            line_errors.append((lineno, f"JSON 错误: {exc}"))
            continue
        if not isinstance(item, dict):
            line_errors.append((lineno, "行内容不是 JSON 对象"))
            continue
        items.append((lineno, item))
    if not items and not line_errors:
        raise ValueError("JSONL 文件为空（零非空行）")
    return items, line_errors


# ----------------------------------------------------------------------
# 装载入口
# ----------------------------------------------------------------------

def load_records(
    source: Union[str, Path], *, skip_invalid: bool = True
) -> LoadResult:
    """从本地源装载公告记录（规范化入口：raw → AnnouncementRecord）。

    Args:
        source: ``.json`` / ``.jsonl`` 文件或包含它们的目录。
        skip_invalid: ``True``（默认）时坏文件/坏记录登记进
            :attr:`LoadResult.failures` 后继续；``False`` 时第一条
            失败即抛对应异常（严格模式）。

    Returns:
        装载结果（成功记录 + 失败明细 + 文件数）。

    Raises:
        SourceError: 源路径/类型问题（无论 skip_invalid）。
        ValueError / RecordValidationError: skip_invalid=False 时的
            首个载荷/记录错误。
    """
    files = resolve_source_files(source)
    result = LoadResult()
    result.files_read = len(files)

    for path in files:
        if path.suffix.lower() == ".jsonl":
            try:
                items, line_errors = _read_jsonl_items(path)
            except ValueError as exc:
                # 文件级失败（空文件/不可读）——坏文件不殃及后续文件
                if skip_invalid:
                    result.add_failure(path.name, str(exc))
                    continue
                raise
            # 行级失败先登记（坏行不殃及好行）
            for lineno, message in line_errors:
                origin = f"{path.name}:{lineno}"
                if skip_invalid:
                    result.add_failure(origin, f"第 {lineno} 行 {message}")
                else:
                    raise ValueError(f"{origin}: 第 {lineno} 行 {message}")
            iterable = [
                (f"{path.name}:{lineno}", payload)
                for lineno, payload in items
            ]
        else:
            try:
                payloads = _read_json_payload(path)
            except ValueError as exc:
                if skip_invalid:
                    result.add_failure(path.name, str(exc))
                    continue
                raise
            iterable = [(path.name, payload) for payload in payloads]

        for origin, payload in iterable:
            try:
                result.records.append(AnnouncementRecord.from_raw(payload))
            except (ValueError, TypeError) as exc:
                if skip_invalid:
                    result.add_failure(origin, str(exc))
                    continue
                raise
    return result
