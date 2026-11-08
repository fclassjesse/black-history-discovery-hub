"""Evidence-grounded guide (RAG) with server-side citation validation.

Flow: hybrid retrieval → numbered evidence pack → provider returns strict JSON → validate that every
citation resolves to the pack (and quotes exist in chunk text) → on failure retry once with the error →
on second failure abstain and still return the records.
"""
from __future__ import annotations

import json
import re
import time
import uuid
from collections import OrderedDict
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.services.quota import answer_quota
from app.services import search as search_svc
from app.services import i18n
from app.services.cards import load_records, record_card
from app.services.llm import LLMNotConfigured, get_llm, provider_info
from app.services import aliases
from app.services.normalize import ascii_fold, question_to_keywords
from app.services.rerank import rerank_items
from app.services.searchlog import log_search

RECORD_K = 12
CHUNK_K = 8
CANDIDATE_RECORDS = 24  # fused candidates handed to the reranker before the pack is cut to RECORD_K
CANDIDATE_CHUNKS = 24
MAX_CHUNKS_PER_RECORD = 3  # one book must not fill every passage slot
MAX_SAME_TITLE = 2  # near-identical titles (e.g. eleven photos of one event) must not fill the record slots
MAX_HISTORY = 3
MAX_ATTEMPTS = 3  # first try + two corrective retries, then abstain
MAX_ANSWER_CHARS = 2500
FOLLOW_UP = re.compile(
    r"^(and|also|what about|how about|tell me more|more about|more|why|where (is|was|are) (it|that|they|those|this)|who (is|was) (he|she|they)|"
    r"(is|was|are|were|does|did|can|could) (it|that|they|this|those|he|she)|it\b|that\b|they\b|those\b|these\b|this\b|he\b|she\b)",
    re.IGNORECASE,
)

SYSTEM_PROMPT = """You are the virtual guide of the Black History Discovery Hub, a referral layer that points people to
Black history resources held by museums, archives, libraries and communities. You never own or claim the material.

Rules (strict):
1. Use ONLY the numbered evidence items provided. EVERY sentence — including the very first one — must carry a
   citation marker like [1] or [2][3] placed just before its full stop, whose numbers you also list in "citations". A sentence without a marker is
   rejected by a validator and your whole answer is discarded, so do not write introductions or summaries without one.
2. Items marked METADATA-ONLY are catalogue entries. For those you may only say what the catalogue entry itself
   establishes (title, creator, date, subjects, publisher, extent, where it is held). Never claim to have read the work,
   never summarise its contents beyond the catalogue description, and never quote it.
3. Items marked EXCERPT include a real passage from the item itself. You may paraphrase or quote that passage; a
   quote must be a verbatim substring of the passage.
3b. Items marked DESCRIPTION carry the catalogue's or finding aid's own text ABOUT the item. You may paraphrase or
   quote it verbatim, but attribute it ("the finding aid describes…", "the catalogue entry says…"); it is not the item's
   contents and must not be presented as something you read in the item.
4. Never invent events, dates, names, places, quotes, links or availability. If the evidence does not answer the
   question, set "abstain": true, explain briefly in "abstain_reason", and keep "answer" to one or two sentences that say
   what the evidence does cover.
5. Keep answers SHORT: two or three plain, warm sentences (≤ 60 words, at most 4 citations). Lead with the direct answer; say online vs physical only if it fits in those sentences.
6. Output exactly one JSON object:
   {"answer": "...", "citations": [{"n": 1, "evidence_id": "E1", "quote": "optional verbatim substring for EXCERPT items"}],
    "abstain": false, "abstain_reason": null}
7. Language: write "answer" and "abstain_reason" in the language of the QUESTION (English or French). If the
   question's language is unclear or mixed, use the UI LANGUAGE given with the question. Evidence may be in either
   language: paraphrase it in the answer's language, but any quote stays verbatim in its own language — never
   translate a quote. In French use plain Canadian French and these terms: fonds, instrument de recherche,
   notice de catalogue, Loyalistes noirs, Néo-Écossais d'origine africaine, Livre des Noirs.
"""


