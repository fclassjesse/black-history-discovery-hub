"""CKAN catalogues — the open-source data portal software (https://ckan.org), keyless Action API.

Docs: https://docs.ckan.org/en/latest/api/ · Endpoint: GET {site}/api/3/action/package_search?q=...&rows=N&start=O
One adapter class serves any CKAN portal: a partner (or BCCNS itself) that publishes its catalogue on CKAN is
added with one `register(CkanAdapter(...))` line. Registered today: the Government of Canada Open Government
Portal (open.canada.ca), which runs CKAN with bilingual extras (`title_translated`, `keywords`).

CKAN full-text search is broad ("African Nova Scotian" also returns ocean-chemistry datasets), so every hit must
pass the same whole-word on-topic check as Wikimedia Commons and Dalhousie before it is stored.
Datasets published by an organisation we already harvest from its own portal (`skip_orgs`) are dropped: the
original portal is the authoritative copy.
Original-source URL: the dataset page on the portal. These are ONLINE datasets/publications, never archival holdings.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.adapters.base import ConnectorStatus, NormalizedRecord, SourceAdapter, register
from app.services.http import BlockedError, get_http
from app.services.normalize import clean, parse_year_range, truncate
from app.services.textmatch import on_black_history_topic, text_matches

PAGE_SIZE = 50
MAX_PAGES = 4


def _en(value: Any) -> str:
    """CKAN core fields are strings; open.canada.ca adds {'en': ..., 'fr': ...} dicts and 'English | French' org titles."""
    if isinstance(value, dict):
        return clean(value.get("en") or next(iter(value.values()), "")) or ""
    return clean(value) or ""


def _org_title(raw: dict[str, Any]) -> str:
    org = raw.get("organization") or {}
    return _en(org.get("title")).split(" | ")[0].strip()


def _keywords(raw: dict[str, Any]) -> list[str]:
    kw = raw.get("keywords")
    out = list(kw.get("en") or []) if isinstance(kw, dict) else []
    out += [t.get("display_name") or t.get("name") for t in raw.get("tags") or [] if isinstance(t, dict)]
    return [k for k in dict.fromkeys(clean(k) for k in out) if k]


class CkanAdapter(SourceAdapter):
    requires_key = False
    min_interval = 1.0

    def __init__(self, *, name: str, label: str, site: str, dataset_url: str, institution_slug: str, skip_orgs: tuple[str, ...] = ()) -> None:
        self.name = name
        self.label = label
        self.site = site.rstrip("/")
        self.docs_url = "https://docs.ckan.org/en/latest/api/"
        self.dataset_url = dataset_url  # format string with {name}
        self.institution_slug = institution_slug
        self.skip_orgs = tuple(o.lower() for o in skip_orgs)

    @property
    def search_url(self) -> str:
        return f"{self.site}/api/3/action/package_search"

    def _status(self, state: str, detail: str, at: datetime | None = None) -> ConnectorStatus:
        return ConnectorStatus(name=self.name, label=self.label, state=state, detail=detail, docs_url=self.docs_url, checked_at=at or datetime.now(timezone.utc))  # type: ignore[arg-type]

    async def status(self) -> ConnectorStatus:
        try:
            res = await get_http().get(self.search_url, {"q": "Black history", "rows": "1"}, source=self.name, ttl=600)
            if not res.ok:
                return self._status("error", f"HTTP {res.status_code}", res.fetched_at)
            n = (res.json().get("result") or {}).get("count", 0)
            return self._status("ok", f"Live and keyless CKAN API ({n} datasets for test query, before the on-topic filter).", res.fetched_at)
        except BlockedError as e:
            return self._status("blocked", e.detail)
        except Exception as e:  # noqa: BLE001
            return self._status("error", f"{type(e).__name__}: {e}")

    def keep(self, raw: dict[str, Any], query: str) -> bool:
        if _org_title(raw).lower() in self.skip_orgs:
            return False
        title_kw = " ".join([_en(raw.get("title_translated") or raw.get("title")), " ".join(_keywords(raw))])
        if not on_black_history_topic(title_kw):
            return False
        return text_matches(title_kw + " " + _en(raw.get("notes_translated") or raw.get("notes")), query)

    async def search(self, query: str, max_records: int = 20) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for page in range(MAX_PAGES):
            res = await get_http().get(self.search_url, {"q": query, "rows": str(PAGE_SIZE), "start": str(page * PAGE_SIZE)}, source=self.name)
            if not res.ok:
                raise RuntimeError(f"CKAN HTTP {res.status_code}")
            result = res.json().get("result") or {}
            hits = result.get("results") or []
            for r in hits:
                if self.keep(r, query):
                    r["_provenance"] = res.provenance(self.name, query)
                    out.append(r)
            if len(out) >= max_records or not hits or (page + 1) * PAGE_SIZE >= int(result.get("count") or 0):
                break
        return out[:max_records]

    def normalize(self, raw: dict[str, Any], provenance: dict[str, Any] | None = None) -> NormalizedRecord:
        rid = str(raw.get("id") or raw.get("name") or "")
        org = _org_title(raw)
        resources = [r for r in raw.get("resources") or [] if r.get("url")]
        formats = sorted({clean(r.get("format")).upper() for r in resources if clean(r.get("format"))})
        notes = _en(raw.get("notes_translated") or raw.get("notes"))
        desc = notes + (f" Formats: {', '.join(formats)}." if formats else "")
        published = clean(raw.get("date_published"))[:10]
        ds, de = parse_year_range(published or None)
        updated = None
        if raw.get("metadata_modified"):
            try:
                updated = datetime.fromisoformat(str(raw["metadata_modified"])).replace(tzinfo=timezone.utc)
            except ValueError:
                updated = None
        licence = clean(raw.get("license_title"))
        return NormalizedRecord(
            source_system=self.name,
            source_record_id=rid,
            title=_en(raw.get("title_translated") or raw.get("title")) or "(untitled dataset)",
            creators=[org] if org else [],
            description=truncate(clean(desc), 2000) or None,
            subjects=_keywords(raw)[:25],
            date_text=published or None,
            date_start=ds,
            date_end=de,
            resource_type="dataset" if raw.get("collection") in (None, "", "primary") else "other",
            language=["en", "fr"] if isinstance(raw.get("title_translated"), dict) else ["en"],
            identifiers={"ckan_id": rid, "ckan_name": raw.get("name"), "portal": self.site},
            original_url=self.dataset_url.format(name=raw.get("name") or rid),
            digital_url=resources[0]["url"] if resources else None,
            rights=licence or None,
            rights_status="open_licence" if raw.get("isopen") or "open government licence" in licence.lower() else "unknown",
            access_type="online",
            access_note=f"Published online by {org or 'the portal'}; open the dataset page for files and links. Not an archival holding.",
            holding_verification="online_item",
            raw_metadata={k: v for k, v in raw.items() if k != "_provenance"},
            source_updated_at=updated,
            institution_slug=self.institution_slug,
            provenance=provenance or raw.get("_provenance", {}) or {"adapter": self.name},
        )


OPEN_CANADA = register(CkanAdapter(
    name="ckan_open_canada",
    label="Open Government Portal, Canada (CKAN)",
    site="https://open.canada.ca/data",
    dataset_url="https://open.canada.ca/data/en/dataset/{name}",
    institution_slug="open-government-canada",
    skip_orgs=("Government of Nova Scotia",),  # harvested from data.novascotia.ca directly (ns_open_data)
))
