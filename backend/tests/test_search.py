"""Deterministic advanced search, published-only visibility, pins only for located physical holdings."""
from __future__ import annotations

from app.adapters.base import NormalizedRecord
from app.services.repository import upsert_record
from tests.conftest import make_institution


async def _rec(session, slug, sid, title, **kw):
    base = dict(source_system="t", source_record_id=sid, title=title, original_url=f"https://x.org/{sid}", access_type="physical", institution_slug=slug, resource_type="book", date_start=2000, date_end=2000)
    base.update(kw)
    r, _ = await upsert_record(session, NormalizedRecord(**base))
    return r


async def test_advanced_search_booleans_filters_and_published_only(client, session):
    loc = await make_institution(session, "loc", "Located Library", latitude=44.0, longitude=-63.0, location_precision="building")
    nowhere = await make_institution(session, "nowhere", "Unlocated Archive")
    await _rec(session, "loc", "1", "Black Loyalists in Nova Scotia", creators=["Walker"], date_start=1976, date_end=1976, call_number="E 1")
    await _rec(session, "loc", "2", "Black Loyalists and Sierra Leone", date_start=1999, date_end=1999)
    await _rec(session, "nowhere", "3", "Black Loyalists oral history", resource_type="audio", access_type="physical")
    await _rec(session, "loc", "4", "Africville online item", access_type="online", digital_url="https://x.org/4d")
    await _rec(session, "loc", "5", "Black Loyalists draft", review_status="draft")
    await session.commit()

    r = await client.get("/api/search", params={"q": '"Black Loyalists" -Sierra', "mode": "advanced"})
    d = r.json()
    titles = {x["title"] for x in d["results"]}
    assert "Black Loyalists in Nova Scotia" in titles and "Black Loyalists oral history" in titles
    assert "Black Loyalists and Sierra Leone" not in titles and "Black Loyalists draft" not in titles
    assert d["alias_expansion"] == []

    r = await client.get("/api/search", params={"q": "Black Loyalists", "mode": "advanced", "date_from": 1970, "date_to": 1980})
    assert [x["title"] for x in r.json()["results"]] == ["Black Loyalists in Nova Scotia"]

    r = await client.get("/api/search", params={"q": "Black Loyalists", "mode": "advanced", "types": "audio"})
    assert [x["title"] for x in r.json()["results"]] == ["Black Loyalists oral history"]

    r = await client.get("/api/search", params={"q": "Black Loyalists", "mode": "advanced", "institution": "loc"})
    assert {x["title"] for x in r.json()["results"]} == {"Black Loyalists in Nova Scotia", "Black Loyalists and Sierra Leone"}

    r = await client.get("/api/search", params={"q": "", "access": "online"})
    assert [x["title"] for x in r.json()["results"]] == ["Africville online item"]

    r = await client.get("/api/search", params={"q": "Loyalists"})
    d = r.json()
    assert [p["institution"]["slug"] for p in d["pins"]] == ["loc"], "only located institutions with physical holdings get pins"
    assert d["unknown_location_count"] == 1, "the unlocated archive's record is counted, never pinned"
    assert str(nowhere.id) not in [p["institution"]["id"] for p in d["pins"]] and loc.slug == "loc"


async def test_nonsense_query_returns_nothing(client, session):
    await make_institution(session, "loc", "Located Library")
    await _rec(session, "loc", "n1", "Black Loyalists in Nova Scotia")
    await session.commit()
    r = await client.get("/api/search", params={"q": "zzqxjv nothing here"})
    assert r.json()["total"] == 0 and r.json()["pins"] == []
    r = await client.get("/api/search", params={"q": "", "date_from": 2020, "date_to": 1990})
    assert r.json()["date_from"] == 1990 and r.json()["date_to"] == 2020


async def test_identifier_filter_and_linked_records(client, session):
    await make_institution(session, "a", "A")
    await make_institution(session, "b", "B")
    await _rec(session, "a", "x1", "Razing Africville", creators=["Nelson, Jennifer"], date_start=2008, date_end=2008, identifiers={"lccn": "2008271810"})
    await _rec(session, "b", "x2", "Razing Africville", creators=["Nelson, Jennifer J."], date_start=2008, date_end=2008)
    await session.commit()
    r = await client.get("/api/search", params={"q": "", "identifier": "2008271810", "mode": "advanced"})
    d = r.json()
    assert d["total"] == 1 and d["results"][0]["also_catalogued_at"][0]["institution_name"] == "B", "same work at another institution is linked, never merged"


async def test_country_filter_keeps_only_holdings_in_that_country(client, session):
    await make_institution(session, "ns-arch", "Nova Scotia Holder", country="Canada", latitude=44.6, longitude=-63.6, location_precision="building")
    await make_institution(session, "kew", "Overseas Holder", country="United Kingdom", latitude=51.4, longitude=-0.2, location_precision="building")
    await _rec(session, "ns-arch", "c1", "Black Loyalists land grants")
    await _rec(session, "kew", "c2", "Black Loyalists embarkation list")
    await session.commit()

    d = (await client.get("/api/search", params={"q": "Black Loyalists", "mode": "advanced", "country": "Canada"})).json()
    assert {x["title"] for x in d["results"]} == {"Black Loyalists land grants"}
    assert d["facets"]["country"] == [{"value": "Canada", "count": 1, "label": "Canada"}]
    d = (await client.get("/api/search", params={"q": "Black Loyalists", "mode": "advanced"})).json()
    assert {f["value"] for f in d["facets"]["country"]} == {"Canada", "United Kingdom"}
