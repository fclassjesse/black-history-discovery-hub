"""Canonical data model (PRD §3 + BUILD_PLAN §6)."""
from __future__ import annotations

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    Computed,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

INSTITUTION_KINDS = ("museum", "archive", "library", "university", "community", "government", "online_repository")
LOCATION_PRECISIONS = ("partner_verified", "building", "road", "locality", "demo", "unknown")
PARTNER_STATUSES = ("link_only", "partner", "demo")
RIGHTS_STATUSES = ("public_domain", "cc", "open_licence", "in_copyright", "unknown", "restricted")
ACCESS_TYPES = ("online", "physical", "both", "unknown")
HOLDING_VERIFICATIONS = ("verified_partner", "catalogue_record", "unverified", "demo", "online_item")
REVIEW_STATUSES = ("draft", "in_review", "published", "withdrawn")
ROLES = ("owner", "editor", "reviewer")


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class Institution(TimestampMixin, Base):
    __tablename__ = "institutions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    slug: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(String(40), nullable=False, default="archive")
    description: Mapped[str | None] = mapped_column(Text)
    website_url: Mapped[str | None] = mapped_column(Text)
    catalogue_url: Mapped[str | None] = mapped_column(Text)
    address: Mapped[str | None] = mapped_column(Text)
    city: Mapped[str | None] = mapped_column(Text)
    region: Mapped[str | None] = mapped_column(Text)
    country: Mapped[str | None] = mapped_column(Text)
    contact_email: Mapped[str | None] = mapped_column(Text)
    contact_phone: Mapped[str | None] = mapped_column(Text)
    access_requirements: Mapped[str | None] = mapped_column(Text)
    collection_summary: Mapped[str | None] = mapped_column(Text)
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    location_precision: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown")
    location_source: Mapped[str | None] = mapped_column(Text)
    location_verified_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    location_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    partner_status: Mapped[str] = mapped_column(String(32), nullable=False, default="link_only")

    records: Mapped[list["Record"]] = relationship(back_populates="institution")


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    memberships: Mapped[list["Membership"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Membership(TimestampMixin, Base):
    __tablename__ = "memberships"
    __table_args__ = (UniqueConstraint("user_id", "institution_id", name="uq_membership"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    institution_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)

    user: Mapped[User] = relationship(back_populates="memberships")
    institution: Mapped[Institution] = relationship()


class ImportBatch(TimestampMixin, Base):
    __tablename__ = "import_batches"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    institution_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    kind: Mapped[str] = mapped_column(String(16), nullable=False)  # csv|json|pdf|manual|shelf_scan
    filename: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="preview")  # preview|committed|failed
    mapping: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    preview: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duplicate_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    committed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error: Mapped[str | None] = mapped_column(Text)


class Record(TimestampMixin, Base):
    __tablename__ = "records"
    __table_args__ = (
        UniqueConstraint("source_system", "source_record_id", name="uq_record_source"),
        Index("ix_records_search_tsv", "search_tsv", postgresql_using="gin"),
        Index("ix_records_search_tsv_fr", "search_tsv_fr", postgresql_using="gin"),
        Index("ix_records_review_status", "review_status"),
        Index("ix_records_dedupe_key", "dedupe_key"),
        Index("ix_records_institution", "institution_id"),
        Index("ix_records_people", "people", postgresql_using="gin"),
        Index("ix_records_places", "places", postgresql_using="gin"),
        Index("ix_records_communities", "communities", postgresql_using="gin"),
        Index("ix_records_work_keys", "work_keys", postgresql_using="gin"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    source_system: Mapped[str] = mapped_column(String(64), nullable=False)
    source_record_id: Mapped[str] = mapped_column(Text, nullable=False)
    institution_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("institutions.id", ondelete="SET NULL"))
    title: Mapped[str] = mapped_column(Text, nullable=False)
    creators: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)
    description: Mapped[str | None] = mapped_column(Text)
    subjects: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)
    date_text: Mapped[str | None] = mapped_column(Text)
    date_start: Mapped[int | None] = mapped_column(Integer)
    date_end: Mapped[int | None] = mapped_column(Integer)
    resource_type: Mapped[str] = mapped_column(String(40), nullable=False, default="other")
    language: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)
    identifiers: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    original_url: Mapped[str] = mapped_column(Text, nullable=False)
    digital_url: Mapped[str | None] = mapped_column(Text)
    rights: Mapped[str | None] = mapped_column(Text)
    rights_status: Mapped[str] = mapped_column(String(24), nullable=False, default="unknown")
    access_type: Mapped[str] = mapped_column(String(16), nullable=False, default="unknown")
    access_note: Mapped[str | None] = mapped_column(Text)
    holding_verification: Mapped[str] = mapped_column(String(24), nullable=False, default="unverified")
    call_number: Mapped[str | None] = mapped_column(Text)
    shelf_label: Mapped[str | None] = mapped_column(Text)
    thumbnail_url: Mapped[str | None] = mapped_column(Text)
    raw_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    source_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_status: Mapped[str] = mapped_column(String(16), nullable=False, default="published")
    provenance: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    dedupe_key: Mapped[str | None] = mapped_column(Text)
    # Deterministic entity axes (app/services/entities.py) and relationship keys (app/services/workkeys.py)
    people: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list, server_default="{}")
    places: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list, server_default="{}")
    communities: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list, server_default="{}")
    work_keys: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list, server_default="{}")
    has_full_text: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    import_batch_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("import_batches.id", ondelete="SET NULL"))
    search_tsv: Mapped[str | None] = mapped_column(
        TSVECTOR,
        Computed(
            "setweight(to_tsvector('english', coalesce(title,'')), 'A') || "
            "setweight(to_tsvector('english', bhdh_arr_text(creators) || ' ' || bhdh_arr_text(subjects)), 'B') || "
            "setweight(to_tsvector('english', coalesce(description,'')), 'C')",
            persisted=True,
        ),
    )
    # Second full-text column with the French stemmer / stopwords (migration 0003); queries run both and fuse.
    search_tsv_fr: Mapped[str | None] = mapped_column(
        TSVECTOR,
        Computed(
            "setweight(to_tsvector('french', coalesce(title,'')), 'A') || "
            "setweight(to_tsvector('french', bhdh_arr_text(creators) || ' ' || bhdh_arr_text(subjects)), 'B') || "
            "setweight(to_tsvector('french', coalesce(description,'')), 'C')",
            persisted=True,
        ),
    )
    embedding = mapped_column(Vector())  # untyped: dimension depends on embedding_model
    embedding_model: Mapped[str | None] = mapped_column(Text)
    embedded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    institution: Mapped[Institution | None] = relationship(back_populates="records")
    chunks: Mapped[list["RecordChunk"]] = relationship(back_populates="record", cascade="all, delete-orphan")


