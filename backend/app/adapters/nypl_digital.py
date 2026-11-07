"""New York Public Library Digital Collections API v2 (free token required).

Docs: https://api.repo.nypl.org/ · token: https://api.repo.nypl.org/sign_up (instant, by email)
Endpoint: GET https://api.repo.nypl.org/api/v2/items/search?q=...&per_page=N&page=P  with header
`Authorization: Token token="KEY"`. Original-source URL: the item's `itemLink` on digitalcollections.nypl.org.
Holding: NYPL (incl. the Schomburg Center for Research in Black Culture) — catalogue record of a digitised item.
Normaliser written from the documented response shape; exercised live only once a token is present.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.adapters.base import ConnectorStatus, NormalizedRecord, SourceAdapter, register
from app.config import get_settings
from app.services.http import BlockedError, get_http
from app.services.normalize import clean, parse_year_range, truncate

SEARCH_URL = "https://api.repo.nypl.org/api/v2/items/search"
INSTITUTION_SLUG = "new-york-public-library"
TYPE_MAP = {"still image": "image", "text": "book", "cartographic": "map", "sound recording": "audio", "moving image": "video", "mixed material": "archival_collection"}


def _s(v: Any) -> str | None:
    if isinstance(v, dict):
        return clean(str(v.get("$") or v.get("#text") or ""))
    if isinstance(v, list):
        return clean(" ".join(x for x in (_s(i) for i in v) if x))
    return clean(str(v)) if v is not None else None


class NyplDigitalAdapter(SourceAdapter):
    name = "nypl_digital"
    label = "NYPL Digital Collections (incl. Schomburg Center)"
    docs_url = "https://api.repo.nypl.org/"
    requires_key = True
    key_env = "NYPL_API_TOKEN"
    min_interval = 1.0

    def is_configured(self) -> bool:
        return bool(get_settings().nypl_api_token)

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f'Token token="{get_settings().nypl_api_token}"'}

    def _status(self, state: str, detail: str, at: datetime | None = None) -> ConnectorStatus:
        return ConnectorStatus(name=self.name, label=self.label, state=state, detail=detail, docs_url=self.docs_url, requires_key=True, key_env=self.key_env, checked_at=at or datetime.now(timezone.utc))  # type: ignore[arg-type]

    async def status(self) -> ConnectorStatus:
        if not self.is_configured():
            return self._status("unconfigured", "NYPL_API_TOKEN not set. Sign up for a free token (instant, by email): https://api.repo.nypl.org/sign_up")
        try:
            res = await get_http().get(SEARCH_URL, {"q": "Nova Scotia", "per_page": "1"}, source=self.name, cache=False, headers=self._headers())
            if not res.ok:
                return self._status("error", f"HTTP {res.status_code}: {res.text[:120]}", res.fetched_at)
            n = ((res.json().get("nyplAPI") or {}).get("response") or {}).get("numResults", 0)
            return self._status("ok", f"Live ({n} hits for test query).", res.fetched_at)
        except BlockedError as e:
            return self._status("blocked", e.detail)
        except Exception as e:  # noqa: BLE001
            return self._status("error", f"{type(e).__name__}: {e}")

    async def search(self, query: str, max_records: int = 20) -> list[dict[str, Any]]:
        if not self.is_configured():
            raise RuntimeError("NYPL_API_TOKEN not configured")
        out: list[dict[str, Any]] = []
        page = 1
        while len(out) < max_records:
            res = await get_http().get(SEARCH_URL, {"q": query, "per_page": str(min(max_records - len(out), 50)), "page": str(page)}, source=self.name, cache=False, headers=self._headers())
            if not res.ok:
                raise RuntimeError(f"NYPL HTTP {res.status_code}")
            resp = (res.json().get("nyplAPI") or {}).get("response") or {}
            results = resp.get("result") or []
            results = results if isinstance(results, list) else [results]
            for r in results:
                r["_provenance"] = res.provenance(self.name, query)
                out.append(r)
            if not results or len(out) >= int(resp.get("numResults") or 0):
                break
            page += 1
        return out[:max_records]

    def normalize(self, raw: dict[str, Any], provenance: dict[str, Any] | None = None) -> NormalizedRecord:
        uuid = _s(raw.get("uuid")) or ""
        title = _s(raw.get("title")) or "(untitled item)"
        item_link = _s(raw.get("itemLink")) or (f"https://digitalcollections.nypl.org/items/{uuid}" if uuid else "https://digitalcollections.nypl.org/")
        date_text = _s(raw.get("dateIssued")) or _s(raw.get("date")) or None
        ds, de = parse_year_range(date_text)
        tor = (_s(raw.get("typeOfResource")) or "").lower()
        rtype = TYPE_MAP.get(tor, "other")
        image_id = _s(raw.get("imageID"))
        thumb = f"https://images.nypl.org/index.php?id={image_id}&t=w" if image_id else None
        rights_txt = _s(raw.get("rightsStatement")) or _s(raw.get("rights"))
        pd = str(_s(raw.get("publicDomain")) or "").lower() == "true"
        return NormalizedRecord(
            source_system=self.name,
            source_record_id=uuid or item_link,
            title=title,
            creators=[c for c in [_s(raw.get("contributor")), _s(raw.get("creator"))] if c],
            description=truncate(_s(raw.get("description")) or _s(raw.get("note")), 2000),
            subjects=[s for s in [_s(raw.get("subject"))] if s],
            date_text=date_text,
            date_start=ds,
            date_end=de,
            resource_type=rtype,
            language=[],
            identifiers={"nypl_uuid": uuid, "image_id": image_id, "api_uri": _s(raw.get("apiUri"))},
            original_url=item_link,
            digital_url=item_link,
            rights=rights_txt or ("NYPL marks this item as public domain." if pd else "See the item's rights statement on digitalcollections.nypl.org."),
            rights_status="public_domain" if pd else "unknown",
            access_type="both",
            access_note="Digitised item held by The New York Public Library (Schomburg Center and other divisions); the original is consulted on site, the digital copy online.",
            holding_verification="catalogue_record",
            thumbnail_url=thumb,
            raw_metadata={k: v for k, v in raw.items() if k != "_provenance"},
            institution_slug=INSTITUTION_SLUG,
            provenance=provenance or raw.get("_provenance", {}) or {"adapter": self.name},
        )


ADAPTER = register(NyplDigitalAdapter())
