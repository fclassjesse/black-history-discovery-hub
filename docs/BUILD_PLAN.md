# Build Plan — Black History Discovery Platform (RBC HubHacks · BCCNS)

Written 2026-11-06 after research in plan mode. Spec: `PRD.md` (identical to `Black_History_Discovery_PRD_Claude_Code.md`). Sketches: `reference-hero.jpg`, `reference-results.jpg`, `reference-data-flow.png`. Background: `Problem statement 1.pdf`, `Black Cultural Centre – Challenge Kickoff Notes.pdf`, `Meeting notes.docx` (mentor summary: build 1–2 fully working features, prototype by Sunday, present Monday).

## 1. Context

The Black Cultural Centre for Nova Scotia (8 staff) wants a trusted discovery layer that points people to Black history resources held by museums, archives, libraries and communities, without claiming to own them. The project folder has no code yet: green-field build.

Non-negotiables from the PRD: real data only; every AI assertion cited to a clickable original-source URL; abstain when evidence is thin; connectors visibly report "unconfigured/blocked" instead of faking success; physical vs online access kept distinct; human confirmation before any shelf-scan holding is published; tenant isolation enforced server-side; WCAG 2.2 AA; "Contemporary Archival Atlas" look, not an AI SaaS dashboard.

## 2. Environment findings (verified 2026-11-06 from this machine)

| Item | Status |
|---|---|
| LoC JSON API (`www.loc.gov/...?fo=json`) | **403 Cloudflare browser challenge** for any non-browser client from this network, even with an honest User-Agent. Do **not** circumvent (no browser UA spoofing, no headless tricks). Build the connector against the documented shape + a fixture; live status reports `blocked`. |
| LoC SRU catalogue `http://lx2.loc.gov:210/LCDB?version=1.1&operation=searchRetrieve&query=...&recordSchema=marcxml` | **Works, keyless.** Returns MARCXML with 001 control no., 010 LCCN, 020 ISBN, 050 LC call number, 100/110/700 creators, 245 title, 260/264 publisher+date, 300 extent, 500/520 notes, 6xx subjects (English + French), 856 online URLs. Original URL = `https://lccn.loc.gov/{lccn}`. **Primary real LoC source.** |
| Internet Archive `advancedsearch.php` + `/metadata/{id}` | **Works, keyless.** `access-restricted-item: true` = lending-library item (borrow with account); open items expose `{id}_djvu.txt` and `{id}_djvu.xml` (per-page) under `/download/{id}/` (follow redirects to `dnNNN.ca.archive.org`). Rights signals: `licenseurl`, `possible-copyright-status`, `date`. ~270 relevant hits for NS Black-history queries, ~25 open texts. |
| DPLA `/v2/items` | Needs `DPLA_API_KEY` (403 without). Free key: `curl -X POST https://api.dp.la/v2/api_key/<email>`. |
| Europeana | Needs `EUROPEANA_API_KEY` (401 without). |
| Open Library `search.json`, `/isbn/{isbn}.json` | **Works, keyless.** Use ≤1 req/s + cache. |
| Nominatim (`nominatim.openstreetmap.org/search`) | **Works** with an identifying User-Agent, 1 req/s. POIs found: Nova Scotia Archives (44.6376, -63.5860), Africville Museum (44.6739, -63.6195), Library and Archives Canada (45.4198, -75.7082), Halifax Central Library (44.6429, -63.5753), NS Museum of Natural History (44.6456, -63.5848), Library of Congress (38.8887, -77.0046), Canadian Museum for Human Rights (49.8906, -97.1311). **No POI** for BCCNS (only road-level "Cherry Brook Road" 44.7069, -63.4746) or Black Loyalist Heritage Centre / Birchtown address → label approximate. |
| OpenFreeMap vector tiles `https://tiles.openfreemap.org/styles/{positron|liberty|bright}` | **Works, keyless.** Attribution required (OpenFreeMap · OpenMapTiles · OpenStreetMap contributors). Use `positron` (muted). |
| AI keys | `ANTHROPIC_API_KEY` set in the shell env. **No `OPENAI_API_KEY`.** |
| Runtime | Node 24.13 / npm 11.8 (no pnpm). Python 3.14 system; uv 0.10 with 3.13 installed, 3.12 installable (`uv python install 3.12`). **No Docker, no psql.** Homebrew present; `postgresql@17`, `pgvector`, `postgis` bottled but not installed. Supabase CLI logged in; only project is the unrelated "RenoCopilot MVP". |
| Latest versions seen | next 16.4.5, react 19.3.1, maplibre-gl 6.16.0, tailwindcss 4.3.5, typescript 7.0.2, zustand 5.1.0, papaparse 5.7.0 · fastapi 0.162, uvicorn 0.54, sqlalchemy 2.1.8, asyncpg 0.32, pgvector 0.5.1, alembic 1.20, httpx 0.28, openai 3.46, anthropic 2.6, pydantic 2.14, pydantic-settings 2.16, pyjwt 2.15, argon2-cffi 25.1, python-multipart 0.0.33, pypdf 7.0, fastembed 0.9.1, pgserver 0.1.4 (cp39–cp312 wheels, PG 16.2 + pgvector), pytest 9.2, pytest-asyncio 1.4, tenacity 9.2. |