META_SENTENCE = re.compile(
    r"^(i can('|’)?t|i cannot|i could not|i don('|’)?t|none of the evidence|the evidence (does|doesn|did)|the retrieved records|"
    r"for more|to consult|to access|you can (visit|borrow|request|read)|these (items|records) (are|can))",
    re.IGNORECASE,
)


ABBREVIATIONS = ("dr", "mr", "mrs", "ms", "prof", "rev", "hon", "st", "mt", "no", "vol", "ed", "eds", "vs", "etc", "jr", "sr", "u.s", "n.s", "b.c", "p", "pp", "ca", "c", "ch", "fig")


def split_sentences(text: str) -> list[str]:
    """Sentence split that does not break on abbreviations ("Dr. Albert Rose"), initials ("J. Nelson") or decimals."""
    # markers written after the full stop (". [1]") belong to the sentence they follow
    text = re.sub(r"([.!?])\s*((?:\[\d+\])+)", r"\2\1", text)
    parts = re.split(r"(?<=[.!?])\s+", text)
    out: list[str] = []
    for part in parts:
        if out:
            prev = out[-1]
            last = re.sub(r"(\[\d+\])+$", "", prev.rstrip()).rstrip()  # ignore trailing [n] markers
            tail = last.rsplit(" ", 1)[-1].rstrip(".").lower()
            prev_word = last.rsplit(" ", 2)[-2].rstrip(".").lower() if last.count(" ") >= 2 else ""
            is_page_ref = re.fullmatch(r"\d+", tail) and prev_word in ("p", "pp", "vol", "no", "ch", "fig")
            if last.endswith(".") and (tail in ABBREVIATIONS or re.fullmatch(r"[a-z]", tail) or is_page_ref or re.search(r"\d\.$", last) and part[:1].isdigit()):
                out[-1] = prev + " " + part
                continue
        out.append(part)
    return out


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", ascii_fold(s).lower()).strip()


class EvidencePack:
    def __init__(self) -> None:
        self.items: list[dict[str, Any]] = []

    def add_record(self, card: dict[str, Any]) -> None:
        self.items.append({"evidence_id": f"E{len(self.items) + 1}", "kind": "record", "card": card, "record_id": card["id"], "chunk_id": None})

    def add_chunk(self, chunk: dict[str, Any], card: dict[str, Any]) -> None:
        self.items.append({"evidence_id": f"E{len(self.items) + 1}", "kind": "chunk", "card": card, "record_id": card["id"], "chunk_id": str(chunk["chunk_id"]), "chunk": chunk})

    def by_id(self, eid: str) -> dict[str, Any] | None:
        return next((i for i in self.items if i["evidence_id"] == eid), None)

    def render(self) -> str:
        lines = []
        for it in self.items:
            c = it["card"]
            inst = c["institution"]["name"] if c.get("institution") else "holding institution unknown"
            head = f'{it["evidence_id"]} — "{c["title"]}"'
            meta = f'type={c["resource_type_label"]}; creators={"; ".join(c["creators"][:3]) or "n/a"}; date={c["date_text"] or "n/a"}; held/served by={inst}; access={c["access_type"]}; url={c["original_url"]}'
            if it["kind"] == "chunk":
                ch = it["chunk"]
                page = f' page {ch["page_number"]}' if ch.get("page_number") is not None else ""
                if ch.get("kind") == "description":
                    lines.append(f"{head} [DESCRIPTION — catalogue / finding-aid text about the item] {meta}\nDESCRIPTION TEXT: {ch['text'][:900]}")
                else:
                    lines.append(f"{head} [EXCERPT{page}] {meta}\nPASSAGE: {ch['text'][:900]}")
            else:
                desc = (c.get("description") or "")[:500]
                subj = "; ".join(c["subjects"][:6])
                lines.append(f"{head} [METADATA-ONLY] {meta}\nCATALOGUE DESCRIPTION: {desc or 'n/a'}\nSUBJECTS: {subj or 'n/a'}")
        return "\n\n".join(lines)


