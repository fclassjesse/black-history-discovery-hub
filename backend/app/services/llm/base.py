from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Protocol


class LLMNotConfigured(Exception):
    pass


@dataclass
class ImageInput:
    data: bytes
    mime: str


class LLMProvider(Protocol):
    name: str
    model: str

    async def complete_json(self, *, system: str, user: str, images: list[ImageInput] | None = None, max_tokens: int = 1500) -> dict[str, Any]: ...


def parse_json_object(text: str) -> dict[str, Any]:
    """Tolerant JSON extraction: strips code fences and leading prose."""
    s = text.strip()
    s = re.sub(r"^```(?:json)?\s*", "", s)
    s = re.sub(r"\s*```$", "", s)
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        start, end = s.find("{"), s.rfind("}")
        if start >= 0 and end > start:
            return json.loads(s[start : end + 1])
        raise
