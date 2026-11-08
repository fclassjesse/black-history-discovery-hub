# Sources, connector status and terms

Live status is on `/about/sources` (and `GET /api/status/sources`). This file explains what each connector does, what it needs, and what it never does.

| Connector | Needs | Status on the build machine (2026-11-06) | What we index | Original-source URL |
|---|---|---|---|---|
| **Library of Congress catalogue — SRU/MARCXML** (`loc_sru`) | nothing | **ok** (primary LoC source) | catalogue records: title, creators, subjects, dates, publisher/extent, call number (MARC 050), ISBN/LCCN/OCLC, 856 digital links | `https://lccn.loc.gov/{lccn}` |
| **Library of Congress JSON API** (`loc_json`) | nothing (20 req/min) | **blocked** — `www.loc.gov/...?fo=json` answers scripts with a Cloudflare browser challenge from this network. Not circumvented. Normaliser built from the documented response shape. | digital collection items (when reachable) | item URL on loc.gov |
| **Dalhousie University Archives finding aids — OAI-PMH/Dublin Core** (`dal_oai`) | nothing | **ok** (added 2026-11-07) | archival descriptions: title, creators, dates, extent, reference code, scope note. OAI-PMH has no search and the feed holds >200,000 descriptions, so the connector reads the ~630 fonds-level descriptions (`ListSets` + `GetRecord`, 1 req/s, cached 7 days), keeps the fonds whose description contains every significant query word (whole words, plural-tolerant), then reads those fonds in full (`ListRecords&set=`, ≤3 pages each). Items are labelled "Part of: <fonds>". **Limitation:** relevant items inside a fonds whose own description never mentions the topic are not reached. | the finding-aid page in `dc:identifier` |
| **Internet Archive** (`internet_archive`) | nothing | **ok** (items labelled *online item*, never a physical holding) | item metadata; for open items with a public-domain/CC signal or published before 1930, page-level OCR text (`{id}_djvu.xml`, ≤120 pages/item, ≤12 items per seed) for page-cited answers | `https://archive.org/details/{id}` (page links `/page/n{N}`) |
| **The National Archives (UK) — Discovery API** (`tna_discovery`) | nothing | **ok** (added 2026-11-07) | Kew holdings only (`sps.heldByCode=TNA`): reference, title, description, context, covering dates, closure status. Colonial Office / Carleton papers: Book of Negroes, Black Loyalists, Sierra Leone settlers, Maroons | `https://discovery.nationalarchives.gov.uk/details/r/{id}` |
| **Wikimedia Commons** (`wikimedia_commons`) | nothing | **ok** (added 2026-11-07) | media files (file namespace) with structured licence metadata (`extmetadata`); labelled *online item*, licence taken only from the file's own metadata | the file's Commons page |
| **Harvard Library — LibraryCloud** (`harvard_librarycloud`) | nothing | **ok** (added 2026-11-07) | MODS catalogue records: title, creators, LCSH subjects, dates, publisher, call number, holding repository (e.g. Widener); e-resources flagged as online/licensed | HOLLIS permalink |
| **Nova Scotia Open Data** (`ns_open_data`) | nothing | **ok** (added 2026-11-07) | Socrata dataset catalogue (e.g. *African Nova Scotian Family Names by Region*); labelled *online item*, rights = Nova Scotia Open Government Licence | dataset permalink |
| **Smithsonian Open Access** (`smithsonian`) | `SMITHSONIAN_API_KEY` (free api.data.gov key, instant) | **unconfigured** | EDAN records incl. NMAAHC: title, names, dates, notes, topics, object rights, online media; unit named on the record holds the object | `record_link` on collections.si.edu |
| **NYPL Digital Collections** (`nypl_digital`) | `NYPL_API_TOKEN` (free, instant) | **unconfigured** | digitised items incl. the Schomburg Center: title, dates, type, public-domain flag, image id | `itemLink` on digitalcollections.nypl.org |
| **DPLA** (`dpla`) | `DPLA_API_KEY` | **ok** once the key is set (owner added it 2026-11-07) | aggregated digital metadata with `isShownAt` links | provider's `isShownAt` |
| **Europeana** (`europeana`) | `EUROPEANA_API_KEY` | **ok** once the key is set (owner added it 2026-11-07) | aggregated European metadata | item `guid` |
| **Curated sample** (`curated_sample`) | nothing — `make curated` | ok (added 2026-11-08) | 14 records copied by hand from public record pages on NovaMuse (4), the Nova Scotia Archives exhibit *African Nova Scotians in the Age of Slavery and Abolition* (6) and the Hamilton Black History Database (4), with the field list the BCCNS CEO asked for. Holder = the institution that holds the original; the site where we found it is kept in provenance as `found_via`. Library and Archives Canada: 0 — every LAC address answered 403 or timed out. Source file: `backend/fixtures/curated_sample.csv` (copy in `docs/curated-sample.csv`). | the record's own page |
| **Partner uploads** (`partner:*`, `partner_shelf_scan:*`) | partner login | ok | CSV/JSON rows, manual entries, PDF finding aids (page chunks), confirmed shelf-scan items | the partner's own catalogue URL |
| **Open Library** | nothing | ok (matching only) | *not indexed* — used to propose bibliographic candidates for shelf scans and to build the demo partner CSV | `https://openlibrary.org{key}` |
| **Nominatim** | nothing | ok | *not indexed* — geocodes institution addresses once; precision label stored with the coordinates | — |

