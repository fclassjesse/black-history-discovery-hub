"""Internet Archive: advancedsearch.php + /metadata/{id} (keyless). Open items expose per-page OCR (`{id}_djvu.xml`).

Docs: https://archive.org/developers/ . We show IA items as ONLINE resources. `contributor` is shown as
"digitized from the collection of …", never as a verified physical holding.
"""
from __future__ import annotations

import httpx

import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any

from app.adapters.base import ChunkIn, ConnectorStatus, NormalizedRecord, SourceAdapter, register
from app.services.http import RetryableHttpError, BlockedError, get_http
from app.services.normalize import clean, lang_code, parse_year_range, truncate
from app.services.rights import classify, full_text_permitted

SEARCH_URL = "https://archive.org/advancedsearch.php"
METADATA_URL = "https://archive.org/metadata/{id}"
DOWNLOAD_URL = "https://archive.org/download/{id}/{file}"
FIELDS = [
    "identifier", "title", "creator", "date", "description", "subject", "mediatype", "licenseurl", "language",
    "publisher", "contributor", "access-restricted-item", "possible-copyright-status", "rights", "year", "collection",
]
INSTITUTION_SLUG = "internet-archive"
MEDIATYPE_TO_TYPE = {"texts": "book", "image": "image", "audio": "audio", "movies": "video", "data": "dataset", "collection": "archival_collection"}
MAX_PAGES_PER_ITEM = 120
MAX_CHUNK_CHARS = 1500


def _as_list(v: Any) -> list[str]:
    if v is None:
        return []
    if isinstance(v, list):
        return [clean(str(x)) for x in v if clean(str(x))]
    return [clean(str(v))] if clean(str(v)) else []


def _bool(v: Any) -> bool:
    return str(v).lower() == "true"


