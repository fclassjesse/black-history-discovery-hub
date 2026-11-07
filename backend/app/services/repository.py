"""Upsert normalized records (+ chunks + embeddings) and resolve institutions by slug."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.base import NormalizedRecord
from app.models import Institution, Record, RecordChunk
from app.services.dedupe import dedupe_key_for
from app.services.entities import entities_for
from app.services.passages import description_passages
from app.services.workkeys import work_keys_for
from app.services.embeddings import get_embeddings, record_embedding_text


async def institution_by_slug(session: AsyncSession, slug: str | None) -> Institution | None:
    if not slug:
        return None
    return (await session.execute(select(Institution).where(Institution.slug == slug))).scalar_one_or_none()


async def upsert_record(session: AsyncSession, rec: NormalizedRecord, *, embed: bool = True, institution_id: uuid.UUID | None = None) -> tuple[Record, bool]:
    """Insert or update by (source_system, source_record_id). Returns (record, created)."""
    inst_id = institution_id
    if inst_id is None and rec.institution_slug:
        inst = await institution_by_slug(session, rec.institution_slug)
        inst_id = inst.id if inst else None
    existing = (
        await session.execute(select(Record).where(Record.source_system == rec.source_system, Record.source_record_id == rec.source_record_id))
    ).scalar_one_or_none()
    created = existing is None
    r = existing or Record(source_system=rec.source_system, source_record_id=rec.source_record_id, original_url=rec.original_url, title=rec.title)
    r.institution_id = inst_id
    r.title = rec.title
    r.creators = rec.creators
    r.description = rec.description
    r.subjects = rec.subjects
    r.date_text = rec.date_text
    r.date_start = rec.date_start
    r.date_end = rec.date_end
    r.resource_type = rec.resource_type
    r.language = rec.language
    r.identifiers = rec.identifiers
    r.original_url = rec.original_url
    r.digital_url = rec.digital_url
    r.rights = rec.rights
    r.rights_status = rec.rights_status
    r.access_type = rec.access_type
    r.access_note = rec.access_note
    r.holding_verification = rec.holding_verification
    r.call_number = rec.call_number
    r.shelf_label = rec.shelf_label
    r.thumbnail_url = rec.thumbnail_url
    r.raw_metadata = rec.raw_metadata
    r.source_updated_at = rec.source_updated_at
    r.provenance = rec.provenance
    r.dedupe_key = dedupe_key_for(rec.title, rec.creators, rec.date_start)
    ents = entities_for(rec.title, rec.creators, rec.subjects, rec.description)
    r.people, r.places, r.communities = ents["people"], ents["places"], ents["communities"]
    r.work_keys = work_keys_for(rec.identifiers, rec.raw_metadata, rec.title, rec.creators, rec.date_start)
    page_chunks = [c for c in rec.chunks if c.kind == "page"]
    r.has_full_text = bool(page_chunks)
    if created:
        r.review_status = rec.review_status
    if "import_batch_id" in rec.provenance:
        try:
            r.import_batch_id = uuid.UUID(str(rec.provenance["import_batch_id"]))
        except ValueError:
            pass
    session.add(r)
    await session.flush()

    if page_chunks:
        # OCR / PDF pages supplied: they replace every chunk of this record
        await session.execute(delete(RecordChunk).where(RecordChunk.record_id == r.id))
        new_chunks = page_chunks
    else:
        # nothing supplied: keep existing OCR pages; otherwise (re)build description passages from the catalogue text
        has_pages = False if created else (await session.execute(select(RecordChunk.id).where(RecordChunk.record_id == r.id, RecordChunk.kind == "page").limit(1))).first() is not None
        r.has_full_text = has_pages
        await session.execute(delete(RecordChunk).where(RecordChunk.record_id == r.id, RecordChunk.kind == "description"))
        new_chunks = [] if has_pages else description_passages(rec.description, rec.original_url)
    for c in new_chunks:
        session.add(RecordChunk(record_id=r.id, chunk_index=c.chunk_index, page_number=c.page_number, text=c.text, page_url=c.page_url, kind=c.kind))
    if new_chunks:
        await session.flush()

    if embed:
        await embed_record(session, r)
    return r, created


async def embed_record(session: AsyncSession, r: Record) -> None:
    provider = get_embeddings()
    texts = [record_embedding_text(r.title, r.creators, r.subjects, r.description, places=list(dict.fromkeys((r.communities or []) + (r.places or []))), resource_type=r.resource_type)]
    chunks = list((await session.execute(select(RecordChunk).where(RecordChunk.record_id == r.id).order_by(RecordChunk.chunk_index))).scalars())
    texts.extend(c.text for c in chunks)
    vecs = []
    for start in range(0, len(texts), 64):
        vecs.extend(await provider.embed(texts[start : start + 64]))
    r.embedding = vecs[0]
    r.embedding_model = provider.model
    r.embedded_at = datetime.now(timezone.utc)
    for c, v in zip(chunks, vecs[1:], strict=True):
        c.embedding = v
        c.embedding_model = provider.model
    await session.flush()
