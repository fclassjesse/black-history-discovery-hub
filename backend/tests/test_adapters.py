"""Adapter normalization on recorded real responses (fixtures/)."""
from __future__ import annotations

import json
from pathlib import Path

from app.adapters.base import all_adapters, get_adapter
from app.adapters.internet_archive import parse_djvu_pages
from app.adapters.loc_sru import cql_for, parse_sru
from app.adapters import partner_csv
from app.services.normalize import dedupe_key, parse_year_range, question_to_keywords

FIX = Path(__file__).resolve().parent.parent / "fixtures"


def test_loc_sru_normalizes_recorded_marcxml():
    total, records, diag = parse_sru((FIX / "loc_sru_black_loyalists.xml").read_text())
    assert diag is None and total >= 3 and len(records) == 3
    adapter = get_adapter("loc_sru")
    rec = adapter.normalize(records[0])
    assert rec.source_system == "loc_sru"
    assert rec.title == "Birchtown and the Black Loyalists"
    assert rec.creators[0].startswith("Taylor, Wanda Lauren")
    assert rec.identifiers["lccn"] == "2014450157"
    assert rec.original_url == "https://lccn.loc.gov/2014450157"
    assert rec.call_number == "F1039.5.B57 T39 2014"
    assert rec.date_start == 2014 and rec.resource_type == "book" and rec.language == ["en"]
    assert rec.access_type == "physical" and rec.holding_verification == "catalogue_record"
    assert rec.institution_slug == "library-of-congress"
    assert any("Birchtown" in s for s in rec.subjects)
    assert rec.rights_status == "unknown"  # never invented


def test_loc_sru_cql_keeps_phrases_and_exclusions():
    assert cql_for('"Black Loyalists" -Sierra') == '"Black Loyalists" not "Sierra"'
    assert cql_for("Africville relocation") == '"Africville" and "relocation"'


def test_internet_archive_normalizes_recorded_json():
    data = json.loads((FIX / "ia_africville.json").read_text())
    docs = data["response"]["docs"]
    assert docs
    adapter = get_adapter("internet_archive")
    for d in docs:
        rec = adapter.normalize(d)
        assert rec.source_system == "internet_archive"
        assert rec.original_url == f"https://archive.org/details/{d['identifier']}"
        assert rec.access_type == "online"
        assert rec.institution_slug == "internet-archive"
        assert rec.holding_verification == "online_item"  # never presented as a physical holding
        assert rec.rights_status in ("public_domain", "cc", "in_copyright", "unknown")
        if str(d.get("access-restricted-item", "")).lower() == "true":
            assert rec.rights_status == "in_copyright" and "borrow" in rec.access_note.lower()
        if d.get("contributor"):
            assert "Digitized from the collection of" in rec.access_note  # provenance, not a holding


def test_djvu_page_chunking_builds_page_urls():
    xml = "<DjVuXML><BODY>" + "".join(
        f'<OBJECT><HIDDENTEXT><PAGECOLUMN><REGION><PARAGRAPH><LINE>{"".join(f"<WORD>word{i}{j}</WORD>" for j in range(60))}</LINE></PARAGRAPH></REGION></PAGECOLUMN></HIDDENTEXT></OBJECT>'
        for i in range(3)
    ) + "</BODY></DjVuXML>"
    chunks = parse_djvu_pages(xml, "item1")
    assert len(chunks) == 3
    assert chunks[1].page_number == 1 and chunks[1].page_url == "https://archive.org/details/item1/page/n1"


def test_keyed_connectors_report_unconfigured_without_keys(monkeypatch):
    monkeypatch.delenv("DPLA_API_KEY", raising=False)
    monkeypatch.delenv("EUROPEANA_API_KEY", raising=False)
    from app.config import get_settings

    monkeypatch.setenv("DPLA_API_KEY", "   ")  # blank value (as in `DPLA_API_KEY=` in .env) must not count as configured
    monkeypatch.setenv("EUROPEANA_API_KEY", "")
    get_settings.cache_clear()
    assert not get_adapter("dpla").is_configured()
    assert not get_adapter("europeana").is_configured()
    get_settings.cache_clear()


