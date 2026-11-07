"""Work keys: identifiers that say two catalogue records describe the same work (relationship mapping).

Keys: isbn:<isbn13>, oclc:<digits>, lccn:<normalised>, dedupe:<title|creator|year>. Records sharing ANY key are
shown to each other as "also catalogued at". Deterministic; nothing is inferred beyond the identifiers the sources gave.
"""
from __future__ import annotations

import re
from typing import Any

from app.services.normalize import dedupe_key


def isbn13(raw: str) -> str | None:
    s = re.sub(r"[^0-9Xx]", "", raw or "").upper()
    if len(s) == 10:
        core = "978" + s[:9]
        if not core.isdigit():
            return None
        check = (10 - sum(int(d) * (1 if i % 2 == 0 else 3) for i, d in enumerate(core)) % 10) % 10
        return core + str(check)
    if len(s) == 13 and s.isdigit():
        return s
    return None


def _values(v: Any) -> list[str]:
    if v is None:
        return []
    if isinstance(v, (list, tuple)):
        return [str(x) for x in v if x is not None]
    return [str(v)]


def work_keys_for(identifiers: dict[str, Any] | None, raw_metadata: dict[str, Any] | None, title: str | None, creators: list[str] | None, year: int | None) -> list[str]:
    keys: list[str] = []
    ids = identifiers or {}
    raw = raw_metadata or {}
    for src in (ids, raw):
        for field in ("isbn", "isbn13", "isbn10"):
            for v in _values(src.get(field)):
                k = isbn13(v)
                if k:
                    keys.append(f"isbn:{k}")
        for v in _values(src.get("oclc")) + _values(src.get("oclc_number")) + _values(src.get("oclc-id")):
            digits = re.sub(r"\D", "", v.split(")")[-1])
            if digits:
                keys.append(f"oclc:{digits.lstrip('0') or '0'}")
        for v in _values(src.get("lccn")):
            n = re.sub(r"[\s-]", "", v).lower()
            if n:
                keys.append(f"lccn:{n}")
    d = dedupe_key(title, creators, year)
    if d:
        keys.append(f"dedupe:{d}")
    return list(dict.fromkeys(keys))
