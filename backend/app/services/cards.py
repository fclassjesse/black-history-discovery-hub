"""Record → public result card (metadata-derived summary, no LLM)."""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Institution, Record
from app.services import i18n
from app.services.normalize import truncate

# English labels kept for callers that import them; prefer i18n.type_label(resource_type, locale).
TYPE_LABEL = i18n.TYPE_LABEL["en"]


def institution_card(i: Institution | None) -> dict[str, Any] | None:
    if i is None:
        return None
    return {
        "id": str(i.id), "slug": i.slug, "name": i.name, "kind": i.kind, "city": i.city, "region": i.region, "country": i.country,
        "website_url": i.website_url, "catalogue_url": i.catalogue_url, "address": i.address, "access_requirements": i.access_requirements,
        "contact_email": i.contact_email, "contact_phone": i.contact_phone, "collection_summary": i.collection_summary,
        "latitude": i.latitude, "longitude": i.longitude, "location_precision": i.location_precision, "location_source": i.location_source,
        "partner_status": i.partner_status, "description": i.description,
    }


def summary_for(r: Record, locale: str = "en") -> str:
    """Only what the metadata establishes. Connective words follow the UI locale; the data stays as catalogued."""
    bits: list[str] = [i18n.type_label(r.resource_type, locale)]
    if r.date_text:
        bits.append(r.date_text)
    if r.creators:
        bits.append(i18n.t(locale, "summary.by") + " " + "; ".join(r.creators[:2]))
    head = " · ".join(bits)
    if r.description:
        return head + ". " + (truncate(r.description, 220) or "")
    if r.subjects:
        return head + ". " + i18n.t(locale, "summary.subjects") + " " + "; ".join(r.subjects[:4])
    return head + "."


def record_card(r: Record, linked: list[Record] | None = None, locale: str = "en") -> dict[str, Any]:
    return {
        "id": str(r.id),
        "source_system": r.source_system,
        "source_record_id": r.source_record_id,
        "title": r.title,
        "creators": r.creators,
        "date_text": r.date_text,
        "date_start": r.date_start,
        "date_end": r.date_end,
        "resource_type": r.resource_type,
        "resource_type_label": i18n.type_label(r.resource_type, locale),
        "language": r.language,
        "language_labels": [i18n.language_name(code, locale) for code in r.language],
        "subjects": r.subjects[:8],
        "summary": summary_for(r, locale),
        "description": r.description,
        "identifiers": r.identifiers,
        "institution": institution_card(r.institution),
        "access_type": r.access_type,
        "access_note": i18n.localize_access_note(r.access_note, locale),
        "original_url": r.original_url,
        "digital_url": r.digital_url,
        "call_number": r.call_number,
        "shelf_label": r.shelf_label,
        "holding_verification": r.holding_verification,
        "rights": r.rights,
        "rights_status": r.rights_status,
        "has_full_text": r.has_full_text,
        "thumbnail_url": r.thumbnail_url,
        "review_status": r.review_status,
        "provenance": r.provenance,
        "updated_at": r.updated_at.isoformat() if r.updated_at else None,
        "also_catalogued_at": [
            {"id": str(l.id), "institution_name": l.institution.name if l.institution else None, "original_url": l.original_url, "source_system": l.source_system}
            for l in (linked or [])
        ],
    }


async def load_records(session: AsyncSession, ids: list[uuid.UUID]) -> list[Record]:
    if not ids:
        return []
    rows = await session.execute(select(Record).options(selectinload(Record.institution)).where(Record.id.in_(ids)))
    by_id = {r.id: r for r in rows.scalars()}
    return [by_id[i] for i in ids if i in by_id]


async def linked_map(session: AsyncSession, records: list[Record]) -> dict[uuid.UUID, list[Record]]:
    """Records describing the same work (shared ISBN / OCLC / LCCN / title+creator+year key) at OTHER institutions."""
    keys = sorted({k for r in records for k in (r.work_keys or [])})
    if not keys:
        return {}
    rows = await session.execute(
        select(Record).options(selectinload(Record.institution)).where(Record.work_keys.overlap(keys), Record.review_status == "published")
    )
    by_key: dict[str, list[Record]] = {}
    for r in rows.scalars():
        for k in r.work_keys or []:
            by_key.setdefault(k, []).append(r)
    out: dict[uuid.UUID, list[Record]] = {}
    for r in records:
        seen: set[uuid.UUID] = set()
        linked: list[Record] = []
        for k in r.work_keys or []:
            for o in by_key.get(k, []):
                if o.id != r.id and o.institution_id != r.institution_id and o.id not in seen:
                    seen.add(o.id)
                    linked.append(o)
        out[r.id] = linked
    return out
