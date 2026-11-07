"""Partner CSV / JSON import: header synonym mapping, row validation, duplicate flags.

Template: docs/partner-import-template.csv. Contract: docs/partner-api.md.
"""
from __future__ import annotations

import csv
import io
import json
import re
from typing import Any

from app.adapters.base import NormalizedRecord
from app.services.normalize import clean, dedupe_key, parse_year_range, RESOURCE_TYPES

CANONICAL_FIELDS = [
    "title", "creators", "description", "subjects", "date", "resource_type", "language", "identifiers",
    "original_url", "digital_url", "rights", "access_type", "access_note", "call_number", "shelf_label", "source_record_id",
]
REQUIRED = ("title",)
SYNONYMS: dict[str, list[str]] = {
    "title": ["title", "name", "item title", "record title", "titre"],
    "creators": ["creators", "creator", "author", "authors", "artist", "contributor", "auteur"],
    "description": ["description", "abstract", "summary", "notes", "scope and content", "scope_content"],
    "subjects": ["subjects", "subject", "keywords", "topics", "tags", "sujets"],
    "date": ["date", "dates", "year", "date created", "date_text", "creation date"],
    "resource_type": ["resource_type", "type", "format", "material type", "object type", "genre"],
    "language": ["language", "languages", "lang", "langue"],
    "identifiers": ["identifiers", "identifier", "accession number", "accession", "isbn", "reference code", "catalogue number", "id"],
    "original_url": ["original_url", "url", "link", "record url", "catalogue url", "permalink", "source url"],
    "digital_url": ["digital_url", "digital url", "online url", "viewer url", "digitized url"],
    "rights": ["rights", "copyright", "license", "licence", "rights statement"],
    "access_type": ["access_type", "access", "availability"],
    "access_note": ["access_note", "access notes", "access conditions", "how to access", "conditions of access"],
    "call_number": ["call_number", "call number", "shelfmark", "shelf mark", "location code"],
    "shelf_label": ["shelf_label", "shelf", "shelf label", "box", "location"],
    "source_record_id": ["source_record_id", "record id", "local id", "catalogue id", "object id", "external id"],
}
ACCESS_VALUES = ("online", "physical", "both", "unknown")


def auto_map(headers: list[str]) -> dict[str, str | None]:
    """canonical field → source header (or None)."""
    norm = {h: re.sub(r"[\s_\-]+", " ", h.strip().lower()) for h in headers}
    mapping: dict[str, str | None] = {}
    used: set[str] = set()
    for field in CANONICAL_FIELDS:
        found = None
        for syn in SYNONYMS[field]:
            s = re.sub(r"[\s_\-]+", " ", syn)
            for h, n in norm.items():
                if n == s and h not in used:
                    found = h
                    break
            if found:
                break
        mapping[field] = found
        if found:
            used.add(found)
    return mapping


def parse_upload(filename: str, content: bytes) -> tuple[list[str], list[dict[str, Any]]]:
    text = content.decode("utf-8-sig", errors="replace")
    if filename.lower().endswith(".json") or text.lstrip().startswith(("[", "{")):
        data = json.loads(text)
        rows = data.get("records", data) if isinstance(data, dict) else data
        if not isinstance(rows, list):
            raise ValueError("JSON must be a list of objects or {\"records\": [...]}")
        headers: list[str] = []
        for r in rows:
            for k in r:
                if k not in headers:
                    headers.append(k)
        return headers, [{k: ("" if v is None else v) for k, v in r.items()} for r in rows]
    reader = csv.DictReader(io.StringIO(text))
    headers = reader.fieldnames or []
    return list(headers), [dict(r) for r in reader]


def _split(v: Any) -> list[str]:
    if v is None:
        return []
    if isinstance(v, list):
        return [clean(str(x)) for x in v if clean(str(x))]
    return [clean(p) for p in re.split(r"[;|]", str(v)) if clean(p)]


def _ident(v: Any) -> dict[str, Any]:
    if v is None or v == "":
        return {}
    if isinstance(v, dict):
        return v
    s = str(v).strip()
    if s.startswith("{"):
        try:
            return json.loads(s)
        except json.JSONDecodeError:
            pass
    out: dict[str, Any] = {}
    for part in re.split(r"[;|]", s):
        if ":" in part or "=" in part:
            k, val = re.split(r"[:=]", part, maxsplit=1)
            out[clean(k).lower().replace(" ", "_")] = clean(val)
        elif clean(part):
            out.setdefault("local_id", clean(part))
    return out


