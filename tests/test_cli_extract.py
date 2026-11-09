"""extract 子命令 CLI 测试（#601 批次 B 第 5 轮）。

直接调用 main.main(argv) 验证退出码与输出（与 CI 冒烟互补：
CI 验进程面，这里断言语义面）。
"""

from __future__ import annotations

import pytest

import main as cli
from src.storage.database import BidDatabase

from tests.test_extract_engine import SAMPLE_ANNOUNCEMENT


@pytest.fixture()
def raw_dir(tmp_path):
    """两好一坏的公告原文目录。"""
    d = tmp_path / "raw"
    d.mkdir()
    (d / "notice-a.txt").write_text(
        SAMPLE_ANNOUNCEMENT, encoding="utf-8"
    )
    (d / "notice-b.txt").write_text(
        SAMPLE_ANNOUNCEMENT.replace("HLJ-GC-2026-001", "HLJ-GC-2026-002"),
        encoding="utf-8",
    )
    (d / "not-announcement.txt").write_text(
        "普通文本，没有任何招标结构。\n", encoding="utf-8"
    )
    return d


class TestExtractCLI:
    """extract 子命令语义面。"""

    def test_full_flow_rule_mode(self, raw_dir, tmp_path, capsys):
        """完整链：装载 → 抽取 → 入库；失败件保持 pending。"""
        db_path = tmp_path / "bids.db"
        code = cli.main(
            [
                "extract",
                "--source",
                str(raw_dir),
                "--db",
                str(db_path),
                "--mode",
                "rule",
            ]
        )
        assert code == 0
        out = capsys.readouterr().out
        assert "原文装载：读取 3 个文件，新入 3 条" in out
        assert "成功 2 条，失败 1 条" in out
        assert "待抽取 1 条，已抽取 2 条" in out

        with BidDatabase(db_path) as db:
            assert db.count_bids() == 2
            bid = db.get_bid("HLJ-GC-2026-001")
            assert bid is not None
            assert bid["budget"] == 1200.0
            assert bid["publish_date"] == "2026-03-01"

    def test_dry_run_no_write(self, raw_dir, tmp_path, capsys):
        db_path = tmp_path / "bids.db"
        code = cli.main(
            [
                "extract",
                "--source",
                str(raw_dir),
                "--db",
                str(db_path),
                "--dry-run",
            ]
        )
        assert code == 0
        out = capsys.readouterr().out
        assert "演练模式：未写库" in out
        with BidDatabase(db_path) as db:
            assert db.count_bids() == 0
            assert db.raw_stats()["pending"] == 3

    def test_retry_pending_only(self, raw_dir, tmp_path, capsys):
        """无 --source 时只处理库内 pending（重试口径）。"""
        db_path = tmp_path / "bids.db"
        cli.main(
            ["extract", "--source", str(raw_dir), "--db", str(db_path)]
        )
        capsys.readouterr()
        # 第二次不带 source：只剩坏件重试
        code = cli.main(["extract", "--db", str(db_path)])
        assert code == 0
        out = capsys.readouterr().out
        assert "原文装载" not in out  # 不重复装载
        assert "处理 1 条，成功 0 条，失败 1 条" in out

    def test_missing_source_exit_2(self, tmp_path, capsys):
        code = cli.main(
            [
                "extract",
                "--source",
                str(tmp_path / "nope"),
                "--db",
                str(tmp_path / "bids.db"),
            ]
        )
        assert code == 2
        assert "不存在" in capsys.readouterr().err

    def test_api_mode_without_key_exit_2(self, tmp_path, capsys, monkeypatch):
        monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        code = cli.main(
            [
                "extract",
                "--db",
                str(tmp_path / "bids.db"),
                "--mode",
                "api",
            ]
        )
        assert code == 2
        assert "DEEPSEEK_API_KEY" in capsys.readouterr().err

    def test_reimport_source_idempotent(self, raw_dir, tmp_path, capsys):
        """同源再导入：内容指纹幂等，零新增零处理。"""
        db_path = tmp_path / "bids.db"
        cli.main(["extract", "--source", str(raw_dir), "--db", str(db_path)])
        capsys.readouterr()
        code = cli.main(
            ["extract", "--source", str(raw_dir), "--db", str(db_path)]
        )
        assert code == 0
        out = capsys.readouterr().out
        assert "重复跳过 3 条" in out
        assert "处理 1 条" in out  # 只重试 pending 坏件
        with BidDatabase(db_path) as db:
            assert db.count_bids() == 2

    def test_per_item_output(self, raw_dir, tmp_path, capsys):
        db_path = tmp_path / "bids.db"
        cli.main(
            ["extract", "--source", str(raw_dir), "--db", str(db_path)]
        )
        out = capsys.readouterr().out
        assert "✓ notice-a.txt → HLJ-GC-2026-001" in out
        assert "✗ not-announcement.txt" in out

    def test_help_registered(self, capsys):
        """extract 已注册在 CLI 帮助面。"""
        with pytest.raises(SystemExit) as exc_info:
            cli.main(["--help"])
        assert exc_info.value.code == 0
        out = capsys.readouterr().out
        assert "extract" in out
