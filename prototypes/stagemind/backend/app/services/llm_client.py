"""LLM API 客户端：调用豆包 / DeepSeek 等 OpenAI 兼容接口。

当前为接口占位，W3-W5 填入真实密钥与模型名后即可启用。
"""

from __future__ import annotations

import re

_MARKDOWN_BLOCK = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


def extract_json_from_text(text: str) -> str:
    """清洗 markdown 代码块标记，返回其中的 JSON 文本。

    模型有时会在 JSON 外包一层 ```json 标记，先剥离再解析。
    """
    match = _MARKDOWN_BLOCK.search(text)
    return match.group(1).strip() if match else text.strip()


def call_llm_api(prompt: str, system_prompt: str) -> str:
    """发送对话请求，返回模型原始文本。

    Args:
        prompt: 用户提示词，由 LogStructurer.build_prompt 构造。
        system_prompt: 系统提示词，固定约束输出格式。

    Returns:
        模型返回的原始文本，可能包含 markdown 包裹，需再清洗。
    """
    raise NotImplementedError("W3-W5 接入豆包 / DeepSeek API 后实现")
