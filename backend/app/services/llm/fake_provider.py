"""Scripted provider for tests. Push responses (dicts or callables) in order."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.services.llm.base import ImageInput


class FakeProvider:
    name = "fake"
    model = "fake-scripted"

    def __init__(self) -> None:
        self.responses: list[dict[str, Any] | Callable[[str, str], dict[str, Any]]] = []
        self.calls: list[dict[str, Any]] = []

    def push(self, *responses: dict[str, Any] | Callable[[str, str], dict[str, Any]]) -> None:
        self.responses.extend(responses)

    async def complete_json(self, *, system: str, user: str, images: list[ImageInput] | None = None, max_tokens: int = 1500) -> dict[str, Any]:
        self.calls.append({"system": system, "user": user, "images": len(images or [])})
        if not self.responses:
            raise RuntimeError("FakeProvider has no scripted response left")
        nxt = self.responses.pop(0)
        return nxt(system, user) if callable(nxt) else nxt
