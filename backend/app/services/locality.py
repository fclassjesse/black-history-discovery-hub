"""Where is the person asking from? "I'm a student at Saint Mary's" → Nova Scotia, so local holdings come first.

Deterministic, no LLM: a self-introduction trigger ("I'm a student from", "I live in", "je suis étudiante à") followed
within a few words by a known place or campus. The introduction is cut out of the search text (it is about the
person, not the topic: "student" and "Saint Mary's" must not become search terms), and the region is returned so
search can rank holders and records from that region first and the map can open there instead of on whichever
holder has the most matches (often Harvard, near Boston).

Without an introduction, a strong place name anywhere in the question ("Black churches in Nova Scotia") also sets
the region but stays in the search text. Short or ambiguous names (NS, SMU, Dal) only count after an introduction.
"""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# How far into the relevance order local results are pulled forward. Search looks deep (a Nova Scotia Archives
# document can sit at rank ~90 behind dozens of US library copies of the same books); the guide's 12-record evidence
# pack looks shallower so a weak local match never displaces the best answer material.
SEARCH_WINDOW = 100
GUIDE_WINDOW = 40
# How far after the introduction trigger the place may appear ("I'm a second-year history student at ...").
INTRO_REACH = 70


@dataclass(frozen=True)
class Region:
    key: str
    label: str
    label_fr: str
    regions: tuple[str, ...]  # institutions.region values
    countries: tuple[str, ...]  # institutions.country values (used when `regions` is empty)
    places: tuple[str, ...]  # lowercase record place names that count as local
    bbox: tuple[float, float, float, float]  # west, south, east, north (for the map)
    strong: tuple[str, ...]  # regex fragments recognised anywhere in the question
    intro_only: tuple[str, ...] = ()  # regex fragments recognised only right after a self-introduction

    def card(self, locale: str = "en") -> dict[str, Any]:
        return {"key": self.key, "label": self.label_fr if locale == "fr" else self.label, "bbox": list(self.bbox)}


NS_PLACES = (
    "nova scotia", "nouvelle-écosse", "halifax", "dartmouth", "bedford", "africville", "preston", "north preston",
    "east preston", "cherry brook", "birchtown", "shelburne", "digby", "yarmouth", "truro", "windsor", "wolfville",
    "antigonish", "guysborough", "tracadie", "lincolnville", "cape breton", "sydney", "glace bay", "new glasgow",
    "annapolis royal", "weymouth falls", "hammonds plains", "beechville", "lucasville", "upper hammonds plains",
)

REGIONS: tuple[Region, ...] = (
    Region(
        key="nova-scotia", label="Nova Scotia", label_fr="Nouvelle-Écosse",
        regions=("Nova Scotia",), countries=("Canada",), places=NS_PLACES,
        bbox=(-66.4, 43.3, -59.6, 47.1),
        strong=(
            r"nova\s+scotia\w*", r"nouvelle[-\s]écosse", r"halifax", r"dartmouth", r"africville", r"birchtown",
            r"north\s+preston", r"cape\s+breton", r"wolfville", r"antigonish", r"truro", r"yarmouth", r"shelburne",
            r"s(?:ain)?t\.?\s+mary'?s?(?:\s+university)?", r"dalhousie(?:\s+university)?", r"acadia(?:\s+university)?",
            r"s(?:ain)?t\.?\s+francis\s+xavier(?:\s+university)?", r"mount\s+s(?:ain)?t\.?\s+vincent(?:\s+university)?",
            r"nscad(?:\s+university)?", r"nscc",
        ),
        intro_only=(r"ns", r"smu", r"dal", r"stfx", r"msvu", r"acadia", r"cbu"),
    ),
    Region(
        key="new-brunswick", label="New Brunswick", label_fr="Nouveau-Brunswick",
        regions=("New Brunswick",), countries=("Canada",), places=("new brunswick", "nouveau-brunswick", "fredericton", "moncton", "saint john"),
        bbox=(-69.1, 44.6, -63.7, 48.1),
        strong=(r"new\s+brunswick", r"nouveau[-\s]brunswick", r"fredericton", r"moncton", r"saint\s+john\b(?!'s)"),
        intro_only=(r"nb", r"unb", r"université\s+de\s+moncton"),
    ),
    Region(
        key="pei", label="Prince Edward Island", label_fr="Île-du-Prince-Édouard",
        regions=("Prince Edward Island",), countries=("Canada",), places=("prince edward island", "charlottetown"),
        bbox=(-64.5, 45.9, -61.9, 47.1),
        strong=(r"prince\s+edward\s+island", r"île[-\s]du[-\s]prince[-\s]édouard", r"charlottetown"),
        intro_only=(r"pei", r"upei"),
    ),
    Region(
        key="ontario", label="Ontario", label_fr="Ontario",
        regions=("Ontario",), countries=("Canada",),
        places=("ontario", "toronto", "hamilton", "ottawa", "chatham", "buxton", "owen sound", "st. catharines", "windsor, ontario", "amherstburg"),
        bbox=(-83.5, 41.7, -74.3, 46.5),  # southern Ontario, where the population and the holders are
        strong=(r"ontario", r"toronto", r"hamilton", r"ottawa", r"mcmaster(?:\s+university)?", r"university\s+of\s+toronto", r"york\s+university", r"carleton(?:\s+university)?"),
        intro_only=(r"u\s?of\s?t", r"uoft", r"tmu", r"waterloo", r"queen'?s"),
    ),
    Region(
        key="quebec", label="Quebec", label_fr="Québec",
        regions=("Quebec", "Québec"), countries=("Canada",), places=("quebec", "québec", "montreal", "montréal"),
        bbox=(-79.8, 45.0, -64.0, 49.5),
        strong=(r"qu[ée]bec", r"montr[ée]al", r"mcgill(?:\s+university)?", r"concordia(?:\s+university)?"),
        intro_only=(r"uqam", r"laval"),
    ),
    Region(
        key="canada", label="Canada", label_fr="Canada",
        regions=(), countries=("Canada",), places=("canada",),
        bbox=(-128.0, 42.0, -52.6, 56.0),
        strong=(),  # "to Canada" is usually the topic (Underground Railroad), not where the person is
        intro_only=(r"canada",),
    ),
)

