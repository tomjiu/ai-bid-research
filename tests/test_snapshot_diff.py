"""研究快照对比测试（#601 R60）。"""

from __future__ import annotations

import json

import main as main_mod
from src.storage.snapshot_diff import diff_snapshots, render_diff_summary


def _row(bid_id, **kw):
    return {"bid_id": bid_id, "project_name": "项目", **kw}


class TestDiffSnapshots:
    def test_added_removed_changed_unchanged(self):
        old = [
            _row("B-1", budget=100.0, winner=None),
            _row("B-2", budget=200.0),
            _row("B-3"),  # 将被移除
            _row("B-4"),  # 不变
        ]
        new = [
            _row("B-1", budget=100.0, winner="甲公司"),  # winner 变更
            _row("B-2", budget=200.0),  # 不变
            _row("B-5"),  # 新增
            _row("B-4"),  # 不变
        ]
        d = diff_snapshots(old, new)
        assert d["old_count"] == 4 and d["new_count"] == 4
        assert d["added"] == ["B-5"]
        assert d["removed"] == ["B-3"]
        assert set(d["changed"]) == {"B-1"}
        assert d["changed"]["B-1"]["winner"] == {"old": None, "new": "甲公司"}
        assert d["unchanged_count"] == 2
        assert d["skipped"] == 0

    def test_missing_bid_id_skipped_honestly(self):
        old = [{"project_name": "无身份"}, _row("B-1")]
        new = [_row("B-1"), {"bid_id": ""}, {"bid_id": "B-1"}]  # 空 id + 重复
        d = diff_snapshots(old, new)
        assert d["skipped"] == 3
        assert d["old_count"] == 1 and d["new_count"] == 1
        assert d["unchanged_count"] == 1

    def test_requirements_form_normalized(self):
        """requirements 列表 vs JSON 字符串 = 同形态，不算变更。"""
        old = [_row("B-1", requirements=["A", "B"])]
        new = [_row("B-1", requirements='["A", "B"]')]
        d = diff_snapshots(old, new)
        assert d["changed"] == {}
        assert d["unchanged_count"] == 1

    def test_none_and_empty_string_equivalent(self):
        old = [_row("B-1", region=None)]
        new = [{"bid_id": "B-1", "project_name": "项目", "region": ""}]
        d = diff_snapshots(old, new)
        assert d["changed"] == {}

    def test_empty_snapshots(self):
        d = diff_snapshots([], [])
        assert d["old_count"] == 0
        assert d["added"] == [] and d["removed"] == []
        assert d["changed"] == {}


class TestRenderSummary:
    def test_summary_lines(self):
        d = diff_snapshots(
            [_row("B-1", budget=1.0), _row("B-9")],
            [_row("B-1", budget=2.0), _row("B-2")],
        )
        text = render_diff_summary(d)
        assert "新增 1 条" in text
        assert "移除 1 条" in text
        assert "变更 1 条，不变 0 条" in text
        assert "B-1: budget: 1.0 → 2.0" in text

    def test_long_values_truncated(self):
        d = diff_snapshots(
            [_row("B-1", project_name="短")],
            [_row("B-1", project_name="超" * 60)],
        )
        text = render_diff_summary(d)
        assert "…" in text

    def test_verbose_expands_all(self):
        rows_old = [_row(f"B-{i}") for i in range(15)]
        rows_new = [_row(f"B-{i}", budget=float(i)) for i in range(15)]
        d = diff_snapshots(rows_old, rows_new)
        compact = render_diff_summary(d)
        verbose = render_diff_summary(d, verbose=True)
        assert "另有 5 条" in compact
        assert "另有" not in verbose
        assert verbose.count("budget") == 15


class TestCliDiff:
    def _snapshot(self, path, rows):
        path.write_text(
            json.dumps(rows, ensure_ascii=False), encoding="utf-8"
        )
        return path

    def test_cli_diff_end_to_end(self, tmp_path, capsys):
        old = self._snapshot(
            tmp_path / "old.json",
            [_row("B-1", budget=100.0), _row("B-2")],
        )
        new = self._snapshot(
            tmp_path / "new.json",
            [_row("B-1", budget=120.0), _row("B-3")],
        )
        out = tmp_path / "diff.json"
        rc = main_mod.main(
            ["db", "--diff", str(old), str(new), "--out", str(out)]
        )
        assert rc == 0
        text = capsys.readouterr().out
        assert "快照对比：旧 2 条 vs 新 2 条" in text
        assert "B-1: budget: 100.0 → 120.0" in text
        payload = json.loads(out.read_text(encoding="utf-8"))
        assert payload["added"] == ["B-3"]
        assert payload["removed"] == ["B-2"]
        assert b"\r" not in out.read_bytes()  # LF 契约

    def test_cli_diff_missing_file_actionable(self, tmp_path, capsys):
        rc = main_mod.main(
            ["db", "--diff", str(tmp_path / "nope.json"),
             str(tmp_path / "nope2.json")]
        )
        assert rc == 2
        assert "不存在" in capsys.readouterr().err

    def test_cli_diff_rejects_non_array(self, tmp_path, capsys):
        p1 = tmp_path / "a.json"
        p2 = tmp_path / "b.json"
        p1.write_text('{"bid_id": "x"}', encoding="utf-8")
        p2.write_text("[]", encoding="utf-8")
        rc = main_mod.main(["db", "--diff", str(p1), str(p2)])
        assert rc == 2
        assert "JSON 数组" in capsys.readouterr().err
