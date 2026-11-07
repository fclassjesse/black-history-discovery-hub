"""Smithsonian Open Access API (api.data.gov key required; free, instant by email).

Docs: https://edan.si.edu/openaccess/apidocs/ · key: https://api.data.gov/signup/
Endpoint: GET https://api.si.edu/openaccess/api/v1.0/search?q=...&rows=N&start=S&api_key=KEY
Original-source URL: `content.descriptiveNonRepeating.record_link` (collections.si.edu). Physical holding: the Smithsonian
unit named in `unitCode` (e.g. NMAAHC) — catalogue record; CC0 metadata, media rights per item.
Normaliser written from the documented response shape; it is exercised live only once a key is present.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.adapters.base import ConnectorStatus, NormalizedRecord, SourceAdapter, register
from app.config import get_settings
from app.services.http import BlockedError, get_http
from app.services.normalize import clean, parse_year_range, truncate

SEARCH_URL = "https://api.si.edu/openaccess/api/v1.0/search"
INSTITUTION_SLUG = "smithsonian-institution"
UNIT_NAMES = {"NMAAHC": "National Museum of African American History and Culture", "NMAH": "National Museum of American History", "NPG": "National Portrait Gallery", "SAAM": "Smithsonian American Art Museum", "NMNH": "National Museum of Natural History", "SIA": "Smithsonian Institution Archives", "AAA": "Archives of American Art", "ACM": "Anacostia Community Museum", "SIL": "Smithsonian Libraries"}


def _labelled(freetext: dict[str, Any], key: str) -> list[str]:
    return [clean(f"{x.get('label')}: {x.get('content')}" if x.get("label") else str(x.get("content", ""))) or "" for x in (freetext.get(key) or []) if isinstance(x, dict)]


class SmithsonianAdapter(SourceAdapter):
    name = "smithsonian"
    label = "Smithsonian Open Access (incl. NMAAHC)"
    docs_url = "https://edan.si.edu/openaccess/apidocs/"
    requires_key = True
    key_env = "SMITHSONIAN_API_KEY"
    min_interval = 1.0

    def is_configured(self) -> bool:
        return bool(get_settings().smithsonian_api_key)

    def _status(self, state: str, detail: str, at: datetime | None = None) -> ConnectorStatus:
        return ConnectorStatus(name=self.name, label=self.label, state=state, detail=detail, docs_url=self.docs_url, requires_key=True, key_env=self.key_env, checked_at=at or datetime.now(timezone.utc))  # type: ignore[arg-type]

    async def status(self) -> ConnectorStatus:
        if not self.is_configured():
            return self._status("unconfigured", "SMITHSONIAN_API_KEY not set. Get a free api.data.gov key (instant, by email): https://api.data.gov/signup/")
        try:
            res = await get_http().get(SEARCH_URL, {"q": "Nova Scotia", "rows": "1", "api_key": get_settings().smithsonian_api_key}, source=self.name, cache=False)
            if not res.ok:
                return self._status("error", f"HTTP {res.status_code}: {res.text[:120]}", res.fetched_at)
            return self._status("ok", f"Live ({(res.json().get('response') or {}).get('rowCount', 0)} hits for test query).", res.fetched_at)
        except BlockedError as e:
            return self._status("blocked", e.detail)
        except Exception as e:  # noqa: BLE001
            return self._status("error", f"{type(e).__name__}: {e}")

    async def search(self, query: str, max_records: int = 20) -> list[dict[str, Any]]:
        if not self.is_configured():
            raise RuntimeError("SMITHSONIAN_API_KEY not configured")
        out: list[dict[str, Any]] = []
        start = 0
        while len(out) < max_records:
            res = await get_http().get(SEARCH_URL, {"q": query, "rows": str(min(max_records - len(out), 100)), "start": str(start), "api_key": get_settings().smithsonian_api_key}, source=self.name, cache=False)
            if not res.ok:
                raise RuntimeError(f"Smithsonian HTTP {res.status_code}")
            resp = res.json().get("response") or {}
            rows = resp.get("rows") or []
            for r in rows:
                r["_provenance"] = res.provenance(self.name, query)
                out.append(r)
            start += len(rows)
            if not rows or start >= int(resp.get("rowCount") or 0):
                break
        return out[:max_records]

    def normalize(self, raw: dict[str, Any], provenance: dict[str, Any] | None = None) -> NormalizedRecord:
        content = raw.get("content") or {}
        dnr = content.get("descriptiveNonRepeating") or {}
        ft = content.get("freetext") or {}
        idx = content.get("indexedStructured") or {}
        unit = raw.get("unitCode") or dnr.get("unit_code") or ""
        unit_name = UNIT_NAMES.get(unit, unit or "Smithsonian Institution")
        title = clean((dnr.get("title") or {}).get("content") if isinstance(dnr.get("title"), dict) else raw.get("title")) or clean(raw.get("title")) or "(untitled)"
        media = ((dnr.get("online_media") or {}).get("media") or [])
        thumb = next((m.get("thumbnail") for m in media if isinstance(m, dict) and m.get("thumbnail")), None)
        media_url = next((m.get("content") for m in media if isinstance(m, dict) and m.get("content")), None)
        record_link = dnr.get("record_link") or f"https://collections.si.edu/search/detail/{raw.get('id')}"
        names = [n.split(":", 1)[-1].strip() for n in _labelled(ft, "name") if n]
        dates = [d for d in (clean(x) for x in (idx.get("date") or [])) if d] or [d.split(":", 1)[-1].strip() for d in _labelled(ft, "date") if d]
        date_text = dates[0] if dates else None
        ds, de = parse_year_range(" ".join(dates))
        topics = [t for t in (clean(x) for x in (idx.get("topic") or []) + (idx.get("place") or []) + (idx.get("culture") or [])) if t]
        notes = [n for n in _labelled(ft, "notes") if n]
        rights_txt = [r.split(":", 1)[-1].strip() for r in _labelled(ft, "objectRights") if r]
        obj_types = [t for t in (clean(x) for x in (idx.get("object_type") or [])) if t]
        tl = " ".join(obj_types).lower()
        rtype = "image" if any(k in tl for k in ("photograph", "print", "drawing", "painting")) else "book" if any(k in tl for k in ("book", "pamphlet", "periodical")) else "audio" if "sound" in tl else "video" if any(k in tl for k in ("film", "video")) else "archival_collection" if "collection" in tl else "artifact" if obj_types else "other"
        rights_status = "unknown"
        if "cc0" in " ".join(rights_txt).lower() or (dnr.get("metadata_usage") or {}).get("access") == "CC0":
            rights_status = "public_domain"
        return NormalizedRecord(
            source_system=self.name,
            source_record_id=str(raw.get("id") or dnr.get("record_ID") or record_link),
            title=title,
            creators=list(dict.fromkeys(n for n in names if n)),
            description=truncate(clean(" ".join(notes)), 3000) if notes else None,
            subjects=list(dict.fromkeys(topics)),
            date_text=date_text,
            date_start=ds,
            date_end=de,
            resource_type=rtype,
            language=[],
            identifiers={"edan_id": raw.get("id"), "record_id": dnr.get("record_ID"), "unit_code": unit, "data_source": dnr.get("data_source")},
            original_url=record_link,
            digital_url=media_url,
            rights="; ".join(rights_txt) if rights_txt else "Metadata released CC0; media and object rights per the Smithsonian record.",
            rights_status=rights_status,
            access_type="both" if media_url else "physical",
            access_note=f"Held by the {unit_name} (Smithsonian Institution). Catalogue record from Smithsonian Open Access." + (" Online media available." if media_url else ""),
            holding_verification="catalogue_record",
            thumbnail_url=thumb,
            raw_metadata={k: v for k, v in raw.items() if k != "_provenance"},
            institution_slug=INSTITUTION_SLUG,
            provenance=provenance or raw.get("_provenance", {}) or {"adapter": self.name},
        )


ADAPTER = register(SmithsonianAdapter())
