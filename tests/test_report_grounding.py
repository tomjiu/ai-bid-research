"""LLM 叙述报告统计锚定测试（#601 批次 F 第 25 轮）。"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.report.generator import ReportGenerator
from src.storage.database import BidDatabase


@pytest.fixture()
def db(tmp_path):
    path = tmp_path / "b.db"
    with BidDatabase(path) as conn:
        conn.import_bids(
            [
                {
                    "bid_id": "G-1", "project_name": "智慧城市一期",
                    "budget": 300.0, "publish_date": "2026-10-01",
                    "region": "浙江",
                },
                {
                    "bid_id": "G-2", "project_name": "智慧城市二期",
                    "budget": 500.0, "publish_date": "2026-10-05",
                    "region": "浙江",
                },
            ]
        )
    return path


def _mock_generator(db_path, tmp_path) -> ReportGenerator:
    """LLM chat 被 mock 的生成器（db 连接由调用方生命周期兜底）。"""
    generator = ReportGenerator(
        llm_client=MagicMock(), output_dir=tmp_path / "r", db=None
    )
    generator.llm.chat = AsyncMock(return_value="模型叙述内容。")
    # 注入 db（绕过构造器以便 mock llm——研究工具单测口径）；
    # 连接不提前关闭：with 块会在 helper 返回时把库关死
    generator.db = BidDatabase(db_path)
    return generator


class TestGroundingBlock:
    """统计锚定面。"""

    def test_prompt_contains_facts(self, db, tmp_path):
        """送入 LLM 的提示词含权威统计块（中位/密度/定标率）。"""
        generator = _mock_generator(db, tmp_path)
        path = asyncio.run(
            generator.generate_competition_report("智慧城市", days=90)
        )
        messages = generator.llm.chat.await_args.args[0]
        user_text = next(m["content"] for m in messages if m["role"] == "user")
        assert "已计算统计事实" in user_text
        assert "中位 300.0" in user_text  # 300/500 的中位
        assert "样本：2 条记录" in user_text
        assert "叙述不得与之冲突" in user_text
        assert path.exists()

    def test_empty_db_no_facts_block(self, tmp_path):
        """库内无命中 → 无事实块，退化为缺口口径。"""
        path = tmp_path / "empty.db"
        with BidDatabase(path):
            pass
        generator = _mock_generator(path, tmp_path)
        asyncio.run(
            generator.generate_competition_report("无命中关键词", days=90)
        )
        messages = generator.llm.chat.await_args.args[0]
        user_text = next(m["content"] for m in messages if m["role"] == "user")
        assert "已计算统计事实" not in user_text
        assert "数据缺口" in user_text
