"""Tenant isolation, publish confirmation workflow, shelf-scan human confirmation, CSV preview via API."""
from __future__ import annotations

import io

import pytest
from sqlalchemy import select

from app.models import AuditLog, Record, ShelfScan, ShelfScanItem
from tests.conftest import login


async def _create_draft(client, inst_id, title="A draft record"):
    r = await client.post(f"/api/partner/institutions/{inst_id}/records", json={"title": title, "creators": ["Someone"], "date_text": "1990", "resource_type": "book", "access_type": "physical", "call_number": "X 1"})
    assert r.status_code == 200, r.text
    return r.json()


async def _public_ids(client, q=""):
    r = await client.get("/api/search", params={"q": q, "page_size": 100})
    assert r.status_code == 200
    return {x["id"] for x in r.json()["results"]}


# ---------------------------------------------------------------- tenant isolation
async def test_unauthenticated_requests_rejected(client, two_tenants):
    a = two_tenants["a"]
    assert (await client.get(f"/api/partner/institutions/{a.id}/records")).status_code == 401


async def test_editor_of_b_cannot_touch_a(client, two_tenants):
    a, b = two_tenants["a"], two_tenants["b"]
    await login(client, "editor@a.test")
    draft = await _create_draft(client, a.id)
    csv = io.BytesIO(b"title,creators\nX,Y\n")
    imp = await client.post(f"/api/partner/institutions/{a.id}/imports", files={"file": ("x.csv", csv, "text/csv")})
    assert imp.status_code == 200
    batch_id = imp.json()["id"]

    await client.post("/api/partner/auth/logout")
    await login(client, "editor@b.test")
    base = f"/api/partner/institutions/{a.id}"
    for method, path in [("GET", f"{base}/records"), ("GET", f"{base}/dashboard"), ("GET", f"{base}/profile"), ("GET", f"{base}/members"), ("GET", f"{base}/imports/{batch_id}"), ("GET", f"{base}/shelf-scans"), ("GET", f"{base}/audit")]:
        r = await client.request(method, path)
        assert r.status_code == 403, (path, r.status_code)
    assert (await client.patch(f"{base}/records/{draft['id']}", json={"title": "hacked"})).status_code == 403
    assert (await client.post(f"{base}/records/{draft['id']}/publish", json={})).status_code == 403
    assert (await client.post(f"{base}/imports/{batch_id}/commit", json={})).status_code == 403
    # B cannot reach A's record through B's own institution path either (404, not 200)
    assert (await client.get(f"/api/partner/institutions/{b.id}/records/{draft['id']}")).status_code == 404
    assert (await client.post(f"/api/partner/institutions/{b.id}/records/{draft['id']}/publish", json={})).status_code == 404
    assert (await client.get(f"/api/partner/institutions/{b.id}/imports/{batch_id}")).status_code == 404
    # and A's draft is untouched
    async with __import__("app.db", fromlist=["session_factory"]).session_factory()() as s:
        rec = await s.get(Record, __import__("uuid").UUID(draft["id"]))
        assert rec.title == "A draft record" and rec.review_status == "draft"


# ---------------------------------------------------------------- publish workflow
async def test_workflow_roles_and_public_index(client, two_tenants):
    a = two_tenants["a"]
    base = f"/api/partner/institutions/{a.id}"
    await login(client, "editor@a.test")
    draft = await _create_draft(client, a.id, "Workflow book about Preston")
    rid = draft["id"]
    assert draft["review_status"] == "draft"
    assert rid not in await _public_ids(client, "Preston")
    # editor may submit but not publish
    assert (await client.post(f"{base}/records/{rid}/publish", json={})).status_code == 403
    assert (await client.post(f"{base}/records/{rid}/submit", json={})).status_code == 200
    assert rid not in await _public_ids(client, "Preston")
    # reviewer publishes
    await client.post("/api/partner/auth/logout")
    await login(client, "reviewer@a.test")
    r = await client.post(f"{base}/records/{rid}/publish", json={"note": "looks right"})
    assert r.status_code == 200 and r.json()["review_status"] == "published"
    assert rid in await _public_ids(client, "Preston")
    assert (await client.get(f"/api/records/{rid}")).status_code == 200
    # withdraw → leaves public search and the public record page
    r = await client.post(f"{base}/records/{rid}/withdraw", json={})
    assert r.status_code == 200 and r.json()["review_status"] == "withdrawn"
    assert rid not in await _public_ids(client, "Preston")
    assert (await client.get(f"/api/records/{rid}")).status_code == 404
    # audit trail recorded every transition
    audit = (await client.get(f"{base}/audit")).json()["entries"]
    actions = [e["action"] for e in audit]
    assert "record.create" in actions and "record.submit" in actions and "record.publish" in actions and "record.withdraw" in actions
    # invalid transition
    assert (await client.post(f"{base}/records/{rid}/publish", json={})).status_code == 409


