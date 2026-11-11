"""近重复检测接入 analyze 报告测试（#601 R80）。

契约：第十六节渲染 + payload JSON 面含 duplicates 键（analyze
--json 自动透出）+ 节序编号一致 + TOC 可导航。
"""

from __future__ import annotations

from src.analyze.report_data import build_analysis_payload, render_analysis_markdown


def _ds(records):
    from src.analyze.dataset import AnalysisDataset

    return AnalysisDataset(records=records)


def _dup_records():
    """3 条记录：2 条改包重发 + 1 条独立——最小近重复信号集。"""
    return [
        {
            "bid_id": "D-1",
            "project_name": "某某市智慧城市建设项目一期工程总承包",
            "budget": 100.0,
        },
        {
            "bid_id": "D-2",
            "project_name": "某某市智慧城市建设项目一期工程总承包（二次）",
            "budget": 100.0,
        },
        {
            "bid_id": "D-3",
            "project_name": "某某区农田水利灌溉工程",
            "budget": 50.0,
        },
    ]


class TestDuplicatesInPayload:
    def test_payload_has_duplicates_key(self):
        payload = build_analysis_payload(_ds(_dup_records()))
        assert "duplicates" in payload
        dup = payload["duplicates"]
        assert dup["total"] == 3
        assert len(dup["clusters"]) == 1
        assert dup["clusters"][0]["size"] == 2
        # JSON 面完整可序列化（analyze --json 直接 json.dumps）
        import json

        json.dumps(payload, ensure_ascii=False)

    def test_empty_dataset_still_has_key(self):
        payload = build_analysis_payload(_ds([]))
        assert payload["duplicates"]["total"] == 0
        assert payload["duplicates"]["clusters"] == []


class TestDuplicatesInReport:
    def test_report_has_section_16(self):
        md = render_analysis_markdown(
            build_analysis_payload(_ds(_dup_records()))
        )
        assert "## 十六、近重复公告检测" in md
        # 行动面话术（去重建议）
        assert "改包重发" in md or "统计分析前建议" in md
        # 表格含簇成员
        assert "D-1" in md and "D-2" in md

    def test_clean_data_still_mentions_check(self):
        """无重复也明示「查过且干净」——不留白。"""
        records = [
            {"bid_id": "C-1", "project_name": "某某市智慧城市建设项目一期工程总承包"},
            {"bid_id": "C-2", "project_name": "某某区农田水利灌溉工程"},
        ]
        md = render_analysis_markdown(build_analysis_payload(_ds(records)))
        assert "十六、近重复公告检测" in md
        assert "未检出近重复" in md

    def test_single_record_omits_section(self):
        """单条无对比意义 → 跳节（与单条趋势等口径一致）。"""
        records = [{"bid_id": "S-1", "project_name": "唯一项目"}]
        md = render_analysis_markdown(build_analysis_payload(_ds(records)))
        assert "十六、近重复" not in md

    def test_toc_includes_section_16(self):
        """R63 目录机制覆盖新节（h2 锚点可导航）。"""
        from src.analyze.report_data import build_toc

        md = render_analysis_markdown(
            build_analysis_payload(_ds(_dup_records()))
        )
        toc = build_toc(md)
        assert "近重复公告检测" in toc
