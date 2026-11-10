"""db 在线备份测试（#601 R71）。"""

from __future__ import annotations


import pytest

import main as main_mod
from src.storage.database import BidDatabase


def _seeded(db_path, n=3):
    db = BidDatabase(db_path)
    try:
        db.import_bids(
            [
                {"bid_id": f"BK-{i}", "project_name": f"项目{i}",
                 "budget": float(i * 10)}
                for i in range(n)
            ]
        )
    finally:
        db.close()
    return db_path


class TestBackupTo:
    def test_backup_roundtrip_equivalent(self, tmp_path):
        src = _seeded(tmp_path / "src.db")
        db = BidDatabase(src)
        try:
            target = db.backup_to(tmp_path / "backup.db")
            src_version = db.schema_info()["user_version"]
        finally:
            db.close()
        assert target.exists()
        restored = BidDatabase(target)
        try:
            assert restored.count_bids() == 3
            row = restored.get_bid("BK-1")
            assert row["project_name"] == "项目1"
            # schema 版本随库走
            assert restored.schema_info()["user_version"] == src_version
        finally:
            restored.close()

    def test_backup_with_uncheckpointed_wal(self, tmp_path):
        """WAL 未 checkpoint 时备份不丢数据（与文件拷贝的本质差异）。"""
        src = _seeded(tmp_path / "w.db", n=2)
        # 写者持连接 + WAL 模式下追加写（未 checkpoint）
        writer = BidDatabase(src)
        try:
            assert writer.pragmas["journal_mode"] == "wal"
            writer.save_bid(
                {"bid_id": "WAL-NEW", "project_name": "未落盘内容"}
            )
            # 不显式 checkpoint、不关连接——直接在线备份
            target = writer.backup_to(tmp_path / "wal-backup.db")
        finally:
            writer.close()
        check = BidDatabase(target)
        try:
            assert check.get_bid("WAL-NEW") is not None  # 关键断言
            assert check.count_bids() == 3
        finally:
            check.close()

    def test_backup_same_file_rejected(self, tmp_path):
        src = _seeded(tmp_path / "same.db")
        db = BidDatabase(src)
        try:
            with pytest.raises(ValueError, match="同文件"):
                db.backup_to(src)
        finally:
            db.close()

    def test_backup_creates_parent_dirs(self, tmp_path):
        src = _seeded(tmp_path / "p.db")
        db = BidDatabase(src)
        try:
            target = db.backup_to(tmp_path / "deep" / "nested" / "b.db")
        finally:
            db.close()
        assert target.exists()


class TestCliBackup:
    def test_cli_backup_end_to_end(self, tmp_path, capsys):
        src = _seeded(tmp_path / "cli.db")
        rc = main_mod.main(
            ["db", "--db", str(src), "--backup", str(tmp_path / "out.db")]
        )
        assert rc == 0
        out = capsys.readouterr().out
        assert "已备份" in out
        restored = BidDatabase(tmp_path / "out.db")
        try:
            assert restored.count_bids() == 3
        finally:
            restored.close()

    def test_cli_backup_failure_actionable(self, tmp_path, capsys):
        src = _seeded(tmp_path / "f.db")
        # 目标与源同文件 → 明确报错而非损坏源
        rc = main_mod.main(
            ["db", "--db", str(src), "--backup", str(src)]
        )
        assert rc == 2
        assert "备份失败" in capsys.readouterr().err

    def test_backup_missing_db_is_data_error(self, tmp_path, capsys):
        rc = main_mod.main(
            ["db", "--db", str(tmp_path / "ghost.db"),
             "--backup", str(tmp_path / "x.db")]
        )
        assert rc == 2
