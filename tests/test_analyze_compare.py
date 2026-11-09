"""领域对照面测试（#601 批次 F 第 28 轮）。"""

import pytest

import main as cli
from src.analyze import build_comparison_payload, render_comparison_markdown
from src.storage.database import BidDatabase


@pytest.fixture()
def db(tmp_path):
    """两个领域各有记录的库。"""
    path = tmp_path / "b.db"
    with BidDatabase(path) as conn:
        conn.import_bids(
            [
                {
                    "bid_id": f"C-{i}", "project_name": f"智慧城市项目{i}",
                    "budget": 100.0 * (i + 1),
                    "publish_date": f"2026-1{i % 2}-{(i % 27) + 1:02d}",
                    "region": "浙江", "winner": "甲" if i % 2 == 0 else None,
                }
                for i in range(4)
            ]
            + [
                {
                    "bid_id": f"W-{i}", "project_name": f"政务云扩容{i}",
                    "budget": 900.0,
                    "publish_date": f"2026-1{i % 2}-{(i % 27) + 1:02d}",
                    "region": "江苏", "purchaser": "某局", "winner": "乙",
                }
                for i in range(2)
            ]
        )
    return path


class TestComparisonPayload:
    """payload 构建面。"""

    def test_two_segments(self, db):
        """两领域 payload 各自独立且可对照。"""
        payload = build_comparison_payload(db, ["智慧城市", "政务云"])
        assert payload["keywords"] == ["智慧城市", "政务云"]
        seg_a = payload["segments"]["智慧城市"]
        seg_b = payload["segments"]["政务云"]
        assert seg_a["record_count"] == 4
        assert seg_b["record_count"] == 2
        assert seg_b["budget"]["median"] == 900.0
        # 完整度/质量面随行
        assert "field_quality" in seg_a

    def test_less_than_two_keywords_raises(self, db):
        """少于 2 个关键词 → ValueError。"""
        with pytest.raises(ValueError, match="至少需要 2 个"):
            build_comparison_payload(db, ["智慧城市"])
        with pytest.raises(ValueError, match="至少需要 2 个"):
            build_comparison_payload(db, ["  ", ""])

    def test_duplicate_keywords_raises(self, db):
        """重复关键词 → ValueError（对照无意义）。"""
        with pytest.raises(ValueError, match="不得重复"):
            build_comparison_payload(db, ["智慧城市", "智慧城市"])

    def test_empty_segment_still_included(self, db):
        """无命中领域照样进对照表（0 条是真实信号）。"""
        payload = build_comparison_payload(db, ["智慧城市", "无命中领域"])
        assert payload["segments"]["无命中领域"]["record_count"] == 0


class TestComparisonRender:
    """渲染面。"""

    def test_table_layout(self, db):
        """对照表：指标行 × 领域列并排。"""
        payload = build_comparison_payload(db, ["智慧城市", "政务云"])
        md = render_comparison_markdown(payload)
        assert "# 领域对照报告：智慧城市 vs 政务云" in md
        assert "| 指标 | 智慧城市 | 政务云 |" in md
        assert "预算中位(万)" in md
        assert "| 记录数 | 4 | 2 |" in md
        assert "| 密度层级 |" in md
        assert "各领域最缺字段" in md
        assert "口径说明" in md

    def test_empty_segment_renders_dashes(self, db):
        """无命中领域：指标格显示 ——（不猜数）。"""
        payload = build_comparison_payload(db, ["智慧城市", "无命中领域"])
        md = render_comparison_markdown(payload)
        assert "| 记录数 | 4 | 0 |" in md
        assert "——" in md  # 无预算/密度的格


class TestComparisonCLI:
    """CLI 面。"""

    def test_compare_flow(self, db, tmp_path, capsys):
        """--compare 双领域：报告落盘。"""
        code = cli.main(
            [
                "analyze", "--db", str(db),
                "--compare", "智慧城市,政务云",
                "--output-dir", str(tmp_path / "r"),
            ]
        )
        out = capsys.readouterr().out
        assert code == 0
        assert "对照报告已生成" in out
        reports = list((tmp_path / "r").glob("compare_智慧城市_vs_政务云_*.md"))
        assert len(reports) == 1
        content = reports[0].read_text(encoding="utf-8")
        assert "智慧城市 vs 政务云" in content

    def test_compare_single_keyword_exits_2(self, db, tmp_path, capsys):
        """单关键词 → 用法错误退出 2。"""
        code = cli.main(
            [
                "analyze", "--db", str(db),
                "--compare", "智慧城市",
                "--output-dir", str(tmp_path / "r"),
            ]
        )
        captured = capsys.readouterr()
        assert code == 2
        assert "至少需要 2 个" in captured.err
