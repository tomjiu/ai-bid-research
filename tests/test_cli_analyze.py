"""analyze 子命令 CLI 测试（#601 批次 C 第 6 轮）。"""

from __future__ import annotations

from datetime import date

import pytest

import main as cli
from src.storage.database import BidDatabase


@pytest.fixture()
def seeded_db(tmp_path):
    """三记录数据库：覆盖金额/区域/日期/定标维度。"""
    db_path = tmp_path / "bids.db"
    with BidDatabase(db_path) as db:
        db.import_bids(
            [
                {
                    "bid_id": "A-1",
                    "project_name": "智慧城市一期平台",
                    "region": "浙江省杭州市",
                    "budget": 1200.0,
                    "publish_date": date.today().isoformat(),
                    "winner": "甲公司",
                },
                {
                    "bid_id": "A-2",
                    "project_name": "数据中心设备采购",
                    "region": "北京市",
                    "budget": 800.0,
                    "publish_date": "2026-01-15",
                    "winner": None,
                },
                {
                    "bid_id": "A-3",
                    "project_name": "智慧城市二期",
                    "region": "浙江省杭州市",
                    "budget": None,
                    "publish_date": "2026-02-20",
                    "winner": "甲公司",
                },
            ]
        )
    return db_path


class TestAnalyzeCLI:
    def test_full_flow(self, seeded_db, tmp_path, capsys):
        out_dir = tmp_path / "reports"
        code = cli.main(
            [
                "analyze",
                "--db",
                str(seeded_db),
                "--output-dir",
                str(out_dir),
            ]
        )
        assert code == 0
        out = capsys.readouterr().out
        assert "数据集：3 条项目（其中已定标 2 条）" in out
        assert "分析报告已生成" in out
        report = list(out_dir.glob("analysis_*.md"))
        assert len(report) == 1
        content = report[0].read_text(encoding="utf-8")
        assert "# 招标数据分析报告" in content
        assert "## 五、竞争密度" in content

    def test_html_export(self, seeded_db, tmp_path, capsys):
        out_dir = tmp_path / "reports"
        code = cli.main(
            [
                "analyze",
                "--db",
                str(seeded_db),
                "--output-dir",
                str(out_dir),
                "--html",
            ]
        )
        assert code == 0
        out = capsys.readouterr().out
        assert "HTML 已导出" in out
        assert list(out_dir.glob("analysis_*.html"))

    def test_keyword_filter(self, seeded_db, tmp_path, capsys):
        out_dir = tmp_path / "reports"
        code = cli.main(
            [
                "analyze",
                "--db",
                str(seeded_db),
                "--keyword",
                "智慧城市",
                "--output-dir",
                str(out_dir),
            ]
        )
        assert code == 0
        out = capsys.readouterr().out
        assert "数据集：2 条项目" in out
        assert "关键词「智慧城市」" in out

    def test_region_filter(self, seeded_db, tmp_path, capsys):
        out_dir = tmp_path / "reports"
        code = cli.main(
            [
                "analyze",
                "--db",
                str(seeded_db),
                "--region",
                "杭州",
                "--output-dir",
                str(out_dir),
            ]
        )
        assert code == 0
        assert "数据集：2 条项目" in capsys.readouterr().out

    def test_days_filter_excludes_undated(self, seeded_db, tmp_path, capsys):
        """days=1：只留今天发布的 A-1（2026-01/02 的旧记录排除）。"""
        out_dir = tmp_path / "reports"
        code = cli.main(
            [
                "analyze",
                "--db",
                str(seeded_db),
                "--days",
                "1",
                "--output-dir",
                str(out_dir),
            ]
        )
        assert code == 0
        assert "数据集：1 条项目" in capsys.readouterr().out

    def test_custom_title(self, seeded_db, tmp_path):
        out_dir = tmp_path / "reports"
        code = cli.main(
            [
                "analyze",
                "--db",
                str(seeded_db),
                "--title",
                "华东区态势",
                "--output-dir",
                str(out_dir),
            ]
        )
        assert code == 0
        report = list(out_dir.glob("analysis_*.md"))[0]
        assert "# 华东区态势" in report.read_text(encoding="utf-8")

    def test_missing_db_exit_2(self, tmp_path, capsys):
        code = cli.main(
            ["analyze", "--db", str(tmp_path / "nope.db")]
        )
        assert code == 2
        assert "不存在" in capsys.readouterr().err

    def test_empty_dataset_exit_2(self, seeded_db, tmp_path, capsys):
        code = cli.main(
            [
                "analyze",
                "--db",
                str(seeded_db),
                "--keyword",
                "不存在的关键词",
                "--output-dir",
                str(tmp_path / "r"),
            ]
        )
        assert code == 2
        assert "数据集为空" in capsys.readouterr().err

    def test_help_registered(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            cli.main(["--help"])
        assert exc_info.value.code == 0
        assert "analyze" in capsys.readouterr().out
