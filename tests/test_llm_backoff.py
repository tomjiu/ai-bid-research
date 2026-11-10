"""LLM 重试退避纪律测试（#601 R59）——分类/退避/抖动/上限四线。"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.llm.client import LLMClient, LLMError

pytestmark = pytest.mark.asyncio


def _client(**kw) -> LLMClient:
    """构造不发真网络请求的客户端（create 走 mock）。"""
    client = LLMClient(api_key="k", retry_jitter=False, **kw)
    return client


def _ok_response(text: str = "ok"):
    resp = MagicMock()
    resp.choices = [MagicMock()]
    resp.choices[0].message.content = text
    return resp


class _HTTPError(Exception):
    """带状态码/响应头的伪 API 异常（openai.APIStatusError 形态）。"""

    def __init__(self, status: int, retry_after: str | None = None):
        super().__init__(f"HTTP {status}")
        self.status_code = status
        self.response = MagicMock()
        self.response.headers = (
            {"retry-after": retry_after} if retry_after else {}
        )


def _wire(client: LLMClient, side_effects: list):
    """替换底层 create 为逐次 side_effect 序列。"""
    client._client.chat.completions.create = AsyncMock(side_effect=side_effects)


class TestRetryClassification:
    async def test_401_fails_fast_single_attempt(self):
        client = _client()
        _wire(client, [_HTTPError(401)])
        with pytest.raises(LLMError, match="不可重试"):
            await client._chat_with_retry(
                [{"role": "user", "content": "x"}],
                temperature=0.0,
                max_tokens=10,
                max_retries=3,
            )
        # 确定性失败只试一次——不浪费两次重试
        assert client._client.chat.completions.create.await_count == 1

    async def test_404_model_not_found_fails_fast(self):
        client = _client()
        _wire(client, [_HTTPError(404)])
        with pytest.raises(LLMError, match="HTTP 404"):
            await client._chat_with_retry(
                [{"role": "user", "content": "x"}],
                temperature=0.0, max_tokens=10, max_retries=5,
            )
        assert client._client.chat.completions.create.await_count == 1

    async def test_500_retryable_eventually_succeeds(self):
        client = _client()
        _wire(
            client,
            [_HTTPError(500), _HTTPError(503), _ok_response("恢复")],
        )
        out = await client._chat_with_retry(
            [{"role": "user", "content": "x"}],
            temperature=0.0, max_tokens=10, max_retries=3,
        )
        assert out == "恢复"
        assert client._client.chat.completions.create.await_count == 3


class TestBackoffTiming:
    async def test_exponential_delays_no_jitter(self):
        client = _client()
        _wire(client, [_HTTPError(429), _HTTPError(429), _ok_response()])
        sleeps: list[float] = []

        async def fake_sleep(sec):
            sleeps.append(sec)

        import src.llm.client as client_mod

        orig = client_mod.asyncio.sleep
        client_mod.asyncio.sleep = fake_sleep
        try:
            out = await client._chat_with_retry(
                [{"role": "user", "content": "x"}],
                temperature=0.0, max_tokens=10, max_retries=3,
            )
        finally:
            client_mod.asyncio.sleep = orig
        assert out == "ok"
        assert sleeps == [1.0, 2.0]  # 纯指数（INITIAL=1.0）

    async def test_retry_after_header_respected(self):
        client = _client()
        _wire(
            client,
            [_HTTPError(429, retry_after="7"), _ok_response()],
        )
        sleeps: list[float] = []

        async def fake_sleep(sec):
            sleeps.append(sec)

        import src.llm.client as client_mod

        orig = client_mod.asyncio.sleep
        client_mod.asyncio.sleep = fake_sleep
        try:
            await client._chat_with_retry(
                [{"role": "user", "content": "x"}],
                temperature=0.0, max_tokens=10, max_retries=3,
            )
        finally:
            client_mod.asyncio.sleep = orig
        assert sleeps == [7.0]  # 服务端明示等待优先于本地指数

    async def test_jitter_bounds_equal_jitter(self, monkeypatch):
        """等抖动：delay/2 + U(0, delay/2)——uniform 取边界验证公式。"""
        import src.llm.client as client_mod

        client = LLMClient(api_key="k", retry_jitter=True)
        _wire(client, [_HTTPError(429), _ok_response()])
        sleeps: list[float] = []

        async def fake_sleep(sec):
            sleeps.append(sec)

        monkeypatch.setattr(client_mod.asyncio, "sleep", fake_sleep)
        # uniform 取上界 → wait = 0.5 + 0.5 = 1.0
        monkeypatch.setattr(
            client_mod.random, "uniform", lambda a, b: b
        )
        await client._chat_with_retry(
            [{"role": "user", "content": "x"}],
            temperature=0.0, max_tokens=10, max_retries=2,
        )
        assert sleeps == [1.0]
        # uniform 取下界 → wait = 0.5
        client2 = LLMClient(api_key="k", retry_jitter=True)
        _wire(client2, [_HTTPError(429), _ok_response()])
        sleeps.clear()
        monkeypatch.setattr(
            client_mod.random, "uniform", lambda a, b: a
        )
        await client2._chat_with_retry(
            [{"role": "user", "content": "x"}],
            temperature=0.0, max_tokens=10, max_retries=2,
        )
        assert sleeps == [0.5]

    async def test_delay_capped_at_max(self):
        """大 retries 时指数封顶 MAX_RETRY_DELAY=30。"""
        client = _client()
        effects = [_HTTPError(429)] * 7 + [_ok_response()]
        _wire(client, effects)
        sleeps: list[float] = []

        async def fake_sleep(sec):
            sleeps.append(sec)

        import src.llm.client as client_mod

        orig = client_mod.asyncio.sleep
        client_mod.asyncio.sleep = fake_sleep
        try:
            await client._chat_with_retry(
                [{"role": "user", "content": "x"}],
                temperature=0.0, max_tokens=10, max_retries=8,
            )
        finally:
            client_mod.asyncio.sleep = orig
        assert sleeps == [1.0, 2.0, 4.0, 8.0, 16.0, 30.0, 30.0]


class TestMaxRetriesSemantics:
    async def test_zero_means_single_attempt(self):
        """显式 0 = 只试一次不重试（原 ``or`` 会吞 0 成默认 3——R59 修正）。"""
        client = _client()
        _wire(client, [_HTTPError(429)])
        with pytest.raises(LLMError):
            await client._chat_with_retry(
                [{"role": "user", "content": "x"}],
                temperature=0.0, max_tokens=10, max_retries=0,
            )
        assert client._client.chat.completions.create.await_count == 1

    async def test_none_means_default_three(self):
        client = _client()
        _wire(client, [_HTTPError(429)] * 3)
        with pytest.raises(LLMError):
            await client._chat_with_retry(
                [{"role": "user", "content": "x"}],
                temperature=0.0, max_tokens=10,
            )
        assert client._client.chat.completions.create.await_count == 3

    async def test_exhausted_error_mentions_attempts(self):
        client = _client()
        _wire(client, [_HTTPError(429)] * 3)
        with pytest.raises(LLMError, match="3 次尝试后仍失败"):
            await client._chat_with_retry(
                [{"role": "user", "content": "x"}],
                temperature=0.0, max_tokens=10, max_retries=3,
            )
