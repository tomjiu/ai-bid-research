"""db --export --dedupe 近重复感知去重快照测试（#601 R88）。

契约：簇内保留首条、库不动、快照纯数组（--diff 消费方不变）、
剔除分账走 stderr、CSV/JSON 双格式同语义。
"""

from __future__ import annotations

import csv
import json

import pytest

from main import main
from src.storage.database import BidDatabase


@pytest.fixture()
def dup_db(tmp_path):
    """库：1 组五条同名（FX-07~11 形态）+ 2 条独立。"""
    db = BidDatabase(tmp_path / "dup.db")
    try:
        for i in range(7, 12):
            db.save_bid(
                {"bid_id": f"FX-{i:02d}", "project_name": "智慧水务运维服务",
                 "budget": 10.0 + i}
            )
        db.save_bid({"bid_id": "SOLO-1", "project_name": "独立项目甲",
                     "budget": 5.0})
        db.save_bid({"bid_id": "SOLO-2", "project_name": "独立项目乙",
                     "budget": 6.0})
    finally:
        db.close()
    return tmp_path / "dup.db"


class TestDedupeExport:
    def test_json_keeps_one_per_cluster(self, dup_db, tmp_path, capsys):
        out = tmp_path / "dedup.json"
        code = main(
            ["db", "--db", str(dup_db), "--export", "json",
             "--dedupe", "--out", str(out)]
        )
        assert code == 0
        snap = json.loads(out.read_text(encoding="utf-8"))
        ids = [r["bid_id"] for r in snap]
        # 五条同名 → 簇代表 1 条 + 2 独立。
        # 「首条」= 导出序第一条（query_bids ORDER BY publish_date
        # DESC, id DESC——无日期时最新入库者 FX-11 在前）
        assert len(ids) == 3
        assert "FX-11" in ids  # 导出序簇首保留
        assert "SOLO-1" in ids and "SOLO-2" in ids
        # 分账在 stderr（剔除 4 条簇成员，明细含最老四条）
        err = capsys.readouterr().err
        assert "剔除 4 条" in err
        assert "FX-07" in err

    def test_library_untouched(self, dup_db, tmp_path):
        """库不动——去重是导出视图，不是库操作。"""
        main(
            ["db", "--db", str(dup_db), "--export", "json",
             "--dedupe", "--out", str(tmp_path / "s.json")]
        )
        db = BidDatabase(dup_db)
        try:
            assert db.count_bids() == 7  # 原样
        finally:
            db.close()

    def test_without_flag_full_export(self, dup_db, tmp_path):
        """不开 --dedupe：行为不变（7 条全导——向后兼容）。"""
        out = tmp_path / "full.json"
        main(
            ["db", "--db", str(dup_db), "--export", "json",
             "--out", str(out)]
        )
        snap = json.loads(out.read_text(encoding="utf-8"))
        assert len(snap) == 7

    def test_csv_same_semantics(self, dup_db, tmp_path):
        out = tmp_path / "dedup.csv"
        code = main(
            ["db", "--db", str(dup_db), "--export", "csv",
             "--dedupe", "--out", str(out)]
        )
        assert code == 0
        # utf-8-sig：BOM 头（Excel 直开契约）
        raw = out.read_bytes()
        assert raw[:3] == b"\xef\xbb\xbf"
        text = raw.decode("utf-8-sig")
        rows = list(csv.DictReader(text.splitlines()))
        assert len(rows) == 3

    def test_diff_consumes_deduped_snapshot(self, dup_db, tmp_path, capsys):
        """--diff 仍可消费去重快照（纯数组兼容契约）。"""
        deduped = tmp_path / "a.json"
        full = tmp_path / "b.json"
        main(["db", "--db", str(dup_db), "--export", "json",
              "--dedupe", "--out", str(deduped)])
        main(["db", "--db", str(dup_db), "--export", "json",
              "--out", str(full)])
        code = main(
            ["db", "--db", str(dup_db), "--diff", str(deduped), str(full)]
        )
        assert code == 0
        out = capsys.readouterr().out
        # full 相对 deduped 新增了 4 条簇成员
        assert "新增" in out

    def test_no_duplicates_no_drop(self, tmp_path, capsys):
        db = BidDatabase(tmp_path / "solo.db")
        try:
            db.save_bid({"bid_id": "A-1", "project_name": "唯一名称项目",
                         "budget": 1.0})
            db.save_bid({"bid_id": "A-2", "project_name": "另一个无关项目",
                         "budget": 2.0})
        finally:
            db.close()
        out = tmp_path / "s.json"
        code = main(
            ["db", "--db", str(tmp_path / "solo.db"), "--export", "json",
             "--dedupe", "--out", str(out)]
        )
        assert code == 0
        assert "无剔除" in capsys.readouterr().err
        assert len(json.loads(out.read_text(encoding="utf-8"))) == 2
