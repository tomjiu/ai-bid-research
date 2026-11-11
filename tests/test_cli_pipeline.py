"""pipeline 子命令 CLI 测试（#601 批次 D 第 18 轮）。"""

import json

import pytest

import main as cli
from src.storage.database import BidDatabase


@pytest.fixture()
def source(tmp_path):
    src = tmp_path / "announcements"
    src.mkdir()
    (src / "a.json").write_text(
        json.dumps(
            [
                {"bid_id": "PC-001", "project_name": "管道一期项目"},
                {"bid_id": "PC-002", "project_name": "管道二期", "budget": "800万元"},
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return src


class TestPipelineCLI:
    """pipeline 子命令。"""

    def test_offline_full_chain(self, source, tmp_path, capsys):
        """离线全链：四阶段状态行 + 台账登记。"""
        code = cli.main(
            [
                "pipeline", "--source", str(source),
                "--db", str(tmp_path / "b.db"),
                "--output-dir", str(tmp_path / "r"),
                "--no-llm",
            ]
        )
        out = capsys.readouterr().out
        assert code == 0
        assert "[collect] ok: 读取 1 文件，装载 2 条（新 2 / 更新 0）" in out
        assert "[extract] skipped: 跳过：未配置抽取器（离线模式）" in out
        assert "[analyze] ok: 2 条记录" in out
        assert "[report] ok: 报告 →" in out
        assert "运行已登记：run #1" in out

    def test_incremental_rerun_zero_new(self, source, tmp_path, capsys):
        """增量重跑：零新文件（水位生效）。"""
        db = tmp_path / "b.db"
        for _ in range(2):
            code = cli.main(
                [
                    "pipeline", "--source", str(source), "--db", str(db),
                    "--output-dir", str(tmp_path / "r"), "--no-llm",
                    "--incremental",
                ]
            )
            assert code == 0
        out = capsys.readouterr().out
        # 第二次运行的 collect 行（最后出现）
        assert "[collect] ok: 读取 0 文件，装载 0 条（新 0 / 更新 0）" in out
        assert "run #2" in out

    def test_html_flag(self, source, tmp_path, capsys):
        """--html 落盘 HTML。"""
        code = cli.main(
            [
                "pipeline", "--source", str(source), "--db", str(tmp_path / "b.db"),
                "--output-dir", str(tmp_path / "r"), "--no-llm", "--html",
            ]
        )
        out = capsys.readouterr().out
        assert code == 0
        assert "HTML 已导出" in out

    def test_missing_source_exits_2(self, tmp_path, capsys):
        """源不存在 → 起步硬错退出 2。"""
        code = cli.main(
            [
                "pipeline", "--source", str(tmp_path / "nope"),
                "--db", str(tmp_path / "b.db"),
                "--output-dir", str(tmp_path / "r"), "--no-llm",
            ]
        )
        captured = capsys.readouterr()
        assert code == 2
        assert "源路径不存在" in captured.err

    def test_no_source_analysis_only(self, tmp_path, capsys):
        """无 --source：纯分析既有库。"""
        with BidDatabase(tmp_path / "b.db") as db_:
            db_.save_bid(
                {"bid_id": "N-1", "project_name": "既有项目", "budget": 90.0}
            )
        code = cli.main(
            [
                "pipeline", "--db", str(tmp_path / "b.db"),
                "--output-dir", str(tmp_path / "r"), "--no-llm",
            ]
        )
        out = capsys.readouterr().out
        assert code == 0
        assert "[collect] skipped" in out
        assert "1 条记录" in out

    def test_keyword_scope(self, source, tmp_path, capsys):
        """--keyword 口径进报告与台账。"""
        code = cli.main(
            [
                "pipeline", "--source", str(source), "--db", str(tmp_path / "b.db"),
                "--output-dir", str(tmp_path / "r"), "--no-llm",
                "--keyword", "管道",
            ]
        )
        capsys.readouterr()
        assert code == 0
        reports = list((tmp_path / "r").glob("analysis_管道_*.md"))
        assert len(reports) == 1
        with BidDatabase(tmp_path / "b.db") as db:
            assert db.pipeline_runs_list()[0]["keyword"] == "管道"

    def test_env_no_key_auto_offline(self, source, tmp_path, capsys,
                                     monkeypatch):
        """无 API key → 警告 + 离线降级（不重复无谓报错）。"""
        monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        code = cli.main(
            [
                "pipeline", "--source", str(source), "--db", str(tmp_path / "b.db"),
                "--output-dir", str(tmp_path / "r"),
            ]
        )
        out = capsys.readouterr().out
        assert code == 0
        assert "警告：未检测到" in out
        assert "[extract] skipped" in out


class TestPipelineCLIMergeRender:
    """R103 collect 渲染面：真实变化明示（零变化零噪音）。"""

    def test_substance_line_shows_fill_and_change(self, tmp_path, capsys):
        """补缺/修正入渲染行；同值重跑不出现「更新实质」。"""
        src = tmp_path / "ann"
        src.mkdir()
        db = tmp_path / "b.db"
        out_dir = tmp_path / "r"

        def _run(records):
            (src / "a.json").write_text(
                json.dumps(records, ensure_ascii=False), encoding="utf-8"
            )
            code = cli.main(
                [
                    "pipeline", "--source", str(src), "--db", str(db),
                    "--output-dir", str(out_dir), "--no-llm",
                ]
            )
            assert code == 0
            return capsys.readouterr().out

        # 首跑：完整形态（预算 + 截止）
        out1 = _run(
            [
                {
                    "bid_id": "MR-1",
                    "project_name": "智慧路灯",
                    "budget": 40.0,
                    "deadline": "2026-12-01",
                }
            ]
        )
        assert "更新实质" not in out1
        # 变更公告形态：预算下修 + 新增中标人
        out2 = _run(
            [
                {
                    "bid_id": "MR-1",
                    "project_name": "智慧路灯",
                    "budget": 35.0,
                    "deadline": "2026-12-01",
                    "winner": "丙公司",
                }
            ]
        )
        assert "更新实质：补缺 1 / 修正 1 个字段" in out2
        # 同值重跑：零变化零噪音
        out3 = _run(
            [
                {
                    "bid_id": "MR-1",
                    "project_name": "智慧路灯",
                    "budget": 35.0,
                    "deadline": "2026-12-01",
                    "winner": "丙公司",
                }
            ]
        )
        assert "更新实质" not in out3
        with BidDatabase(db) as conn:
            row = conn.get_bid("MR-1")
        assert (row["budget"], row["winner"]) == (35.0, "丙公司")
