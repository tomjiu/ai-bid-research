"""批量性能护栏测试（#601 批次 E 第 20 轮）。

研究级数据规模（千条）下的管道各面耗时护栏——防性能病态回退
（不是基准测试：上限取 CI 慢机的宽容口径，只抓数量级回退）。
"""

import json
import time

import pytest

from src.collect import dedupe_records, load_records
from src.storage.database import BidDatabase

#: 千条装载+去重的护栏（秒）——正常 <1s，CI 慢机宽容 30s。
_BULK_GUARD = 30.0

#: 千条入库的护栏（秒）。
_IMPORT_GUARD = 30.0

#: 千条关键词查询的护栏（秒）。
_QUERY_GUARD = 10.0


@pytest.fixture(scope="module")
def bulk_source(tmp_path_factory):
    """1200 条合成公告（含 200 条同件重复）。"""
    directory = tmp_path_factory.mktemp("bulk")
    records = []
    for i in range(1200):
        if i < 1000:
            records.append(
                {
                    "招标编号": f"BULK-{i:04d}",
                    "项目名称": f"智慧城市平台项目{i}期",
                    "地区": f"某省某市{i % 30}",
                    "预算金额": f"{100 + i}万元",
                    "发布日期": f"2026-{(i % 12) + 1:02d}-{(i % 27) + 1:02d}",
                    "资格要求": "ISO9001；独立法人",
                }
            )
        else:
            # 200 条重复（同 bid_id 大小写形态）
            j = i - 1000
            records.append(
                {
                    "bid_id": f"bulk-{j:04d}",
                    "project_name": f"智慧城市平台项目{j}期",
                }
            )
    path = directory / "bulk.json"
    path.write_text(
        json.dumps(records, ensure_ascii=False), encoding="utf-8"
    )
    return path


class TestBulkPerformance:
    """千条级护栏。"""

    def test_load_and_dedupe_under_guard(self, bulk_source):
        """1200 条装载+三级去重 < 30s（正常 <1s）。"""
        start = time.monotonic()
        loaded = load_records(bulk_source)
        deduped = dedupe_records(loaded.records)
        elapsed = time.monotonic() - start

        assert len(loaded.records) == 1200
        assert deduped.by_bid_id == 200  # 大小写不敏感判重
        assert len(deduped.unique) == 1000
        assert elapsed < _BULK_GUARD, (
            f"装载+去重 1200 条耗时 {elapsed:.1f}s 超护栏 {_BULK_GUARD}s"
        )

    def test_bulk_import_under_guard(self, bulk_source, tmp_path):
        """千条幂等入库 < 30s；重跑（全 update 面）同护栏内。"""
        loaded = load_records(bulk_source)
        deduped = dedupe_records(loaded.records)
        rows = [r.to_bid_row() for r in deduped.unique]

        db_path = tmp_path / "bulk.db"
        start = time.monotonic()
        with BidDatabase(db_path) as db:
            saved_first = db.import_bids(rows)
            elapsed_first = time.monotonic() - start

            start = time.monotonic()
            saved_second = db.import_bids(rows)  # 幂等重入
            elapsed_second = time.monotonic() - start
            stats = db.stats()

        assert saved_first == 1000
        assert saved_second == 1000
        assert stats["total"] == 1000
        assert elapsed_first < _IMPORT_GUARD
        assert elapsed_second < _IMPORT_GUARD

    def test_keyword_query_under_guard(self, bulk_source, tmp_path):
        """千条库上关键词+时间窗查询 < 10s（索引生效面）。"""
        loaded = load_records(bulk_source)
        deduped = dedupe_records(loaded.records)
        db_path = tmp_path / "bulk.db"
        with BidDatabase(db_path) as db:
            db.import_bids([r.to_bid_row() for r in deduped.unique])

        start = time.monotonic()
        with BidDatabase(db_path) as db:
            rows = db.query_bids(keyword="智慧城市", days=None, limit=1000)
            count = db.count_bids(days=90)
        elapsed = time.monotonic() - start

        assert len(rows) == 1000
        assert count > 0
        assert elapsed < _QUERY_GUARD

    def test_pipeline_bulk_e2e_under_guard(self, bulk_source, tmp_path):
        """千条源全链管道（离线）< 60s——含分析面（分位/词表/密度）。"""
        from src.pipeline import ResearchPipeline

        start = time.monotonic()
        pipeline = ResearchPipeline(
            tmp_path / "b.db", output_dir=tmp_path / "r"
        )
        result = pipeline.run(bulk_source)
        elapsed = time.monotonic() - start

        assert result.stage("collect").detail["new"] == 1000
        assert result.stage("analyze").detail["records"] == 1000
        assert result.report_path.exists()
        assert elapsed < 60.0, f"千条全链耗时 {elapsed:.1f}s"
