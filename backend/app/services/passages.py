"""Description passages: make long catalogue / finding-aid text citable by the guide.

A record with no OCR pages but a description of >= MIN_CHARS characters gets `description` chunks: sentence-aligned
pieces of <= MAX_CHARS, each pointing at the record's own original URL. The guide labels them DESCRIPTION (catalogue
text) — quotable verbatim, but explicitly "what the catalogue says about the item", never the item's own content.
"""
from __future__ import annotations

import re

from app.adapters.base import ChunkIn

MIN_CHARS = 400
MAX_CHARS = 900
MAX_PASSAGES = 8
_SENT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(\[])")


def split_passages(text: str, max_chars: int = MAX_CHARS) -> list[str]:
    sentences = _SENT.split(text.strip())
    out: list[str] = []
    cur = ""
    for s in sentences:
        if not s:
            continue
        if len(s) > max_chars:  # one giant sentence: hard-wrap on word boundaries
            if cur:
                out.append(cur)
                cur = ""
            words = s.split()
            buf = ""
            for w in words:
                if len(buf) + len(w) + 1 > max_chars:
                    out.append(buf)
                    buf = w
                else:
                    buf = f"{buf} {w}".strip()
            if buf:
                cur = buf
            continue
        if len(cur) + len(s) + 1 > max_chars and cur:
            out.append(cur)
            cur = s
        else:
            cur = f"{cur} {s}".strip()
    if cur:
        out.append(cur)
    return out


def description_passages(description: str | None, original_url: str) -> list[ChunkIn]:
    text = (description or "").strip()
    if len(text) < MIN_CHARS:
        return []
    return [
        ChunkIn(chunk_index=i, text=p, page_number=None, page_url=original_url, kind="description")
        for i, p in enumerate(split_passages(text)[:MAX_PASSAGES])
        if len(p) >= 120
    ]
