"""data-quality 命令与报告第十七节测试（#601 R82）。

CLI 契约：幽灵库不静默建库（EXIT_DATA）、审计发现问题也退出 0
（审计揭示不拦截）、--json 机器可读、控制台含健康分与行动面。
报告契约：第十七节渲染（与命令同源单点）。
"""

from __future__ import annotations

import json

import pytest

from main import main
from src.analyze.report_data import build_analysis_payload, render_analysis_markdown
from src.storage.database import BidDatabase


@pytest.fixture()
def dirty_db(tmp_path):
    """含四类问题的库：负预算 + 发布晚于截止 + 缺 ID + 零预算。

    空 bid_id 在本工具所有入库路径都被 save_bid 校验挡住——
    这里用 SQL 直插模拟「外部写库/手工改库」（防御性审计的
    真实防对象）。
    """
    db = BidDatabase(tmp_path / "dirty.db")
    try:
        db.save_bid(
            {"bid_id": "B-1", "project_name": "正常项目", "budget": 100.0,
             "publish_date": "2026-05-01", "deadline": "2026-06-01"}
        )
        db.save_bid({"bid_id": "B-2", "project_name": "负预算", "budget": -5.0})
        db.save_bid(
            {"bid_id": "B-3", "project_name": "日期倒挂",
             "publish_date": "2026-06-01", "deadline": "2026-05-01"}
        )
        conn = db._conn
        conn.execute(
            "INSERT INTO bids (bid_id, project_name, budget) "
            "VALUES ('', '无ID', 0)"
        )
        conn.commit()
    finally:
        db.close()
    return tmp_path / "dirty.db"


class TestDataQualityCommand:
    def test_ghost_db_is_data_error(self, tmp_path, capsys):
        code = main(["data-quality", "--db", str(tmp_path / "ghost.db")])
        assert code == 2
        assert "数据库不存在" in capsys.readouterr().err

    def test_findings_exit_zero_with_score(self, dirty_db, capsys):
        """审计揭示不拦截：有问题也 0——健康分供外部决策。"""
        code = main(["data-quality", "--db", str(dirty_db)])
        assert code == 0
        out = capsys.readouterr().out
        assert "数据质量审计" in out
        assert "健康分" in out
        assert "预算为负" in out
        assert "发布晚于截止" in out
        assert "bid_id 缺失" in out

    def test_json_face_machine_readable(self, dirty_db, capsys):
        code = main(["data-quality", "--db", str(dirty_db), "--json"])
        assert code == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["records"] == 4
        issues = payload["semantic_health"]["issues"]
        assert "budget_negative" in issues
        assert "publish_after_deadline" in issues
        assert payload["semantic_health"]["health_score"] < 100
        assert 0 <= payload["semantic_health"]["health_score"] <= 100

    def test_clean_db_full_marks(self, tmp_path, capsys):
        db = BidDatabase(tmp_path / "clean.db")
        try:
            db.save_bid(
                {"bid_id": "OK-1", "project_name": "干净数据",
                 "budget": 88.0, "publish_date": "2026-01-10",
                 "deadline": "2026-02-01"}
            )
        finally:
            db.close()
        code = main(["data-quality", "--db", str(tmp_path / "clean.db")])
        assert code == 0
        out = capsys.readouterr().out
        assert "无异常" in out

    def test_scope_filters_apply(self, dirty_db, capsys):
        """--keyword 限定范围：未命中 → 空数据集如实报 0 条。"""
        code = main(
            ["data-quality", "--db", str(dirty_db), "--keyword", "不存在词"]
        )
        assert code == 0
        assert "0 条记录" in capsys.readouterr().out


class TestSection17InReport:
    def test_report_renders_section_17(self, dirty_db):
        from src.analyze import load_dataset

        dataset = load_dataset(dirty_db)
        payload = build_analysis_payload(dataset)
        assert "semantic_health" in payload
        md = render_analysis_markdown(payload)
        assert "## 十七、语义质量审计" in md
        assert "健康分" in md
        assert "预算为负" in md

    def test_clean_data_section_17_all_clear(self, tmp_path):
        from src.analyze import load_dataset

        db = BidDatabase(tmp_path / "ok.db")
        try:
            db.save_bid(
                {"bid_id": "OK-1", "project_name": "干净",
                 "budget": 88.0, "publish_date": "2026-01-10",
                 "deadline": "2026-02-01"}
            )
        finally:
            db.close()
        md = render_analysis_markdown(
            build_analysis_payload(load_dataset(tmp_path / "ok.db"))
        )
        assert "十七、语义质量审计" in md
        assert "无异常" in md

    def test_json_payload_serializable(self, dirty_db):
        from src.analyze import load_dataset

        payload = build_analysis_payload(load_dataset(dirty_db))
        json.dumps(payload, ensure_ascii=False)  # 不炸即契约
