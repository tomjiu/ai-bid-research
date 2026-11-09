"""管道台账与增量水位测试（#601 批次 D 第 17 轮）。"""

import json
import os
import time

import pytest

from src.pipeline import ResearchPipeline
from src.storage.database import BidDatabase


@pytest.fixture()
def source(tmp_path):
    """公告源。"""
    src = tmp_path / "announcements"
    src.mkdir()
    (src / "a.json").write_text(
        json.dumps(
            [{"bid_id": "IN-001", "project_name": "水位一期项目"}],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return src


def _touch_later(path, seconds=5):
    """把文件 mtime 推到未来（保证晚于水位）。"""
    future = time.time() + seconds
    os.utime(path, (future, future))


class TestRunLedger:
    """运行台账。"""

    def test_run_recorded(self, source, tmp_path):
        """每次运行自动登记：stages/报告路径/状态可查。"""
        pipeline = ResearchPipeline(
            tmp_path / "b.db", output_dir=tmp_path / "r"
        )
        result = pipeline.run(source, keyword="水位")
        with BidDatabase(tmp_path / "b.db") as db:
            runs = db.pipeline_runs_list()
        assert len(runs) == 1
        assert runs[0]["status"] == "done"
        assert runs[0]["keyword"] == "水位"
        assert runs[0]["report_path"].endswith(".md")
        stages = runs[0]["stages"]
        assert [s["name"] for s in stages] == [
            "collect", "extract", "analyze", "report",
        ]
        assert result.run_id == runs[0]["id"]

    def test_failed_run_recorded(self, tmp_path):
        """起步硬错（源不存在）→ 台账记 failed 后异常上抛。"""
        from src.collect.sources import SourceError

        pipeline = ResearchPipeline(
            tmp_path / "b.db", output_dir=tmp_path / "r"
        )
        with pytest.raises(SourceError):
            pipeline.run(tmp_path / "nope")
        with BidDatabase(tmp_path / "b.db") as db:
            runs = db.pipeline_runs_list()
        assert runs[0]["status"] == "failed"
        assert runs[0]["finished_at"] is not None

    def test_multiple_runs_listed_newest_first(self, source, tmp_path):
        """多次运行按 id 降序可查。"""
        pipeline = ResearchPipeline(
            tmp_path / "b.db", output_dir=tmp_path / "r"
        )
        pipeline.run(source)
        pipeline.run()  # 无 source 纯分析
        with BidDatabase(tmp_path / "b.db") as db:
            runs = db.pipeline_runs_list()
            last_done = db.pipeline_runs_last()
        assert len(runs) == 2
        assert runs[0]["id"] > runs[1]["id"]
        assert last_done["id"] == runs[0]["id"]


class TestIncrementalWatermark:
    """增量水位。"""

    def test_first_run_full_second_incremental_skips_old(self, source,
                                                          tmp_path):
        """首次无水位=全量；之后 incremental 只读新文件。"""
        pipeline = ResearchPipeline(
            tmp_path / "b.db", output_dir=tmp_path / "r"
        )
        first = pipeline.run(source)
        assert first.stage("collect").detail["new"] == 1

        # 无新文件：incremental → collect 零文件零记录
        second = pipeline.run(source, incremental=True)
        collect = second.stage("collect")
        assert collect.detail["files_read"] == 0
        assert collect.detail["loaded"] == 0
        assert collect.detail["new"] == 0

    def test_incremental_picks_new_file_only(self, source, tmp_path):
        """水位后新增文件被读、旧文件跳过。"""
        pipeline = ResearchPipeline(
            tmp_path / "b.db", output_dir=tmp_path / "r"
        )
        pipeline.run(source)  # 建立水位

        # 新文件（mtime 推到水位后）
        new_file = source / "b.json"
        new_file.write_text(
            json.dumps(
                [{"bid_id": "IN-002", "project_name": "水位新项目"}],
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        _touch_later(new_file, seconds=10)

        result = pipeline.run(source, incremental=True)
        collect = result.stage("collect")
        assert collect.detail["files_read"] == 1  # 只读了 b.json
        assert collect.detail["new"] == 1
        with BidDatabase(tmp_path / "b.db") as db:
            assert db.get_bid("IN-002") is not None
            assert db.get_bid("IN-001") is not None

    def test_corrupted_watermark_degrades_to_full(self, source, tmp_path):
        """水位值损坏 → 退化全量（不炸管道）。"""
        pipeline = ResearchPipeline(
            tmp_path / "b.db", output_dir=tmp_path / "r"
        )
        pipeline.run(source)
        # 手工损坏最近一次 done 运行的水位值
        with BidDatabase(tmp_path / "b.db") as db:
            db._conn.execute(
                "UPDATE pipeline_runs SET watermark = NULL"
                " WHERE status = 'done'"
            )
            db._conn.commit()
        result = pipeline.run(source, incremental=True)
        # 水位缺失 → 全量重读（幂等 upsert 保护，new=0 update=1）
        collect = result.stage("collect")
        assert collect.detail["files_read"] == 1
        assert collect.detail["updated"] == 1

    def test_non_incremental_rereads_all(self, source, tmp_path):
        """非增量模式：无视水位全量重读（幂等 upsert 保护）。"""
        pipeline = ResearchPipeline(
            tmp_path / "b.db", output_dir=tmp_path / "r"
        )
        pipeline.run(source)
        result = pipeline.run(source)  # 非 incremental
        collect = result.stage("collect")
        assert collect.detail["files_read"] == 1
        assert collect.detail["new"] == 0  # 已入库 → update 分账
        assert collect.detail["updated"] == 1
