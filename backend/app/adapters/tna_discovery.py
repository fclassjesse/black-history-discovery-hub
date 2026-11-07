"""The National Archives (UK) Discovery API — keyless.

Docs: https://discovery.nationalarchives.gov.uk/API/sandbox/index
Endpoint: GET /API/search/records?sps.searchQuery=...&sps.heldByCode=TNA&sps.resultsPageSize=N&sps.page=P
Only records held at Kew (`heldByCode=TNA`) are requested, so the holding statement is always TNA's own.
Original-source URL: https://discovery.nationalarchives.gov.uk/details/r/{id}. Physical holding: TNA (catalogue record).
Why it matters here: Colonial Office (CO 217 Nova Scotia), the Carleton papers (Book of Negroes), Sierra Leone Company
and Maroon records — primary sources for Black Loyalist and Maroon history in Nova Scotia.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from app.adapters.base import ConnectorStatus, NormalizedRecord, SourceAdapter, register
from app.services.http import BlockedError, get_http
from app.services.normalize import clean, parse_year_range, truncate

SEARCH_URL = "https://discovery.nationalarchives.gov.uk/API/search/records"
INSTITUTION_SLUG = "uk-national-archives"
LEVELS = {1: "archival_collection", 2: "archival_collection", 3: "archival_collection", 4: "archival_collection", 5: "archival_collection", 6: "manuscript", 7: "manuscript"}


def _strip_tags(s: str | None) -> str | None:
    return clean(re.sub(r"<[^>]+>", " ", s or "")) or None


class TnaDiscoveryAdapter(SourceAdapter):
    name = "tna_discovery"
    label = "The National Archives (UK) — Discovery API"
    docs_url = "https://discovery.nationalarchives.gov.uk/API/sandbox/index"
    requires_key = False
    min_interval = 1.0

    def _status(self, state: str, detail: str, at: datetime | None = None) -> ConnectorStatus:
        return ConnectorStatus(name=self.name, label=self.label, state=state, detail=detail, docs_url=self.docs_url, checked_at=at or datetime.now(timezone.utc))  # type: ignore[arg-type]

    async def status(self) -> ConnectorStatus:
        try:
            res = await get_http().get(SEARCH_URL, {"sps.searchQuery": "Nova Scotia", "sps.heldByCode": "TNA", "sps.resultsPageSize": "1"}, source=self.name, ttl=600)
            if not res.ok:
                return self._status("error", f"HTTP {res.status_code}", res.fetched_at)
            return self._status("ok", f"Live and keyless ({res.json().get('count', 0)} Kew records for test query).", res.fetched_at)
        except BlockedError as e:
            return self._status("blocked", e.detail)
        except Exception as e:  # noqa: BLE001
            return self._status("error", f"{type(e).__name__}: {e}")

    async def search(self, query: str, max_records: int = 20) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        page = 1
        size = min(max_records, 100)
        while len(out) < max_records:
            res = await get_http().get(SEARCH_URL, {"sps.searchQuery": query, "sps.heldByCode": "TNA", "sps.resultsPageSize": str(size), "sps.page": str(page)}, source=self.name)
            if not res.ok:
                raise RuntimeError(f"Discovery HTTP {res.status_code}")
            data = res.json()
            records = data.get("records") or []
            for r in records:
                r["_provenance"] = res.provenance(self.name, query)
                out.append(r)
            if not records or len(out) >= int(data.get("count") or 0):
                break
            page += 1
        return out[:max_records]

    def normalize(self, raw: dict[str, Any], provenance: dict[str, Any] | None = None) -> NormalizedRecord:
        rid = str(raw.get("id") or "")
        reference = clean(raw.get("reference")) or None
        title = _strip_tags(raw.get("title")) or _strip_tags(raw.get("description")) or reference or "(untitled record)"
        if len(title) > 300:
            title = title[:297] + "…"
        desc_bits = [_strip_tags(raw.get("description"))]
        if raw.get("context"):
            desc_bits.append("Context: " + (_strip_tags(raw["context"]) or ""))
        if raw.get("adminHistory"):
            desc_bits.append(_strip_tags(raw["adminHistory"]))
        if raw.get("note"):
            desc_bits.append(_strip_tags(raw["note"]))
        description = truncate(clean(" ".join(b for b in desc_bits if b)), 3000)
        date_text = clean(raw.get("coveringDates")) or None
        ds, de = parse_year_range(date_text or f"{raw.get('startDate') or ''} {raw.get('endDate') or ''}")
        level = raw.get("catalogueLevel")
        rtype = LEVELS.get(int(level), "manuscript") if isinstance(level, int) else "manuscript"
        held_by = raw.get("heldBy") or []
        closure = raw.get("closureStatus")
        access_note = "Held by The National Archives (Kew, UK). Order the document to a reading room or request a digital copy via the catalogue entry."
        if closure and closure != "O":
            access_note += " The catalogue marks this record as not open (closure status " + str(closure) + ")."
        return NormalizedRecord(
            source_system=self.name,
            source_record_id=rid or (reference or title),
            title=title,
            creators=[c for c in (clean(x) for x in (raw.get("corpBodies") or [])) if c],
            description=description,
            subjects=[s for s in (clean(x) for x in (raw.get("places") or [])) if s],
            date_text=date_text,
            date_start=ds,
            date_end=de,
            resource_type=rtype,
            language=["en"],
            identifiers={"tna_id": rid, "reference": reference, "catalogue_level": level, "department": raw.get("department"), "held_by": held_by},
            original_url=f"https://discovery.nationalarchives.gov.uk/details/r/{rid}" if rid else "https://discovery.nationalarchives.gov.uk/",
            digital_url=None,
            rights="Crown copyright / Open Government Licence applies to most TNA catalogue descriptions; the documents' own rights vary. See the catalogue entry.",
            rights_status="unknown",
            access_type="physical",
            access_note=access_note,
            holding_verification="catalogue_record",
            call_number=reference,
            raw_metadata={k: v for k, v in raw.items() if k != "_provenance"},
            institution_slug=INSTITUTION_SLUG,
            provenance=provenance or raw.get("_provenance", {}) or {"adapter": self.name},
        )


ADAPTER = register(TnaDiscoveryAdapter())
