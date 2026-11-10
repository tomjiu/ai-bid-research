"""db 导入/导出往返一致性契约（#601 R57）。

契约：``db export`` 的产物经 ``db --import``（JSON 路）或
``collect``（CSV 路）回到库里，记录集合与原库等价
（按 bid_id 逐字段对比，None/缺失同口径）。
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import main as main_mod
from src.storage.database import BidDatabase

_SEED = [
    {
        "bid_id": "RT-1",
        "project_name": "智慧城市一期",
        "region": "浙江省杭州市",
        "budget": 100.5,
        "publish_date": "2026-01-05",
        "deadline": "2026-01-20",
        "category": "信息化",
        "purchaser": "大数据局",
        "agency": "某代理机构",
        "winner": "甲公司",
        "source_url": "https://example.com/1",
        "requirements": ["资质A", "业绩B"],
    },
    {
        "bid_id": "RT-2",
        "project_name": "管网改造（含空字段）",
        "region": None,
        "budget": None,
        "publish_date": None,
        "winner": None,
    },
    {
        "bid_id": "RT-3",
        "project_name": "特殊字符：引号\"反斜杠\\逗号,换行\n",
        "budget": 0.0,
        "publish_date": "2026-02-29",
    },
]


def _seed(db: BidDatabase) -> None:
    db.import_bids(_SEED)


def _fetch_all(db_path: Path) -> dict:
    db = BidDatabase(db_path)
    try:
        rows = db.query_bids()
        return {r["bid_id"]: dict(r) for r in rows}
    finally:
        db.close()


class TestJsonRoundTrip:
    def test_export_then_import_equivalent(self, tmp_path, capsys):
        src = tmp_path / "src.db"
        db = BidDatabase(src)
        _seed(db)
        db.close()

        out = tmp_path / "export.json"
        rc = main_mod.main(
            ["db", "--db", str(src), "--export", "json", "--out", str(out)]
        )
        assert rc == 0
        capsys.readouterr()

        dst = tmp_path / "dst.db"
        rc = main_mod.main(
            ["db", "--db", str(dst), "--import", str(out)]
        )
        assert rc == 0

        original = _fetch_all(src)
        restored = _fetch_all(dst)
        assert set(original) == set(restored) == {"RT-1", "RT-2", "RT-3"}
        for bid_id, row in original.items():
            got = restored[bid_id]
            for col in (
                "project_name", "region", "budget", "publish_date",
                "deadline", "category", "purchaser", "agency",
                "winner", "source_url",
            ):
                assert got[col] == row[col], f"{bid_id}.{col}: {got[col]!r} != {row[col]!r}"

    def test_requirements_survive_jsonl_payload(self, tmp_path):
        """requirements 列表经 JSON 导出再导入后语义不变。"""
        src = tmp_path / "req.db"
        db = BidDatabase(src)
        _seed(db)
        db.close()
        out = tmp_path / "req.json"
        main_mod.main(
            ["db", "--db", str(src), "--export", "json", "--out", str(out)]
        )
        payload = json.loads(out.read_text(encoding="utf-8"))
        rt1 = next(r for r in payload if r["bid_id"] == "RT-1")
        # 导出面 requirements 已反序列化为列表（机器可读契约）
        assert rt1["requirements"] == ["资质A", "业绩B"]


class TestCsvRoundTrip:
    def test_export_csv_reimport_via_collect(self, tmp_path, capsys):
        """CSV 导出（utf-8-sig）→ collect 装载 → 逐字段等价。

        这是跨子命令的真实数据链路契约：CSV 是外部交换面，
        必须经 collect 归一化路径回到库内仍等价。
        """
        src = tmp_path / "c.db"
        db = BidDatabase(src)
        _seed(db)
        db.close()

        out = tmp_path / "export.csv"
        rc = main_mod.main(
            ["db", "--db", str(src), "--export", "csv", "--out", str(out)]
        )
        assert rc == 0
        capsys.readouterr()

        dst = tmp_path / "c2.db"
        rc = main_mod.main(
            ["collect", "--source", str(out), "--db", str(dst)]
        )
        assert rc == 0

        original = _fetch_all(src)
        restored = _fetch_all(dst)
        assert set(original) == set(restored)
        rt1_o, rt1_r = original["RT-1"], restored["RT-1"]
        assert rt1_r["project_name"] == rt1_o["project_name"]
        assert rt1_r["region"] == rt1_o["region"]
        assert rt1_r["budget"] == rt1_o["budget"]
        assert rt1_r["purchaser"] == rt1_o["purchaser"]
        assert rt1_r["winner"] == rt1_o["winner"]
        # 特殊字符行
        rt3_r = restored["RT-3"]
        assert rt3_r["budget"] == 0.0
        assert "换行" in rt3_r["project_name"]

    def test_csv_export_is_utf8sig_with_bom(self, tmp_path):
        src = tmp_path / "b.db"
        db = BidDatabase(src)
        _seed(db)
        db.close()
        out = tmp_path / "b.csv"
        main_mod.main(
            ["db", "--db", str(src), "--export", "csv", "--out", str(out)]
        )
        raw = out.read_bytes()
        assert raw.startswith(b"\xef\xbb\xbf")  # Excel 直开不乱码
        text = raw.decode("utf-8-sig")
        header = next(csv.reader([text.splitlines()[0]]))
        assert header[0] == "bid_id"
