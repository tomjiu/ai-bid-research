"""R43 递归目录源测试——嵌套遍历/链接环/路径键去重三面。"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

from src.collect.sources import (
    SourceError,
    load_records,
    resolve_source_files,
)


def _write_jsonl(path: Path, bid_id: str) -> None:
    path.write_text(
        json.dumps(
            {
                "bid_id": bid_id,
                "project_name": f"项目{bid_id}",
                "publish_date": "2026-01-10",
            }
        )
        + "\n",
        encoding="utf-8",
    )


class TestRecursiveWalk:
    def test_nested_dirs_collected_sorted(self, tmp_path):
        (tmp_path / "beta").mkdir()
        (tmp_path / "alpha" / "deep").mkdir(parents=True)
        _write_jsonl(tmp_path / "root.jsonl", "R1")
        _write_jsonl(tmp_path / "alpha" / "a.jsonl", "A1")
        _write_jsonl(tmp_path / "alpha" / "deep" / "d.jsonl", "D1")
        _write_jsonl(tmp_path / "beta" / "b.jsonl", "B1")
        (tmp_path / "alpha" / "notes.txt").write_text("ignore")

        files = resolve_source_files(tmp_path, recursive=True)
        rels = [str(f.relative_to(tmp_path)).replace(os.sep, "/") for f in files]
        assert rels == [
            "alpha/a.jsonl",
            "alpha/deep/d.jsonl",
            "beta/b.jsonl",
            "root.jsonl",
        ]

    def test_non_recursive_stays_flat(self, tmp_path):
        (tmp_path / "sub").mkdir()
        _write_jsonl(tmp_path / "x.jsonl", "X1")
        _write_jsonl(tmp_path / "sub" / "y.jsonl", "Y1")
        files = resolve_source_files(tmp_path)
        assert [f.name for f in files] == ["x.jsonl"]

    def test_recursive_no_sources_raises(self, tmp_path):
        (tmp_path / "only" / "txt").mkdir(parents=True)
        (tmp_path / "only" / "txt" / "a.txt").write_text("x")
        with pytest.raises(SourceError, match="含子目录"):
            resolve_source_files(tmp_path, recursive=True)

    def test_symlink_loop_terminated(self, tmp_path):
        """符号链接环——真实 Linux 场景：walk 不得无限递归。"""
        _write_jsonl(tmp_path / "real.jsonl", "L1")
        # 自引用环：loop -> tmp_path
        os.symlink(tmp_path, tmp_path / "loop")
        files = resolve_source_files(tmp_path, recursive=True)
        names = [f.name for f in files]
        assert names.count("real.jsonl") == 1  # 环不产生重复读取

    def test_load_records_recursive_end_to_end(self, tmp_path):
        (tmp_path / "in" / "2026").mkdir(parents=True)
        _write_jsonl(tmp_path / "in" / "2026" / "a.jsonl", "E1")
        _write_jsonl(tmp_path / "in" / "b.jsonl", "E2")
        result = load_records(tmp_path / "in", recursive=True)
        assert result.files_read == 2
        assert {r.bid_id for r in result.records} == {"E1", "E2"}

    def test_cli_collect_recursive_flag(self, tmp_path, monkeypatch, capsys):
        """CLI 接线：--recursive 真正透传到装载面。"""
        import main as main_mod

        captured = {}

        def fake_load(source, *, skip_invalid=True, since=None, today=None,
                      recursive=False):
            captured["recursive"] = recursive

            class _R:  # 极简装载结果替身
                files_read = 0
                records = []
                failures = []

            return _R()

        monkeypatch.setattr(main_mod, "load_records", fake_load)

        class _Dedup:  # 去重结果替身
            removed = 0
            by_bid_id = 0
            by_source_url = 0
            by_fingerprint = 0
            unique = []
            duplicates = []

        monkeypatch.setattr(main_mod, "dedupe_records", lambda recs: _Dedup())
        rc = main_mod.main(
            [
                "collect",
                "--source",
                str(tmp_path),
                "--recursive",
                "--dry-run",
            ]
        )
        assert rc == 0
        assert captured["recursive"] is True


class TestWindowsCaseFold:
    def test_case_fold_dedup_on_windows(self, tmp_path, monkeypatch):
        """Windows 分支：大小写不同的目录键折叠为同键。

        通过替换 os.walk 模拟大小写不敏感卷上的重复目录入口
        （真实 Windows 上 Data/ 与 data/ 是同一目录）。
        """
        monkeypatch.setattr(sys, "platform", "win32")
        (tmp_path / "Data").mkdir()
        _write_jsonl(tmp_path / "Data" / "a.jsonl", "W1")

        def doubled_walk(top, topdown=True, **kw):
            # 模拟不敏感卷：同一目录以两种大小写出现
            yield str(top), ["Data"], []
            yield str(top) + "/Data", [], ["a.jsonl"]
            yield str(top) + "/data", [], ["a.jsonl"]

        monkeypatch.setattr(os, "walk", doubled_walk)
        files = resolve_source_files(tmp_path, recursive=True)
        assert len(files) == 1  # Data 与 data 折叠，只读一次

    def test_case_sensitive_linux_keeps_both(self, tmp_path, monkeypatch):
        monkeypatch.setattr(sys, "platform", "linux")

        def doubled_walk(top, topdown=True, **kw):
            yield str(top), ["Data", "data"], []

        monkeypatch.setattr(os, "walk", doubled_walk)
        # Linux 上两个大小写不同的目录键不同——walk 各自下钻
        from src.platform import normalize_path_key

        assert normalize_path_key("/x/Data") != normalize_path_key("/x/data")