_INTRO = re.compile(
    r"\b(?:"
    r"i'?m|i\s+am|we'?re|we\s+are|i\s+(?:live|study|work|teach|go\s+to\s+school)|i'?ve\s+lived|living|based|"
    r"je\s+suis|j'habite|j'étudie|nous\s+sommes|on\s+est"
    r")\b",
    re.IGNORECASE,
)
_PREP = r"(?:from|at|in|of|near|around|à|de|du|en|au|près\s+de)"
# words that make the sentence about the topic, not about where the person is ("I'm interested in Halifax history")
_TOPIC_WORDS = re.compile(
    r"\b(?:interest\w*|curious|look\w*|search\w*|research(?!er)\w*|writ(?!er)\w*|read(?!er)\w*|learn\w*|project|essay|paper|thesis|"
    r"history|histoire|about|on|into|keen|passionate|want\w*|need\w*|trying|work\w*\s+on|intéress\w*|cherch\w*|sur)\b",
    re.IGNORECASE,
)
_TRAIL = re.compile(
    r"^(?:\s*(?:university|université|campus|college|collège|area|region|région|here|ici|province|student|étudiant\w*))*"
    r"[\s,;:.!]*(?:(?:and|so|but|et|mais|donc)\b[\s,]*)?",
    re.IGNORECASE,
)
_GREETING = re.compile(r"^\s*(?:hey|hi|hello|hiya|bonjour|salut|allo|good\s+(?:morning|afternoon|evening))\b[\s,!.]*", re.IGNORECASE)


def _compiled(fragments: tuple[str, ...]) -> re.Pattern[str] | None:
    return re.compile(r"\b(?:" + "|".join(fragments) + r")(?![\w'])", re.IGNORECASE) if fragments else None


_STRONG = [(r, _compiled(r.strong)) for r in REGIONS]
_ANY = [(r, _compiled(r.strong + r.intro_only)) for r in REGIONS]


def _after_intro(q: str) -> tuple[Region, int, int] | None:
    """(region, cut_start, cut_end) for the first self-introduction that names a known place."""
    for m in _INTRO.finditer(q):
        window = q[m.end() : m.end() + INTRO_REACH]
        best: tuple[int, int, Region] | None = None
        for region, pat in _ANY:
            if pat is None:
                continue
            for hit in pat.finditer(window):
                # the place must follow a preposition ("student AT smu", "from Halifax"), not just appear nearby
                before = window[: hit.start()]
                if not re.search(_PREP + r"\s*(?:the\s+)?$", before, re.IGNORECASE):
                    continue
                # no sentence break between the trigger and the place ("I'm curious. Halifax ...")
                if re.search(r"[?!]|\.\s+[A-Z]", before) or _TOPIC_WORDS.search(before):
                    continue
                if best is None or hit.start() < best[0]:
                    best = (hit.start(), hit.end(), region)
                break
        if best:
            end = m.end() + best[1]
            end += _TRAIL.match(q[end:]).end()  # type: ignore[union-attr]
            return best[2], m.start(), end
    return None


def detect(question: str) -> tuple[Region | None, str]:
    """Returns (region or None, text to search). The search text has the self-introduction removed."""
    q = (question or "").strip()
    if not q:
        return None, q
    intro = _after_intro(q)
    if intro:
        region, start, end = intro
        rest = (q[:start] + " " + q[end:]).strip()
        rest = _GREETING.sub("", rest).strip(" ,;:.-")
        # an introduction with nothing else ("I'm from Halifax") still searches for something sensible
        return region, rest or region.label
    for region, pat in _STRONG:
        if pat is not None and pat.search(q):
            return region, q
    return None, q


async def local_tiers(session: AsyncSession, ids: list[uuid.UUID], region: Region) -> dict[uuid.UUID, int]:
    """Which of `ids` are local. Tier 0: held by an institution in the region (you can go and see it). Tier 1: held
    elsewhere but about a place in the region (a Harvard copy of a book on Nova Scotia's Black Loyalists)."""
    if not ids:
        return {}
    by_holder = "i.region = ANY(:regions)" if region.regions else "i.country = ANY(:countries)"
    rows = await session.execute(
        text(
            f"SELECT r.id, ({by_holder}) AS held FROM records r LEFT JOIN institutions i ON i.id = r.institution_id "
            f"WHERE r.id = ANY(:ids) AND (({by_holder}) "
            "OR EXISTS (SELECT 1 FROM unnest(r.places) p WHERE lower(p) = ANY(:places)))"
        ),
        {"ids": ids, "regions": list(region.regions), "countries": list(region.countries), "places": list(region.places)},
    )
    return {row[0]: (0 if row[1] else 1) for row in rows}


def promote(items: list[Any], tiers: dict[uuid.UUID, int], window: int, id_of=lambda x: x.id) -> list[Any]:
    """Within the top `window`: held locally first, then about the region, then the rest; each group keeps its
    relevance order (sorted() is stable). The tail is untouched."""
    if not tiers:
        return items
    head, tail = items[:window], items[window:]
    return sorted(head, key=lambda i: tiers.get(id_of(i), 2)) + tail