class InternetArchiveAdapter(SourceAdapter):
    name = "internet_archive"
    label = "Internet Archive (search + metadata APIs)"
    docs_url = "https://archive.org/developers/"
    requires_key = False
    min_interval = 1.0

    async def status(self) -> ConnectorStatus:
        try:
            res = await get_http().get(SEARCH_URL, {"q": "Africville", "fl[]": "identifier", "rows": "1", "output": "json"}, source=self.name, ttl=600)
            n = res.json().get("response", {}).get("numFound", 0)
            return ConnectorStatus(name=self.name, label=self.label, state="ok", detail=f"Live and keyless ({n} hits for test query).", docs_url=self.docs_url, checked_at=res.fetched_at)
        except BlockedError as e:
            return ConnectorStatus(name=self.name, label=self.label, state="blocked", detail=e.detail, docs_url=self.docs_url, checked_at=datetime.now(timezone.utc))
        except Exception as e:  # noqa: BLE001
            return ConnectorStatus(name=self.name, label=self.label, state="error", detail=f"{type(e).__name__}: {e}", docs_url=self.docs_url, checked_at=datetime.now(timezone.utc))

    @staticmethod
    def ia_query(query: str) -> str:
        phrases = re.findall(r'"([^"]+)"', query)
        rest = re.sub(r'"[^"]+"', " ", query)
        parts = [f'"{p}"' for p in phrases] + [w for w in rest.split() if w.lower() not in ("and", "or", "not")]
        return "(" + " AND ".join(parts) + ") AND (mediatype:texts OR mediatype:image OR mediatype:audio OR mediatype:movies)"

    async def search(self, query: str, max_records: int = 20) -> list[dict[str, Any]]:
        http = get_http()
        out: list[dict[str, Any]] = []
        page = 1
        rows = min(max_records, 50)
        while len(out) < max_records:
            params: dict[str, Any] = {"q": self.ia_query(query), "fl[]": FIELDS, "rows": str(rows), "page": str(page), "output": "json"}
            res = await http.get(SEARCH_URL, params, source=self.name)
            docs = res.json().get("response", {}).get("docs", [])
            for d in docs:
                d["_provenance"] = res.provenance(self.name, query)
                out.append(d)
            if len(docs) < rows:
                break
            page += 1
        return out[:max_records]

    def normalize(self, raw: dict[str, Any], provenance: dict[str, Any] | None = None) -> NormalizedRecord:
        ident = raw["identifier"]
        restricted = _bool(raw.get("access-restricted-item"))
        date_text = clean(str(raw.get("date") or raw.get("year") or "")) or None
        if date_text and "T00:00:00Z" in date_text:
            date_text = date_text.split("T")[0]
        date_start, date_end = parse_year_range(date_text)
        rights_status, rights_label = classify(
            license_url=raw.get("licenseurl") if isinstance(raw.get("licenseurl"), str) else (raw.get("licenseurl") or [None])[0],
            rights_text=" ".join(_as_list(raw.get("rights"))) or None,
            copyright_status=" ".join(_as_list(raw.get("possible-copyright-status"))) or None,
            restricted=restricted,
        )
        contributor = ", ".join(_as_list(raw.get("contributor")))
        description = clean(" ".join(_as_list(raw.get("description"))))
        mediatype = clean(str(raw.get("mediatype") or "texts")) or "texts"
        url = f"https://archive.org/details/{ident}"
        access_note = (
            "Lending-library item on archive.org: borrow with a free Internet Archive account (controlled digital lending)."
            if restricted else "Open online on archive.org."
        )
        if contributor:
            access_note += f" Digitized from the collection of {contributor} (shown as provenance, not as a verified current holding)."
        langs = [lang_code(x) for x in _as_list(raw.get("language")) if lang_code(x)]
        return NormalizedRecord(
            source_system=self.name,
            source_record_id=ident,
            title=clean(" ".join(_as_list(raw.get("title")))) or ident,
            creators=_as_list(raw.get("creator")),
            description=truncate(description, 2000),
            subjects=[s for s in _as_list(raw.get("subject")) if s],
            date_text=date_text,
            date_start=date_start,
            date_end=date_end,
            resource_type=MEDIATYPE_TO_TYPE.get(mediatype, "other"),
            language=langs,
            identifiers={"ia_identifier": ident, **({"contributor": contributor} if contributor else {})},
            original_url=url,
            digital_url=url,
            rights=rights_label,
            rights_status=rights_status,
            access_type="online",
            access_note=access_note,
            holding_verification="online_item",  # an online copy, not a verified physical holding
            thumbnail_url=f"https://archive.org/services/img/{ident}",
            raw_metadata={k: v for k, v in raw.items() if k != "_provenance"},
            institution_slug=INSTITUTION_SLUG,
            provenance=provenance or raw.get("_provenance", {}) or {"adapter": self.name},
        )

    async def enrich(self, rec: NormalizedRecord) -> NormalizedRecord:
        """Attach per-page OCR chunks for open, permitted items only."""
        restricted = _bool(rec.raw_metadata.get("access-restricted-item"))
        if rec.resource_type != "book" or not full_text_permitted(rec.rights_status, rec.date_start, restricted):
            return rec
        http = get_http()
        ident = rec.source_record_id
        meta_res = await http.get(METADATA_URL.format(id=ident), source=self.name)
        if not meta_res.ok:
            return rec
        meta = meta_res.json()
        files = [f.get("name", "") for f in meta.get("files", [])]
        djvu = next((f for f in files if f.endswith("_djvu.xml")), None)
        if not djvu:
            return rec
        try:
            xml_res = await http.get(DOWNLOAD_URL.format(id=ident, file=djvu), source=self.name)
        except (RetryableHttpError, httpx.HTTPError) as e:
            # The item is still indexed as metadata; only the OCR pages are skipped (and retried on a later seed).
            print(f"  [internet_archive] OCR skipped for {ident}: {type(e).__name__}: {e}")
            rec.raw_metadata = {**rec.raw_metadata, "ocr_error": f"{type(e).__name__}: {e}"[:200]}
            return rec
        if not xml_res.ok:
            return rec
        chunks = parse_djvu_pages(xml_res.text, ident)
        rec.chunks = chunks
        rec.raw_metadata = {**rec.raw_metadata, "ocr_file": djvu, "ocr_pages_indexed": len({c.page_number for c in chunks})}
        return rec


def parse_djvu_pages(xml_text: str, ident: str) -> list[ChunkIn]:
    chunks: list[ChunkIn] = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return chunks
    idx = 0
    for page_no, obj in enumerate(root.iter("OBJECT")):
        if page_no >= MAX_PAGES_PER_ITEM:
            break
        words = [w.text for w in obj.iter("WORD") if w.text]
        text = clean(" ".join(words)) or ""
        if len(text) < 200:
            continue
        page_url = f"https://archive.org/details/{ident}/page/n{page_no}"
        for start in range(0, len(text), MAX_CHUNK_CHARS):
            piece = text[start : start + MAX_CHUNK_CHARS]
            if len(piece) < 120:
                continue
            chunks.append(ChunkIn(chunk_index=idx, text=piece, page_number=page_no, page_url=page_url))
            idx += 1
    return chunks


ADAPTER = register(InternetArchiveAdapter())
