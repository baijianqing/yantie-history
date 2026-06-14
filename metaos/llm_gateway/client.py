"""Minimal DeepSeek-compatible chat gateway.

Business modules should depend on this boundary instead of calling a provider
directly. The concrete model name stays in environment/config.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.request import Request, urlopen

from metaos.core.config import Settings, get_settings
from metaos.core.errors import ConfigurationError


@dataclass(frozen=True)
class ChatMessage:
    role: str
    content: str


@dataclass(frozen=True)
class ChatResult:
    content: str
    model: str
    usage: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "content": self.content,
            "model": self.model,
            "usage": self.usage,
        }


class LLMGateway:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    def chat(self, messages: list[ChatMessage], *, temperature: float = 0.2) -> ChatResult:
        if not self.settings.deepseek_api_key:
            raise ConfigurationError("DEEPSEEK_API_KEY is not configured")

        payload = {
            "model": self.settings.deepseek_model,
            "messages": [message.__dict__ for message in messages],
            "temperature": temperature,
        }
        request = Request(
            f"{self.settings.deepseek_base_url.rstrip('/')}/chat/completions",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.settings.deepseek_api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urlopen(request, timeout=120) as response:
            data: dict[str, Any] = json.loads(response.read().decode("utf-8"))
        choices = data.get("choices") or []
        if not choices:
            raise RuntimeError("LLM response has no choices")
        message = choices[0].get("message") or {}
        return ChatResult(
            content=str(message.get("content") or ""),
            model=str(data.get("model") or self.settings.deepseek_model),
            usage=data.get("usage") or {},
        )

    def chat_text(self, messages: list[ChatMessage], *, temperature: float = 0.2) -> str:
        return self.chat(messages, temperature=temperature).content

    def get_balance(self) -> dict[str, Any]:
        if not self.settings.deepseek_api_key:
            raise ConfigurationError("DEEPSEEK_API_KEY is not configured")

        request = Request(
            f"{self.settings.deepseek_base_url.rstrip('/')}/user/balance",
            headers={
                "Authorization": f"Bearer {self.settings.deepseek_api_key}",
                "Accept": "application/json",
            },
            method="GET",
        )
        with urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