def test_dpla_and_europeana_normalize_documented_shapes():
    dpla = get_adapter("dpla").normalize({
        "id": "abc123", "isShownAt": "https://example.org/item/1", "dataProvider": "Example Library",
        "sourceResource": {"title": ["A title"], "creator": ["Someone"], "date": {"displayDate": "1901"}, "type": ["text"], "subject": [{"name": "Nova Scotia"}], "description": ["desc"]},
    })
    assert dpla.original_url == "https://example.org/item/1" and dpla.date_start == 1901 and dpla.resource_type == "book" and dpla.holding_verification == "online_item"
    eu = get_adapter("europeana").normalize({"id": "/123/abc", "title": ["T"], "guid": "https://www.europeana.eu/item/123/abc", "type": "IMAGE", "rights": ["http://creativecommons.org/publicdomain/mark/1.0/"], "dataProvider": ["Museum"]})
    assert eu.rights_status == "public_domain" and eu.resource_type == "image"


def test_helpers():
    assert parse_year_range("[2014]") == (2014, 2014)
    assert parse_year_range("1990-2005") == (1990, 2005)
    assert parse_year_range("18--") == (1800, 1899)
    assert parse_year_range("192-") == (1920, 1929)
    assert dedupe_key("The Black Loyalists", ["Walker, James W. St. G."], 1976) == dedupe_key("Black loyalists", ["Walker James"], 1976)
    assert question_to_keywords("what happened to Africville?") == "Africville"
    assert question_to_keywords("tell me about the Book of Negroes") == "Book of Negroes"


def test_csv_preview_flags_errors_and_duplicates():
    headers, rows = partner_csv.parse_upload("x.csv", (FIX / "demo_partner_sample.csv").read_bytes())
    mapping = partner_csv.auto_map(headers)
    assert mapping["title"] == "title" and mapping["creators"] == "creators" and mapping["date"] == "date"
    preview = partner_csv.validate_rows(rows, mapping, set(), "demo")
    assert sum(1 for p in preview if p["errors"]) == 1
    assert any("title is required" in e for p in preview for e in p["errors"])
    assert sum(1 for p in preview if p["duplicate_of"]) >= 1
    dups = [p for p in preview if p["duplicate_of"]]
    assert dups[0]["duplicate_of"].startswith("row ")


def test_csv_header_synonyms_and_existing_duplicates():
    headers, rows = partner_csv.parse_upload("y.csv", b"Item Title,Author,Year,Record URL\nA book,Jane Doe,1990,notaurl\nA book,Jane Doe,1990,https://x.org/1\n")
    mapping = partner_csv.auto_map(headers)
    assert mapping["title"] == "Item Title" and mapping["creators"] == "Author" and mapping["date"] == "Year" and mapping["original_url"] == "Record URL"
    preview = partner_csv.validate_rows(rows, mapping, {dedupe_key("A book", ["Jane Doe"], 1990)}, "x")
    assert preview[0]["errors"] == ["original_url must start with http:// or https://"]
    assert preview[0]["duplicate_of"] == "existing record in this institution"
    assert preview[1]["duplicate_of"] == "row 1"


# --- Dalhousie University Archives (OAI-PMH, whole-feed harvest filtered locally) ---------------

def test_dal_oai_parses_recorded_page_and_resumption_token():
    from app.adapters.dal_oai import parse_oai_page

    records, token, err = parse_oai_page((FIX / "dal_oai_listrecords.xml").read_text())
    assert err is None and len(records) == 3
    assert token and token.startswith("eyJ")  # AtoM cursor token → next page
    assert records[0]["oai_identifier"] == "oai:findingaids.library.dal.ca:nshd_16"
    assert records[0]["dc"]["language"] == ["eng"]


