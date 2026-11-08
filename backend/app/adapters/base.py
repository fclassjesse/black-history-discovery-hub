from __future__ import annotations

import abc
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

ConnectorState = Literal["ok", "unconfigured", "blocked", "error", "untested"]


class ChunkIn(BaseModel):
    chunk_index: int
    text: str
    page_number: int | None = None
    page_url: str | None = None
    kind: str = "page"  # page (OCR / PDF page) | description (catalogue or finding-aid text)


class NormalizedRecord(BaseModel):
    """Canonical record (PRD §3). `institution_slug` resolves to an institution at upsert time."""

    source_system: str
    source_record_id: str
    title: str
    creators: list[str] = Field(default_factory=list)
    description: str | None = None
    subjects: list[str] = Field(default_factory=list)
    date_text: str | None = None
    date_start: int | None = None
    date_end: int | None = None
    resource_type: str = "other"
    language: list[str] = Field(default_factory=list)
    identifiers: dict[str, Any] = Field(default_factory=dict)
    original_url: str
    digital_url: str | None = None
    rights: str | None = None
    rights_status: str = "unknown"
    access_type: str = "unknown"
    access_note: str | None = None
    holding_verification: str = "unverified"
    call_number: str | None = None
    shelf_label: str | None = None
    thumbnail_url: str | None = None
    raw_metadata: dict[str, Any] = Field(default_factory=dict)
    source_updated_at: datetime | None = None
    institution_slug: str | None = None
    provenance: dict[str, Any] = Field(default_factory=dict)
    review_status: str = "published"
    chunks: list[ChunkIn] = Field(default_factory=list)


class ConnectorStatus(BaseModel):
    name: str
    label: str
    state: ConnectorState
    detail: str
    docs_url: str | None = None
    requires_key: bool = False
    key_env: str | None = None
    checked_at: datetime | None = None
    last_run: dict[str, Any] | None = None


class SourceAdapter(abc.ABC):
    name: str
    label: str
    docs_url: str | None = None
    requires_key: bool = False
    key_env: str | None = None
    min_interval: float = 1.0

    def is_configured(self) -> bool:
        return True

    @abc.abstractmethod
    async def status(self) -> ConnectorStatus: ...

    @abc.abstractmethod
    async def search(self, query: str, max_records: int = 20) -> list[dict[str, Any]]:
        """Return raw source records (each must be JSON-serializable)."""

    @abc.abstractmethod
    def normalize(self, raw: dict[str, Any], provenance: dict[str, Any] | None = None) -> NormalizedRecord: ...

    async def enrich(self, rec: NormalizedRecord) -> NormalizedRecord:
        """Optional second pass (e.g. fetch OCR chunks). Default: no-op."""
        return rec


_REGISTRY: dict[str, SourceAdapter] = {}
_LOADED = False


def register(adapter: SourceAdapter) -> SourceAdapter:
    _REGISTRY[adapter.name] = adapter
    return adapter


def get_adapter(name: str) -> SourceAdapter:
    _ensure_loaded()
    return _REGISTRY[name]


def all_adapters() -> list[SourceAdapter]:
    _ensure_loaded()
    return list(_REGISTRY.values())


def _ensure_loaded() -> None:
    global _LOADED
    if not _LOADED:
        from app.adapters import (  # noqa: F401
            ckan, dal_oai, dpla, europeana, harvard_librarycloud, internet_archive, loc_json, loc_sru, ns_open_data, nypl_digital, smithsonian, tna_discovery, wikimedia_commons,
        )

        _LOADED = True
