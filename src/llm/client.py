"""LLM 客户端封装模块。

基于 OpenAI 兼容接口（DeepSeek）的异步 LLM 调用封装，
提供并发控制、速率限制、指数退避重试与 JSON 解析能力。
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
from typing import Any, Dict, List, Optional, Sequence

from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

# 匹配 markdown 代码块包裹的 JSON（```json ... ``` 或 ``` ... ```）
_JSON_CODE_BLOCK_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


class LLMError(Exception):
    """LLM 调用或解析过程中的异常。"""


class LLMClient:
    """异步 LLM 客户端，封装 DeepSeek 兼容的 OpenAI 接口。

    特性：
        - 信号量并发控制（默认同时 5 个请求）
        - 相邻请求间速率限制（默认 0.5 秒）
        - 指数退避自动重试（默认 3 次）
        - JSON mode 调用与正则兜底提取

    Attributes:
        model: 使用的模型名称。
        max_concurrent: 最大并发请求数。
        rate_limit: 相邻两个请求之间的最小间隔（秒）。
    """

    DEFAULT_MAX_RETRIES = 3
    INITIAL_RETRY_DELAY = 1.0

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: str = "deepseek-chat",
        max_concurrent: int = 5,
        rate_limit: float = 0.5,
    ) -> None:
        """初始化 LLM 客户端。

        Args:
            api_key: API 密钥；缺省时依次读取环境变量
                ``DEEPSEEK_API_KEY``、``OPENAI_API_KEY``。
            base_url: API 基础地址；缺省时读取 ``DEEPSEEK_BASE_URL``，
                再缺省为 DeepSeek 官方地址。
            model: 模型名称。
            max_concurrent: 最大并发请求数。
            rate_limit: 相邻请求之间的最小间隔（秒）。

        Raises:
            ValueError: 当 ``max_concurrent`` 或 ``rate_limit`` 非正时。
        """
        if max_concurrent <= 0:
            raise ValueError(f"max_concurrent 必须为正数，收到 {max_concurrent}")
        if rate_limit <= 0:
            raise ValueError(f"rate_limit 必须为正数，收到 {rate_limit}")

        self.api_key = (
            api_key
            or os.getenv("DEEPSEEK_API_KEY")
            or os.getenv("OPENAI_API_KEY")
            or "EMPTY"
        )
        self.base_url = (
            base_url
            or os.getenv("DEEPSEEK_BASE_URL")
            or "https://api.deepseek.com"
        )
        self.model = model
        self.max_concurrent = max_concurrent
        self.rate_limit = rate_limit
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._rate_lock = asyncio.Lock()
        self._last_request_time = 0.0
        self._client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)

    # ------------------------------------------------------------------
    # 核心调用
    # ------------------------------------------------------------------

    async def chat(
        self,
        messages: Sequence[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2048,
        response_format: Optional[Dict[str, Any]] = None,
    ) -> str:
        """发送单次对话请求并返回模型回复文本。

        受信号量并发约束与速率限制保护，失败时自动指数退避重试。

        Args:
            messages: OpenAI 格式的消息列表。
            temperature: 采样温度。
            max_tokens: 回复最大 token 数。
            response_format: 可选的响应格式（如 ``{"type": "json_object"}``）。

        Returns:
            模型回复文本。

        Raises:
            LLMError: 重试耗尽仍失败时。
        """
        async with self._semaphore:
            await self._respect_rate_limit()
            return await self._chat_with_retry(
                messages,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format=response_format,
            )

    async def chat_json(
        self,
        messages: Sequence[Dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 2048,
    ) -> Any:
        """发送请求并将回复解析为 JSON 对象。

        优先使用 JSON mode（``response_format=json_object``）；
        解析阶段带正则兜底：即使回复包裹在 markdown 代码块中也能提取。

        Args:
            messages: OpenAI 格式的消息列表。
            temperature: 采样温度（JSON 场景默认更低）。
            max_tokens: 回复最大 token 数。

        Returns:
            解析后的 Python 对象（通常是 dict）。

        Raises:
            LLMError: 调用失败或无法解析出 JSON 时。
        """
        content = await self.chat(
            messages,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
        )
        return self._extract_json(content)

    async def batch_chat(
        self,
        messages_list: Sequence[Sequence[Dict[str, str]]],
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> List[str]:
        """并发批量调用 ``chat``，返回与输入顺序一致的回复列表。

        并发上限由 ``max_concurrent`` 信号量控制。

        Args:
            messages_list: 多组消息列表。
            temperature: 采样温度。
            max_tokens: 回复最大 token 数。

        Returns:
            按输入顺序排列的回复文本列表。
        """
        tasks = [
            self.chat(messages, temperature=temperature, max_tokens=max_tokens)
            for messages in messages_list
        ]
        return list(await asyncio.gather(*tasks))

    async def close(self) -> None:
        """关闭底层 HTTP 客户端，释放连接资源。"""
        await self._client.close()

    # ------------------------------------------------------------------
    # 内部实现
    # ------------------------------------------------------------------

    async def _respect_rate_limit(self) -> None:
        """在速率限制窗口内等待，确保相邻请求间隔不小于 ``rate_limit`` 秒。"""
        async with self._rate_lock:
            now = time.monotonic()
            wait = self._last_request_time + self.rate_limit - now
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_request_time = time.monotonic()

    async def _chat_with_retry(
        self,
        messages: Sequence[Dict[str, str]],
        temperature: float,
        max_tokens: int,
        response_format: Optional[Dict[str, Any]] = None,
        max_retries: Optional[int] = None,
    ) -> str:
        """带指数退避重试的单次调用。

        Args:
            messages: OpenAI 格式的消息列表。
            temperature: 采样温度。
            max_tokens: 回复最大 token 数。
            response_format: 可选的响应格式。
            max_retries: 最大尝试次数；缺省为 ``DEFAULT_MAX_RETRIES``。

        Returns:
            模型回复文本。

        Raises:
            LLMError: 重试耗尽仍失败时。
        """
        retries = max_retries or self.DEFAULT_MAX_RETRIES
        delay = self.INITIAL_RETRY_DELAY
        last_exc: Optional[BaseException] = None

        for attempt in range(1, retries + 1):
            try:
                kwargs: Dict[str, Any] = {
                    "model": self.model,
                    "messages": list(messages),
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                }
                if response_format is not None:
                    kwargs["response_format"] = response_format
                response = await self._client.chat.completions.create(**kwargs)
                return response.choices[0].message.content or ""
            except Exception as exc:  # noqa: BLE001 - 网络/限流等均可重试
                last_exc = exc
                logger.warning(
                    "LLM 调用失败（第 %d/%d 次尝试）: %s", attempt, retries, exc
                )
                if attempt < retries:
                    await asyncio.sleep(delay)
                    delay *= 2

        raise LLMError(
            f"LLM 调用在 {retries} 次重试后仍失败: {last_exc}"
        ) from last_exc

    @classmethod
    def _extract_json(cls, content: str) -> Any:
        """从模型回复文本中提取 JSON。

        依次尝试：直接 ``json.loads`` → markdown 代码块提取 →
        首个花括号/方括号片段提取。

        Args:
            content: 模型回复文本。

        Returns:
            解析后的 Python 对象。

        Raises:
            LLMError: 所有策略均无法解析出合法 JSON 时。
        """
        # 策略 1：整体直接解析
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass

        # 策略 2：markdown 代码块内容
        match = _JSON_CODE_BLOCK_RE.search(content)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

        # 策略 3：首个 {...} 或 [...] 片段
        bracket_match = re.search(r"(\{.*\}|\[.*\])", content, re.DOTALL)
        if bracket_match:
            try:
                return json.loads(bracket_match.group(1))
            except json.JSONDecodeError:
                pass

        raise LLMError(
            "无法从 LLM 回复中解析出 JSON，回复前 200 字符: "
            f"{content[:200]!r}"
        )
