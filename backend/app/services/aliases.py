"""Query expansion from fixtures/aliases.yaml (natural-language mode only; Advanced Search never uses it).

Each group lists names for the same place / people / topic across institutions and languages, canonical English
first, canonical French second. Matching ignores case and accents, so "neo-ecossais" finds "Néo-Écossais".
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

from app.config import BACKEND_ROOT
from app.services.normalize import ascii_fold


def _norm(s: str) -> str:
    return ascii_fold(s).lower()


@lru_cache
def alias_groups() -> list[list[str]]:
    p = Path(BACKEND_ROOT) / "fixtures" / "aliases.yaml"
    if not p.exists():
        return []
    data = yaml.safe_load(p.read_text()) or {}
    return [[str(x) for x in g] for g in data.get("groups", [])]


def expand(query: str, max_variants: int = 4) -> list[str]:
    """Returns the original query plus alias phrases for any group name found in it, in group order."""
    q = _norm(query)
    variants: list[str] = []
    for group in alias_groups():
        if any(_norm(term) in q for term in group):
            for term in group:
                if _norm(term) not in q and term not in variants:
                    variants.append(term)
    return [query] + variants[: max_variants - 1]
