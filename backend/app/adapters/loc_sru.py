"""Library of Congress catalogue via SRU (keyless). Returns MARCXML.

Docs: https://www.loc.gov/apis/additional-apis/search-retrieval-via-url/
Endpoint: http://lx2.loc.gov:210/LCDB?version=1.1&operation=searchRetrieve&query=<CQL>&maximumRecords=N&recordSchema=marcxml
Original-source URL: https://lccn.loc.gov/{lccn}. Physical holding: Library of Congress (catalogue record).
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any

from app.adapters.base import ConnectorStatus, NormalizedRecord, SourceAdapter, register
from app.services.http import BlockedError, get_http
from app.services.normalize import clean, lang_code, parse_year_range, strip_marc_punct

SRU_ENDPOINT = "http://lx2.loc.gov:210/LCDB"
NS = {"zs": "http://www.loc.gov/zing/srw/", "marc": "http://www.loc.gov/MARC21/slim"}
INSTITUTION_SLUG = "library-of-congress"

LEADER_TYPE = {
    "a": "book", "t": "manuscript", "k": "image", "g": "video", "i": "audio", "j": "audio",
    "e": "map", "f": "map", "m": "dataset", "p": "archival_collection", "o": "other", "r": "artifact",
}


def cql_for(query: str) -> str:
    """Natural phrase → CQL. Quoted phrases kept; remaining words ANDed. Supports -term exclusion."""
    phrases = re.findall(r'"([^"]+)"', query)
    rest = re.sub(r'"[^"]+"', " ", query)
    terms: list[str] = [f'"{p}"' for p in phrases]
    excludes: list[str] = []
    for w in rest.split():
        if w.startswith("-") and len(w) > 1:
            excludes.append(w[1:])
        elif w.lower() not in ("and", "or", "not"):
            terms.append(f'"{w}"')
    cql = " and ".join(terms) if terms else '"history"'
    for ex in excludes:
        cql += f' not "{ex}"'
    return cql


def marc_to_dict(record_el: ET.Element) -> dict[str, Any]:
    """Flatten a MARCXML record into a JSON-serializable dict (tag → list of {ind1, ind2, subfields})."""
    out: dict[str, Any] = {"leader": (record_el.findtext("marc:leader", default="", namespaces=NS) or ""), "control": {}, "fields": []}
    for cf in record_el.findall("marc:controlfield", NS):
        out["control"][cf.get("tag", "")] = cf.text or ""
    for df in record_el.findall("marc:datafield", NS):
        out["fields"].append({
            "tag": df.get("tag", ""), "ind1": df.get("ind1", " "), "ind2": df.get("ind2", " "),
            "sub": [(sf.get("code", ""), sf.text or "") for sf in df.findall("marc:subfield", NS)],
        })
    return out


def parse_sru(xml_text: str) -> tuple[int, list[dict[str, Any]], str | None]:
    root = ET.fromstring(xml_text)
    diag = root.find(".//{http://www.loc.gov/zing/srw/diagnostic/}message")
    if diag is not None:
        return 0, [], diag.text
    total = int(root.findtext("zs:numberOfRecords", default="0", namespaces=NS) or 0)
    records = [marc_to_dict(r) for r in root.findall(".//marc:record", NS)]
    return total, records, None


def _fields(raw: dict, tag: str) -> list[dict]:
    return [f for f in raw.get("fields", []) if f["tag"] == tag]


def _sub(field: dict, codes: str, sep: str = " ") -> str | None:
    vals = [v for c, v in field["sub"] if c in codes]
    return clean(sep.join(vals)) if vals else None


class LocSruAdapter(SourceAdapter):
    name = "loc_sru"
    label = "Library of Congress catalogue (SRU / MARCXML)"
    docs_url = "https://www.loc.gov/apis/additional-apis/search-retrieval-via-url/"
    requires_key = False
    min_interval = 1.0

    async def status(self) -> ConnectorStatus:
        try:
            res = await get_http().get(
                SRU_ENDPOINT,
                {"version": "1.1", "operation": "searchRetrieve", "query": '"Nova Scotia"', "maximumRecords": "1", "recordSchema": "marcxml"},
                source=self.name, cache=True, ttl=600,
            )
            total, _, diag = parse_sru(res.text)
            if diag:
                return ConnectorStatus(name=self.name, label=self.label, state="error", detail=f"SRU diagnostic: {diag}", docs_url=self.docs_url, checked_at=res.fetched_at)
            return ConnectorStatus(name=self.name, label=self.label, state="ok", detail=f"Live and keyless ({total} hits for test query).", docs_url=self.docs_url, checked_at=res.fetched_at)
        except BlockedError as e:
            return ConnectorStatus(name=self.name, label=self.label, state="blocked", detail=e.detail, docs_url=self.docs_url, checked_at=datetime.now(timezone.utc))
        except Exception as e:  # noqa: BLE001
            return ConnectorStatus(name=self.name, label=self.label, state="error", detail=f"{type(e).__name__}: {e}", docs_url=self.docs_url, checked_at=datetime.now(timezone.utc))

    async def search(self, query: str, max_records: int = 20) -> list[dict[str, Any]]:
        http = get_http()
        out: list[dict[str, Any]] = []
        start = 1
        page = min(max_records, 50)
        while len(out) < max_records:
            res = await http.get(
                SRU_ENDPOINT,
                {"version": "1.1", "operation": "searchRetrieve", "query": cql_for(query), "startRecord": str(start),
                 "maximumRecords": str(page), "recordSchema": "marcxml"},
                source=self.name,
            )
            total, records, diag = parse_sru(res.text)
            if diag:
                raise RuntimeError(f"SRU diagnostic: {diag}")
            for r in records:
                r["_provenance"] = res.provenance(self.name, query)
                out.append(r)
            if not records or start + len(records) > total:
                break
            start += len(records)
        return out[:max_records]

    def normalize(self, raw: dict[str, Any], provenance: dict[str, Any] | None = None) -> NormalizedRecord:
        control_no = clean(raw.get("control", {}).get("001")) or ""
        f008 = raw.get("control", {}).get("008", "")
        leader = raw.get("leader", "")
        lccn = None
        for f in _fields(raw, "010"):
            lccn = (_sub(f, "a") or "").replace(" ", "") or None
            if lccn:
                break
        isbns = [re.sub(r"[^0-9Xx]", "", _sub(f, "a") or "") for f in _fields(raw, "020")]
        isbns = [i for i in isbns if i]
        oclc = next((v for f in _fields(raw, "035") for c, v in f["sub"] if c == "a" and "OCoLC" in v), None)

        title = None
        for f in _fields(raw, "245"):
            title = strip_marc_punct(_sub(f, "ab"))
        title = title or "(untitled catalogue record)"

        creators = []
        for tag in ("100", "110", "111", "700", "710", "711"):
            for f in _fields(raw, tag):
                c = strip_marc_punct(_sub(f, "abcdq"))
                if c and c not in creators:
                    creators.append(c)

        subjects = []
        for tag in ("600", "610", "611", "630", "650", "651", "655"):
            for f in _fields(raw, tag):
                parts = [clean(v) for c, v in f["sub"] if c in "abcdxyzv" and clean(v)]
                s = strip_marc_punct(" -- ".join(p for p in parts if p))
                if s and s not in subjects:
                    subjects.append(s)

        pub_parts = []
        date_text = None
        for tag in ("264", "260"):
            for f in _fields(raw, tag):
                if tag == "264" and f["ind2"] not in ("1", " ", "0"):
                    continue
                pub = strip_marc_punct(_sub(f, "ab"))
                if pub:
                    pub_parts.append(pub)
                d = strip_marc_punct(_sub(f, "c"))
                if d and not date_text:
                    date_text = d
            if pub_parts:
                break
        date_start, date_end = parse_year_range(date_text)
        if date_start is None and len(f008) >= 15:
            date_start, date_end = parse_year_range(f008[7:11] + " " + f008[11:15])
            if date_start and not date_text:
                date_text = str(date_start)

        extent = next((strip_marc_punct(_sub(f, "abc")) for f in _fields(raw, "300")), None)
        notes = []
        for tag in ("500", "504", "505", "520", "530", "545", "546"):
            for f in _fields(raw, tag):
                n = clean(_sub(f, "a"))
                if n:
                    notes.append(n)
        desc_bits = []
        if pub_parts:
            desc_bits.append("Published: " + "; ".join(pub_parts) + (f", {date_text}" if date_text else ""))
        if extent:
            desc_bits.append(extent)
        desc_bits.extend(notes[:6])
        description = clean(" ".join(desc_bits)) if desc_bits else None

        langs = []
        if len(f008) >= 38 and lang_code(f008[35:38]):
            langs.append(lang_code(f008[35:38]))
        for f in _fields(raw, "041"):
            for c, v in f["sub"]:
                if c == "a" and lang_code(v) and lang_code(v) not in langs:
                    langs.append(lang_code(v))

        call_number = next((strip_marc_punct(_sub(f, "ab")) for f in _fields(raw, "050")), None)

        digital_url = None
        for f in _fields(raw, "856"):
            if f["ind2"] in ("0", "1"):
                u = _sub(f, "u")
                if u and u.startswith("http"):
                    digital_url = u
                    break

        rtype = LEADER_TYPE.get(leader[6] if len(leader) > 6 else "", "other")
        if len(leader) > 7 and leader[7] == "s":
            rtype = "serial"
        if len(leader) > 7 and leader[7] == "c" and rtype == "book":
            rtype = "archival_collection"

        original_url = f"https://lccn.loc.gov/{lccn}" if lccn else f"https://catalog.loc.gov/vwebv/holdingsInfo?bibId={control_no}"
        identifiers: dict[str, Any] = {"lc_control_number": control_no}
        if lccn:
            identifiers["lccn"] = lccn
        if isbns:
            identifiers["isbn"] = isbns
        if oclc:
            identifiers["oclc"] = oclc.replace("(OCoLC)", "")

        return NormalizedRecord(
            source_system=self.name,
            source_record_id=control_no or (lccn or original_url),
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
            digital_url=digital_url,
            rights="Not stated in the catalogue record. The item is held physically by the Library of Congress; consult the record for terms.",
            rights_status="unknown",
            access_type="both" if digital_url else "physical",
            access_note="Held by the Library of Congress (Washington, DC). Use the catalogue record to request the item in a reading room." + (" A digital version is linked from the record." if digital_url else ""),
            holding_verification="catalogue_record",
            call_number=call_number,
            raw_metadata={k: v for k, v in raw.items() if k != "_provenance"},
            institution_slug=INSTITUTION_SLUG,
            provenance=provenance or raw.get("_provenance", {}) or {"adapter": self.name},
        )


ADAPTER = register(LocSruAdapter())
