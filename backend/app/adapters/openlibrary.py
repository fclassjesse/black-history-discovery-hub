"""Open Library bibliographic matching for shelf-scan candidates and the demo partner CSV.

Docs: https://openlibrary.org/developers/api . Keyless; identify with a User-Agent; ≤1 request/second; cached.
Used ONLY to propose bibliographic candidates — never to assert that an institution holds a book.
"""
from __future__ import annotations

import re
from typing import Any

from app.services.http import get_http
from app.services.normalize import ascii_fold, clean

SEARCH_URL = "https://openlibrary.org/search.json"
ISBN_URL = "https://openlibrary.org/isbn/{isbn}.json"
SOURCE = "openlibrary"


def _tokens(s: str | None) -> set[str]:
    if not s:
        return set()
    return {w for w in re.sub(r"[^a-z0-9 ]", " ", ascii_fold(s).lower()).split() if len(w) > 2}


def score_candidate(doc: dict[str, Any], title: str | None, author: str | None, isbn: str | None) -> float:
    """0..1 similarity from token overlap; ISBN hit dominates."""
    if isbn and isbn in [re.sub(r"[^0-9Xx]", "", i) for i in doc.get("isbn", [])]:
        return 0.98
    t_q, t_d = _tokens(title), _tokens(doc.get("title"))
    a_q, a_d = _tokens(author), _tokens(" ".join(doc.get("author_name", [])))
    t = len(t_q & t_d) / len(t_q | t_d) if (t_q or t_d) else 0.0
    a = len(a_q & a_d) / len(a_q | a_d) if (a_q and a_d) else (0.5 if not a_q else 0.0)
    return round(min(1.0, 0.7 * t + 0.3 * a), 2)


def candidate_from_doc(doc: dict[str, Any], score: float) -> dict[str, Any]:
    key = doc.get("key", "")
    return {
        "source": SOURCE,
        "openlibrary_work_key": key,
        "openlibrary_url": f"https://openlibrary.org{key}" if key else None,
        "title": clean(doc.get("title")),
        "authors": [clean(a) for a in doc.get("author_name", []) if clean(a)],
        "first_publish_year": doc.get("first_publish_year"),
        "publishers": [clean(p) for p in doc.get("publisher", [])[:5] if clean(p)],
        "isbns": [i for i in doc.get("isbn", [])[:10]],
        "edition_count": doc.get("edition_count"),
        "editions": [clean(e) for e in doc.get("edition_key", [])[:10]],
        "cover_id": doc.get("cover_i"),
        "score": score,
    }


async def find_candidates(*, title: str | None, author: str | None = None, isbn: str | None = None, limit: int = 5) -> list[dict[str, Any]]:
    http = get_http()
    params: dict[str, Any] = {"limit": str(limit), "fields": "key,title,author_name,first_publish_year,publisher,isbn,edition_count,edition_key,cover_i"}
    if isbn:
        params["isbn"] = re.sub(r"[^0-9Xx]", "", isbn)
    else:
        if title:
            params["title"] = title
        if author:
            params["author"] = author
    if not (isbn or title):
        return []
    res = await http.get(SEARCH_URL, params, source=SOURCE)
    if not res.ok:
        return []
    docs = res.json().get("docs", [])
    cands = [candidate_from_doc(d, score_candidate(d, title, author, isbn)) for d in docs]
    cands.sort(key=lambda c: c["score"], reverse=True)
    return cands[:limit]


async def lookup_isbn(isbn: str) -> dict[str, Any] | None:
    res = await get_http().get(ISBN_URL.format(isbn=re.sub(r"[^0-9Xx]", "", isbn)), source=SOURCE)
    return res.json() if res.ok else None
