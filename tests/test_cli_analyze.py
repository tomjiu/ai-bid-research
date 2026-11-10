"""analyze 子命令 CLI 测试（#601 批次 C 第 15 轮）。"""

import pytest

import main as cli
from src.storage.database import BidDatabase


@pytest.fixture()
def filled_db(tmp_path):
    """预置 6 条记录的研究库。"""
    records = []
    for i in range(6):
        records.append(
            {
                "bid_id": f"AN-{i:02d}",
                "project_name": "智慧城市平台" if i % 2 == 0 else "政务云项目",
                "region": ["浙江", "江苏"][i % 2],
                "budget": 100.0 * (i + 1),
                "publish_date": f"2026-1{i % 2}-{(i % 27) + 1:02d}",
                "purchaser": f"买家{i % 3}",
                "winner": "甲公司" if i < 2 else None,
            }
        )
    path = tmp_path / "b.db"
    with BidDatabase(path) as db:
        db.import_bids(records)
    return path


class TestAnalyzeCLI:
    """analyze 子命令。"""

    def test_full_analysis_flow(self, filled_db, tmp_path, capsys):
        """全量分析：摘要打印 + 报告落盘 + HTML。"""
        out_dir = tmp_path / "reports"
        code = cli.main(
            [
                "analyze", "--db", str(filled_db),
                "--html", "--output-dir", str(out_dir),
            ]
        )
        out = capsys.readouterr().out
        assert code == 0
        assert "全量 6 条记录" in out
        assert "报告已生成" in out
        assert "HTML 已导出" in out
        reports = sorted(out_dir.glob("analysis_all_*.md"))
        assert len(reports) == 1
        content = reports[0].read_text(encoding="utf-8")
        assert "领域数据分析报告" in content
        assert "| 智慧城市 |" in content  # 词表命中行（领域词表「智慧城市」）

    def test_keyword_filter(self, filled_db, tmp_path, capsys):
        """关键词过滤口径与 db --query 一致。"""
        code = cli.main(
            [
                "analyze", "--db", str(filled_db), "--keyword", "政务云",
                "--output-dir", str(tmp_path / "r"),
            ]
        )
        out = capsys.readouterr().out
        assert code == 0
        assert "「政务云」 3 条记录" in out
        reports = list((tmp_path / "r").glob("analysis_政务云_*.md"))
        assert len(reports) == 1

    def test_empty_db_renders_gap(self, tmp_path, capsys):
        """空库：仍退出 0，报告含数据缺口说明。"""
        db_path = tmp_path / "empty.db"
        with BidDatabase(db_path) as db:  # 建空库（只有表结构）
            pass
        code = cli.main(
            [
                "analyze", "--db", str(db_path),
                "--output-dir", str(tmp_path / "r"),
            ]
        )
        out = capsys.readouterr().out
        assert code == 0
        assert "0 条记录" in out
        report = list((tmp_path / "r").glob("analysis_all_*.md"))[0]
        assert "数据缺口" in report.read_text(encoding="utf-8")

    def test_missing_db_path_treated_as_empty(self, tmp_path, capsys):
        """库路径不存在 → 空数据集报告（不报错——分析面不替调用方决定）。"""
        code = cli.main(
            [
                "analyze", "--db", str(tmp_path / "nope.db"),
                "--output-dir", str(tmp_path / "r"),
            ]
        )
        out = capsys.readouterr().out
        assert code == 0
        assert "0 条记录" in out

    def test_help_lists_analyze(self, capsys):
        """--help 收录 analyze。"""
        with pytest.raises(SystemExit):
            cli.main(["--help"])
        assert "analyze" in capsys.readouterr().out


class TestAnalyzeJsonExport:
    """R54：analyze --json 机器可读导出面。"""

    def test_json_file_export_roundtrip(self, tmp_path, capsys):
        import json as _json

        import main as main_mod
        from src.storage.database import BidDatabase

        db = BidDatabase(tmp_path / "bids.db")
        try:
            db.save_bid(
                {
                    "bid_id": "J-1",
                    "project_name": "智慧城市平台",
                    "region": "浙江省杭州市",
                    "budget": 100.0,
                    "publish_date": "2026-01-05",
                    "winner": "甲公司",
                    "purchaser": "大数据局",
                }
            )
        finally:
            db.close()

        out = tmp_path / "analysis.json"
        rc = main_mod.main(
            [
                "analyze", "--db", str(tmp_path / "bids.db"),
                "--json", str(out),
                "--output-dir", str(tmp_path / "reports"),
            ]
        )
        assert rc == 0
        payload = _json.loads(out.read_text(encoding="utf-8"))
        assert payload["record_count"] == 1
        assert payload["supplier_profiles"][0]["winner"] == "甲公司"
        assert payload["province_distribution"]["distribution"]["浙江省"] == 1
        # R45 字节契约：LF 行尾
        assert b"\r" not in out.read_bytes()
        assert "分析 JSON 已导出" in capsys.readouterr().out

    def test_json_stdout_dash_mode(self, tmp_path, capsys):
        import json as _json

        import main as main_mod

        rc = main_mod.main(
            [
                "analyze", "--db", str(tmp_path / "empty.db"),
                "--json", "-",
                "--output-dir", str(tmp_path / "reports"),
            ]
        )
        assert rc == 0
        out = capsys.readouterr().out
        json_line = next(
            ln for ln in out.splitlines() if ln.startswith("{")
        )
        payload = _json.loads(json_line)
        assert payload["record_count"] == 0

    def test_json_export_too_long_path_actionable(self, tmp_path, monkeypatch):
        import sys as _sys

        import main as main_mod

        monkeypatch.setattr(_sys, "platform", "win32")
        deep = tmp_path / ("x" * 240) / ("y" * 40) / "a.json"
        rc = main_mod.main(
            [
                "analyze", "--db", str(tmp_path / "e.db"),
                "--json", str(deep),
                "--output-dir", str(tmp_path / "r"),
            ]
        )
        # 长路径防护触发 → rc=2 且报错可行动（不落误导性 FileNotFoundError）
        assert rc == 2