def validate(resp: dict[str, Any], pack: EvidencePack, locale: str = "en") -> tuple[bool, str | None, dict[str, Any]]:
    """Returns (ok, error, cleaned). Abstentions are always acceptable. ``locale`` only picks the fallback abstain text."""
    if not isinstance(resp, dict):
        return False, "response is not a JSON object", {}
    answer = str(resp.get("answer") or "").strip()[:MAX_ANSWER_CHARS]
    abstain = bool(resp.get("abstain"))
    cits_raw = resp.get("citations") or []
    if abstain:
        # keep whatever citations resolve so an abstention can still point at the records it did read
        cits_ok = []
        for c in cits_raw if isinstance(cits_raw, list) else []:
            try:
                it = pack.by_id(str(c.get("evidence_id") or ""))
                if it is not None:
                    cits_ok.append({"n": int(c.get("n")), "evidence_id": it["evidence_id"], "record_id": it["record_id"], "chunk_id": it["chunk_id"], "quote": None})
            except (TypeError, ValueError, AttributeError):
                continue
        known = {c["n"] for c in cits_ok}
        answer = re.sub(r"\[(\d+)\]", lambda m: m.group(0) if int(m.group(1)) in known else "", answer)
        return True, None, {"answer": answer.strip(), "citations": cits_ok, "abstain": True, "abstain_reason": str(resp.get("abstain_reason") or i18n.t(locale, "guide.insufficient"))}
    if not answer:
        return False, "empty answer", {}
    if not isinstance(cits_raw, list) or not cits_raw:
        return False, "no citations provided for a non-abstaining answer", {}
    cits: list[dict[str, Any]] = []
    seen_n: set[int] = set()
    for c in cits_raw:
        try:
            n = int(c.get("n"))
        except (TypeError, ValueError, AttributeError):
            return False, "citation without a numeric n", {}
        it = pack.by_id(str(c.get("evidence_id") or ""))
        if it is None:
            return False, f"citation [{n}] references evidence_id {c.get('evidence_id')!r} which is not in the evidence pack", {}
        quote = str(c.get("quote") or "").strip() or None
        if quote:
            if it["kind"] != "chunk":
                return False, f"citation [{n}] quotes a METADATA-ONLY item; quotes are only allowed for EXCERPT or DESCRIPTION items", {}
            if _norm(quote) not in _norm(it["chunk"]["text"]):
                return False, f"citation [{n}] quote is not a verbatim substring of the passage", {}
        seen_n.add(n)
        cits.append({"n": n, "evidence_id": it["evidence_id"], "record_id": it["record_id"], "chunk_id": it["chunk_id"], "quote": quote})
    markers = {int(m) for m in re.findall(r"\[(\d+)\]", answer)}
    if not markers:
        return False, "answer contains no [n] citation markers", {}
    unknown = markers - seen_n
    if unknown:
        return False, f"answer cites {sorted(unknown)} but those numbers are not in citations", {}
    sentences = [s for s in split_sentences(answer) if len(s.strip()) > 25]
    uncited = [s for s in sentences if not re.search(r"\[\d+\]", s) and not META_SENTENCE.match(s.strip())]
    if uncited:
        return False, f"{len(uncited)} substantive sentence(s) lack citation markers: {uncited[0][:80]!r}", {}
    # any quoted span in the answer must exist verbatim in the cited evidence (excerpt text or catalogue description/title)
    cited_items = [pack.by_id(c["evidence_id"]) for c in cits]
    corpus = _norm(" ".join(
        (it["chunk"]["text"] if it["kind"] == "chunk" else f'{it["card"].get("title", "")} {it["card"].get("description") or ""} {" ".join(it["card"].get("subjects", []))}')
        for it in cited_items if it
    ))
    spans = re.findall(r"[\"“]([^\"”]{12,})[\"”]", answer) + re.findall(r"(?:(?<=\s)|^)[\'‘]([^\'’]{12,})[\'’](?=[\s.,;:!?\]]|$)", answer)
    for span in spans:
        if _norm(span) not in corpus:
            return False, f"quoted text {span[:60]!r} does not appear in the cited evidence", {}
    return True, None, {"answer": answer, "citations": cits, "abstain": False, "abstain_reason": None}