async def test_manual_verified_partner_requires_confirmation(client, two_tenants):
    a = two_tenants["a"]
    await login(client, "editor@a.test")
    base = f"/api/partner/institutions/{a.id}/records"
    r = await client.post(base, json={"title": "Held book", "holding_verification": "verified_partner"})
    assert r.status_code == 422 and "physically holds" in r.json()["detail"]
    r = await client.post(base, json={"title": "Held book", "holding_verification": "verified_partner", "confirm_holding": True})
    assert r.status_code == 200 and r.json()["holding_verification"] == "verified_partner"
    d = await _create_draft(client, a.id, "Unverified book")
    assert (await client.patch(f"{base}/{d['id']}", json={"holding_verification": "verified_partner"})).status_code == 422
    assert (await client.patch(f"{base}/{d['id']}", json={"holding_verification": "verified_partner", "confirm_holding": True})).status_code == 200


async def test_owner_can_publish_from_draft(client, two_tenants):
    a = two_tenants["a"]
    await login(client, "owner@a.test")
    d = await _create_draft(client, a.id, "Owner direct publish")
    r = await client.post(f"/api/partner/institutions/{a.id}/records/{d['id']}/publish", json={})
    assert r.status_code == 200 and r.json()["review_status"] == "published"


# ---------------------------------------------------------------- shelf scan confirmation
async def _seed_scan(session, inst, user):
    scan = ShelfScan(institution_id=inst.id, created_by=user.id, image_path="/tmp/none.jpg", image_mime="image/jpeg", status="proposed", model="fake")
    session.add(scan)
    await session.flush()
    item = ShelfScanItem(scan_id=scan.id, position=0, spine_text="BLACK LOYALISTS WHITEHEAD", proposed_title="Black Loyalists", proposed_author="Whitehead", confidence=0.8, uncertainties=["author partially hidden"],
                         candidates=[{"source": "openlibrary", "openlibrary_work_key": "/works/OL1", "openlibrary_url": "https://openlibrary.org/works/OL1", "title": "Black Loyalists", "authors": ["Ruth Holmes Whitehead"], "first_publish_year": 2013, "isbns": ["9781771080163"], "score": 0.9}])
    session.add(item)
    await session.commit()
    return scan, item


async def test_confirm_requires_checkbox_and_selection_and_yields_draft(client, session, two_tenants):
    a, editor = two_tenants["a"], two_tenants["a_editor"]
    scan, item = await _seed_scan(session, a, editor)
    await login(client, "editor@a.test")
    url = f"/api/partner/institutions/{a.id}/shelf-scans/{scan.id}/items/{item.id}/confirm"
    cand = item.candidates[0]
    # missing checkbox
    r = await client.post(url, json={"confirmed_holding": False, "selected_candidate": cand, "call_number": "F 1"})
    assert r.status_code == 422 and "physically holds" in r.json()["detail"]
    # checkbox but no selection and no manual title
    r = await client.post(url, json={"confirmed_holding": True, "selected_candidate": None, "manual_title": None})
    assert r.status_code == 422
    # nothing was created
    assert (await session.execute(select(Record))).scalars().first() is None
    # proper confirmation → DRAFT, not published
    r = await client.post(url, json={"confirmed_holding": True, "selected_candidate": cand, "call_number": "F 1039 .W55", "shelf_label": "A3", "edition_note": "2013 pbk"})
    assert r.status_code == 200, r.text
    rec = r.json()["record"]
    assert rec["review_status"] == "draft" and rec["holding_verification"] == "verified_partner" and rec["call_number"] == "F 1039 .W55"
    assert rec["title"] == "Black Loyalists" and rec["identifiers"]["openlibrary_work_key"] == "/works/OL1"
    assert rec["id"] not in await _public_ids(client, "Loyalists")
    # second confirm is refused
    assert (await client.post(url, json={"confirmed_holding": True, "selected_candidate": cand})).status_code == 409
    # another tenant cannot confirm items on A's scan
    await client.post("/api/partner/auth/logout")
    await login(client, "editor@b.test")
    assert (await client.post(url, json={"confirmed_holding": True, "selected_candidate": cand})).status_code == 403


async def test_shelf_scan_upload_without_vision_is_visible_error(client, two_tenants, monkeypatch):
    a = two_tenants["a"]
    monkeypatch.setenv("LLM_PROVIDER", "none")
    from app.config import get_settings

    get_settings.cache_clear()
    try:
        await login(client, "editor@a.test")
        r = await client.post(f"/api/partner/institutions/{a.id}/shelf-scans", files={"image": ("shelf.jpg", io.BytesIO(b"\xff\xd8\xff"), "image/jpeg")})
        assert r.status_code == 503 and "vision unconfigured" in r.json()["detail"]
    finally:
        get_settings.cache_clear()


