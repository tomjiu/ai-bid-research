"""src/analyze.cooccurrence 领域词共现测试（#601 R50）。"""

from src.analyze import (
    AnalysisDataset,
    build_analysis_payload,
    render_analysis_markdown,
)
from src.analyze.cooccurrence import keyword_cooccurrence


def _ds(*names):
    return AnalysisDataset(
        records=[{"project_name": n} for n in names]
    )


class TestCooccurrence:
    def test_pair_counted_per_record(self):
        ds = _ds(
            "智慧城市大数据平台",
            "智慧城市与大数据底座",
            "智慧城市建设",
            "大数据中心",
        )
        out = keyword_cooccurrence(ds)
        pairs = {tuple(e["pair"]): e["count"] for e in out}
        # 智慧城市×大数据 共现 2 条
        # 词对按码点字典序（“大数据” < “智慧城市”）
        assert pairs[("大数据", "智慧城市")] == 2

    def test_min_count_filters_singleton(self):
        ds = _ds("智慧城市大数据", "智慧城市建设")
        out = keyword_cooccurrence(ds)
        pairs = [tuple(e["pair"]) for e in out]
        assert ("智慧城市", "大数据") not in pairs  # 只共现 1 次

    def test_requirements_text_matched(self):
        # 匹配面与 keywords 同口径：项目名 + 资格要求
        ds = AnalysisDataset(
            records=[
                {"project_name": "平台", "requirements": ["需具备等保资质", "含安防模块"]},
                {"project_name": "系统", "requirements": "等保与安防齐备"},
                {"project_name": "无关", "requirements": "无信号"},
            ]
        )
        out = keyword_cooccurrence(ds)
        pairs = {tuple(e["pair"]): e["count"] for e in out}
        assert pairs[("安防", "等保")] == 2

    def test_top_n_and_ordering_deterministic(self):
        ds = _ds(
            "智慧城市大数据",
            "智慧城市大数据",
            "智慧城市安防",
            "智慧城市安防",
            "智慧城市交通",
        )
        out = keyword_cooccurrence(ds, top_n=1)
        assert len(out) == 1
        # 计数并列时按词对名升序（安防 < 交通 都=2）
        ds2 = _ds("智慧城市安防", "智慧城市安防", "智慧城市交通", "智慧城市交通")
        out2 = keyword_cooccurrence(ds2)
        # 并列按词对名升序：“交通” < “安防”（码点序）
        assert [tuple(e["pair"]) for e in out2][:1] == [("交通", "智慧城市")]

    def test_sample_projects_capped_at_3(self):
        ds = _ds(*[f"智慧城市大数据{i}" for i in range(10)])
        out = keyword_cooccurrence(ds)
        assert out[0]["count"] == 10
        assert len(out[0]["sample_projects"]) == 3

    def test_empty_dataset(self):
        assert keyword_cooccurrence(AnalysisDataset(records=[])) == []


class TestReportSectionFourteen:
    def test_payload_and_markdown(self):
        ds = _ds("智慧城市大数据", "智慧城市大数据", "安防等保", "安防等保")
        md = render_analysis_markdown(build_analysis_payload(ds))
        assert "## 十四、领域词共现（同项目结伴出现）" in md
        assert "大数据 × 智慧城市" in md  # 码点字典序
        assert "共现 ≠ 因果" in md

    def test_section_omitted_without_pairs(self):
        md = render_analysis_markdown(build_analysis_payload(_ds("单项")))
        assert "十四、领域词共现" not in md
