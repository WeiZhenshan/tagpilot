"""根据用户首条消息生成简洁会话标题；失败时返回截断原文或「新对话」。"""
from __future__ import annotations

import os
import re
import httpx

SYSTEM = (
    "你是会话标题助手。根据用户第一条消息，生成一个简洁的中文会话标题。"
    "要求：不超过20个字；概括核心意图；不要引号、标点装饰、前后缀或解释；只输出标题本身。"
)
DEFAULT_TITLE = "新对话"
MAX_TITLE = 40


def fallback_title(message: str) -> str:
    text = re.sub(r"\s+", " ", (message or "").strip())
    if not text:
        return DEFAULT_TITLE
    return text[:MAX_TITLE]


def sanitize_title(raw: str, message: str) -> str:
    text = (raw or "").strip()
    text = text.splitlines()[0].strip() if text else ""
    text = re.sub(r"^[\s\"'“”‘’《》【】\[\]]+|[\s\"'“”‘’《》【】\[\]]+$", "", text)
    text = re.sub(r"^(标题|会话标题|名称)[:：\s]+", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    if not text or len(text) > MAX_TITLE:
        return fallback_title(message)
    return text


async def summarize_title(message: str) -> str:
    """调用已配置大模型生成标题；任何失败都回退到截断原文。"""
    fallback = fallback_title(message)
    base = os.getenv("ANTHROPIC_BASE_URL", "")
    key = os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_AUTH_TOKEN") or os.getenv("TAG_LLM_API_KEY", "")
    model = os.getenv("ANTHROPIC_MODEL") or os.getenv("TAG_LLM_MODEL", "deepseek-chat")
    if not base or not key or not message.strip():
        return fallback
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(
                base.rstrip("/") + "/v1/messages",
                headers={"x-api-key": key, "anthropic-version": "2023-06-01"},
                json={
                    "model": model,
                    "max_tokens": 64,
                    "system": SYSTEM,
                    "messages": [{"role": "user", "content": message.strip()[:2000]}],
                },
            )
            response.raise_for_status()
            data = response.json()
            text = "".join(
                block.get("text", "")
                for block in data.get("content", [])
                if block.get("type") == "text"
            )
            return sanitize_title(text, message)
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        return fallback
