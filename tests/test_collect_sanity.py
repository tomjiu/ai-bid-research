"""src/collect.sanity 健全性规则测试（#601 R33）。

覆盖四规则（倒挂/长窗口/未来发布/零预算）、today 注入确定性、
纯函数与就地扩展两面，以及 load_records 全链接线。
"""

import pytest

from src.collect import AnnouncementRecord, load_records
from src.collect.sanity import (
    apply_sanity_checks,
    sanity_warnings,
)


def _record(**overrides) -> AnnouncementRecord:
    """构造基准记录（默认无任何告警命中）。"""
    base = {
        "bid_id": "S-1",
        "project_name": "某项目",
        "publish_date": "2026-01-10",
        "deadline": "2026-02-10",
        "budget": 100.0,
    }
    base.update(overrides)
    return AnnouncementRecord(**base)


class TestSanityRules:
    """四规则独立命中面。"""

    def test_clean_record_no_warnings(self):
        """干净记录：零告警。"""
        assert sanity_warnings(_record(), today="2026-06-01") == []

    def test_date_inversion(self):
        """规则 1：发布晚于截止 → 倒挂告警。"""
        record = _record(publish_date="2026-03-01", deadline="2026-02-10")
        warnings = sanity_warnings(record, today="2026-06-01")
        assert len(warnings) == 1
        assert "日期倒挂" in warnings[0]

    def test_long_window(self):
        """规则 2：窗口超过 365 天 → 可疑长周期。"""
        record = _record(publish_date="2026-01-01", deadline="2027-03-01")
        warnings = sanity_warnings(record, today="2026-06-01")
        assert len(warnings) == 1
        assert "可疑长周期" in warnings[0]

    def test_window_boundary_exact_365_no_warning(self):
        """边界：恰好 365 天不告警（超过才告警）。"""
        record = _record(publish_date="2026-01-01", deadline="2027-01-01")
        assert sanity_warnings(record, today="2026-06-01") == []

    def test_future_publish_date(self):
        """规则 3：发布日期在未来 → 告警（today 注入保证确定性）。"""
        record = _record(publish_date="2026-05-01", deadline="2026-06-01")
        warnings = sanity_warnings(record, today="2026-04-01")
        assert len(warnings) == 1
        assert "发布日期在未来" in warnings[0]

    def test_zero_budget(self):
        """规则 4：预算为 0 → 告警；None/正数不告警。"""
        zero_warnings = sanity_warnings(_record(budget=0), today="2026-06-01")
        assert any("预算为 0" in w for w in zero_warnings)
        assert sanity_warnings(_record(budget=None), today="2026-06-01") == []
        assert sanity_warnings(_record(budget=0.5), today="2026-06-01") == []

    def test_multiple_rules_can_stack(self):
        """多规则可同时命中（倒挂 + 零预算）。"""
        record = _record(
            publish_date="2026-03-01", deadline="2026-02-10", budget=0
        )
        warnings = sanity_warnings(record, today="2026-06-01")
        assert len(warnings) == 2

    def test_missing_dates_skip_rules(self):
        """日期缺失：相关规则跳过（不猜数）。"""
        record = _record(publish_date=None, deadline=None)
        assert sanity_warnings(record, today="2026-06-01") == []


class TestTodayInjection:
    """today 基准注入面。"""

    def test_today_as_date_object(self):
        from datetime import date

        record = _record(publish_date="2026-05-01", deadline="2026-06-01")
        assert sanity_warnings(record, today=date(2026, 4, 1))

    def test_bad_today_string_rejected(self):
        with pytest.raises(ValueError, match="today"):
            sanity_warnings(_record(), today="2026/4/1")

    def test_today_none_uses_system_date(self):
        """today=None → 系统当前日期（冒烟：不抛即过）。"""
        sanity_warnings(_record())


class TestApplyAndWiring:
    """就地扩展与全链接线。"""

    def test_sanity_warnings_is_pure(self):
        """纯函数：不修改记录。"""
        record = _record(budget=0)
        before = list(record.warnings)
        sanity_warnings(record, today="2026-06-01")
        assert record.warnings == before

    def test_apply_extends_record_warnings(self):
        """apply_sanity_checks：就地扩展并返回新增告警。"""
        record = _record(budget=0)
        added = apply_sanity_checks(record, today="2026-06-01")
        assert added == record.warnings
        assert len(added) == 1

    def test_load_records_applies_sanity(self, tmp_path):
        """全链接线：load_records 产出记录自带健全性告警。"""
        path = tmp_path / "src.json"
        path.write_text(
            "[{"
            '"bid_id": "W-1", "project_name": "某项目",'
            '"publish_date": "2026-03-01", "deadline": "2026-02-10",'
            '"budget": 100'
            "}]",
            encoding="utf-8",
        )
        result = load_records(path, today="2026-06-01")
        assert result.failures == []
        assert any("日期倒挂" in w for w in result.records[0].warnings)

    def test_load_records_clean_record_stays_clean(self, tmp_path):
        """全链接线：干净记录 warnings 仍为空。"""
        path = tmp_path / "clean.json"
        path.write_text(
            '[{"bid_id": "W-2", "project_name": "某项目",'
            '"publish_date": "2026-01-10", "deadline": "2026-02-10",'
            '"budget": 100}]',
            encoding="utf-8",
        )
        result = load_records(path, today="2026-06-01")
        assert result.records[0].warnings == []
