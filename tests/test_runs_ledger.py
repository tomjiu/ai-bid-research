"""db --runs 运行台账 + 阶段耗时测试（#601 R83）。

契约：done 运行的 stages 含 duration_seconds（≥0 数值）；
db --runs 渲染状态/参数/阶段链；failed 运行如实显示未收口；
空台账友好提示。
"""

from __future__ import annotations

import json

import pytest

from main import main
from src.storage.database import BidDatabase


def _run_pipeline(db_path, source, keyword=None):
    from src.pipeline import ResearchPipeline

    pipeline = ResearchPipeline(db_path, output_dir=db_path.parent / "out")
    return pipeline.run(source, keyword=keyword)


@pytest.fixture()
def src_dir(tmp_path):
    import json as j

    src = tmp_path / "ann"
    src.mkdir()
    (src / "a.json").write_text(
        j.dumps(
            [{"bid_id": "R-1", "project_name": "智慧城市台账",
              "budget": 10.0, "publish_date": "2026-10-01"}],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return src


class TestStageTiming:
    def test_done_run_stages_have_duration(self, tmp_path, src_dir):
        db_path = tmp_path / "t.db"
        result = _run_pipeline(db_path, src_dir)
        assert result.run_id is not None
        for stage in result.stages:
            if stage.status == "skipped" and stage.name == "extract":
                # skipped 在构造处未计时——保持 None（快得无需计）
                continue
            assert stage.duration_seconds is not None
            assert stage.duration_seconds >= 0.0

        db = BidDatabase(db_path)
        try:
            runs = db.pipeline_runs_list(limit=5)
            assert len(runs) == 1
            stages = runs[0]["stages"]
            # 台账序列化含耗时（analyze/report 两个必跑阶段）
            analyze = next(s for s in stages if s["name"] == "analyze")
            assert analyze["duration_seconds"] is not None
            report = next(s for s in stages if s["name"] == "report")
            assert report["duration_seconds"] is not None
        finally:
            db.close()

    def test_stages_json_serializable(self, tmp_path, src_dir):
        db_path = tmp_path / "s.db"
        _run_pipeline(db_path, src_dir)
        db = BidDatabase(db_path)
        try:
            run = db.pipeline_runs_list(limit=1)[0]
            json.dumps(run, ensure_ascii=False)  # 全量可序列化
        finally:
            db.close()


class TestDbRunsCommand:
    def test_empty_ledger_friendly(self, tmp_path, capsys):
        db = BidDatabase(tmp_path / "e.db")
        db.close()
        code = main(["db", "--db", str(tmp_path / "e.db"), "--runs"])
        assert code == 0
        assert "无管道运行记录" in capsys.readouterr().out

    def test_renders_run_chain(self, tmp_path, src_dir, capsys):
        db_path = tmp_path / "r.db"
        _run_pipeline(db_path, src_dir, keyword="智慧城市")
        code = main(["db", "--db", str(db_path), "--runs", "5"])
        assert code == 0
        out = capsys.readouterr().out
        assert "[done]" in out
        assert "智慧城市" in out
        assert "阶段：" in out
        assert "analyze@ok" in out
        assert "report@ok" in out
        # 耗时出现在阶段链里
        assert "(" in out and "s)" in out

    def test_failed_run_shows_unclosed(self, tmp_path, src_dir, capsys):
        from src.pipeline import ResearchPipeline

        db_path = tmp_path / "f.db"

        class _Boom:
            def extract_batch(self, records, raw_texts=None):
                raise RuntimeError("崩溃模拟")

        pipeline = ResearchPipeline(
            db_path, extractor=_Boom(), output_dir=tmp_path / "o"
        )
        with pytest.raises(RuntimeError):
            pipeline.run(src_dir)

        code = main(["db", "--db", str(db_path), "--runs"])
        assert code == 0
        out = capsys.readouterr().out
        assert "[failed]" in out
        assert "未收口" in out or "崩溃于收口前" in out

    def test_ghost_db_is_data_error(self, tmp_path, capsys):
        code = main(["db", "--db", str(tmp_path / "ghost.db"), "--runs"])
        assert code == 2
        assert "数据库不存在" in capsys.readouterr().err
