# Going live — public demo deployment

Written 2026-11-08. Goal: a public URL for the Black History Discovery Hub that is safe for visitors' privacy and
for the API bill. The code-side guards are done (see "What the code already enforces"); what remains is choosing
hosts, setting the environment, seeding, and the launch checks below.

## What the code already enforces

| Risk | Guard | Where |
|---|---|---|
| Uploaded shelf photos / PDFs readable by anyone with the link | `/api/files/{institution}/{name}`: public only if a **published** record points to it (finding-aid PDF); otherwise members of that institution only; everyone else gets 404. Names are validated, path traversal rejected | `backend/app/routers/files.py`, tests in `backend/tests/test_public_guards.py` |
| Published demo password (`hub-demo-2026`) and quick login (`test@test.com` / `12345678`) | With `APP_ENV=production` the seed **refuses** a `SEED_PASSWORD` that is the default or shorter than 14 chars, never creates the quick login, and does not print the password | `backend/scripts/seed.py` |
| Dev JWT secret (forged staff sessions) | With `APP_ENV=production` the API **refuses to start** unless `JWT_SECRET` ≥ 32 chars and not the dev value, `COOKIE_SECURE=true`, and `CORS_ORIGINS` / `PUBLIC_BASE_URL` are not localhost | `backend/app/config.py` |
| Password guessing on partner logins | 10 failed sign-ins per (visitor, email) per 15 min → 429 | `backend/app/services/quota.py`, `routers/partner_auth.py` |
| API bill (anyone can ask Nova questions) | `GUIDE_DAILY_LIMIT` (default 300 AI answers / UTC day) and `GUIDE_DAILY_LIMIT_PER_VISITOR` (30). Counted only when the model would be called; cached answers and "no records" answers are free. Over the cap Nova says so and still lists the matching records | `backend/app/services/quota.py`, `services/guide.py` |
| Visitors typing personal details into questions | `search_log` keeps question text only (no IP, no ID) and deletes rows older than `SEARCH_LOG_RETENTION_DAYS` (30) on startup and daily | `backend/app/services/searchlog.py`, `app/main.py` |
| Telling visitors what happens to their data | `/privacy` (EN + FR), linked from the menu and footer; contact from `NEXT_PUBLIC_PRIVACY_CONTACT` | `frontend/app/privacy/page.tsx`, `messages/*.json` → `privacy` |

Visitor counting for the daily cap uses a salted hash of the IP held **in memory only** (salt rotates daily; nothing
is stored). The cap is per API process, so run **one** API process (single uvicorn worker).

## Recommended hosting (small, cheap, fits the stack)

| Piece | Recommendation | Why / notes |
|---|---|---|
| Frontend (Next.js 16) | **Vercel** (Hobby/Pro) | Native Next host. `next.config.ts` rewrites `/api/*`, `/api-docs`, `/openapi.json` to `API_URL`, so the browser stays same-origin and the session cookie is first-party |
| Backend (FastAPI) | **Render** or **Railway** web service, **≥ 2 GB RAM**, one instance, a **persistent disk** mounted for `UPLOAD_DIR` (and `HTTP_CACHE_DIR`) | The local embedding model and the cross-encoder load in memory (~1 GB peak). Uploads are files on disk, so the disk must survive deploys |
| Database | **Neon** or **Supabase** Postgres 16 with `pgvector` enabled | `CREATE EXTENSION vector;` once. Use the pooled connection string only if it supports prepared statements for asyncpg; otherwise the direct one |

Region: Canada (e.g. `ca-central` / Toronto / Montréal) for all three where offered, to keep visitor data in Canada.

## Environment

### Backend

