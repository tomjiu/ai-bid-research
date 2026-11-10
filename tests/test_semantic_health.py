"""语义质量审计测试（#601 R81）。

四类「填了但可疑」：预算语义（负/零/超大/非数值）、日期逻辑
（发布>截止/未来/远古）、标识完整（bid_id/名称缺失）、标识唯一
（bid_id 重复——import 拼接源绕过库层 UNIQUE 的真实场景）。
"""

from __future__ import annotations

from src.analyze.dataset import AnalysisDataset
from src.analyze.quality import (
    render_semantic_health_markdown,
    semantic_health,
)


def _ds(records):
    return AnalysisDataset(records=records)


def _rec(**kw):
    base = {"bid_id": "Q-1", "project_name": "某项目"}
    base.update(kw)
    return base


class TestSemanticHealth:
    def test_clean_dataset_scores_100(self):
        payload = semantic_health(
            _ds(
                [
                    _rec(budget=100.0, publish_date="2026-01-10",
                         deadline="2026-02-01"),
                    _rec(bid_id="Q-2", budget=50.0,
                         publish_date="2026-03-01", deadline="2026-04-01"),
                ],
            ),
            today="2026-11-10",
        )
        assert payload["clean"] is True
        assert payload["health_score"] == 100
        assert payload["issues"] == {}

    def test_empty_dataset(self):
        payload = semantic_health(_ds([]))
        assert payload["records"] == 0
        assert payload["clean"] is True

    def test_negative_budget(self):
        payload = semantic_health(
            _ds([_rec(budget=-5.0)]), today="2026-11-10"
        )
        assert payload["issues"]["budget_negative"]["count"] == 1

    def test_zero_and_oversized_budget(self):
        payload = semantic_health(
            _ds(
                [
                    _rec(bid_id="Z-1", budget=0),
                    _rec(bid_id="Z-2", budget=600_000.0),  # 60 亿——疑单位错位
                ]
            ),
            today="2026-11-10",
        )
        assert payload["issues"]["budget_zero"]["count"] == 1
        assert payload["issues"]["budget_oversized"]["count"] == 1
        assert "单位错位" in payload["issues"]["budget_oversized"]["items"][0]["detail"]

    def test_non_numeric_budget(self):
        payload = semantic_health(
            _ds([_rec(budget="一百万元")]), today="2026-11-10"
        )
        assert payload["issues"]["budget_invalid"]["count"] == 1

    def test_publish_after_deadline(self):
        payload = semantic_health(
            _ds([_rec(publish_date="2026-05-01", deadline="2026-04-01")]),
            today="2026-11-10",
        )
        slot = payload["issues"]["publish_after_deadline"]
        assert slot["count"] == 1
        assert "2026-05-01 > 2026-04-01" in slot["items"][0]["detail"]

    def test_future_and_ancient_publish(self):
        payload = semantic_health(
            _ds(
                [
                    _rec(bid_id="F-1", publish_date="2030-01-01"),
                    _rec(bid_id="A-1", publish_date="2013-06-01"),
                ]
            ),
            today="2026-11-10",
        )
        assert payload["issues"]["future_publish"]["count"] == 1
        assert payload["issues"]["ancient_publish"]["count"] == 1

    def test_missing_ids_and_names(self):
        payload = semantic_health(
            _ds(
                [
                    _rec(bid_id="", project_name="无名之辈"),
                    _rec(bid_id="M-2", project_name="  "),
                ]
            ),
            today="2026-11-10",
        )
        assert payload["issues"]["missing_bid_id"]["count"] == 1
        assert payload["issues"]["missing_project_name"]["count"] == 1

    def test_duplicate_bid_ids_count_repeats(self):
        payload = semantic_health(
            _ds(
                [
                    _rec(bid_id="DUP"),
                    _rec(bid_id="DUP", project_name="第二份"),
                    _rec(bid_id="DUP", project_name="第三份"),
                ]
            ),
            today="2026-11-10",
        )
        slot = payload["issues"]["duplicate_bid_id"]
        assert slot["count"] == 2  # 重复份数（首份合法）
        assert slot["items"][0]["detail"] == "3 次"

    def test_detail_limit_five_but_count_full(self):
        records = [
            _rec(bid_id=f"F{i:02d}", budget=-1.0) for i in range(8)
        ]
        payload = semantic_health(_ds(records), today="2026-11-10")
        slot = payload["issues"]["budget_negative"]
        assert slot["count"] == 8
        assert len(slot["items"]) == 5  # 明细截断、计数全量

    def test_score_penalized_but_floored_at_zero(self):
        # 全坏数据：分数被压向 0 但不为负
        records = [
            _rec(bid_id="", project_name="", budget=-1.0,
                 publish_date="2030-01-01")
            for _ in range(10)
        ]
        payload = semantic_health(_ds(records), today="2026-11-10")
        assert 0 <= payload["health_score"] < 100
        assert payload["clean"] is False

    def test_today_defaults_to_dataset_generated_at(self):
        # 不传 today → 用数据集生成时刻（防未来日期误判）
        ds = _ds([_rec(publish_date="2026-11-10")])
        ds.generated_at = "2026-11-10 08:00:00"
        payload = semantic_health(ds)
        assert "future_publish" not in payload["issues"]


class TestRenderMarkdown:
    def test_clean_copy(self):
        md = render_semantic_health_markdown(
            {"records": 5, "issues": {}, "health_score": 100, "clean": True}
        )
        assert "无异常" in md

    def test_issues_table_sorted_by_count(self):
        md = render_semantic_health_markdown(
            {
                "records": 10,
                "issues": {
                    "budget_zero": {"count": 1, "items": [{"ref": "Z"}]},
                    "missing_bid_id": {"count": 4, "items": [{"ref": "M"}]},
                },
                "health_score": 80,
                "clean": False,
            }
        )
        # 计数多的行在前
        assert md.index("bid_id 缺失") < md.index("零预算")
        assert "80/100" in md
        assert "误作" in md  # 单位错位阈值脚注

    def test_ordinal_in_title(self):
        md = render_semantic_health_markdown(
            {"records": 0, "issues": {}, "health_score": 100, "clean": True},
            ordinal="十七",
        )
        assert "## 十七、语义质量审计" in md

    def test_empty_copy(self):
        md = render_semantic_health_markdown({"records": 0})
        assert "无可审计内容" in md
