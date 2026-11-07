"""CSV/JSON import batches: preview (mapping, errors, duplicates) → commit as drafts."""
from __future__ import annotations

import uuid
from typing import Any

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters import partner_csv
from app.models import ImportBatch, Institution, User
from app.services import audit
from app.services.dedupe import existing_keys_for_institution
from app.services.repository import upsert_record


async def create_preview(session: AsyncSession, *, institution: Institution, user: User, filename: str, content: bytes, mapping_override: dict[str, str | None] | None = None) -> ImportBatch:
    try:
        headers, rows = partner_csv.parse_upload(filename, content)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(400, f"Could not parse file: {e}") from e
    if not rows:
        raise HTTPException(400, "The file has no data rows")
    mapping = partner_csv.auto_map(headers)
    if mapping_override:
        mapping.update({k: v for k, v in mapping_override.items() if k in mapping})
    existing = await existing_keys_for_institution(session, institution.id)
    preview = partner_csv.validate_rows(rows, mapping, existing, institution.slug)
    kind = "json" if filename.lower().endswith(".json") else "csv"
    batch = ImportBatch(
        institution_id=institution.id, created_by=user.id, kind=kind, filename=filename, status="preview",
        mapping={"headers": headers, "fields": mapping, "rows": rows[:500]}, preview=preview, row_count=len(rows),
        error_count=sum(1 for p in preview if p["errors"]), duplicate_count=sum(1 for p in preview if p["duplicate_of"]),
    )
    session.add(batch)
    await session.flush()
    await audit.log(session, institution_id=institution.id, actor=user, action="import.preview", entity_type="import_batch", entity_id=batch.id, after={"filename": filename, "rows": len(rows), "errors": batch.error_count, "duplicates": batch.duplicate_count})
    return batch


async def remap(session: AsyncSession, batch: ImportBatch, institution: Institution, mapping: dict[str, str | None]) -> ImportBatch:
    rows = batch.mapping.get("rows", [])
    fields = dict(batch.mapping.get("fields", {}))
    fields.update({k: v for k, v in mapping.items() if k in fields})
    existing = await existing_keys_for_institution(session, institution.id)
    preview = partner_csv.validate_rows(rows, fields, existing, institution.slug)
    batch.mapping = {**batch.mapping, "fields": fields}
    batch.preview = preview
    batch.error_count = sum(1 for p in preview if p["errors"])
    batch.duplicate_count = sum(1 for p in preview if p["duplicate_of"])
    await session.flush()
    return batch


async def commit(session: AsyncSession, batch: ImportBatch, institution: Institution, user: User, *, skip_duplicates: bool = True, demo: bool = False) -> dict[str, Any]:
    if batch.status != "preview":
        raise HTTPException(409, f"Batch already {batch.status}")
    created = 0
    skipped: list[dict[str, Any]] = []
    for row in batch.preview:
        if row["errors"]:
            skipped.append({"row_number": row["row_number"], "reason": "; ".join(row["errors"])})
            continue
        if row["duplicate_of"] and skip_duplicates:
            skipped.append({"row_number": row["row_number"], "reason": f"duplicate of {row['duplicate_of']}"})
            continue
        rec = partner_csv.row_to_record(row, institution.slug, str(batch.id), user.email)
        if not rec.original_url:
            rec.original_url = institution.catalogue_url or institution.website_url or f"/institutions/{institution.slug}"
        if demo:
            rec.holding_verification = "demo"
        await upsert_record(session, rec, institution_id=institution.id)
        created += 1
    batch.status = "committed"
    batch.committed_count = created
    await session.flush()
    await audit.log(session, institution_id=institution.id, actor=user, action="import.commit", entity_type="import_batch", entity_id=batch.id, after={"created_drafts": created, "skipped": len(skipped)})
    return {"batch_id": str(batch.id), "created_drafts": created, "skipped": skipped}


def batch_card(b: ImportBatch, include_preview: bool = False) -> dict[str, Any]:
    d = {
        "id": str(b.id), "kind": b.kind, "filename": b.filename, "status": b.status, "row_count": b.row_count, "error_count": b.error_count,
        "duplicate_count": b.duplicate_count, "committed_count": b.committed_count, "created_at": b.created_at.isoformat(), "error": b.error,
        "mapping": {"headers": b.mapping.get("headers", []), "fields": b.mapping.get("fields", {})},
        "canonical_fields": partner_csv.CANONICAL_FIELDS,
    }
    if include_preview:
        d["preview"] = b.preview
    return d


__all__ = ["create_preview", "remap", "commit", "batch_card", "uuid"]
