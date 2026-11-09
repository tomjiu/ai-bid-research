"""src/analyze 数据集测试（#601 批次 C·R10）。"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from src.analyze.dataset import BidDataset, filter_records, load_dataset
from src.storage.database import BidDatabase


def make_db(tmp_path, rows):
    db = BidDatabase(tmp_path / "t.db")
    db.import_bids(rows)
    return db


@pytest.fixture()
def rows():
    """构造覆盖过滤维度的样本集。"""
    today = date.today()
    recent = today.isoformat()
    old = (today - timedelta(days=40)).isoformat()
    return [
        {
            "bid_id": "A-1",
            "project_name": "智慧城市一期平台",
            "region": "浙江省杭州市",
            "budget": 1200.0,
            "publish_date": recent,
            "winner": "甲公司",
        },
        {
            "bid_id": "A-2",
            "project_name": "数据中心设备采购",
            "region": "北京市",
            "budget": 800.0,
            "publish_date": old,  # 40 天前——days=30 窗口外
            "winner": None,
        },
        {
            "bid_id": "B-1",
            "project_name": "智慧城市二期",
            "region": "浙江省宁波市",
            "budget": None,  # 预算缺失
            "publish_date": None,  # 日期缺失——days 窗口内不保留
            "winner": "乙公司",
        },
        {
            "bid_id": "b-2",
            "project_name": "运维服务",
            "region": None,
            "budget": 100.0,
            "publish_date": recent,
            "winner": "乙公司",
        },
    ]


class TestBidDataset:
    def test_counts(self, rows):
        ds = BidDataset(rows)
        assert ds.total == 4
        assert ds.awarded == 3
        assert ds.award_rate == pytest.approx(0.75)
        assert ds.with_budget == 3
        assert ds.with_date == 3

    def test_budget_views(self, rows):
        ds = BidDataset(rows)
        assert ds.budget_values == [1200.0, 800.0, 100.0]
        assert ds.budget_total == pytest.approx(2100.0)

    def test_winners_dedup_order(self, rows):
        ds = BidDataset(rows)
        assert ds.winners() == ["甲公司", "乙公司"]

    def test_regions_dedup_order(self, rows):
        ds = BidDataset(rows)
        assert ds.regions() == ["浙江省杭州市", "北京市", "浙江省宁波市"]

    def test_months_sorted_unique(self, rows):
        ds = BidDataset(rows)
        today = date.today()
        expected = sorted(
            {today.isoformat()[:7], (today - timedelta(days=40)).isoformat()[:7]}
        )
        assert ds.months() == expected

    def test_empty_dataset(self):
        ds = BidDataset([])
        assert ds.total == 0
        assert ds.awarded == 0
        assert ds.award_rate is None
        assert ds.budget_values == []
        assert ds.budget_total == 0
        assert ds.months() == []
        assert ds.winners() == []


class TestFilterRecords:
    def test_keyword_case_insensitive(self, rows):
        got = filter_records(rows, keyword="智慧城市")
        assert [r["bid_id"] for r in got] == ["A-1", "B-1"]

    def test_keyword_matches_bid_id_too(self, rows):
        got = filter_records(rows, keyword="a-")  # 命中 A-1/A-2（bid_id 子串）
        assert [r["bid_id"] for r in got] == ["A-1", "A-2"]

    def test_days_window_excludes_old_and_undated(self, rows):
        got = filter_records(rows, days=30)
        # A-2（40 天前）与 B-1（无日期）都不保留
        assert [r["bid_id"] for r in got] == ["A-1", "b-2"]

    def test_region_substring(self, rows):
        got = filter_records(rows, region="浙江省")
        assert [r["bid_id"] for r in got] == ["A-1", "B-1"]

    def test_filters_combine_with_and(self, rows):
        got = filter_records(rows, keyword="智慧城市", region="宁波市")
        assert [r["bid_id"] for r in got] == ["B-1"]

    def test_no_filters_returns_all_in_order(self, rows):
        got = filter_records(rows)
        assert [r["bid_id"] for r in got] == ["A-1", "A-2", "B-1", "b-2"]


class TestLoadDataset:
    def test_load_all(self, tmp_path, rows):
        db = make_db(tmp_path, rows)
        ds = load_dataset(db)
        assert ds.total == 4
        db.close()

    def test_load_with_filters(self, tmp_path, rows):
        db = make_db(tmp_path, rows)
        ds = load_dataset(db, keyword="智慧城市", days=30)
        assert [r["bid_id"] for r in ds.records] == ["A-1"]
        db.close()

    def test_requirements_deserialized(self, tmp_path):
        db = make_db(
            tmp_path,
            [
                {
                    "bid_id": "R-1",
                    "project_name": "要求还原",
                    "requirements": ["资质A", "业绩B"],
                }
            ],
        )
        ds = load_dataset(db)
        assert ds.records[0]["requirements"] == ["资质A", "业绩B"]
        db.close()
