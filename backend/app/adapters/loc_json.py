"""Library of Congress JSON API (www.loc.gov ... ?fo=json). Keyless, 20 req/min.

Docs: https://www.loc.gov/apis/json-and-yaml . On this network the endpoint answers scripts with a
Cloudflare browser challenge (HTTP 403). We never work around that: the connector reports `blocked`
and the normalizer is exercised against a recorded fixture.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.adapters.base import ConnectorStatus, NormalizedRecord, SourceAdapter, register
from app.services.http import BlockedError, get_http
from app.services.normalize import clean, parse_year_range, truncate

SEARCH_URL = "https://www.loc.gov/search/"
INSTITUTION_SLUG = "library-of-congress"
FORMAT_TO_TYPE = {"book": "book", "manuscript/mixed material": "archival_collection", "photo, print, drawing": "image", "map": "map", "audio": "audio", "film, video": "video", "newspaper": "serial", "periodical": "serial"}


class LocJsonAdapter(SourceAdapter):
    name = "loc_json"
    label = "Library of Congress digital collections (JSON API)"
    docs_url = "https://www.loc.gov/apis/json-and-yaml"
    requires_key = False
    min_interval = 3.0  # 20 requests / minute

    async def status(self) -> ConnectorStatus:
        try:
            res = await get_http().get(SEARCH_URL, {"q": "Nova Scotia", "fo": "json", "c": "1"}, source=self.name, ttl=600, cache=False)
            if res.ok:
                return ConnectorStatus(name=self.name, label=self.label, state="ok", detail="Live and keyless.", docs_url=self.docs_url, checked_at=res.fetched_at)
            return ConnectorStatus(name=self.name, label=self.label, state="error", detail=f"HTTP {res.status_code}", docs_url=self.docs_url, checked_at=res.fetched_at)
        except BlockedError as e:
            return ConnectorStatus(name=self.name, label=self.label, state="blocked", detail=e.detail + ". Not circumvented; normalizer covered by a recorded fixture.", docs_url=self.docs_url, checked_at=datetime.now(timezone.utc))
        except Exception as e:  # noqa: BLE001
            return ConnectorStatus(name=self.name, label=self.label, state="error", detail=f"{type(e).__name__}: {e}", docs_url=self.docs_url, checked_at=datetime.now(timezone.utc))

    async def search(self, query: str, max_records: int = 20) -> list[dict[str, Any]]:
        res = await get_http().get(SEARCH_URL, {"q": query, "fo": "json", "c": str(min(max_records, 100))}, source=self.name, min_interval=self.min_interval)
        if not res.ok:
            raise RuntimeError(f"LoC JSON HTTP {res.status_code}")
        results = res.json().get("results", [])
        for r in results:
            r["_provenance"] = res.provenance(self.name, query)
        return results[:max_records]

    def normalize(self, raw: dict[str, Any], provenance: dict[str, Any] | None = None) -> NormalizedRecord:
        rid = raw.get("id") or raw.get("url")
        fmt = (raw.get("original_format") or ["other"])
        fmt0 = fmt[0].lower() if isinstance(fmt, list) and fmt else str(fmt).lower()
        date_text = clean(str(raw.get("date") or "")) or None
        ds, de = parse_year_range(date_text)
        desc = raw.get("description")
        description = clean(" ".join(desc) if isinstance(desc, list) else str(desc or "")) or None
        online = any(k in raw for k in ("resources", "image_url")) and bool(raw.get("resources") or raw.get("image_url"))
        contributors = raw.get("contributor") or []
        return NormalizedRecord(
            source_system=self.name,
            source_record_id=str(rid),
            title=clean(raw.get("title")) or "(untitled)",
            creators=[clean(c) for c in contributors if clean(c)] if isinstance(contributors, list) else [],
            description=truncate(description, 2000),
            subjects=[clean(s) for s in raw.get("subject", []) if clean(s)],
            date_text=date_text,
            date_start=ds,
            date_end=de,
            resource_type=FORMAT_TO_TYPE.get(fmt0, "other"),
            language=[clean(l) for l in raw.get("language", []) if clean(l)],
            identifiers={"loc_item_id": rid},
            original_url=str(raw.get("url") or raw.get("id")),
            digital_url=str(raw.get("url") or raw.get("id")) if online else None,
            rights=clean(raw.get("rights")) if isinstance(raw.get("rights"), str) else None,
            rights_status="unknown",
            access_type="both" if online else "physical",
            access_note="Library of Congress digital collections item; see the item page for rights and access.",
            holding_verification="catalogue_record",
            thumbnail_url=(raw.get("image_url") or [None])[0] if isinstance(raw.get("image_url"), list) else None,
            raw_metadata={k: v for k, v in raw.items() if k != "_provenance"},
            institution_slug=INSTITUTION_SLUG,
            provenance=provenance or raw.get("_provenance", {}) or {"adapter": self.name},
        )


ADAPTER = register(LocJsonAdapter())
