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


class LLMGateway:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    def chat(self, messages: list[ChatMessage], *, temperature: float = 0.2) -> str:
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
        return str(message.get("content") or "")