def test_dal_oai_normalizes_recorded_description():
    from app.adapters.dal_oai import parse_oai_page

    records, _, _ = parse_oai_page((FIX / "dal_oai_listrecords.xml").read_text())
    rec = get_adapter("dal_oai").normalize(records[0])
    assert rec.source_system == "dal_oai" and rec.source_record_id == "oai:findingaids.library.dal.ca:nshd_16"
    assert rec.title.startswith("A description of the Bay of Fundy")
    assert rec.creators == ["Janigan, David"]
    assert rec.original_url.startswith("https://findingaids.library.dal.ca/a-description-of-the-bay-of-fundy")
    assert "//a-description" not in rec.original_url  # feed's doubled slash normalised
    assert rec.call_number == "2011-006, Oversized Folder 3" and rec.identifiers["reference_code"] == rec.call_number
    assert rec.date_text == "[ca.1729]" and rec.date_start == 1729
    assert rec.resource_type == "map" and rec.language == ["en"]
    assert rec.access_type == "physical" and rec.holding_verification == "catalogue_record"
    assert rec.institution_slug == "dalhousie-university-archives"
    assert rec.rights_status == "unknown" and rec.digital_url is None  # never invented


def test_dal_oai_parses_recorded_listsets_page():
    from app.adapters.dal_oai import parse_sets_page

    sets, token, err = parse_sets_page((FIX / "dal_oai_listsets.xml").read_text())
    assert err is None and len(sets) == 4 and token
    assert sets[0] == ("oai:findingaids.library.dal.ca:nshd_2", "David and Marilyn Janigan Map Collection")


def test_dal_oai_child_record_carries_its_fonds():
    from app.adapters.dal_oai import parse_oai_page

    records, _, _ = parse_oai_page((FIX / "dal_oai_listrecords.xml").read_text())
    child = dict(records[1], set_name="David and Marilyn Janigan Map Collection", set_spec="oai:findingaids.library.dal.ca:nshd_2", is_fonds=False)
    rec = get_adapter("dal_oai").normalize(child)
    assert rec.description.startswith("Part of: David and Marilyn Janigan Map Collection.")
    assert "David and Marilyn Janigan Map Collection" in rec.subjects and rec.identifiers["fonds"]


def test_dal_oai_local_filter_requires_whole_words():
    from app.adapters.dal_oai import matches, parse_oai_page

    records, _, _ = parse_oai_page((FIX / "dal_oai_listrecords.xml").read_text())
    blackmore = records[0]
    assert not matches(blackmore, "Black Nova Scotians")  # "Blackmore" is not "Black"
    assert matches(records[1], "Halifax map")
    assert not matches(records[1], "Halifax Africville")  # every significant word must appear
    assert matches({"dc": {"title": ["Africville Genealogy Society fonds"], "description": ["Relocation of Africville residents, 1964-1970."]}}, "Africville relocation")
    assert matches({"dc": {"title": ["Black Loyalist settlement papers"]}}, "Black Loyalists")  # plural-tolerant


def test_dal_oai_treats_atom_challenge_page_as_blocked():
    import pytest

    from app.adapters.dal_oai import ChallengeError, parse_oai_page

    challenge = "<!DOCTYPE html><html><body><script>localStorage.setItem('atom_challenge_redirect_url', '/;oai');window.location.href='/challenge';</script></body></html>"
    with pytest.raises(ChallengeError):
        parse_oai_page(challenge)


def test_dal_oai_is_registered_and_keyless():
    names = {a.name for a in all_adapters()}
    assert "dal_oai" in names
    assert get_adapter("dal_oai").requires_key is False and get_adapter("dal_oai").is_configured()


# --- Keyless sources added 2026-11-07 (recorded real responses in fixtures/) ----------------------

def test_tna_discovery_normalizes_recorded_book_of_negroes_record():
    data = json.loads((FIX / "tna_black_loyalists.json").read_text())
    rec = get_adapter("tna_discovery").normalize(data["records"][0])
    assert rec.source_system == "tna_discovery" and rec.source_record_id == "C3070438"
    assert "Book of Negroes" in rec.title and rec.call_number == "PRO 30/55/100"
    assert rec.original_url == "https://discovery.nationalarchives.gov.uk/details/r/C3070438"
    assert rec.date_start == 1783 and rec.date_end == 1784
    assert rec.access_type == "physical" and rec.holding_verification == "catalogue_record"
    assert rec.institution_slug == "uk-national-archives" and rec.identifiers["held_by"] == ["The National Archives, Kew"]
    assert rec.rights_status == "unknown"


