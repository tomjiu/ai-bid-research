"""db --export 研究快照导出 CLI 测试（#601 R34）。

覆盖 CSV/JSON 双格式、文件/STDOUT 双落点、关键词过滤、条数上限、
空库导出、库不存在与目标不可写错误面。
"""

import json

import pytest

import main as cli
from src.storage.database import BidDatabase


@pytest.fixture()
def db_with_rows(tmp_path):
    """构造含两条记录（含/不含 requirements）的数据库。"""
    db_path = tmp_path / "bids.db"
    with BidDatabase(db_path) as db:
        db.import_bids(
            [
                {
                    "bid_id": "X-1",
                    "project_name": "智慧城市一期",
                    "region": "浙江",
                    "budget": 350.0,
                    "publish_date": "2026-01-05",
                    "requirements": ["ISO9001", "业绩 2 项"],
                },
                {
                    "bid_id": "X-2",
                    "project_name": "政务云平台",
                    "region": "江苏",
                    "budget": 800.0,
                    "publish_date": "2026-02-10",
                },
            ]
        )
    return db_path


class TestCsvExport:
    """CSV 快照面。"""

    def test_export_csv_to_file(self, db_with_rows, tmp_path, capsys):
        """落盘：utf-8-sig 表头 + requirements 分号拼接 + stderr 汇总。"""
        out = tmp_path / "snap.csv"
        rc = cli.main(
            ["db", "--db", str(db_with_rows), "--export", "csv",
             "--out", str(out)]
        )
        assert rc == 0
        text = out.read_text(encoding="utf-8-sig")
        lines = text.strip().splitlines()
        assert lines[0].startswith("bid_id,project_name,region,budget")
        assert any("X-1" in ln and "ISO9001;业绩 2 项" in ln for ln in lines)
        assert "已导出 2 条" in capsys.readouterr().err

    def test_export_csv_stdout(self, db_with_rows, capsys):
        """STDOUT：纯 CSV 载荷（机器可读，无杂行）。"""
        rc = cli.main(["db", "--db", str(db_with_rows), "--export", "csv"])
        assert rc == 0
        captured = capsys.readouterr()
        assert captured.out.startswith("bid_id,")
        assert "X-2" in captured.out


class TestJsonExport:
    """JSON 快照面。"""

    def test_export_json_keeps_requirements_list(
        self, db_with_rows, tmp_path
    ):
        """落盘：requirements 保持列表；只导 12 业务列。"""
        out = tmp_path / "snap.json"
        rc = cli.main(
            ["db", "--db", str(db_with_rows), "--export", "json",
             "--out", str(out)]
        )
        assert rc == 0
        data = json.loads(out.read_text(encoding="utf-8"))
        assert len(data) == 2
        first = next(r for r in data if r["bid_id"] == "X-1")
        assert first["requirements"] == ["ISO9001", "业绩 2 项"]
        assert "id" not in first
        assert "created_at" not in first

    def test_export_json_stdout(self, db_with_rows, capsys):
        """STDOUT：纯 JSON 载荷可直接 json.loads。"""
        rc = cli.main(
            ["db", "--db", str(db_with_rows), "--export", "json"]
        )
        assert rc == 0
        data = json.loads(capsys.readouterr().out)
        assert {r["bid_id"] for r in data} == {"X-1", "X-2"}


class TestExportFilters:
    """过滤与上限。"""

    def test_keyword_filter(self, db_with_rows, capsys):
        rc = cli.main(
            ["db", "--db", str(db_with_rows), "--export", "json",
             "--query", "政务云"]
        )
        assert rc == 0
        data = json.loads(capsys.readouterr().out)
        assert [r["bid_id"] for r in data] == ["X-2"]

    def test_limit_caps_rows(self, db_with_rows, capsys):
        rc = cli.main(
            ["db", "--db", str(db_with_rows), "--export", "json",
             "--limit", "1"]
        )
        assert rc == 0
        assert len(json.loads(capsys.readouterr().out)) == 1


class TestExportEdges:
    """空库与错误面。"""

    def test_empty_db_exports_header_only(self, tmp_path, capsys):
        db_path = tmp_path / "empty.db"
        with BidDatabase(db_path):
            pass
        rc = cli.main(
            ["db", "--db", str(db_path), "--export", "csv"]
        )
        assert rc == 0
        out = capsys.readouterr().out.strip()
        assert out.count("\n") == 0  # 仅表头行
        assert out.startswith("bid_id,")

    def test_missing_db_rejected(self, tmp_path, capsys):
        rc = cli.main(
            ["db", "--db", str(tmp_path / "nope.db"), "--export", "csv"]
        )
        assert rc == 2
        assert "不存在" in capsys.readouterr().err

    def test_unwritable_out_rejected(self, db_with_rows, tmp_path):
        rc = cli.main(
            ["db", "--db", str(db_with_rows), "--export", "csv",
             "--out", str(tmp_path / "no" / "dir" / "x.csv")]
        )
        assert rc == 2