## 3. Decisions (owner-confirmed 2026-11-06)

1. **Database: embedded Postgres via `pgserver`** (pip package; PG 16 + pgvector; Python 3.12 venv; data dir `backend/.pgdata`). App only reads `DATABASE_URL`, so hosted Supabase or Homebrew Postgres drop in later. **PostGIS not required by the schema**: institutions store `latitude/longitude` + a precision label; bbox queries are plain SQL. `docker-compose.yml` (pgvector image) included for Docker users but untestable here.
2. **Auth: FastAPI-native** (argon2 hashes, JWT in httpOnly cookie, `memberships` with owner/editor/reviewer). Supabase Auth/RLS needs a hosted project; server-side tenant enforcement is what the PRD tests. Next.js rewrites `/api/*` → FastAPI so cookies are same-origin.
3. **LLM provider switch** `LLM_PROVIDER=openai|anthropic`. OpenAI Responses API with `gpt-6.1-terra` (env-overridable) is the PRD default; **Anthropic (`claude-sonnet-5-5`, vision-capable) is used now** with the key already present. One interface for guide answers and shelf vision. No key → guide returns `abstained: true, reason: "AI guide not configured"` and still shows retrieved records; shelf scan returns a visible "vision unconfigured" error.
4. **Embeddings** `EMBEDDINGS_PROVIDER=openai|local`; `local` = fastembed `BAAI/bge-small-en-v1.5` (384-d, ONNX, no key). Column is untyped `vector` + `embedding_model`; vector search filters on the active model; `scripts/reindex.py` recomputes after a switch. Exact kNN is fine at MVP scale.
5. **Voice:** push-to-talk only. Browser Web Speech API (no key), transcript shown and editable before submit; optional `/api/voice/transcribe` when `OPENAI_API_KEY` exists; optional browser `speechSynthesis` read-aloud, off by default. Same `/api/guide/ask` path.
6. **Demo tenants:** BCCNS seeded as a real institution with partner logins and **zero pre-seeded holdings** (we cannot verify what they hold). A separate institution literally named "Demo Partner (sample data)" carries the sample CSV import (`holding_verification=demo`, dashed marker, `location_precision=demo`). LoC records get `catalogue_record` verification (LC's own catalogue says LC holds it) with real call numbers and the geocoded LoC pin. Nova Scotia Archives, MemoryNS, LAC, Halifax Public Libraries, Dalhousie, Africville Museum, Black Loyalist Heritage Centre are **link-only** directory entries (no scraping).
7. **Jobs:** `jobs` table + `python -m app.worker` polling loop; `JOBS_INLINE=true` runs jobs in-process (dev/tests). No Redis.
8. **Fonts:** Fraunces (serif headlines) + IBM Plex Sans (UI) via `next/font`; tabular numerals for identifiers. Two families only.

## 4. What the sketches add to the PRD text

- **Hero:** one large framed panel on paper. Guide character is a big bust/silhouette center-left (~2/3 of panel height). "advance search" is a small underlined link at the top-right corner. Mic button immediately left of a wide text input, both in the **bottom-right quadrant**. Lots of empty space.
- **Results:** left filter rail (heading, grouped rules, checkbox row, bulleted options). The rest is the **map as the main stage** (coastline, pins); each pin has a **preview card anchored above it on a stem**. "online resources:" list docked **bottom-right over the map** with URL lines and a "summary" block. No separate list drawn → the full accessible results list goes **below the map** (screen readers; records with unknown location).
- **Data flow:** 1 Museums/Archives/Libraries/Communities + 7 Partner Updates & Review → 2 Data Collection (API, CSV, Portal, Finding Aids) → 3 Unified Metadata & Knowledge DB → 4 Hybrid Search + Evidence-Grounded RAG → 5 AI Virtual Guide (Voice & Text) → 6 "Where is the resource?" → Online: Open Original Source / Physical: Visit or Request Access.

## 5. Monorepo layout

```
RBC Hackthon/
├── README.md                      setup, keys, run, seed, demo script, limitations
├── .env.example                   every variable, commented
├── docker-compose.yml             optional pgvector Postgres for Docker users
├── Makefile                       make db / migrate / seed / api / worker / web / test
├── docs/
│   ├── BUILD_PLAN.md              this file
│   ├── HANDOFF_PROMPT.md          prompt for the executing session
│   ├── partner-import-template.csv
│   ├── partner-api.md             import/API contract for integrators
│   └── sources.md                 connector status, terms, attribution
├── backend/                       FastAPI · uv · Python 3.12
│   ├── pyproject.toml  alembic.ini  migrations/
│   ├── app/
│   │   ├── main.py  config.py  db.py  security.py  worker.py
│   │   ├── models/      institutions, records, record_chunks, users, memberships,
│   │   │                import_batches, shelf_scans, shelf_scan_items, jobs,
│   │   │                audit_log, connector_runs
│   │   ├── schemas/
│   │   ├── adapters/    base.py (SourceAdapter + registry), loc_sru.py, loc_json.py,
│   │   │                internet_archive.py, dpla.py, europeana.py,
│   │   │                openlibrary.py (matching only), partner_csv.py, pdf_finding_aid.py
│   │   ├── services/    http.py (rate limit + retry + disk cache + UA + provenance),
│   │   │                normalize.py, rights.py, dedupe.py, geocode.py,
│   │   │                search.py (FTS + vector + RRF + filters + facets),
│   │   │                embeddings.py, llm/{base,openai,anthropic,fake}.py,
│   │   │                guide.py (RAG + citation validation), vision.py,
│   │   │                imports.py, publish.py, audit.py, status.py
│   │   └── routers/     search, records, institutions, guide, voice, status,
│   │                    partner_auth, partner_{profile,members,records,imports,
│   │                    finding_aids,shelf_scans,review}
│   ├── scripts/         db.py (embedded pg start/stop/url), seed.py, ingest.py, reindex.py
│   ├── fixtures/        institutions.json, queries.yaml, aliases.yaml,
│   │                    recorded real responses (loc_sru_*.xml, ia_*.json, ol_*.json),
│   │                    demo_partner_sample.csv
│   └── tests/
└── frontend/                      Next.js 16 App Router · TS · Tailwind 4 · MapLibre 6
    ├── app/           page.tsx (hero) · search/ · records/[id] · institutions/[id] ·
    │                  about/sources · partner/{login,dashboard,profile,members,records,
    │                  import,finding-aids,shelf-scan,review} · manifest.ts
    ├── components/    hero/ search/ filters/ map/ results/ guide/ voice/ partner/ ui/
    ├── lib/           api.ts  types.ts  store.ts (zustand: selection + map focus)
    └── styles/        tokens.css  globals.css
```

## 6. Data model (canonical fields per PRD §3)

**institutions**: id, slug, name, kind (museum|archive|library|university|community|government|online_repository), description, website_url, catalogue_url, address, city, region, country, contact_email, contact_phone, access_requirements, collection_summary, latitude, longitude, `location_precision` (partner_verified|building|road|locality|demo|unknown), `location_source` (free text, e.g. "Nominatim query … on 2026-11-07"), location_verified_by/at, `partner_status` (link_only|partner|demo), timestamps.

**records**: id uuid, source_system, source_record_id, institution_id (nullable = holding unknown), title, creators text[], description, subjects text[], date_text, date_start int, date_end int, resource_type, language text[], identifiers jsonb (lccn, isbn, oclc, openlibrary…), original_url, digital_url nullable, rights text, rights_status (public_domain|cc|in_copyright|unknown|restricted), access_type (online|physical|both|unknown), access_note, holding_verification (verified_partner|catalogue_record|unverified|demo), call_number, thumbnail_url, raw_metadata jsonb, source_updated_at, review_status (draft|in_review|published|withdrawn), provenance jsonb (adapter, fetched_at, request_url, query, import_batch_id, created_by), dedupe_key, search_tsv (generated; title A, creators+subjects B, description C), embedding vector, embedding_model, embedded_at, timestamps. Unique (source_system, source_record_id).

**record_chunks**: record_id, chunk_index, page_number nullable, text, page_url (e.g. `https://archive.org/details/{id}/page/n{idx}`), tsv, embedding, embedding_model.

**users**, **memberships** (user_id, institution_id, role), **audit_log** (institution_id, actor, action, entity_type, entity_id, before, after, at), **import_batches** (institution_id, kind csv|json|pdf|manual|shelf_scan, filename, status preview|committed|failed, mapping, row_count, error_count, duplicate_count), **shelf_scans** (institution_id, image_path, status queued|processing|proposed|reviewed|failed, model, error), **shelf_scan_items** (scan_id, spine_text, proposed_title/author/isbn, confidence, uncertainties text[], candidates jsonb, selected_candidate jsonb, call_number, shelf_label, confirmed_holding bool, status proposed|confirmed|rejected, record_id nullable), **jobs** (kind, payload, status, attempts, error, timestamps), **connector_runs** (source_system, query, started/finished, status ok|unconfigured|blocked|error, fetched, upserted, error, request_url).

Public search reads only `review_status='published'`. Dedupe: same `dedupe_key` (normalized title + first creator surname + year) across sources is **linked** ("Also catalogued at …"), never merged; inside one institution it is a flagged duplicate at import preview.

## 7. Build order (PRD §7) — each step ends runnable

### Step 0 — Scaffold
- `uv venv --python 3.12`; deps: fastapi, uvicorn, sqlalchemy[asyncio], asyncpg, pgvector, alembic, pydantic-settings, httpx, tenacity, pyjwt, argon2-cffi, python-multipart, pypdf, fastembed, openai, anthropic, pgserver, pytest, pytest-asyncio, pyyaml.
- `scripts/db.py` starts embedded pg, creates the `vector` extension, prints the URL; `make db`.
- `npx create-next-app@latest frontend --ts --tailwind --app --no-src-dir --eslint`; add maplibre-gl, zustand, papaparse, lucide-react. `next.config.ts` rewrites `/api/:path*` → `${API_URL}/api/:path*`.
- `.env.example`, `Makefile`, README skeleton.

### Step 1 — Real data in, cited result cards out
- `services/http.py`: shared async client, per-adapter token bucket, tenacity backoff, on-disk JSON cache with TTL, honest User-Agent `BlackHistoryDiscoveryHub/0.1 (hackathon prototype)`, provenance capture (request URL, fetched_at).
- `adapters/base.py`: `SourceAdapter` with `name`, `is_configured()`, `search(query, page)`, `normalize(raw) -> NormalizedRecord`, `status()`; registry.
- `loc_sru.py` (ElementTree MARCXML parse; leader → resource_type; institution = Library of Congress; access physical; `catalogue_record`; call number from 050; `digital_url` from 856 when ind2 ∈ {0,1}).
- `internet_archive.py` (search → metadata; online access; restricted vs open; rights from licenseurl / copyright status / date; `contributor` preserved and shown as "digitized from", not as a holding). OCR chunking for open, permitted items (public-domain mark, CC license, or published before 1930) from `_djvu.xml` per page, capped (~12 items, ~120 pages each).
- `loc_json.py`, `dpla.py`, `europeana.py` built from docs + fixtures; live statuses `blocked` / `unconfigured` on `GET /api/status/sources` and `/about/sources`.
- `normalize.py`, `rights.py`, `dedupe.py`; alembic migration 001; `scripts/ingest.py --source loc_sru --query "…"`; `fixtures/queries.yaml` (Black Loyalists; Africville; African Nova Scotian; Black Nova Scotians; Book of Negroes; Preston NS; Viola Desmond; William Hall VC; Underground Railroad Canada; Sierra Leone loyalists; Black Canadians history; Birchtown; Shelburne; Africville relocation).
- `fixtures/institutions.json` (real orgs, public addresses/URLs) + `geocode.py` (Nominatim, 1 req/s, cached, precision label).
- `search.py`: FTS (`websearch_to_tsquery`, weighted), vector kNN, RRF (k=60), deterministic filters, facets, institution pin aggregation, "unknown location" bucket. Routers: search, records, institutions.
- Frontend `/search` with result cards: title, date, type, institution, metadata-derived summary (no LLM), access badge, **View original source** / **Visit / Request access**, call number + access instructions when present, verification label, "Also catalogued at".
- Tests: adapter normalization on fixtures; search booleans/filters; published-only.

### Step 2 — Hero, advanced filters, map, evidence-grounded guide
- Design tokens (warm paper, deep ink, muted forest teal, brass, archival rule lines), type scale, brass focus rings, reduced-motion.
- Hero per sketch (see §4): big neutral guide placeholder plate center-left captioned "Guide character: designer asset pending"; serif headline + one-line promise; mic + wide input + submit bottom-right; **Advanced Search** small link top-right → deterministic form (Boolean/exact, date range, type, language, location, institution, identifier, online/physical). Below fold: institution directory strip; sources/attribution footer.
- Results per sketch: filter rail · map main stage (MapLibre, OpenFreeMap positron, attribution control, keyboard nav; sober DOM markers: solid ink = partner-verified, brass ring = catalogue record, dashed = demo; nothing for unknown locations) with preview cards anchored above pins on a stem · Online Resources panel docked bottom-right over the map · full accessible results list below the map (incl. "Location unknown / unverified"). Record↔institution two-way highlight via zustand. Mobile: filter drawer, map ~55vh with controls, online panel, list.
- `guide.py`: hybrid retrieval (records k=12 + chunks k=8) → evidence pack → provider call with strict JSON `{answer, citations:[{n, record_id, chunk_id?, quote?}], abstain, abstain_reason}` → server validation (every `[n]` maps to evidence; metadata-only records described only as catalogue entries; invalid → one retry with the error, then abstain) → response adds clickable original URLs, `highlight_record_ids`, `map_focus_institution_ids` (evidence-only). `aliases.yaml` query expansion (Africville, Preston/North Preston/East Preston, Black Loyalists/Loyalistes noirs, African vs Black Nova Scotian) in natural mode only.
- Guide panel with numbered citations that highlight cards/pins; abstention still shows records; "not configured" state when no key.
- Tests: citation validator (valid / foreign id / empty evidence → abstain) with the fake provider.

### Step 3 — Partner portal, shelf camera, voice
- Auth + roles + tenant guards (`security.py`: `current_user`, `require_role(institution_id, roles)`); seed accounts for BCCNS (owner/editor/reviewer) and Demo Partner; passwords printed by seed and listed in README.
- Portal: login · dashboard (sync status from connector_runs / import_batches / jobs, recent audit) · profile (location + precision, contact, access requirements, collection summary; owner may set verified coordinates → `partner_verified`) · members · records (by status; edit; withdraw) · manual entry · CSV/JSON import (upload → preview grid, auto field mapping by header synonyms, editable mapping, per-row error flags, duplicate flags → commit as drafts) · PDF finding aid (pypdf text → finding_aid record + page chunks → draft) · review queue (submit → in_review → publish/withdraw; audit on every transition).
- Shelf camera (`/partner/shelf-scan`, PWA manifest, `<input accept="image/*" capture="environment">`): upload → job → `vision.py` strict-JSON spine extraction (only visible text; uncertainties listed; no ISBN guessing) → Open Library candidates per item (title+author or ISBN; ≤1 req/s; cached) with scores → per-item review UI (editable fields, candidate radio incl. "none/manual", edition, call number, shelf label, mandatory "our institution physically holds this" checkbox) → Confirm creates a **draft** record (`source_system=partner_shelf_scan`, `holding_verification=verified_partner` only after confirm; Open Library stored as bibliographic reference) → normal review/publish. Nothing auto-publishes.
- Voice: push-to-talk component (Web Speech API, editable transcript, aria-live), optional `/api/voice/transcribe` when OpenAI key present, optional read-aloud toggle.
- `docs/partner-import-template.csv`, `docs/partner-api.md` (FastAPI OpenAPI at `/docs`).
- Tests: tenant isolation (A's editor → 403/404 on B's records/imports/scans); publish confirmation (confirm needs checkbox + selection; confirm yields draft; only reviewer/owner publish; withdraw disappears from public search); CSV preview errors/duplicates.

### Step 4 — Polish, verification, docs
- Accessibility pass: skip link, focus order, labels, contrast, reduced-motion, map keyboard hints, transcripts.
- README: setup, `.env` keys and how to obtain DPLA/Europeana keys, LoC JSON block note, run commands, seed, demo script matching the PRD acceptance demo, known limitations (no PostGIS, no Supabase Auth, LoC JSON blocked here).

## 8. Verification (end to end)

1. `make db && make migrate && make seed` → seed prints a connector table: loc_sru ok (N records), internet_archive ok (N records + M chunks), loc_json **blocked**, dpla/europeana **unconfigured**, demo partner CSV committed.
2. `make api` + `make web` → `http://localhost:3000`: hero renders; vague query ("what happened to Africville?") returns real cited records; guide answer shows numbered citations linking to `lccn.loc.gov` / `archive.org`; unsupported claim ("what did Viola Desmond eat for breakfast?") → abstain with records shown.
3. Map: LoC pin (brass ring) → anchored card lists LoC holdings with call numbers; Demo Partner pin dashed/labeled; unknown-holding records appear under "Location unknown", never on the map. Online Resources panel lists IA items separately from physical ones.
4. Advanced search: `"Black Loyalists" -Sierra`, date 1990–2020, type book, institution LoC → deterministic list; no guide involvement.
5. Partner: log in as BCCNS editor → CSV import preview flags a bad row and a duplicate → commit → reviewer publishes → record appears in public search (pin only after owner verifies location). Withdraw → gone from search. Shelf scan (phone, or desktop upload of a real shelf photo) → candidates with confidence → confirm one → draft → publish.
6. `cd backend && uv run pytest` green; `cd frontend && npx tsc --noEmit && npm run build` green.
7. `GET /api/status/sources` and `/about/sources` show honest connector states.

## 9. Open items for the owner
- Add `OPENAI_API_KEY` (PRD default models), `DPLA_API_KEY`, `EUROPEANA_API_KEY` to `.env` when obtained; connectors light up without code changes.
- LoC JSON API is Cloudflare-blocked for scripts from this network; try another network or rely on LoC SRU.
- Designer character assets replace the placeholder plate later.
