"""analyze --json payload 键集契约测试（#601 R84）。

payload 是对外接口（analyze --json / pipeline 透出 / db --diff
消费方）——键集**精确断言**：加键必须改这里的预期集（强制过目
+ 同步 USER-GUIDE），删键/改名直接挂（防静默破坏下游）。
"""

from __future__ import annotations

from src.analyze.report_data import build_analysis_payload


def _dataset():
    from src.analyze.dataset import AnalysisDataset

    return AnalysisDataset(
        records=[
            {
                "bid_id": "K-1",
                "project_name": "某市智慧城市一期",
                "region": "江苏",
                "budget": 100.0,
                "publish_date": "2026-03-01",
                "deadline": "2026-04-01",
                "purchaser": "某局",
                "winner": "某公司",
                "category": "服务",
            }
        ]
    )


EXPECTED_KEYS = {
    "keyword",
    "days",
    "generated_at",
    "record_count",
    "complete_rate",
    "budget",
    "region",
    "trend",
    "date_range",
    "keywords",
    "bigrams",
    "density",
    "field_quality",
    "buyer_profiles",
    "supplier_profiles",
    "budget_outliers",
    "keyword_cooccurrence",
    "province_distribution",
    "rolling_comparison",
    "purchaser_supplier_pairs",
    "budget_region_crosstab",
    "keyword_trends",
    "concentration_trend",
    # 批 L 增量（R80/R82）：十六/十七节的数据面
    "duplicates",
    "semantic_health",
    # 批 N 增量（R95-R98）：十八至二十一节的数据面
    "response_windows",
    "agency_profiles",
    "category_distribution",
    "platform_distribution",
}


class TestPayloadSchema:
    def test_key_set_exact(self):
        payload = build_analysis_payload(_dataset())
        got = set(payload.keys())
        missing = EXPECTED_KEYS - got
        extra = got - EXPECTED_KEYS
        assert not missing, f"缺键（下游契约破坏）: {sorted(missing)}"
        assert not extra, (
            f"多键（新增面未入契约/未同步 USER-GUIDE）: {sorted(extra)}"
            "——若为有意新增，请更新本测试 EXPECTED_KEYS 并同步文档节序"
        )

    def test_duplices_shape(self):
        dup = build_analysis_payload(_dataset())["duplicates"]
        assert set(dup) == {
            "total", "clusters", "records_in_clusters",
            "duplicate_rate", "budget_exhausted",
        }

    def test_semantic_health_shape(self):
        sem = build_analysis_payload(_dataset())["semantic_health"]
        assert set(sem) == {"records", "issues", "health_score", "clean"}
        assert 0 <= sem["health_score"] <= 100

    def test_stage_duration_in_ledger(self):
        """R83 耗时面：done 运行 stages 每项含 duration_seconds 键。"""
        from src.pipeline import ResearchPipeline
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / "ann"
            src.mkdir()
            (src / "a.json").write_text(
                '[{"bid_id": "L-1", "project_name": "x", "budget": 1.0}]',
                encoding="utf-8",
            )
            pipeline = ResearchPipeline(
                Path(td) / "l.db", output_dir=Path(td) / "out"
            )
            result = pipeline.run(src)
            assert result.run_id is not None
            from src.storage.database import BidDatabase

            db = BidDatabase(Path(td) / "l.db")
            try:
                run = db.pipeline_runs_list(limit=1)[0]
                for stage in run["stages"]:
                    assert "duration_seconds" in stage
            finally:
                db.close()
