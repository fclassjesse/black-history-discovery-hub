"""Shared normalization helpers: text cleanup, year parsing, dedupe keys, language codes."""
from __future__ import annotations

import re
import unicodedata

RESOURCE_TYPES = (
    "book", "serial", "manuscript", "archival_collection", "image", "map", "audio", "video",
    "dataset", "finding_aid", "artifact", "other",
)

MARC_LANG = {
    "eng": "en", "fre": "fr", "fra": "fr", "mik": "mic", "spa": "es", "ger": "de", "deu": "de", "por": "pt", "ita": "it",
    "lat": "la", "dut": "nl", "nld": "nl", "ara": "ar", "und": "und", "mul": "mul",
    "english": "en", "french": "fr", "français": "fr", "spanish": "es", "german": "de", "portuguese": "pt", "italian": "it",
    "latin": "la", "dutch": "nl", "arabic": "ar", "mi'kmaq": "mic", "mikmaq": "mic",
}

_PUNCT_TRAIL = re.compile(r"[\s/:;,.=]+$")
_WS = re.compile(r"\s+")


def clean(s: str | None) -> str | None:
    if s is None:
        return None
    s = _WS.sub(" ", str(s)).strip()
    return s or None


def strip_marc_punct(s: str | None) -> str | None:
    s = clean(s)
    if not s:
        return None
    return _PUNCT_TRAIL.sub("", s).strip() or None


def parse_year_range(text: str | None) -> tuple[int | None, int | None]:
    """'1783', '[2014]', 'c1920', '1990-2005', '2011-01-01T00:00:00Z', '18--' → (start, end)."""
    if not text:
        return None, None
    years = [int(y) for y in re.findall(r"(?<!\d)(1[0-9]{3}|20[0-9]{2})(?!\d)", str(text))]
    if not years:
        m = re.search(r"(?<!\d)(1[0-9]|20)--", str(text))  # 18-- → 1800-1899
        if m:
            start = int(m.group(1)) * 100
            return start, start + 99
        m = re.search(r"(?<!\d)(1[0-9]{2}|20[0-9])-(?!\d)", str(text))  # 192- → 1920-1929
        if m:
            start = int(m.group(1)) * 10
            return start, start + 9
        return None, None
    return min(years), max(years)


def lang_code(code: str | None) -> str | None:
    if not code:
        return None
    c = code.strip().lower()
    if len(c) == 2:
        return c
    if c in MARC_LANG:
        return MARC_LANG[c]
    head = c.split()[0] if c.split() else c  # "australian english" → "english"
    tail = c.split()[-1] if c.split() else c
    return MARC_LANG.get(tail, MARC_LANG.get(head, c[:12]))


