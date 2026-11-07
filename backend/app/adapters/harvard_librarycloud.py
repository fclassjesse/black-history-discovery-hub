"""Harvard Library — LibraryCloud Item API (keyless, MODS as JSON).

Docs: https://wiki.harvard.edu/confluence/display/LibraryStaffDoc/LibraryCloud+APIs
Endpoint: GET https://api.lib.harvard.edu/v2/items.json?q=...&limit=N&start=S
Original-source URL: HOLLIS catalogue record https://hollis.harvard.edu/permalink/f/1s5nrq/HVD2{recordIdentifier}
(when the record identifier is an Alma MMS id); otherwise the LibraryCloud item itself. Physical holding: the
Harvard repository named in MODS `location/physicalLocation` (catalogue record); e-resources are linked.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.adapters.base import ConnectorStatus, NormalizedRecord, SourceAdapter, register
from app.services.http import BlockedError, get_http
from app.services.normalize import clean, lang_code, parse_year_range, truncate

ITEMS_URL = "https://api.lib.harvard.edu/v2/items.json"
INSTITUTION_SLUG = "harvard-library"
TYPE_MAP = {"text": "book", "still image": "image", "cartographic": "map", "sound recording": "audio", "moving image": "video", "mixed material": "archival_collection", "notated music": "other", "three dimensional object": "artifact"}


def _as_list(v: Any) -> list[Any]:
    if v is None:
        return []
    return v if isinstance(v, list) else [v]


def _text(v: Any) -> str | None:
    """MODS-as-JSON values are strings or {"#text": ..., "@attr": ...} objects."""
    if v is None:
        return None
    if isinstance(v, dict):
        return clean(str(v.get("#text", "")))
    if isinstance(v, list):
        return clean(" ".join(t for t in (_text(x) for x in v) if t))
    return clean(str(v))


def _attr(v: Any, name: str) -> str | None:
    return v.get(name) if isinstance(v, dict) else None


class HarvardLibraryCloudAdapter(SourceAdapter):
    name = "harvard_librarycloud"
    label = "Harvard Library (LibraryCloud item API)"
    docs_url = "https://wiki.harvard.edu/confluence/display/LibraryStaffDoc/LibraryCloud+APIs"
    requires_key = False
    min_interval = 1.0

    def _status(self, state: str, detail: str, at: datetime | None = None) -> ConnectorStatus:
        return ConnectorStatus(name=self.name, label=self.label, state=state, detail=detail, docs_url=self.docs_url, checked_at=at or datetime.now(timezone.utc))  # type: ignore[arg-type]

    async def status(self) -> ConnectorStatus:
        try:
            res = await get_http().get(ITEMS_URL, {"q": "Nova Scotia", "limit": "1"}, source=self.name, ttl=600)
            if not res.ok:
                return self._status("error", f"HTTP {res.status_code}", res.fetched_at)
            n = (res.json().get("pagination") or {}).get("numFound", 0)
            return self._status("ok", f"Live and keyless ({n} hits for test query).", res.fetched_at)
        except BlockedError as e:
            return self._status("blocked", e.detail)
        except Exception as e:  # noqa: BLE001
            return self._status("error", f"{type(e).__name__}: {e}")

    async def search(self, query: str, max_records: int = 20) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        start = 0
        while len(out) < max_records:
            res = await get_http().get(ITEMS_URL, {"q": query, "limit": str(min(max_records - len(out), 50)), "start": str(start)}, source=self.name)
            if not res.ok:
                raise RuntimeError(f"LibraryCloud HTTP {res.status_code}")
            data = res.json()
            items = _as_list((data.get("items") or {}).get("mods"))
            for m in items:
                m["_provenance"] = res.provenance(self.name, query)
                out.append(m)
            total = int((data.get("pagination") or {}).get("numFound") or 0)
            start += len(items)
            if not items or start >= total:
                break
        return out[:max_records]

    def normalize(self, raw: dict[str, Any], provenance: dict[str, Any] | None = None) -> NormalizedRecord:
        ti = _as_list(raw.get("titleInfo"))
        main = next((t for t in ti if isinstance(t, dict) and not t.get("@type")), ti[0] if ti else {})
        title = clean(" ".join(x for x in (_text(main.get("title")), _text(main.get("subTitle"))) if x)) if isinstance(main, dict) else _text(main)
        title = title or "(untitled catalogue record)"

        creators = []
        for n in _as_list(raw.get("name")):
            if not isinstance(n, dict):
                continue
            parts = [p for p in (_text(x) for x in _as_list(n.get("namePart")) if not (isinstance(x, dict) and x.get("@type") == "date")) if p]
            if parts:
                creators.append(clean(" ".join(parts)).rstrip(","))
        creators = list(dict.fromkeys(c for c in creators if c))

        subjects = []
        for s in _as_list(raw.get("subject")):
            if not isinstance(s, dict):
                continue
            bits = []
            for key in ("topic", "geographic", "temporal", "genre", "name"):
                for x in _as_list(s.get(key)):
                    t = _text(x.get("namePart") if isinstance(x, dict) and key == "name" else x)
                    if t:
                        bits.append(t)
            if bits:
                subjects.append(" -- ".join(bits))
        subjects = list(dict.fromkeys(subjects))

        oi = _as_list(raw.get("originInfo"))
        oi0 = oi[0] if oi and isinstance(oi[0], dict) else {}
        date_text = next((t for t in (_text(d) for d in _as_list(oi0.get("dateIssued")) + _as_list(oi0.get("dateCreated"))) if t), None)
        ds, de = parse_year_range(date_text)
        publisher = clean(" ".join(t for t in (_text(a.get("namePart")) for a in _as_list(oi0.get("agent")) if isinstance(a, dict)) if t))
        place = next((t for t in (_text(p.get("placeTerm")) for p in _as_list(oi0.get("place")) if isinstance(p, dict)) if t and len(t) > 3), None)

        rtype = TYPE_MAP.get((_text(raw.get("typeOfResource")) or "").lower(), "other")
        langs = []
        for lg in _as_list(raw.get("language")):
            for term in _as_list(lg.get("languageTerm") if isinstance(lg, dict) else None):
                if _attr(term, "@type") == "code" and lang_code(_text(term)):
                    langs.append(lang_code(_text(term)))
        langs = list(dict.fromkeys(l for l in langs if l))

        pd = raw.get("physicalDescription") if isinstance(raw.get("physicalDescription"), dict) else {}
        extent = _text(pd.get("extent"))
        is_online = any("online" in (_text(f) or "").lower() for f in _as_list(pd.get("form")))

        repo = None
        shelf = None
        digital_url = None
        for loc in _as_list(raw.get("location")):
            if not isinstance(loc, dict):
                continue
            repo = repo or _text(loc.get("physicalLocation"))
            shelf = shelf or _text(loc.get("shelfLocator"))
            for u in _as_list(loc.get("url")):
                t = _text(u)
                if t and t.startswith("http") and not digital_url:
                    digital_url = t

        identifiers: dict[str, Any] = {}
        for ident in _as_list(raw.get("identifier")):
            t = _attr(ident, "@type") or "other"
            identifiers.setdefault(t, []).append(_text(ident))
        ri = raw.get("recordInfo") if isinstance(raw.get("recordInfo"), dict) else {}
        rec_id = _text(ri.get("recordIdentifier")) or ""
        identifiers["record_identifier"] = rec_id
        original_url = f"https://hollis.harvard.edu/permalink/f/1s5nrq/HVD2{rec_id}" if rec_id.startswith("99") else f"https://api.lib.harvard.edu/v2/items.json?recordIdentifier={rec_id}"

        abstract = _text((raw.get("abstract") or {}) if not isinstance(raw.get("abstract"), list) else raw.get("abstract"))
        desc_bits = []
        if publisher or place or date_text:
            desc_bits.append("Published: " + ", ".join(b for b in (place, publisher, date_text) if b))
        if extent:
            desc_bits.append(extent)
        if abstract:
            desc_bits.append(abstract)
        access_type = "online" if is_online and not repo else ("both" if digital_url else "physical")
        note = f"Held by {repo} (Harvard University)." if repo else "Catalogued by Harvard Library; see the HOLLIS record for the holding repository."
        if is_online:
            note += " The catalogue describes an online resource licensed to Harvard; access may require Harvard credentials."
        return NormalizedRecord(
            source_system=self.name,
            source_record_id=rec_id or original_url,
            title=title,
            creators=creators,
            description=truncate(clean(" ".join(desc_bits)), 3000) if desc_bits else None,
            subjects=subjects,
            date_text=date_text,
            date_start=ds,
            date_end=de,
            resource_type=rtype,
            language=langs,
            identifiers=identifiers,
            original_url=original_url,
            digital_url=digital_url,
            rights="Not stated in the catalogue record. Consult the HOLLIS record for terms.",
            rights_status="unknown",
            access_type=access_type,
            access_note=note,
            holding_verification="catalogue_record",
            call_number=shelf,
            raw_metadata={k: v for k, v in raw.items() if k != "_provenance"},
            institution_slug=INSTITUTION_SLUG,
            provenance=provenance or raw.get("_provenance", {}) or {"adapter": self.name},
        )


ADAPTER = register(HarvardLibraryCloudAdapter())