def is_follow_up(question: str, history: list[dict[str, Any]] | None) -> bool:
    """Deterministic: a short question, or one that opens with a pronoun / "tell me more", continues the previous turn."""
    if not history:
        return False
    q = question.strip()
    return len(q.split()) <= 4 or bool(FOLLOW_UP.match(q))


def retrieval_query(question: str, history: list[dict[str, Any]] | None) -> tuple[str, bool]:
    """Returns (query used for retrieval, follow_up). A follow-up borrows the previous question's keywords."""
    if is_follow_up(question, history):
        prev = str(history[-1].get("question") or "")
        return f"{question_to_keywords(prev)} {question_to_keywords(question)}".strip(), True
    return question, False


def _title_key(title: str) -> str:
    """Title normalised for near-duplicate detection: accents/case folded, trailing file ids like "(16257177989)" dropped."""
    t = re.sub(r"\s*\(\d{6,}\)\s*$", "", title or "")
    return re.sub(r"[^a-z0-9]+", " ", ascii_fold(t).lower()).strip()[:80]


def _collapse_same_work(records: list[Any], keep: int) -> list[Any]:
    """Keep the best-ranked record per work key, and at most MAX_SAME_TITLE per near-identical title, so the pack is
    not twelve copies of one book or eleven photos of one evening."""
    seen: set[str] = set()
    titles: dict[str, int] = {}
    out: list[Any] = []
    for r in records:
        keys = [k for k in (r.work_keys or []) if not k.startswith("dedupe:")] or list(r.work_keys or [])
        if any(k in seen for k in keys):
            continue
        tk = _title_key(r.title)
        if titles.get(tk, 0) >= MAX_SAME_TITLE:
            continue
        titles[tk] = titles.get(tk, 0) + 1
        seen.update(keys)
        out.append(r)
        if len(out) >= keep:
            break
    return out


def rerank_query(question: str, query: str) -> str:
    """What the cross-encoder scores against. The local reranker is English-only, so a French question is anchored
    with the English alias names it maps to ("Livre des Noirs" → "Book of Negroes"); English questions are unchanged."""
    expansions = aliases.expand(question_to_keywords(query))[1:]
    return f"{query} ({' / '.join(expansions)})" if expansions else query


