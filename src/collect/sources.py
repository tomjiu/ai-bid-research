"""本地源读取器（JSON / JSONL / CSV 三形态，#601 批次 A；CSV 为 R31、
读取器注册表为 R32 扩展）。

设计说明
--------
采集面的默认源是**本地文件**（离线可测，PYTHON-BOUNDARY 研究面定性）：

- ``.json`` 文件：JSON 数组（每元素一条公告）或单 JSON 对象；
- ``.jsonl`` 文件：每行一个 JSON 对象（行式流式形态，空行容忍）；
- ``.csv`` 文件（R31）：首行表头（规范名或中文别名均可，
  ``AnnouncementRecord.from_raw`` 统一归一），每数据行一条公告
  （行级失败粒度；UTF-8 含 BOM 容忍；**单元格内换行不支持**——
  含换行源请先清洗或改用 JSONL）；
- 目录源：收集全部 ``*.json`` / ``*.jsonl`` / ``*.csv``，按文件名排序（确定性——
  同一批文件两次运行产出顺序一致，研究可复现）。

失败语义（对照 AGENTS「不静默吞错」纪律）：

- 单条/单文件损坏**不中断整批**（缺一行坏数据就丢整目录不可接受）；
- 但失败必须**计数并逐条登记**在 :attr:`LoadResult.failures`
  （origin 携带文件名与 jsonl 行号），调用方决定打印/入库；
- ``skip_invalid=False`` 时第一条失败即抛——严格模式供断言用。
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

from src.collect.records import AnnouncementRecord

#: 行式读取器签名：``Path → (items, row_errors)``（同 _read_jsonl_items）。
RowReader = Callable[[Path], tuple]


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
        SourceError: 路径不存在，或目录内无受支持扩展名
            （``.json`` + 已注册行式读取器）的源文件，
            或文件扩展名不支持。
    """
    path = Path(source)
    if not path.exists():
        raise SourceError(f"源路径不存在: {path}")
    suffixes = supported_suffixes()
    if path.is_dir():
        files = sorted(
            p for p in path.iterdir() if p.suffix.lower() in suffixes
        )
        if not files:
            raise SourceError(
                f"目录内无 {'/'.join(suffixes)} 源文件: {path}"
            )
        return files
    if path.suffix.lower() not in suffixes:
        raise SourceError(
            f"不支持的源文件类型: {path.suffix or '(无扩展名)'}"
            f"（支持 {'/'.join(suffixes)}）"
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


def _read_csv_rows(path: Path) -> tuple:
    """读取 CSV 载荷（行级粒度：坏行不殃及好行，#601 R31）。

    约定：

    - 首行为表头（字段名支持规范名与中文别名，``from_raw`` 统一归一）；
    - 空白单元格置 ``None``（「缺失」与「显式留空」同口径）；
    - 列数与表头不齐的行登记行级失败；
    - 编码 UTF-8（BOM 容忍 ``utf-8-sig``）；
    - **单元格内换行不支持**（研究面约定：导出源先清洗，或改用 JSONL）。

    Returns:
        ``(items, row_errors)`` 二元组（与 :func:`_read_jsonl_items` 同形）：
        行号从 2 起（1 为表头行）。

    Raises:
        ValueError: 文件为空 / 无表头 / 零数据行 / 解码失败
            （文件级失败语义同 JSONL「零非空行」——大概率是截断/损坏）。
    """
    try:
        text = path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError(f"CSV 解码失败（须 UTF-8）: {exc}") from exc
    lines = text.splitlines()
    if not lines or not lines[0].strip():
        raise ValueError("CSV 文件为空（无表头行）")
    try:
        header = next(csv.reader([lines[0]]))
    except csv.Error as exc:
        raise ValueError(f"CSV 表头语法错误: {exc}") from exc
    header = [cell.strip() for cell in header]
    if not any(header):
        raise ValueError("CSV 表头行为空")
    data_lines = lines[1:]
    if not any(line.strip() for line in data_lines):
        raise ValueError("CSV 文件为空（零数据行）")
    items: List[tuple] = []
    row_errors: List[tuple] = []
    for lineno, line in enumerate(data_lines, start=2):
        if not line.strip():
            continue
        try:
            row = next(csv.reader([line]))
        except csv.Error as exc:
            row_errors.append((lineno, f"CSV 语法错误: {exc}"))
            continue
        if len(row) != len(header):
            row_errors.append(
                (lineno, f"列数不齐（表头 {len(header)} 列，该行 {len(row)} 列）")
            )
            continue
        payload: Dict[str, Any] = {}
        for key, cell in zip(header, row):
            cell = cell.strip()
            payload[key] = cell if cell else None
        items.append((lineno, payload))
    return items, row_errors


# ----------------------------------------------------------------------
# 读取器注册表（R32）——研究脚本扩展点
# ----------------------------------------------------------------------

#: 行式源读取器注册表（后缀 → 读取函数）。注册即可被目录源收集与
#: 单文件分发自动识别（无需改动本文件）。
_ROW_READERS: Dict[str, RowReader] = {
    ".csv": _read_csv_rows,
    ".jsonl": _read_jsonl_items,
}


def supported_suffixes() -> tuple:
    """当前受支持的源扩展名（``.json`` + 已注册行式读取器，排序确定性）。"""
    return tuple(sorted({".json", *_ROW_READERS}))


def register_source_reader(suffix: str, reader: RowReader) -> None:
    """注册行式源读取器（研究面扩展点，R32）。

    注册后目录源自动收集该扩展名、单文件源自动分发——研究脚本
    无需改动 ``sources.py`` 即可接入新格式（如 ``.tsv``）。

    Args:
        suffix: 扩展名（须以 ``.`` 开头，大小写不敏感，归一为小写）。
        reader: 读取函数，签名同 :func:`_read_jsonl_items`：
            ``Path → (items, row_errors)``。

    Raises:
        ValueError: suffix 不以 ``.`` 开头，或 reader 不可调用。
    """
    name = str(suffix).strip().lower()
    if not name.startswith("."):
        raise ValueError(f"扩展名须以 . 开头: {suffix!r}")
    if not callable(reader):
        raise ValueError(f"reader 不可调用: {reader!r}")
    _ROW_READERS[name] = reader


# ----------------------------------------------------------------------
# 装载入口
# ----------------------------------------------------------------------

def load_records(
    source: Union[str, Path],
    *,
    skip_invalid: bool = True,
    since: Optional[float] = None,
) -> LoadResult:
    """从本地源装载公告记录（规范化入口：raw → AnnouncementRecord）。

    Args:
        source: ``.json`` / ``.jsonl`` / ``.csv`` 文件或包含它们的目录。
        skip_invalid: ``True``（默认）时坏文件/坏记录登记进
            :attr:`LoadResult.failures` 后继续；``False`` 时第一条
            失败即抛对应异常（严格模式）。
        since: 增量水位（epoch 秒）——只读 mtime 晚于水位的文件；
            目录内无新文件时返回**空结果**（零记录零失败，
            不是错误——「无新文件」是增量的正常结局）。

    Returns:
        装载结果（成功记录 + 失败明细 + 文件数）。

    Raises:
        SourceError: 源路径/类型问题（无论 skip_invalid）。
        ValueError / RecordValidationError: skip_invalid=False 时的
            首个载荷/记录错误。
    """
    files = resolve_source_files(source)
    if since is not None:
        # 增量水位：只读新文件（mtime 严格晚于水位）
        files = [p for p in files if p.stat().st_mtime > since]
        if not files:
            return LoadResult(files_read=0)  # 无新文件——空结果不报错
    result = LoadResult()
    result.files_read = len(files)

    for path in files:
        row_reader = _ROW_READERS.get(path.suffix.lower())

        if row_reader is not None:
            try:
                items, line_errors = row_reader(path)
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
