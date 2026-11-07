"""Nova Scotia Open Data Portal — Socrata Discovery API (keyless).

Docs: https://socratadiscovery.docs.apiary.io/ · portal: https://data.novascotia.ca/
Endpoint: GET https://data.novascotia.ca/api/catalog/v1?q=...&only=datasets&limit=N&offset=O
Original-source URL: the dataset's permalink. These are ONLINE government datasets under the Nova Scotia Open
Government Licence (e.g. "African Nova Scotian Family Names by Region"), never archival holdings.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.adapters.base import ConnectorStatus, NormalizedRecord, SourceAdapter, register
from app.services.http import BlockedError, get_http
from app.services.normalize import clean, parse_year_range, truncate

CATALOG_URL = "https://data.novascotia.ca/api/catalog/v1"
INSTITUTION_SLUG = "nova-scotia-open-data"


class NsOpenDataAdapter(SourceAdapter):
    name = "ns_open_data"
    label = "Nova Scotia Open Data Portal (Socrata catalogue)"
    docs_url = "https://data.novascotia.ca/"
    requires_key = False
    min_interval = 1.0

    @staticmethod
    def _params(query: str, limit: int, offset: int = 0) -> dict[str, str]:
        """The Socrata Discovery API is federated across portals; pin it to Nova Scotia's domain so no
        other government's datasets are ever shown as Nova Scotia Open Data."""
        return {"q": query, "only": "datasets", "domains": "data.novascotia.ca", "search_context": "data.novascotia.ca", "limit": str(limit), "offset": str(offset)}

    def _status(self, state: str, detail: str, at: datetime | None = None) -> ConnectorStatus:
        return ConnectorStatus(name=self.name, label=self.label, state=state, detail=detail, docs_url=self.docs_url, checked_at=at or datetime.now(timezone.utc))  # type: ignore[arg-type]

    async def status(self) -> ConnectorStatus:
        try:
            res = await get_http().get(CATALOG_URL, self._params("African Nova Scotian", 1), source=self.name, ttl=600)
            if not res.ok:
                return self._status("error", f"HTTP {res.status_code}", res.fetched_at)
            return self._status("ok", f"Live and keyless ({res.json().get('resultSetSize', 0)} datasets for test query).", res.fetched_at)
        except BlockedError as e:
            return self._status("blocked", e.detail)
        except Exception as e:  # noqa: BLE001
            return self._status("error", f"{type(e).__name__}: {e}")

    async def search(self, query: str, max_records: int = 20) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        offset = 0
        while len(out) < max_records:
            res = await get_http().get(CATALOG_URL, self._params(query, min(max_records - len(out), 100), offset), source=self.name)
            if not res.ok:
                raise RuntimeError(f"Socrata HTTP {res.status_code}")
            data = res.json()
            results = data.get("results") or []
            for r in results:
                r["_provenance"] = res.provenance(self.name, query)
                out.append(r)
            offset += len(results)
            if not results or offset >= int(data.get("resultSetSize") or 0):
                break
        return out[:max_records]

    def normalize(self, raw: dict[str, Any], provenance: dict[str, Any] | None = None) -> NormalizedRecord:
        r = raw.get("resource") or {}
        cls = raw.get("classification") or {}
        meta = raw.get("metadata") or {}
        rid = str(r.get("id") or "")
        cols = [c for c in (r.get("columns_name") or []) if c]
        desc_bits = [clean(r.get("description"))]
        if cols:
            desc_bits.append("Columns: " + ", ".join(cols[:15]) + ("…" if len(cols) > 15 else ""))
        if r.get("data_updated_at"):
            desc_bits.append("Data last updated " + str(r["data_updated_at"])[:10] + ".")
        subjects = [s for s in (clean(x) for x in [cls.get("domain_category")] + (cls.get("categories") or []) + (cls.get("domain_tags") or [])[:20]) if s]
        updated = None
        if r.get("updatedAt"):
            try:
                updated = datetime.fromisoformat(str(r["updatedAt"]).replace("Z", "+00:00"))
            except ValueError:
                updated = None
        ds, de = parse_year_range(clean(r.get("description")))
        return NormalizedRecord(
            source_system=self.name,
            source_record_id=rid or (raw.get("permalink") or ""),
            title=clean(r.get("name")) or "(untitled dataset)",
            creators=[clean(raw.get("attribution") or (raw.get("owner") or {}).get("display_name") or "Government of Nova Scotia") or "Government of Nova Scotia"],
            description=truncate(clean(" ".join(b for b in desc_bits if b)), 2000),
            subjects=list(dict.fromkeys(subjects)),
            date_text=None,
            date_start=ds,
            date_end=de,
            resource_type="dataset",
            language=["en"],
            identifiers={"socrata_id": rid, "domain": meta.get("domain"), "rows": r.get("row_count") if isinstance(r.get("row_count"), int) else None},
            original_url=raw.get("permalink") or raw.get("link") or f"https://data.novascotia.ca/d/{rid}",
            digital_url=raw.get("link") or raw.get("permalink"),
            rights=meta.get("license") or "See dataset page",
            rights_status="open_licence" if meta.get("license") else "unknown",
            access_type="online",
            access_note="Open government dataset on data.novascotia.ca (download as CSV/JSON). Not an archival holding.",
            holding_verification="online_item",
            raw_metadata={k: v for k, v in raw.items() if k != "_provenance"},
            source_updated_at=updated,
            institution_slug=INSTITUTION_SLUG,
            provenance=provenance or raw.get("_provenance", {}) or {"adapter": self.name},
        )


ADAPTER = register(NsOpenDataAdapter())
