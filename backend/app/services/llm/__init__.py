from __future__ import annotations

from app.config import get_settings
from app.services.llm.base import ImageInput, LLMNotConfigured, LLMProvider  # noqa: F401
from app.services.llm.fake_provider import FakeProvider

_override: LLMProvider | None = None
_cached: LLMProvider | None = None
_cached_key: str | None = None


def set_provider_override(p: LLMProvider | None) -> None:
    """Tests inject a FakeProvider here."""
    global _override
    _override = p


def provider_info() -> dict:
    s = get_settings()
    name = s.resolved_llm_provider()
    if _override is not None:
        return {"name": _override.name, "model": _override.model, "configured": True}
    if name == "openai":
        return {"name": "openai", "model": s.openai_model, "configured": bool(s.openai_api_key)}
    if name == "anthropic":
        return {"name": "anthropic", "model": s.anthropic_model, "configured": bool(s.anthropic_api_key)}
    if name == "fake":
        return {"name": "fake", "model": "fake-scripted", "configured": True}
    return {"name": "none", "model": None, "configured": False}


def get_llm() -> LLMProvider:
    global _cached, _cached_key
    if _override is not None:
        return _override
    s = get_settings()
    name = s.resolved_llm_provider()
    key = f"{name}:{s.openai_model}:{s.anthropic_model}"
    if _cached is not None and _cached_key == key:
        return _cached
    if name == "openai" and s.openai_api_key:
        from app.services.llm.openai_provider import OpenAIProvider

        _cached = OpenAIProvider(s.openai_api_key, s.openai_model, s.openai_vision_model)
    elif name == "anthropic" and s.anthropic_api_key:
        from app.services.llm.anthropic_provider import AnthropicProvider

        _cached = AnthropicProvider(s.anthropic_api_key, s.anthropic_model)
    elif name == "fake":
        _cached = FakeProvider()
    else:
        raise LLMNotConfigured("No AI provider configured. Set OPENAI_API_KEY (PRD default) or ANTHROPIC_API_KEY.")
    _cached_key = key
    return _cached
