# Partner import template and API

This document is the integration contract for partner institutions. Everything a partner can do in the portal is also
available as a JSON API (OpenAPI/Swagger at `http://localhost:8000/docs`, proxied at `http://localhost:3000/api-docs`).

## 1. Principles

- **You keep ownership.** The hub stores a *description* of each record plus a link to your original record (`original_url`). We never claim to own or digitize the material.
- **Nothing is public until a reviewer or owner publishes it.** Imports, manual entries, finding aids and shelf-scan confirmations all create **drafts**.
- **Tenant isolation is server-side.** Every partner endpoint is scoped by `/api/partner/institutions/{institution_id}/…` and checked against your membership. Other institutions' data returns `403`/`404`.
- **Audit trail.** Every create, edit, import, workflow transition and membership change is written to `audit_log` and visible on the dashboard.

## 2. Roles

| Role | Can |
|---|---|
| `owner` | everything below + manage members, verify the map location |
| `editor` | create/edit records, import CSV/JSON/PDF, use the shelf camera, submit for review, reopen withdrawn |
| `reviewer` | all editor actions + publish, return to draft, withdraw |

Workflow: `draft → in_review → published → withdrawn` (`reopen` returns a withdrawn record to draft). Owners and reviewers may publish directly from draft.

## 3. CSV / JSON import template

Template file: [`partner-import-template.csv`](partner-import-template.csv) (also served at `/partner-import-template.csv`). Only `title` is required.
Headers are matched by synonym (e.g. `Author` → `creators`, `Year` → `date`, `Record URL` → `original_url`); the preview lets you fix the mapping.

| Canonical field | Type / format | Notes |
|---|---|---|
| `title` | text | **required** |
| `creators` | `;`-separated | people or organisations |
| `description` | text | scope and content |
| `subjects` | `;`-separated | people, places, communities, topics |
| `date` | free text | a year or range is extracted when possible (`1983`, `c. 1920`, `1990-2005`) |
| `resource_type` | one of `book, serial, manuscript, archival_collection, image, map, audio, video, dataset, finding_aid, artifact, other` | unknown values become `other` with a warning |
| `language` | `;`-separated codes | `en`, `fr`, `mic` … |
| `identifiers` | `key:value; key:value` or JSON | e.g. `isbn:978…; accession:1983.12.4` |
| `original_url` | `http(s)://…` | **your** catalogue entry; defaults to your institution's catalogue URL |
| `digital_url` | URL | only if the item is viewable online |
| `rights` | text | rights statement as you publish it |
| `access_type` | `online`, `physical`, `both`, `unknown` | default: `both` if a digital URL exists, else `physical` |
| `access_note` | text | how the public consults the item |
| `call_number` | text | shown on result cards and map cards |
| `shelf_label` | text | shelf / box / room |
| `source_record_id` | text | your stable id; re-importing the same id updates the record |

JSON uploads: an array of objects with the same keys, or `{"records": [...]}`.

**Preview flags** — `errors` (row is skipped): missing title, malformed URL, invalid access_type. `warnings`: unparseable date, unknown resource type. `duplicate_of`: same normalised title + first creator surname + year as another row (`row N`) or as an existing record in your institution; duplicates are skipped by default (`skip_duplicates=false` imports them anyway).

## 4. Endpoints (all require the session cookie from `POST /api/partner/auth/login`)

Base: `/api/partner/institutions/{institution_id}`

| Method & path | Purpose |
|---|---|
| `GET /dashboard` | counts by status, imports, scans, jobs, recent audit, sync status |
| `GET /audit?limit=` | full audit trail |
| `GET /profile` · `PUT /profile` | profile; body may include `latitude`, `longitude`, `verify_location` (owner only → `partner_verified`) |
| `GET /members` · `POST /members` · `DELETE /members/{membership_id}` | owner only for writes |
| `GET /records?status=&q=&page=` | list records in any status |
| `POST /records` | manual entry → draft (`holding_verification: "verified_partner"` requires `confirm_holding: true`) |
| `GET /records/{id}` · `PATCH /records/{id}` | read / edit |
| `POST /records/{id}/{submit\|return\|publish\|withdraw\|reopen}` | workflow transition (role-checked, audited) |
| `GET /imports` · `POST /imports` (multipart `file`) | list / upload → preview batch |
| `GET /imports/{batch_id}` | preview rows with flags |
| `PUT /imports/{batch_id}/mapping` `{fields: {canonical: header\|null}}` | re-map and re-validate |
| `POST /imports/{batch_id}/commit` `{skip_duplicates: true}` | create drafts |
| `POST /finding-aids` (multipart `file`, `title`, `description`, `original_url`) | PDF → draft `finding_aid` record with page chunks |
| `GET /shelf-scans` · `POST /shelf-scans` (multipart `image`) | upload a shelf photo → vision proposals + Open Library candidates (`503 vision unconfigured` without an AI key) |
| `GET /shelf-scans/{scan_id}` | items with candidates, confidence, uncertainties |
| `PATCH /shelf-scans/{scan_id}/items/{item_id}` | edit read fields, `refresh_candidates: true` |
| `POST /shelf-scans/{scan_id}/items/{item_id}/confirm` | **requires** `confirmed_holding: true` and either `selected_candidate` or `manual_title`; creates a draft |
| `POST /shelf-scans/{scan_id}/items/{item_id}/reject` | mark as not a book |

Uploaded files (finding-aid PDFs, shelf photos) are served publicly from `/api/files/{institution_id}/{name}` in this prototype.

Public, read-only: `GET /api/search`, `GET /api/records/{id}`, `GET /api/institutions`, `GET /api/institutions/{slug}/records`, `POST /api/guide/ask`, `GET /api/status/sources`.

### Example: upload and commit a CSV with curl

```bash
curl -c jar -X POST http://localhost:8000/api/partner/auth/login -H 'Content-Type: application/json' \
  -d '{"email":"editor@bccns.example","password":"hub-demo-2026"}'
INST=$(curl -s -b jar http://localhost:8000/api/partner/auth/me | python3 -c 'import json,sys;print(json.load(sys.stdin)["memberships"][0]["institution_id"])')
curl -b jar -F file=@docs/partner-import-template.csv http://localhost:8000/api/partner/institutions/$INST/imports     # → preview (note the batch id)
curl -b jar -X POST -H 'Content-Type: application/json' -d '{"skip_duplicates":true}' \
  http://localhost:8000/api/partner/institutions/$INST/imports/<batch_id>/commit                                     # → drafts
```

## 5. Automated sync (later)

The same endpoints can be called by a scheduled job on your side (CSV/JSON export → `POST /imports` → `commit`). Standards-based harvesting (OAI-PMH, MARC21, EAD) is on the roadmap and will reuse the same normalisation and review pipeline.
