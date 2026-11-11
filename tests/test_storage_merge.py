"""src.storage.database.merge_bid 单元测试（#601 R102）。

「更完整记录胜出」的存储面形态——不倒退合并写入：

- 传入空缺（None/空串/空列表）不覆盖库内已有值（稀疏源重导不抹库）；
- 传入有值采用传入值（跨批时序上新证据胜——变更公告修正合法更新）；
- 分账返回 action / filled / changed / preserved 四键；
- unchanged 零写入（不制造 updated_at 搅动）。
"""

from pathlib import Path

import pytest

from src.storage.database import BidDatabase


def _bid(bid_id: str, name: str = "某项目", **overrides) -> dict:
    """最小必填形态（其余字段缺省 None——稀疏源典型形态）。"""
    row = {"bid_id": bid_id, "project_name": name}
    row.update(overrides)
    return row


@pytest.fixture()
def db(tmp_path: Path) -> BidDatabase:
    database = BidDatabase(tmp_path / "merge.db")
    yield database
    database.close()


class TestMergeBid:
    """merge_bid 不倒退合并。"""

    def test_insert_when_absent(self, db: BidDatabase):
        """库内无此 id → 直插（与 save_bid 等价），三计数为 0。"""
        result = db.merge_bid(_bid("N-1", budget=88.0))
        assert result == {
            "action": "inserted",
            "filled": 0,
            "changed": 0,
            "preserved": 0,
        }
        assert db.get_bid("N-1")["budget"] == 88.0

    def test_missing_required_raises(self, db: BidDatabase):
        """必填校验与 save_bid 同口径。"""
        with pytest.raises(KeyError):
            db.merge_bid({"project_name": "无编号"})
        with pytest.raises(KeyError):
            db.merge_bid({"bid_id": "X-1", "project_name": ""})

    def test_sparse_reimport_does_not_clobber(self, db: BidDatabase):
        """稀疏源重导：库内 budget/agency/winner 全部保值不倒退。"""
        db.save_bid(
            _bid(
                "S-1",
                "智慧城市一期",
                budget=350.0,
                agency="某代理",
                winner="甲公司",
                deadline="2026-12-01",
            )
        )
        # 稀疏形态：只有编号与名称（另一源只收录了标题）
        result = db.merge_bid(_bid("S-1", "智慧城市一期"))
        assert result == {
            "action": "unchanged",
            "filled": 0,
            "changed": 0,
            "preserved": 0,
        }
        row = db.get_bid("S-1")
        assert row["budget"] == 350.0
        assert row["agency"] == "某代理"
        assert row["winner"] == "甲公司"
        assert row["deadline"] == "2026-12-01"

    def test_unchanged_is_zero_write(self, db: BidDatabase):
        """unchanged 零写入——total_changes 计数器不动（同值重导
        不产生写事务，增量重跑的库写面最小化）。"""
        db.merge_bid(_bid("U-1", "项目甲", budget=1.0))
        before = db._conn.total_changes
        result = db.merge_bid(_bid("U-1", "项目甲", budget=1.0))
        assert result["action"] == "unchanged"
        assert db._conn.total_changes == before  # 零写入
        # 稀疏重导（传入缺省）同样零写入
        sparse = db.merge_bid(_bid("U-1", "项目甲"))
        assert sparse["action"] == "unchanged"
        assert db._conn.total_changes == before

    def test_merged_does_write(self, db: BidDatabase):
        """真实变化（补缺/更新）才产生写事务。"""
        db.merge_bid(_bid("T-1", "项目乙"))
        before = db._conn.total_changes
        result = db.merge_bid(_bid("T-1", "项目乙", budget=9.0))
        assert result["action"] == "merged"
        assert db._conn.total_changes > before
        assert db.get_bid("T-1")["budget"] == 9.0

    def test_fill_missing_fields(self, db: BidDatabase):
        """库内空缺被传入值补上（filled 分账）。"""
        db.merge_bid(_bid("F-1", "项目丙", region="浙江"))
        result = db.merge_bid(
            _bid("F-1", "项目丙", budget=120.0, winner="乙公司")
        )
        assert result == {
            "action": "merged",
            "filled": 2,
            "changed": 0,
            "preserved": 1,  # region：传入缺、库内有 → 保值
        }
        row = db.get_bid("F-1")
        assert row["budget"] == 120.0
        assert row["winner"] == "乙公司"
        assert row["region"] == "浙江"

    def test_newer_value_wins(self, db: BidDatabase):
        """冲突值新证据胜（变更公告修正预算）——changed 分账。"""
        db.merge_bid(_bid("C-1", "项目丁", budget=350.0, deadline="2026-12-01"))
        result = db.merge_bid(
            _bid("C-1", "项目丁", budget=300.0, deadline="2026-12-20")
        )
        assert result["action"] == "merged"
        assert result["changed"] == 2
        row = db.get_bid("C-1")
        assert row["budget"] == 300.0
        assert row["deadline"] == "2026-12-20"

    def test_zero_budget_is_value(self, db: BidDatabase):
        """budget=0.0 是记录在案的值（病态但如实）——可填充。"""
        db.merge_bid(_bid("Z-1", "项目戊"))
        result = db.merge_bid(_bid("Z-1", "项目戊", budget=0.0))
        assert result["action"] == "merged"
        assert result["filled"] == 1
        assert db.get_bid("Z-1")["budget"] == 0.0

    def test_requirements_replaced_as_unit(self, db: BidDatabase):
        """requirements 非空列表整体替换（不逐条并集——同件两源
        措辞不一，并集会无限膨胀；新证据整体胜出更诚实）。"""
        db.merge_bid(_bid("R-1", "项目己", requirements=["一级资质", "三个业绩"]))
        result = db.merge_bid(_bid("R-1", "项目己", requirements=["一级资质"]))
        assert result["action"] == "merged"
        assert result["changed"] == 1
        assert db.get_bid("R-1")["requirements"] == ["一级资质"]

    def test_requirements_preserved_when_missing(self, db: BidDatabase):
        """传入 requirements 空缺 → 库内列表保值。"""
        db.merge_bid(_bid("R-2", "项目庚", requirements=["ISO9001"]))
        result = db.merge_bid(_bid("R-2", "项目庚"))
        assert result["action"] == "unchanged"
        assert db.get_bid("R-2")["requirements"] == ["ISO9001"]

    def test_requirements_json_text_form(self, db: BidDatabase):
        """JSON 文本形态的 requirements（db --import 路径）与列表同权。"""
        db.merge_bid(_bid("R-3", "项目辛", requirements=["A"]))
        result = db.merge_bid(
            {
                "bid_id": "R-3",
                "project_name": "项目辛",
                "requirements": '["A", "B"]',  # JSON 文本形态
            }
        )
        assert result["action"] == "merged"
        assert db.get_bid("R-3")["requirements"] == ["A", "B"]
        # 同值 JSON 文本重导 → unchanged（归一比较非字符串比较）
        again = db.merge_bid(
            {
                "bid_id": "R-3",
                "project_name": "项目辛",
                "requirements": '["A", "B"]',
            }
        )
        assert again["action"] == "unchanged"

    def test_mixed_accounting(self, db: BidDatabase):
        """一次合并同时发生补/改/保——三计数各记各的账。"""
        db.merge_bid(
            _bid(
                "M-1",
                "项目壬",
                region="浙江",
                budget=100.0,
                winner="甲",
            )
        )
        result = db.merge_bid(
            _bid(
                "M-1",
                "项目壬",
                budget=200.0,       # changed（100→200）
                deadline="2026-12-01",  # filled（库内缺）
                agency="某代理",      # filled（库内缺）
                # winner/region 传入缺而库内有 → preserved ×2
            )
        )
        assert result == {
            "action": "merged",
            "filled": 2,
            "changed": 1,
            "preserved": 2,
        }
        row = db.get_bid("M-1")
        assert (row["budget"], row["deadline"], row["agency"], row["winner"]) == (
            200.0,
            "2026-12-01",
            "某代理",
            "甲",
        )
