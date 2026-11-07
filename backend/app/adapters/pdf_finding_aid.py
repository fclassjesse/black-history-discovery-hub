"""PDF finding aid → one `finding_aid` record + page-level chunks (text extracted with pypdf)."""
from __future__ import annotations

import io
from typing import Any

from pypdf import PdfReader

from app.adapters.base import ChunkIn, NormalizedRecord
from app.services.normalize import clean, truncate

MAX_PAGES = 200
MAX_CHUNK_CHARS = 1500


def extract_pages(content: bytes) -> list[tuple[int, str]]:
    reader = PdfReader(io.BytesIO(content))
    pages: list[tuple[int, str]] = []
    for i, page in enumerate(reader.pages[:MAX_PAGES], start=1):
        try:
            txt = clean(page.extract_text() or "") or ""
        except Exception:  # noqa: BLE001
            txt = ""
        if txt:
            pages.append((i, txt))
    return pages


def build_record(*, filename: str, content: bytes, institution_slug: str, title: str | None, description: str | None, original_url: str | None, batch_id: str, actor: str, public_file_url: str) -> NormalizedRecord:
    pages = extract_pages(content)
    chunks: list[ChunkIn] = []
    idx = 0
    for page_no, text in pages:
        for start in range(0, len(text), MAX_CHUNK_CHARS):
            piece = text[start : start + MAX_CHUNK_CHARS]
            if len(piece) < 80:
                continue
            chunks.append(ChunkIn(chunk_index=idx, text=piece, page_number=page_no, page_url=f"{public_file_url}#page={page_no}"))
            idx += 1
    first_text = pages[0][1] if pages else ""
    return NormalizedRecord(
        source_system=f"partner:{institution_slug}",
        source_record_id=f"finding-aid:{batch_id}",
        title=clean(title) or filename,
        description=clean(description) or truncate(first_text, 600),
        resource_type="finding_aid",
        identifiers={"filename": filename, "pages": len(pages)},
        original_url=original_url or public_file_url,
        digital_url=public_file_url,
        rights="Uploaded by the partner institution; terms set by the partner.",
        rights_status="unknown",
        access_type="both",
        access_note="Finding aid uploaded by the holding institution. Contact the institution to consult the described material.",
        holding_verification="unverified",
        raw_metadata={"filename": filename, "page_count": len(pages)},
        institution_slug=institution_slug,
        provenance={"adapter": "pdf_finding_aid", "import_batch_id": batch_id, "created_by": actor},
        review_status="draft",
        chunks=chunks,
    )


def summary(record: NormalizedRecord) -> dict[str, Any]:
    return {"title": record.title, "pages": record.identifiers.get("pages"), "chunks": len(record.chunks)}
