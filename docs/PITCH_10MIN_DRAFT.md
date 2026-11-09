# 10-minute pitch — draft v1 (2026-11-08)

Black History Discovery Hub · RBC HubHacks · Problem Statement 1 (Black Cultural Centre for Nova Scotia)

Sources used for this draft: `Problem statement 1.pdf`, `Black Cultural Centre – Challenge Kickoff Notes.pdf`,
`Meeting notes.docx` (mentor summary), `README.md`, `docs/DB_RAG_OPTIMIZATION_PLAN.md`, the live local database
(counted 2026-11-08), and the code in `backend/app/services/{guide,vision,search}.py`.

---

## 1. How to sell it (the strategy, before the script)

### What the judges will score
The mentor summary tells us what wins: **clear problem → solution → working demo → community impact, without jargon.**
"Strong communication, usability and a convincing product demonstration are essential." "Build 1–2 fully working
features rather than several incomplete ones." So the deck must feel like one product, not a list of features.

### The big idea: follow one record's journey
Our three functions are three stops on one path. Tell it as one story, in the order the owner asked for:

```
 small museum / BCC shelf            the hub's engine                    a curious member of the public
 ─────────────────────────          ─────────────────────                ─────────────────────────────
 1. PORTAL  ───────────────▶  2. PIPELINE + EVIDENCE  ─────────────▶  3. NOVA
 "we add what we hold,            "every source becomes one              "ask anything, vaguely,
  in 5 minutes, no IT"             common record; every answer            get records + where they
                                    must point to one"                     are held"
```

This order also answers the three things the BCC said in the kickoff, one each:
| BCC constraint (kickoff notes) | Which function answers it |
|---|---|
| Only 8 staff; small partners must onboard easily and cheaply | 1. Portal (partners add their own listings; camera + spreadsheet, no cataloguing skills) |
| Different names, languages and formats; must not duplicate; must preserve provenance | 2. Pipeline (one common record, aliases EN/FR, duplicate detection, source link on every record) |
| Public-facing, for people who don't know where to look; AI must not invent | 3. Nova (vague/natural questions, every sentence cited, refuses when it can't prove it) |

### Cold open (30 s) — show the ending first
Judges decide in the first minute. Open on the finished experience, then rewind:
> "Before we explain anything, watch." → type a vague question into Nova → cited answer + globe flies to the holder.
> "That photo isn't on Google's first page. It's in a small Nova Scotia museum. Here's how it got here."

Then do functions 1 → 2 → 3, and land back on Nova for the full demo. The cold open makes the technical middle
feel like "how the magic works", not a lecture.

### Rules for the room
- **One hero question everyone remembers.** Suggested: *"that old Black hockey team from Africville"* → Africville
  Sea-Sides hockey photograph (1921), held by the Nova Scotia Sport Hall of Fame (record is in our curated set).
  **Verified 2026-11-08 (evening)** on the local build after a retrieval fix: Nova answers in three cited sentences and
  the photo is the first result. Re-test on the demo machine anyway (and hard-refresh first).
- **Say "where it is held" more than "AI".** The BCC fears looking like it owns other people's material. Every demo
  moment should end on the source institution's name and the "Visit / request access" link.
- **Never say "zero hallucination".** Judges can try to break it. Say: *"Nova can't publish a sentence without a
  source. Our server checks every quote word-for-word against the record. If it can't prove it, it says so."*
  Then prove it live with the refusal question.
- **Numbers on slides must be real.** Use the verified numbers in section 4.
- **Pre-recorded backup for every demo step** (mentor advice). Run live; switch to video at the first stall.

---

## 2. Run of show — 10:00, 4 speakers

