"""src/pipeline 模块单元测试（#601 批次 D 第 16 轮）。

离线端到端：mock LLM → 管道四阶段 → 报告落盘。
"""

import json
from unittest.mock import AsyncMock

import pytest

from src.llm.client import LLMClient
from src.pipeline import (
    STAGE_EMPTY,
    STAGE_OK,
    STAGE_SKIPPED,
    ResearchPipeline,
)
from src.storage.database import BidDatabase


def _mock_extractor(llm_output=None, *, fail=False):
    """构造抽取器（mock chat_json）。"""
    from src.extract import AnnouncementExtractor

    client = LLMClient(api_key="k")
    if fail:
        client.chat_json = AsyncMock(side_effect=RuntimeError("网络断"))
    else:
        client.chat_json = AsyncMock(
            return_value=llm_output or {"bid_id": "placeholder"}
        )
    return AnnouncementExtractor(client)


@pytest.fixture()
def source(tmp_path):
    """公告源（含原文）。"""
    src = tmp_path / "announcements"
    src.mkdir()
    (src / "a.json").write_text(
        json.dumps(
            [
                {
                    "bid_id": "PL-001",
                    "project_name": "智慧城市管道一期",
                    "content": "预算 300万元，发布日期 2026年11月1日",
                },
                {
                    "bid_id": "PL-002",
                    "project_name": "政务云扩容",
                    "budget": "500万元",
                },
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return src


class TestPipelineFullRun:
    """全链端到端。"""

    def test_full_chain_with_llm(self, source, tmp_path):
        """mock LLM 全链：采集 2 新 → 抽取 2 → 分析 → 报告。"""
        extractor = _mock_extractor(
            {
                "bid_id": "PL-001",
                "budget": "300万元",
                "region": "浙江省",
                "publish_date": "2026年11月1日",
            }
        )
        pipeline = ResearchPipeline(
            tmp_path / "b.db", extractor=extractor, output_dir=tmp_path / "r"
        )
        result = pipeline.run(source, keyword="智慧城市")

        stages = {s.name: s for s in result.stages}
        assert stages["collect"].status == STAGE_OK
        assert stages["collect"].detail["new"] == 2
        assert stages["extract"].status == STAGE_OK
        assert stages["extract"].detail["extracted"] == 2
        assert stages["analyze"].status == STAGE_OK
        assert stages["report"].status == STAGE_OK
        assert result.report_path.exists()

        with BidDatabase(tmp_path / "b.db") as db:
            row = db.get_bid("PL-001")
        assert row["budget"] == 300.0  # LLM 补缺生效
        content = result.report_path.read_text(encoding="utf-8")
        assert "「智慧城市」" in content

    def test_offline_pipeline(self, source, tmp_path):
        """无抽取器：extract 阶段 skipped（离线口径如实记录）。"""
        pipeline = ResearchPipeline(
            tmp_path / "b.db", extractor=None, output_dir=tmp_path / "r"
        )
        result = pipeline.run(source)
        stages = {s.name: s for s in result.stages}
        assert stages["collect"].detail["new"] == 2
        assert stages["extract"].status == STAGE_SKIPPED
        assert "离线模式" in stages["extract"].detail["reason"]
        assert result.report_path.exists()

    def test_rerun_only_updates(self, source, tmp_path):
        """重复运行：全部为 update、零 new、extract skipped（省 API）。"""
        extractor = _mock_extractor()
        pipeline = ResearchPipeline(
            tmp_path / "b.db", extractor=extractor, output_dir=tmp_path / "r"
        )
        pipeline.run(source)
        second = pipeline.run(source)
        collect = second.stage("collect")
        extract = second.stage("extract")
        assert collect.detail["new"] == 0
        assert collect.detail["updated"] == 2
        assert extract.status == STAGE_SKIPPED
        assert "无新公告" in extract.detail["reason"]

    def test_source_only_analysis(self, tmp_path):
        """无 source：collect skipped，纯分析既有库。"""
        with BidDatabase(tmp_path / "b.db") as db:
            db.save_bid({"bid_id": "O-1", "project_name": "既有项目", "budget": 100.0})
        pipeline = ResearchPipeline(tmp_path / "b.db", output_dir=tmp_path / "r")
        result = pipeline.run()
        stages = {s.name: s for s in result.stages}
        assert stages["collect"].status == STAGE_SKIPPED
        assert stages["analyze"].detail["records"] == 1
        assert result.payload["budget"]["median"] == 100.0

    def test_empty_db_full_chain(self, tmp_path):
        """空库全链：analyze empty、report 渲染缺口节。"""
        pipeline = ResearchPipeline(tmp_path / "b.db", output_dir=tmp_path / "r")
        result = pipeline.run()
        assert result.stage("analyze").status == STAGE_EMPTY
        content = result.report_path.read_text(encoding="utf-8")
        assert "数据缺口" in content


class TestPipelineFailureFaces:
    """失败面。"""

    def test_extract_failure_parks_pending(self, source, tmp_path):
        """LLM 失败 → pending 登记 + 管道继续出报告。

        PL-001 有原文走 LLM（失败→pending）；PL-002 无原文直通（不失败）。
        """
        extractor = _mock_extractor(fail=True)
        pipeline = ResearchPipeline(
            tmp_path / "b.db", extractor=extractor, output_dir=tmp_path / "r"
        )
        result = pipeline.run(source)
        extract = result.stage("extract")
        assert extract.detail["llm_failures"] == 1
        assert extract.detail["parked"] == 1
        assert extract.detail["stored"] == 1  # PL-002 直通入库
        with BidDatabase(tmp_path / "b.db") as db:
            assert db.pending_stats()["pending"] == 1
        assert result.report_path.exists()  # 管道不因抽取失败中断

    def test_collect_failure_recorded(self, source, tmp_path):
        """collect 坏文件进 failures 明细（不静默）。"""
        (source / "broken.json").write_text("{bad", encoding="utf-8")
        pipeline = ResearchPipeline(
            tmp_path / "b.db", output_dir=tmp_path / "r"
        )
        result = pipeline.run(source)
        collect = result.stage("collect")
        assert collect.status == STAGE_OK
        assert any(
            f["origin"] == "broken.json" for f in collect.failures
        )

    def test_missing_source_raises(self, tmp_path):
        """源不存在 → SourceError 直抛（管道起步硬错）。"""
        from src.collect.sources import SourceError

        pipeline = ResearchPipeline(tmp_path / "b.db", output_dir=tmp_path / "r")
        with pytest.raises(SourceError):
            pipeline.run(tmp_path / "nope")

    def test_html_export(self, source, tmp_path):
        """html=True → HTML 也落盘。"""
        pipeline = ResearchPipeline(
            tmp_path / "b.db", output_dir=tmp_path / "r"
        )
        result = pipeline.run(source, html=True)
        assert result.payload["_html_path"]
        import pathlib

        assert pathlib.Path(result.payload["_html_path"]).exists()


class TestNoClobberCollect:
    """R103 不倒退合并接链：collect 更新走 merge_bid。

    「更完整记录胜出」的管道面——稀疏源重导不抹库、变更修正
    合法更新、真实变化 filled/changed 分账可见。
    """

    def _write(self, src, records):
        (src / "a.json").write_text(
            json.dumps(records, ensure_ascii=False), encoding="utf-8"
        )

    @pytest.fixture()
    def src(self, tmp_path):
        d = tmp_path / "ann"
        d.mkdir()
        return d

    def test_sparse_rerun_preserves_db(self, src, tmp_path):
        """稀疏源重跑：库内 budget/agency/winner 全保值不倒退。"""
        self._write(
            src,
            [
                {
                    "bid_id": "NC-1",
                    "project_name": "智慧水务",
                    "budget": 350.0,
                    "agency": "某代理",
                    "winner": "甲公司",
                }
            ],
        )
        db_path = tmp_path / "b.db"
        pipeline = ResearchPipeline(db_path, output_dir=tmp_path / "r")
        pipeline.run(src)
        # 另一源只收录了编号与名称——盲覆盖会抹掉三个字段
        self._write(src, [{"bid_id": "NC-1", "project_name": "智慧水务"}])
        second = pipeline.run(src)
        detail = second.stage("collect").detail
        assert detail["updated"] == 1
        assert detail["updated_filled"] == 0
        assert detail["updated_changed"] == 0
        with BidDatabase(db_path) as db:
            row = db.get_bid("NC-1")
        assert row["budget"] == 350.0
        assert row["agency"] == "某代理"
        assert row["winner"] == "甲公司"

    def test_enriched_rerun_fills_and_changes(self, src, tmp_path):
        """源侧修订（变更公告形态）：补缺 + 修正都入账。"""
        self._write(
            src,
            [
                {
                    "bid_id": "NC-2",
                    "project_name": "智慧交通",
                    "budget": 100.0,
                }
            ],
        )
        db_path = tmp_path / "b.db"
        pipeline = ResearchPipeline(db_path, output_dir=tmp_path / "r")
        pipeline.run(src)
        # 变更公告：预算下修 + 新增截止日与中标人
        self._write(
            src,
            [
                {
                    "bid_id": "NC-2",
                    "project_name": "智慧交通",
                    "budget": 88.0,
                    "deadline": "2026-12-20",
                    "winner": "乙公司",
                }
            ],
        )
        second = pipeline.run(src)
        detail = second.stage("collect").detail
        assert detail["updated_filled"] == 2  # deadline + winner
        assert detail["updated_changed"] == 1  # budget 100→88
        with BidDatabase(db_path) as db:
            row = db.get_bid("NC-2")
        assert row["budget"] == 88.0
        assert row["deadline"] == "2026-12-20"
        assert row["winner"] == "乙公司"

    def test_identical_rerun_zero_substance(self, src, tmp_path):
        """同值重跑：updated 计数（存在即复核口径）但实质分账为零。"""
        records = [
            {"bid_id": "NC-3", "project_name": "智慧园区", "budget": 50.0}
        ]
        self._write(src, records)
        db_path = tmp_path / "b.db"
        pipeline = ResearchPipeline(db_path, output_dir=tmp_path / "r")
        pipeline.run(src)
        second = pipeline.run(src)
        detail = second.stage("collect").detail
        assert detail["updated"] == 1
        assert detail["updated_filled"] == 0
        assert detail["updated_changed"] == 0

    def test_batch_merge_flows_to_db(self, src, tmp_path):
        """R101 批内补全 + R103 首跑入库链通：同件两源合并后一次入库。"""
        self._write(
            src,
            [
                {"bid_id": "NC-4", "project_name": "智慧安防", "region": "浙江"},
                {"bid_id": "nc-4", "project_name": "智慧安防", "budget": 66.0},
            ],
        )
        db_path = tmp_path / "b.db"
        pipeline = ResearchPipeline(db_path, output_dir=tmp_path / "r")
        result = pipeline.run(src)
        detail = result.stage("collect").detail
        assert detail["deduped"] == 1
        assert detail["merged_fields"] == 1  # 批内补全事件数
        assert detail["new"] == 1
        with BidDatabase(db_path) as db:
            row = db.get_bid("NC-4")
        assert row["region"] == "浙江"
        assert row["budget"] == 66.0  # 后到件补全的字段随首跑入库
