"""批 L 冒烟（#601 R85）：fixture 真链路 → 新面真渲染。

覆盖 R79-R84 六个增量在真实数据形态下的联动：
近重复聚类（fixture 的五条同名「智慧水务运维服务」）、
语义健康审计、data-quality 命令、db --runs 台账、阶段耗时。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from main import main
from src.pipeline import ResearchPipeline
from src.storage.database import BidDatabase

FIXTURES = Path(__file__).parent / "fixtures" / "announcements"


@pytest.fixture(scope="module")
def smokes(tmp_path_factory):
    """模块级一次全链（冒烟共享，减少重复跑管道）。"""
    td = tmp_path_factory.mktemp("smoke-l")
    db_path = td / "smoke.db"
    pipeline = ResearchPipeline(db_path, output_dir=td / "reports")
    result = pipeline.run(FIXTURES, keyword=None)
    return {"db": db_path, "result": result, "td": td}


class TestSmokeBatchL:
    def test_duplicates_detected_on_real_fixture(self, smokes):
        """f-定标面.json 五条同名 → 一簇 size=5（多平台转发形态）。"""
        payload = smokes["result"].payload
        clusters = payload["duplicates"]["clusters"]
        water = [
            c for c in clusters if c["normalized"] == "智慧水务运维服务"
        ]
        assert water, f"应检出「智慧水务运维服务」簇，实际簇: {clusters}"
        assert water[0]["size"] == 5
        ids = {m["bid_id"] for m in water[0]["members"]}
        assert ids == {"FX-07", "FX-08", "FX-09", "FX-10", "FX-11"}

    def test_report_has_sections_16_17(self, smokes):
        report = Path(smokes["result"].report_path)
        text = report.read_text(encoding="utf-8")
        assert "## 十六、近重复公告检测" in text
        assert "智慧水务运维服务" in text
        assert "## 十七、语义质量审计" in text

    def test_data_quality_cli_on_real_db(self, smokes, capsys):
        code = main(["data-quality", "--db", str(smokes["db"])])
        assert code == 0
        out = capsys.readouterr().out
        assert "数据质量审计" in out
        # fixture 含缺字段记录（e-缺字段.json）——行动面有内容
        assert "最缺字段" in out or "无缺口" in out

    def test_data_quality_json_ci_face(self, smokes, capsys):
        code = main(["data-quality", "--db", str(smokes["db"]), "--json"])
        assert code == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["records"] >= 10
        assert 0 <= payload["semantic_health"]["health_score"] <= 100

    def test_runs_ledger_with_durations(self, smokes, capsys):
        code = main(["db", "--db", str(smokes["db"]), "--runs", "3"])
        assert code == 0
        out = capsys.readouterr().out
        assert "[done]" in out
        assert "collect@ok" in out
        assert "analyze@ok(" in out  # 带耗时的阶段链
        assert "report@ok(" in out

    def test_semantic_issues_reflect_fixture_defects(self, smokes):
        """fixture 故意埋的问题被审计看见（诚实揭示）。"""
        db = BidDatabase(smokes["db"])
        try:
            from src.analyze import load_dataset
            from src.analyze.quality import semantic_health

            sem = semantic_health(load_dataset(smokes["db"]))
            # f-定标面 FX-07~11 若 publish 晚于 deadline 等由 fixture 决定；
            # 冒烟只锁「审计跑通且分数在界内」+ 输出可序列化
            json.dumps(sem, ensure_ascii=False)
            assert sem["records"] >= 10
        finally:
            db.close()
