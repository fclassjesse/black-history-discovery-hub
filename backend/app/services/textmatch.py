"""Whole-word, plural-tolerant query matching used by connectors that have no server-side relevance control
(OAI-PMH harvests, Wikimedia Commons full-text search). Keeps results on topic: every significant query word
must appear as a whole word in the record's own text, so "Black" never matches "Blackmore" and a photo that
merely mentions "Black History Month" does not pass for "Black Canadians history"."""
from __future__ import annotations

import re

from app.services.normalize import ascii_fold

STOPWORDS = {"the", "and", "of", "in", "on", "at", "to", "for", "a", "an", "nova", "scotia", "history", "canada", "canadian"}


def query_terms(query: str) -> list[str]:
    words = re.findall(r"[a-z0-9]+", ascii_fold(query).lower())
    return [w for w in words if len(w) > 2 and w not in STOPWORDS] or [w for w in words if len(w) > 2]


def term_pattern(term: str) -> re.Pattern[str]:
    stem = term[:-1] if term.endswith("s") and len(term) > 4 else term
    return re.compile(rf"(?<![a-z0-9]){re.escape(stem)}(?:s|es)?(?![a-z0-9])")


def text_matches(text: str, query: str) -> bool:
    terms = query_terms(query)
    if not terms:
        return False
    folded = ascii_fold(text).lower()
    return all(term_pattern(t).search(folded) for t in terms)


# Government data portals (CKAN, Socrata) rank by loose full-text match, so "Black Nova Scotians" also returns
# payday-lender licences, black carbon and the Scotian Shelf. A dataset from those portals must also name Black
# people or communities in its own title, tags or (short) description before it is stored.
TOPIC_GATE = re.compile(
    r"\b(black (canadian|communit|people|person|individual|youth|wom[ae]n|m[ae]n|famil|nova scotian|histor|loyalist|refugee|justice|social|business|entrepreneur|student|heritage|culture|settle)"
    r"|african[- ](canadian|nova scotian|descent|heritage)|people of african descent|anti-black|africville|book of negroes"
    r"|construction battalion|underground railroad|slavery|enslave)",
    re.I,
)


def on_black_history_topic(text: str) -> bool:
    return bool(TOPIC_GATE.search(text or ""))
