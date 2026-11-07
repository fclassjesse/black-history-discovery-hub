"""Dalhousie University Archives finding aids via OAI-PMH (keyless, Dublin Core).

Endpoint: https://findingaids.library.dal.ca/;oai  (AtoM). OAI-PMH has no search verb and the feed holds
well over 200,000 descriptions, so a whole-feed harvest is not practical. Strategy:

1. `ListSets` → one set per top-level fonds/collection (~630).
2. `GetRecord` for each set's own description (fonds title + scope note), 1 req/s, cached on disk 7 days.
3. For a query, keep the fonds whose description contains every significant query word (whole words,
   plural-tolerant), then `ListRecords&set=…` for those fonds (a few pages each) so item-level
   descriptions come in too. Items carry "Part of: <fonds>" so search can find them.

Limitation (documented in docs/sources.md): relevant items inside a fonds whose own description does not
mention the topic are not reached. Original-source URL: the finding-aid page in dc:identifier. Physical
holding: Dalhousie University Archives (catalogue record — a finding aid describes what the archive holds).
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any

from app.adapters.base import ConnectorStatus, NormalizedRecord, SourceAdapter, register
from app.config import get_settings
from app.services.http import BlockedError, get_http
from app.services.normalize import clean, lang_code, parse_year_range
from app.services.textmatch import text_matches

OAI_ENDPOINT = "https://findingaids.library.dal.ca/;oai"
NS = {
    "oai": "http://www.openarchives.org/OAI/2.0/",
    "oai_dc": "http://www.openarchives.org/OAI/2.0/oai_dc/",
    "dc": "http://purl.org/dc/elements/1.1/",
}
INSTITUTION_SLUG = "dalhousie-university-archives"
MAX_SETS_PER_QUERY = 8

FORMAT_TYPES: list[tuple[str, str]] = [
    ("map", "map"), ("plan", "map"), ("photograph", "image"), ("negative", "image"), ("slide", "image"),
    ("print", "image"), ("drawing", "image"), ("poster", "image"), ("sound", "audio"), ("audio", "audio"),
    ("cassette", "audio"), ("moving image", "video"), ("video", "video"), ("film", "video"),
]


class ChallengeError(Exception):
    """AtoM's JavaScript challenge page: the feed exists but is closed to automated clients."""


def _looks_like_atom_challenge(text: str) -> bool:
    head = text[:3000]
    return "atom_challenge_redirect_url" in head or ("/challenge" in head and "JavaScript is required" in text)


def _record_dict(rec: ET.Element) -> dict[str, Any] | None:
    header = rec.find("oai:header", NS)
    if header is None or header.get("status") == "deleted":
        return None
    dc = rec.find(".//oai_dc:dc", NS)
    fields: dict[str, list[str]] = {}
    if dc is not None:
        for el in dc:
            tag = el.tag.split("}")[-1]
            val = clean(el.text)
            if val:
                fields.setdefault(tag, []).append(val)
    return {
        "oai_identifier": header.findtext("oai:identifier", default="", namespaces=NS),
        "datestamp": header.findtext("oai:datestamp", default="", namespaces=NS),
        "sets": [s.text for s in header.findall("oai:setSpec", NS) if s.text],
        "dc": fields,
    }


def _parse_root(xml_text: str) -> ET.Element:
    if _looks_like_atom_challenge(xml_text):
        raise ChallengeError("Server answered with a JavaScript challenge page instead of OAI-PMH XML")
    return ET.fromstring(xml_text)


def _error(root: ET.Element) -> str | None:
    err = root.find("oai:error", NS)
    return f"{err.get('code')}: {(err.text or '').strip()}" if err is not None else None


def _token(root: ET.Element) -> str | None:
    el = root.find(".//oai:resumptionToken", NS)
    tok = (el.text or "").strip() if el is not None else ""
    return tok or None


