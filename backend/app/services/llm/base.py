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
            try:
                return json.loads(s[start : end + 1])
            except json.JSONDecodeError:
                pass
        salvaged = salvage_items(s)
        if salvaged is not None:
            return salvaged
        raise


def salvage_items(text: str) -> dict[str, Any] | None:
    """A reply cut off by the token limit ('{"items": [{...}, {...}, {"spine_te') keeps every complete item.
    Returns None when there is no items list to rescue."""
    m = re.search(r'"items"\s*:\s*\[', text)
    if not m:
        return None
    dec = json.JSONDecoder()
    items: list[Any] = []
    i = m.end()
    while i < len(text):
        while i < len(text) and text[i] in " \t\r\n,":
            i += 1
        if i >= len(text) or text[i] != "{":
            break
        try:
            obj, i = dec.raw_decode(text, i)
        except json.JSONDecodeError:
            break
        items.append(obj)
    return {"items": items, "notes": "Reply was cut off; only the books read before the cut are listed.", "truncated": True}
