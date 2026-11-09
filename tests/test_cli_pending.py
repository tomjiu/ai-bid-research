"""db 子命令 pending 面 CLI 测试（#601 批次 E 第 24 轮）。"""

import pytest

import main as cli
from src.extract import REASON_LLM_ERROR, REASON_REJECTED
from src.extract.pending import park_raw_failure
from src.collect import AnnouncementRecord
from src.pipeline import ResearchPipeline
from src.storage.database import BidDatabase


@pytest.fixture()
def db_with_pending(tmp_path):
    """带 pending 面数据的库。"""
    db_path = tmp_path / "b.db"
    with BidDatabase(db_path) as db:
        record = AnnouncementRecord.from_raw(
            {"bid_id": "PV-001", "project_name": "抽取失败项目-QA",
             "content": "原文"}
        )
        from src.extract import park_record_failure

        park_record_failure(
            db, record, REASON_LLM_ERROR, raw_text="原文", error="LLM 超时"
        )
        park_raw_failure(
            db, "没有编号的公告原文-QA", REASON_REJECTED, error="缺招标编号"
        )
    return db_path


class TestDBPendingCLI:
    """db --pending / --pending-stats。"""

    def test_pending_list(self, db_with_pending, capsys):
        """列出待处理：原因/编号/指纹/原文有无/错误。"""
        code = cli.main(
            ["db", "--db", str(db_with_pending), "--pending"]
        )
        out = capsys.readouterr().out
        assert code == 0
        assert "pending 面待处理 2 条" in out
        assert "[llm_error] PV-001" in out
        assert "[rejected] （缺编号）" in out
        assert "指纹" in out

    def test_pending_stats(self, db_with_pending, capsys):
        """统计：状态分组 + 原因分组。"""
        code = cli.main(
            ["db", "--db", str(db_with_pending), "--pending-stats"]
        )
        out = capsys.readouterr().out
        assert code == 0
        assert "共 2 条（待处理 2 / 已解决 0 / 跳过 0）" in out
        assert "· llm_error: 1" in out
        assert "· rejected: 1" in out

    def test_stats_shows_last_pipeline_run(self, tmp_path, capsys):
        """默认统计面带出最近管道运行（台账可见性）。"""
        db_path = tmp_path / "b.db"
        pipeline = ResearchPipeline(db_path, output_dir=tmp_path / "r")
        pipeline.run()  # 空库分析（登记 run #1）
        code = cli.main(["db", "--db", str(db_path), "--stats"])
        out = capsys.readouterr().out
        assert code == 0
        assert "最近管道运行 #1（done" in out

    def test_stats_default_without_pending_flags(self, db_with_pending,
                                                 capsys):
        """不带 pending 参数时默认统计仍工作（回归面）。"""
        code = cli.main(["db", "--db", str(db_with_pending)])
        out = capsys.readouterr().out
        assert code == 0
        assert "数据库统计：共 0 条项目" in out

    def test_empty_pending(self, tmp_path, capsys):
        """空 pending 面：零条不炸。"""
        db_path = tmp_path / "empty.db"
        with BidDatabase(db_path):
            pass
        code = cli.main(["db", "--db", str(db_path), "--pending"])
        out = capsys.readouterr().out
        assert code == 0
        assert "pending 面待处理 0 条" in out
