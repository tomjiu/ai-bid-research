"""src/pipeline 编排器测试（#601 批次 D·R17/R18）。"""

from __future__ import annotations

import json

import pytest

from src.pipeline.runner import (
    Pipeline,
    PipelineRun,
    run_analyze_stage,
    run_report_stage,
)
from src.pipeline.stages import StageResult
from src.storage.database import BidDatabase

from tests.test_extract_engine import SAMPLE_ANNOUNCEMENT


@pytest.fixture()
def db(tmp_path):
    database = BidDatabase(tmp_path / "t.db")
    yield database
    database.close()


@pytest.fixture()
def ann_dir(tmp_path):
    d = tmp_path / "ann"
    d.mkdir()
    (d / "a.json").write_text(
        json.dumps(
            [
                {
                    "bid_id": "P-1",
                    "project_name": "管道验证项目一",
                    "budget": 100,
                    "publish_date": "2026-01-10",
                    "region": "北京市",
                    "winner": "甲公司",
                },
                {
                    "bid_id": "P-2",
                    "project_name": "管道验证项目二",
                    "budget": 300,
                    "publish_date": "2026-02-10",
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
    (d / "n1.txt").write_text(SAMPLE_ANNOUNCEMENT, encoding="utf-8")
    return d


# ----------------------------------------------------------------------
# analyze / report 阶段
# ----------------------------------------------------------------------


class TestAnalyzeStage:
    def test_analyze_reads_dataset(self, db, ann_dir):
        db.import_bids(
            json.loads((ann_dir / "a.json").read_text(encoding="utf-8"))
        )
        result = run_analyze_stage(db)
        assert result.ok
        assert result.summary["total"] == 2
        assert result.summary["awarded"] == 1
        assert "stats" in result.summary
        assert result.summary["stats"]["overview"]["total"] == 2

    def test_analyze_empty_fails_honestly(self, db):
        result = run_analyze_stage(db)
        assert result.ok is False
        assert "数据集为空" in result.error

    def test_analyze_filters(self, db, ann_dir):
        db.import_bids(
            json.loads((ann_dir / "a.json").read_text(encoding="utf-8"))
        )
        result = run_analyze_stage(db, keyword="项目一")
        assert result.summary["total"] == 1


class TestReportStage:
    def test_report_saves_markdown(self, tmp_path):
        stats = {
            "generated_at": "2026-01-01 00:00:00",
            "overview": {"total": 1, "awarded": 0, "budget_total_wan": 100},
            "budget": {"count": 1},
            "regions": {"regions": []},
            "trend": {"months": []},
            "keywords": {"keywords": []},
            "competition": {"awarded": 0},
        }
        result = run_report_stage(stats, tmp_path / "reports")
        assert result.ok
        assert result.summary["markdown"].endswith(".md")
        content = open(result.summary["markdown"], encoding="utf-8").read()
        assert "# 招标数据分析报告" in content


# ----------------------------------------------------------------------
# Pipeline 编排
# ----------------------------------------------------------------------


class TestPipeline:
    def test_full_chain(self, db, ann_dir, raw_dir, tmp_path):
        """端到端：双源输入 → 四阶段 → 报告 + 留档。"""
        pipeline = Pipeline(db, output_dir=tmp_path / "reports")
        run = pipeline.run(announcements=ann_dir, raw_texts=raw_dir)
        assert run.all_ok, [s.error for s in run.stages]
        # 四阶段齐
        names = [s.name for s in run.stages]
        assert names == ["collect", "extract", "analyze", "report"]
        # collect：2 新增
        assert run.stage("collect").summary["new"] == 2
        # extract：1 成功
        assert run.stage("extract").summary["extracted"] == 1
        # analyze：3 条（2 collect + 1 extract）
        assert run.stage("analyze").summary["total"] == 3
        # report：落盘
        report_path = run.stage("report").summary["markdown"]
        content = open(report_path, encoding="utf-8").read()
        assert "## 五、竞争密度" in content
        # 留档
        history = pipeline.run_history()
        assert len(history) == 1
        assert history[0]["ok"] == 1
        assert history[0]["report_path"] == report_path

    def test_incremental_rerun(self, db, ann_dir, raw_dir, tmp_path):
        """增量：同源重跑——collect 零新增、extract 零处理、报告重生成。"""
        pipeline = Pipeline(db, output_dir=tmp_path / "reports")
        first = pipeline.run(announcements=ann_dir, raw_texts=raw_dir)
        assert first.stage("collect").summary["new"] == 2

        second = pipeline.run(announcements=ann_dir, raw_texts=raw_dir)
        assert second.all_ok
        assert second.stage("collect").summary["new"] == 0
        assert second.stage("collect").summary["update"] == 2  # bid_id 命中
        assert second.stage("extract").summary["processed"] == 0
        assert second.stage("analyze").summary["total"] == 3  # 库内不变
        # 两次运行留档
        assert len(pipeline.run_history()) == 2

    def test_dry_run_no_side_effects(self, db, ann_dir, raw_dir, tmp_path):
        pipeline = Pipeline(db, output_dir=tmp_path / "reports")
        run = pipeline.run(
            announcements=ann_dir, raw_texts=raw_dir, dry_run=True
        )
        assert run.dry_run
        assert run.stage("collect").summary["new"] == 2  # 会做什么——预演
        assert run.stage("extract").summary["new"] == 1
        assert run.stage("analyze").ok is False  # 空库 + 只读 → 诚实失败
        # 零副作用：库空、无报告、无留档
        assert db.count_bids() == 0
        assert db.raw_stats()["total"] == 0
        assert list((tmp_path / "reports").glob("pipeline_*.md")) == []
        assert pipeline.run_history() == []

    def test_stage_failure_does_not_block_rest(self, db, tmp_path):
        """collect 源不可读：该阶段失败，但 analyze/report 照跑（库内有数据时）。"""
        db.save_bid(
            {
                "bid_id": "S-1",
                "project_name": "既有数据",
                "budget": 50,
                "publish_date": "2026-01-01",
            }
        )
        pipeline = Pipeline(db, output_dir=tmp_path / "reports")
        run = pipeline.run(announcements=tmp_path / "missing-dir")
        assert run.all_ok is False
        assert run.stage("collect").ok is False
        assert run.stage("analyze").ok is True
        assert run.stage("report").ok is True

    def test_no_sources_only_analyze_report(self, db, tmp_path):
        """无源输入：只跑 analyze/report（库内数据存在时）。"""
        db.save_bid(
            {
                "bid_id": "S-1",
                "project_name": "既有数据",
                "budget": 50,
                "publish_date": "2026-01-01",
            }
        )
        pipeline = Pipeline(db, output_dir=tmp_path / "reports")
        run = pipeline.run()
        names = [s.name for s in run.stages]
        assert names == ["analyze", "report"]
        assert run.all_ok

    def test_run_summary_format(self, db, ann_dir, tmp_path):
        pipeline = Pipeline(db, output_dir=tmp_path / "reports")
        run = pipeline.run(announcements=ann_dir)
        summary = run.format_summary()
        assert "✓ collect" in summary
        assert "✓ analyze" in summary
        assert "总耗时" in summary

    def test_pipeline_runs_table_idempotent(self, db, tmp_path):
        """pipeline_runs 表创建幂等（多次 Pipeline 构造不炸）。"""
        Pipeline(db, output_dir=tmp_path / "r1")
        Pipeline(db, output_dir=tmp_path / "r2")


# ----------------------------------------------------------------------
# PipelineRun 模型
# ----------------------------------------------------------------------


class TestPipelineRunModel:
    def test_all_ok_and_stage_lookup(self):
        run = PipelineRun(
            started_at="2026-01-01",
            stages=[
                StageResult("collect", True, summary={}),
                StageResult("extract", False, error="x"),
            ],
        )
        assert run.all_ok is False
        assert run.stage("extract").error == "x"
        assert run.stage("missing") is None
        assert run.duration_ms == 0

    def test_to_dict_shape(self):
        run = PipelineRun(started_at="2026-01-01", stages=[])
        data = run.to_dict()
        assert data["started_at"] == "2026-01-01"
        assert data["all_ok"] is True
        assert data["stages"] == []
