"""Guards for a public deployment: uploaded-file access, daily AI-answer cap, login throttle,
production settings check and search-log retention."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select

from app.config import Settings, get_settings
from app.models import Record, SearchLog
from app.services import searchlog
from app.services.quota import AnswerQuota, login_throttle
from tests.conftest import login


def _write_upload(institution_id: uuid.UUID, name: str = "1a2b3c4d-shelf.jpg") -> str:
    folder = get_settings().upload_dir / str(institution_id)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / name).write_bytes(b"\xff\xd8\xff private shelf photo")
    return f"/api/files/{institution_id}/{name}"


# ---------------------------------------------------------------- uploaded files
async def test_unpublished_upload_is_members_only(client, two_tenants):
    url = _write_upload(two_tenants["a"].id)
    assert (await client.get(url)).status_code == 404  # anonymous
    await login(client, "editor@b.test")
    assert (await client.get(url)).status_code == 404  # member of another institution
    await login(client, "editor@a.test")
    r = await client.get(url)
    assert r.status_code == 200
    assert r.headers["cache-control"] == "private, no-store"


async def test_published_finding_aid_file_is_public(client, two_tenants, session):
    a = two_tenants["a"]
    url = _write_upload(a.id, "9f8e7d6c-finding-aid.pdf")
    session.add(Record(institution_id=a.id, title="Finding aid", original_url=url, digital_url=url, review_status="published", source_system="partner_pdf", source_record_id=str(uuid.uuid4()), resource_type="finding_aid", access_type="physical"))
    await session.commit()
    r = await client.get(url)
    assert r.status_code == 200
    assert r.headers["cache-control"].startswith("public")


async def test_file_names_cannot_escape_the_upload_folder(client, two_tenants):
    a = two_tenants["a"]
    await login(client, "editor@a.test")
    for bad in ("..%2F..%2F.env", "not-a-generated-name.jpg", "1a2b3c4d-..", "%2E%2E"):
        assert (await client.get(f"/api/files/{a.id}/{bad}")).status_code == 404, bad


# ---------------------------------------------------------------- daily AI-answer cap
def test_answer_quota_global_and_per_visitor(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "guide_daily_limit", 3)
    monkeypatch.setattr(s, "guide_daily_limit_per_visitor", 2)
    q = AnswerQuota()
    v1, v2 = q.visitor_key("203.0.113.1"), q.visitor_key("203.0.113.2")
    assert v1 != v2 and "203.0.113" not in v1  # only a salted hash is kept
    assert q.try_take(v1) and q.try_take(v1)
    assert not q.try_take(v1)  # per-visitor cap
    assert q.try_take(v2)
    assert not q.try_take(v2)  # global cap (3) reached
    assert q.usage()["answers"] == 3


def test_answer_quota_zero_means_unlimited(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "guide_daily_limit", 0)
    monkeypatch.setattr(s, "guide_daily_limit_per_visitor", 0)
    q = AnswerQuota()
    assert all(q.try_take("v") for _ in range(500))


# ---------------------------------------------------------------- login throttle
async def test_login_is_throttled_after_repeated_failures(client, two_tenants):
    login_throttle._fails.clear()
    for _ in range(10):
        r = await client.post("/api/partner/auth/login", json={"email": "owner@a.test", "password": "wrong-password"})
        assert r.status_code == 401
    r = await client.post("/api/partner/auth/login", json={"email": "owner@a.test", "password": "password123"})
    assert r.status_code == 429  # even the right password waits out the window
    login_throttle._fails.clear()


# ---------------------------------------------------------------- production settings
def test_production_refuses_dev_secrets():
    with pytest.raises(ValidationError, match="JWT_SECRET"):
        Settings(app_env="production", jwt_secret="dev-only-change-me", cookie_secure=True, cors_origins="https://hub.example", public_base_url="https://hub.example")
    with pytest.raises(ValidationError, match="COOKIE_SECURE"):
        Settings(app_env="production", jwt_secret="x" * 48, cookie_secure=False, cors_origins="https://hub.example", public_base_url="https://hub.example")
    ok = Settings(app_env="production", jwt_secret="x" * 48, cookie_secure=True, cors_origins="https://hub.example", public_base_url="https://hub.example")
    assert ok.is_production


# ---------------------------------------------------------------- search-log retention
async def test_search_log_older_than_retention_is_deleted(session, monkeypatch):
    monkeypatch.setattr(get_settings(), "search_log_retention_days", 30)
    old = datetime.now(timezone.utc) - timedelta(days=31)
    session.add_all([SearchLog(kind="search", query="old question", created_at=old), SearchLog(kind="search", query="new question")])
    await session.commit()
    assert await searchlog.prune_old() == 1
    left = (await session.execute(select(func.count()).select_from(SearchLog))).scalar_one()
    assert left == 1
