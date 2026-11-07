"""Shelf photo → separate book proposals (strict JSON) → Open Library candidates. Nothing is published here."""
from __future__ import annotations

from typing import Any

from app.adapters import openlibrary
from app.services.llm import ImageInput, LLMNotConfigured, get_llm

SYSTEM_PROMPT = """You read photographs of bookshelves for a library partner. Identify each SEPARATE physical book whose spine or
cover is visible. For each book report only what is actually legible: spine text as printed, and, if clearly readable,
the title, author and ISBN. Do NOT guess ISBNs, publishers, or years that are not visible. List uncertainties
(e.g. "author partially hidden", "two volumes may be one set", "text blurred"). Confidence is 0-1 for the item being a
distinct book with a correctly read title. Output exactly one JSON object:
{"items": [{"spine_text": "...", "title": "...|null", "author": "...|null", "isbn": "...|null", "confidence": 0.0, "uncertainties": ["..."]}],
 "notes": "optional short note about image quality"}
"""


async def propose_books(image: bytes, mime: str) -> dict[str, Any]:
    llm = get_llm()  # raises LLMNotConfigured → visible error upstream
    raw = await llm.complete_json(system=SYSTEM_PROMPT, user="Photograph of a bookshelf. List the separate books you can actually read.", images=[ImageInput(image, mime)], max_tokens=2000)
    items = raw.get("items") if isinstance(raw, dict) else None
    if not isinstance(items, list):
        raise ValueError("vision response did not contain an items list")
    cleaned: list[dict[str, Any]] = []
    for it in items[:40]:
        if not isinstance(it, dict):
            continue
        cleaned.append({
            "spine_text": (str(it.get("spine_text") or "").strip() or None),
            "title": (str(it.get("title") or "").strip() or None),
            "author": (str(it.get("author") or "").strip() or None),
            "isbn": (str(it.get("isbn") or "").strip() or None),
            "confidence": max(0.0, min(1.0, float(it.get("confidence") or 0.0))),
            "uncertainties": [str(u) for u in (it.get("uncertainties") or []) if str(u).strip()],
        })
    return {"items": cleaned, "notes": str(raw.get("notes") or "") if isinstance(raw, dict) else "", "model": llm.model}


async def candidates_for(item: dict[str, Any]) -> list[dict[str, Any]]:
    title = item.get("title") or item.get("spine_text")
    if not title and not item.get("isbn"):
        return []
    return await openlibrary.find_candidates(title=title, author=item.get("author"), isbn=item.get("isbn"), limit=5)


__all__ = ["propose_books", "candidates_for", "LLMNotConfigured"]
