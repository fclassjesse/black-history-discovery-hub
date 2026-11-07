"""Deterministic entity extraction: people, places and communities from a record's own fields.

No model calls. People come from personal-name patterns in creators and name subjects (LCSH 600 style);
places and communities come from whole-word matches against fixtures/gazetteer.yaml (communities list sourced from
the NS Open Data set "African Nova Scotian Family Names by Region"). Everything returned here is also present in
the record text, so a facet never claims something the source did not say.
"""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

import yaml

from app.config import BACKEND_ROOT
from app.services.normalize import ascii_fold, clean

ORG_WORDS = re.compile(
    r"\b(company|co\.|ltd|limited|inc\.?|society|association|church|committee|department|ministry|university|college|library|"
    r"archives?|museum|centre|center|institute|council|board|government|office|fonds|collection|studio|press|publishing|"
    r"bank|railway|club|school|league|union|congress|assembly|house|legislature|corporation|band|choir|team)\b",
    re.IGNORECASE,
)
# "Surname, Given" (optionally with middle names/initials), optional trailing dates or role: "Walker, James W. St. G., 1940-"
PERSON = re.compile(r"^(?P<surname>[A-Z][\w'’.\-]+(?: [A-Z][\w'’.\-]+){0,2}), (?P<given>[A-Z][\w'’.\-]*(?: [A-Z][\w'’.\-]*){0,3})")
DATES = re.compile(r",?\s*(?:\(?\b(?:b\.|d\.|ca\.|c\.|fl\.|active)?\s*\d{3,4}\??\s*[-–]\s*(?:\d{3,4}\??)?\)?)\s*$")
TRAILING_ROLE = re.compile(r",?\s*\b(author|editor|creator|compiler|photographer|contributor|illustrator|translator|interviewee|interviewer|narrator|collector)\.?\s*$", re.IGNORECASE)


@lru_cache
def gazetteer() -> dict:
    p = Path(BACKEND_ROOT) / "fixtures" / "gazetteer.yaml"
    data = yaml.safe_load(p.read_text()) if p.exists() else {}
    communities = [str(x) for x in data.get("communities", [])]
    places = [str(x) for x in data.get("places", [])]
    orgs = [str(x) for x in data.get("community_organisations", [])]
    aliases = {str(k): str(v) for k, v in {**data.get("community_aliases", {}), **data.get("place_aliases", {})}.items()}
    names = {}
    for canonical in communities + places + orgs:
        names[canonical] = canonical
    for alias, canonical in aliases.items():
        names[alias] = canonical
    # longest first so "North Preston" wins over "Preston", "Windsor, Ontario" over "Windsor"
    ordered = sorted(names.items(), key=lambda kv: -len(kv[0]))
    patterns = [(re.compile(rf"(?<![A-Za-z0-9]){re.escape(ascii_fold(alias).lower())}(?![A-Za-z0-9])"), canonical) for alias, canonical in ordered]
    return {"communities": set(communities), "places": set(places), "orgs": set(orgs), "patterns": patterns}


def _is_place(s: str) -> bool:
    g = gazetteer()
    folded = ascii_fold(s).lower().strip(" .,")
    return any(ascii_fold(name).lower() == folded for name in g["places"] | g["communities"]) or folded in {"n.s", "ns", "n.b", "nb", "ont", "que", "canada", "u.s", "usa"}


def person_name(s: str | None) -> str | None:
    """'Walker, James W. St. G., 1940-' → 'Walker, James W. St. G.'; corporate names, places ("Halifax, Nova Scotia")
    and publisher statements ("Halifax, N.S. : Nimbus") → None."""
    s = clean(s)
    if not s or ORG_WORDS.search(s) or " : " in s or ";" in s:
        return None
    s = TRAILING_ROLE.sub("", s)
    s = DATES.sub("", s).strip().rstrip(",")
    m = PERSON.match(s)
    if not m:
        return None
    surname, given = m.group("surname"), m.group("given")
    if _is_place(surname) or _is_place(given) or _is_place(f"{surname}, {given}"):
        return None
    return f"{surname}, {given}".strip()


def extract_people(creators: list[str], subjects: list[str]) -> list[str]:
    out: list[str] = []
    for c in creators:
        n = person_name(c)
        if n and n not in out:
            out.append(n)
    for s in subjects:
        head = s.split(" -- ")[0]
        n = person_name(head)
        if n and n not in out:
            out.append(n)
    return out[:12]


def _mentions(text: str) -> list[str]:
    g = gazetteer()
    folded = ascii_fold(text).lower()
    found: list[str] = []
    consumed = [False] * len(folded)
    for pat, canonical in g["patterns"]:
        for m in pat.finditer(folded):
            if any(consumed[m.start() : m.end()]):
                continue
            for i in range(m.start(), m.end()):
                consumed[i] = True
            if canonical not in found:
                found.append(canonical)
    return found


def extract_places(title: str, subjects: list[str], description: str | None, *, max_items: int = 12) -> tuple[list[str], list[str]]:
    """Returns (places, communities). Subjects count fully; title and description are scanned too, since finding aids
    and LoC records put the place in the scope note rather than a heading."""
    g = gazetteer()
    text = " | ".join([title or "", *subjects, (description or "")[:4000]])
    found = _mentions(text)
    communities = [x for x in found if x in g["communities"] or x in g["orgs"]][:max_items]
    places = [x for x in found if x in g["places"] or x in g["communities"]][:max_items]
    return places, communities


def entities_for(title: str, creators: list[str], subjects: list[str], description: str | None) -> dict[str, list[str]]:
    places, communities = extract_places(title, subjects, description)
    return {"people": extract_people(creators, subjects), "places": places, "communities": communities}