QUESTION_PREFIXES = (
    "what happened to", "what happened in", "what happened at", "what happened", "tell me about", "tell me more about", "what do you know about",
    "what is known about", "can you tell me about", "i want to know about", "i'm looking for", "im looking for", "looking for", "where can i find",
    "where can i read about", "where can i learn about", "how can i learn about", "what can you tell me about", "what is", "what was", "what are", "what were",
    "who was", "who were", "who is", "who are", "where is", "where was", "where were", "when was", "when were", "when did", "why did", "why was", "how did",
    "i want to learn more about", "i want to learn about", "i need to learn more about", "i need to learn about", "i'd like to learn about",
    "i would like to learn about", "i'd like to know about", "i would like to know about", "want to learn more about", "want to learn about",
    "need to learn more about", "need to learn about", "i'm researching", "i am researching", "researching", "i'm interested in", "i am interested in",
    "do you have", "is there", "are there", "show me", "find", "search for", "information about", "information on", "anything about", "resources about", "resources on",
    # French (Canadian, plain register). Prefixes ending in an apostrophe match without a following space ("qu'est-ce qu'Africville").
    "qu'est-ce que c'est que", "qu'est-ce que c'est", "qu'est-ce que", "qu'est-ce qu'", "qu'est ce que", "qu'est-ce qui est arrivé à", "qu'est-il arrivé à",
    "que s'est-il passé à", "que s'est-il passé avec", "que s'est-il passé", "parle-moi de", "parlez-moi de", "parle-moi des", "parlez-moi des", "dis-moi en plus sur",
    "que sais-tu sur", "que savez-vous sur", "que sait-on sur", "que sait-on de", "qui était", "qui étaient", "qui est", "qui sont", "où est", "où sont", "où se trouve",
    "où se trouvent", "où puis-je trouver", "où puis-je lire sur", "où peut-on trouver", "où peut-on lire sur", "je cherche", "je recherche", "y a-t-il", "existe-t-il",
    "avez-vous", "as-tu", "montre-moi", "montrez-moi", "des informations sur", "de l'information sur", "informations sur", "ressources sur", "quelque chose sur",
    "quand a eu lieu", "quand est", "quand était", "pourquoi", "comment",
)
QUESTION_STOPWORDS = {
    "the", "a", "an", "about", "of", "in", "on", "to", "for", "and", "or", "is", "was", "were", "are", "did", "do", "does", "any", "some", "please", "me", "i", "you", "there", "it", "its", "their", "this", "that", "these", "those", "with", "what", "who", "when", "where", "why", "how", "which", "can", "could", "would", "should",
    # French function words (dropped only when they lead the query)
    "le", "la", "les", "l", "un", "une", "des", "du", "de", "d", "à", "au", "aux", "et", "ou", "est", "sont", "était", "étaient", "que", "qu", "qui", "quoi", "où", "quand",
    "pourquoi", "comment", "sur", "dans", "pour", "avec", "ce", "cet", "cette", "ces", "il", "elle", "on", "nous", "vous", "ils", "elles", "y", "en", "svp", "moi", "te",
}
_FRENCH_ELISION = re.compile(r"^(l|d|qu|j|m|n|s|t|c)'(?=\w)", re.IGNORECASE)


def question_to_keywords(q: str) -> str:
    """Deterministic question → search terms. Keeps quoted phrases and -exclusions intact."""
    s = q.strip().replace("\u2019", "'")  # typographic apostrophe → ASCII so French prefixes match
    low = s.lower()
    for pre in sorted(QUESTION_PREFIXES, key=len, reverse=True):
        if low.startswith(pre + " ") or (pre.endswith("'") and low.startswith(pre)):
            s = s[len(pre) :].strip()
            low = s.lower()
            break
    s = s.rstrip("?!. ").rstrip(" ?!.\u00a0")  # French puts a space before "?"
    # drop leading question/stop words only; keep inner words ("Book of Negroes", "Livre des Noirs" stay intact)
    words = s.split()
    while words and words[0].lower().strip(",.;:'") in QUESTION_STOPWORDS and not words[0].startswith('"'):
        words.pop(0)
    if words and not words[0].startswith('"'):
        words[0] = _FRENCH_ELISION.sub("", words[0])  # "l'Africville" → "Africville"
    out = " ".join(words).strip()
    return out or q.strip()


def ascii_fold(s: str) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFKD", s) if not unicodedata.combining(ch))


def dedupe_key(title: str | None, creators: list[str] | None, year: int | None) -> str | None:
    """Normalized title + first creator surname + year. Used to LINK, never merge."""
    if not title:
        return None
    t = ascii_fold(title).lower()
    t = re.sub(r"[^a-z0-9 ]+", " ", t)
    t = " ".join(w for w in t.split() if w not in {"the", "a", "an", "of", "and", "le", "la", "les", "de"})[:80]
    surname = ""
    if creators:
        first = ascii_fold(creators[0]).lower()
        surname = re.split(r"[,\s]+", first.strip())[0] if first.strip() else ""
        surname = re.sub(r"[^a-z]", "", surname)
    return f"{t}|{surname}|{year or ''}"


def truncate(s: str | None, n: int) -> str | None:
    if s is None:
        return None
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"
