"""Anthropic Messages API (claude-sonnet-5-5 by default; vision-capable)."""
from __future__ import annotations

import base64
from typing import Any

from app.services.llm.base import ImageInput, parse_json_object


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, api_key: str, model: str):
        from anthropic import AsyncAnthropic

        self._client = AsyncAnthropic(api_key=api_key)
        self.model = model

    async def complete_json(self, *, system: str, user: str, images: list[ImageInput] | None = None, max_tokens: int = 1500) -> dict[str, Any]:
        content: list[dict[str, Any]] = []
        for img in images or []:
            content.append({"type": "image", "source": {"type": "base64", "media_type": img.mime, "data": base64.b64encode(img.data).decode()}})
        content.append({"type": "text", "text": user})
        msg = await self._client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system + "\nRespond with a single JSON object and nothing else — no prose, no code fences.",
            messages=[{"role": "user", "content": content}],
        )
        text = "".join(block.text for block in msg.content if getattr(block, "type", "") == "text")
        return parse_json_object(text)