class RecordChunk(Base):
    __tablename__ = "record_chunks"
    __table_args__ = (
        UniqueConstraint("record_id", "chunk_index", name="uq_chunk"),
        Index("ix_chunks_tsv", "tsv", postgresql_using="gin"),
        Index("ix_chunks_tsv_fr", "tsv_fr", postgresql_using="gin"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    record_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("records.id", ondelete="CASCADE"), nullable=False, index=True)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    page_number: Mapped[int | None] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    page_url: Mapped[str | None] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(String(16), nullable=False, default="page", server_default="page")  # page | description
    tsv: Mapped[str | None] = mapped_column(TSVECTOR, Computed("to_tsvector('english', coalesce(text,''))", persisted=True))
    tsv_fr: Mapped[str | None] = mapped_column(TSVECTOR, Computed("to_tsvector('french', coalesce(text,''))", persisted=True))
    embedding = mapped_column(Vector())
    embedding_model: Mapped[str | None] = mapped_column(Text)

    record: Mapped[Record] = relationship(back_populates="chunks")


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    institution_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("institutions.id", ondelete="CASCADE"), index=True)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    actor_label: Mapped[str | None] = mapped_column(Text)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False)
    entity_id: Mapped[str | None] = mapped_column(Text)
    before: Mapped[dict | None] = mapped_column(JSONB)
    after: Mapped[dict | None] = mapped_column(JSONB)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ShelfScan(TimestampMixin, Base):
    __tablename__ = "shelf_scans"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    institution_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    image_path: Mapped[str] = mapped_column(Text, nullable=False)
    image_mime: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="queued")  # queued|processing|proposed|reviewed|failed
    model: Mapped[str | None] = mapped_column(Text)
    error: Mapped[str | None] = mapped_column(Text)

    items: Mapped[list["ShelfScanItem"]] = relationship(back_populates="scan", cascade="all, delete-orphan", order_by="ShelfScanItem.position")


class ShelfScanItem(TimestampMixin, Base):
    __tablename__ = "shelf_scan_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    scan_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("shelf_scans.id", ondelete="CASCADE"), nullable=False, index=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    spine_text: Mapped[str | None] = mapped_column(Text)
    proposed_title: Mapped[str | None] = mapped_column(Text)
    proposed_author: Mapped[str | None] = mapped_column(Text)
    proposed_isbn: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[float | None] = mapped_column(Float)
    uncertainties: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)
    candidates: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    selected_candidate: Mapped[dict | None] = mapped_column(JSONB)
    call_number: Mapped[str | None] = mapped_column(Text)
    shelf_label: Mapped[str | None] = mapped_column(Text)
    confirmed_holding: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="proposed")  # proposed|confirmed|rejected
    record_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("records.id", ondelete="SET NULL"))

    scan: Mapped[ShelfScan] = relationship(back_populates="items")


class Job(TimestampMixin, Base):
    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    kind: Mapped[str] = mapped_column(String(48), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="queued")  # queued|running|done|failed
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ConnectorRun(Base):
    __tablename__ = "connector_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    source_system: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    query: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="running")  # ok|unconfigured|blocked|error|running
    fetched: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    upserted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error: Mapped[str | None] = mapped_column(Text)
    request_url: Mapped[str | None] = mapped_column(Text)


SQL_HELPERS = [
    "CREATE EXTENSION IF NOT EXISTS vector",
    # array_to_string is STABLE in PostgreSQL; a text[] wrapper is safe to mark IMMUTABLE for generated columns.
    "CREATE OR REPLACE FUNCTION bhdh_arr_text(text[]) RETURNS text LANGUAGE sql IMMUTABLE AS "
    "$$ SELECT coalesce(array_to_string($1, ' '), '') $$",
]


class SearchLog(Base):
    """One row per public search or guide question: what was asked, how many results, how long. No user data."""

    __tablename__ = "search_log"
    __table_args__ = (Index("ix_search_log_created", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    kind: Mapped[str] = mapped_column(String(16), nullable=False, default="search")  # search | guide
    query: Mapped[str] = mapped_column(Text, nullable=False)
    mode: Mapped[str | None] = mapped_column(String(16))
    filters: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    result_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    took_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    abstained: Mapped[bool | None] = mapped_column(Boolean)
