"""批量写事务测试（#601 R62）——原子性/commit 合并/N+1 消除。"""

from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from src.storage.database import BidDatabase


def _row(bid_id, name=None):
    return {"bid_id": bid_id, "project_name": name or f"项目{bid_id}"}


class TestTransactionSemantics:
    def test_import_bids_atomic_rollback(self, tmp_path):
        """批内任一失败 → 整体回滚（部分落盘语义废止）。"""
        db = BidDatabase(tmp_path / "a.db")
        try:
            db.import_bids([_row("OK-1")])  # 既有状态
            with pytest.raises(KeyError):
                db.import_bids(
                    [
                        _row("B-1"),
                        {"bid_id": "BAD", "project_name": ""},  # 必填缺失
                        _row("B-2"),
                    ]
                )
            # 坏批一行都没落（B-1/B-2 不可见）
            assert db.get_bid("B-1") is None
            assert db.get_bid("B-2") is None
            assert db.get_bid("OK-1") is not None  # 既有状态未受牵连
        finally:
            db.close()

    def test_single_commit_for_batch(self, tmp_path):
        """100 行导入 = 1 次 commit（而非 100 次——fsync 契约）。

        计数面：``set_trace_callback``（sqlite3 官方 API——
        Connection.commit 属性只读，不可 patch）。
        """
        db = BidDatabase(tmp_path / "c.db")
        try:
            commits = []
            db._conn.set_trace_callback(
                lambda stmt: commits.append(stmt)
                if stmt.strip().upper().startswith("COMMIT")
                else None
            )
            db.import_bids([_row(f"B-{i}") for i in range(100)])
            assert len(commits) == 1
            assert db.count_bids() == 100
        finally:
            db.close()

    def test_nested_transaction_joins_outer(self, tmp_path):
        db = BidDatabase(tmp_path / "n.db")
        try:
            with db.transaction():
                with db.transaction():
                    db.save_bid(_row("N-1"))
                # 内层收口不 commit（深度归零才提交）
                assert db._tx_depth == 1
            assert db.get_bid("N-1") is not None
        finally:
            db.close()

    def test_exception_rolls_back_nested(self, tmp_path):
        db = BidDatabase(tmp_path / "r.db")
        try:
            with pytest.raises(RuntimeError):
                with db.transaction():
                    db.save_bid(_row("R-1"))
                    raise RuntimeError("块内失败")
            assert db.get_bid("R-1") is None
        finally:
            db.close()

    def test_autocommit_mode_unchanged(self, tmp_path):
        """非事务路径（单条 save_bid）保持逐次提交——历史行为。"""
        db = BidDatabase(tmp_path / "s.db")
        try:
            db.save_bid(_row("S-1"))
            # 无事务包裹也真实落盘（重开连接可见）
            db.close()
            db2 = BidDatabase(tmp_path / "s.db")
            try:
                assert db2.get_bid("S-1") is not None
            finally:
                db2.close()
        finally:
            try:
                db.close()
            except Exception:
                pass

    def test_all_bid_ids(self, tmp_path):
        db = BidDatabase(tmp_path / "ids.db")
        try:
            db.import_bids([_row("X-1"), _row("X-2")])
            assert db.all_bid_ids() == {"X-1", "X-2"}
        finally:
            db.close()


class TestPipelineCollectBatched:
    def test_pipeline_collect_functional_and_fast(self, tmp_path):
        """500 条源单事务入库（功能性 + 事务面真激活）。"""
        from src.pipeline import ResearchPipeline

        src = tmp_path / "ann"
        src.mkdir()
        (src / "big.json").write_text(
            json.dumps(
                [
                    {"bid_id": f"P-{i}", "project_name": f"项目{i}"}
                    for i in range(500)
                ],
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        db_path = tmp_path / "b.db"

        # spy：collect 阶段的 commit 次数应远小于记录数
        # （Connection.commit 只读——经 runner 符号注入 trace 工厂）
        import src.pipeline.runner as runner_mod

        real_cls = runner_mod.BidDatabase
        commit_count = {"n": 0}

        def tracing_factory(*a, **kw):
            db = real_cls(*a, **kw)
            db._conn.set_trace_callback(
                lambda stmt: commit_count.__setitem__(
                    "n", commit_count["n"] + 1
                )
                if stmt.strip().upper().startswith("COMMIT")
                else None
            )
            return db

        with patch.object(runner_mod, "BidDatabase", tracing_factory):
            pipeline = ResearchPipeline(
                db_path, output_dir=tmp_path / "out"
            )
            result = pipeline.run(src)
        collect = result.stage("collect")
        assert collect.detail["new"] == 500
        # 建库/PRAGMA/迁移等固有 commit 之外，500 行只贡献 1 次
        assert commit_count["n"] < 10, commit_count["n"]

        db = BidDatabase(db_path)
        try:
            assert db.count_bids() == 500
            # 全部标 raw（待抽取）
            assert len(db.list_by_extract_status("raw")) == 500
        finally:
            db.close()

    def test_second_run_all_updated_no_duplicates(self, tmp_path):
        from src.pipeline import ResearchPipeline

        src = tmp_path / "ann"
        src.mkdir()
        (src / "one.json").write_text(
            json.dumps(
                [{"bid_id": "D-1", "project_name": "重跑"}],
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        db_path = tmp_path / "d.db"
        p1 = ResearchPipeline(db_path, output_dir=tmp_path / "o1")
        p1.run(src)
        p2 = ResearchPipeline(db_path, output_dir=tmp_path / "o2")
        result = p2.run(src)
        collect = result.stage("collect")
        assert collect.detail["new"] == 0
        assert collect.detail["updated"] == 1
        db = BidDatabase(db_path)
        try:
            assert db.count_bids() == 1
        finally:
            db.close()