def parse_oai_page(xml_text: str) -> tuple[list[dict[str, Any]], str | None, str | None]:
    """ListRecords page → (records, resumption_token, error). Each record is a JSON-serializable dict."""
    root = _parse_root(xml_text)
    err = _error(root)
    if err:
        return [], None, err
    records = [d for d in (_record_dict(r) for r in root.findall(".//oai:record", NS)) if d]
    return records, _token(root), None


def parse_sets_page(xml_text: str) -> tuple[list[tuple[str, str]], str | None, str | None]:
    """ListSets page → ([(setSpec, setName)], resumption_token, error)."""
    root = _parse_root(xml_text)
    err = _error(root)
    if err:
        return [], None, err
    sets = []
    for s in root.findall(".//oai:set", NS):
        spec = s.findtext("oai:setSpec", default="", namespaces=NS)
        name = clean(s.findtext("oai:setName", default="", namespaces=NS)) or spec
        if spec:
            sets.append((spec, name))
    return sets, _token(root), None


def parse_get_record(xml_text: str) -> tuple[dict[str, Any] | None, str | None]:
    root = _parse_root(xml_text)
    err = _error(root)
    if err:
        return None, err
    rec = root.find(".//oai:record", NS)
    return (_record_dict(rec) if rec is not None else None), None


def record_text(raw: dict[str, Any]) -> str:
    dc = raw.get("dc", {})
    parts = [*dc.get("title", []), *dc.get("description", []), *dc.get("subject", []), *dc.get("creator", []), *dc.get("coverage", [])]
    if raw.get("set_name"):
        parts.append(raw["set_name"])
    return " ".join(parts)


def matches(raw: dict[str, Any], query: str) -> bool:
    """Every significant query word must occur as a whole word (so 'Black' never matches 'Blackmore');
    simple plurals are tolerated ('Loyalists' ~ 'Loyalist'). See app.services.textmatch."""
    return text_matches(record_text(raw), query)


