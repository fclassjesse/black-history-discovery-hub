# Database + RAG optimization plan (2026-11-07)

Goal: make search and the evidence-grounded guide faster, more relevant and closer to the brief ("search by people,
places, communities, subjects, dates, institutions and resource type"; "relationship mapping"; "grounded natural-language
search"). No security work in this plan (owner's call for the demo). Everything stays deterministic and auditable:
no new LLM calls in retrieval; the guide keeps its server-side citation validator.

## Findings (audited 2026-11-07)

| Area | Current state | Problem |
|---|---|---|
| Vector search | `records.embedding` / `record_chunks.embedding` (pgvector, bge-small 384-d) with **no index** | sequential scan on every query; fine at 1.5k rows, wrong at 100k |
| Entities | people/places/communities only exist as words inside `creators`/`subjects` | brief asks for them as search axes; no facets |
| Relationship mapping | `dedupe_key` = title+creator+year → "also catalogued at" | misses the same work across LoC / Harvard / IA when titles differ slightly; ignores ISBN/OCLC/LCCN |
| Guide evidence | 12 records (METADATA-ONLY) + 8 OCR passages (EXCERPT) | rich finding-aid descriptions (TNA, Dalhousie) are never quotable; near-duplicate records waste pack slots; one book can take all 8 passage slots |
| Guide context | one question at a time; ignores on-screen filters | "tell me more" fails; answers ignore "Held in Canada" |
| Guide cost | every question → retrieval + LLM | repeated demo questions pay again |
| Search quality signal | nothing is logged | no way to see zero-result queries (where the gaps are) |
| Freshness | connectors only run from `make seed` | no refresh path except re-seeding everything |

## Changes

### 1. Schema (Alembic `0002_entities_and_vectors`)
- `records.people text[]`, `records.places text[]`, `records.communities text[]`, `records.work_keys text[]` (+ GIN indexes).
- `record_chunks.kind varchar(16) default 'page'` (`page` = OCR/PDF page, `description` = catalogue / finding-aid text).
- HNSW cosine indexes on `records.embedding` and `record_chunks.embedding`.
- `search_log` table: `id, created_at, query, mode, filters jsonb, result_count, took_ms, kind ('search'|'guide')`. No user data.
- Backfill script `scripts/backfill_entities.py`: recompute entities, work keys and description passages for existing rows (no re-fetch).

### 2. Entity extraction (`app/services/entities.py`, deterministic)
- **People**: creators that look like personal names (`Surname, Given…`, optional dates) and LCSH 600-style subjects (`Name, Given, 1827-1904`). Corporate names (contain "Company", "Society", "Department", "University", "Fonds" …) are excluded.
- **Places**: subject parts and description mentions that match a gazetteer: all African Nova Scotian communities from the NS Open Data set *African Nova Scotian Family Names by Region* (fetched 2026-11-07, stored as `fixtures/gazetteer.yaml` with the dataset URL), plus NS counties/towns, Canadian provinces, and the countries/cities that recur in this corpus (Sierra Leone, Freetown, Jamaica, New York, London, Kew…).
- **Communities**: the subset of places that are African Nova Scotian communities (Africville, North Preston, Birchtown, …) plus community organisations named in subjects (e.g. "African United Baptist Association").
- Alias expansion reuses the gazetteer (e.g. "Preston" → "North Preston", "East Preston").

### 3. Relationship mapping (`work_keys`)
- `work_keys` = normalised ISBN-13s, OCLC numbers, LCCNs, plus the existing `dedupe_key`. `linked_map` uses `work_keys && :keys` (GIN) instead of equality on one key. The result card keeps the same `also_catalogued_at` shape, so the UI needs no change.

### 4. Description passages
- At upsert, a record with no page chunks and a description ≥ 400 chars gets `description` chunks (≤ 900 chars each, sentence-aligned, `page_url = original_url`).
- The evidence pack labels them `DESCRIPTION (catalogue text)`: quotable verbatim, but the prompt says it describes the item and is not the item's content. Validator unchanged (quotes must be verbatim substrings).

### 5. Retrieval improvements (`search.py`, `guide.py`)
- Pack diversity: collapse candidates sharing a `work_key` (keep the best-ranked), cap 3 passages per record.
- Guide accepts the active filters (`country`, `institution`, `types`, …) and a short `history` (last 3 turns). Follow-up detection is deterministic: short questions or ones starting with a pronoun/"more"/"where is it" reuse the previous question's keywords and keep the previous answer's cited records in the pack. The previous turn is shown to the model as non-citable context.
- Optional local reranker (`RERANKER=local|none`, default `local`, fastembed cross-encoder `Xenova/ms-marco-MiniLM-L-6-v2`): reorders the top 40 fused candidates for the guide pack and page 1 of natural search. Falls back silently to fused order if the model is unavailable.
- Guide answer cache: in-process LRU keyed by (question, filters, history tail, published-record count), TTL 10 min.
- Embedding text adds places/communities and resource type so the semantic leg "knows" where a record is about.

### 6. Search log + gaps view
- Every `/api/search` and `/api/guide/ask` writes one `search_log` row (fire-and-forget).
- `GET /api/status/search-log` → top queries, zero-result queries, p50/p95 latency (last 7 days). Rendered at the bottom of `/about/sources` as "Search gaps".

### 7. Refresh path
- `scripts/refresh.py [--source X]`: re-runs connectors for the seed queries, re-embeds records whose `embedding_model` differs from the current provider, rebuilds description passages where missing. `make refresh`.

### 8. Frontend
- Filter rail: People, Places, Communities groups (from new facets).
- Guide panel sends current filters + last 3 turns; shows "(follow-up)" tag when history was used.
- Sources page: "Search gaps" block.

## Verification
- `uv run pytest` (new tests: entity extraction, work-key linking, description passages labelled and quotable, follow-up detection reuses previous keywords, search log row written, reranker fallback), `npx tsc --noEmit`, `npm run build`.
- Live: `alembic upgrade head`, backfill, then three guide questions incl. one follow-up and one with "Held in Canada"; `EXPLAIN` shows HNSW index use; search p95 before/after from `search_log`.

## Out of scope (deliberately)
Rate limiting, auth hardening, CSP, French UI, subject thesaurus mapping (next plan), scheduled cron (the refresh script can be cron'd by the owner).

## Status (2026-11-07)

Implemented and tested (63 backend tests, tsc, build): sections 1–8. Notes from execution:
- `ix_records_subjects` (GIN on subjects) was dropped: some subject strings exceed the GIN item size limit; full-text search already covers subjects.
- HNSW indexes are expression + partial per model (`(embedding::vector(384)) … WHERE embedding_model = 'BAAI/bge-small-en-v1.5'`); the query helper `vector_expr()` keeps the SQL identical so the planner uses them.
- Reranker model downloads (~90 MB) on first use; tests run with `RERANKER=none`.
- Reranker budget tuned after measurement (CPU, bge cross-encoder): 40 pairs × 1200 chars = 3.8 s; 20 × 400 chars = 0.4 s. Search now reranks the top 20 fused candidates at 400 chars; the guide reranks 24 records / 24 passages at ≤ 500 chars.
- Live after backfill (1,557 records, 4,245 passages incl. 1,569 description passages): `EXPLAIN` shows `ix_records_embedding_hnsw_local` / `ix_chunks_embedding_hnsw_local` index scans; natural search ≈ 0.32 s steady state (advanced mode ≈ 0.03 s); guide ≈ 5–7 s (LLM-bound), cached repeat 0.00 s; follow-up "Where is it held?" resolved against the previous answer's records; `country=Canada` respected by the guide.
- Entities on live data: people 660 records, places 1,086, communities 208 (e.g. Africville 103, Seaview African United Baptist Church 3, North Preston, East Preston, Cherry Brook, Lucasville…). Place strings that look like names ("Halifax, Nova Scotia") are excluded from people.

## 9. Bilingual interface and search (English / French) — added 2026-11-07, built 2026-11-07

Why: a *national* Black History Knowledge Hub serves Canada's two official languages; Library and Archives Canada, BAnQ,
Europeana and partner uploads carry French records and French subject headings (RVM), and BCCNS's audience includes
Acadian and francophone communities.

Current state (audited): the UI is English only (`<html lang="en">`, ~170 hard-coded strings across ~80 components);
full-text search uses the `'english'` dictionary for both the stored tsvector and the query, so French stemming
("loyalistes" ↔ "loyaliste") does not work; the alias list has one French variant ("Loyalistes noirs"); the guide
answers in English regardless of the question's language; records' `language` facet shows raw codes (`en`, `zxx`).

Scope:
1. **UI locale** (`en`, `fr`): locale in the URL (`/fr/...`) with a visible EN | FR switch; `next-intl` (App Router) or an
   equivalent dictionary approach; every user-facing string in both languages; `lang` attribute, dates and numbers
   localized; the character (Nova) speaks the active language; voice push-to-talk uses `fr-CA` when French is active.
   Partner-portal strings included (institutions use it). Language preference remembered.
2. **Search in both languages**: a second generated column `search_tsv_fr` (`'french'` dictionary) + GIN index,
   alias groups extended with French names (Africville, Loyalistes noirs, Livre des Noirs / Book of Negroes, Chemin de fer
   clandestin, Marrons jamaïcains, Néo-Écossais d'origine africaine…), queries run against both dictionaries and fuse by
   RRF; the embeddings model stays as is (bge-small is weak on French — note the limitation; `bge-m3` as a later option).
3. **Guide**: answers in the language of the question (or the UI locale when ambiguous); the system prompt gains the
   rule; the validator is unchanged (quotes verbatim in either language). Abstain messages and access notes localized.
4. **Data labels**: language facet shows names (English / Anglais, French / Français, "no linguistic content" for `zxx`);
   resource types, access and holding labels translated; institution descriptions stay in the source language with an
   "English only" / "French only" badge.
5. **Docs**: README (how to add a string / a locale), sources.md note on French dictionaries, `.env.example` unchanged.

Verification: `uv run pytest` (new tests: French query matches French stem; alias expansion both ways; guide prompt
carries the language rule), `npx tsc --noEmit`, `npm run build`, Playwright screenshots of `/fr` home, search, a record,
the partner dashboard; a French guide question answered in French with citations.

### Status (2026-11-07, built)

Done, verified locally (`uv run pytest` 71 passed incl. 8 new in `tests/test_bilingual.py`; `npx tsc --noEmit`, `npx eslint`, `npm run build` clean; migration `0003_french_fts` applied to `bhdh`):

1. UI locale `/fr/…` via `frontend/proxy.ts` (rewrite + `x-locale` header + `bhdh_locale` cookie; `/en/…` redirects and remembers English), EN | FR switch in the site header, menu plate and institution-app header; `<html lang>`, `en-CA`/`fr-CA` dates and numbers, `fr-CA` push-to-talk and read-aloud. Strings (774 keys) in `frontend/messages/{en,fr}.json`; every component, page, badge and label reads them. Legacy `components/map/AtlasMap.tsx` (unused since the globe) was translated too.
2. Search: `search_tsv_fr` / `tsv_fr` generated columns + GIN (migration 0003), both dictionaries in natural (RRF) and advanced (single OR query) modes; French question prefixes/stopwords in `question_to_keywords`; aliases.yaml with French names for every group plus four new groups (Nouvelle-Écosse, Halifax, esclavage, histoire des Noirs), accent-insensitive matching. Embedding model unchanged (English-only; bge-m3 noted as upgrade path in `docs/sources.md`).
3. Guide: `locale` in `/api/guide/ask` body, rule 7 in `SYSTEM_PROMPT` (answer in the question's language, fall back to UI language, never translate a quote), `UI LANGUAGE` line in the user prompt, abstain messages translated server-side (`app/services/i18n.py`), cache key includes locale, validator unchanged. Two retrieval fixes found while testing in French: the local cross-encoder is English-only, so `rerank_query()` appends the English alias names to a French question ("Livre des Noirs" → "Book of Negroes") before reranking; and `_collapse_same_work` now also caps near-identical titles at 2 per pack (eleven Commons photos of one evening were filling the 12 record slots and pushing out the TNA and LoC records that actually define the Book of Negroes).
4. Data labels: language facet names (English/Anglais, Français, "Sans contenu linguistique" for `zxx`, tolerant of stray codes like `Eng`), resource type / access / rights / holding-verification labels in both languages (server for facets and cards, client for badges), institution descriptions kept in source language with an *English only / French only* badge when they differ from the UI.
5. Docs: README "Languages" section, sources.md note, this status.

Verified in the browser (Playwright, Chromium): `/fr` home, `/fr?q=Loyalistes+noirs` (180 notices, French badges and labels), a French record page, the BCCNS partner dashboard in French, the institution app in French; no console errors. Guide asked « Qu'est-ce que le Livre des Noirs ? », « Qu'est-il arrivé à Africville ? » and « Qui étaient les Loyalistes noirs ? » in French: cited French answers whose citations resolve to records in the pack (TNA Discovery, LoC, Harvard, Internet Archive, Commons). Before the two retrieval fixes above, the first question abstained in French because the pack held only the Commons photos.

Known limits: the PWA manifest (`app/manifest.ts`) is English only (one manifest per origin); connector `detail` strings on `/about/sources` come from the backend status service in English; vision/transcription provider messages are English; recognised text from `fr-CA` speech was not testable headless.

