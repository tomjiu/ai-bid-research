"""分析报告组装与渲染测试（#601 批次 C 第 14 轮）。"""

import pytest

from src.analyze import AnalysisDataset
from src.analyze.report_data import (
    build_analysis_payload,
    render_analysis_markdown,
)
from src.report.generator import ReportGenerator


def _filled_ds() -> AnalysisDataset:
    """构造全字段的演示数据集。"""
    records = []
    # 10 条跨月、跨区域、多关键词、部分定标的记录
    for i in range(10):
        records.append(
            {
                "bid_id": f"R-{i:03d}",
                "project_name": (
                    "智慧城市一期平台" if i % 2 == 0 else "政务云数据中心扩容"
                ),
                "region": ["浙江", "江苏", "广东"][i % 3],
                "budget": 100.0 * (i + 1),
                "publish_date": f"2026-{8 + i // 4:02d}-{(i % 28) + 1:02d}",
                "purchaser": f"买家{i % 2}",
                "winner": "甲公司" if i < 4 else None,
                "requirements": ["ISO9001 认证"],
            }
        )
    return AnalysisDataset(records=records)


class TestBuildAnalysisPayload:
    """payload 组装。"""

    def test_payload_structure(self):
        """payload 含全部 12 个分析面键。"""
        payload = build_analysis_payload(_filled_ds(), keyword="智慧城市")
        expected_keys = {
            "keyword", "days", "generated_at", "record_count",
            "complete_rate", "budget", "region", "trend", "date_range",
            "keywords", "bigrams", "density",
        }
        assert expected_keys.issubset(payload.keys())
        assert payload["record_count"] == 10
        assert payload["budget"]["count"] == 10
        assert payload["density"]["records"] == 10

    def test_payload_json_serializable(self):
        """payload 可 JSON 序列化（研究面交换口径）。"""
        import json

        payload = build_analysis_payload(_filled_ds())
        json.dumps(payload, ensure_ascii=False)  # 不抛即可

    def test_empty_dataset_payload(self):
        """空集 payload：record_count 0 + 各面空值形态。"""
        payload = build_analysis_payload(AnalysisDataset())
        assert payload["record_count"] == 0
        assert payload["budget"]["count"] == 0
        assert payload["region"] == {}
        assert payload["density"]["monthly_rate"] is None


class TestRenderAnalysisMarkdown:
    """Markdown 渲染。"""

    def test_full_sections(self):
        """全字段数据集渲染出六大节 + 口径说明。"""
        payload = build_analysis_payload(_filled_ds(), keyword="智慧城市")
        md = render_analysis_markdown(payload)
        assert "领域数据分析报告：「智慧城市」" in md
        for section in (
            "一、预算分布", "二、区域分布", "三、月度发布趋势",
            "四、领域关键词", "五、新词发现", "六、竞争密度",
            "口径说明",
        ):
            assert section in md
        assert "| 指标 | 值 |" in md
        assert "智慧城市" in md
        assert "甲公司" not in md  # 中标人 top3 是占比，不点名（隐私面）
        assert "启发式估算" in md

    def test_empty_dataset_renders_gap_section(self):
        """空集 → 数据缺口节，不炸。"""
        md = render_analysis_markdown(build_analysis_payload(AnalysisDataset()))
        assert "数据缺口" in md
        assert "collect" in md

    def test_partial_fields(self):
        """只有部分字段的记录也能渲染（缺啥跳啥）。"""
        ds = AnalysisDataset(
            records=[
                {"project_name": "只有名字", "budget": 50.0},
                {"project_name": "另一项目"},
            ]
        )
        md = render_analysis_markdown(build_analysis_payload(ds))
        assert "一、预算分布" in md
        assert "二、区域分布" not in md  # 无区域 → 节跳过
        assert "三、月度发布趋势" not in md  # 无日期 → 节跳过


class TestReportGeneratorIntegration:
    """与 ReportGenerator 的集成面。"""

    def test_generate_analysis_report_saves_file(self, tmp_path):
        """离线报告保存为 markdown 文件（无 LLM 调用）。"""
        generator = ReportGenerator(
            output_dir=tmp_path / "reports",
            db=None,
        )
        payload = build_analysis_payload(_filled_ds(), keyword="智慧城市")
        path = generator.generate_analysis_report(payload)
        assert path.exists()
        content = path.read_text(encoding="utf-8")
        assert "领域数据分析报告" in content
        assert path.name.startswith("analysis_智慧城市")

    def test_export_html_roundtrip(self, tmp_path):
        """分析报告可走现有 export_html 面。"""
        generator = ReportGenerator(output_dir=tmp_path / "reports")
        payload = build_analysis_payload(_filled_ds())
        md_path = generator.generate_analysis_report(payload)
        html_path = generator.export_html(md_path)
        assert html_path.exists()
        assert "领域数据分析报告" in html_path.read_text(encoding="utf-8")