async def test_shelf_scan_pipeline_with_fake_vision(client, two_tenants, fake_llm, monkeypatch):
    a = two_tenants["a"]
    fake_llm.push({"items": [{"spine_text": "BIRCHTOWN AND THE BLACK LOYALISTS TAYLOR", "title": "Birchtown and the Black Loyalists", "author": "Wanda Lauren Taylor", "isbn": None, "confidence": 0.85, "uncertainties": ["year not visible"]}], "notes": "ok"})

    async def fake_candidates(item):
        return [{"source": "openlibrary", "openlibrary_work_key": "/works/OLX", "openlibrary_url": "https://openlibrary.org/works/OLX", "title": item["title"], "authors": [item["author"]], "first_publish_year": 2014, "isbns": [], "score": 0.95}]

    monkeypatch.setattr("app.services.vision.candidates_for", fake_candidates)
    await login(client, "editor@a.test")
    r = await client.post(f"/api/partner/institutions/{a.id}/shelf-scans", files={"image": ("shelf.jpg", io.BytesIO(b"\xff\xd8\xff\xe0"), "image/jpeg")})
    assert r.status_code == 200, r.text
    scan = r.json()
    assert scan["status"] == "proposed" and len(scan["items"]) == 1
    it = scan["items"][0]
    assert it["status"] == "proposed" and it["candidates"][0]["score"] == 0.95 and it["uncertainties"] == ["year not visible"]
    # nothing auto-published
    assert await _public_ids(client, "Birchtown") == set()


# ---------------------------------------------------------------- imports via API
async def test_csv_import_preview_commit_and_review(client, two_tenants):
    a = two_tenants["a"]
    base = f"/api/partner/institutions/{a.id}"
    await login(client, "editor@a.test")
    csv = b"Title,Author,Year,URL\nGood book,Jane Doe,1990,https://x.org/1\n,Nobody,1991,https://x.org/2\nGood book,Jane Doe,1990,https://x.org/3\n"
    r = await client.post(f"{base}/imports", files={"file": ("import.csv", io.BytesIO(csv), "text/csv")})
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["row_count"] == 3 and b["error_count"] == 1 and b["duplicate_count"] == 1
    assert b["mapping"]["fields"]["title"] == "Title" and b["mapping"]["fields"]["original_url"] == "URL"
    # remap: unmap title → every row errors
    r = await client.put(f"{base}/imports/{b['id']}/mapping", json={"fields": {"title": None}})
    assert r.status_code == 200 and r.json()["error_count"] == 3
    r = await client.put(f"{base}/imports/{b['id']}/mapping", json={"fields": {"title": "Title"}})
    assert r.json()["error_count"] == 1
    r = await client.post(f"{base}/imports/{b['id']}/commit", json={"skip_duplicates": True})
    assert r.status_code == 200 and r.json()["created_drafts"] == 1 and len(r.json()["skipped"]) == 2
    drafts = (await client.get(f"{base}/records?status=draft")).json()["results"]
    assert len(drafts) == 1 and drafts[0]["title"] == "Good book" and drafts[0]["holding_verification"] == "unverified"
    assert await _public_ids(client, "Good book") == set()
    assert (await client.post(f"{base}/imports/{b['id']}/commit", json={})).status_code == 409


async def test_members_only_owner(client, two_tenants):
    a = two_tenants["a"]
    await login(client, "editor@a.test")
    assert (await client.post(f"/api/partner/institutions/{a.id}/members", json={"email": "new@a.test", "role": "editor", "password": "password123"})).status_code == 403
    await client.post("/api/partner/auth/logout")
    await login(client, "owner@a.test")
    assert (await client.post(f"/api/partner/institutions/{a.id}/members", json={"email": "new@a.test", "role": "editor", "password": "password123"})).status_code == 200
    await client.post("/api/partner/auth/logout")
    await login(client, "new@a.test")
    assert (await client.get(f"/api/partner/institutions/{a.id}/records")).status_code == 200


async def test_profile_location_verification_requires_owner(client, two_tenants):
    a = two_tenants["a"]
    base = f"/api/partner/institutions/{a.id}"
    await login(client, "editor@a.test")
    r = await client.put(f"{base}/profile", json={"latitude": 44.7, "longitude": -63.4})
    assert r.status_code == 200 and r.json()["location_precision"] == "building"
    assert (await client.put(f"{base}/profile", json={"verify_location": True})).status_code == 403
    await client.post("/api/partner/auth/logout")
    await login(client, "owner@a.test")
    r = await client.put(f"{base}/profile", json={"verify_location": True})
    assert r.status_code == 200 and r.json()["location_precision"] == "partner_verified"


@pytest.mark.parametrize("path", ["/api/search?q=test", "/api/institutions", "/api/status/sources"])
async def test_public_endpoints_need_no_auth(client, path):
    r = await client.get(path)
    assert r.status_code == 200