Roles (assign names): **A = host/storyteller**, **B = portal**, **C = engine/tech**, **D = Nova**.
Whoever is not speaking drives the laptop (A drives during B/C/D; B drives during A's close).
≈ 130 spoken words per minute — scripts below are sized to that.

| Time | Who | Slide / screen | Content |
|---|---|---|---|
| 0:00–0:30 | D | Live: home page, Nova | **Cold open.** Ask the hero question. Answer + citation + globe flies. No talking over it. |
| 0:30–1:45 | A | Slides 1–2 | **Problem.** Personal story, the gap, the 3 constraints. |
| 1:45–4:00 | B | Slide 3 + live `/app` | **Function 1 — Institution portal.** Shelf camera, spreadsheet import, one standard format, review → publish. |
| 4:00–6:15 | C | Slides 4–5 (diagram) | **Function 2 — Engine.** Sources → common record → search index → evidence → checked answer. |
| 6:15–8:45 | D | Live: Nova | **Function 3 — Nova.** Vague question, French question, refusal, click through to holder. |
| 8:45–10:00 | A | Slides 6–7 | **Impact + ask.** What BCC gets on day 1, cost, what's next, close on the mission. |

### Slide list (7 slides + live demo)
1. **Title + hook line** — "Find it. See who holds it. Trust where it came from." Team names.
2. **The gap** — map of scattered holders (museums, archives, universities, community groups), 3 constraints from BCC.
3. **Function 1: partners add what they hold** — phone screenshot of shelf camera + CSV preview; "draft → review → published, withdraw any time".
4. **Function 2: one engine, one record format** — the pipeline diagram (section 3 below), plain-words labels.
5. **Function 2: why you can trust an answer** — an answer with `[1] [2]` + the record cards it points to, and the "I can't confirm that" refusal.
6. **Impact** — numbers (section 4), "for 8 staff: zero data entry for connected sources", bilingual, accessible.
7. **What's next + ask** — onboard first 5 BCC partners, digitization backlog via shelf camera, hosting cost.

---

## 3. Speaker scripts (draft — rewrite in your own voice)

### 0:00 — D · Cold open (live, ~30 s)
*(Home page open. Type slowly so the room can read.)*
> "Hi, I'm Nova's voice for today. Watch this." *(type: "that old Black hockey team from Africville")*
*(Answer appears, citation number, globe flies to Halifax.)*
> "A vague question. A real answer. And it tells you exactly who holds the photo."

### 0:30 — A · The problem (~75 s)
> "At the kickoff, the BCC's assistant director told us she went to high school right next to the Black Cultural
> Centre — and never learned about it. Black history in Canada is held by museums, archives, universities and
> community groups. They don't know about each other, and you only find something if you already know where to look.
>
> The BCC wants one trusted front door. But they gave us three hard limits. One: they have eight staff — they can't
> catalogue the country. Two: the hub must never look like it owns anyone's collection; it points you to the holder.
> Three: it's for the public, so it must be simple — and any AI must not make things up.
>
> We built one product that answers all three. B will start where history actually lives: on the shelf."

### 1:45 — B · Function 1: Institution portal (~2 min 15 s)
*(Phone or phone-size browser on `/app`, logged in as a BCC editor.)*
> "Most of this history is physical — books, photos, letters — and much of it has never been put online.
> A small museum has no IT person. So we built an app for their phone.
>
> *(Shelf camera.)* A staff member photographs a shelf. Our AI reads each spine, and it tells us what it is *not*
> sure about. We match each book to a public library record so nobody types a title twice. A person always
> confirms — the AI never publishes anything by itself.
>
> *(CSV import.)* Bigger partners already have spreadsheets or catalogue exports. They upload them as they are.
> We show a preview, map their column names to ours, and flag missing titles and duplicates before anything goes in.
> PDF finding aids work too, and so does typing one record by hand.
>
> *(Review queue.)* Everything lands as a draft. A reviewer from that institution publishes it — and can withdraw it
> any second, and it disappears from search immediately. Every change is in an audit trail.
>
> The result: every partner, big or small, ends up in one standard format, and the BCC didn't type a thing."

**Honesty note for B:** the shelf camera reads **book spines** today (`backend/app/services/vision.py`). For photos,
letters and objects, the path is spreadsheet / manual entry with a photo. If you want to say "AI describes any
physical object", that has to be built first — otherwise say "books today, photos and objects next".

### 4:00 — C · Function 2: the engine (~2 min 15 s)
Plain-words version for the room; technical names on the slide in small type for technical judges.

> "Here's what happens behind that search.
>
> **Step 1 — collect, don't copy.** We connect to 12 sources: the Library of Congress, Internet Archive, Dalhousie
> University Archives, the UK National Archives, Harvard, DPLA, Europeana, Wikimedia Commons, Nova Scotia Open Data,
> and partner uploads. We store only the description and a link back. The original stays with its owner.
>
> **Step 2 — one common record.** Every source describes things differently. We turn each one into the same card:
> title, people, places, communities, dates, type, who holds it, how to access it, and the link to the original.
> We also know that 'Black Loyalists' and 'Loyalistes noirs' are the same thing, and that the same book at three
> libraries is one book held in three places.
>
> **Step 3 — search by words and by meaning.** We search two ways at once: exact words, in English and French, and
> meaning — so 'the hockey team from Africville' finds a record that never uses those exact words. Then we combine
> and re-rank the results.
>
> **Step 4 — evidence first.** Before the AI writes a word, we hand it a numbered pack of real records. It may only
> use those. Every sentence must point to a number. Then our server — not the AI — checks every citation and every
> quote word-for-word. If something doesn't match, it gets one more try. If it still can't prove it, Nova says
> 'I can't confirm that' and shows you the records anyway.
>
> So the AI never has the last word. The records do."

### 6:15 — D · Function 3: Nova (live, ~2 min 30 s)
> "Nova is the front door for someone who knows nothing about archives."

Demo beats (≈30 s each):
1. **Vague input.** "what happened to Africville?" → short answer with `[1] [2]`. Click a citation → record card
   shows holder, access note, "View at source".
2. **Natural language + voice (optional).** Push-to-talk a question. Mention: "you don't need keywords or catalogue terms."
3. **French.** Switch FR, ask « Qu'est-ce que le Livre des Noirs ? » → answer in French, citing the UK National Archives
   record. Line: "A national hub has to work in both official languages."
4. **The refusal.** "What did Viola Desmond eat for breakfast?" → Nova declines, still lists records.
   Line: "This is the most important feature we built. A history hub that invents facts is worse than no hub."
5. **Where is it held.** Click a pin on the globe → institution card → "Visit / request access".
   Line: "We never keep you. We send you to the people who hold it."

### 8:45 — A · Impact and close (~75 s)
> "What does the BCC get? A public front door that already connects [12] sources and [1,536] records — in English and
> French. Partners add their own material from a phone, so eight staff aren't the bottleneck. Nothing is copied,
> every result names its owner, and the AI can't publish a sentence it can't prove.
>
> Next: onboard the first five BCC partners, use the shelf camera on the pre-1983 backlog, and open it to the public.
> [Cost line — fill in from research: hosting per month + cost per answer.]
>
> She never learned about the Black Cultural Centre in school, even living next door. We want the next student to
> find it in one question. Thank you."

---

## 4. Real numbers you may put on slides (counted 2026-11-08, local DB)

| Fact | Value | Source |
|---|---|---|
| Records indexed | **1,536** | `records` table |
| Searchable text passages (OCR pages, finding-aid text) | **4,226** | `record_chunks` |
| Source systems with records | **12** (Internet Archive 393, Harvard 283, Wikimedia Commons 211, DPLA 194, Dalhousie 127, LoC 98, UK National Archives 98, Europeana 90, hand-curated 16, demo partner 11, Open Canada 10, NS Open Data 5) | `records.source_system` |
| Institutions in directory | **25** | `institutions` |
| Languages | English + French, end to end (UI, search, answers) | README |
| Automated tests | ~80 (citation validation, tenant isolation, bilingual, public guards) | `backend/tests` |
| AI answer attempts before refusal | 3 (first try + 2 corrective retries) | `guide.py` `MAX_ATTEMPTS` |

Re-count on the demo machine before the pitch if you re-seed. Don't claim the Smithsonian/NYPL connectors as live
(they wait for keys) and don't claim LAC / Archives of Ontario (blocked; we did not bypass).

---

## 5. Tech talking points (for C, and for Q&A)

Keep these ready; use the plain-words version on stage and the technical version only if a judge asks.

| Topic | Plain words | Technical (Q&A) |
|---|---|---|
| Ingestion | "We connect to catalogues that offer open access, and we respect their rules." | One adapter per source (`backend/app/adapters/`): SRU/MARCXML (LoC), OAI-PMH (Dalhousie), REST (TNA, Harvard, DPLA, Europeana, IA, Commons), Socrata/CKAN. ≤1 req/s per source, honest user agent, 7-day HTTP cache, no bypassing of blocks — blocked sources are shown as "blocked" on `/about/sources`. |
| Standard format | "Every source becomes the same card." | Common `Record` model (`models/core.py`): title, creators, subjects, people/places/communities arrays, date range, resource type, language, identifiers, original_url, rights, access type/note, holding verification, call number; raw metadata kept for provenance. |
| Same name, different words | "We know two names mean the same thing." | `fixtures/aliases.yaml` (EN/FR alias groups, accent-insensitive), gazetteer of African Nova Scotian communities from NS Open Data, deterministic entity extraction. |
| Duplicates / relationships | "Same book in three libraries = one book, three holders." | `work_keys` (ISBN-13, OCLC, LCCN, title+creator+year) with GIN overlap → "also catalogued at". |
| Search | "Words and meaning together." | Postgres full-text (English + French dictionaries) + pgvector semantic search (local `bge-small` embeddings, HNSW index), fused with Reciprocal Rank Fusion, local cross-encoder rerank of top 40. |
| Grounded answers | "The AI only sees real records and must cite each sentence." | Evidence pack of numbered records + passages → strict-JSON answer → server-side validator: every citation must exist in the pack, quotes must be verbatim substrings; up to 2 corrective retries, then abstain while still returning records. |
| Physical items | "The shelf camera turns a shelf into drafts." | Vision model proposes books with confidence + uncertainties (told not to guess ISBNs) → Open Library candidates → human confirms → draft → reviewer publishes. |
| Trust & ownership | "Partners control their own records." | Institution-scoped roles (owner/editor/reviewer), draft → review → published → withdrawn, audit trail, tenant isolation tested. |
| Privacy & cost | "No visitor accounts, no tracking." | Questions kept 30 days without IP; daily AI cap (300/day, 30/visitor), salted in-memory IP hash; local embeddings = no per-search cost. |
| Stack | — | Next.js 16 + MapLibre globe; FastAPI + PostgreSQL 16 + pgvector; Claude (Anthropic) for answers and vision; OpenAI optional. |

### Likely judge questions — have one-line answers ready
1. *How do you stop hallucination?* → server-side citation check + refusal (demo it).
2. *Who maintains this with 8 staff?* → partners self-serve; connectors refresh automatically (`make refresh`).
3. *What about restricted / sensitive records?* → access type + access note on each record, "request access" link,
   partner can withdraw instantly. (Cultural protocols for family records/oral histories: say we'd co-design with BCC.)
4. *Copyright?* → we store descriptions and links, not collections; licensed media only from Wikimedia Commons.
5. *What does it cost to run?* → fill in from research (section 6).
6. *How does it scale to all of Canada?* → new source = one adapter or one spreadsheet; vector index + full-text scale to 100k+ records on one Postgres.
7. *Why a character?* → the target user knows nothing about archives; a guide lowers the fear of "I don't know what to search".

---

## 6. Questions to research before the pitch

### About the room and format (ask organizers / mentors — highest priority)
1. Is it 10 minutes **including** Q&A, or 10 + Q&A? Hard cut-off or soft?
2. What are the judging criteria and their weights? Who are the judges (RBC tech, BCC staff, Volta)?
3. Projector: resolution and aspect ratio (16:9?), HDMI or USB-C, can we use our own laptop?
4. Is venue Wi-Fi reliable enough for a live AI call? Can we hotspot? Can we mirror a phone screen for the shelf camera?
5. Live demo allowed, or must it be a recording? Is a pre-recorded fallback acceptable mid-pitch?
6. Will the BCC (Russell Grosse / assistant director) be in the room? If yes, speak to their constraints by name.

### About presenting
7. How do winning hackathon pitches structure a 10-minute slot (problem → live demo → impact)? Look at recent
   Devpost / MLH winner videos for timing.
8. How do others explain RAG / "grounded AI" to non-technical audiences? (Look for a one-picture analogy — we use
   "a librarian who must show the page for every sentence".)
9. How to hand off between 4 speakers smoothly (who holds the clicker, who drives the demo)?
10. Best practice for a live AI demo: pre-warming, fixed demo questions, fallback video.

### Facts for the impact slide (verify; cite the source on the slide)
11. How many historic African Nova Scotian communities are there? (often quoted ~50 — verify.)
12. Size of the BCC's partner network across Canada — ask the BCC directly.
13. Africville: key dates (1960s relocation, 2010 Halifax apology) — for the hero question context.
14. Comparable national discovery hubs: Trove (Australia), DPLA (US), Europeana (EU), Canadiana, ArchivesCanada.ca —
    what they cost and how many staff they have. Supports "a small team can run a federated hub".
15. Real running cost: hosting per month (see `docs/DEPLOY.md` options) + Anthropic cost per answer at our prompt size.

### Respect and risk
16. Community / cultural protocols for Black Canadian family records, oral histories and photos of individuals —
    is there an accepted framework we should name?
17. Accessibility: which WCAG 2.2 AA items can we show in 10 seconds (keyboard-only, flat-map toggle)?

---

## 7. Demo-day checklist

- [ ] **Raise the per-visitor AI cap on the demo machine.** Default is 30 answers per visitor per day
      (`GUIDE_DAILY_LIMIT_PER_VISITOR`); a team rehearsing from one IP will hit it. Set `0` (unlimited) for demo day.
- [ ] Test every demo question on the demo machine the night before; write down the exact wording that works.
- [ ] Run each demo question again ~5 minutes before going on — answers are cached for 10 minutes, so it will be
      instant on stage.
- [ ] Record a screen video of the full demo (cold open, portal, Nova 5 beats) as a fallback.
- [ ] Have a shelf photo ready on the phone in case the room camera angle is bad.
- [ ] Hard-refresh the browser (stale CSS has bitten us before).
- [ ] Log in to `/app` as `editor@bccns.example` ahead of time; have `docs/demo-upload.csv` on the demo machine
      (9 real Library of Congress rows with partner-style headers `Author` / `Year` / `Record URL`, one deliberate
      duplicate → preview shows "9 rows · 0 errors · 1 duplicate", mapping works, "Create 8 drafts"). Every row says it
      is a demo row copied from the LoC catalogue, so nobody mistakes it for a BCCNS holding.
- [ ] **After the demo, withdraw the demo drafts/published rows** from Review (or run the cleanup SQL in the handoff) so
      BCCNS goes back to zero holdings before the repo/DB is shown to anyone else.
- [ ] The upload flow creates drafts only; publishing needs the **reviewer** login (`reviewer@bccns.example`) — decide who
      types which password on stage.
- [ ] Two full timed rehearsals with all 4 speakers; cut lines, not demo beats, if over time.
- [ ] Decide on one person to answer each Q&A topic (tech → C, partners/data → B, product/public → D, impact/cost → A).
