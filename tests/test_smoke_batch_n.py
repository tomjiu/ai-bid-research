"""批 N 冒烟（#601 R100）：沉睡字段真链路 → 四新节真渲染。

覆盖 R95-R98 四个增量在真实数据形态（g-沉睡字段.json 入共享
fixture 语料）下的联动：响应窗口分布与短窗示例、代理机构画像、
品类分布、平台来源与跨平台转发信号（www·裸域名·http 三形态
归一；单平台簇不算跨平台的反例覆盖）。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.pipeline import ResearchPipeline

FIXTURES = Path(__file__).parent / "fixtures" / "announcements"


@pytest.fixture(scope="module")
def smokes(tmp_path_factory):
    """模块级一次全链（冒烟共享，减少重复跑管道）。"""
    td = tmp_path_factory.mktemp("smoke-n")
    db_path = td / "smoke.db"
    pipeline = ResearchPipeline(db_path, output_dir=td / "reports")
    result = pipeline.run(FIXTURES, keyword=None)
    return {"db": db_path, "result": result, "td": td}


class TestSmokeBatchN:
    def test_response_window_section(self, smokes):
        """十八节：分布表 + 14 日短窗示例（GN-03 智慧安防）。

        全语料 15 条：g 5 条全带双日期 + a 的 FX-001 也带截止
        （2026-10-12→11-05，24 日）→ 有效 6 / 缺 9。
        """
        payload = smokes["result"].payload
        windows = payload["response_windows"]
        assert windows["sample_count"] == 6
        assert windows["missing_count"] == 9
        assert windows["invalid_count"] == 0
        # 窗口集 [14,24,27,33,35,60] → 最近邻秩位中位 = 27
        assert windows["median_days"] == 27
        assert windows["min_days"] == 14
        assert windows["max_days"] == 60
        assert windows["short_window_count"] == 1
        examples = windows["short_window_examples"]
        assert examples and examples[0]["project_name"] == "智慧安防改造工程"
        assert examples[0]["window_days"] == 14

    def test_agency_section(self, smokes):
        """十九节：某信招标代理 3 项目 2 采购人；无代理记录不入聚。

        采购人序随数据集序（publish DESC）——非插入序。
        """
        payload = smokes["result"].payload
        agencies = {p["agency"]: p for p in payload["agency_profiles"]}
        trust = agencies["某信招标代理"]
        assert trust["project_count"] == 3
        assert trust["purchaser_count"] == 2
        assert trust["purchasers"] == ["某区公安分局", "某市大数据局"]
        # GN-04/05 无代理（采购人自采）——不进任何画像
        assert all(p["project_count"] <= 3 for p in payload["agency_profiles"])

    def test_category_section(self, smokes):
        """二十节：全语料只有 g 填了品类（5/15），三品类精确归并。"""
        payload = smokes["result"].payload
        cats = payload["category_distribution"]
        assert cats["filled_count"] == 5
        assert cats["missing_count"] == 10
        assert cats["distinct_count"] == 3
        counts = {c["category"]: c["count"] for c in cats["categories"]}
        assert counts == {"信息化": 2, "服务": 2, "安防": 1}

    def test_platform_section(self, smokes):
        """二十一节：三形态域名归一到同平台 + 跨平台信号恰 1 簇。"""
        payload = smokes["result"].payload
        platforms = payload["platform_distribution"]
        assert platforms["sample_count"] == 5  # g 全带 URL
        assert platforms["missing_count"] == 10
        counts = {p["platform"]: p["count"] for p in platforms["platforms"]}
        # www.qianlima / 裸域名 qianlima / http://www.qianlima → 同平台 2 条
        assert counts["qianlima.com"] == 2
        assert counts["ccgp.gov.cn"] == 2
        assert counts["ggzy.jiangsu.gov.cn"] == 1

    def test_multi_platform_signal_exact(self, smokes):
        """跨平台信号：数据中枢族（ccgp+ggzy）实证；城市运维族
        两平台形态实为同一平台（qianlima）——不算跨平台的反例。"""
        payload = smokes["result"].payload
        multi = payload["platform_distribution"]["multi_platform"]
        assert multi["clusters"] == 1
        assert multi["records"] == 2
        example = multi["examples"][0]
        assert example["normalized"] == "数据中枢平台建设项目"
        assert example["platforms"] == ["ccgp.gov.cn", "ggzy.jiangsu.gov.cn"]

    def test_report_renders_all_four_sections(self, smokes):
        """报告 18-21 节 + 诚实口径注全部落面。"""
        report = Path(smokes["result"].report_path)
        text = report.read_text(encoding="utf-8")
        for marker in (
            "## 十八、响应窗口期",
            "## 十九、代理机构画像",
            "## 二十、品类分布",
            "## 二十一、平台来源分布",
            "### 跨平台转发信号",
            "研究提示非违规认定",  # R95 短窗口径注
            "精确匹配",  # R97 品类口径注
        ):
            assert marker in text, f"报告缺: {marker}"

    def test_payload_json_serializable(self, smokes):
        """全 payload（含四新键）JSON 可序列化（--json 消费面）。"""
        text = json.dumps(smokes["result"].payload, ensure_ascii=False)
        for key in (
            "response_windows",
            "agency_profiles",
            "category_distribution",
            "platform_distribution",
        ):
            assert f'"{key}"' in text
