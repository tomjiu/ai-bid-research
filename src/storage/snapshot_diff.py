"""研究快照对比（非生产链路——仅供研究，见 docs/PYTHON-BOUNDARY.md）。

R60：两次 ``db export`` JSON 快照的**结构化差异**——数据集演化
追踪面（两次采集之间发生了什么：新增/移除/字段变更）。

口径：

- 以 ``bid_id`` 为身份锚点；缺 bid_id 的行跳过并计数（不猜身份）；
- 字段对比前做**形态归一**（``None``/缺失同口径；``requirements``
  的 JSON 字符串 ↔ 列表折叠到同形态）——避免导出版本差异伪装成
  数据变更；
- 全部描述性输出，不做任何语义判断（如「变更是否可疑」）。
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional


def _normalize(value: Any) -> Any:
    """字段形态归一：缺失≈None；requirements 字符串折叠为列表。"""
    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        if stripped.startswith("["):
            try:
                parsed = json.loads(stripped)
                if isinstance(parsed, list):
                    return parsed
            except json.JSONDecodeError:
                pass
        return stripped
    return value


def _row_key(row: Dict[str, Any]) -> Optional[str]:
    bid = _normalize(row.get("bid_id"))
    return str(bid) if bid else None


def diff_snapshots(
    old_rows: List[Dict[str, Any]],
    new_rows: List[Dict[str, Any]],
    *,
    max_examples: int = 10,
) -> Dict[str, Any]:
    """对比两份快照（按 ``bid_id`` 锚定）。

    Args:
        old_rows: 旧快照行列表（``db export --export json`` 产物）。
        new_rows: 新快照行列表。
        max_examples: 新增/移除示例条数上限（明细全量在
            ``changed``，本参数只限摘要展示面）。

    Returns:
        JSON 可序列化结果：

        - ``old_count`` / ``new_count``：有效行数（去重后）；
        - ``added`` / ``removed``：bid_id 列表（升序）；
        - ``changed``：``{bid_id: {字段: {"old":, "new":}}}``；
        - ``unchanged_count``：无变化行数；
        - ``skipped``：缺 bid_id / 重复 bid_id 的行数（诚实计数）。
    """
    old_map: Dict[str, Dict[str, Any]] = {}
    new_map: Dict[str, Dict[str, Any]] = {}
    skipped = 0
    for row in old_rows:
        key = _row_key(row) if isinstance(row, dict) else None
        if key is None or key in old_map:
            skipped += 1
            continue
        old_map[key] = row
    for row in new_rows:
        key = _row_key(row) if isinstance(row, dict) else None
        if key is None or key in new_map:
            skipped += 1
            continue
        new_map[key] = row

    added = sorted(set(new_map) - set(old_map))
    removed = sorted(set(old_map) - set(new_map))

    changed: Dict[str, Dict[str, Any]] = {}
    unchanged = 0
    for bid_id in sorted(set(old_map) & set(new_map)):
        old_row, new_row = old_map[bid_id], new_map[bid_id]
        fields = set(old_map[bid_id]) | set(new_map[bid_id])
        field_diffs: Dict[str, Any] = {}
        for field in sorted(fields):
            if field == "bid_id":
                continue
            old_val = _normalize(old_row.get(field))
            new_val = _normalize(new_row.get(field))
            if old_val != new_val:
                field_diffs[field] = {"old": old_val, "new": new_val}
        if field_diffs:
            changed[bid_id] = field_diffs
        else:
            unchanged += 1

    return {
        "old_count": len(old_map),
        "new_count": len(new_map),
        "added": added,
        "removed": removed,
        "changed": changed,
        "unchanged_count": unchanged,
        "skipped": skipped,
        "added_examples": added[:max_examples],
        "removed_examples": removed[:max_examples],
    }


def render_diff_summary(diff: Dict[str, Any], *, verbose: bool = False) -> str:
    """diff 结果的人读摘要（多行文本）。

    Args:
        diff: :func:`diff_snapshots` 产物。
        verbose: ``True`` 时变更明细全量展开（缺省只列前 10 条）。
    """
    lines = [
        f"快照对比：旧 {diff['old_count']} 条 vs 新 {diff['new_count']} 条",
        f"新增 {len(diff['added'])} 条"
        + (
            "（示例）："
            + "、".join(diff["added_examples"])
            if diff["added_examples"]
            else ""
        ),
        f"移除 {len(diff['removed'])} 条"
        + (
            "（示例）："
            + "、".join(diff["removed_examples"])
            if diff["removed_examples"]
            else ""
        ),
        f"变更 {len(diff['changed'])} 条，不变 {diff['unchanged_count']} 条",
    ]
    if diff["skipped"]:
        lines.append(
            f"跳过 {diff['skipped']} 行（缺/重 bid_id——不猜身份）"
        )
    if diff["changed"]:
        lines.append("变更明细：")
        items = list(diff["changed"].items())
        if not verbose:
            items = items[:10]
        for bid_id, fields in items:
            parts = [
                f"{field}: {_short(v['old'])} → {_short(v['new'])}"
                for field, v in fields.items()
            ]
            lines.append(f"  {bid_id}: {'; '.join(parts)}")
        if not verbose and len(diff["changed"]) > 10:
            lines.append(
                f"  … 另有 {len(diff['changed']) - 10} 条（全量见 JSON 导出）"
            )
    return "\n".join(lines)


def _short(value: Any, limit: int = 24) -> str:
    text = "∅" if value is None else str(value)
    if len(text) > limit:
        return text[: limit - 1] + "…"
    return text
