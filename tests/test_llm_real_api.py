"""LLM 真实 API 端到端验证（#601 批次 E 第 22 轮）。

环境门纪律（AGENTS ⑥ / #295 口径）：无 ``DEEPSEEK_API_KEY`` /
``OPENAI_API_KEY`` 时**横幅 SKIP**（不红不静默）——本地研究者的
真连验证面，CI 无 secret 面自动跳过。

只烧一次真实调用（token 纪律）：一条短公告的完整抽取链
（PromptTemplates.bid_extraction → LLMClient.chat_json → 归一）。
"""

import asyncio
import os

import pytest

from src.extract import AnnouncementExtractor
from src.collect import AnnouncementRecord

_BANNER = """
============================================================
SKIP: test_llm_real_api —— 未检测到 DEEPSEEK_API_KEY / OPENAI_API_KEY
  真连验证面：export DEEPSEEK_API_KEY=<key> 后本地重跑即可
  （CI 无 secret 面恒跳过——python-tests.yml 不注入任何 key）
============================================================
"""


def _real_api_available() -> bool:
    return bool(
        os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY")
    )


def _skip_if_no_real_api():
    """仓库横幅门（#295 口径）：无 key → 打印横幅 + skip（不红不静默）。"""
    if not _real_api_available():
        print(_BANNER)
        pytest.skip(_BANNER)


class TestRealAPIExtraction:
    """真实 DeepSeek 兼容 API 的抽取链验证（有 key 才跑）。"""

    def _extractor(self):
        from src.llm.client import LLMClient

        return AnnouncementExtractor(LLMClient())

    def test_real_extraction_chain(self):
        """真连单次调用：短公告 → 结构化抽取 → 归一入库形态。"""
        _skip_if_no_real_api()

        record = AnnouncementRecord.from_raw(
            {
                "bid_id": "REAL-001",
                "project_name": "（占位——以 LLM 抽取为准）",
                "content": (
                    "智慧路灯节能改造项目招标公告。项目预算金额：人民币"
                    " 480万元。发布公告日期：2026年10月18日。"
                    "投标截止时间：2026年11月10日 09:30。"
                    "采购人：某市城市管理局。资格要求：城市照明工程三级"
                    "及以上资质；近三年类似业绩不少于 2 项。"
                ),
            }
        )
        outcome = asyncio.run(self._extractor().extract(record))

        assert outcome.used_llm is True
        fields = outcome.fields
        # 结构断言（宽松——模型输出形态有波动，只卡硬契约）
        assert isinstance(fields, dict)
        name = fields.get("project_name")
        assert name and "路灯" in name, "项目名应从原文抽出"
        budget = fields.get("budget")
        assert budget is None or isinstance(budget, (int, float))
        if budget is not None:
            assert 400 <= budget <= 600, "480 万元量级（±20% 容差）"
        publish = fields.get("publish_date")
        if publish is not None:
            assert publish == "2026-10-18", "日期归一 YYYY-MM-DD"
        requirements = fields.get("requirements")
        if requirements is not None:
            assert isinstance(requirements, list) and len(requirements) >= 1

    def test_real_pipeline_smoke(self):
        """真连管道冒烟：extract 面经真实 API 后整链仍收口。

        单条公告 → 抽取 → 合并（补全不覆盖）→ 报告存在。
        （复用同一条短公告——第二次真实调用）
        """
        _skip_if_no_real_api()

        from tempfile import TemporaryDirectory
        from pathlib import Path

        from src.pipeline import ResearchPipeline
        from src.storage.database import BidDatabase

        with TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "b.db"
            source = Path(tmp) / "ann.json"
            source.write_text(
                '[{"bid_id": "REAL-002", "project_name": "占位项目",'
                ' "content": "防汛物资采购项目招标公告。预算金额：120万元。"'
                "}]",
                encoding="utf-8",
            )
            pipeline = ResearchPipeline(
                db_path, extractor=self._extractor(), output_dir=Path(tmp)
            )
            result = pipeline.run(source)

            extract = result.stage("extract")
            # 真连要么成功（stored>=0——预算字段补全），要么失败进 pending
            # （网络/限流），两种都是管道的正确结局；断言不静默即可
            assert extract.status == "ok"
            assert (
                extract.detail["stored"]
                + extract.detail["llm_failures"]
            ) >= 1
            assert result.report_path.exists()
            with BidDatabase(db_path) as db:
                row = db.get_bid("REAL-002")
            assert row is not None
            if extract.detail["stored"]:
                # 合并面：LLM 补的预算进来（120 万元）
                assert row["budget"] in (None, 120.0, pytest.approx(120.0))
