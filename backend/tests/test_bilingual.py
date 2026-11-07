"""Bilingual search and guide: French stemming, alias expansion both ways, locale-aware guide and labels."""
from __future__ import annotations

from app.adapters.base import NormalizedRecord
from app.services import aliases, guide
from app.services.i18n import localize_access_note
from app.services.normalize import question_to_keywords
from app.services.repository import upsert_record
from tests.conftest import make_institution


async def _rec(session, slug, sid, title, **kw):
    base = dict(source_system="t", source_record_id=sid, title=title, original_url=f"https://x.org/{sid}", access_type="physical", institution_slug=slug, resource_type="book", date_start=2000, date_end=2000)
    base.update(kw)
    r, _ = await upsert_record(session, NormalizedRecord(**base))
    return r


async def test_french_query_matches_french_stem(client, session):
    await make_institution(session, "banq", "Bibliothèque", country="Canada")
    await _rec(session, "banq", "f1", "Histoire des Loyalistes noirs en Nouvelle-Écosse", language=["fr"], description="Les communautés noires fondées après 1783.")
    await _rec(session, "banq", "f2", "Une école nationale", language=["fr"])
    await session.commit()
    # plural ↔ singular (both dictionaries agree, but the French one must be queried for French text)
    for q in ("loyaliste", "loyalistes", "Loyalistes noirs"):
        d = (await client.get("/api/search", params={"q": q, "mode": "advanced"})).json()
        assert "Histoire des Loyalistes noirs en Nouvelle-Écosse" in {x["title"] for x in d["results"]}, q
    # French-only stems: 'nationaux' → 'national' and 'fonder' → 'fond' only happen with the 'french' dictionary
    d = (await client.get("/api/search", params={"q": "nationaux", "mode": "advanced"})).json()
    assert [x["title"] for x in d["results"]] == ["Une école nationale"]
    d = (await client.get("/api/search", params={"q": "fonder", "mode": "natural"})).json()
    assert "Histoire des Loyalistes noirs en Nouvelle-Écosse" in {x["title"] for x in d["results"]}
    # a French question is stripped of its question words before retrieval
    d = (await client.get("/api/search", params={"q": "Qu’est-ce que les Loyalistes noirs ?"})).json()
    assert d["keywords"] == "Loyalistes noirs" and d["total"] >= 1


def test_alias_expansion_both_directions():
    assert "Book of Negroes" in aliases.expand("Livre des Noirs")
    assert "Livre des Noirs" in aliases.expand("Book of Negroes")
    assert "Loyalistes noirs" in aliases.expand("Black Loyalists") and "Black Loyalists" in aliases.expand("loyalistes noirs")
    assert "Néo-Écossais d'origine africaine" in aliases.expand("African Nova Scotian")
    # accents and case do not matter
    assert "African Nova Scotian" in aliases.expand("neo-ecossais d'origine africaine")
    # Advanced mode never expands
    assert aliases.expand("Africville")[0] == "Africville"


def test_french_question_keywords():
    assert question_to_keywords("Qu'est-ce que le Livre des Noirs ?") == "Livre des Noirs"
    assert question_to_keywords("qu'est-ce qu'Africville") == "Africville"
    assert question_to_keywords("Parle-moi des Loyalistes noirs") == "Loyalistes noirs"
    assert question_to_keywords("what happened to Africville?") == "Africville"


def test_guide_prompt_carries_language_rule():
    assert "language of the QUESTION" in guide.SYSTEM_PROMPT and "UI LANGUAGE" in guide.SYSTEM_PROMPT
    assert "never" in guide.SYSTEM_PROMPT and "translate a quote" in guide.SYSTEM_PROMPT