async def build_pack(
    session: AsyncSession, question: str, filters: "search_svc.SearchFilters | None" = None, history: list[dict[str, Any]] | None = None, locale: str = "en"
) -> tuple[EvidencePack, list[dict[str, Any]], bool]:
    filters = filters or search_svc.SearchFilters()
    query, follow_up = retrieval_query(question, history)
    ids = await search_svc.search_ids(session, query, filters, mode="natural", limit=CANDIDATE_RECORDS)
    # a follow-up keeps the records the previous answer cited, so "where is it held?" can resolve "it"
    if follow_up:
        prev_ids = []
        for rid in history[-1].get("record_ids") or []:
            try:
                prev_ids.append(uuid.UUID(str(rid)))
            except ValueError:
                continue
        ids = list(dict.fromkeys(prev_ids + ids))
    records = await load_records(session, ids)
    rq = rerank_query(question, query)
    records = await rerank_items(rq, records, lambda r: f"{r.title}. {'; '.join(r.subjects[:6])}. {(r.description or '')[:400]}")
    records = _collapse_same_work(records, RECORD_K)
    cards = [record_card(r, locale=locale) for r in records]
    chunks = await search_svc.chunk_hits(session, query, k=CANDIDATE_CHUNKS, filters=filters)
    chunks = await rerank_items(rq, chunks, lambda c: c["text"])
    per_record: dict[str, int] = {}
    kept: list[dict[str, Any]] = []
    for ch in chunks:
        rid = str(ch["record_id"])
        if per_record.get(rid, 0) >= MAX_CHUNKS_PER_RECORD:
            continue
        per_record[rid] = per_record.get(rid, 0) + 1
        kept.append(ch)
        if len(kept) >= CHUNK_K:
            break
    chunks = kept
    need = [uuid.UUID(str(c["record_id"])) for c in chunks if str(c["record_id"]) not in {x["id"] for x in cards}]
    extra = {str(r.id): record_card(r, locale=locale) for r in await load_records(session, list(dict.fromkeys(need)))}
    by_id = {c["id"]: c for c in cards} | extra
    pack = EvidencePack()
    for c in cards:
        pack.add_record(c)
    for ch in chunks:
        card = by_id.get(str(ch["record_id"]))
        if card:
            pack.add_chunk(ch, card)
    return pack, cards, follow_up


def _finish(pack: EvidencePack, cleaned: dict[str, Any], cards: list[dict[str, Any]], info: dict[str, Any], validation_error: str | None = None, *, follow_up: bool = False) -> dict[str, Any]:
    cit_out = []
    for c in cleaned.get("citations", []):
        it = pack.by_id(c["evidence_id"])
        card = it["card"] if it else {}
        url = it["chunk"].get("page_url") if it and it["kind"] == "chunk" and it["chunk"].get("page_url") else card.get("original_url")
        cit_out.append({
            **c, "title": card.get("title"), "url": url, "original_url": card.get("original_url"),
            "institution": (card.get("institution") or {}).get("name"), "institution_id": (card.get("institution") or {}).get("id"),
            "access_type": card.get("access_type"), "page_number": it["chunk"].get("page_number") if it and it["kind"] == "chunk" else None,
            "kind": it["kind"] if it else None,
        })
    highlight = list(dict.fromkeys(c["record_id"] for c in cit_out))
    focus = list(dict.fromkeys(c["institution_id"] for c in cit_out if c.get("institution_id")))
    return {
        "answer": cleaned.get("answer", ""),
        "citations": cit_out,
        "abstain": bool(cleaned.get("abstain")),
        "abstain_reason": cleaned.get("abstain_reason"),
        "records": cards,
        "highlight_record_ids": highlight,
        "map_focus_institution_ids": focus,
        "provider": info,
        "follow_up": follow_up,
        "validation_error": validation_error,
        "evidence_count": len(pack.items),
    }


_CACHE: "OrderedDict[str, tuple[float, dict[str, Any]]]" = OrderedDict()
_CACHE_MAX = 256


def _cache_key(question: str, filters: "search_svc.SearchFilters", history: list[dict[str, Any]] | None, locale: str = "en") -> str:
    prev = str(history[-1].get("question") or "") if history else ""
    return json.dumps([question.strip().lower(), filters.__dict__, prev.strip().lower(), provider_info().get("model"), locale], sort_keys=True, default=str)


def cache_clear() -> None:
    _CACHE.clear()


