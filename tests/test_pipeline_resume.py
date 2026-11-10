"""pipeline 断点续跑测试（#601 R58）。

两种「未完成抽取」的残留形态（都必须能被 --resume 收编）：

1. **崩溃**：extract 阶段整体异常（asyncio/基础设施级）——
   台账记 failed，bids 行停留 ``raw``，无 pending；
2. **降级**：单条 LLM 失败被 park——运行标记 done，bids 行
   停留 ``raw``，pending 挂账。

resume 语义：崩溃形态自动从台账恢复 source/keyword；降级形态
需显式 --source（done 运行不回溯参数）。补抽成功统一标记
``extracted`` 并自动清 pending 账。
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest

from src.extract import AnnouncementExtractor
from src.llm.client import LLMClient
from src.pipeline import ResearchPipeline
from src.storage.database import BidDatabase


def _extractor(fail: bool = False, llm_output=None):
    client = LLMClient(api_key="k")
    if fail:
        client.chat_json = AsyncMock(side_effect=RuntimeError("网络断"))
    else:
        client.chat_json = AsyncMock(
            return_value=llm_output or {"bid_id": "placeholder"}
        )
    return AnnouncementExtractor(client)


def _crash_extractor():
    """extract_batch 层真崩溃（绕过单条异常隔离——模拟进程级故障）。"""
    ext = _extractor()

    async def crashing(records, raw_texts=None):
        raise RuntimeError("进程崩溃模拟（基础设施级）")

    ext.extract_batch = crashing
    return ext


@pytest.fixture()
def source(tmp_path):
    src = tmp_path / "ann"
    src.mkdir()
    (src / "a.json").write_text(
        json.dumps(
            [
                {
                    "bid_id": "RS-001",
                    "project_name": "智慧城市续跑验证",
                    "content": "预算 300万元，发布日期 2026年11月1日",
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return src


class TestExtractStatusLifecycle:
    def test_migration_v3_column_present(self, tmp_path):
        db = BidDatabase(tmp_path / "m.db")
        try:
            cols = {
                r[1]
                for r in db._conn.execute("PRAGMA table_info(bids)").fetchall()
            }
            assert "extract_status" in cols
            assert db.schema_info()["user_version"] == 3
        finally:
            db.close()

    def test_crash_run_marks_failed_and_leaves_raw(self, tmp_path, source):
        db_path = tmp_path / "c.db"
        pipeline = ResearchPipeline(
            db_path, extractor=_crash_extractor(),
            output_dir=tmp_path / "out",
        )
        with pytest.raises(RuntimeError, match="进程崩溃模拟"):
            pipeline.run(source, keyword="智慧城市")
        db = BidDatabase(db_path)
        try:
            # bids 行停留 raw（collect 已入库、extract 未消费）
            assert db.extract_status_of("RS-001") == "raw"
            # 台账 failed
            failed = db.pipeline_runs_last(status="failed")
            assert failed is not None
            assert failed["keyword"] == "智慧城市"
            # 崩溃在 park 之前——无 pending 挂账
            assert db.list_pending(limit=10) == []
        finally:
            db.close()

    def test_degraded_run_leaves_raw_and_parks(self, tmp_path, source):
        """降级（单条失败 park）：done 运行 + raw 残留 + pending 挂账。"""
        db_path = tmp_path / "d.db"
        pipeline = ResearchPipeline(
            db_path, extractor=_extractor(fail=True),
            output_dir=tmp_path / "out",
        )
        result = pipeline.run(source)  # 不炸——降级契约
        assert result.run_id is not None
        db = BidDatabase(db_path)
        try:
            assert db.extract_status_of("RS-001") == "raw"
            parked = db.list_pending(limit=10)
            assert len(parked) == 1
            assert parked[0]["status"] == "pending"
            # 运行标记 done（失败被 park 吸收）
            assert db.pipeline_runs_last(status="done") is not None
        finally:
            db.close()


class TestResume:
    def test_resume_crash_recovers_params_and_leftovers(self, tmp_path, source):
        db_path = tmp_path / "r.db"
        pipeline = ResearchPipeline(
            db_path, extractor=_crash_extractor(),
            output_dir=tmp_path / "out",
        )
        with pytest.raises(RuntimeError):
            pipeline.run(source, keyword="智慧城市")

        # resume：无显式 source → 从失败台账恢复 + 补抽
        pipeline2 = ResearchPipeline(
            db_path, extractor=_extractor(), output_dir=tmp_path / "out2",
        )
        result = pipeline2.run(resume=True)
        collect = result.stage("collect")
        assert collect.detail["recovered_raw"] == 1
        db = BidDatabase(db_path)
        try:
            last = db.pipeline_runs_last(status="done")
            assert last["keyword"] == "智慧城市"  # 参数从失败运行恢复
        finally:
            db.close()

    def test_resume_parked_leftover_with_explicit_source(self, tmp_path, source):
        """降级残留（done 运行）：显式 source + resume → 补抽 + pending 清账。"""
        db_path = tmp_path / "p.db"
        pipeline = ResearchPipeline(
            db_path, extractor=_extractor(fail=True),
            output_dir=tmp_path / "out",
        )
        pipeline.run(source)
        db = BidDatabase(db_path)
        try:
            assert len(db.list_pending(limit=10)) == 1
        finally:
            db.close()

        pipeline2 = ResearchPipeline(
            db_path, extractor=_extractor(), output_dir=tmp_path / "out2",
        )
        result = pipeline2.run(source, resume=True)
        assert result.stage("collect").detail["recovered_raw"] == 1
        db = BidDatabase(db_path)
        try:
            # 补抽成功：状态翻转 + pending 自动清账（store 单点闭环）
            assert db.extract_status_of("RS-001") == "extracted"
            assert db.list_pending(limit=10) == []
            assert db.list_by_extract_status("raw") == []
        finally:
            db.close()

    def test_resume_without_failed_run_is_honest_noop(self, tmp_path):
        pipeline = ResearchPipeline(
            tmp_path / "n.db", output_dir=tmp_path / "out",
        )
        result = pipeline.run(resume=True)
        # 无失败运行可恢复 → source None → collect 跳过（明示原因）
        collect = result.stage("collect")
        assert collect.status == "skipped"
        assert "未指定" in collect.detail["reason"]

    def test_resume_explicit_source_wins_over_ledger(self, tmp_path, source):
        db_path = tmp_path / "e.db"
        pipeline = ResearchPipeline(
            db_path, extractor=_crash_extractor(),
            output_dir=tmp_path / "o",
        )
        with pytest.raises(RuntimeError):
            pipeline.run(source, keyword="旧词")
        # resume 显式给 source → 用显式值；keyword 显式传入也优先
        pipeline2 = ResearchPipeline(
            db_path, extractor=_extractor(), output_dir=tmp_path / "o2",
        )
        result = pipeline2.run(source, keyword="新词", resume=True)
        assert result.stage("collect").detail["recovered_raw"] == 1
        db = BidDatabase(db_path)
        try:
            assert db.pipeline_runs_last(status="done")["keyword"] == "新词"
        finally:
            db.close()


class TestPendingResolution:
    def test_resolve_pending_by_bid_direct(self, tmp_path):
        from src.extract.pending import park_raw_failure

        db = BidDatabase(tmp_path / "pd.db")
        try:
            park_raw_failure(
                db,
                raw_text="某公告原文",
                reason="llm_error",
                error="超时",
                bid_id="PD-1",
            )
            assert db.list_pending(limit=5)[0]["status"] == "pending"
            assert db.resolve_pending_by_bid("PD-1") == 1
            assert db.list_pending(limit=5) == []
            assert db.resolve_pending_by_bid("PD-1") == 0  # 幂等
        finally:
            db.close()

    def test_extract_status_helpers(self, tmp_path):
        db = BidDatabase(tmp_path / "st.db")
        try:
            db.save_bid(
                {"bid_id": "S-1", "project_name": "状态面", "budget": 1.0}
            )
            # 外部导入/历史行：未标记 → None（不参与续跑扫描）
            assert db.extract_status_of("S-1") is None
            db.set_extract_status("S-1", "raw")
            assert db.extract_status_of("S-1") == "raw"
            assert db.list_by_extract_status("raw") == [{"bid_id": "S-1"}]
            db.set_extract_status("S-1", "extracted")
            assert db.list_by_extract_status("raw") == []
            assert db.extract_status_of("不存在") is None
        finally:
            db.close()
