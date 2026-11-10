"""R42 SQLite 平台 PRAGMA 测试——WAL 生效/回退/探测三面。"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from src.storage.database import BidDatabase
from src.storage.pragmas import configure_pragmas, journal_mode_of, wal_available


class TestConfigurePragmas:
    def test_local_file_gets_wal(self, tmp_path):
        db = tmp_path / "a.db"
        conn = sqlite3.connect(str(db))
        try:
            applied = configure_pragmas(conn)
            assert applied["journal_mode"] == "wal"
            assert applied["synchronous"] == "1"  # NORMAL
        finally:
            conn.close()
        # 落盘持久：重开仍是 wal
        assert journal_mode_of(db) == "wal"

    def test_memory_db_falls_back_gracefully(self):
        conn = sqlite3.connect(":memory:")
        try:
            applied = configure_pragmas(conn)
            # 内存库不支持 WAL——必须优雅回退而非抛错
            assert applied["journal_mode"] in ("memory", "delete")
            assert applied["synchronous"] in ("0", "2", "unknown")
        finally:
            conn.close()

    def test_wal_probe_cleans_up(self, tmp_path):
        target = tmp_path / "probe-target.db"
        assert wal_available(target) is True
        # 探测伴生文件（-wal-probe*）不留残骸
        leftovers = [p.name for p in tmp_path.iterdir() if "wal-probe" in p.name]
        assert leftovers == []


class TestBidDatabaseWiring:
    def test_file_db_reports_wal(self, tmp_path):
        db = BidDatabase(tmp_path / "b.db")
        try:
            assert db.pragmas["journal_mode"] == "wal"
        finally:
            db.close()

    def test_memory_db_skips_pragmas(self):
        db = BidDatabase(":memory:")
        try:
            assert db.pragmas["journal_mode"] == "memory"
        finally:
            db.close()

    def test_wal_allows_concurrent_reader(self, tmp_path):
        """WAL 核心收益：写者持事务时读者不被阻塞（本地文件系统）。"""
        writer = BidDatabase(tmp_path / "c.db")
        try:
            writer.save_bid(
                {"bid_id": "B-1", "project_name": "智慧城市一期", "budget": 100.0}
            )
            writer._conn.execute("BEGIN")
            writer._conn.execute(
                "INSERT INTO bids(bid_id, project_name) VALUES('B-2','二期')"
            )
            # 读者在写事务未提交时仍可读到已提交数据（WAL 快照）
            import sqlite3

            reader = sqlite3.connect(
                str(tmp_path / "c.db"), timeout=2.0
            )
            try:
                rows = reader.execute(
                    "SELECT COUNT(*) FROM bids WHERE bid_id='B-1'"
                ).fetchone()
                assert rows[0] == 1
            finally:
                reader.close()
            writer._conn.execute("ROLLBACK")
        finally:
            writer.close()


class TestSchemaVersioning:
    """R56：PRAGMA user_version 迁移框架 + 状态面。"""

    def test_fresh_db_gets_latest_version(self, tmp_path):
        db = BidDatabase(tmp_path / "v.db")
        try:
            info = db.schema_info()
            assert info["user_version"] == 3
            assert set(info["tables"]) >= {
                "bids", "pending_announcements", "pipeline_runs",
            }
            assert all(count == 0 for count in info["tables"].values())
        finally:
            db.close()

    def test_migration_runs_once_idempotent(self, tmp_path):
        db = BidDatabase(tmp_path / "i.db")
        try:
            assert db.schema_info()["user_version"] == 3
            # 重复初始化（旧实例关闭重开）不重复迁移、版本不漂
            db.close()
            db2 = BidDatabase(tmp_path / "i.db")
            assert db2.schema_info()["user_version"] == 3
        finally:
            try:
                db.close()
            except Exception:
                pass
            try:
                db2.close()
            except Exception:
                pass

    def test_legacy_db_upgraded(self, tmp_path):
        """伪造 user_version=0 的旧库（bids 表结构与现版一致，
        缺 pending/pipeline_runs 两表与 extract_status 列）
        → 打开后自动逐级迁移到最新 v3。"""
        import sqlite3

        legacy = tmp_path / "legacy.db"
        conn = sqlite3.connect(str(legacy))
        conn.execute(
            "CREATE TABLE bids ("
            " id INTEGER PRIMARY KEY AUTOINCREMENT,"
            " bid_id TEXT UNIQUE NOT NULL,"
            " project_name TEXT NOT NULL,"
            " region TEXT, budget REAL, publish_date TEXT,"
            " deadline TEXT, category TEXT, purchaser TEXT,"
            " agency TEXT, winner TEXT, source_url TEXT,"
            " requirements TEXT,"
            " created_at TEXT NOT NULL DEFAULT"
            " (datetime('now', 'localtime')))"
        )
        conn.execute("PRAGMA user_version = 0")
        conn.commit()
        conn.close()
        db = BidDatabase(legacy)
        try:
            info = db.schema_info()
            assert info["user_version"] == 3
            # 补齐的表已可见
            assert "pending_announcements" in info["tables"]
            assert "pipeline_runs" in info["tables"]
            # v3 迁移列已补齐
            cols = {
                r[1] for r in db._conn.execute("PRAGMA table_info(bids)")
            }
            assert "extract_status" in cols
        finally:
            db.close()

    def test_cli_status_output(self, tmp_path, capsys):
        import main as main_mod

        db = BidDatabase(tmp_path / "s.db")
        db.close()  # status 需库已存在（与 --stats 同口径）
        rc = main_mod.main(
            ["db", "--db", str(tmp_path / "s.db"), "--status"]
        )
        assert rc == 0
        out = capsys.readouterr().out
        assert "schema 版本：v3" in out
        assert "bids: 0" in out
        assert "PRAGMA 生效" in out
