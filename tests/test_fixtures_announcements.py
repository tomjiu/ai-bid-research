"""合成公告语料契约测试（#601 批次 E·R21）。

守护 ``fixtures/announcements`` 数据集的形态契约：
文件清单、装载行为、去重/更新/失败降级用例、验收冒烟。
fixtures 变更（有意）时同步更新本测试。
"""

from __future__ import annotations

from pathlib import Path

import pytest

import main as cli
from src.collect import load_records
from src.extract.runner import load_raw_texts, resolve_raw_files
from src.storage.database import BidDatabase

FIXTURES = Path(__file__).parent.parent / "fixtures" / "announcements"
STRUCTURED = FIXTURES / "structured"
RAW = FIXTURES / "raw"


@pytest.fixture()
def db(tmp_path):
    database = BidDatabase(tmp_path / "t.db")
    yield database
    database.close()


class TestFixtureContract:
    def test_directory_layout(self):
        """布局契约：README + structured 三件 + raw 三件。"""
        assert (FIXTURES / "README.md").is_file()
        assert sorted(p.name for p in STRUCTURED.iterdir()) == [
            "a-zhejiang.json",
            "b-beijing.jsonl",
            "c-update.json",
        ]
        assert sorted(p.name for p in RAW.iterdir()) == [
            "hlj-smartcity.txt",
            "noise.txt",
            "zj-cloud.txt",
        ]

    def test_structured_loads_seven_records(self, db):
        """结构化源 3 文件 7 条（3+3+1）——全部可规范化。"""
        result = load_records(STRUCTURED)
        assert result.files_read == 3
        assert len(result.records) == 7
        assert result.failures == []

    def test_chinese_alias_forms_covered(self, db):
        """a-zhejiang.json 用中文别名键 + 亿元/中文日期——归一可过。"""
        result = load_records(STRUCTURED)
        by_id = {r.bid_id: r for r in result.records}
        assert by_id["ZJ-SYN-2026-002"].budget == 15000.0  # 1.5亿 → 万元
        # 同 bid_id 的最后一条是 c-update.json（预算 3500 / 日期 2026-01-15）
        assert by_id["ZJ-SYN-2026-001"].budget == 3500.0
        assert by_id["ZJ-SYN-2026-001"].publish_date == "2026-01-15"

    def test_url_duplicate_pair_present(self):
        """b-beijing.jsonl 内 101/103 同 URL——去重面用例在场。"""
        result = load_records(STRUCTURED)
        urls = [
            r.source_url
            for r in result.records
            if r.bid_id in ("BJ-SYN-2026-101", "BJ-SYN-2026-103")
        ]
        assert urls[0] == urls[1]

    def test_update_pair_present(self):
        """c-update.json 与 a-zhejiang.json 同 bid_id——增量 update 用例在场。"""
        result = load_records(STRUCTURED)
        ids = [r.bid_id for r in result.records]
        assert ids.count("ZJ-SYN-2026-001") == 2

    def test_raw_sources_resolvable(self):
        files = resolve_raw_files(RAW)
        assert len(files) == 3

    def test_raw_load_three(self, db):
        stats = load_raw_texts(RAW, db)
        assert stats.saved == 3
        assert stats.failures == []


class TestAcceptanceSmoke:
    """#601 批次 D 验收口径：fixtures 双源 → 离线报告含统计数字。"""

    def test_pipeline_acceptance(self, tmp_path, capsys):
        db_path = tmp_path / "demo.db"
        out_dir = tmp_path / "reports"
        code = cli.main(
            [
                "pipeline",
                "--announcements",
                str(STRUCTURED),
                "--raw-texts",
                str(RAW),
                "--db",
                str(db_path),
                "--output-dir",
                str(out_dir),
            ]
        )
        assert code == 0
        out = capsys.readouterr().out
        # 去重/更新/失败降级全链路用例都真实发生
        assert "新增 5" in out  # 3 浙江 + 2 北京新件
        assert "更新 1" in out  # c-update.json 命中 ZJ-SYN-2026-001
        assert "重复跳过 1" in out  # BJ-103 同 URL
        assert "成功 2" in out and "失败 1" in out  # noise.txt 降级

        # 验收口径：报告含统计数字（解包断言，不信 CLI 输出）
        report = list(out_dir.glob("pipeline_*.md"))[0]
        content = report.read_text(encoding="utf-8")
        assert "共 7 条项目" in content
        assert "26,240" in content  # 预算总额（含 update 后的 3500）
        assert "## 五、竞争密度" in content

    def test_pipeline_dry_run_acceptance(self, tmp_path, capsys):
        """演练模式：预演统计可见、零副作用。"""
        db_path = tmp_path / "demo.db"
        out_dir = tmp_path / "reports"
        code = cli.main(
            [
                "pipeline",
                "--announcements",
                str(STRUCTURED),
                "--raw-texts",
                str(RAW),
                "--db",
                str(db_path),
                "--output-dir",
                str(out_dir),
                "--dry-run",
            ]
        )
        assert code == 1  # 空库 analyze 诚实失败
        assert db_path.exists() is False or BidDatabase(
            db_path
        ).count_bids() >= 0
        with BidDatabase(db_path) as db:
            assert db.count_bids() == 0  # 零写入
