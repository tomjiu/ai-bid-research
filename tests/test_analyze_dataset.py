"""src/analyze.dataset 模块单元测试（#601 批次 C 第 10 轮）。"""

import pytest

from src.analyze import AnalysisDataset, load_dataset
from src.storage.database import BidDatabase


@pytest.fixture()
def filled_db(tmp_path):
    """预置 4 条记录（含缺预算/缺日期/已定标形态）的研究库。"""
    with BidDatabase(tmp_path / "b.db") as db:
        db.import_bids(
            [
                {
                    "bid_id": "A-1",
                    "project_name": "智慧城市一期",
                    "budget": 300.0,
                    "publish_date": "2026-11-01",
                    "region": "浙江",
                    "winner": "甲公司",
                },
                {
                    "bid_id": "A-2",
                    "project_name": "智慧城市二期",
                    "budget": 500.0,
                    "publish_date": "2026-11-03",
                    "region": "江苏",
                },
                {
                    "bid_id": "A-3",
                    "project_name": "无预算项目",
                    "publish_date": "2026-11-05",
                },
                {
                    "bid_id": "A-4",
                    "project_name": "坏日期项目",
                    "budget": 100.0,
                    "publish_date": None,
                },
            ]
        )
    return tmp_path / "b.db"


class TestAnalysisDatasetViews:
    """数据集视图与派生访问器。"""

    def test_empty_dataset(self):
        """空集：is_empty、len=0、比率 None。"""
        ds = AnalysisDataset()
        assert ds.is_empty is True
        assert len(ds) == 0
        assert ds.award_rate is None
        assert ds.complete_rate is None
        assert ds.budgets == []
        assert ds.publish_dates == []

    def test_load_from_path(self, filled_db):
        """从路径加载：记录数与字段完整。"""
        ds = load_dataset(filled_db)
        assert len(ds) == 4
        assert ds.keyword is None
        assert not ds.is_empty

    def test_budgets_only_valid(self, filled_db):
        """预算序列剔除 None（A-3 无预算）——顺序随查询序，无序比较。"""
        ds = load_dataset(filled_db)
        assert sorted(ds.budgets) == [100.0, 300.0, 500.0]

    def test_publish_dates_sorted_and_valid(self, filled_db):
        """日期序列升序、剔除坏值（A-4 无日期）。"""
        ds = load_dataset(filled_db)
        dates = ds.publish_dates
        assert len(dates) == 3
        assert dates[0] < dates[1] < dates[2]

    def test_award_rate(self, filled_db):
        """开标率：1/4。"""
        ds = load_dataset(filled_db)
        assert ds.award_rate == pytest.approx(0.25)
        assert len(ds.awarded_records) == 1

    def test_complete_rate_range(self, filled_db):
        """命中率在 (0,1) 区间且可复算。"""
        ds = load_dataset(filled_db)
        assert 0 < ds.complete_rate < 1

    def test_generated_at_present(self, filled_db):
        """数据集带生成时刻（报告可追溯）。"""
        ds = load_dataset(filled_db)
        assert len(ds.generated_at) >= 10


class TestLoadDatasetFilters:
    """加载过滤面。"""

    def test_keyword_filter(self, filled_db):
        """关键词过滤与 db --query 同口径。"""
        ds = load_dataset(filled_db, keyword="二期")
        assert len(ds) == 1
        assert ds.records[0]["bid_id"] == "A-2"

    def test_days_filter(self, filled_db):
        """时间窗口过滤（publi_date 早于窗口的剔除）。"""
        ds = load_dataset(filled_db, days=1)
        # 数据是「今天」入库、发布日期在 2026-11-01~05——
        # days=1 只保留最近 1 天内的发布记录，应得 0 条
        assert ds.days == 1
        # （入库日期=今天 > 发布日期，全部超出窗口）
        assert len(ds) == 0

    def test_missing_path_returns_empty(self, tmp_path):
        """路径不存在 → 空数据集（不抛）。"""
        ds = load_dataset(tmp_path / "nope.db")
        assert ds.is_empty

    def test_load_from_open_db(self, filled_db):
        """已打开的 db 实例直传。"""
        with BidDatabase(filled_db) as db:
            ds = load_dataset(db, keyword="一期")
        assert len(ds) == 1
