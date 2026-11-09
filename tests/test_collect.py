"""src/collect 模块单元测试（#601 批次 A）。

覆盖 AnnouncementRecord 的别名归一、字段清洗、金额/日期规范化、
必填校验、指纹稳定性与入库行兼容性。
"""

import pytest

from src.collect import AnnouncementRecord, RecordValidationError
from src.storage.database import BidDatabase


# ----------------------------------------------------------------------
# 构造与校验
# ----------------------------------------------------------------------

class TestFromRaw:
    """from_raw 构造面。"""

    def test_canonical_fields(self):
        """规范名直传：字段原样保留。"""
        record = AnnouncementRecord.from_raw(
            {
                "bid_id": "ZJ-2026-001",
                "project_name": "智慧城市感知平台",
                "region": "浙江省 杭州市",
                "budget": 350.0,
                "publish_date": "2026-11-01",
                "deadline": "2026-11-20",
                "category": "信息化",
                "purchaser": "某市大数据局",
                "agency": "某招标代理公司",
                "source_url": "https://example.gov.cn/notice/1",
                "requirements": ["ISO9001 认证", "近三年类似业绩"],
            }
        )
        assert record.bid_id == "ZJ-2026-001"
        assert record.project_name == "智慧城市感知平台"
        assert record.budget == 350.0
        assert record.publish_date == "2026-11-01"
        assert record.deadline == "2026-11-20"
        assert record.requirements == ["ISO9001 认证", "近三年类似业绩"]
        assert record.extras == {}
        assert record.warnings == []

    def test_chinese_aliases(self):
        """中文常见命名全部映射到规范名。"""
        record = AnnouncementRecord.from_raw(
            {
                "招标编号": "HZ-2026-77",
                "项目名称": "校园安防改造",
                "地区": "浙江省 杭州市",
                "预算金额": "120万元",
                "发布日期": "2026年11月2日",
                "截止时间": "2026/11/25",
                "采购人": "某教育局",
                "中标人": "某科技公司",
                "链接": "https://example.gov.cn/n/2",
                "资格要求": "ISO9001；近三年业绩不少于2项",
            }
        )
        assert record.bid_id == "HZ-2026-77"
        assert record.project_name == "校园安防改造"
        assert record.region == "浙江省 杭州市"
        assert record.budget == 120.0
        assert record.publish_date == "2026-11-02"
        assert record.deadline == "2026-11-25"
        assert record.purchaser == "某教育局"
        assert record.winner == "某科技公司"
        assert record.source_url == "https://example.gov.cn/n/2"
        assert record.requirements == ["ISO9001", "近三年业绩不少于2项"]

    def test_missing_bid_id_raises(self):
        """缺 bid_id → RecordValidationError 且指明字段。"""
        with pytest.raises(RecordValidationError) as excinfo:
            AnnouncementRecord.from_raw({"project_name": "某项目"})
        assert excinfo.value.field == "bid_id"

    def test_empty_project_name_raises(self):
        """project_name 为空白 → 校验失败。"""
        with pytest.raises(RecordValidationError) as excinfo:
            AnnouncementRecord.from_raw(
                {"bid_id": "X-1", "project_name": "   "}
            )
        assert excinfo.value.field == "project_name"

    def test_non_dict_raises_type_error(self):
        """载荷非字典 → TypeError。"""
        with pytest.raises(TypeError):
            AnnouncementRecord.from_raw(["not", "a", "dict"])

    def test_unknown_fields_kept_in_extras(self):
        """未知字段不丢弃，保留在 extras。"""
        record = AnnouncementRecord.from_raw(
            {
                "bid_id": "X-2",
                "project_name": "某项目",
                "评分办法": "综合评分法",
                "开标地点": "第三开标室",
            }
        )
        assert record.extras == {
            "评分办法": "综合评分法",
            "开标地点": "第三开标室",
        }

    def test_none_values_tolerated(self):
        """全部可选字段为 None 时不告警、不炸。"""
        record = AnnouncementRecord.from_raw(
            {
                "bid_id": "X-3",
                "project_name": "某项目",
                "budget": None,
                "publish_date": None,
                "requirements": None,
            }
        )
        assert record.budget is None
        assert record.publish_date is None
        assert record.requirements == []
        assert record.warnings == []


# ----------------------------------------------------------------------
# 金额归一
# ----------------------------------------------------------------------

class TestBudgetNormalization:
    """budget 字段单位归一面。"""

    @pytest.mark.parametrize(
        "raw, expected",
        [
            (350, 350.0),
            (350.5, 350.5),
            ("350", 350.0),
            ("350.5", 350.5),
            ("350万", 350.0),
            ("350万元", 350.0),
            ("3,500,000元", 350.0),
            ("3500000元", 350.0),
            ("1.2亿", 12000.0),
            ("1.2亿元", 12000.0),
            (0, 0.0),
        ],
    )
    def test_budget_forms(self, raw, expected):
        """各金额形态统一归一为万元。"""
        record = AnnouncementRecord.from_raw(
            {"bid_id": "B-1", "project_name": "某项目", "budget": raw}
        )
        assert record.budget == pytest.approx(expected)
        assert record.warnings == []

    @pytest.mark.parametrize(
        "raw",
        ["面议", "详见公告", "-50", True],
    )
    def test_budget_unparseable_becomes_none_with_warning(self, raw):
        """不可解析金额 → None + 告警（不炸管道）。"""
        record = AnnouncementRecord.from_raw(
            {"bid_id": "B-2", "project_name": "某项目", "budget": raw}
        )
        assert record.budget is None
        assert any(w.startswith("budget") for w in record.warnings)


