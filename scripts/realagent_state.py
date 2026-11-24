#!/usr/bin/env python3
"""realagent_state.py —— run_real_llm_path 的状态持久层（#113 审计修复批）。

背景（2026-11-24 机器审计实锤）：旧 save_state 是「全量重建」——每次保存
只带当轮 extra 键，其余键全部丢弃；断点续跑（9 轮）每轮重启进程后：

- P4.6 重跑时 cov0 unmapped=0 → mapping_log=[] → `scoring_mapping.decisions`
  被 `[]` 覆盖（首轮 36 项映射决策洗掉——审计缺口 1：REPORT.md 称
  「driver-state.json 含 13 节次修复决策日志」而实际 decisions=[]）；
- P6.5 repair_log 只活在当轮进程内存，轮次边界一过即被后续保存洗掉。

本模块把状态持久改为**读-改-写合并**：extra 键覆盖、既有键保留；
scoring_mapping.decisions / repair 两个列表键提供按判别键的累积合并
（幂等去重——resume 轮重跑安全）。纯函数无副作用，tests 可直测。
"""

from __future__ import annotations

import json
import os
from typing import Any, Callable

# 累积语义键：值是 list[dict]，跨轮合并（同判别键后者覆盖前者）
_ACCUM_LIST_KEYS = ("scoring_mapping", "repair")


def _merge_accum(old_value: Any, new_value: Any) -> Any:
    """累积合并：dict 外层键保留，decisions 子列表按判别键去重合并。

    形态约定（run_real_llm_path 实际产出）：
    - scoring_mapping = {"unmapped_before": int, "unmapped_after": int,
                          "decisions": [{req_id, section_id, method}, ...]}
    - repair = [{round, sid, why, floor, ban, words, citations}, ...]
    判别键：scoring_mapping.decisions 按 req_id；repair 按 (round, sid)。
    """
    if not isinstance(old_value, dict) or not isinstance(new_value, dict):
        return new_value  # 非预期形态——新值直盖（保守：不猜合并）

    merged = dict(old_value)
    for k, nv in new_value.items():
        if k in ("decisions", "log") and isinstance(merged.get(k), list) and isinstance(nv, list):
            # decisions：req_id 判别；log：全对象判别（round/sid 在对象里）
            key_fn: Callable[[dict], Any]
            key_fn = (lambda d: d.get("req_id")) if k == "decisions" else (
                lambda d: (d.get("round"), d.get("sid")))
            by_key = {key_fn(d): d for d in merged[k] if isinstance(d, dict)}
            for d in nv:
                if isinstance(d, dict):
                    by_key[key_fn(d)] = d  # 幂等重提更新
            merged[k] = list(by_key.values())
        else:
            merged[k] = nv  # 标量（unmapped_before 等）：新值覆盖
    return merged


def merge_state(
    state_path: str,
    base: dict,
    extra: dict | None = None,
) -> dict:
    """读-改-写合并：既有 state 的键保留（_ACCUM_LIST_KEYS 走累积语义），
    base 是每轮重建的基础字段（project_id/star_missing 等恒新鲜面），
    extra 是当轮保存的增量键。返回合并后的完整 state（调用方负责落盘）。"""
    existing: dict = {}
    if os.path.exists(state_path):
        try:
            existing = json.load(open(state_path))
        except (OSError, ValueError):
            existing = {}  # 坏盘文件不阻断跑批——从 base 重建
    merged = dict(existing)
    merged.update(base)  # 基础字段恒覆盖（新鲜面）
    for k, v in (extra or {}).items():
        if k in _ACCUM_LIST_KEYS and k in merged:
            merged[k] = _merge_accum(merged[k], v)
        else:
            merged[k] = v  # draft.stats 等调用方已自维护全量——直盖
    return merged


def save_state(
    state_path: str,
    base: dict,
    extra: dict | None = None,
) -> dict:
    """merge_state + 落盘（原子写：tmp → rename，防中途断电留半个 JSON）。"""
    merged = merge_state(state_path, base, extra)
    tmp = state_path + ".tmp"
    os.makedirs(os.path.dirname(state_path) or ".", exist_ok=True)
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=1)
    os.replace(tmp, state_path)
    return merged


def count_evidence_citations(docx_path: str, ev_ids: list[str]) -> dict:
    """成品 docx 的 EV 引用计数（零依赖：zipfile 解 word/document.xml）。

    审计缺口 4 的检出面：EV-0065（业绩合同）实质未用（正文 0 次出现）
    无任何提示——注册证据件是否被正文实际引用，跑批结束时应留痕。
    """
    import re
    import zipfile

    if not os.path.exists(docx_path):
        return {"registered": ev_ids, "cited": [], "uncited": ev_ids, "note": "成品不在场"}
    with zipfile.ZipFile(docx_path) as z:
        xml = z.read("word/document.xml").decode("utf-8", errors="replace")
    text = re.sub(r"<[^>]+>", "", xml)
    cited = sorted({ev for ev in ev_ids if ev in text})
    return {
        "registered": ev_ids,
        "cited": cited,
        "uncited": sorted(set(ev_ids) - set(cited)),
    }
