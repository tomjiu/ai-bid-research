"""字段级质量评估测试（#601 批次 E 第 23 轮）。"""

import pytest

from src.analyze import AnalysisDataset
from src.analyze.quality import field_quality
from src.analyze.report_data import build_analysis_payload, render_analysis_markdown


def _ds(items):
    return AnalysisDataset(records=items)


class TestFieldQuality:
    """字段级填充率。"""

    def test_per_field_rates(self):
        """各字段独立计数：region 填 2/3、winner 填 1/3。"""
        ds = _ds(
            [
                {"bid_id": "Q-1", "project_name": "甲", "region": "浙江",
                 "winner": "某公司"},
                {"bid_id": "Q-2", "project_name": "乙", "region": "江苏"},
                {"bid_id": "Q-3", "project_name": "丙"},
            ]
        )
        q = field_quality(ds)
        assert q["records"] == 3
        assert q["fields"]["region"]["filled"] == 2
        assert q["fields"]["region"]["rate"] == pytest.approx(2 / 3)
        assert q["fields"]["winner"]["filled"] == 1
        # bid_id/project_name 全满 → 不进 most_missing
        assert "bid_id" not in q["most_missing"]
        assert "project_name" not in q["most_missing"]

    def test_most_missing_asc(self):
        """最缺字段清单：缺失率降序、至多 5 个。"""
        ds = _ds(
            [
                {"bid_id": "M-1", "project_name": "甲"},
            ] * 3
        )
        q = field_quality(ds)
        assert len(q["most_missing"]) == 5
        # 全部缺失率相同时按字段名排序（确定性）
        assert q["most_missing"] == sorted(q["most_missing"])

    def test_overall_is_mean(self):
        """overall = 各字段 rate 的均值。"""
        ds = _ds([{"bid_id": "O-1", "project_name": "甲", "region": "浙"}])
        q = field_quality(ds)
        rates = [f["rate"] for f in q["fields"].values()]
        assert q["overall"] == pytest.approx(sum(rates) / len(rates))

    def test_empty_dataset(self):
        """空集 → None/空清单（不猜数）。"""
        q = field_quality(AnalysisDataset())
        assert q["records"] == 0
        assert q["fields"] == {}
        assert q["overall"] is None
        assert q["most_missing"] == []

    def test_full_dataset_no_missing_list(self):
        """全字段填满 → most_missing 空（无行动面）。"""
        ds = _ds(
            [
                {
                    "bid_id": "F-1", "project_name": "甲", "region": "浙",
                    "budget": 1.0, "publish_date": "2026-01-01",
                    "deadline": "2026-02-01", "category": "服务",
                    "purchaser": "某局", "agency": "某代理",
                    "winner": "某公司", "source_url": "https://x",
                    "requirements": ["资质"],
                }
            ]
        )
        q = field_quality(ds)
        assert q["most_missing"] == []


class TestQualityInReport:
    """报告集成面。"""

    def test_report_has_quality_section(self):
        """报告渲染第七节：数据质量行动面。"""
        ds = _ds(
            [
                {"bid_id": "R-1", "project_name": "甲"},
                {"bid_id": "R-2", "project_name": "乙"},
            ]
        )
        payload = build_analysis_payload(ds)
        assert "field_quality" in payload
        md = render_analysis_markdown(payload)
        assert "## 七、数据质量" in md
        assert "系统性缺口" in md
        assert "整体字段填充率" in md

    def test_full_dataset_omits_quality_section(self):
        """无缺口 → 质量节不渲染（不输出空表）。"""
        ds = _ds(
            [
                {
                    "bid_id": "F-1", "project_name": "甲", "region": "浙",
                    "budget": 1.0, "publish_date": "2026-01-01",
                    "deadline": "2026-02-01", "category": "服务",
                    "purchaser": "某局", "agency": "某代理",
                    "winner": "某公司", "source_url": "https://x",
                    "requirements": ["资质"],
                }
            ]
        )
        md = render_analysis_markdown(build_analysis_payload(ds))
        assert "七、数据质量" not in md