def test_wikimedia_commons_normalizes_recorded_file_with_licence():
    from app.adapters.wikimedia_commons import rights_status_for

    pages = json.loads((FIX / "commons_africville.json").read_text())["query"]["pages"]
    rec = get_adapter("wikimedia_commons").normalize(pages[0])
    assert rec.title == "Africville and bridge" and rec.resource_type == "image"
    assert rec.original_url == "https://commons.wikimedia.org/wiki/File:Africville_and_bridge.jpg"
    assert rec.access_type == "online" and rec.holding_verification == "online_item"  # never a physical holding
    assert rec.rights_status == "cc" and "CC BY-SA 3.0" in rec.rights and rec.thumbnail_url
    assert rec.date_start == 2009 and rec.institution_slug == "wikimedia-commons"
    assert rights_status_for("pd-old-100", "True") == "public_domain" and rights_status_for(None, None) == "unknown"


def test_wikimedia_commons_search_filter_keeps_results_on_topic():
    from app.adapters.wikimedia_commons import is_on_topic

    pages = json.loads((FIX / "commons_africville.json").read_text())["query"]["pages"]
    assert all(is_on_topic(p, "Africville") for p in pages)
    reception = {"title": "File:2024 Black History Month Reception at Embassy of the United States in Ottawa.jpg", "imageinfo": [{"extmetadata": {"ImageDescription": {"value": "Reception, Ottawa, 2024"}, "Categories": {"value": "Black History Month|Ottawa"}}}]}
    assert not is_on_topic(reception, "Black Canadians history")  # mentions Black History Month, not Black Canadians
    assert not is_on_topic(pages[0], "Viola Desmond")


def test_harvard_librarycloud_normalizes_recorded_mods():
    mods = json.loads((FIX / "harvard_africville.json").read_text())["items"]["mods"]
    recs = [get_adapter("harvard_librarycloud").normalize(m) for m in mods]
    physical = next(r for r in recs if r.call_number == "F1039.5.H17 C37 2021")
    assert physical.title.startswith("love letter to Africville") and physical.creators == ["Carvery-Taylor, Amanda"]
    assert physical.access_type == "physical" and physical.holding_verification == "catalogue_record"
    assert "Widener Library" in physical.access_note and physical.institution_slug == "harvard-library"
    assert physical.original_url.startswith("https://hollis.harvard.edu/permalink/") and physical.language == ["en"]
    assert any("Black people" in s for s in physical.subjects) and physical.date_start == 2021
    ebook = next(r for r in recs if r.title.startswith("Razing Africville"))
    assert ebook.access_type == "online" and "credentials" in ebook.access_note


def test_ns_open_data_normalizes_recorded_dataset():
    results = json.loads((FIX / "ns_open_data_ans.json").read_text())["results"]
    rec = get_adapter("ns_open_data").normalize(results[0])
    assert rec.title == "African Nova Scotian Family Names by Region" and rec.resource_type == "dataset"
    assert rec.original_url == "https://data.novascotia.ca/d/kbzq-tfz7"
    assert rec.rights == "Nova Scotia Open Government Licence" and rec.rights_status == "open_licence"
    assert rec.access_type == "online" and rec.holding_verification == "online_item"
    assert "Columns:" in rec.description and rec.institution_slug == "nova-scotia-open-data"
    from app.adapters.ns_open_data import NsOpenDataAdapter

    assert NsOpenDataAdapter._params("x", 5)["domains"] == "data.novascotia.ca"  # federated API pinned to NS
    from app.adapters.ns_open_data import is_on_topic

    assert is_on_topic(results[0])
    assert not is_on_topic({"resource": {"name": "Licensed Payday Lenders in Nova Scotia", "description": "List of licensed payday lenders."}, "classification": {}})


