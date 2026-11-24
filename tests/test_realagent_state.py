"""test_realagent_state.py —— #113 审计修复批：run_real_llm_path 状态持久层。

旧实现（全量重建）实锤缺陷——断点续跑 9 轮后：
- scoring_mapping.decisions 被后续轮的 [] 覆盖（REPORT.md 与
  driver-state.json 实际内容矛盾的根因）；
- P6.5 repair 历史只在当轮进程内存，轮次边界一过即被洗掉。

本测试锁读-改-写合并语义：既有键保留、extra 覆盖、累积键幂等合并、
坏文件容错、原子写；证据引用计数（zipfile 解包）两分支。
"""

from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import realagent_state  # noqa: E402


@pytest.fixture
def state_path(tmp_path):
    return str(tmp_path / "driver-state.json")


def test_merge_preserves_unrelated_keys(state_path):
    """读-改-写合并：extra 覆盖其键，其余既有键保留（全量重建缺陷的正面修复）。"""
    existing = {
        "project_id": "PRJ-0001",
        "scoring_mapping": {"unmapped_before": 36, "unmapped_after": 0,
                             "decisions": [{"req_id": "REQ-0001", "section_id": "SEC-0007",
                                            "method": "bigram-overlap:9"}]},
        "repair": [{"round": 1, "sid": "SEC-0012", "why": ["E_CHARS_BELOW_MIN"], "floor": 700}],
    }
    Path(state_path).write_text(json.dumps(existing, ensure_ascii=False), encoding="utf-8")
    merged = realagent_state.merge_state(
        state_path,
        base={"project_id": "PRJ-0001", "req_total": 380},
        extra={"draft": {"stats": [{"sid": "SEC-0007", "words": 1039}]}},
    )
    # draft（extra）覆盖、project_id/req_total（base）新鲜
    assert merged["draft"]["stats"][0]["words"] == 1039
    assert merged["req_total"] == 380
    # 既有键保留——scoring_mapping/repair 不被洗掉
    assert merged["scoring_mapping"]["decisions"][0]["req_id"] == "REQ-0001"
    assert merged["repair"][0]["sid"] == "SEC-0012"


def test_scoring_decisions_accumulate_idempotent(state_path):
    """decisions 按 req_id 累积去重：resume 轮重提同 req_id 更新而非洗史。"""
    first = {
        "scoring_mapping": {"unmapped_before": 36, "unmapped_after": 0,
                             "decisions": [
                                 {"req_id": "REQ-0001", "section_id": "SEC-0007"},
                                 {"req_id": "REQ-0002", "section_id": "SEC-0008"}]}}
    Path(state_path).write_text(json.dumps(first, ensure_ascii=False), encoding="utf-8")
    realagent_state.save_state(
        state_path, base={"project_id": "PRJ"},
        extra={"scoring_mapping": {"unmapped_before": 0, "unmapped_after": 0,
                                    "decisions": [
                                        {"req_id": "REQ-0002", "section_id": "SEC-0009"},
                                        {"req_id": "REQ-0003", "section_id": "SEC-0010"}]}},
    )
    merged = json.loads(Path(state_path).read_text(encoding="utf-8"))
    by_req = {d["req_id"]: d["section_id"] for d in merged["scoring_mapping"]["decisions"]}
    # 三项都在；REQ-0002 取重提新值（幂等更新）
    assert by_req == {"REQ-0001": "SEC-0007", "REQ-0002": "SEC-0009", "REQ-0003": "SEC-0010"}
    # 标量取新值（终态）
    assert merged["scoring_mapping"]["unmapped_after"] == 0


def test_repair_log_accumulates_across_rounds(state_path):
    """repair 按 (round, sid) 判别——跨轮修复历史不被轮次边界洗掉。"""
    Path(state_path).write_text(json.dumps(
        {"repair": [{"round": 1, "sid": "SEC-0012", "floor": 700}]}, ensure_ascii=False),
        encoding="utf-8")
    realagent_state.save_state(
        state_path, base={"project_id": "PRJ"},
        extra={"repair": [{"round": 2, "sid": "SEC-0030", "floor": 800},
                          {"round": 1, "sid": "SEC-0012", "floor": 900}]},  # 重提更新
    )
    merged = json.loads(Path(state_path).read_text(encoding="utf-8"))
    got = {(r["round"], r["sid"]): r["floor"] for r in merged["repair"]}
    assert got == {(1, "SEC-0012"): 900, (2, "SEC-0030"): 800}


def test_corrupt_state_rebuilds_from_base(state_path):
    """坏盘 JSON 不阻断跑批——从 base 重建（容错面）。"""
    Path(state_path).write_text("{not json", encoding="utf-8")
    merged = realagent_state.merge_state(state_path, base={"project_id": "PRJ-X"}, extra=None)
    assert merged == {"project_id": "PRJ-X"}


def test_save_is_atomic_no_tmp_residue(state_path):
    """原子写：tmp→rename，落盘后无 .tmp 残留。"""
    realagent_state.save_state(state_path, base={"a": 1}, extra={"b": 2})
    assert Path(state_path).exists()
    assert not Path(state_path + ".tmp").exists()
    assert json.loads(Path(state_path).read_text()) == {"a": 1, "b": 2}


def _mini_docx(tmp_path, body: str) -> str:
    """零依赖造 mini docx：word/document.xml 单段。"""
    xml = (f'<?xml version="1.0"?><w:document xmlns:w="http://schemas.openxmlformats.org/'
           f'wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>{body}</w:t></w:r>'
           f'</w:p></w:body></w:document>')
    p = tmp_path / "mini.docx"
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("word/document.xml", xml)
    return str(p)


def test_evidence_citation_counts(tmp_path):
    """EV 引用计数：cited/uncited 正确分桶（审计缺口 4 的检出面）。"""
    docx = _mini_docx(tmp_path, "我方具备 [EV-0063] 所列资质；营业执照另附。")
    got = realagent_state.count_evidence_citations(docx, ["EV-0063", "EV-0064", "EV-0065"])
    assert got["cited"] == ["EV-0063"]
    assert got["uncited"] == ["EV-0064", "EV-0065"]


def test_evidence_citation_missing_docx(tmp_path):
    """成品不在场分支：全部记 uncited（note 标注），不抛异常。"""
    got = realagent_state.count_evidence_citations(
        str(tmp_path / "nope.docx"), ["EV-0063"])
    assert got["uncited"] == ["EV-0063"]
    assert got["note"] == "成品不在场"
