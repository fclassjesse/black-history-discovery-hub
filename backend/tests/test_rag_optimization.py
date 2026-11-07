"""Entities, work-key linking, description passages, follow-up retrieval, search log, reranker fallback."""
from __future__ import annotations

from sqlalchemy import select

from app.adapters.base import NormalizedRecord
from app.models import Record, RecordChunk, SearchLog
from app.services import guide
from app.services.entities import entities_for, person_name
from app.services.passages import description_passages, split_passages
from app.services.repository import upsert_record
from app.services.search import SearchFilters
from app.services.workkeys import isbn13, work_keys_for
from tests.conftest import make_institution


def test_person_names_are_recognised_and_corporate_names_are_not():
    assert person_name("Walker, James W. St. G., 1940-") == "Walker, James W. St. G."
    assert person_name("Taylor, Wanda Lauren, author.") == "Taylor, Wanda Lauren"
    assert person_name("Pickford and Black Limited") is None
    assert person_name("African United Baptist Association") is None
    assert person_name("Africville") is None
    assert person_name("Halifax, Nova Scotia") is None and person_name("Halifax, N.S. : Nimbus") is None


def test_entities_come_only_from_the_record_text():
    e = entities_for(
        "Birchtown and the Black Loyalists", ["Taylor, Wanda Lauren, 1976-"],
        ["Black loyalists -- Nova Scotia -- Birchtown -- History", "Hall, William, 1827-1904"],
        "Settlement at Birchtown near Shelburne, N.S.; many later sailed to Freetown, Sierra Leone. Mr Blackmore was not involved.",
    )
    assert e["people"] == ["Taylor, Wanda Lauren", "Hall, William"]
    assert "Birchtown" in e["communities"] and "Shelburne" in e["communities"]
    assert "Sierra Leone" in e["places"] and "Freetown" in e["places"] and "Nova Scotia" in e["places"]
    assert "Blackmore" not in " ".join(e["places"] + e["communities"])


def test_work_keys_normalise_identifiers():
    assert isbn13("0-306-40615-2") == "9780306406157"
    keys = work_keys_for({"isbn": ["1-4426-9158-1"], "oclc": ["(OCoLC)647922097"], "lccn": "2014450157"}, {}, "Razing Africville", ["Nelson, Jennifer"], 2008)
    assert keys == ["isbn:9781442691582", "oclc:647922097", "lccn:2014450157", "dedupe:razing africville|nelson|2008"]


def test_description_passages_are_sentence_aligned_and_capped():
    text = ("The Book of Negroes lists three thousand Black Loyalists who left New York for Nova Scotia in 1783. " * 14).strip()
    ps = description_passages(text, "https://example.org/r/1")
    assert ps and all(p.kind == "description" and p.page_url == "https://example.org/r/1" for p in ps)
    assert all(len(p.text) <= 900 for p in ps)
    assert description_passages("short", "https://x") == []
    assert split_passages("One. Two. Three.") == ["One. Two. Three."]


async def test_same_work_links_across_institutions_by_isbn(client, session):
    await make_institution(session, "a", "Library A", country="Canada")
    await make_institution(session, "b", "Library B", country="United States")
    base = dict(source_system="t", access_type="physical", resource_type="book", date_start=2008, date_end=2008)
    await upsert_record(session, NormalizedRecord(**base, source_record_id="1", title="Razing Africville", creators=["Nelson, Jennifer"], identifiers={"isbn": "9781442691582"}, original_url="https://a/1", institution_slug="a"))
    await upsert_record(session, NormalizedRecord(**base, source_record_id="2", title="Razing Africville : a geography of racism", creators=["Nelson, Jennifer J."], identifiers={"isbn": ["1-4426-9158-1"]}, original_url="https://b/2", institution_slug="b"))
    await session.commit()
    d = (await client.get("/api/search", params={"q": "Africville", "mode": "advanced"})).json()
    by_title = {r["title"]: r for r in d["results"]}
    assert by_title["Razing Africville"]["also_catalogued_at"][0]["institution_name"] == "Library B"
    assert by_title["Razing Africville : a geography of racism"]["also_catalogued_at"][0]["institution_name"] == "Library A"


