from __future__ import annotations

import time

from collections import Counter
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.services import i18n
from app.services import search as search_svc
from app.services.cards import institution_card, linked_map, load_records, record_card
from app.services.rerank import rerank_items
from app.services.searchlog import log_search

router = APIRouter(prefix="/api/search", tags=["search"])


RERANK_HEAD = 20  # cross-encoder cost grows with pairs × text length; 20 × 400 chars ≈ 0.4 s on CPU


def _csv(v: str | None) -> list[str]:
    return [x.strip() for x in (v or "").split(",") if x.strip()]


@router.get("")
async def search(
    q: str = Query("", max_length=500),
    mode: str = Query("natural", pattern="^(natural|advanced)$"),
    types: str | None = None,
    access: str | None = None,
    institution: str | None = None,
    lang: str | None = None,
    rights: str | None = None,
    verification: str | None = None,
    source: str | None = None,
    country: str | None = Query(None, max_length=200, description="Comma-separated holding-institution countries, e.g. Canada"),
    people: str | None = Query(None, max_length=400, description="Comma-separated person names as shown in the people facet"),
    places: str | None = Query(None, max_length=400),
    communities: str | None = Query(None, max_length=400),
    date_from: int | None = Query(None, ge=0, le=2100),
    date_to: int | None = Query(None, ge=0, le=2100),
    identifier: str | None = Query(None, max_length=120),
    location: str | None = Query(None, max_length=120),
    full_text: bool | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    locale: str = Query("en", pattern="^(en|fr)$", description="UI language for generated labels (resource types, language names, access notes)"),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    filters = search_svc.SearchFilters(
        resource_types=_csv(types), access_types=_csv(access), institution_slugs=_csv(institution), languages=_csv(lang),
        rights_statuses=_csv(rights), verifications=_csv(verification), source_systems=_csv(source), countries=_csv(country), people=_csv(people), places=_csv(places), communities=_csv(communities), date_from=date_from, date_to=date_to,
        identifier=identifier, location=location, has_full_text=full_text,
    )
    t0 = time.monotonic()
    ids = await search_svc.search_ids(session, q, filters, mode=mode)
    all_records = await load_records(session, ids)
    if q.strip() and mode == "natural":
        # cross-encoder reorders the fused head (same reordering on every page, so pagination stays stable)
        head = await rerank_items(search_svc.question_to_keywords(q), all_records[:RERANK_HEAD], lambda r: f"{r.title}. {'; '.join(r.subjects[:6])}. {(r.description or '')[:400]}")
        all_records = head + all_records[RERANK_HEAD:]
    capped = len(ids) >= search_svc.CANDIDATES
    total = await search_svc.count_browse(session, filters) if not q.strip() else len(all_records)
    start = (page - 1) * page_size
    page_records = all_records[start : start + page_size]
    linked = await linked_map(session, page_records)
    results = [record_card(r, linked.get(r.id, []), locale=locale) for r in page_records]

    facets = {
        "resource_type": Counter(r.resource_type for r in all_records),
        "access_type": Counter(r.access_type for r in all_records),
        "institution": Counter(r.institution.slug for r in all_records if r.institution),
        "language": Counter(l for r in all_records for l in r.language),
        "rights_status": Counter(r.rights_status for r in all_records),
        "holding_verification": Counter(r.holding_verification for r in all_records),
        "source_system": Counter(r.source_system for r in all_records),
        "country": Counter(r.institution.country for r in all_records if r.institution and r.institution.country),
        "people": Counter(p for r in all_records for p in (r.people or [])),
        "places": Counter(p for r in all_records for p in (r.places or [])),
        "communities": Counter(p for r in all_records for p in (r.communities or [])),
    }
    inst_names = {r.institution.slug: r.institution.name for r in all_records if r.institution}

    def facet_label(kind: str, value: str) -> str:
        if kind == "institution":
            return inst_names.get(value, value)
        if kind == "language":
            return i18n.language_name(value, locale)
        if kind == "resource_type":
            return i18n.type_label(value, locale)
        if kind == "access_type":
            return i18n.ACCESS_LABEL[locale].get(value, value)
        if kind == "rights_status":
            return i18n.RIGHTS_LABEL[locale].get(value, value.replace("_", " "))
        if kind == "holding_verification":
            return i18n.VERIFICATION_LABEL[locale].get(value, value)
        return value

    facets_out = {k: [{"value": v, "count": c, "label": facet_label(k, v)} for v, c in cnt.most_common(30)] for k, cnt in facets.items()}

    pins: dict[str, dict[str, Any]] = {}
    unknown_location = 0
    online_only = 0
    for r in all_records:
        inst = r.institution
        physical = r.access_type in ("physical", "both")
        if inst and inst.latitude is not None and inst.longitude is not None and physical:
            p = pins.setdefault(inst.slug, {"institution": institution_card(inst), "record_ids": [], "count": 0})
            p["record_ids"].append(str(r.id))
            p["count"] += 1
        elif physical or r.access_type == "unknown":
            unknown_location += 1
        else:
            online_only += 1
    online = [record_card(r, locale=locale) for r in all_records if r.access_type in ("online", "both") and (r.digital_url or r.original_url)][:40]
    if page == 1:
        await log_search(kind="search", query=q, mode=mode, filters={k: v for k, v in {"types": types, "access": access, "institution": institution, "country": country, "people": people, "places": places, "communities": communities, "date_from": date_from, "date_to": date_to}.items() if v}, result_count=total, took_ms=int((time.monotonic() - t0) * 1000))
    return {
        "query": q, "mode": mode, "total": total, "page": page, "page_size": page_size, "results": results, "facets": facets_out,
        "capped": capped, "candidate_limit": search_svc.CANDIDATES, "date_from": filters.date_from, "date_to": filters.date_to,
        "pins": list(pins.values()), "unknown_location_count": unknown_location, "online_only_count": online_only,
        "online_resources": online, "alias_expansion": search_svc.aliases.expand(search_svc.question_to_keywords(q))[1:] if (q and mode == "natural") else [],
        "keywords": search_svc.question_to_keywords(q) if (q and mode == "natural") else q,
        "locale": locale,
    }
