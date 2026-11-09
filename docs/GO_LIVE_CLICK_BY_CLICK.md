# Go live — click by click (Render only)

Written 2026-11-09. One service, one setup file. `render.yaml` in the repo tells Render to create:

| Piece | Render name | Plan | Cost / month |
|---|---|---|---|
| Database (Postgres 16 + pgvector) | `bhdh-db` | Basic 256 MB | ≈ US$6 |
| Backend (search, Nova, partner API) | `bhdh-api` | Standard, 2 GB + 1 GB disk | ≈ US$25 |
| Website | `bhdh-web` | Starter | ≈ US$7 |

Time: about 20 minutes, mostly waiting. You need: a credit card for Render, and the AI key from your local
`backend/.env`.

---

## Step 1 — Create everything (5 clicks)

1. Go to <https://dashboard.render.com> → sign in with **GitHub**.
2. Top right: **+ New** → **Blueprint**.
3. Find `black-history-discovery-hub` → **Connect**.
   (Not listed? Click **Configure GitHub**, give Render access to that repo, come back.)
4. **Blueprint Name:** `bhdh`. Render shows the 3 pieces from the table above. It asks for 3 values:
   - `ANTHROPIC_API_KEY` — paste your Anthropic key (or leave empty if you use OpenAI)
   - `OPENAI_API_KEY` — paste your OpenAI key (or leave empty if you use Anthropic)
   - `NEXT_PUBLIC_PRIVACY_CONTACT` — the email visitors write to about privacy
5. Click **Apply** (or **Deploy Blueprint**). Add a card if Render asks.

Wait about 10 minutes. On the dashboard, all three turn green (**Available** / **Live**).
If `bhdh-api` fails, open it → **Logs**, and send the last 20 lines to Claude.

---

## Step 2 — Load your data (1 command)

The new database is empty. This copies your 1,543 records from the laptop and sets a new partner password.

1. Render dashboard → **bhdh-db** → **Connect** (top right) → **External** tab → copy the
   **External Database URL**.
2. Make sure the app runs on your laptop (the local database must be on). Then in the VS Code terminal:
   ```bash
   cd "/Users/xsy/Desktop/RBC Hackthon"
   scripts/go_live_restore.sh "PASTE_EXTERNAL_DATABASE_URL_HERE"
   ```
3. It asks for a **new partner password** twice (at least 14 characters; nothing shows while you type).
   **Write it down.** It replaces `hub-demo-2026` and `test@test.com` for every live login, because those are
   public in the README.

It ends with `✓ Done` and `records on the live site: 1543`.
If it says `✗ The load did not finish`, send `backend/.cache/restore-errors.log` to Claude.

---

## Step 3 — Open the site

Render dashboard → **bhdh-web** → the address at the top, e.g. **`https://bhdh-web.onrender.com`**.
That is the link for the judges.

Check, on your phone with Wi-Fi off:

- [ ] Home page loads, Nova moves, the globe spins.
- [ ] Search **hockey** → Africville Sea-Sides; Nova answers with a numbered citation.
- [ ] `/fr` is French; `/privacy` shows your email.
- [ ] `/app` → sign in as `owner@demo-partner.example` with the **new** password → works.
- [ ] Same login with `hub-demo-2026` → fails (good).

---

## Step 4 — Spend limit (2 min, recommended)

The app stops at 300 Nova answers a day. Add a second guard at your AI provider:
Anthropic console → **Settings** → **Limits**, or OpenAI → **Settings** → **Limits** → set a monthly limit
(for example US$20).

---

## Good to know

- **Updates:** every `git push` to `main` rebuilds `bhdh-api` and `bhdh-web` by themselves (about 5 minutes).
  Records added on your laptop do not copy over — run Step 2 again on a fresh database.
- **Uploads:** PDFs and shelf photos uploaded on the laptop stay on the laptop. New uploads on the live site
  are kept on the `bhdh-api` disk.
- **Region:** Render has no Canadian region, so everything runs in Ohio (US East).
- **Do not** put the new partner password in the README — the repo is public.
- **Stop paying:** Render → each service → **Settings** → **Suspend** (or **Delete**). The database and disk
  are billed until deleted.
- The longer multi-host plan (Vercel + Supabase in Canada) is still described in `docs/DEPLOY.md`.
