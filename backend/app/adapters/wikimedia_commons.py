"""Wikimedia Commons media search — keyless (MediaWiki Action API).

Docs: https://www.mediawiki.org/wiki/API:Search · https://www.mediawiki.org/wiki/Extension:CommonsMetadata
Endpoint: GET https://commons.wikimedia.org/w/api.php?action=query&generator=search&gsrnamespace=6&prop=imageinfo&iiprop=url|extmetadata
Original-source URL: the file's Commons page (`descriptionurl`). These are ONLINE items (photographs, scans, maps)
with an explicit licence from Commons' structured metadata; never presented as a physical holding.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from app.adapters.base import ConnectorStatus, NormalizedRecord, SourceAdapter, register
from app.services.http import BlockedError, get_http
from app.services.normalize import clean, parse_year_range, truncate
from app.services.textmatch import text_matches

API_URL = "https://commons.wikimedia.org/w/api.php"
INSTITUTION_SLUG = "wikimedia-commons"
MIME_TYPES = {"image": "image", "audio": "audio", "video": "video", "application/pdf": "book"}


def _strip_tags(s: str | None) -> str | None:
    return clean(re.sub(r"<[^>]+>", " ", s or "")) or None


def _meta(info: dict[str, Any], key: str) -> str | None:
    v = (info.get("extmetadata") or {}).get(key) or {}
    return clean(str(v.get("value", ""))) or None


def rights_status_for(license_code: str | None, copyrighted: str | None) -> str:
    code = (license_code or "").lower()
    if code.startswith(("pd", "cc0")) or "public domain" in code or (copyrighted or "").lower() == "false":
        return "public_domain"
    if code.startswith("cc"):
        return "cc"
    if code:
        return "in_copyright" if "fair" in code or "copyright" in code else "unknown"
    return "unknown"


def file_text(page: dict[str, Any]) -> str:
    info = (page.get("imageinfo") or [{}])[0]
    return " ".join(x for x in (page.get("title", ""), _meta(info, "ImageDescription") or "", _meta(info, "ObjectName") or "", _meta(info, "Categories") or "") if x)


def is_on_topic(page: dict[str, Any], query: str) -> bool:
    """Commons full-text search is loose; keep only files whose own title/description/categories carry every
    significant query word as a whole word."""
    return text_matches(_strip_tags(file_text(page)) or "", query)


class WikimediaCommonsAdapter(SourceAdapter):
    name = "wikimedia_commons"
    label = "Wikimedia Commons (media files with structured licences)"
    docs_url = "https://www.mediawiki.org/wiki/API:Search"
    requires_key = False
    min_interval = 1.0

    def _params(self, query: str, limit: int, offset: int = 0) -> dict[str, str]:
        return {
            "action": "query", "generator": "search", "gsrsearch": query, "gsrnamespace": "6", "gsrlimit": str(limit), "gsroffset": str(offset),
            "prop": "imageinfo", "iiprop": "url|extmetadata|mime|size", "iiurlwidth": "640", "format": "json", "formatversion": "2",
        }

    def _status(self, state: str, detail: str, at: datetime | None = None) -> ConnectorStatus:
        return ConnectorStatus(name=self.name, label=self.label, state=state, detail=detail, docs_url=self.docs_url, checked_at=at or datetime.now(timezone.utc))  # type: ignore[arg-type]

    async def status(self) -> ConnectorStatus:
        try:
            res = await get_http().get(API_URL, self._params("Nova Scotia", 1), source=self.name, ttl=600)
            if not res.ok or "error" in res.json():
                return self._status("error", f"HTTP {res.status_code}: {res.text[:120]}", res.fetched_at)
            pages = (res.json().get("query") or {}).get("pages") or []
            if not pages:
                return self._status("error", "Test query returned no files; the API shape may have changed.", res.fetched_at)
            return self._status("ok", "Live and keyless (test query returned files with licence metadata).", res.fetched_at)
        except BlockedError as e:
            return self._status("blocked", e.detail)
        except Exception as e:  # noqa: BLE001
            return self._status("error", f"{type(e).__name__}: {e}")

    async def search(self, query: str, max_records: int = 20) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        offset = 0
        while len(out) < max_records:
            res = await get_http().get(API_URL, self._params(query, min(max_records - len(out), 50), offset), source=self.name)
            if not res.ok:
                raise RuntimeError(f"Commons HTTP {res.status_code}")
            data = res.json()
            pages = (data.get("query") or {}).get("pages") or []
            for p in sorted(pages, key=lambda x: x.get("index", 0)):
                if p.get("imageinfo") and is_on_topic(p, query):
                    p["_provenance"] = res.provenance(self.name, query)
                    out.append(p)
            cont = (data.get("continue") or {}).get("gsroffset")
            if not pages or cont is None:
                break
            offset = int(cont)
        return out[:max_records]

    def normalize(self, raw: dict[str, Any], provenance: dict[str, Any] | None = None) -> NormalizedRecord:
        info = (raw.get("imageinfo") or [{}])[0]
        title = re.sub(r"^File:", "", raw.get("title") or "").rsplit(".", 1)[0].replace("_", " ").strip() or "(untitled file)"
        page_url = info.get("descriptionurl") or f"https://commons.wikimedia.org/?curid={raw.get('pageid')}"
        license_short = _meta(info, "LicenseShortName")
        license_code = _meta(info, "License")
        license_url = _meta(info, "LicenseUrl")
        artist = _strip_tags(_meta(info, "Artist"))
        credit = _strip_tags(_meta(info, "Credit"))
        date_text = _meta(info, "DateTimeOriginal")
        ds, de = parse_year_range(date_text)
        desc = _strip_tags(_meta(info, "ImageDescription"))
        cats = [c for c in (clean(x) for x in (_meta(info, "Categories") or "").split("|")) if c and not c.lower().startswith(("license migration", "self-published", "gfdl", "cc-", "pd-", "taken with", "files with"))]
        mime = info.get("mime") or ""
        rtype = next((t for k, t in MIME_TYPES.items() if mime.startswith(k)), "other")
        rights_bits = [b for b in (license_short, license_url, f"Credit: {credit}" if credit else None) if b]
        return NormalizedRecord(
            source_system=self.name,
            source_record_id=str(raw.get("pageid") or raw.get("title")),
            title=title,
            creators=[artist] if artist else [],
            description=truncate(desc, 2000),
            subjects=cats[:12],
            date_text=date_text,
            date_start=ds,
            date_end=de,
            resource_type=rtype,
            language=[],
            identifiers={"commons_pageid": raw.get("pageid"), "file": raw.get("title"), "mime": mime, "width": info.get("width"), "height": info.get("height")},
            original_url=page_url,
            digital_url=info.get("url"),
            rights="; ".join(rights_bits) if rights_bits else None,
            rights_status=rights_status_for(license_code, _meta(info, "Copyrighted")),
            access_type="online",
            access_note="Media file hosted on Wikimedia Commons; the licence shown comes from the file's structured metadata. Not a museum or archive holding.",
            holding_verification="online_item",
            thumbnail_url=info.get("thumburl"),
            raw_metadata={k: v for k, v in raw.items() if k != "_provenance"},
            institution_slug=INSTITUTION_SLUG,
            provenance=provenance or raw.get("_provenance", {}) or {"adapter": self.name},
        )


ADAPTER = register(WikimediaCommonsAdapter())
