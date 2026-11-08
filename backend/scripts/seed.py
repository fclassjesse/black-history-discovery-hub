"""Seed: institutions (geocoded via Nominatim), partner logins, live connector ingestion, demo partner CSV.

  uv run python scripts/seed.py            # full seed
  uv run python scripts/seed.py --no-live  # skip live connectors (institutions, users, demo CSV only)
  uv run python scripts/seed.py --max 10   # cap records per source per query

Prints a connector table at the end. Never fakes a successful API call.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml
from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.adapters.base import all_adapters  # noqa: E402
from app.config import BACKEND_ROOT, get_settings  # noqa: E402
from app.db import session_factory  # noqa: E402
from app.models import ConnectorRun, Institution, Membership, Record, User  # noqa: E402
from app.security import hash_password  # noqa: E402
from app.services import geocode, imports as imports_svc  # noqa: E402
from app.services.http import BlockedError  # noqa: E402
from app.services.repository import upsert_record  # noqa: E402

FIXTURES = BACKEND_ROOT / "fixtures"
DEFAULT_DEMO_PASSWORD = "hub-demo-2026"
DEMO_PASSWORD = os.environ.get("SEED_PASSWORD", DEFAULT_DEMO_PASSWORD)
MIN_PROD_PASSWORD = 14
SEED_USERS = [
    ("bccns", "owner@bccns.example", "BCCNS Owner", "owner"),
    ("bccns", "editor@bccns.example", "BCCNS Editor", "editor"),
    ("bccns", "reviewer@bccns.example", "BCCNS Reviewer", "reviewer"),
    ("demo-partner", "owner@demo-partner.example", "Demo Partner Owner", "owner"),
    ("demo-partner", "editor@demo-partner.example", "Demo Partner Editor", "editor"),
    ("demo-partner", "reviewer@demo-partner.example", "Demo Partner Reviewer", "reviewer"),
]
# Easy login for live demos (owner of the demo partner). Local/demo data only — never seed this in production.
DEMO_QUICK_LOGIN = ("demo-partner", os.environ.get("DEMO_QUICK_EMAIL", "test@test.com"), "Demo Tester", "owner", os.environ.get("DEMO_QUICK_PASSWORD", "12345678"))
IA_FULL_TEXT_ITEMS_MAX = 12


async def seed_institutions(session) -> None:
    data = json.loads((FIXTURES / "institutions.json").read_text())
    for row in data:
        inst = (await session.execute(select(Institution).where(Institution.slug == row["slug"]))).scalar_one_or_none()
        created = inst is None
        inst = inst or Institution(slug=row["slug"], name=row["name"])
        for k in ("name", "kind", "description", "website_url", "catalogue_url", "address", "city", "region", "country", "access_requirements", "collection_summary", "partner_status"):
            if k in row:
                setattr(inst, k, row[k])
        if created and row.get("geocode_query") and inst.latitude is None:
            try:
                g = await geocode.geocode(row["geocode_query"])
            except Exception as e:  # noqa: BLE001
                g = None
                print(f"  [geocode] {row['slug']}: {type(e).__name__}: {e}")
            if g:
                inst.latitude, inst.longitude = g["latitude"], g["longitude"]
                inst.location_precision = row.get("force_precision") or g["precision"]
                inst.location_source = g["source"] + (f" — {row['geocode_note']}" if row.get("geocode_note") else "")
                print(f"  [geocode] {row['slug']}: {g['latitude']:.4f},{g['longitude']:.4f} ({inst.location_precision})")
            else:
                inst.location_precision = "unknown"
                print(f"  [geocode] {row['slug']}: no match → location unknown")
        session.add(inst)
    await session.commit()


async def seed_users(session) -> None:
    users = [(*u, DEMO_PASSWORD) for u in SEED_USERS]
    if not get_settings().is_production:
        users.append(DEMO_QUICK_LOGIN)  # the easy test@test.com login exists only on local/demo machines
    for slug, email, name, role, password in users:
        inst = (await session.execute(select(Institution).where(Institution.slug == slug))).scalar_one()
        user = (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()
        if user is None:
            user = User(email=email, display_name=name, password_hash=hash_password(password))
            session.add(user)
            await session.flush()
        m = (await session.execute(select(Membership).where(Membership.user_id == user.id, Membership.institution_id == inst.id))).scalar_one_or_none()
        if m is None:
            session.add(Membership(user_id=user.id, institution_id=inst.id, role=role))
    await session.commit()


async def run_connectors(session, max_per_query: int, only: str | None = None) -> list[dict]:
    cfg = yaml.safe_load((FIXTURES / "queries.yaml").read_text())
    queries: list[str] = cfg["queries"]
    summary: list[dict] = []
    for adapter in all_adapters():
        if only and adapter.name != only:
            continue
        st = await adapter.status()
        if st.state != "ok":
            session.add(ConnectorRun(source_system=adapter.name, query=None, finished_at=datetime.now(timezone.utc), status=st.state, error=st.detail))
            await session.commit()
            summary.append({"source": adapter.name, "status": st.state, "records": 0, "chunks": 0, "detail": st.detail})
            print(f"  [{adapter.name}] {st.state}: {st.detail}")
            continue
        total_upserted = 0
        total_created = 0
        total_chunks = 0
        full_text_items = 0
        for q in queries:
            run = ConnectorRun(source_system=adapter.name, query=q, status="running")
            session.add(run)
            await session.commit()
            run_id = run.id  # captured now: after a rollback the instance is expired and attribute access would need IO
            try:
                raws = await adapter.search(q, max_records=max_per_query)
                run.fetched = len(raws)
                run.request_url = raws[0].get("_provenance", {}).get("request_url") if raws else None
                for raw in raws:
                    rec = adapter.normalize(raw)
                    if adapter.name == "internet_archive" and full_text_items < IA_FULL_TEXT_ITEMS_MAX:
                        existing = (await session.execute(select(Record).where(Record.source_system == rec.source_system, Record.source_record_id == rec.source_record_id))).scalar_one_or_none()
                        if existing is None or not existing.has_full_text:
                            rec = await adapter.enrich(rec)
                            if rec.chunks:
                                full_text_items += 1
                                total_chunks += len(rec.chunks)
                    _, created = await upsert_record(session, rec)
                    run.upserted += 1
                    total_created += int(created)
                run.status = "ok"
                total_upserted += run.upserted
                print(f"  [{adapter.name}] '{q}': fetched {run.fetched}, upserted {run.upserted}")
            except BlockedError as e:
                run.status, run.error = "blocked", e.detail
                print(f"  [{adapter.name}] '{q}': BLOCKED {e.detail}")
            except Exception as e:  # noqa: BLE001
                await session.rollback()
                run = await session.get(ConnectorRun, run_id) or run
                run.status, run.error = "error", f"{type(e).__name__}: {e}"[:500]
                print(f"  [{adapter.name}] '{q}': ERROR {type(e).__name__}: {e}")
            run.finished_at = datetime.now(timezone.utc)
            await session.commit()
        summary.append({"source": adapter.name, "status": "ok", "records": total_created, "chunks": total_chunks, "detail": f"{total_upserted} rows fetched across queries (duplicates update the same record)" + (f"; {full_text_items} items with OCR pages" if total_chunks else "")})
    return summary


async def seed_demo_partner(session) -> dict:
    inst = (await session.execute(select(Institution).where(Institution.slug == "demo-partner"))).scalar_one()
    owner = (await session.execute(select(User).where(User.email == "owner@demo-partner.example"))).scalar_one()
    existing = (await session.execute(select(Record).where(Record.institution_id == inst.id))).scalars().first()
    if existing is not None:
        return {"skipped": "demo partner already has records"}
    csv_path = FIXTURES / "demo_partner_sample.csv"
    batch = await imports_svc.create_preview(session, institution=inst, user=owner, filename=csv_path.name, content=csv_path.read_bytes())
    out = await imports_svc.commit(session, batch, inst, owner, demo=True)
    rows = (await session.execute(select(Record).where(Record.institution_id == inst.id, Record.review_status == "draft"))).scalars()
    n = 0
    for r in rows:
        r.review_status = "published"
        n += 1
    await session.commit()
    return {"batch": str(batch.id), "rows": batch.row_count, "errors": batch.error_count, "duplicates": batch.duplicate_count, "published": n}


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-live", action="store_true")
    ap.add_argument("--max", type=int, default=int(os.environ.get("SEED_MAX_PER_QUERY", "40")))
    args = ap.parse_args()
    if get_settings().is_production and (DEMO_PASSWORD == DEFAULT_DEMO_PASSWORD or len(DEMO_PASSWORD) < MIN_PROD_PASSWORD):
        sys.exit(f"[seed] refusing to seed production: set SEED_PASSWORD to a private password of at least {MIN_PROD_PASSWORD} characters "
                 f"(the default {DEFAULT_DEMO_PASSWORD!r} is published in the public README)")
    async with session_factory()() as session:
        print("[seed] institutions")
        await seed_institutions(session)
        print("[seed] partner logins")
        await seed_users(session)
        summary = []
        if not args.no_live:
            print("[seed] live connectors")
            summary = await run_connectors(session, args.max)
        print("[seed] demo partner CSV")
        demo = await seed_demo_partner(session)
        print("  ", demo)
    print("\nConnector summary")
    print(f"  {'source':<18}{'status':<14}{'new recs':>8}{'chunks':>8}  detail")
    for s in summary:
        print(f"  {s['source']:<18}{s['status']:<14}{s['records']:>8}{s['chunks']:>8}  {s['detail'][:70]}")
    print(f"\nQuick demo login: {DEMO_QUICK_LOGIN[1]} / {DEMO_QUICK_LOGIN[4]}")
    print("Partner logins (password for all: %s)" % ("<SEED_PASSWORD from the environment>" if get_settings().is_production else DEMO_PASSWORD))
    for slug, email, _, role in SEED_USERS:
        print(f"  {slug:<14}{role:<10}{email}")


if __name__ == "__main__":
    asyncio.run(main())
