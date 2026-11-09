"""端到端离线全链测试（#601 批次 D 第 19 轮）。

fixture 公告数据集 → pipeline 全链 → 报告内容逐节断言。
fixture 为**合成脱敏**数据（非真实语料），覆盖：中文别名、
同件重复、原文流、坏行、坏文件、缺必填、多形态金额日期。
"""

import json
from pathlib import Path

import pytest

from src.pipeline import ResearchPipeline
from src.storage.database import BidDatabase

FIXTURES = Path(__file__).parent / "fixtures" / "announcements"


class TestEndToEndOffline:
    """fixture → pipeline → 报告端到端。"""

    @pytest.fixture()
    def result(self, tmp_path):
        """跑一次全链管道（离线）。"""
        pipeline = ResearchPipeline(
            tmp_path / "b.db", output_dir=tmp_path / "r"
        )
        return pipeline.run(FIXTURES)

    def test_collect_stage_accounting(self, result):
        """collect 分账：文件/装载/去重/失败数全对得上。"""
        collect = result.stage("collect")
        assert collect.status == "ok"
        # 5 个可读文件（d-损坏 在装载面失败，不计 files_read？——
        # files_read 统计的是「进入读取的文件」= 全部 6 个源文件
        assert collect.detail["files_read"] == 6
        # a.json 3 条（1 与 FX-001 dup）+ b.jsonl 2 好 + c 1 + e 1 条失败在
        # 记录面 + f.json 5 条 = 成功 3+2+1+5 = 11
        assert collect.detail["loaded"] == 11
        # 去重 1（FX-001 同件）
        assert collect.detail["deduped"] == 1
        assert collect.detail["new"] == 10
        # 失败：d-损坏.json（文件级）+ b-原文流.jsonl:2（行级）+ e-缺字段.json（记录级）
        assert len(collect.failures) == 3
        origins = {f["origin"] for f in collect.failures}
        assert origins == {
            "d-损坏.json", "b-原文流.jsonl:2", "e-缺字段.json",
        }

    def test_extract_skipped_offline(self, result):
        """离线模式：extract skipped（fixture 全链不调 API）。"""
        extract = result.stage("extract")
        assert extract.status == "skipped"
        assert "离线模式" in extract.detail["reason"]

    def test_analyze_stage(self, result):
        """analyze：10 条入库记录。"""
        analyze = result.stage("analyze")
        assert analyze.status == "ok"
        assert analyze.detail["records"] == 10

    def test_report_content_sections(self, result, tmp_path):
        """报告内容：六节 + 关键数据落面。"""
        content = result.report_path.read_text(encoding="utf-8")
        # 标题与数据集口径
        assert "领域数据分析报告：全量数据" in content
        assert "**10 条**" in content
        # 预算分布表（FX-002 1.2亿 → 12000 万元在 max）
        assert "一、预算分布" in content
        assert "12,000.0" in content
        # 区域分布（浙江最多：FX-001/003/005/007~010 = 6 条）
        assert "二、区域分布" in content
        assert "| 浙江省 杭州市 |" in content
        # 月度趋势（9 月 2 条）
        assert "三、月度发布趋势" in content
        assert "| 2026-09 | 2 |" in content
        # 领域关键词（智慧城市/智慧水务命中）
        assert "四、领域关键词" in content
        assert "| 智慧水务 |" in content or "| 智慧城市 |" in content
        # 密度（10 条跨 3 月 → ~3.3/月 → 中）
        assert "六、竞争密度" in content
        # 口径说明
        assert "启发式估算" in content

    def test_pipeline_runs_ledger(self, result, tmp_path):
        """台账：stages 四段 + 报告路径。"""
        with BidDatabase(tmp_path / "b.db") as db:
            runs = db.pipeline_runs_list()
        assert runs[0]["status"] == "done"
        assert len(runs[0]["stages"]) == 4
        assert runs[0]["report_path"] == str(result.report_path)

    def test_db_state_after_pipeline(self, result, tmp_path):
        """库状态：10 条 bids + 幂等可重跑。"""
        db_path = tmp_path / "b.db"
        with BidDatabase(db_path) as db:
            stats = db.stats()
            row = db.get_bid("FX-001")
        assert stats["total"] == 10
        assert row["budget"] == 3500.0  # 3,500万元 归一
        assert row["publish_date"] == "2026-10-12"

        # 重跑（幂等）
        pipeline = ResearchPipeline(db_path, output_dir=tmp_path / "r2")
        second = pipeline.run(FIXTURES)
        assert second.stage("collect").detail["new"] == 0
        assert second.stage("collect").detail["updated"] == 10
        with BidDatabase(db_path) as db:
            assert db.stats()["total"] == 10

    def test_keyword_scoped_run(self, tmp_path):
        """关键词切片全链（智慧水务 5 条）。"""
        pipeline = ResearchPipeline(
            tmp_path / "b.db", output_dir=tmp_path / "r"
        )
        result = pipeline.run(FIXTURES, keyword="智慧水务")
        content = result.report_path.read_text(encoding="utf-8")
        assert "「智慧水务」" in content
        assert "**5 条**" in content
        # 定标率 100%（f-定标面全部已定标）
        assert "| 智慧水务 | 5 |" in content
