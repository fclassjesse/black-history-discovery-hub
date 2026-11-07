"""Citation validation: valid answer, foreign evidence id, empty evidence → abstain."""
from __future__ import annotations

from app.adapters.base import ChunkIn, NormalizedRecord
from app.services import guide
from app.services.repository import upsert_record
from tests.conftest import make_institution


async def _seed(session, with_chunk: bool = True):
    inst = await make_institution(session, "lib", "Test Library", latitude=44.0, longitude=-63.0, location_precision="building")
    rec = NormalizedRecord(
        source_system="test", source_record_id="r1", title="Africville: the life and death of a Canadian Black community", creators=["Clairmont, Donald"],
        description="A study of the Africville community in Halifax and its relocation in the 1960s.", subjects=["Africville (Halifax, N.S.)"], date_text="1974", date_start=1974,
        resource_type="book", original_url="https://lccn.loc.gov/75302713", access_type="physical", holding_verification="catalogue_record", institution_slug="lib",
        chunks=[ChunkIn(chunk_index=0, page_number=3, text="The community of Africville will be expropriated and cleared during the period commencing April 1 1964 according to the report.", page_url="https://archive.org/details/x/page/n3")] if with_chunk else [],
    )
    r, _ = await upsert_record(session, rec)
    await session.commit()
    return r


async def test_valid_cited_answer(session, fake_llm):
    r = await _seed(session)
    fake_llm.push({
        "answer": "Africville was a Black community in Halifax that was relocated in the 1960s [1]. A report said it would be expropriated and cleared from April 1 1964 [2].",
        "citations": [{"n": 1, "evidence_id": "E1"}, {"n": 2, "evidence_id": "E2", "quote": "expropriated and cleared during the period commencing April 1 1964"}],
        "abstain": False, "abstain_reason": None,
    })
    out = await guide.ask(session, "what happened to Africville?")
    assert out["abstain"] is False, out
    assert len(out["citations"]) == 2
    assert out["citations"][0]["record_id"] == str(r.id) and out["citations"][0]["url"] == "https://lccn.loc.gov/75302713"
    assert out["citations"][1]["url"] == "https://archive.org/details/x/page/n3" and out["citations"][1]["page_number"] == 3
    assert out["highlight_record_ids"] == [str(r.id)]
    assert out["map_focus_institution_ids"] == [str(r.institution_id)]
    assert len(fake_llm.calls) == 1


async def test_foreign_evidence_id_is_rejected_then_abstains(session, fake_llm):
    await _seed(session)
    bad = {"answer": "Africville was bulldozed in 1965 [1].", "citations": [{"n": 1, "evidence_id": "E99"}], "abstain": False}
    fake_llm.push(bad, bad, bad)  # first attempt and both retries cite a non-existent evidence item
    out = await guide.ask(session, "what happened to Africville?")
    assert out["abstain"] is True
    assert out["citations"] == []
    assert "E99" in (out["validation_error"] or "")
    assert len(fake_llm.calls) == 3 and "rejected by the citation validator" in fake_llm.calls[1]["user"]


def test_sentence_splitter_keeps_abbreviations_and_initials():
    from app.services.guide import split_sentences

    s = split_sentences("A 1963 report by Dr. Albert Rose recommended clearing [1]. Jennifer J. Nelson wrote about it [2]. See p. 12 of the report [1].")
    assert s == ["A 1963 report by Dr. Albert Rose recommended clearing [1].", "Jennifer J. Nelson wrote about it [2].", "See p. 12 of the report [1]."]
    # a year is a sentence end, not an abbreviation; markers after the full stop belong to the preceding sentence
    s2 = split_sentences("Africville was bulldozed by the city in 1965. The catalogue entry describes the relocation programme [1].")
    assert s2 == ["Africville was bulldozed by the city in 1965.", "The catalogue entry describes the relocation programme [1]."]
    s3 = split_sentences("It was cleared in 1965. [1] A 1963 report recommended it. [2]")
    assert s3 == ["It was cleared in 1965[1].", "A 1963 report recommended it[2]."]


async def test_abbreviation_sentence_is_not_rejected(session, fake_llm):
    await _seed(session)
    fake_llm.push({"answer": "A report to Halifax City Council by Dr. Albert Rose said the community would be expropriated and cleared [2].", "citations": [{"n": 2, "evidence_id": "E2"}], "abstain": False})
    out = await guide.ask(session, "Africville")
    assert out["abstain"] is False and len(fake_llm.calls) == 1


async def test_single_quoted_invented_span_rejected(session, fake_llm):
    await _seed(session)
    bad = {"answer": "The report called it 'a thriving and prosperous village' [2].", "citations": [{"n": 2, "evidence_id": "E2"}], "abstain": False}
    fake_llm.push(bad, bad, bad)
    out = await guide.ask(session, "Africville")
    assert out["abstain"] is True and "quoted text" in (out["validation_error"] or "")
    assert out["records"], "records are still shown when the guide abstains"


async def test_uncited_claims_rejected(session, fake_llm):
    await _seed(session)
    fake_llm.push({"answer": "Africville was a community that was destroyed by the city for industrial reasons and nobody was compensated properly.", "citations": [{"n": 1, "evidence_id": "E1"}], "abstain": False},
                  {"answer": "The catalogue describes a study of Africville and its relocation [1].", "citations": [{"n": 1, "evidence_id": "E1"}], "abstain": False})
    out = await guide.ask(session, "Africville")
    assert out["abstain"] is False and len(fake_llm.calls) == 2


async def test_inline_quote_not_in_evidence_rejected(session, fake_llm):
    await _seed(session)
    bad = {"answer": 'The report said "the community was thriving and happy" [2].', "citations": [{"n": 2, "evidence_id": "E2"}], "abstain": False}
    fake_llm.push(bad, bad, bad)
    out = await guide.ask(session, "Africville")
    assert out["abstain"] is True and "quoted text" in (out["validation_error"] or "")


async def test_quote_from_metadata_only_record_rejected(session, fake_llm):
    await _seed(session, with_chunk=False)
    bad = {"answer": "It says 'the people were happy' [1].", "citations": [{"n": 1, "evidence_id": "E1", "quote": "the people were happy"}], "abstain": False}
    fake_llm.push(bad, bad, bad)
    out = await guide.ask(session, "Africville")
    assert out["abstain"] is True and "METADATA-ONLY" in (out["validation_error"] or "")


async def test_empty_evidence_abstains_without_calling_provider(session, fake_llm):
    out = await guide.ask(session, "what did Viola Desmond eat for breakfast?")
    assert out["abstain"] is True and out["citations"] == [] and out["records"] == []
    assert fake_llm.calls == []


async def test_unconfigured_guide_abstains_but_shows_records(session, monkeypatch):
    await _seed(session)
    monkeypatch.setenv("LLM_PROVIDER", "none")
    from app.config import get_settings

    get_settings.cache_clear()
    try:
        out = await guide.ask(session, "Africville")
        assert out["abstain"] is True and "not configured" in out["abstain_reason"] and out["records"]
        assert out["provider"]["configured"] is False
    finally:
        get_settings.cache_clear()
