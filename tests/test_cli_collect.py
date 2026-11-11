"""collect 子命令 CLI 测试（#601 批次 A 第 4 轮）。

直接调用 main.main(argv) 验证退出码与输出（与 CI 冒烟互补：
CI 验进程面，这里断言语义面）。
"""

import json

import pytest

import main as cli
from src.storage.database import BidDatabase


@pytest.fixture()
def source_dir(tmp_path):
    """构造含好/坏数据的公告源目录。"""
    good = tmp_path / "announcements"
    good.mkdir()
    (good / "a.json").write_text(
        json.dumps(
            [
                {
                    "招标编号": "ZJ-2026-001",
                    "项目名称": "智慧城市一期",
                    "预算金额": "1.2亿",
                    "发布日期": "2026年11月1日",
                },
                {
                    "bid_id": "ZJ-2026-001",  # 同 bid_id 重复（另一源收录）
                    "project_name": "智慧城市一期-重复",
                },
                {
                    "bid_id": "ZJ-2026-002",
                    "project_name": "智慧城市二期",
                    "预算金额": "500万元",
                },
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (good / "b.jsonl").write_text(
        json.dumps(
            {"bid_id": "JS-2026-009", "项目名称": "政务云扩容"},
            ensure_ascii=False,
        )
        + "\n{broken\n",
        encoding="utf-8",
    )
    (good / "broken.json").write_text("{bad", encoding="utf-8")
    return good


class TestCollectCLI:
    """collect 子命令语义面。"""

    def test_collect_full_flow(self, source_dir, tmp_path, capsys):
        """完整链：装载→去重→入库，输出各阶段统计。"""
        db_path = tmp_path / "bids.db"
        code = cli.main(
            [
                "collect",
                "--source", str(source_dir),
                "--db", str(db_path),
            ]
        )
        out = capsys.readouterr().out
        assert code == 0
        assert "读取 3 个文件" in out
        assert "失败 2 条" in out  # broken.json + b.jsonl 坏行
        assert "去除 1 条重复" in out
        assert "已入库 3 条" in out  # 001 / 002 / 009

        with BidDatabase(db_path) as db:
            stats = db.stats()
            row = db.get_bid("ZJ-2026-001")
        assert stats["total"] == 3
        assert row["budget"] == 12000.0  # 1.2亿 → 万元归一
        assert row["project_name"] == "智慧城市一期"  # keep-first
        assert row["publish_date"] == "2026-11-01"

    def test_dry_run_does_not_write(self, source_dir, tmp_path, capsys):
        """演练模式：全链报告但不写库。"""
        db_path = tmp_path / "bids.db"
        code = cli.main(
            [
                "collect",
                "--source", str(source_dir),
                "--db", str(db_path),
                "--dry-run",
            ]
        )
        out = capsys.readouterr().out
        assert code == 0
        assert "演练模式：未写库" in out
        assert not db_path.exists()

    def test_failures_printed_with_origin(self, source_dir, tmp_path, capsys):
        """失败明细逐条打印（origin 可定位），退出码仍 0。"""
        code = cli.main(
            [
                "collect",
                "--source", str(source_dir),
                "--db", str(tmp_path / "bids.db"),
            ]
        )
        out = capsys.readouterr().out
        assert code == 0
        assert "broken.json" in out
        assert "b.jsonl:2" in out

    def test_strict_mode_exits_2(self, source_dir, tmp_path, capsys):
        """严格模式：坏数据即中止，退出码 2。"""
        code = cli.main(
            [
                "collect",
                "--source", str(source_dir),
                "--db", str(tmp_path / "bids.db"),
                "--strict",
            ]
        )
        captured = capsys.readouterr()
        assert code == 2
        assert "错误：" in captured.err

    def test_missing_source_exits_2(self, tmp_path, capsys):
        """源路径不存在 → 退出码 2，错误进 stderr。"""
        code = cli.main(
            [
                "collect",
                "--source", str(tmp_path / "nope"),
                "--db", str(tmp_path / "bids.db"),
            ]
        )
        captured = capsys.readouterr()
        assert code == 2
        assert "源路径不存在" in captured.err

    def test_rerun_idempotent(self, source_dir, tmp_path, capsys):
        """重复采集幂等：bid_id upsert，库内不重复。"""
        db_path = tmp_path / "bids.db"
        for _ in range(2):
            code = cli.main(
                ["collect", "--source", str(source_dir), "--db", str(db_path)]
            )
            assert code == 0
        with BidDatabase(db_path) as db:
            assert db.stats()["total"] == 3

    def test_single_file_source(self, tmp_path, capsys):
        """单文件源（.json 单对象形态）。"""
        path = tmp_path / "one.json"
        path.write_text(
            json.dumps(
                {"bid_id": "S-1", "project_name": "单文件项目"},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        db_path = tmp_path / "bids.db"
        code = cli.main(
            ["collect", "--source", str(path), "--db", str(db_path)]
        )
        out = capsys.readouterr().out
        assert code == 0
        assert "已入库 1 条" in out

    def test_help_lists_collect(self, capsys):
        """--help 收录 collect 子命令（自发现性）。"""
        with pytest.raises(SystemExit) as excinfo:
            cli.main(["--help"])
        assert excinfo.value.code == 0
        out = capsys.readouterr().out
        assert "collect" in out


class TestCollectCLINoClobber:
    """R104 collect CLI：入库走不倒退合并，实质分账明示。"""

    def test_recollect_sparse_preserves_and_reports(self, tmp_path, capsys):
        """稀疏重采：库内字段保值 + 「已入库 0 条」+ 无变化提示。"""
        import json as _json

        src = tmp_path / "ann"
        src.mkdir()
        (src / "a.json").write_text(
            _json.dumps(
                [
                    {
                        "bid_id": "RC-1",
                        "project_name": "智慧校园",
                        "budget": 200.0,
                        "winner": "甲公司",
                    }
                ],
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        db_path = tmp_path / "b.db"
        cli.main(["collect", "--source", str(src), "--db", str(db_path)])
        assert "已入库 1 条" in capsys.readouterr().out
        # 另一采集批次只有编号与名称（稀疏形态）
        (src / "a.json").write_text(
            _json.dumps(
                [{"bid_id": "RC-1", "project_name": "智慧校园"}],
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        code = cli.main(["collect", "--source", str(src), "--db", str(db_path)])
        out = capsys.readouterr().out
        assert code == 0
        assert "已入库 0 条" in out  # 无实质写入（merged=0）
        with BidDatabase(db_path) as db:
            row = db.get_bid("RC-1")
        assert row["budget"] == 200.0
        assert row["winner"] == "甲公司"

    def test_recollect_enriched_reports_substance(self, tmp_path, capsys):
        """增补重采：分账渲染（补缺/修正）。"""
        import json as _json

        src = tmp_path / "ann"
        src.mkdir()
        (src / "a.json").write_text(
            _json.dumps(
                [{"bid_id": "RC-2", "project_name": "智慧医院", "budget": 90.0}],
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        db_path = tmp_path / "b.db"
        cli.main(["collect", "--source", str(src), "--db", str(db_path)])
        capsys.readouterr()
        (src / "a.json").write_text(
            _json.dumps(
                [
                    {
                        "bid_id": "RC-2",
                        "project_name": "智慧医院",
                        "budget": 90.0,
                        "agency": "某代理",
                    }
                ],
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        code = cli.main(["collect", "--source", str(src), "--db", str(db_path)])
        out = capsys.readouterr().out
        assert code == 0
        assert "已入库 1 条" in out  # inserted 0 + merged 1
        assert "更新 1：补缺 1 / 修正 0 个字段" in out
        assert db_path.exists()