## Rules we follow

- Honest User-Agent (`BlackHistoryDiscoveryHub/0.1 (hackathon prototype)`), ≤1 request/second per source, retry with back-off on 5xx/429, on-disk cache (7 days) so demos don't hammer sources.
- A connector that is blocked or lacks a key reports exactly that; the seed never fabricates records, counts, dates, links or availability.
- Internet Archive `contributor` (the library that supplied a scan) is shown as *provenance* ("digitized from the collection of …"), never as a verified current physical holding. Lending-library items are linked, not copied.
- Rights are only ever taken from explicit signals (`licenseurl`, `possible-copyright-status`, rights text). Otherwise `rights_status = unknown` and the UI says so.
- Catalogue records from LoC are labelled **catalogue record** (LC's catalogue says LC holds it). Only a partner owner can mark a location **partner-verified**. A `verified_partner` holding requires an explicit human confirmation ("our institution physically holds this") — in the shelf-camera flow or on manual entry/edit — and the confirmation is written to the audit trail.
- Link-only institutions (Nova Scotia Archives, MemoryNS, Library and Archives Canada, Halifax Public Libraries, Africville Museum, Black Loyalist Heritage Centre, Canadian Museum for Human Rights) are directory entries that point to their own catalogues. **No scraping** (Halifax's BiblioCommons terms forbid it); ingestion waits for partner exports or permission.
- Checked 2026-11-07 for Canadian feeds: MemoryNS and Nova Scotia Archives (AtoM) answer automated clients with a JavaScript challenge page and their REST API needs an archive-issued key; LAC Collection Search returns a security-check page; Halifax Public Libraries (BiblioCommons) and NovaMuse (CollectiveAccess) have no keyless API; Novanet (the SMU/Dalhousie/MSVU shared Primo catalogue) has an official search API that needs a free institutional key — ask the library. None of these are circumvented.

## Search API additions (2026-11-07)

- `GET /api/search?country=Canada` (comma-separated) keeps only records whose holding institution is in that country; the response's `facets.country` lists counts per country. The UI exposes it as the *Held in* filter.
- `people=`, `places=`, `communities=` filters and facets (deterministic entity extraction; see README) and `facets.country`.
- Wikimedia Commons and Dalhousie OAI-PMH results pass a whole-word, plural-tolerant on-topic check (`app/services/textmatch.py`) before they are stored.

## Languages and search (2026-11-07)

- Full-text search runs two PostgreSQL dictionaries: `'english'` (`records.search_tsv`, `record_chunks.tsv`) and `'french'` (`records.search_tsv_fr`, `record_chunks.tsv_fr`, migration `0003_french_fts`). A French query is stemmed the French way ("fondée" ↔ "fonder", "nationale" ↔ "nationaux") and an English one the English way; natural mode fuses both rankings by RRF, Advanced mode ORs them in one deterministic query.
- **The embedding model is weak on French.** `BAAI/bge-small-en-v1.5` is English-only, so the semantic leg of natural search and of the guide's passage retrieval contributes little for French queries; French recall comes from the French dictionary and from `fixtures/aliases.yaml`, which carries French names for every alias group. The upgrade path is a multilingual model such as `BAAI/bge-m3` (`EMBEDDINGS_PROVIDER=local` with a new model id, then `uv run python scripts/reindex.py`); it was deliberately **not** changed in this pass because it would re-embed every record and passage.
- API responses take `?locale=en|fr` (search, records, institution records) and `locale` in the guide body: generated labels, summaries, connector access notes and abstain messages come back in that language. Source data is never translated.

## Attribution

- Map tiles: © [OpenFreeMap](https://openfreemap.org) · © [OpenMapTiles](https://www.openmaptiles.org/) · © [OpenStreetMap contributors](https://www.openstreetmap.org/copyright)
- Geocoding: [Nominatim](https://nominatim.org/) (OpenStreetMap data, ODbL)
- Catalogue data: Library of Congress (public domain in the US), Internet Archive item metadata, Open Library (CC0 bibliographic data), Dalhousie University Archives finding aids, The National Archives (UK) catalogue descriptions (Open Government Licence), Harvard LibraryCloud (CC0 metadata), Wikimedia Commons (per-file licence), Nova Scotia Open Government Licence datasets, DPLA and Europeana metadata (CC0)

## Getting the missing keys

- **DPLA**: `curl -X POST https://api.dp.la/v2/api_key/you@example.org` — the key is emailed to you. Put it in `.env` as `DPLA_API_KEY`.
- **Europeana**: register at <https://www.europeana.eu/en/how-to-register-for-and-manage-an-api-key>, then set `EUROPEANA_API_KEY`.
- **OpenAI** (PRD default models): <https://platform.openai.com/api-keys> → `OPENAI_API_KEY`; set `LLM_PROVIDER=openai` (or leave `auto`).
- **LoC JSON API**: no key; try from another network. The seed will pick it up automatically once `/api/status/sources` reports `ok`.
