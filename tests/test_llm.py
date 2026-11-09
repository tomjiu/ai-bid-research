"""src/llm 模块单元测试。

全部通过 AsyncMock 替换底层 OpenAI 客户端，不发起真实网络请求。
"""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.llm.client import LLMClient, LLMError
from src.llm.prompts import PromptTemplates


def make_mock_response(content: str) -> MagicMock:
    """构造模拟的 OpenAI ChatCompletion 响应对象。

    Args:
        content: 模拟的回复文本。

    Returns:
        形如 ``response.choices[0].message.content`` 的 mock 对象。
    """
    response = MagicMock()
    response.choices = [MagicMock()]
    response.choices[0].message.content = content
    return response


class TestLLMClient:
    """LLMClient 行为测试。"""

    def setup_method(self) -> None:
        self.client = LLMClient(api_key="test-key")

    def test_chat_success(self) -> None:
        """chat 正常返回模型回复文本。"""
        mock_response = make_mock_response("你好，这是分析结果。")
        with patch.object(self.client, "_client") as mock_openai:
            mock_openai.chat.completions.create = AsyncMock(return_value=mock_response)
            result = asyncio.run(
                self.client.chat([{"role": "user", "content": "你好"}])
            )
        assert result == "你好，这是分析结果。"
        mock_openai.chat.completions.create.assert_awaited_once()

    def test_chat_retries_on_failure(self) -> None:
        """chat 在失败时自动重试并最终成功。"""
        mock_response = make_mock_response("ok")
        with patch.object(self.client, "_client") as mock_openai, patch(
            "src.llm.client.asyncio.sleep", new_callable=AsyncMock
        ) as mock_sleep:
            create = AsyncMock(
                side_effect=[
                    ConnectionError("网络抖动"),
                    TimeoutError("超时"),
                    mock_response,
                ]
            )
            mock_openai.chat.completions.create = create
            result = asyncio.run(
                self.client.chat([{"role": "user", "content": "重试我"}])
            )
        assert result == "ok"
        assert create.await_count == 3
        # 指数退避：两次失败各触发一次 sleep
        assert mock_sleep.await_count >= 2

    def test_chat_retry_exhausted_raises_llm_error(self) -> None:
        """重试耗尽后抛出 LLMError。"""
        with patch.object(self.client, "_client") as mock_openai, patch(
            "src.llm.client.asyncio.sleep", new_callable=AsyncMock
        ):
            mock_openai.chat.completions.create = AsyncMock(
                side_effect=ConnectionError("一直失败")
            )
            with pytest.raises(LLMError, match="3 次重试"):
                asyncio.run(
                    self.client.chat([{"role": "user", "content": "必败"}])
                )

    def test_chat_json_plain_response(self) -> None:
        """chat_json 解析纯 JSON 回复。"""
        payload = {"project_name": "智慧园区平台", "budget": 350.0}
        mock_response = make_mock_response(
            json.dumps(payload, ensure_ascii=False)
        )
        with patch.object(self.client, "_client") as mock_openai:
            mock_openai.chat.completions.create = AsyncMock(return_value=mock_response)
            result = asyncio.run(
                self.client.chat_json([{"role": "user", "content": "抽取"}])
            )
        assert result == payload
        # 确认启用了 JSON mode
        call_kwargs = mock_openai.chat.completions.create.await_args.kwargs
        assert call_kwargs["response_format"] == {"type": "json_object"}

    def test_chat_json_markdown_code_block(self) -> None:
        """chat_json 能从 markdown 代码块中兜底提取 JSON。"""
        wrapped = "分析结果如下：\n```json\n{\"a\": 1, \"b\": [2, 3]}\n```\n以上。"
        mock_response = make_mock_response(wrapped)
        with patch.object(self.client, "_client") as mock_openai:
            mock_openai.chat.completions.create = AsyncMock(return_value=mock_response)
            result = asyncio.run(
                self.client.chat_json([{"role": "user", "content": "抽取"}])
            )
        assert result == {"a": 1, "b": [2, 3]}

    def test_chat_json_invalid_content_raises(self) -> None:
        """完全无法解析出 JSON 时抛出 LLMError。"""
        mock_response = make_mock_response("抱歉，我无法完成该任务。")
        with patch.object(self.client, "_client") as mock_openai:
            mock_openai.chat.completions.create = AsyncMock(return_value=mock_response)
            with pytest.raises(LLMError, match="无法从 LLM 回复中解析出 JSON"):
                asyncio.run(
                    self.client.chat_json([{"role": "user", "content": "抽取"}])
                )

    def test_batch_chat_preserves_order(self) -> None:
        """batch_chat 并发调用且结果顺序与输入一致。"""
        replies = ["回复一", "回复二", "回复三"]

        async def fake_chat(messages, **kwargs):  # noqa: ANN001, ANN003
            return replies[len(fake_chat.calls)]

        fake_chat.calls = 0
        with patch.object(self.client, "chat", side_effect=None):
            with patch.object(
                self.client,
                "chat",
                new=AsyncMock(side_effect=replies),
            ) as mock_chat:
                result = asyncio.run(
                    self.client.batch_chat(
                        [
                            [{"role": "user", "content": "问题1"}],
                            [{"role": "user", "content": "问题2"}],
                            [{"role": "user", "content": "问题3"}],
                        ]
                    )
                )
        assert result == replies
        assert mock_chat.await_count == 3

    def test_invalid_config_raises(self) -> None:
        """非法并发数/速率限制配置被拒绝。"""
        with pytest.raises(ValueError):
            LLMClient(api_key="k", max_concurrent=0)
        with pytest.raises(ValueError):
            LLMClient(api_key="k", rate_limit=0)


class TestPromptTemplates:
    """提示词模板内容测试。"""

    def test_bid_extraction_template(self) -> None:
        """抽取模板包含公告原文与 JSON 字段要求。"""
        template = PromptTemplates.bid_extraction("某市政智慧交通项目招标公告全文")
        assert "某市政智慧交通项目招标公告全文" in template
        assert "JSON" in template
        assert "project_name" in template

    def test_bid_analysis_template(self) -> None:
        """单项目分析模板包含项目信息与报告小节要求。"""
        template = PromptTemplates.bid_analysis('{"project_name": "测试项目"}')
        assert "测试项目" in template
        assert "投标建议" in template

    def test_competitor_analysis_template(self) -> None:
        """竞争分析模板包含关键词与项目清单。"""
        template = PromptTemplates.competitor_analysis(
            keyword="智慧园区", bid_list="项目A；项目B"
        )
        assert "智慧园区" in template
        assert "项目A；项目B" in template
        assert "竞争态势" in template or "格局" in template

    def test_report_generation_template(self) -> None:
        """报告生成模板包含分析数据与结构要求。"""
        template = PromptTemplates.report_generation('{"summary": "市场火热"}')
        assert "市场火热" in template
        assert "结论与建议" in template
        assert "Markdown" in template

    def test_get_all_templates(self) -> None:
        """get_all_templates 返回全部四个模板。"""
        templates = PromptTemplates.get_all_templates()
        assert set(templates.keys()) == {
            "bid_extraction",
            "bid_analysis",
            "competitor_analysis",
            "report_generation",
        }
        assert all(callable(t) for t in templates.values())
