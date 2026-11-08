# Black History Discovery Hub — MVP

An evidence-first discovery layer for Black history resources held by museums, archives, libraries and communities,
built for RBC HubHacks with the Black Cultural Centre for Nova Scotia (BCCNS). **We index records and link people to
the institution that holds them; we never claim to own the material, and the AI guide never speaks without a citation.**

Spec: [`PRD.md`](PRD.md) · plan: [`docs/BUILD_PLAN.md`](docs/BUILD_PLAN.md) · partner contract: [`docs/partner-api.md`](docs/partner-api.md) · sources & terms: [`docs/sources.md`](docs/sources.md)

## What is in the box

| Layer | Stack |
|---|---|
| Frontend | Next.js 16 (App Router, TypeScript, Tailwind 4), MapLibre GL **globe** on OpenFreeMap tiles, GSAP + Lenis motion, Young Serif / Instrument Serif / Bricolage Grotesque, PWA manifest for the partner shelf camera |
| Backend | FastAPI, SQLAlchemy 2 (async), PostgreSQL 16 + pgvector + full-text search, Alembic, fastembed (local embeddings), provider switch OpenAI ⇄ Anthropic |
| Data | Library of Congress catalogue (SRU/MARCXML, live), Internet Archive (live, with page-level OCR for open items), Dalhousie University Archives finding aids (OAI-PMH, live; fonds-level descriptions matched locally, matching fonds read in full), The National Archives UK (Discovery, live), Harvard Library (LibraryCloud, live), Wikimedia Commons (live, licensed media), Nova Scotia Open Data (live), DPLA and Europeana (live with free keys), partner CSV/JSON/PDF/manual/shelf-camera uploads; Smithsonian / NYPL connectors built and reporting `unconfigured` until a free key is added; LoC JSON reporting `blocked` honestly |
| Guide | hybrid retrieval (FTS + vector, RRF) → numbered evidence pack → strict-JSON answer → **server-side citation validation** (retry once, then abstain) |
| Partner portal | institution-scoped logins (owner / editor / reviewer), draft → in review → published → withdrawn with audit trail, CSV/JSON import preview with field mapping + error/duplicate flags, PDF finding aids, manual entry, shelf camera → Open Library candidates → human confirmation → draft |
| Institution app | `/app`: phone-first PWA in the same cartoon style for partner staff — shelf camera (vision model), uploads (CSV/JSON, PDF, by hand), review queue, with Nova the guide in every header |

## Requirements

