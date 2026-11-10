"""src/analyze.suppliers 供应商画像测试（#601 R47）。

覆盖聚合口径（中标数/预算有值样本/买方去重/类别/活跃月）、
未定标不猜数、排序确定性、Top 上限。
"""

from src.analyze import AnalysisDataset
from src.analyze.suppliers import supplier_profiles


def _rows(*rows):
    return [dict(r) for r in rows]


class TestSupplierProfiles:
    def test_aggregation_fields(self):
        ds = AnalysisDataset(
            records=_rows(
                {
                    "winner": "甲公司",
                    "project_name": "A",
                    "budget": 100.0,
                    "category": "信息化",
                    "publish_date": "2026-01-05",
                    "purchaser": "大数据局",
                },
                {
                    "winner": "甲公司",
                    "project_name": "B",
                    "budget": 300.0,
                    "category": "安防",
                    "publish_date": "2026-03-10",
                    "purchaser": "政务办",
                },
                {
                    "winner": "甲公司",
                    "project_name": "C",
                    "budget": None,
                    "category": "信息化",
                    "publish_date": "2026-01-20",
                    "purchaser": "大数据局",
                },
            )
        )
        profiles = supplier_profiles(ds)
        assert len(profiles) == 1
        p = profiles[0]
        assert p["winner"] == "甲公司"
        assert p["award_count"] == 3
        # 预算只计有值样本（100+300，缺预算样本不计）
        assert p["budget_total"] == 400.0
        assert p["budget_mean"] == 200.0
        assert p["budget_sample_count"] == 2
        # 买方去重（出现序）
        assert p["purchasers"] == ["大数据局", "政务办"]
        assert p["purchaser_count"] == 2
        # 类别去重（出现序）
        assert p["categories"] == ["信息化", "安防"]
        # 活跃月升序
        assert p["active_months"] == ["2026-01", "2026-03"]

    def test_unawarded_records_excluded(self):
        """未定标/流标记录不属于任何供应商——不猜数。"""
        ds = AnalysisDataset(
            records=_rows(
                {"winner": "", "project_name": "流标A", "budget": 50.0},
                {"winner": None, "project_name": "未定标B"},
                {"winner": "  ", "project_name": "空白C"},
                {"winner": "乙公司", "project_name": "D", "budget": 80.0},
            )
        )
        profiles = supplier_profiles(ds)
        assert len(profiles) == 1
        assert profiles[0]["winner"] == "乙公司"
        assert profiles[0]["award_count"] == 1

    def test_all_missing_budget_stays_none(self):
        ds = AnalysisDataset(
            records=_rows(
                {"winner": "丙公司", "project_name": "X"},
                {"winner": "丙公司", "project_name": "Y", "budget": None},
            )
        )
        p = supplier_profiles(ds)[0]
        assert p["budget_total"] is None
        assert p["budget_mean"] is None
        assert p["budget_sample_count"] == 0

    def test_ordering_deterministic_and_top_n(self):
        ds = AnalysisDataset(
            records=_rows(
                *[
                    {"winner": w, "project_name": f"P{i}"}
                    for i, w in enumerate(
                        ["乙公司", "甲公司", "乙公司", "丙公司", "乙公司"]
                    )
                ]
            )
        )
        profiles = supplier_profiles(ds, top_n=2)
        # 中标数降序：乙(3) > 甲(1)=丙(1)，并列按名称
        assert [p["winner"] for p in profiles] == ["乙公司", "丙公司"]

    def test_empty_dataset(self):
        assert supplier_profiles(AnalysisDataset(records=[])) == []
