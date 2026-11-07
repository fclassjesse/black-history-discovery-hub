# PRD — Black History Discovery Platform
**Claude Code build brief | November 2026**

## 1. Product
An accessible, evidence-first discovery layer connecting Black history resources held by museums, archives, libraries and communities. Start with Black Nova Scotian/Canadian history, then international collections. Users include the general public, students and professional researchers. **We index records and link users to original institutions; we do not claim to own or digitize every source.** See the three accompanying sketches.

## 2. Core experiences
**Hero (`reference-hero.jpg`):** Spacious editorial homepage. Virtual guide positioned centrally/left; the character's design and motion assets will arrive from our designer, so use a neutral placeholder only. Large input accepts messy conversational text, incomplete questions and voice. Put **Advanced Search** discreetly top-right for Boolean/exact queries, dates, resource type, language, location, institution, identifiers and online/physical filters. Text search must remain usable without the guide.

**Results (`reference-results.jpg`):** Desktop has a left filter rail, a large *real, interactive, zoomable and pannable map*, and a right/bottom **Online Resources** panel. Markers show **verified physical holding institutions**, with anchored preview cards; selecting a record highlights its institution and vice versa. Each result displays title, date, type, institution, concise evidence-grounded summary, online/physical access status and **View Original Source** or **Visit/Request Access** link. Show call number and access instructions when verified. Clearly label unknown holdings/locations. On mobile, stack panels and preserve map controls. The guide can highlight retrieved records or pan the map, but cannot invent geographic facts.

**Partner Portal (essential):** Institution-specific, mobile-friendly login with owner/editor/reviewer roles. Partner profile includes location, contact, access requirements and collection details. Support **CSV/JSON imports, PDF finding aids, photo uploads, and manual entry** with preview, field mapping, error flags, duplicates, draft/review/publish workflow, edit/withdraw, sync status and audit trail. Offer a documented import template and API for later integration.

**Shelf-camera feature (essential):** Partner photographs a bookshelf from the mobile portal/PWA. Vision proposes *separate* books using spine text/title/author/ISBN. Cross-check candidates with targeted Open Library or authorized catalogue lookups; display candidate matches, confidence, uncertainties and editable fields. A human must confirm each item, edition, shelf/call number and that **their institution really holds it** before publishing. Never silently invent or auto-publish book metadata or holdings.

## 3. Data + evidence architecture
`Partner/API/CSV/photo → adapters → normalize & rights-check → PostgreSQL → keyword + vector search → cited RAG guide → map/online results → partner corrections` (`reference-data-flow.png`).

Canonical fields: `id`, `source_system`, `source_record_id`, `institution_id`, `title`, `creators`, `description`, `subjects`, `date`, `resource_type`, `language`, `identifiers`, `original_url`, `digital_url?`, `rights`, `access_type`, `holding_verification`, `call_number?`, `verified_institution_coordinates?`, `raw_metadata`, `source_updated_at`, `review_status` and `provenance`. Preserve source identifiers; deduplicate cautiously without merging distinct editions or different institutions' holdings. Do not index private or rights-restricted content without permission.

**Hybrid retrieval:** PostgreSQL full-text search + pgvector semantic search, fused/reranked; use permitted full text/OCR chunks with page-level citations where available. For **metadata-only** records, answer only what metadata actually establishes, never claim to have read the work. **Every substantive AI assertion must be supported by clickable original-source record URLs.** If evidence is insufficient, say so, show relevant records, and abstain. No fake quotes, events, locations, source links or availability. Advanced Search is deterministic, not an LLM-generated approximation.

## 4. Ingestion adapters / API priorities
Implement modular `SourceAdapter` connectors with pagination, provenance, retry/backoff, rate limits, cache and scheduled ingestion. Do not assume every online library catalogue exposes a public API.

| Priority | Source / method |
|---|---|
| **P0** | Library of Congress **digital** JSON API (`loc.gov`; no key, 20 req/min; *not* its complete library catalogue). |
| **P0** | DPLA `/v2/items` (API key; cross-institution digital metadata). |
| **P0 fallback** | Internet Archive search/metadata APIs, checking permissions and original links. |
| **P0** | Authorized partner CSV/JSON/manual records, including physical holdings. |
| **P1** | LoC catalogue SRU/MARCXML; Europeana API (key); IIIF for viewing digital objects. |
| **P1** | Open Library / Google Books **individual book matching** for shelf-camera candidates, respecting usage limits. |
| **P1** | Nova Scotia Archives, MemoryNS, Library and Archives Canada, Halifax Public Libraries: link first; request partner exports/permission before ingestion. **No unauthorized BiblioCommons scraping.** |
| **Later** | MARC21, Dublin Core/OAI-PMH, EAD and other standards when a provider actually supports them. |