async def test_long_description_becomes_quotable_description_evidence(session, fake_llm):
    await make_institution(session, "kew", "The National Archives (UK)")
    desc = ("The Book of Negroes: a list of 3,000 self-emancipated Black Loyalist men, women and children who departed New York for Nova Scotia in 1783. " * 5).strip()
    r, _ = await upsert_record(session, NormalizedRecord(source_system="t", source_record_id="bn", title="Carleton papers: Book of Negroes", description=desc, original_url="https://kew/bn", access_type="physical", institution_slug="kew", resource_type="manuscript", date_start=1783, date_end=1784))
    await session.commit()
    kinds = {c.kind for c in (await session.execute(select(RecordChunk).where(RecordChunk.record_id == r.id))).scalars()}
    assert kinds == {"description"}
    assert r.has_full_text is False  # description text is not full text of the item
    pack, cards, follow_up = await guide.build_pack(session, "Who is listed in the Book of Negroes?")
    rendered = pack.render()
    assert "DESCRIPTION — catalogue / finding-aid text" in rendered and "EXCERPT" not in rendered
    chunk_item = next(i for i in pack.items if i["kind"] == "chunk")
    fake_llm.push({"answer": f"The finding aid describes it as \"a list of 3,000 self-emancipated Black Loyalist men, women and children\" [1].", "citations": [{"n": 1, "evidence_id": chunk_item["evidence_id"], "quote": "a list of 3,000 self-emancipated Black Loyalist men, women and children"}], "abstain": False, "abstain_reason": None})
    out = await guide.ask(session, "Who is listed in the Book of Negroes?")
    assert not out["abstain"] and out["citations"][0]["kind"] == "chunk" and out["follow_up"] is False


async def test_follow_up_reuses_previous_keywords_and_records(session, fake_llm):
    await make_institution(session, "kew", "The National Archives (UK)")
    r, _ = await upsert_record(session, NormalizedRecord(source_system="t", source_record_id="bn", title="Carleton papers: Book of Negroes", original_url="https://kew/bn", access_type="physical", institution_slug="kew", resource_type="manuscript", date_start=1783, date_end=1784))
    await session.commit()
    history = [{"question": "What is the Book of Negroes?", "answer": "A list [1].", "record_ids": [str(r.id)]}]
    q, follow_up = guide.retrieval_query("Where is it held?", history)
    assert follow_up and "Book of Negroes" in q
    assert guide.retrieval_query("Where is the Book of Negroes held?", history)[1] is False
    pack, cards, fu = await guide.build_pack(session, "Where is it held?", SearchFilters(), history)
    assert fu and cards and cards[0]["id"] == str(r.id)


async def test_guide_respects_filters(session, fake_llm):
    await make_institution(session, "ca", "Canadian Holder", country="Canada")
    await make_institution(session, "uk", "Overseas Holder", country="United Kingdom")
    await upsert_record(session, NormalizedRecord(source_system="t", source_record_id="1", title="Black Loyalists land grants", original_url="https://ca/1", access_type="physical", institution_slug="ca", resource_type="manuscript"))
    await upsert_record(session, NormalizedRecord(source_system="t", source_record_id="2", title="Black Loyalists embarkation list", original_url="https://uk/2", access_type="physical", institution_slug="uk", resource_type="manuscript"))
    await session.commit()
    pack, cards, _ = await guide.build_pack(session, "Black Loyalists", SearchFilters.from_params({"country": "Canada"}))
    assert [c["title"] for c in cards] == ["Black Loyalists land grants"]


async def test_search_and_guide_are_logged(client, session, fake_llm):
    await make_institution(session, "a", "Library A", country="Canada")
    await upsert_record(session, NormalizedRecord(source_system="t", source_record_id="1", title="Africville church", original_url="https://a/1", access_type="physical", institution_slug="a"))
    await session.commit()
    await client.get("/api/search", params={"q": "Africville", "country": "Canada"})
    await client.get("/api/search", params={"q": "zzqx nothing"})
    fake_llm.push({"answer": "", "citations": [], "abstain": True, "abstain_reason": "no"})
    await client.post("/api/guide/ask", json={"question": "Tell me about Africville", "filters": {"country": "Canada"}, "history": [{"question": "hi", "answer": "x"}]})
    rows = list((await session.execute(select(SearchLog).order_by(SearchLog.created_at))).scalars())
    kinds = [(r.kind, r.result_count) for r in rows]
    assert ("search", 1) in kinds and ("search", 0) in kinds and any(k == "guide" for k, _ in kinds)
    assert any(r.filters == {"countries": ["Canada"]} for r in rows if r.kind == "guide")  # SearchFilters field names
    gaps = (await client.get("/api/status/search-log")).json()
    assert {g["query"] for g in gaps["zero_result_queries"]} == {"zzqx nothing"}
    assert "search" in gaps["latency"]


async def test_reranker_falls_back_to_input_order_on_failure(monkeypatch):
    from app.services import rerank

    class Broken(rerank.Reranker):
        async def rerank(self, query, texts):
            raise RuntimeError("model missing")

    monkeypatch.setenv("RERANKER", "local")
    from app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setattr(rerank, "get_reranker", lambda: Broken())
    try:
        assert await rerank.rerank_items("q", ["a", "b"], lambda x: x) == ["a", "b"]
    finally:
        monkeypatch.delenv("RERANKER", raising=False)
        monkeypatch.setenv("RERANKER", "none")
        get_settings.cache_clear()


def test_records_table_has_entity_columns_after_upsert():
    assert {"people", "places", "communities", "work_keys"} <= set(Record.__table__.columns.keys())