- macOS/Linux, **Python 3.12 via [uv](https://docs.astral.sh/uv/)** (`uv python install 3.12`), **Node 20+ with npm**
- No Docker/psql needed: `make db` runs an embedded PostgreSQL 16 + pgvector (the `pgserver` wheel). `docker-compose.yml` is provided for Docker users.
- Internet access for the seed (LoC SRU, Internet Archive, Dalhousie OAI-PMH, UK National Archives, Harvard LibraryCloud, Wikimedia Commons, NS Open Data, DPLA/Europeana with keys, Open Library, Nominatim, Hugging Face model download ≈130 MB on first run) and for map tiles.

## Setup

```bash
cp .env.example .env            # then edit (see "Environment" below)
make install                    # backend: uv sync · frontend: npm install
make db                         # start embedded Postgres on 127.0.0.1:54329 (creates bhdh + bhdh_test, vector extension)
make migrate                    # alembic upgrade head
make seed                       # institutions (geocoded), partner logins, LIVE connectors, demo partner CSV — prints a connector table
```

The seed is idempotent and takes a few minutes (rate limits are respected: ≤1 request/s per source). `SEED_MAX_PER_QUERY=10 make seed` for a quicker run, `uv run python scripts/seed.py --no-live` to skip connectors.

## Run

```bash
make api      # FastAPI on http://127.0.0.1:8000 (OpenAPI at /docs)
make web      # Next.js on http://localhost:3000 (proxies /api/* to the backend, same-origin cookies)
make worker   # optional: background job worker; by default JOBS_INLINE=true runs shelf-scan jobs inside the API
```

Open <http://localhost:3000> (public site: Nova the guide + the globe, one page) and <http://localhost:3000/app> (institution app, sign in with a partner login).

**Partner logins** (seeded; password `hub-demo-2026` unless `SEED_PASSWORD` is set — **local development only**: with `APP_ENV=production` the seed refuses this published password and skips the quick `test@test.com` login; see `docs/DEPLOY.md`):

| Institution | owner | editor | reviewer |
|---|---|---|---|
| BCCNS (real institution, **zero pre-seeded holdings**) | owner@bccns.example | editor@bccns.example | reviewer@bccns.example |
| Demo Partner (sample data) | owner@demo-partner.example | editor@demo-partner.example | reviewer@demo-partner.example |

## Tests and checks

```bash
cd backend && uv run pytest          # 80 tests: bilingual search/guide, citation validation, publish confirmation, tenant isolation, adapter fixtures (incl. Dalhousie OAI-PMH), CSV preview, search, public-deployment guards
cd frontend && npx tsc --noEmit && npm run build
```

Tests use the `bhdh_test` database on the embedded server (started by `make db`), fake embeddings and a scripted fake LLM — no network, no keys.

## Environment (`.env` in the project root)

| Variable | Default | Purpose / how to get it |
|---|---|---|
| `DATABASE_URL` | `postgresql://postgres@127.0.0.1:54329/bhdh` | any Postgres 16 with pgvector works (Supabase, Homebrew, Docker) |
| `TEST_DATABASE_URL` | `…/bhdh_test` | used by pytest |
| `PG_PORT`, `PGDATA_DIR` | `54329`, `backend/.pgdata` | embedded server settings |
| `LLM_PROVIDER` | `auto` | `openai` (PRD default, Responses API) · `anthropic` · `none`. `auto` = openai if `OPENAI_API_KEY`, else anthropic if `ANTHROPIC_API_KEY`, else none (guide abstains, shelf vision reports *unconfigured*). **This build runs on Anthropic `claude-sonnet-5-5`** because only `ANTHROPIC_API_KEY` is available. |
| `OPENAI_API_KEY` | — | <https://platform.openai.com/api-keys>. Enables `gpt-6.1-terra` guide + vision, `text-embedding-3-small` (`EMBEDDINGS_PROVIDER=openai`) and server-side voice transcription |
| `OPENAI_MODEL`, `OPENAI_VISION_MODEL`, `OPENAI_TRANSCRIBE_MODEL` | `gpt-6.1-terra`, `gpt-6.1-terra`, `gpt-4o-mini-transcribe` | |
| `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL` | —, `claude-sonnet-5-5` | <https://console.anthropic.com/> |
| `EMBEDDINGS_PROVIDER` | `local` | `local` = fastembed `BAAI/bge-small-en-v1.5` (no key) · `openai`. After switching run `uv run python scripts/reindex.py` |
| `DPLA_API_KEY` | — | free: `curl -X POST https://api.dp.la/v2/api_key/<your-email>` (key arrives by email) |
| `EUROPEANA_API_KEY` | — | free: <https://www.europeana.eu/en/how-to-register-for-and-manage-an-api-key> |
| `HTTP_USER_AGENT`, `HTTP_CACHE_TTL_SECONDS` | honest UA, 7 days | outbound etiquette |
| `APP_ENV` | `development` | `production` turns on the startup guards: the API refuses to start with the dev `JWT_SECRET` (or one under 32 chars), `COOKIE_SECURE=false`, or localhost `CORS_ORIGINS`/`PUBLIC_BASE_URL` |
| `JWT_SECRET`, `JWT_EXPIRE_MINUTES`, `COOKIE_SECURE` | dev values | **change `JWT_SECRET`** beyond local demos |
| `GUIDE_DAILY_LIMIT`, `GUIDE_DAILY_LIMIT_PER_VISITOR` | `300`, `30` | AI-written answers per UTC day (0 = unlimited). Over the cap Nova says so and still lists the matching records. Visitors are counted by a salted IP hash held in memory only |
| `TRUST_PROXY_HEADERS` | `true` | read the visitor IP from `X-Forwarded-For` (the API sits behind the Next.js proxy) |
| `SEARCH_LOG_RETENTION_DAYS` | `30` | logged questions are deleted after this many days (0 = keep) |
| `NEXT_PUBLIC_PRIVACY_CONTACT` (frontend) | — | email shown on `/privacy` for questions and removal requests |
| `JOBS_INLINE` | `true` | `false` → run `make worker` |
| `UPLOAD_DIR`, `CORS_ORIGINS`, `SEED_PASSWORD`, `SEED_MAX_PER_QUERY` | see `.env.example` | |
| `API_URL` (frontend) | `http://127.0.0.1:8000` | where Next.js proxies `/api/*` |

Connectors light up automatically when a key is added — no code changes. Their state is always visible on `/about/sources`.

## Useful scripts

```bash
cd backend
uv run python scripts/ingest.py --source loc_sru --query "Viola Desmond" --max 20      # one connector, one query
uv run python scripts/ingest.py --source internet_archive --query "Africville" --full-text
uv run python scripts/reindex.py --only-missing                                       # recompute embeddings
uv run python scripts/db.py stop                                                      # stop embedded Postgres
```

## Demo script (matches the PRD acceptance demo)

1. **Vague question, real cited records.** Home → type (or push-to-talk) *"what happened to Africville?"* → Ask. The Guide answers in a few sentences; every claim ends in `[n]`; each citation links to `lccn.loc.gov/…` or `archive.org/details/…` (page-level links for OCR passages). Click a citation to highlight the record and pan the map.
2. **Online and physical stay distinct.** On the results page the *Online resources* panel (bottom-right of the map) lists Internet Archive items; the map only pins institutions with **physical** holdings and a known location (Library of Congress = brass ring "catalogue record"; Demo Partner = dashed "demo"). Records without a location are counted as "location unknown" and appear only in the list.
3. **Click a verified pin.** Click the Library of Congress pin → anchored card lists holdings with call numbers → "Visit / request access" opens the institution page with access requirements.
4. **Unsupported claim is refused.** Ask *"what did Viola Desmond eat for breakfast?"* → the Guide abstains and still shows the matching records.
5. **Advanced search is deterministic.** Top-right "Advanced search" → query `"Black Loyalists" -Sierra`, type *book*, institution *Library of Congress* → SQL-only results, no guide involvement.
6. **Partner import → review → publish → withdraw.** Partner portal → log in as `editor@bccns.example` → *Import CSV / JSON* → upload [`docs/partner-import-template.csv`](docs/partner-import-template.csv) (or your own; the preview flags missing titles and duplicates and lets you remap columns) → Commit → *Records* → Submit for review. Sign out, log in as `reviewer@bccns.example` → *Review queue* → Publish → the record is now in public search; its pin carries the seeded precision label (BCCNS: *road-level, approximate*) until an owner ticks the verification box on *Profile & location*, which upgrades it to *partner-verified*. Withdraw → it disappears from search immediately.
7. **Shelf camera.** Log in on a phone (or desktop) → *Shelf camera* → photograph a shelf. Vision proposes separate books with confidence and uncertainties; Open Library candidates appear per book; edit the title/author, pick the edition, enter call number and shelf, tick **"Our institution physically holds this item"** → Confirm creates a **draft**. Publish it from the Review queue. Without an AI key the upload returns a visible *vision unconfigured* error.
7b. **Held in Canada.** The filter rail has a *Held in* group (country of the holding institution) so the demo can be narrowed to Canadian holders in one click; online-only items have no holder country and stay in the *Online resources* panel.
8. **Transparency.** `/about/sources` shows each connector live: LoC SRU, Internet Archive, Dalhousie OAI-PMH, UK National Archives, Harvard, Wikimedia Commons, NS Open Data (and DPLA/Europeana with keys) ok; Smithsonian/NYPL **unconfigured** until a key is added; LoC JSON **blocked** (Cloudflare challenge, not circumvented), DPLA/Europeana **unconfigured**.

## Languages (English / French)

The whole product is bilingual (added 2026-11-07): public site, partner portal, institution app, data labels, search and the guide.

- **Locale in the URL.** `/…` is English, `/fr/…` is French. `frontend/proxy.ts` rewrites `/fr/x` to the `/x` route and passes `x-locale: fr`; `/en/x` redirects to `/x`. The choice is remembered in the `bhdh_locale` cookie, so a returning French reader who opens `/` is sent to `/fr`. The header (and the institution-app header) shows an **EN | FR** switch. `<html lang>` follows the locale; dates and numbers use `en-CA` / `fr-CA`; push-to-talk recognises `fr-CA` in French.
- **Strings live in one place:** `frontend/messages/en.json` and `frontend/messages/fr.json` (same keys, checked by hand with a small script; a missing key renders as the key itself, never silently). Client components call `const { t, tn, raw, label } = useT()` from `@/lib/i18n`; server components call `await getT()` from `@/lib/i18n-server`. Internal links use `Link` from `@/lib/i18n` (prefixes the locale) and `useLocaleRouter()` instead of `useRouter()`.
- **Data labels** (resource types, access, rights, holding verification, language names such as *English / Anglais*, *No linguistic content* for `zxx`) are translated; **source data** (titles, descriptions, partner-typed notes) stays in its source language. Institution descriptions carry an *English only / French only* badge when their language differs from the UI (deterministic function-word detection, no badge when unsure).
- **API.** `GET /api/search`, `/api/records/{id}`, `/api/institutions/{slug}/records` take `?locale=en|fr` and return localized `resource_type_label`, `language_labels`, `summary` and connector `access_note`s (translated sentence by sentence from `backend/app/services/i18n.py`; partner-written notes are left as written). Facet labels follow the locale too.
- **Search.** Records and passages carry two generated tsvectors: `search_tsv` / `tsv` (`'english'`) and `search_tsv_fr` / `tsv_fr` (`'french'`, migration 0003). Natural mode runs each query variant against both dictionaries and fuses by RRF; Advanced mode ORs both dictionaries in one deterministic SQL query. `fixtures/aliases.yaml` has French names for every group (Loyalistes noirs, Livre des Noirs, Chemin de fer clandestin, Néo-Écossais d'origine africaine…), matched without regard to case or accents. French question words are stripped before retrieval (« Qu'est-ce que le Livre des Noirs ? » → `Livre des Noirs`). The embedding model is English-only (see `docs/sources.md`).
- **Guide.** `POST /api/guide/ask` accepts `locale`; the system prompt tells the model to answer in the language of the question and to fall back to the UI language, never translating a quote. Abstain messages are translated server-side. The citation validator is unchanged.

**Add a string:** add the key to *both* `messages/en.json` and `messages/fr.json`, then use `t("section.key")` (or `tn("section.key", n)` for `_one` / `_other` plurals, `raw("section.key")` for arrays). Run `npx tsc --noEmit`; keep the two files' key sets identical.

**Add a locale (e.g. `mi`):** add it to `LOCALES` / `BCP47` / `LOCALE_NAME` in `frontend/lib/i18n-core.ts`, create `frontend/messages/mi.json` with every key, map it in `frontend/lib/i18n-server.ts`, widen the regexes in `proxy.ts` and `i18n-core.ts` (`en|fr` → `en|fr|mi`), and on the backend add the code to `LOCALES` and the tables in `backend/app/services/i18n.py` plus the `pattern` on the `locale` parameters. A third full-text dictionary would need a new generated column and migration.

## Design

"Paper Atlas" (rebuilt 2026-11-07, see [`docs/DESIGN.md`](docs/DESIGN.md)): a real MapLibre **globe** sits behind the
page as an orange sea with paper continents; content floats over it in chalk plates and speech bubbles. Vermilion /
ochre / sun / rose / moss palette with semantic colour (moss = online, sun = catalogue record, ink = partner-verified,
dashed = demo). Young Serif slab headlines, Instrument Serif italic accents, Bricolage Grotesque UI. GSAP + Lenis
motion (scroll reveals, parallax, cursor tilt, page wipes), all reduced-motion aware. The guide character is a
separately designed asset; `frontend/lib/character.ts` is the integration contract and a neutral paper "understudy"
stands in until it arrives. WCAG 2.2 AA: skip link, labelled controls, focus rings, flat-map toggle and a complete
results list beside the globe for keyboard and screen-reader users.

## Known limitations

- **LoC JSON API** is Cloudflare-blocked for scripts on the build network; the connector reports `blocked` and the LoC catalogue (SRU) is the live LoC source. Try another network — no code change needed.
- **No PostGIS**: institutions store lat/lon + a precision label; fine at this scale.
- **Auth is FastAPI-native** (argon2 + JWT cookie) rather than Supabase Auth/RLS; tenant checks are enforced server-side on every partner endpoint and covered by tests.
- **Voice** uses the browser Web Speech API (push-to-talk, editable transcript). Server transcription needs `OPENAI_API_KEY`; live duplex voice is out of scope.
- **Uploaded files** (PDF finding aids, shelf photos) are served by `app/routers/files.py`: a file that a **published** record points to (a finding-aid PDF) is public; everything else is visible only to signed-in members of the uploading institution (others get 404).
- **Search candidate cap**: natural-language search keeps lexical hits plus semantic hits under a cosine-distance floor, ranked and capped at 300 (the UI then says "300+ · showing the 300 most relevant"); browse mode reports the true count but pages through the 300 most recent.
- Partner-verified holdings can also be declared in manual entry, but only with an explicit confirmation checkbox that is written to the audit trail.
- The **Demo Partner** is fictional. Its records are real Open Library bibliographic entries but its *holdings* are sample data (`holding_verification=demo`, dashed pin). BCCNS has logins and no holdings until staff add them.
- **Nova** is the designer's painted portrait (`png-girl1.png`), cut into animation layers by `frontend/scripts/build_nova_layers.py` without repainting; the rig lives in `frontend/components/character/` (portrait, speech bubble, styles).
- **Privacy**: `/privacy` (EN/FR) explains what is kept: question text (no IP, no ID, deleted after 30 days), what goes to Anthropic, browser voice recognition, map tiles. No visitor accounts or analytics; the only visitor cookie remembers the language. Failed partner sign-ins are throttled (10 per 15 min).

## Search, entities and the guide (2026-11-07 optimization)

- **Entity axes.** Every record carries `people`, `places` and `communities` arrays extracted deterministically from its own creators, subjects and description (`app/services/entities.py`; communities list from the NS Open Data set *African Nova Scotian Family Names by Region*, see `fixtures/gazetteer.yaml`). They are facets and filters (`/api/search?communities=Africville`), GIN-indexed.
- **Relationship mapping.** `work_keys` (ISBN-13 / OCLC / LCCN / title+creator+year) link the same work across institutions → "also catalogued at".
- **Description passages.** Long catalogue / finding-aid text (≥ 400 chars, no OCR) is split into sentence-aligned passages the guide can quote, labelled DESCRIPTION (text *about* the item), distinct from EXCERPT (text *from* the item).
- **Guide.** Reads the active filters, understands short follow-ups ("where is it held?") by reusing the previous question's keywords and cited records, collapses duplicate works, caps passages per record, reranks candidates with a local cross-encoder (`RERANKER=local|none`), and caches answers (`GUIDE_CACHE_TTL_SECONDS`). Citation validation is unchanged.
- **Vector indexes.** HNSW (cosine) on records and passages via expression indexes per embedding model (migration 0002).
- **Search gaps.** Every search / guide question is logged (query text and counts only) → `GET /api/status/search-log`, shown at the bottom of `/about/sources`.
- **Maintenance.** `make backfill` recomputes entities, work keys, passages and embeddings for existing rows; `make refresh` re-runs connectors and re-embeds stale rows (cron-able). `cd backend && uv run alembic upgrade head` after pulling.
