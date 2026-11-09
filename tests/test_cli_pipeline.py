"""pipeline 子命令 CLI 测试 + 端到端离线全链（#601 批次 D·R19/R20）。"""

from __future__ import annotations

import json

import pytest

import main as cli
from src.storage.database import BidDatabase

from tests.test_extract_engine import SAMPLE_ANNOUNCEMENT


@pytest.fixture()
def ann_dir(tmp_path):
    d = tmp_path / "ann"
    d.mkdir()
    (d / "a.json").write_text(
        json.dumps(
            [
                {
                    "bid_id": "E2E-1",
                    "project_name": "端到端验证智慧城市项目",
                    "budget": 1200,
                    "publish_date": "2026-01-10",
                    "region": "浙江省杭州市",
                    "winner": "甲公司",
                },
                {
                    "bid_id": "E2E-2",
                    "project_name": "端到端验证数据中心项目",
                    "budget": 800,
                    "publish_date": "2026-02-15",
                    "region": "北京市",
                },
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return d


@pytest.fixture()
def raw_dir(tmp_path):
    d = tmp_path / "raw"
    d.mkdir()
    (d / "notice.txt").write_text(SAMPLE_ANNOUNCEMENT, encoding="utf-8")
    return d


class TestPipelineCLI:
    def test_e2e_offline_full_chain(self, ann_dir, raw_dir, tmp_path, capsys):
        """#601 验收口径（批次 D）：双源 → 离线产出含统计数字的 Markdown 报告。"""
        db_path = tmp_path / "bids.db"
        out_dir = tmp_path / "reports"
        code = cli.main(
            [
                "pipeline",
                "--announcements",
                str(ann_dir),
                "--raw-texts",
                str(raw_dir),
                "--db",
                str(db_path),
                "--output-dir",
                str(out_dir),
                "--html",
            ]
        )
        assert code == 0
        out = capsys.readouterr().out
        assert "全部成功" in out
        assert "collect：读取 1 文件，新增 2" in out
        assert "extract：读取 1 文件，新入 1，处理 1，成功 1" in out
        assert "analyze：数据集 3 条（已定标 1）" in out
        assert "report：" in out

        # 解包断言报告内容（不信任 CLI 返回值——读文件）
        reports = list(out_dir.glob("pipeline_*.md"))
        assert len(reports) == 1
        content = reports[0].read_text(encoding="utf-8")
        assert "# 招标数据分析报告" in content
        assert "共 3 条项目" in content
        assert "3,200" in content  # 预算总额（1200+800 collect + 1200 extract）
        assert "HLJ-GC-2026-001" not in content  # 报告是统计面不是清单
        assert "## 五、竞争密度" in content
        assert "甲公司" in content
        # HTML 导出
        assert list(out_dir.glob("pipeline_*.html"))

        # 数据库状态：bids 3 条（2 collect + 1 extract），raw 1 extracted
        with BidDatabase(db_path) as db:
            assert db.count_bids() == 3
            assert db.get_bid("HLJ-GC-2026-001")["budget"] == 1200.0
            assert db.raw_stats() == {"total": 1, "pending": 0, "extracted": 1}

    def test_incremental_rerun_cli(self, ann_dir, raw_dir, tmp_path, capsys):
        db_path = tmp_path / "bids.db"
        out_dir = tmp_path / "reports"
        argv = [
            "pipeline",
            "--announcements",
            str(ann_dir),
            "--raw-texts",
            str(raw_dir),
            "--db",
            str(db_path),
            "--output-dir",
            str(out_dir),
        ]
        assert cli.main(argv) == 0
        capsys.readouterr()
        # 第二跑：增量——collect 零新增、extract 零处理
        assert cli.main(argv) == 0
        out = capsys.readouterr().out
        assert "collect：读取 1 文件，新增 0，更新 2" in out
        assert "extract：读取 1 文件，新入 0，处理 0" in out
        assert "analyze：数据集 3 条" in out
        # 报告重生成（新一轮时间戳文件）
        assert len(list(out_dir.glob("pipeline_*.md"))) == 2

    def test_dry_run_cli(self, ann_dir, raw_dir, tmp_path, capsys):
        db_path = tmp_path / "bids.db"
        out_dir = tmp_path / "reports"
        code = cli.main(
            [
                "pipeline",
                "--announcements",
                str(ann_dir),
                "--raw-texts",
                str(raw_dir),
                "--db",
                str(db_path),
                "--output-dir",
                str(out_dir),
                "--dry-run",
            ]
        )
        # 演练：collect/extract 预演 ok，analyze 空库失败 → 退出 1
        assert code == 1
        out = capsys.readouterr().out
        assert "演练" in out
        assert "存在失败阶段" in out
        assert "collect：读取 1 文件，新增 2" in out  # 预演显示会做什么
        # 零副作用
        with BidDatabase(db_path) as db:
            assert db.count_bids() == 0
        assert list(out_dir.glob("pipeline_*.md")) == []

    def test_stage_failure_exit_1(self, tmp_path, capsys):
        """collect 源不可读：阶段失败 → 退出 1（但 analyze 照跑）。"""
        db_path = tmp_path / "bids.db"
        with BidDatabase(db_path) as db:
            db.save_bid(
                {
                    "bid_id": "S-1",
                    "project_name": "既有数据",
                    "budget": 50,
                    "publish_date": "2026-01-01",
                }
            )
        code = cli.main(
            [
                "pipeline",
                "--announcements",
                str(tmp_path / "missing"),
                "--db",
                str(db_path),
                "--output-dir",
                str(tmp_path / "r"),
            ]
        )
        assert code == 1
        out = capsys.readouterr().out
        assert "✗ collect" in out
        assert "✓ analyze" in out

    def test_no_db_no_source_exit_2(self, tmp_path, capsys):
        code = cli.main(
            [
                "pipeline",
                "--db",
                str(tmp_path / "nope.db"),
                "--output-dir",
                str(tmp_path / "r"),
            ]
        )
        assert code == 2
        assert "未指定任何源" in capsys.readouterr().err

    def test_filters_passed_to_analyze(self, ann_dir, tmp_path, capsys):
        db_path = tmp_path / "bids.db"
        code = cli.main(
            [
                "pipeline",
                "--announcements",
                str(ann_dir),
                "--db",
                str(db_path),
                "--keyword",
                "智慧城市",
                "--output-dir",
                str(tmp_path / "r"),
            ]
        )
        assert code == 0
        out = capsys.readouterr().out
        assert "analyze：数据集 1 条" in out

    def test_help_registered(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            cli.main(["--help"])
        assert exc_info.value.code == 0
        assert "pipeline" in capsys.readouterr().out