## 5. Recommended 2026 stack
- **Frontend:** Next.js App Router, TypeScript, React, Tailwind with bespoke components; responsive partner PWA with mobile camera capture.
- **Map:** MapLibre GL JS + legitimate attributed vector-tile provider; verified institution geometry via PostGIS. No simulated map artwork.
- **Backend:** **FastAPI** (yes, use mentor's recommendation), Pydantic, SQLAlchemy, async `httpx`; modular ingestion, catalog, search, RAG, partner, map, voice APIs; background worker for imports/vision/indexing.
- **DB/auth/storage:** Supabase PostgreSQL, `pgvector`, PostgreSQL full-text search, PostGIS, Auth/RLS and file storage. Enforce tenant permissions server-side.
- **AI:** `gpt-6.1-terra` for vision extraction and grounded answer generation; optional `gpt-6-luna` for routine mapping/classification; `text-embedding-3-small` embeddings. Models configured via environment variables and server-side Responses API.
- **Voice:** MVP microphone → speech-to-text → **the exact same cited RAG service** → text output + optional TTS. Later optional full-duplex `gpt-live-1` delegating historical lookup to that service. No unsourced factual voice responses or default microphone activation.
- **Build:** Small monorepo, Docker, migrations, `.env.example`, seed importer, test fixtures; never expose API secrets to browser.

## 6. Visual art direction: *Contemporary Archival Atlas*
Create a distinctive combination of **modern museum editorial design, research reading room and historical cartography**—not an AI SaaS dashboard. Warm paper white, deep ink, muted forest teal and subtle brass; striking serif headlines, readable sans-serif UI, restrained archival dividers, substantial whitespace, precise source labels. Interactive map must look like a tasteful real atlas but use actual geographic tiles, sober markers, and clear linked record popovers.

**Avoid:** gradient orbs, glowing AI halos, sci-fi grids, glass cards, generic chat bubbles, playful pin emojis, invented map shapes, unnecessary animations, stock SaaS dashboard patterns. Build for WCAG 2.2 AA: keyboard use, contrast, transcripts, accessible forms and reduced-motion. Character visuals are handled separately by our designer.

## 7. Development order and proof of completion
1. **First**: real LoC data + a second permitted source/partner import; normalized records and original URLs; search and cited result cards.
2. **Second**: hero, advanced filters, working map with *verified or clearly labeled demo* institution locations, and separate online-resource links; evidence-grounded text guide.
3. **Third**: partner CSV/manual review/publish and functioning shelf-photo → candidate → human-confirmation flow; simple voice input using the same RAG path.
4. **Later**: live duplex voice, designer avatar animation, additional catalogue standards and automated partner sync.

**Acceptance demo:** vague text/voice query returns real cited records; online and physical sources remain distinct; clicking a verified pin reveals associated holdings; partner photographs a shelf and reviews a candidate; correcting/withdrawing a record changes the index; unsupported historical claims are refused. Include tests for source citations, publish confirmation and tenant isolation. If a key is missing, visibly mark the connector unconfigured and use clearly attributed, real seeded records—**never fake successful API calls**. Deliver runnable code, README, scripts and tests.

### Official technical references
LoC JSON https://www.loc.gov/apis/json-and-yaml | LoC SRU https://www.loc.gov/apis/additional-apis/search-retrieval-via-url/ | DPLA https://pro.dp.la/developers/requests | Europeana https://www.europeana.eu/en/how-to-register-for-and-manage-an-api-key | Open Library https://openlibrary.org/developers/api | MemoryNS https://www.councilofnsarchives.ca/memoryns/ | Halifax catalogue terms https://halifax.bibliocommons.com/info/terms | Supabase https://supabase.com/docs/guides/ai | MapLibre https://maplibre.org/maplibre-gl-js/docs/ | OpenAI models https://developers.openai.com/api/docs/models | Voice https://developers.openai.com/api/docs/guides/voice-agents
