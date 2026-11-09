"""src/collect.dedupe 模块单元测试（#601 批次 A 第 3 轮）。

覆盖三级证据判重（bid_id / source_url / fingerprint）、keep-first
顺序确定性、URL 归一与 duplicates 明细完整性。
"""

import pytest

from src.collect import (
    AnnouncementRecord,
    dedupe_records,
    normalize_source_url,
)


def _record(bid_id: str, name: str = "某项目", **overrides) -> AnnouncementRecord:
    """构造规范化记录（绕过 from_raw 的便捷构造）。"""
    raw = {"bid_id": bid_id, "project_name": name}
    raw.update(overrides)
    return AnnouncementRecord.from_raw(raw)


# ----------------------------------------------------------------------
# URL 归一
# ----------------------------------------------------------------------

class TestNormalizeSourceUrl:
    """source_url 归一（比较用）。"""

    def test_forms_parametrized(self):
        """参数化用例体（大小写/尾斜杠/utm 归一；非 utm 参数保序）。"""
        cases = [
            (
                "https://Example.COM/notice/1/",
                "https://example.com/notice/1",
            ),
            (
                "HTTPS://example.com/notice/1",
                "https://example.com/notice/1",
            ),
            (
                "http://example.com/n?utm_source=b&id=9",
                "http://example.com/n?id=9",
            ),
            # 非 utm 参数保持源顺序（id 在前 cat 在后）
            (
                "http://example.com/n?id=9&utm_medium=x&cat=3",
                "http://example.com/n?id=9&cat=3",
            ),
        ]
        for raw, expected in cases:
            assert normalize_source_url(raw) == expected

    @pytest.mark.parametrize(
        "raw",
        [None, "", "   ", "相对路径/非URL", "javascript:void(0)"],
    )
    def test_non_url_returns_none(self, raw):
        """空值/非 URL/无 host（无 scheme 文本、伪协议）→ None。"""
        assert normalize_source_url(raw) is None


# ----------------------------------------------------------------------
# 三级判重
# ----------------------------------------------------------------------

class TestDedupeRecords:
    """dedupe_records 三级证据判重。"""

    def test_empty_batch(self):
        """空批 → 零 unique 零 removed。"""
        result = dedupe_records([])
        assert result.unique == []
        assert result.removed == 0

    def test_same_bid_id_case_insensitive(self):
        """同 bid_id（大小写/空白不一）判重，keep-first。"""
        first = _record("ZJ-2026-001", "智慧城市一期")
        second = _record("zj-2026-001 ", "智慧城市一期-另一源收录")
        third = _record("ZJ-2026-001", "再次重复")
        result = dedupe_records([first, second, third])
        assert len(result.unique) == 1
        assert result.unique[0].project_name == "智慧城市一期"
        assert result.by_bid_id == 2
        assert [d["reason"] for d in result.duplicates] == [
            "bid_id",
            "bid_id",
        ]
        assert all(d["duplicate_of"] == "ZJ-2026-001" for d in result.duplicates)

    def test_same_normalized_url(self):
        """同公告页（URL 归一后一致）判重。"""
        first = _record(
            "A-1",
            source_url="https://example.com/notice/5/?utm_source=wechat",
        )
        second = _record(
            "B-2",
            source_url="HTTPS://Example.COM/notice/5/",
        )
        result = dedupe_records([first, second])
        assert len(result.unique) == 1
        assert result.by_source_url == 1
        assert result.duplicates[0]["reason"] == "source_url"
        assert result.duplicates[0]["duplicate_of"] == "A-1"

    def test_same_fingerprint_different_bid_id(self):
        """同件多源（bid_id 拼写不一）指纹判重。"""
        first = _record(
            "A-1", "智慧园区平台", publish_date="2026-11-01", region="浙江"
        )
        second = _record(
            "A-1-备选编号", "智慧园区平台", publish_date="2026-11-01", region="浙江"
        )
        result = dedupe_records([first, second])
        assert len(result.unique) == 1
        assert result.by_fingerprint == 1
        assert result.duplicates[0]["reason"] == "fingerprint"

    def test_bid_id_wins_over_url(self):
        """bid_id 证据最强：即使 URL 不同也判重（先判 bid_id）。"""
        first = _record("C-1", "项目一", source_url="https://x.com/1")
        second = _record("C-1", "项目一改", source_url="https://y.com/2")
        result = dedupe_records([first, second])
        assert result.by_bid_id == 1
        assert result.by_source_url == 0

    def test_distinct_records_all_kept(self):
        """互不重复的记录全部保留且顺序不变。"""
        records = [
            _record("D-1", "甲项目", region="浙江"),
            _record("D-2", "乙项目", region="江苏"),
            _record("D-3", "丙项目", region="广东"),
        ]
        result = dedupe_records(records)
        assert [r.bid_id for r in result.unique] == ["D-1", "D-2", "D-3"]
        assert result.removed == 0

    def test_keep_first_deterministic(self):
        """keep-first 与传入顺序绑定（先到者胜，可复现）。"""
        early = _record("E-1", "早批次项目", budget=100.0)
        late = _record("E-2", "早批次项目", budget=999.0)  # 同指纹后到
        result = dedupe_records([early, late])
        assert result.unique[0].budget == 100.0

        result_swapped = dedupe_records([late, early])
        assert result_swapped.unique[0].budget == 999.0

    def test_three_evidence_levels_counted(self):
        """三类判重计数互不混账。"""
        records = [
            _record("F-1", "项目甲", region="浙江"),
            _record("f-1", "项目甲-重复源", region="浙江"),          # bid_id
            _record(
                "F-2", "项目乙", source_url="https://c.com/n?utm_x=1"
            ),
            _record("F-3", "项目乙变", source_url="https://c.com/n"),  # url
            _record("F-4", "项目丙", region="江苏", publish_date="2026-01-01"),
            _record("F-5", "项目丙", region="江苏", publish_date="2026-01-01"),
        ]
        result = dedupe_records(records)
        assert result.by_bid_id == 1
        assert result.by_source_url == 1
        assert result.by_fingerprint == 1
        assert result.removed == 3
        assert len(result.unique) == 3

    def test_duplicate_detail_fields(self):
        """duplicates 明细含 bid_id/reason/duplicate_of 三键。"""
        records = [
            _record("G-1", "项目X"),
            _record("G-1 ", "项目X-重复"),
        ]
        result = dedupe_records(records)
        detail = result.duplicates[0]
        assert set(detail.keys()) == {"bid_id", "reason", "duplicate_of"}
        assert detail["bid_id"] == "G-1"
