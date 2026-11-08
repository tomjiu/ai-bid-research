"""src/storage 模块单元测试。

使用 pytest tmp_path 隔离的临时数据库文件，验证 CRUD、
关键词/时间窗口查询与幂等 upsert 行为。
"""

from datetime import datetime, timedelta
from pathlib import Path

import pytest

from src.storage.database import BidDatabase


def _make_bid(bid_id: str, name: str, **overrides) -> dict:
    """构造测试用招标项目字典。

    Args:
        bid_id: 招标编号。
        name: 项目名称。
        overrides: 覆盖默认值的字段。

    Returns:
        项目数据字典。
    """
    bid = {
        "bid_id": bid_id,
        "project_name": name,
        "region": "浙江省 杭州市",
        "budget": 350.0,
        "publish_date": datetime.now().strftime("%Y-%m-%d"),
        "deadline": None,
        "category": "服务",
        "purchaser": "某市大数据局",
        "agency": None,
        "winner": None,
        "source_url": None,
        "requirements": ["ISO9001 认证", "近三年类似业绩"],
    }
    bid.update(overrides)
    return bid


@pytest.fixture()
def db(tmp_path: Path) -> BidDatabase:
    """返回使用临时文件的数据库实例（测试结束自动关闭）。"""
    database = BidDatabase(tmp_path / "bids.db")
    yield database
    database.close()


class TestBidDatabase:
    """BidDatabase 行为测试。"""

    def test_init_creates_db_file(self, tmp_path: Path) -> None:
        """初始化时创建数据库文件与父目录。"""
        target = tmp_path / "nested" / "data" / "bids.db"
        BidDatabase(target).close()
        assert target.is_file()

    def test_save_and_get_bid_roundtrip(self, db: BidDatabase) -> None:
        """保存后可完整读回，requirements 列表往返无损。"""
        bid = _make_bid("ZJ-2026-001", "智慧园区综合管理平台", budget=880.5)
        assert db.save_bid(bid) == 1

        loaded = db.get_bid("ZJ-2026-001")
        assert loaded is not None
        assert loaded["project_name"] == "智慧园区综合管理平台"
        assert loaded["budget"] == 880.5
        assert loaded["requirements"] == ["ISO9001 认证", "近三年类似业绩"]
        assert loaded["created_at"]  # 自动填充

    def test_save_bid_missing_required_field(self, db: BidDatabase) -> None:
        """缺少 bid_id 或 project_name 时拒绝保存。"""
        with pytest.raises(KeyError):
            db.save_bid({"project_name": "无编号项目"})
        with pytest.raises(KeyError):
            db.save_bid({"bid_id": "X-1", "project_name": ""})

    def test_save_bid_upsert_idempotent(self, db: BidDatabase) -> None:
        """同 bid_id 重复保存为更新而非新增。"""
        db.save_bid(_make_bid("X-1", "原名称", winner=None))
        db.save_bid(_make_bid("X-1", "新名称", winner="某某科技"))
        assert db.count_bids() == 1
        loaded = db.get_bid("X-1")
        assert loaded["project_name"] == "新名称"
        assert loaded["winner"] == "某某科技"

    def test_get_missing_returns_none(self, db: BidDatabase) -> None:
        """查询不存在的编号返回 None。"""
        assert db.get_bid("NOT-EXIST") is None

    def test_import_bids_batch(self, db: BidDatabase) -> None:
        """批量导入返回成功条数。"""
        bids = [
            _make_bid("B-1", "项目一"),
            _make_bid("B-2", "项目二"),
            _make_bid("B-3", "项目三"),
        ]
        assert db.import_bids(bids) == 3
        assert db.count_bids() == 3

    def test_query_by_keyword(self, db: BidDatabase) -> None:
        """关键词对项目名与编号模糊匹配。"""
        db.save_bid(_make_bid("A-1", "智慧园区管理平台"))
        db.save_bid(_make_bid("A-2", "城市交通监控系统"))
        db.save_bid(_make_bid("ZH-2026-9", "数据中心建设"))

        assert len(db.query_bids(keyword="智慧")) == 1
        assert len(db.query_bids(keyword="系统")) == 1
        # 编号模糊匹配
        assert len(db.query_bids(keyword="ZH-2026")) == 1
        # 不限关键词
        assert len(db.query_bids()) == 3

    def test_query_by_days_window(self, db: BidDatabase) -> None:
        """时间窗口过滤：仅返回 publish_date 在窗口内的记录。"""
        today = datetime.now()
        db.save_bid(
            _make_bid("NEW-1", "新项目", publish_date=today.strftime("%Y-%m-%d"))
        )
        db.save_bid(
            _make_bid(
                "OLD-1",
                "旧项目",
                publish_date=(today - timedelta(days=60)).strftime("%Y-%m-%d"),
            )
        )
        rows = db.query_bids(days=30)
        assert [row["bid_id"] for row in rows] == ["NEW-1"]
        # 不过滤天数时全部可见
        assert len(db.query_bids()) == 2

    def test_query_orders_by_date_desc(self, db: BidDatabase) -> None:
        """结果按发布日期降序排列。"""
        db.save_bid(_make_bid("D-1", "较早", publish_date="2026-01-10"))
        db.save_bid(_make_bid("D-2", "较晚", publish_date="2026-02-20"))
        rows = db.query_bids()
        assert [row["bid_id"] for row in rows] == ["D-2", "D-1"]

    def test_query_limit(self, db: BidDatabase) -> None:
        """limit 参数限制返回条数。"""
        for i in range(5):
            db.save_bid(_make_bid(f"L-{i}", f"限量项目{i}"))
        assert len(db.query_bids(limit=3)) == 3

    def test_count_bids_with_filters(self, db: BidDatabase) -> None:
        """count_bids 与 query_bids 过滤语义一致。"""
        db.save_bid(_make_bid("K-1", "智慧交通平台"))
        db.save_bid(_make_bid("K-2", "环保监测系统"))
        assert db.count_bids() == 2
        assert db.count_bids(keyword="智慧") == 1

    def test_stats_awarded_count(self, db: BidDatabase) -> None:
        """统计中仅含中标人的记录计入 awarded。"""
        db.save_bid(_make_bid("S-1", "已定标项目", winner="甲公司"))
        db.save_bid(_make_bid("S-2", "未定标项目", winner=None))
        db.save_bid(_make_bid("S-3", "空中标人项目", winner=""))
        stats = db.stats()
        assert stats["total"] == 3
        assert stats["awarded"] == 1

    def test_context_manager_closes(self, tmp_path: Path) -> None:
        """上下文管理器退出时关闭连接。"""
        with BidDatabase(tmp_path / "ctx.db") as db:
            db.save_bid(_make_bid("C-1", "上下文项目"))
        # 连接已关闭，再操作应报 ProgrammingError
        with pytest.raises(Exception):
            db.count_bids()

    def test_corrupted_requirements_fallback(self, db: BidDatabase) -> None:
        """requirements 字段损坏时回退为空列表而非报错。"""
        db.save_bid(_make_bid("R-1", "需求字段异常项目"))
        db._conn.execute("UPDATE bids SET requirements = '{bad json' WHERE bid_id = 'R-1'")
        db._conn.commit()
        loaded = db.get_bid("R-1")
        assert loaded is not None
        assert loaded["requirements"] == []
