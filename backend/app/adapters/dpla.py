"""DPLA /v2/items (API key required). Docs: https://pro.dp.la/developers/requests
Free key: `curl -X POST https://api.dp.la/v2/api_key/<your email>` (the key is emailed to you).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.adapters.base import ConnectorStatus, NormalizedRecord, SourceAdapter, register
from app.config import get_settings
from app.services.http import BlockedError, get_http
from app.services.normalize import clean, parse_year_range, truncate

ITEMS_URL = "https://api.dp.la/v2/items"
TYPE_MAP = {"text": "book", "image": "image", "sound": "audio", "moving image": "video", "physical object": "artifact", "collection": "archival_collection"}


def _l(v: Any) -> list[str]:
    if v is None:
        return []
    return [clean(str(x)) for x in (v if isinstance(v, list) else [v]) if clean(str(x))]


class DplaAdapter(SourceAdapter):
    name = "dpla"
    label = "Digital Public Library of America (/v2/items)"
    docs_url = "https://pro.dp.la/developers/requests"
    requires_key = True
    key_env = "DPLA_API_KEY"
    min_interval = 1.0

    def is_configured(self) -> bool:
        return bool(get_settings().dpla_api_key)

    async def status(self) -> ConnectorStatus:
        if not self.is_configured():
            return ConnectorStatus(name=self.name, label=self.label, state="unconfigured", detail="DPLA_API_KEY not set. Request a free key: POST https://api.dp.la/v2/api_key/<email>.", docs_url=self.docs_url, requires_key=True, key_env=self.key_env, checked_at=datetime.now(timezone.utc))
        try:
            res = await get_http().get(ITEMS_URL, {"q": "Nova Scotia", "page_size": "1", "api_key": get_settings().dpla_api_key}, source=self.name, ttl=600, cache=False)
            if res.ok:
                return ConnectorStatus(name=self.name, label=self.label, state="ok", detail=f"Live ({res.json().get('count', 0)} hits for test query).", docs_url=self.docs_url, requires_key=True, key_env=self.key_env, checked_at=res.fetched_at)
            return ConnectorStatus(name=self.name, label=self.label, state="error", detail=f"HTTP {res.status_code}", docs_url=self.docs_url, requires_key=True, key_env=self.key_env, checked_at=res.fetched_at)
        except BlockedError as e:
            return ConnectorStatus(name=self.name, label=self.label, state="blocked", detail=e.detail, docs_url=self.docs_url, requires_key=True, key_env=self.key_env, checked_at=datetime.now(timezone.utc))
        except Exception as e:  # noqa: BLE001
            return ConnectorStatus(name=self.name, label=self.label, state="error", detail=f"{type(e).__name__}: {e}", docs_url=self.docs_url, requires_key=True, key_env=self.key_env, checked_at=datetime.now(timezone.utc))

    async def search(self, query: str, max_records: int = 20) -> list[dict[str, Any]]:
        if not self.is_configured():
            raise RuntimeError("DPLA_API_KEY not configured")
        res = await get_http().get(ITEMS_URL, {"q": query, "page_size": str(min(max_records, 100)), "api_key": get_settings().dpla_api_key}, source=self.name, cache=False)
        if not res.ok:
            raise RuntimeError(f"DPLA HTTP {res.status_code}")
        docs = res.json().get("docs", [])
        for d in docs:
            d["_provenance"] = res.provenance(self.name, query)
        return docs[:max_records]

    def normalize(self, raw: dict[str, Any], provenance: dict[str, Any] | None = None) -> NormalizedRecord:
        sr = raw.get("sourceResource", {})
        rid = raw.get("id") or raw.get("@id")
        provider = (raw.get("dataProvider") or raw.get("provider", {}).get("name") or "")
        if isinstance(provider, list):
            provider = ", ".join(provider)
        date = sr.get("date")
        date_text = clean(date.get("displayDate") if isinstance(date, dict) else str(date or "")) or None
        ds, de = parse_year_range(date_text)
        types = _l(sr.get("type"))
        rtype = TYPE_MAP.get(types[0].lower(), "other") if types else "other"
        subjects = [clean(s.get("name") if isinstance(s, dict) else s) for s in sr.get("subject", [])]
        rights = clean(str(sr.get("rights") or raw.get("rights") or "")) or None
        return NormalizedRecord(
            source_system=self.name,
            source_record_id=str(rid),
            title=clean(" ".join(_l(sr.get("title")))) or "(untitled)",
            creators=_l(sr.get("creator")),
            description=truncate(clean(" ".join(_l(sr.get("description")))), 2000),
            subjects=[s for s in subjects if s],
            date_text=date_text,
            date_start=ds,
            date_end=de,
            resource_type=rtype,
            language=[clean(l.get("iso639_3") if isinstance(l, dict) else l) for l in sr.get("language", []) if l],
            identifiers={"dpla_id": rid, "data_provider": provider},
            original_url=str(raw.get("isShownAt") or raw.get("@id")),
            digital_url=str(raw.get("isShownAt")) if raw.get("isShownAt") else None,
            rights=rights,
            rights_status="unknown",
            access_type="online",
            access_note=f"Digital item aggregated by DPLA from {provider}." if provider else "Digital item aggregated by DPLA.",
            holding_verification="online_item",
            thumbnail_url=raw.get("object") if isinstance(raw.get("object"), str) else None,
            raw_metadata={k: v for k, v in raw.items() if k != "_provenance"},
            institution_slug=None,
            provenance=provenance or raw.get("_provenance", {}) or {"adapter": self.name},
        )


ADAPTER = register(DplaAdapter())