# ----------------------------------------------------------------------
# 日期归一
# ----------------------------------------------------------------------

class TestDateNormalization:
    """日期字段归一面。"""

    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("2026-11-09", "2026-11-09"),
            ("2026/11/9", "2026-11-09"),
            ("2026.11.9", "2026-11-09"),
            ("2026年11月9日", "2026-11-09"),
            ("2026-11-09 14:30:00", "2026-11-09"),
            (" 2026-11-09 ", "2026-11-09"),
        ],
    )
    def test_date_forms(self, raw, expected):
        """各日期形态统一归一为 YYYY-MM-DD。"""
        record = AnnouncementRecord.from_raw(
            {
                "bid_id": "D-1",
                "project_name": "某项目",
                "publish_date": raw,
            }
        )
        assert record.publish_date == expected
        assert record.warnings == []

    @pytest.mark.parametrize(
        "raw",
        ["预计 2026 年 11 月", "下周二", "2026-13-45", ""],
    )
    def test_date_unparseable(self, raw):
        """不可解析日期 → None + 告警（或空值静默）。"""
        record = AnnouncementRecord.from_raw(
            {
                "bid_id": "D-2",
                "project_name": "某项目",
                "publish_date": raw,
            }
        )
        assert record.publish_date is None
        if raw:  # 空串属合法缺省，静默
            assert any(w.startswith("publish_date") for w in record.warnings)


# ----------------------------------------------------------------------
# 文本清洗与 requirements
# ----------------------------------------------------------------------

class TestTextCleaning:
    """文本清洗面。"""

    def test_region_whitespace_collapsed(self):
        """地区内部空白折叠为单空格。"""
        record = AnnouncementRecord.from_raw(
            {
                "bid_id": "T-1",
                "project_name": "  某改造   项目  ",
                "region": " 浙江省　杭州市  余杭区 ",
            }
        )
        assert record.project_name == "某改造 项目"
        assert record.region == "浙江省 杭州市 余杭区"

    def test_requirements_string_split(self):
        """requirements 字符串按分号/换行切分。"""
        record = AnnouncementRecord.from_raw(
            {
                "bid_id": "T-2",
                "project_name": "某项目",
                "requirements": "ISO9001认证；近三年业绩≥2项\n独立法人资格",
            }
        )
        assert record.requirements == [
            "ISO9001认证",
            "近三年业绩≥2项",
            "独立法人资格",
        ]

    def test_requirements_list_passthrough(self):
        """requirements 列表原样保留（清洗空白项）。"""
        record = AnnouncementRecord.from_raw(
            {
                "bid_id": "T-3",
                "project_name": "某项目",
                "requirements": ["ISO9001 认证", "  ", "近三年业绩"],
            }
        )
        assert record.requirements == ["ISO9001 认证", "近三年业绩"]


# ----------------------------------------------------------------------
# 导出面：to_bid_row / fingerprint
# ----------------------------------------------------------------------

class TestExport:
    """导出面。"""

    def test_to_bid_row_saves_via_database(self, tmp_path):
        """to_bid_row 可直接走 save_bid 入库（幂等 upsert 兼容）。"""
        record = AnnouncementRecord.from_raw(
            {
                "招标编号": "E-1",
                "项目名称": "数据中心机房改造",
                "预算金额": "2,800万元",
                "发布日期": "2026年11月5日",
                "资格要求": "ISO27001;CCRC认证",
            }
        )
        with BidDatabase(tmp_path / "bids.db") as db:
            assert db.save_bid(record.to_bid_row()) == 1
            stored = db.get_bid("E-1")
        assert stored["project_name"] == "数据中心机房改造"
        assert stored["budget"] == 2800.0
        assert stored["publish_date"] == "2026-11-05"
        assert stored["requirements"] == ["ISO27001", "CCRC认证"]

    def test_fingerprint_stable_and_discriminating(self):
        """同件多源指纹一致；标题变化指纹变化。"""
        base = {"项目名称": "智慧园区平台", "发布日期": "2026-11-01", "地区": "浙江"}
        same_via_alias = dict(base, 招标编号="A-1")
        same_via_alias2 = dict(base, 招标编号="A-1-alternate-spelling")
        changed_title = dict(base, 项目名称="智慧园区平台二期", 招标编号="A-1")
        changed_date = dict(base, 发布日期="2026-11-02", 招标编号="A-1")

        fp1 = AnnouncementRecord.from_raw(same_via_alias).fingerprint()
        fp2 = AnnouncementRecord.from_raw(same_via_alias2).fingerprint()
        fp3 = AnnouncementRecord.from_raw(changed_title).fingerprint()
        fp4 = AnnouncementRecord.from_raw(changed_date).fingerprint()

        assert fp1 == fp2, "bid_id 不同拼写的同件公告应指纹一致"
        assert len(fp1) == 12
        assert fp1 != fp3
        assert fp1 != fp4

    def test_to_bid_row_does_not_leak_extras(self):
        """extras 不进 bids 行（表列固定）。"""
        record = AnnouncementRecord.from_raw(
            {
                "bid_id": "E-2",
                "project_name": "某项目",
                "开标地点": "第三开标室",
            }
        )
        row = record.to_bid_row()
        assert "开标地点" not in row
        assert row["bid_id"] == "E-2"