async def ask(
    session: AsyncSession, question: str, filters: "search_svc.SearchFilters | None" = None, history: list[dict[str, Any]] | None = None, locale: str = "en",
    visitor: str | None = None,
) -> dict[str, Any]:
    """``locale`` is the UI language (en|fr): the fallback answer language and the language of generated messages."""
    locale = i18n.norm_locale(locale)
    filters = filters or search_svc.SearchFilters()
    history = [h for h in (history or []) if isinstance(h, dict) and h.get("question")][-MAX_HISTORY:]
    t0 = time.monotonic()
    key = _cache_key(question, filters, history, locale)
    ttl = get_settings().guide_cache_ttl_seconds
    hit = _CACHE.get(key)
    if hit and time.monotonic() - hit[0] < ttl:
        out = dict(hit[1], cached=True)
        await log_search(kind="guide", query=question, mode="cached", filters=filters.__dict__, result_count=len(out.get("records", [])), took_ms=int((time.monotonic() - t0) * 1000), abstained=out.get("abstain"))
        return out
    out = await _ask_uncached(session, question, filters, history, locale, visitor)
    out["cached"] = False
    if ttl > 0:
        _CACHE[key] = (time.monotonic(), out)
        while len(_CACHE) > _CACHE_MAX:
            _CACHE.popitem(last=False)
    await log_search(kind="guide", query=question, mode="follow_up" if out.get("follow_up") else "natural", filters=filters.__dict__, result_count=len(out.get("records", [])), took_ms=int((time.monotonic() - t0) * 1000), abstained=out.get("abstain"))
    return out


async def _ask_uncached(
    session: AsyncSession, question: str, filters: "search_svc.SearchFilters", history: list[dict[str, Any]], locale: str = "en", visitor: str | None = None
) -> dict[str, Any]:
    info = provider_info()
    pack, cards, follow_up = await build_pack(session, question, filters, history, locale)
    if not pack.items:
        return _finish(pack, {"answer": "", "abstain": True, "abstain_reason": i18n.t(locale, "guide.no_evidence")}, cards, info, follow_up=follow_up)
    try:
        llm = get_llm()
    except LLMNotConfigured as e:
        return _finish(pack, {"answer": "", "abstain": True, "abstain_reason": i18n.t(locale, "guide.not_configured", error=str(e))}, cards, info, follow_up=follow_up)
    # daily cap on paid AI answers: over it, the visitor still gets the matching records (counted only when the model would be called)
    if not answer_quota.try_take(visitor):
        out = _finish(pack, {"answer": "", "abstain": True, "abstain_reason": i18n.t(locale, "guide.daily_limit")}, cards, info, follow_up=follow_up)
        out["daily_limit_reached"] = True
        return out

    context = ""
    if history:
        prev = history[-1]
        context = (
            "\n\nPREVIOUS TURN (context only — NOT evidence, never cite it):\n"
            f"Q: {str(prev.get('question'))[:300]}\nA: {str(prev.get('answer') or '')[:600]}\n"
        )
    ui_language = "French (fr-CA)" if locale == "fr" else "English (en-CA)"
    user = f"QUESTION: {question}\nUI LANGUAGE: {ui_language}{context}\n\nEVIDENCE ({len(pack.items)} items):\n{pack.render()}"
    last_error: str | None = None
    for attempt in range(MAX_ATTEMPTS):
        prompt = user if attempt == 0 else user + (
            f"\n\nYour previous answer was rejected by the citation validator: {last_error}. "
            "Rewrite it so that EVERY sentence ends with a [n] marker that is listed in citations, quote only text that appears verbatim in EXCERPT passages, "
            "cite only the evidence ids above, or abstain."
        )
        try:
            raw = await llm.complete_json(system=SYSTEM_PROMPT, user=prompt, max_tokens=3000)
        except Exception as e:  # noqa: BLE001
            last_error = f"provider error: {type(e).__name__}: {str(e)[:200]}"
            continue
        ok, err, cleaned = validate(raw, pack, locale)
        if ok:
            return _finish(pack, cleaned, cards, info, follow_up=follow_up)
        last_error = err
    return _finish(
        pack,
        {"answer": "", "abstain": True, "abstain_reason": i18n.t(locale, "guide.validation_failed")},
        cards, info, validation_error=last_error, follow_up=follow_up,
    )
