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
