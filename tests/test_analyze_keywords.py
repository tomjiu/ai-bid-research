"""src/analyze.keywords 模块单元测试（#601 批次 C 第 12 轮）。"""

import pytest

from src.analyze import AnalysisDataset
from src.analyze.keywords import (
    DEFAULT_LEXICON,
    common_bigrams,
    keyword_frequency,
)


def _ds(items):
    return AnalysisDataset(records=items)


class TestKeywordFrequency:
    """词表匹配 + 预算关联。"""

    def test_match_count_and_budget(self):
        """命中计数 + 预算合计/均值（一词一项只计一次）。"""
        ds = _ds(
            [
                {"project_name": "智慧城市一期平台", "budget": 100.0},
                {"project_name": "智慧城市二期", "budget": 300.0},
                {"project_name": "某道路改造", "budget": None},
            ]
        )
        freq = keyword_frequency(ds)
        assert freq["智慧城市"]["count"] == 2
        assert freq["智慧城市"]["budget_total"] == pytest.approx(400.0)
        assert freq["智慧城市"]["budget_mean"] == pytest.approx(200.0)
        assert freq["改造"]["count"] == 1
        assert freq["改造"]["budget_total"] is None  # 该项无预算

    def test_requirements_text_matched(self):
        """资格要求文本也进匹配面。"""
        ds = _ds(
            [
                {
                    "project_name": "某项目",
                    "requirements": ["具备等保三级资质", "通过ISO9001"],
                }
            ]
        )
        freq = keyword_frequency(ds)
        assert freq["等保"]["count"] == 1

    def test_no_double_count_per_record(self):
        """同一项目命中同词多次只计一次（子串去重口径）。"""
        ds = _ds([{"project_name": "智慧城市中的智慧城市系统"}])
        freq = keyword_frequency(ds)
        assert freq["智慧城市"]["count"] == 1

    def test_sorted_by_count(self):
        """按 count 降序、平局按词序。"""
        ds = _ds(
            [
                {"project_name": "乙词项目"},
                {"project_name": "甲词项目"},
                {"project_name": "乙词再项目"},
            ]
        )
        freq = keyword_frequency(ds, lexicon=["甲词", "乙词"])
        assert list(freq.keys()) == ["乙词", "甲词"]

    def test_extra_terms_extend(self):
        """extra_terms 追加词（与词表并集）。"""
        ds = _ds([{"project_name": "卫星遥感监测项目"}])
        freq = keyword_frequency(ds, extra_terms=["遥感"])
        assert freq["遥感"]["count"] == 1
        # 内置词表仍生效
        assert freq.get("监测") is None  # 「监测」不在内置词表——仅 extra

    def test_replace_lexicon(self):
        """lexicon 完整替换（内置词不参与）。"""
        ds = _ds([{"project_name": "智慧城市遥感项目"}])
        freq = keyword_frequency(ds, lexicon=["遥感"])
        assert list(freq.keys()) == ["遥感"]

    def test_case_insensitive(self):
        """英文词大小写不敏感。"""
        ds = _ds([{"project_name": "GIS 地理信息系统"}])
        freq = keyword_frequency(ds, extra_terms=["gis"])
        assert freq["gis"]["count"] == 1

    def test_empty_dataset(self):
        """空集 → 空 dict。"""
        assert keyword_frequency(AnalysisDataset()) == {}


class TestCommonBigrams:
    """Bigram 发现模式。"""

    def test_discovery(self):
        """高频二元组浮现（词表没覆盖的领域词）。"""
        ds = _ds(
            [
                {"project_name": "低空经济平台建设"},
                {"project_name": "低空经济产业园"},
                {"project_name": "低空经济服务"},
            ]
        )
        grams = common_bigrams(ds, top=10)
        assert grams["低空"] == 3
        assert grams["空经"] == 3
        assert grams["经济"] == 3

    def test_stop_filtered(self):
        """助词/泛词被过滤。"""
        ds = _ds(
            [
                {"project_name": "的与项目"},
                {"project_name": "工程建设"},
            ]
        )
        grams = common_bigrams(ds)
        assert "的与" not in grams
        assert "项目" not in grams
        assert "工程" not in grams

    def test_top_limit(self):
        """top 截断条数。"""
        ds = _ds([{"project_name": "甲乙丙丁戊己庚辛"}])
        assert len(common_bigrams(ds, top=3)) == 3

    def test_empty(self):
        """空集/空名 → 空 dict。"""
        assert common_bigrams(AnalysisDataset()) == {}
        assert common_bigrams(_ds([{"project_name": ""}])) == {}


class TestLexiconContract:
    """词表契约。"""

    def test_default_lexicon_nonempty_unique(self):
        """内置词表非空且无重复。"""
        terms = list(DEFAULT_LEXICON)
        assert len(terms) > 20
        assert len(terms) == len(set(terms))