def validate_rows(rows: list[dict[str, Any]], mapping: dict[str, str | None], existing_keys: set[str], institution_slug: str) -> list[dict[str, Any]]:
    """Returns preview rows: {row_number, values, errors, warnings, duplicate_of, dedupe_key}."""
    preview: list[dict[str, Any]] = []
    seen: dict[str, int] = {}
    for i, raw in enumerate(rows, start=1):
        vals: dict[str, Any] = {}
        for field, header in mapping.items():
            if header and header in raw:
                vals[field] = raw[header]
        errors: list[str] = []
        warnings: list[str] = []
        title = clean(str(vals.get("title") or ""))
        if not title:
            errors.append("title is required")
        url = clean(str(vals.get("original_url") or ""))
        if url and not re.match(r"^https?://", url):
            errors.append("original_url must start with http:// or https://")
        access = clean(str(vals.get("access_type") or "")).lower() if vals.get("access_type") else ""
        if access and access not in ACCESS_VALUES:
            errors.append(f"access_type must be one of {', '.join(ACCESS_VALUES)}")
        rtype = clean(str(vals.get("resource_type") or "")).lower().replace(" ", "_") if vals.get("resource_type") else ""
        if rtype and rtype not in RESOURCE_TYPES:
            warnings.append(f"resource_type '{rtype}' not recognised; will be stored as 'other'")
        ds, de = parse_year_range(str(vals.get("date") or ""))
        if vals.get("date") and ds is None:
            warnings.append("date could not be parsed into a year; kept as text")
        creators = _split(vals.get("creators"))
        key = dedupe_key(title, creators, ds) if title else None
        dup_of = None
        if key:
            if key in seen:
                dup_of = f"row {seen[key]}"
            else:
                seen[key] = i
                if key in existing_keys:
                    dup_of = "existing record in this institution"
        preview.append({
            "row_number": i,
            "values": {k: (v if isinstance(v, (list, dict)) else clean(str(v)) if v not in (None, "") else None) for k, v in vals.items()},
            "errors": errors,
            "warnings": warnings,
            "duplicate_of": dup_of,
            "dedupe_key": key,
        })
    return preview


def row_to_record(row: dict[str, Any], institution_slug: str, batch_id: str, actor: str) -> NormalizedRecord:
    vals = row["values"]
    title = clean(str(vals.get("title")))
    creators = _split(vals.get("creators"))
    date_text = clean(str(vals.get("date"))) if vals.get("date") else None
    ds, de = parse_year_range(date_text)
    rtype = (clean(str(vals.get("resource_type") or "")) or "other").lower().replace(" ", "_")
    access = (clean(str(vals.get("access_type") or "")) or "").lower()
    digital = clean(str(vals.get("digital_url"))) if vals.get("digital_url") else None
    if access not in ACCESS_VALUES:
        access = "both" if digital else "physical"
    original = clean(str(vals.get("original_url"))) if vals.get("original_url") else None
    src_id = clean(str(vals.get("source_record_id"))) if vals.get("source_record_id") else f"{batch_id}:{row['row_number']}"
    return NormalizedRecord(
        source_system=f"partner:{institution_slug}",
        source_record_id=src_id,
        title=title or "(untitled)",
        creators=creators,
        description=clean(str(vals.get("description"))) if vals.get("description") else None,
        subjects=_split(vals.get("subjects")),
        date_text=date_text,
        date_start=ds,
        date_end=de,
        resource_type=rtype if rtype in RESOURCE_TYPES else "other",
        language=_split(vals.get("language")),
        identifiers=_ident(vals.get("identifiers")),
        original_url=original or "",
        digital_url=digital,
        rights=clean(str(vals.get("rights"))) if vals.get("rights") else None,
        rights_status="unknown",
        access_type=access,
        access_note=clean(str(vals.get("access_note"))) if vals.get("access_note") else None,
        holding_verification="unverified",
        call_number=clean(str(vals.get("call_number"))) if vals.get("call_number") else None,
        shelf_label=clean(str(vals.get("shelf_label"))) if vals.get("shelf_label") else None,
        raw_metadata={"import_row": row["row_number"], "values": vals},
        institution_slug=institution_slug,
        provenance={"adapter": "partner_csv", "import_batch_id": batch_id, "created_by": actor},
        review_status="draft",
    )