def test_ckan_open_canada_normalizes_recorded_package_and_filters_off_topic():
    raw = json.loads((FIX / "ckan_open_canada_black_youth.json").read_text())["result"]["results"][0]
    ad = get_adapter("ckan_open_canada")
    rec = ad.normalize(raw)
    assert rec.title.startswith("Black Youth and the Criminal Justice System")
    assert rec.creators == ["Department of Justice Canada"]  # bilingual "EN | FR" org title → English part
    assert rec.original_url == f"https://open.canada.ca/data/en/dataset/{raw['name']}"
    assert rec.access_type == "online" and rec.holding_verification == "online_item"
    assert rec.rights_status == "open_licence" and "Black youth" in rec.subjects
    assert rec.institution_slug == "open-government-canada"
    assert ad.keep(raw, "Black youth") and not ad.keep(raw, "ocean chemistry")
    coral = {**raw, "title": "Black Coral Fields in the Scotian Shelf", "title_translated": {"en": "Black Coral Fields in the Scotian Shelf"}, "keywords": {"en": ["coral"]}, "tags": []}
    assert not ad.keep(coral, "Black Nova Scotians")  # word match alone is not enough
    assert not ad.keep({**raw, "organization": {"title": "Government of Nova Scotia | Gouvernement de la Nouvelle-Écosse"}}, "Black youth")


def test_smithsonian_and_nypl_report_unconfigured_without_keys(monkeypatch):
    monkeypatch.setenv("SMITHSONIAN_API_KEY", "")
    monkeypatch.setenv("NYPL_API_TOKEN", " ")
    from app.config import get_settings

    get_settings.cache_clear()
    assert not get_adapter("smithsonian").is_configured() and not get_adapter("nypl_digital").is_configured()
    get_settings.cache_clear()


def test_smithsonian_and_nypl_normalize_documented_shapes():
    si = get_adapter("smithsonian").normalize({
        "id": "edanmdm-nmaahc_2011.57.10", "unitCode": "NMAAHC", "title": "Photograph of a church",
        "content": {"descriptiveNonRepeating": {"record_ID": "nmaahc_2011.57.10", "record_link": "https://collections.si.edu/search/detail/edanmdm:nmaahc_2011.57.10", "title": {"content": "Photograph of a church"},
                                                "online_media": {"media": [{"thumbnail": "https://ids.si.edu/ids/deliveryService?id=x&max=150", "content": "https://ids.si.edu/ids/deliveryService?id=x"}]}, "metadata_usage": {"access": "CC0"}},
                    "freetext": {"name": [{"label": "Photograph by", "content": "Unknown"}], "date": [{"label": "Date", "content": "1920s"}], "notes": [{"label": "Description", "content": "A church."}], "objectRights": [{"label": "Rights", "content": "Public domain"}]},
                    "indexedStructured": {"object_type": ["Photographs"], "topic": ["Religion"], "date": ["1920s"]}},
    })
    assert si.institution_slug == "smithsonian-institution" and "African American History" in si.access_note
    assert si.resource_type == "image" and si.access_type == "both" and si.date_start == 1920 and si.holding_verification == "catalogue_record"
    ny = get_adapter("nypl_digital").normalize({"uuid": "abc-123", "title": "Portrait", "itemLink": "https://digitalcollections.nypl.org/items/abc-123", "dateIssued": "1890", "typeOfResource": "still image", "imageID": "12345", "publicDomain": "true"})
    assert ny.original_url == "https://digitalcollections.nypl.org/items/abc-123" and ny.rights_status == "public_domain"
    assert ny.resource_type == "image" and ny.thumbnail_url and ny.institution_slug == "new-york-public-library"


def test_registry_has_all_twelve_connectors():
    assert {a.name for a in all_adapters()} == {
        "loc_sru", "loc_json", "internet_archive", "dpla", "europeana", "dal_oai",
        "tna_discovery", "wikimedia_commons", "harvard_librarycloud", "ns_open_data", "smithsonian", "nypl_digital",
        "ckan_open_canada",
    }
