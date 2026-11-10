"""src/analyze.regions 省级归一测试（#601 R51）。"""

import pytest

from src.analyze import (
    AnalysisDataset,
    build_analysis_payload,
    render_analysis_markdown,
)
from src.analyze.regions import parse_region, province_distribution


class TestParseRegion:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("浙江省杭州市", {"province": "浙江省", "city": "杭州市"}),
            ("浙江省", {"province": "浙江省", "city": None}),
            ("黑龙江省哈尔滨市", {"province": "黑龙江省", "city": "哈尔滨市"}),
            ("北京市海淀区", {"province": "北京市", "city": "北京市"}),
            ("上海", {"province": "上海市", "city": "上海市"}),  # 简称
            ("内蒙古自治区呼和浩特市", {"province": "内蒙古自治区", "city": "呼和浩特市"}),
            ("新疆维吾尔自治区", {"province": "新疆维吾尔自治区", "city": None}),
            ("广西南宁市", {"province": "广西壮族自治区", "city": "南宁市"}),
            ("香港特别行政区", {"province": "香港特别行政区", "city": None}),
        ],
    )
    def test_patterns(self, raw, expected):
        assert parse_region(raw) == expected

    @pytest.mark.parametrize("raw", ["", "  ", "杭州", "华北地区", "境外"])
    def test_unresolvable_returns_none(self, raw):
        assert parse_region(raw) is None


class TestProvinceDistribution:
    def test_mixed_granularity_folded(self):
        ds = AnalysisDataset(
            records=[
                {"region": "浙江省杭州市"},
                {"region": "浙江省"},
                {"region": "浙江省嘉兴市"},
                {"region": "江苏省南京市"},
                {"region": "杭州市西湖区"},  # 裸市名——无法定位
                {"region": ""},
            ]
        )
        out = province_distribution(ds)
        assert out["distribution"] == {"浙江省": 3, "江苏省": 1}
        assert out["parsed_count"] == 4
        assert out["unknown_count"] == 2

    def test_ordering_desc_then_name(self):
        ds = AnalysisDataset(
            records=[
                {"region": "江苏省"},
                {"region": "安徽省"},
                {"region": "江苏省"},
            ]
        )
        out = province_distribution(ds)
        assert list(out["distribution"]) == ["江苏省", "安徽省"]


class TestReportSectionFifteen:
    def test_payload_and_markdown(self):
        ds = AnalysisDataset(
            records=[
                {"region": "浙江省杭州市"},
                {"region": "浙江省"},
                {"region": "广东省深圳市"},
            ]
        )
        md = render_analysis_markdown(build_analysis_payload(ds))
        assert "## 十五、省级归一分布（混杂口径折叠）" in md
        assert "浙江省" in md
        assert "不猜数" in md

    def test_section_omitted_when_no_province_signal(self):
        ds = AnalysisDataset(records=[{"region": "杭州"}])
        md = render_analysis_markdown(build_analysis_payload(ds))
        assert "十五、省级归一分布" not in md
