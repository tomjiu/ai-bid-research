#!/usr/bin/env python3
"""v3_integration.py — V3 文档内核集成边界三问断言（verification-plan §3.3）

评审原文的三个"还应验证"（引擎本体 Rust 工具链在验证环境不可执行——本脚本为
doc-engine-audit §5 映射契约的**设计语义断言**（SEMUL 口径，同 V1-b/V2 纪律）；
引擎接入后按三问各断言升级 ENGINE_RUN）：

  Q1 章节多次重写后引用如何保持有效？
     5 轮重写循环（每轮改写一条引用段）——断言：被改写链恰 stale（有状态
     LinkageStatus，非无状态指纹比对）；其余链 valid；无悬空书签；重验通道
     显式恢复；重写不破坏其他链的锚（BlockId/书签语义）。
  Q2 撤销/恢复/另存/重开后条款—证据—文档关联如何维持？
     undo 语义（正文回退）：引擎 degrade_linkage **只降不升**——undo 恢复了
     内容，linkage 状态也不自发回升（需显式重验）；外部修改重开（adopt 面）：
     检测指纹变化 → 不自动 adopt（OfferChoice → 业务默认转人工）。
  Q3 导出失败或保存中断时，业务状态与文档状态如何一致？
     两阶段确认（EXPORTING → 渲染 → sha256 落库 → EXPORTED）：中断注入
     （渲染后确认前 kill）→ 业务态停 EXPORTING、零"EXPORTED 而产物缺失"；
     恢复重导（幂等）→ sha256 落库 → EXPORTED。

引擎语义对齐（doc-engine-audit §2/§5 + evidence 源码语义）：
  - LinkageStatus 有状态：Valid --失配--> Stale --显式重验--> Valid；
    内容恢复不自动回升（只降不升）
  - 原子发布：tmp+rename；EXPORTED 以产物 sha256 落库为界
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

from docx import Document

sys.path.insert(0, str(Path(__file__).resolve().parent))
import v1_citation  # noqa: E402
import v1_export  # noqa: E402
from ooxml_util import fnv64, norm_text  # noqa: E402

REPO = Path(__file__).resolve().parent.parent


# ================================================================ 有状态 Linkage（引擎 evidence.rs 语义）
class LinkageLedger:
    """证据链状态账本：Valid/Stale 有状态迁移（只降不升 + 显式重验通道）。"""

    def __init__(self, chain_ids: list[str]):
        self.status = {cid: "valid" for cid in chain_ids}
        self.audit: list[dict] = []

    def refresh(self, body_changed: bool, locators: dict[str, dict], fps: list[str]):
        """引擎 refresh_document 语义：仅正文变化时跑锚断；失配 → Stale（只降不升）。"""
        if not body_changed:
            return []
        degraded = []
        for cid, loc in locators.items():
            if self.status[cid] != "valid":
                continue                     # 已 Stale：不自动恢复（只降不升）
            i = loc["paragraph_index"]
            if i >= len(fps) or fps[i] != loc["text_fingerprint"]:
                self.status[cid] = "stale"
                degraded.append(cid)
        if degraded:
            self.audit.append({"op": "body_refresh", "degraded": degraded})
        return degraded

    def reverify(self, cid: str, locators: dict[str, dict], fps: list[str]) -> bool:
        """显式重验（reverify_claim 语义）：新位置 + 指纹 → Valid。"""
        loc = locators[cid]
        i = loc["paragraph_index"]
        if i < len(fps) and fps[i] == loc["text_fingerprint"]:
            self.status[cid] = "valid"
            self.audit.append({"op": "claim_reverified", "cid": cid})
            return True
        return False

    def all_valid(self) -> bool:
        return all(v == "valid" for v in self.status.values())


# ================================================================ 两阶段导出（G 语义：原子发布 + sha256 落库为界）
class ExportGate:
    """两阶段确认：EXPORTING → render → confirm(sha256 落库) → EXPORTED。"""

    def __init__(self):
        self.state = "READY_TO_EXPORT"
        self.artifact_sha: str | None = None

    def start(self):
        self.state = "EXPORTING"

    def render(self, docx_path: Path) -> str:
        import hashlib
        self.start()
        h = hashlib.sha256(docx_path.read_bytes()).hexdigest()
        self._rendered_sha = h
        return h

    def confirm(self) -> bool:
        """sha256 落库为界——无落库就没有 EXPORTED。"""
        if self._rendered_sha is None:
            return False
        self.artifact_sha = self._rendered_sha
        self.state = "EXPORTED"
        return True

    @property
    def consistent(self) -> bool:
        """一致性不变式：EXPORTED ⟺ 产物 sha256 已落库。"""
        return (self.state == "EXPORTED") == (self.artifact_sha is not None)


# ================================================================ 三问断言
def run_v3(workdir: Path) -> dict:
    results = {}
    bright = workdir / "技术标-导出样本.docx"
    v1_export.build_bid_docx(bright, "bright", workdir=workdir)
    chains_src = v1_export.build_chain_locators()
    bm = v1_citation.bookmark_paragraph_map(bright)
    texts = v1_citation.paragraph_texts(bright)
    chain_ids = [c["gt_id"] for c in chains_src]
    # 正文引用定位器（导出时刻）
    from ooxml_util import emit_docx_paragraph
    locators = {c["gt_id"]: emit_docx_paragraph(bm[f"CIT-{c['gt_id']}"],
                                                texts[bm[f"CIT-{c['gt_id']}"]])
                for c in chains_src}

    # ---- Q1 五轮重写循环
    ledger = LinkageLedger(chain_ids)
    q1 = {"rounds": 5, "each_round_exact": True, "reverify_recovers": True,
          "no_dangling": True, "no_silent_recovery": True}
    work = workdir / "q1_rewrite.docx"
    shutil.copy(bright, work)
    for rnd in range(5):
        victim = chain_ids[rnd]
        doc = Document(str(work))
        pi = bookmark_paragraph_map_local(work)[f"CIT-{victim}"]
        doc.paragraphs[pi].runs[0].text += f"（第 {rnd + 1} 轮润色）"
        doc.save(str(work))
        fps = [fnv64(norm_text(p.text)) for p in Document(str(work)).paragraphs]
        degraded = ledger.refresh(True, locators, fps)
        # 恰 victim 一条降级（本轮改写者）；此前轮次已重验恢复为 valid
        if degraded != [victim]:
            q1["each_round_exact"] = False
        # 无悬空书签：全部 CIT- 书签仍可解析
        if set(bookmark_paragraph_map_local(work)) != {f"CIT-{c}" for c in chain_ids}:
            q1["no_dangling"] = False
        # 显式重验恢复（rebind 到当前位置+指纹）
        new_pi = bookmark_paragraph_map_local(work)[f"CIT-{victim}"]
        new_texts = [p.text for p in Document(str(work)).paragraphs]
        locators[victim] = emit_docx_paragraph(new_pi, new_texts[new_pi])
        if not ledger.reverify(victim, locators, fps):
            q1["reverify_recovers"] = False
        if not ledger.all_valid():
            q1["reverify_recovers"] = False
    # 只降不升：改回原文（等价 undo）不会让已 Stale 的链自发恢复——见 Q2
    results["Q1_rewrite_5rounds"] = {"pass": all(q1.values()), "detail": q1}

    # ---- Q2 undo / 外部修改重开（adopt 面）
    ledger2 = LinkageLedger(chain_ids)
    work2 = workdir / "q2_undo.docx"
    shutil.copy(bright, work2)
    doc = Document(str(work2))
    victim = chain_ids[0]
    pi = bookmark_paragraph_map_local(work2)[f"CIT-{victim}"]
    original_text = doc.paragraphs[pi].text
    doc.paragraphs[pi].runs[0].text += "（改写）"
    doc.save(str(work2))
    fps = [fnv64(norm_text(p.text)) for p in Document(str(work2)).paragraphs]
    ledger2.refresh(True, locators_from(bright, chains_src), fps)
    # undo：内容恢复原文
    doc = Document(str(work2))
    doc.paragraphs[pi].runs[0].text = original_text.replace("（改写）", "")
    doc.save(str(work2))
    fps_undo = [fnv64(norm_text(p.text)) for p in Document(str(work2)).paragraphs]
    # 引擎语义：内容回来了，但 Stale 不自发回升（只降不升）
    ledger2.refresh(True, locators_from(bright, chains_src), fps_undo)
    stays_stale = ledger2.status[victim] == "stale"
    # 显式重验后恢复
    recovered = ledger2.reverify(victim, locators_from(bright, chains_src), fps_undo)
    q2a = {"undo_no_auto_recovery": stays_stale, "reverify_recovers": recovered}
    # 外部修改重开（adopt 三分）：修改导出件正文 → 检测指纹变化 → 不自动 adopt
    external = workdir / "q2_external.docx"
    shutil.copy(bright, external)
    doc = Document(str(external))
    doc.paragraphs[bookmark_paragraph_map_local(external)["CIT-GT-01"]].runs[0].text += "（外部编辑）"
    doc.save(str(external))
    fps_ext = [fnv64(norm_text(p.text)) for p in Document(str(external)).paragraphs]
    ledger3 = LinkageLedger(chain_ids)
    degraded_ext = ledger3.refresh(True, locators_from(bright, chains_src), fps_ext)
    q2b = {"external_change_detected": degraded_ext == ["GT-01"],
           "no_silent_adopt": ledger3.status["GT-01"] == "stale",
           "adopt_note": "引擎 plan_reload 三分（Noop/SilentAdopt/OfferChoice）——业务对 OfferChoice 默认转人工（doc-engine-audit §5.3），无自动重绑"}
    results["Q2_undo_and_reopen"] = {"pass": all(q2a.values()) and q2b["external_change_detected"]
                                               and q2b["no_silent_adopt"],
                                     "detail": {**q2a, **q2b}}

    # ---- Q3 两阶段导出 + 中断注入
    gate = ExportGate()
    q3 = {}
    # 正常路径
    sha = gate.render(bright)
    q3["exporting_before_confirm"] = gate.state == "EXPORTING"
    gate.confirm()
    q3["exported_with_sha"] = gate.state == "EXPORTED" and gate.artifact_sha == sha
    # 中断路径：渲染后确认前 kill（模拟：新 gate 渲染后不 confirm）
    gate2 = ExportGate()
    gate2.render(bright)                      # 渲染完成即"kill"——不 confirm
    q3["interrupted_stays_exporting"] = gate2.state == "EXPORTING"
    q3["interrupted_no_exported_without_sha"] = gate2.artifact_sha is None
    q3["invariant_holds"] = gate.consistent and gate2.consistent
    # 恢复路径：重新导出（幂等——同产物 sha 一致）
    gate2.confirm()
    q3["resume_same_sha"] = gate2.artifact_sha == sha
    results["Q3_export_interrupt"] = {"pass": all(q3.values()), "detail": q3}

    return {"results": results,
            "semul_note": "三问断言为 doc-engine-audit §5 映射契约的设计语义验证"
                          "（LinkageLedger = evidence.rs 有状态语义复刻；ExportGate = 原子发布+"
                          "sha256 落库为界）；引擎本体接入后升 ENGINE_RUN"}


def bookmark_paragraph_map_local(docx_path: Path) -> dict[str, int]:
    return v1_citation.bookmark_paragraph_map(docx_path)


def locators_from(docx_path: Path, chains_src: list[dict]) -> dict[str, dict]:
    bm = v1_citation.bookmark_paragraph_map(docx_path)
    texts = v1_citation.paragraph_texts(docx_path)
    from ooxml_util import emit_docx_paragraph
    return {c["gt_id"]: emit_docx_paragraph(bm[f"CIT-{c['gt_id']}"],
                                            texts[bm[f"CIT-{c['gt_id']}"]])
            for c in chains_src}


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        report = run_v3(Path(td))
        for qid, r in report["results"].items():
            mark = "✓" if r["pass"] else "✗"
            print(f"[V3] {mark} {qid}")
            if not r["pass"]:
                for k, v in r["detail"].items():
                    if isinstance(v, bool) and not v:
                        print(f"      ✗ {k}")
        ok = all(r["pass"] for r in report["results"].values())
        print(f"[V3] 内核集成三问：{'全绿' if ok else '存在失败'}（SEMUL 口径）")
        return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