```bash
APP_ENV=production
DATABASE_URL=postgresql://USER:PASSWORD@HOST:5432/DB         # from Neon/Supabase
JWT_SECRET=$(python -c 'import secrets; print(secrets.token_urlsafe(48))')
COOKIE_SECURE=true
CORS_ORIGINS=https://YOUR-DOMAIN
PUBLIC_BASE_URL=https://YOUR-DOMAIN
ANTHROPIC_API_KEY=...                                         # set a monthly spend limit in the Anthropic console too
LLM_PROVIDER=anthropic
GUIDE_DAILY_LIMIT=300
GUIDE_DAILY_LIMIT_PER_VISITOR=30
SEARCH_LOG_RETENTION_DAYS=30
TRUST_PROXY_HEADERS=true
UPLOAD_DIR=/data/uploads                                      # on the persistent disk
HTTP_CACHE_DIR=/data/http-cache
JOBS_INLINE=true
SEED_PASSWORD=...                                             # private, ≥ 14 chars; share only with the team
# optional connector keys: DPLA_API_KEY, EUROPEANA_API_KEY, SMITHSONIAN_API_KEY, NYPL_API_TOKEN
```

Start command (one process): `uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 1`

### Frontend

```bash
API_URL=https://YOUR-BACKEND-HOST                              # server-side only; where /api/* is proxied
NEXT_PUBLIC_PRIVACY_CONTACT=privacy@YOUR-DOMAIN               # shown on /privacy
```

## Steps

1. **Database**: create the Postgres project (Canada region), run `CREATE EXTENSION IF NOT EXISTS vector;`.
2. **Backend**: create the service from the GitHub repo (`backend/` root), add the persistent disk at `/data`,
   set the environment above, deploy. It must start cleanly; if it refuses with "Unsafe production settings",
   fix the listed variables.
3. **Schema + data**: from the backend shell, `uv run alembic upgrade head` (`make migrate`; do **not** use
   `scripts/db.py`, which runs a local embedded Postgres), then `SEED_MAX_PER_QUERY=10 uv run python scripts/seed.py`
   (a few minutes; respects source rate limits).
   Load curated rows with `uv run python scripts/load_curated.py` if wanted.
4. **Frontend**: import the repo into Vercel with root `frontend/`, set `API_URL` and `NEXT_PUBLIC_PRIVACY_CONTACT`, deploy.
5. **Domain**: attach the domain to Vercel; set `CORS_ORIGINS` / `PUBLIC_BASE_URL` on the backend to it; redeploy the backend.
6. **Anthropic console**: set a monthly spend limit as a second guard behind `GUIDE_DAILY_LIMIT`.

## Launch checks (do all before sharing the link)

- [ ] `https://YOUR-DOMAIN/` loads; Nova animates; a question gets a cited answer.
- [ ] `/privacy` shows the contact email (EN and `/fr/privacy`).
- [ ] An upload URL from the partner app opens when signed in and returns **404 in a private window**.
- [ ] Sign-in with `hub-demo-2026` **fails**; `test@test.com` does **not** exist.
- [ ] 11 wrong passwords in a row → the 11th attempt answers 429.
- [ ] Response headers on `/api/partner/auth/login` set the cookie with `Secure; HttpOnly; SameSite=Lax`.
- [ ] Set `GUIDE_DAILY_LIMIT=1` temporarily: the second question shows the "answered as many questions as she can today"
      message with records listed; then restore 300.
- [ ] Vercel forwards the visitor IP: if every visitor shares one per-visitor bucket, the per-visitor cap will trip
      early — check the backend log / raise `GUIDE_DAILY_LIMIT_PER_VISITOR` accordingly (the global cap still holds).

## Known limits (acceptable for a public demo)

- Counters live in memory: a restart resets today's count (at worst one extra day's allowance).
- `X-Forwarded-For` can be spoofed if the backend URL is reachable directly; that only moves a visitor into another
  per-visitor bucket — the global daily cap is unaffected. Restricting the backend to the Vercel egress is a later step.
- Partner staff emails sit in `users` and `audit_log` (needed to operate the portal); they are not shown publicly.