class DalOaiAdapter(SourceAdapter):
    name = "dal_oai"
    label = "Dalhousie University Archives finding aids (OAI-PMH / Dublin Core)"
    docs_url = "https://findingaids.library.dal.ca/"
    requires_key = False
    min_interval = 1.0

    def __init__(self) -> None:
        self._sets: list[tuple[str, str]] | None = None
        self._fonds: dict[str, dict[str, Any]] | None = None  # setSpec → fonds-level record
        self._set_records: dict[str, list[dict[str, Any]]] = {}
        self._note: str = ""

    # --- status -----------------------------------------------------------
    async def status(self) -> ConnectorStatus:
        now = datetime.now(timezone.utc)
        try:
            res = await get_http().get(OAI_ENDPOINT, {"verb": "Identify"}, source=self.name, cache=True, ttl=600)
            if _looks_like_atom_challenge(res.text):
                return ConnectorStatus(name=self.name, label=self.label, state="blocked", detail="The feed answers automated clients with a JavaScript challenge page. Not circumvented.", docs_url=self.docs_url, checked_at=res.fetched_at)
            root = ET.fromstring(res.text)
            name = root.findtext(".//oai:Identify/oai:repositoryName", default="", namespaces=NS)
            if not name:
                return ConnectorStatus(name=self.name, label=self.label, state="error", detail="Identify response did not look like OAI-PMH.", docs_url=self.docs_url, checked_at=res.fetched_at)
            detail = f"Live and keyless (repository: {name}). No search API: fonds-level descriptions are harvested and matched locally, then matching fonds are read in full."
            if self._note:
                detail += " " + self._note
            return ConnectorStatus(name=self.name, label=self.label, state="ok", detail=detail, docs_url=self.docs_url, checked_at=res.fetched_at)
        except BlockedError as e:
            return ConnectorStatus(name=self.name, label=self.label, state="blocked", detail=e.detail, docs_url=self.docs_url, checked_at=now)
        except Exception as e:  # noqa: BLE001
            return ConnectorStatus(name=self.name, label=self.label, state="error", detail=f"{type(e).__name__}: {e}", docs_url=self.docs_url, checked_at=now)

    # --- harvest helpers --------------------------------------------------
    async def _get(self, params: dict[str, Any]) -> str:
        res = await get_http().get(OAI_ENDPOINT, params, source=self.name, min_interval=self.min_interval)
        if _looks_like_atom_challenge(res.text):
            raise BlockedError(res.url, res.status_code, "Server answered with a JavaScript challenge page instead of OAI-PMH XML")
        self._last_url = res.url
        return res.text

    async def list_sets(self) -> list[tuple[str, str]]:
        if self._sets is not None:
            return self._sets
        out: list[tuple[str, str]] = []
        token: str | None = None
        while True:
            params = {"verb": "ListSets", "resumptionToken": token} if token else {"verb": "ListSets"}
            sets, token, err = parse_sets_page(await self._get(params))
            if err:
                raise RuntimeError(f"OAI-PMH ListSets error: {err}")
            out.extend(sets)
            if not token:
                break
        self._sets = out
        return out

    async def fonds_records(self) -> dict[str, dict[str, Any]]:
        """Fonds-level description for every set (GetRecord on the set's own identifier)."""
        if self._fonds is not None:
            return self._fonds
        sets = await self.list_sets()
        limit = get_settings().dal_oai_max_sets
        fonds: dict[str, dict[str, Any]] = {}
        for spec, name in sets[:limit]:
            rec, err = parse_get_record(await self._get({"verb": "GetRecord", "identifier": spec, "metadataPrefix": "oai_dc"}))
            if err or rec is None:
                continue
            rec["set_name"] = name
            rec["set_spec"] = spec
            rec["is_fonds"] = True
            fonds[spec] = rec
        self._fonds = fonds
        self._note = f"{len(fonds)} fonds-level descriptions read" + ("." if len(sets) <= limit else f" (first {limit} of {len(sets)} sets; raise DAL_OAI_MAX_SETS to read all).")
        return fonds

    async def set_records(self, spec: str, name: str) -> list[dict[str, Any]]:
        if spec in self._set_records:
            return self._set_records[spec]
        out: list[dict[str, Any]] = []
        token: str | None = None
        pages = 0
        max_pages = get_settings().dal_oai_max_pages_per_set
        while pages < max_pages:
            params = {"verb": "ListRecords", "resumptionToken": token} if token else {"verb": "ListRecords", "metadataPrefix": "oai_dc", "set": spec}
            records, token, err = parse_oai_page(await self._get(params))
            if err:
                if not err.startswith("noRecordsMatch"):
                    raise RuntimeError(f"OAI-PMH ListRecords error: {err}")
                break
            pages += 1
            for r in records:
                r["set_name"] = name
                r["set_spec"] = spec
                r["is_fonds"] = r["oai_identifier"] == spec
                out.append(r)
            if not token or not records:
                break
        self._set_records[spec] = out
        return out

    # --- SourceAdapter ----------------------------------------------------
    async def search(self, query: str, max_records: int = 20) -> list[dict[str, Any]]:
        fonds = await self.fonds_records()
        matching = [f for f in fonds.values() if matches(f, query)][:MAX_SETS_PER_QUERY]
        prov_base = {"adapter": self.name, "fetched_at": datetime.now(timezone.utc).isoformat(), "query": query}
        fonds_hits: list[dict[str, Any]] = []
        direct_hits: list[dict[str, Any]] = []
        rest: list[dict[str, Any]] = []
        for f in matching:
            fonds_hits.append(dict(f, _provenance={**prov_base, "request_url": f"{OAI_ENDPOINT}?verb=GetRecord&identifier={f['set_spec']}&metadataPrefix=oai_dc"}))
            try:
                children = await self.set_records(f["set_spec"], f["set_name"])
            except RuntimeError:
                children = []
            for c in children:
                if c["oai_identifier"] == f["oai_identifier"]:
                    continue
                target = direct_hits if matches(dict(c, set_name=None), query) else rest
                target.append(dict(c, _provenance={**prov_base, "request_url": f"{OAI_ENDPOINT}?verb=ListRecords&metadataPrefix=oai_dc&set={f['set_spec']}"}))
        return (fonds_hits + direct_hits + rest)[:max_records]

    def normalize(self, raw: dict[str, Any], provenance: dict[str, Any] | None = None) -> NormalizedRecord:
        dc = raw.get("dc", {})
        oai_id = raw.get("oai_identifier", "")
        title = clean(dc.get("title", [None])[0]) or "(untitled finding aid)"
        urls = [i for i in dc.get("identifier", []) if i.startswith("http")]
        ref_codes = [i for i in dc.get("identifier", []) if not i.startswith("http")]
        original_url = urls[0].replace("dal.ca//", "dal.ca/") if urls else f"https://findingaids.library.dal.ca/search?query={oai_id}"

        date_text = clean(dc.get("date", [None])[0])
        date_start, date_end = parse_year_range(date_text)
        fmt = clean(" ; ".join(dc.get("format", [])))
        set_name = raw.get("set_name")
        is_child = bool(set_name) and not raw.get("is_fonds")
        desc_bits = []
        if is_child:
            desc_bits.append(f"Part of: {set_name}.")
        desc_bits.extend(dc.get("description", []))
        if fmt:
            desc_bits.append(f"Extent: {fmt}")
        if ref_codes:
            desc_bits.append("Reference code: " + "; ".join(ref_codes))
        description = clean(" ".join(desc_bits)) if desc_bits else None

        low = (fmt or "").lower()
        rtype = next((t for key, t in FORMAT_TYPES if key in low), None)
        if rtype is None:
            tl = title.lower()
            rtype = "archival_collection" if raw.get("is_fonds") or any(w in tl for w in ("fonds", "collection", "series", "sous-fonds")) else "manuscript"

        langs = list(dict.fromkeys(c for c in (lang_code(v) for v in dc.get("language", [])) if c))
        creators = list(dict.fromkeys(c for c in (clean(v) for v in dc.get("creator", []) + dc.get("contributor", [])) if c))
        subjects = list(dict.fromkeys(s for s in (clean(v) for v in dc.get("subject", []) + dc.get("coverage", [])) if s))
        if is_child and set_name not in subjects:
            subjects.append(set_name)

        identifiers: dict[str, Any] = {"oai_identifier": oai_id}
        if ref_codes:
            identifiers["reference_code"] = ref_codes[0]
        if raw.get("sets"):
            identifiers["oai_sets"] = raw["sets"]
        if set_name:
            identifiers["fonds"] = set_name

        updated = None
        if raw.get("datestamp"):
            try:
                updated = datetime.fromisoformat(raw["datestamp"].replace("Z", "+00:00"))
            except ValueError:
                updated = None

        return NormalizedRecord(
            source_system=self.name,
            source_record_id=oai_id or original_url,
            title=title,
            creators=creators,
            description=description,
            subjects=subjects,
            date_text=date_text,
            date_start=date_start,
            date_end=date_end,
            resource_type=rtype,
            language=langs,
            identifiers=identifiers,
            original_url=original_url,
            digital_url=None,
            rights="Not stated in the finding aid. Consult Dalhousie University Archives for reproduction and use terms.",
            rights_status="unknown",
            access_type="physical",
            access_note="Held by Dalhousie University Archives (Killam Memorial Library, Halifax). The finding aid is online; the material is consulted in the reading room by appointment.",
            holding_verification="catalogue_record",
            call_number=ref_codes[0] if ref_codes else None,
            raw_metadata={k: v for k, v in raw.items() if k != "_provenance"},
            source_updated_at=updated,
            institution_slug=INSTITUTION_SLUG,
            provenance=provenance or raw.get("_provenance", {}) or {"adapter": self.name},
        )


ADAPTER = register(DalOaiAdapter())