async def test_guide_ask_accepts_locale_and_localizes_messages(client, session, fake_llm):
    # no records → the abstain message comes back in the UI language
    r = await client.post("/api/guide/ask", json={"question": "Qu'est-ce que le Livre des Noirs ?", "locale": "fr"})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["abstain"] is True and d["locale"] == "fr" and d["abstain_reason"].startswith("Aucune notice")
    r = await client.post("/api/guide/ask", json={"question": "What is the Book of Negroes?"})
    assert r.json()["abstain_reason"].startswith("No records")
    r = await client.post("/api/guide/ask", json={"question": "x", "locale": "de"})
    assert r.status_code == 422

    # with evidence, the UI language reaches the model prompt and the fake answer passes validation unchanged
    await make_institution(session, "lib", "Test Library")
    await _rec(session, "lib", "g1", "Le Livre des Noirs", description="Registre des Loyalistes noirs évacués de New York en 1783.")
    await session.commit()
    fake_llm.push({"answer": "Le Livre des Noirs est un registre des Loyalistes noirs évacués de New York en 1783 [1].", "citations": [{"n": 1, "evidence_id": "E1"}], "abstain": False, "abstain_reason": None})
    out = await guide.ask(session, "Qu'est-ce que le Livre des Noirs ?", locale="fr")
    assert out["abstain"] is False and out["citations"][0]["title"] == "Le Livre des Noirs"
    assert "UI LANGUAGE: French (fr-CA)" in fake_llm.calls[-1]["user"] and "language of the QUESTION" in fake_llm.calls[-1]["system"]


async def test_locale_labels_on_search_and_records(client, session):
    await make_institution(session, "loc", "Located Library")
    r = await _rec(session, "loc", "l1", "Carte de la Nouvelle-Écosse", resource_type="map", language=["zxx", "fr"], access_note="Held by the Library of Congress (Washington, DC). Use the catalogue record to request the item in a reading room. A digital version is linked from the record.")
    await session.commit()
    d = (await client.get("/api/search", params={"q": "", "locale": "fr"})).json()
    langs = {f["value"]: f["label"] for f in d["facets"]["language"]}
    assert langs == {"zxx": "Sans contenu linguistique", "fr": "Français"}
    assert d["facets"]["resource_type"][0]["label"] == "Carte"
    card = d["results"][0]
    assert card["resource_type_label"] == "Carte" and card["language_labels"] == ["Sans contenu linguistique", "Français"]
    assert card["access_note"].startswith("Conservé par la Library of Congress") and card["access_note"].endswith("Une version numérique est liée à la notice.")
    d = (await client.get("/api/search", params={"q": ""})).json()
    assert {f["value"]: f["label"] for f in d["facets"]["language"]} == {"zxx": "No linguistic content", "fr": "French"}
    assert (await client.get(f"/api/records/{r.id}", params={"locale": "fr"})).json()["resource_type_label"] == "Carte"
    # partner-written notes are never translated
    assert localize_access_note("Ask at the front desk for box 12.", "fr") == "Ask at the front desk for box 12."


def test_rerank_query_anchors_french_question_with_english_aliases():
    rq = guide.rerank_query("Qu'est-ce que le Livre des Noirs ?", "Qu'est-ce que le Livre des Noirs ?")
    assert rq.startswith("Qu'est-ce que le Livre des Noirs ?") and "Book of Negroes" in rq
    assert guide.rerank_query("what did Viola Desmond eat?", "what did Viola Desmond eat?") == "what did Viola Desmond eat? (Desmond, Viola)"
    assert guide.rerank_query("zzqx", "zzqx") == "zzqx"


def test_pack_caps_near_identical_titles():
    class R:  # minimal stand-in for a Record
        def __init__(self, title, keys):
            self.title, self.work_keys = title, keys

    recs = [R(f'Celebrating Black History Month An Evening Honouring "The Book of Negroes" ({16257177980 + i})', [f"w{i}"]) for i in range(6)] + [R("The book of negroes", ["w9"])]
    kept = guide._collapse_same_work(recs, keep=12)
    assert [r.title[:20] for r in kept] == ["Celebrating Black Hi", "Celebrating Black Hi", "The book of negroes"]
