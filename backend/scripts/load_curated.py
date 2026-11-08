"""Load the hand-curated sample (fixtures/curated_sample.csv) into the index.

  uv run python scripts/load_curated.py

The sample answers the BCCNS CEO's request (2026-11-08): 10–20 public records from NovaMuse,
Nova Scotia Archives, Library and Archives Canada and the Hamilton Black History Database,
with his field list. Each row was copied by hand from the public record page named in
`source_url`; nothing here is generated. The holding institution is always the institution
that holds the original, never the aggregator site (NovaMuse / HBHC) where we found it —
that goes into provenance as `found_via`.

Idempotent: rows upsert on (source_system, source_record_id).
"""
from __future__ import annotations

import asyncio
import csv
import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.adapters.base import NormalizedRecord  # noqa: E402
from app.config import BACKEND_ROOT  # noqa: E402
from app.db import session_factory  # noqa: E402
import json  # noqa: E402

from sqlalchemy import select  # noqa: E402

from app.models import Institution  # noqa: E402
from app.services import geocode  # noqa: E402
from app.services.normalize import parse_year_range  # noqa: E402
from app.services.repository import upsert_record  # noqa: E402
from scripts.seed import seed_institutions  # noqa: E402

CSV_PATH = BACKEND_ROOT / "fixtures" / "curated_sample.csv"
SOURCE_SYSTEM = "curated_sample"

HOLDER_SLUGS = {
    "Nova Scotia Sport Hall of Fame": "ns-sport-hall-of-fame",
    "Shelburne County Museum": "shelburne-county-museum",
    "West Hants Historical Museum": "west-hants-historical-museum",
    "Nova Scotia Archives": "nova-scotia-archives",
    "The National Archives (UK), Kew": "uk-national-archives",
    "Hamilton Public Library": "hamilton-public-library",
    "Archives of Ontario": "archives-of-ontario",
    "Internet Archive": "internet-archive",
    "Library and Archives Canada": "library-and-archives-canada",
}
DCB_PREFIX = "Dictionary of Canadian Biography"

TYPE_MAP = {
    "photograph": "image", "artwork": "image", "document": "manuscript", "archival file": "archival_collection",
    "book": "book", "web article": "other",
}


def holder_slug(name: str) -> str:
    if name.startswith(DCB_PREFIX):
        return "dictionary-of-canadian-biography"
    if name not in HOLDER_SLUGS:
        raise ValueError(f"Unknown holding institution in curated sample: {name!r} — add it to HOLDER_SLUGS and institutions.json")
    return HOLDER_SLUGS[name]


def split(value: str) -> list[str]:
    return [v.strip() for v in value.split(";") if v.strip()]


def access_for(row: dict) -> tuple[str, str, str]:
    """(access_type, holding_verification, access_note) — stated plainly, no guessing."""
    holder, found_via = row["holding_institution"], row["found_via"]
    if holder == "Internet Archive":
        return "online", "online_item", "Borrow-only online copy at the Internet Archive (free account needed)."
    if found_via.startswith("Hamilton Black History Database"):
        return "unknown", "unverified", f"Listed by the Hamilton Black History Database. Follow the link to {holder} for access details."
    if holder == "Library and Archives Canada":
        return "both", "catalogue_record", "Held by Library and Archives Canada (Ottawa). Open access: view a digital copy on the record page, consult in person, or order copies."
    note = f"Original held by {holder}."
    if row["image_url"]:
        note += " An image is viewable online at the source page; contact the holder to see the original."
    return ("both" if row["image_url"] else "physical"), "catalogue_record", note


def to_record(row: dict) -> NormalizedRecord:
    start, end = parse_year_range(row["date_or_period"])
    access_type, verification, access_note = access_for(row)
    ref = row["reference_number"].strip()
    rid = hashlib.sha1(row["source_url"].encode()).hexdigest()[:16]
    provenance = {
        "adapter": "curated_sample",
        "method": "copied by hand from the public record page",
        "captured_on": row["captured_on"],
        "found_via": row["found_via"],
        "collection": row["collection_name"] or None,
        "note": row["notes"] or None,
    }
    return NormalizedRecord(
        source_system=SOURCE_SYSTEM,
        source_record_id=rid,
        title=row["title"].strip(),
        creators=split(row["people"]) if row["resource_type"] in ("book", "web article") else [],
        description=row["description"].strip() or None,
        subjects=split(row["subjects_keywords"]),
        date_text=row["date_or_period"].strip() or None,
        date_start=start,
        date_end=end,
        resource_type=TYPE_MAP.get(row["resource_type"], "other"),
        language=["en"],
        identifiers={"reference": ref} if ref else {},
        original_url=row["source_url"].strip(),
        digital_url=row["source_url"].strip() if row["image_url"] else None,
        access_type=access_type,
        access_note=access_note,
        holding_verification=verification,
        call_number=ref or None,
        thumbnail_url=row["image_url"].strip() or None,
        raw_metadata={k: v for k, v in row.items() if v},
        institution_slug=holder_slug(row["holding_institution"]),
        provenance={k: v for k, v in provenance.items() if v},
    )


def merge(extracted: list[str], curated: list[str]) -> list[str]:
    out = list(extracted)
    for v in curated:
        if v.lower() not in {o.lower() for o in out}:
            out.append(v)
    return out


async def geocode_missing(session, slugs: set[str]) -> None:
    """seed_institutions only geocodes on first creation; retry holders still without a location."""
    queries = {r["slug"]: r.get("geocode_query") for r in json.loads((BACKEND_ROOT / "fixtures" / "institutions.json").read_text())}
    for slug in sorted(slugs):
        inst = (await session.execute(select(Institution).where(Institution.slug == slug))).scalar_one_or_none()
        if inst is None or inst.latitude is not None or not queries.get(slug):
            continue
        g = await geocode.geocode(queries[slug])
        if g:
            inst.latitude, inst.longitude = g["latitude"], g["longitude"]
            inst.location_precision, inst.location_source = g["precision"], g["source"]
            print(f"  [geocode] {slug}: {g['latitude']:.4f},{g['longitude']:.4f} ({g['precision']})")
        else:
            print(f"  [geocode] {slug}: still no match")
    await session.commit()


async def main() -> None:
    rows = list(csv.DictReader(CSV_PATH.open(encoding="utf-8-sig")))
    async with session_factory()() as session:
        await seed_institutions(session)
        await geocode_missing(session, {holder_slug(r["holding_institution"]) for r in rows})
        created_n = 0
        for row in rows:
            rec = to_record(row)
            r, created = await upsert_record(session, rec)
            # keep the hand-captured people / places / communities alongside the automatic extraction
            r.people = merge(r.people, split(row["people"]))
            r.places = merge(r.places, split(row["geographic_location"]))
            r.communities = merge(r.communities, split(row["communities"]))
            created_n += int(created)
            print(f"  {'new' if created else 'upd'}  {rec.institution_slug:<34} {rec.title[:60]}")
        await session.commit()
    print(f"[curated] {len(rows)} rows, {created_n} new")


if __name__ == "__main__":
    asyncio.run(main())
