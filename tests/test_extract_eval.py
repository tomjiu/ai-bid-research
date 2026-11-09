"""src/extract 质量评估测试（#601 批次 E·R22）。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.extract.engine import RuleExtractor
from src.extract.eval import (
    EvalReport,
    _field_matches,
    evaluate_extractor,
    load_gold,
)

FIXTURES = Path(__file__).parent.parent / "fixtures" / "announcements"
GOLD_PATH = FIXTURES / "gold-extraction.json"
RAW_DIR = FIXTURES / "raw"


def load_fixture_texts() -> dict:
    return {
        path.name: path.read_text(encoding="utf-8")
        for path in sorted(RAW_DIR.glob("*.txt"))
    }


# ----------------------------------------------------------------------
# 比对语义单元
# ----------------------------------------------------------------------


class TestFieldMatches:
    def test_exact_fields(self):
        assert _field_matches("bid_id", "X-1", "X-1")
        assert _field_matches("bid_id", "X-1", " X-1 ")
        assert not _field_matches("bid_id", "X-1", "X-2")
        assert _field_matches("publish_date", "2026-01-01", "2026-01-01")
        assert _field_matches("category", "服务", "服务")

    def test_budget_float(self):
        assert _field_matches("budget", 1200, 1200.0)
        assert _field_matches("budget", "1200", 1200.0)
        assert not _field_matches("budget", 1200, 1201.0)

    def test_contains_fields(self):
        assert _field_matches("project_name", "智慧城市", "某某市智慧城市一期项目")
        assert not _field_matches("project_name", "智慧城市", "数据中心项目")
        assert _field_matches("region", "杭州", "浙江省杭州市")

    def test_requirements_keywords(self):
        assert _field_matches(
            "requirements",
            ["ISO9001", "业绩"],
            ["具备 ISO9001 认证", "近三年业绩 2 项"],
        )
        assert not _field_matches(
            "requirements", ["ISO9001"], ["近三年业绩 2 项"]
        )

    def test_none_semantics(self):
        assert _field_matches("region", None, None)
        assert not _field_matches("region", None, "北京市")
        assert not _field_matches("region", "北京市", None)


# ----------------------------------------------------------------------
# gold 装载
# ----------------------------------------------------------------------


class TestLoadGold:
    def test_load_fixture_gold(self):
        gold = load_gold(GOLD_PATH)
        assert set(gold) == {"hlj-smartcity.txt", "zj-cloud.txt", "noise.txt"}
        assert gold["noise.txt"]["ok"] is False
        assert gold["hlj-smartcity.txt"]["fields"]["bid_id"] == "HLJ-SYN-2026-001"

    def test_bad_shape_raises(self, tmp_path):
        bad = tmp_path / "bad.json"
        bad.write_text('["not", "object"]', encoding="utf-8")
        with pytest.raises(ValueError, match="对象"):
            load_gold(bad)

    def test_missing_ok_key_raises(self, tmp_path):
        bad = tmp_path / "bad.json"
        bad.write_text('{"case": {"fields": {}}}', encoding="utf-8")
        with pytest.raises(ValueError, match="ok"):
            load_gold(bad)


# ----------------------------------------------------------------------
# 评估器
# ----------------------------------------------------------------------


class TestEvaluateExtractor:
    def test_rule_extractor_on_fixture_gold(self):
        """规则基线在合成 gold 上的命中率（基线登记面）。"""
        gold = load_gold(GOLD_PATH)
        texts = load_fixture_texts()
        report = evaluate_extractor(RuleExtractor(), gold, texts)
        # 三个用例的成败预期全对上
        assert all(
            c.expected_ok == c.actual_ok for c in report.cases
        )
        assert report.failure_mismatches == []
        # 基线命中率 ≥ 80%（当前实测 100%——低于阈值说明规则退化）
        assert report.overall_hit_rate >= 0.8
        assert report.total_fields == 14  # 10（hlj）+ 4（zj-cloud）

    def test_report_field_rates(self):
        gold = load_gold(GOLD_PATH)
        report = evaluate_extractor(
            RuleExtractor(), gold, load_fixture_texts()
        )
        rates = report.field_hit_rates()
        assert "bid_id" in rates
        assert rates["bid_id"]["total"] == 2  # 两用例标注了 bid_id
        assert rates["bid_id"]["hits"] == 2

    def test_missing_text_case(self):
        """语料缺失的 gold 用例：actual_ok=False 空评估（不炸）。"""
        gold = {"ghost.txt": {"ok": True, "fields": {"bid_id": "G-1"}}}
        report = evaluate_extractor(RuleExtractor(), gold, {})
        case = report.cases[0]
        assert case.actual_ok is False
        assert case.verdict_ok is False
        assert report.overall_hit_rate is None  # 零标注分母

    def test_expected_failure_case(self):
        """预期失败的用例（noise）：抽取也失败 → verdict_ok。"""
        gold = {"noise.txt": {"ok": False, "fields": {}}}
        texts = {"noise.txt": "普通文本无结构"}
        report = evaluate_extractor(RuleExtractor(), gold, texts)
        assert report.cases[0].verdict_ok is True

    def test_summary_format(self):
        gold = load_gold(GOLD_PATH)
        report = evaluate_extractor(
            RuleExtractor(), gold, load_fixture_texts()
        )
        summary = report.format_summary()
        assert "抽取质量评估" in summary
        assert "字段命中率" in summary
        assert "bid_id: 2/2" in summary


# ----------------------------------------------------------------------
# 报告模型
# ----------------------------------------------------------------------


def test_eval_report_empty():
    report = EvalReport()
    assert report.overall_hit_rate is None
    assert report.total_fields == 0
    assert report.field_hit_rates() == {}
    assert report.format_summary().startswith("抽取质量评估")
