"""src/analyze.relationships 采购人-供应商关系测试（#601 R53）。"""

from src.analyze import (
    AnalysisDataset,
    build_analysis_payload,
    render_analysis_markdown,
)
from src.analyze.relationships import purchaser_supplier_pairs


def _rows(*rows):
    return [dict(r) for r in rows]


class TestPairs:
    def test_repeat_pair_aggregated(self):
        ds = AnalysisDataset(
            records=_rows(
                {"purchaser": "教育局", "winner": "甲公司", "budget": 10.0,
                 "publish_date": "2026-01-05"},
                {"purchaser": "教育局", "winner": "甲公司", "budget": 20.0,
                 "publish_date": "2026-03-01"},
                {"purchaser": "教育局", "winner": "乙公司", "budget": 5.0},
                {"purchaser": "公安局", "winner": "甲公司"},
            )
        )
        pairs = purchaser_supplier_pairs(ds)
        assert len(pairs) == 1  # 只有 教育局×甲 重复
        p = pairs[0]
        assert (p["purchaser"], p["winner"]) == ("教育局", "甲公司")
        assert p["repeat_count"] == 2
        assert p["budget_total"] == 30.0
        assert p["budget_sample_count"] == 2
        assert p["months"] == ["2026-01", "2026-03"]

    def test_one_side_missing_excluded(self):
        ds = AnalysisDataset(
            records=_rows(
                {"purchaser": "", "winner": "甲公司"},
                {"purchaser": "教育局", "winner": None},
            )
        )
        assert purchaser_supplier_pairs(ds) == []

    def test_min_repeat_respected(self):
        ds = AnalysisDataset(
            records=_rows(
                {"purchaser": "A局", "winner": "甲"},
                {"purchaser": "A局", "winner": "甲"},
                {"purchaser": "B局", "winner": "乙"},
            )
        )
        pairs = purchaser_supplier_pairs(ds, min_repeat=3)
        assert pairs == []  # 无 ≥3 次的对

    def test_ordering_and_top_n(self):
        ds = AnalysisDataset(
            records=_rows(
                *[{"purchaser": "A局", "winner": "甲"} for _ in range(3)],
                *[{"purchaser": "B局", "winner": "乙"} for _ in range(2)],
                *[{"purchaser": "C局", "winner": "丙"} for _ in range(2)],
            )
        )
        pairs = purchaser_supplier_pairs(ds, top_n=2)
        assert [(p["purchaser"], p["winner"]) for p in pairs] == [
            ("A局", "甲"),
            ("B局", "乙"),  # 并列 2 次，按对名升序 B < C
        ]


class TestReportWiring:
    def test_markdown_subsection(self):
        ds = AnalysisDataset(
            records=_rows(
                {"purchaser": "教育局", "winner": "甲公司", "budget": 10.0},
                {"purchaser": "教育局", "winner": "甲公司", "budget": 20.0},
            )
        )
        md = render_analysis_markdown(build_analysis_payload(ds))
        assert "### 重复合作关系（同采购人 × 同供应商 ≥ 2 次）" in md
        assert "合作信号" in md

    def test_subsection_omitted_without_pairs(self):
        ds = AnalysisDataset(
            records=_rows({"purchaser": "教育局", "winner": "甲公司"})
        )
        md = render_analysis_markdown(build_analysis_payload(ds))
        assert "重复合作关系" not in md
