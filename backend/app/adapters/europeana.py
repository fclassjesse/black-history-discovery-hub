"""Europeana Search API (API key required). Docs: https://europeana.atlassian.net/wiki/spaces/EF/pages/2385739812/Search+API
Register for a key: https://www.europeana.eu/en/how-to-register-for-and-manage-an-api-key
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.adapters.base import ConnectorStatus, NormalizedRecord, SourceAdapter, register
from app.config import get_settings
from app.services.http import BlockedError, get_http
from app.services.normalize import clean, parse_year_range, truncate
from app.services.rights import classify

SEARCH_URL = "https://api.europeana.eu/record/v2/search.json"
TYPE_MAP = {"TEXT": "book", "IMAGE": "image", "SOUND": "audio", "VIDEO": "video", "3D": "artifact"}


def _l(v: Any) -> list[str]:
    if v is None:
        return []
    return [clean(str(x)) for x in (v if isinstance(v, list) else [v]) if clean(str(x))]


class EuropeanaAdapter(SourceAdapter):
    name = "europeana"
    label = "Europeana Search API"
    docs_url = "https://www.europeana.eu/en/how-to-register-for-and-manage-an-api-key"
    requires_key = True
    key_env = "EUROPEANA_API_KEY"
    min_interval = 1.0

    def is_configured(self) -> bool:
        return bool(get_settings().europeana_api_key)

    async def status(self) -> ConnectorStatus:
        if not self.is_configured():
            return ConnectorStatus(name=self.name, label=self.label, state="unconfigured", detail="EUROPEANA_API_KEY not set. Register at europeana.eu (free).", docs_url=self.docs_url, requires_key=True, key_env=self.key_env, checked_at=datetime.now(timezone.utc))
        try:
            res = await get_http().get(SEARCH_URL, {"query": "Nova Scotia", "rows": "1", "wskey": get_settings().europeana_api_key}, source=self.name, cache=False)
            if res.ok:
                return ConnectorStatus(name=self.name, label=self.label, state="ok", detail=f"Live ({res.json().get('totalResults', 0)} hits for test query).", docs_url=self.docs_url, requires_key=True, key_env=self.key_env, checked_at=res.fetched_at)
            return ConnectorStatus(name=self.name, label=self.label, state="error", detail=f"HTTP {res.status_code}", docs_url=self.docs_url, requires_key=True, key_env=self.key_env, checked_at=res.fetched_at)
        except BlockedError as e:
            return ConnectorStatus(name=self.name, label=self.label, state="blocked", detail=e.detail, docs_url=self.docs_url, requires_key=True, key_env=self.key_env, checked_at=datetime.now(timezone.utc))
        except Exception as e:  # noqa: BLE001
            return ConnectorStatus(name=self.name, label=self.label, state="error", detail=f"{type(e).__name__}: {e}", docs_url=self.docs_url, requires_key=True, key_env=self.key_env, checked_at=datetime.now(timezone.utc))

    async def search(self, query: str, max_records: int = 20) -> list[dict[str, Any]]:
        if not self.is_configured():
            raise RuntimeError("EUROPEANA_API_KEY not configured")
        res = await get_http().get(SEARCH_URL, {"query": query, "rows": str(min(max_records, 100)), "profile": "rich", "wskey": get_settings().europeana_api_key}, source=self.name, cache=False)
        if not res.ok:
            raise RuntimeError(f"Europeana HTTP {res.status_code}")
        items = res.json().get("items", [])
        for i in items:
            i["_provenance"] = res.provenance(self.name, query)
        return items[:max_records]

    def normalize(self, raw: dict[str, Any], provenance: dict[str, Any] | None = None) -> NormalizedRecord:
        rid = raw.get("id")
        rights_urls = _l(raw.get("rights"))
        rights_status, rights_label = classify(license_url=rights_urls[0] if rights_urls else None)
        date_text = " ".join(_l(raw.get("year"))) or None
        ds, de = parse_year_range(date_text)
        provider = ", ".join(_l(raw.get("dataProvider")))
        return NormalizedRecord(
            source_system=self.name,
            source_record_id=str(rid),
            title=" ".join(_l(raw.get("title"))) or "(untitled)",
            creators=_l(raw.get("dcCreator")),
            description=truncate(clean(" ".join(_l(raw.get("dcDescription")))), 2000),
            subjects=_l(raw.get("dcSubject")),
            date_text=date_text,
            date_start=ds,
            date_end=de,
            resource_type=TYPE_MAP.get(str(raw.get("type", "")).upper(), "other"),
            language=_l(raw.get("language")),
            identifiers={"europeana_id": rid, "data_provider": provider},
            original_url=str(raw.get("guid") or f"https://www.europeana.eu/item{rid}"),
            digital_url=_l(raw.get("edmIsShownBy"))[0] if raw.get("edmIsShownBy") else None,
            rights=rights_label,
            rights_status=rights_status,
            access_type="online",
            access_note=f"Digital item aggregated by Europeana from {provider}." if provider else "Digital item aggregated by Europeana.",
            holding_verification="online_item",
            thumbnail_url=_l(raw.get("edmPreview"))[0] if raw.get("edmPreview") else None,
            raw_metadata={k: v for k, v in raw.items() if k != "_provenance"},
            institution_slug=None,
            provenance=provenance or raw.get("_provenance", {}) or {"adapter": self.name},
        )


ADAPTER = register(EuropeanaAdapter())
