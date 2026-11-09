"""extract 子命令 CLI 测试（#601 批次 B 第 9 轮）。

离线语义面：--no-llm 直通、env 无 key 自动降级、pending 登记面。
LLM 真实调用面由单测的 mock 覆盖（test_extract*.py），此处不重复。
"""

import json
from unittest.mock import AsyncMock

import pytest

import main as cli
from src.llm.client import LLMClient
from src.storage.database import BidDatabase


@pytest.fixture()
def source_dir(tmp_path):
    """含原文公告的源目录（一条重复、一条正常）。"""
    src = tmp_path / "announcements"
    src.mkdir()
    (src / "a.json").write_text(
        json.dumps(
            [
                {
                    "bid_id": "EX-001",
                    "project_name": "智慧园区一期",
                    "content": "预算 300万元，发布日期 2026年11月1日",
                },
                {
                    "bid_id": "EX-002",
                    "project_name": "政务云扩容",
                    "budget": "500万元",
                },
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return src


class TestExtractCLI:
    """extract 子命令语义面（离线）。"""

    def test_no_llm_passthrough_flow(self, source_dir, tmp_path, capsys):
        """--no-llm：直通入库（EX-001 原文不消费，EX-002 字段入库）。"""
        db_path = tmp_path / "b.db"
        code = cli.main(
            [
                "extract", "--source", str(source_dir),
                "--db", str(db_path), "--no-llm",
            ]
        )
        out = capsys.readouterr().out
        assert code == 0
        assert "直通 2 条" in out
        assert "入库：成功 2 条" in out
        with BidDatabase(db_path) as db:
            assert db.stats()["total"] == 2
            row = db.get_bid("EX-002")
        assert row["budget"] == 500.0

    def test_no_env_key_auto_degrades(self, source_dir, tmp_path, capsys,
                                      monkeypatch):
        """无 API key 环境变量 → 警告 + 自动离线直通。"""
        monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        code = cli.main(
            [
                "extract", "--source", str(source_dir),
                "--db", str(tmp_path / "b.db"),
            ]
        )
        out = capsys.readouterr().out
        assert code == 0
        assert "警告：未检测到" in out
        assert "降级为离线直通模式" in out

    def test_retry_without_key_exits_2(self, tmp_path, capsys, monkeypatch):
        """--retry 无 key → 明确报错退出 2（不静默假装重试）。"""
        monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        code = cli.main(
            ["extract", "--retry", "--db", str(tmp_path / "b.db")]
        )
        captured = capsys.readouterr()
        assert code == 2
        assert "--retry 需要真实 LLM" in captured.err

    def test_neither_source_nor_retry_exits_2(self, tmp_path, capsys):
        """缺 --source 且无 --retry → 用法错误退出 2。"""
        code = cli.main(["extract", "--db", str(tmp_path / "b.db")])
        captured = capsys.readouterr()
        assert code == 2
        assert "需要 --source 或 --retry" in captured.err

    def test_missing_source_exits_2(self, tmp_path, capsys):
        """源路径不存在 → 退出 2。"""
        code = cli.main(
            [
                "extract", "--source", str(tmp_path / "nope"),
                "--db", str(tmp_path / "b.db"), "--no-llm",
            ]
        )
        captured = capsys.readouterr()
        assert code == 2
        assert "源路径不存在" in captured.err

    def test_help_lists_extract(self, capsys):
        """--help 收录 extract 子命令。"""
        with pytest.raises(SystemExit) as excinfo:
            cli.main(["--help"])
        assert excinfo.value.code == 0
        assert "extract" in capsys.readouterr().out


class TestExtractCLIPendingFace:
    """CLI 面的 pending 登记（离线可测：拒收面）。"""

    def test_pending_registered_via_llm_failure(self, tmp_path, capsys,
                                                 monkeypatch):
        """LLM 失败 → pending 登记（mock 炸）+ 摘要打印。

        用 monkeypatch 造一个有 key 的环境，但把 chat_json mock 成失败
        ——验证 CLI 到 pending 的完整降级链。
        """
        monkeypatch.setenv("DEEPSEEK_API_KEY", "fake-key-for-test")
        src = tmp_path / "src"
        src.mkdir()
        (src / "a.json").write_text(
            json.dumps(
                [{
                    "bid_id": "PE-1",
                    "project_name": "抽取失败公告",
                    "content": "有原文必走 LLM",
                }],
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        db_path = tmp_path / "b.db"

        # 只拦截 extractor 的底层调用：CLI 内部构建的 LLMClient
        # 的 chat_json 炸（网络面模拟），抽取器把它包成 ExtractionError
        from src.extract import AnnouncementExtractor

        original_init = AnnouncementExtractor.__init__

        def _hook(self, client=None):
            original_init(self, client)
            if client is not None:
                client.chat_json = AsyncMock(
                    side_effect=RuntimeError("3 次重试后仍失败")
                )

        monkeypatch.setattr(AnnouncementExtractor, "__init__", _hook)
        code = cli.main(
            ["extract", "--source", str(src), "--db", str(db_path)]
        )
        out = capsys.readouterr().out
        assert code == 0
        assert "失败 1 条" in out
        assert "本次登记 pending 1 条" in out
        with BidDatabase(db_path) as db:
            stats = db.pending_stats()
            assert stats["pending"] == 1
            rows = db.list_pending()
        assert rows[0]["reason"] == "llm_error"
        assert rows[0]["raw_text"] == "有原文必走 LLM"
