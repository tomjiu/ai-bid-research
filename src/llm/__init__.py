"""LLM 调用封装模块（非生产链路——仅供研究，见 docs/PYTHON-BOUNDARY.md）。

提供基于 DeepSeek 兼容 OpenAI 接口的异步客户端与提示词模板。
"""

from src.llm.client import LLMClient, LLMError
from src.llm.prompts import PromptTemplates

__all__ = ["LLMClient", "LLMError", "PromptTemplates"]
