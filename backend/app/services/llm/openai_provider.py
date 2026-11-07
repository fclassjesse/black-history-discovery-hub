"""OpenAI via the server-side Responses API (PRD default: gpt-6.1-terra). Vision through input_image."""
from __future__ import annotations

import base64
from typing import Any

from app.services.llm.base import ImageInput, parse_json_object


class OpenAIProvider:
    name = "openai"

    def __init__(self, api_key: str, model: str, vision_model: str | None = None):
        from openai import AsyncOpenAI

        self._client = AsyncOpenAI(api_key=api_key)
        self.model = model
        self.vision_model = vision_model or model

    async def complete_json(self, *, system: str, user: str, images: list[ImageInput] | None = None, max_tokens: int = 1500) -> dict[str, Any]:
        content: list[dict[str, Any]] = [{"type": "input_text", "text": user}]
        for img in images or []:
            b64 = base64.b64encode(img.data).decode()
            content.append({"type": "input_image", "image_url": f"data:{img.mime};base64,{b64}"})
        resp = await self._client.responses.create(
            model=self.vision_model if images else self.model,
            instructions=system + "\nRespond with a single JSON object and nothing else.",
            input=[{"role": "user", "content": content}],
            max_output_tokens=max_tokens,
            text={"format": {"type": "json_object"}},
        )
        return parse_json_object(resp.output_text)
