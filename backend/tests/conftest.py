"""Test harness: real embedded Postgres (bhdh_test database), fake embeddings, scripted fake LLM."""
from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator
from pathlib import Path

os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL", "postgresql://postgres@127.0.0.1:54329/bhdh_test")
os.environ["EMBEDDINGS_PROVIDER"] = "fake"
os.environ["LLM_PROVIDER"] = "fake"
os.environ["RERANKER"] = "none"
os.environ["GUIDE_CACHE_TTL_SECONDS"] = "0"
os.environ["JOBS_INLINE"] = "true"
os.environ["JOBS_INLINE_BACKGROUND"] = "false"
os.environ["JWT_SECRET"] = "test-secret"
os.environ["UPLOAD_DIR"] = str(Path(__file__).resolve().parent / ".uploads")

import pytest  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.db import Base, get_engine, reset_engine, session_factory  # noqa: E402
from app.models import SQL_HELPERS, Institution, Membership, User  # noqa: E402
from app.security import hash_password  # noqa: E402
from app.services.llm import set_provider_override  # noqa: E402
from app.services.llm.fake_provider import FakeProvider  # noqa: E402

get_settings.cache_clear()
reset_engine()

TABLES = ["search_log", "audit_log", "shelf_scan_items", "shelf_scans", "jobs", "connector_runs", "record_chunks", "records", "import_batches", "memberships", "users", "institutions"]


@pytest.fixture(scope="session", autouse=True)
async def _schema():
    engine = get_engine()
    async with engine.begin() as conn:
        for stmt in SQL_HELPERS:
            await conn.execute(text(stmt))
        # the test database persists between runs; rebuild it so model changes (new columns) always apply
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield


@pytest.fixture(autouse=True)
async def _clean():
    async with session_factory()() as s:
        await s.execute(text("TRUNCATE " + ", ".join(TABLES) + " CASCADE"))
        await s.commit()
    yield


@pytest.fixture
def fake_llm() -> FakeProvider:
    p = FakeProvider()
    set_provider_override(p)
    yield p
    set_provider_override(None)


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    from app.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.fixture
async def session():
    async with session_factory()() as s:
        yield s


async def make_institution(session, slug: str, name: str | None = None, **kw) -> Institution:
    inst = Institution(slug=slug, name=name or slug.title(), kind=kw.pop("kind", "archive"), **kw)
    session.add(inst)
    await session.flush()
    return inst


async def make_user(session, email: str, institution: Institution, role: str, password: str = "password123") -> User:
    u = User(email=email, display_name=email, password_hash=hash_password(password))
    session.add(u)
    await session.flush()
    session.add(Membership(user_id=u.id, institution_id=institution.id, role=role))
    await session.flush()
    return u


async def login(client: AsyncClient, email: str, password: str = "password123") -> None:
    r = await client.post("/api/partner/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text


@pytest.fixture
async def two_tenants(session):
    """Institution A (owner, editor, reviewer) and institution B (editor). Returns dict."""
    a = await make_institution(session, "inst-a", "Institution A", latitude=44.6, longitude=-63.5, location_precision="building")
    b = await make_institution(session, "inst-b", "Institution B")
    users = {
        "a_owner": await make_user(session, "owner@a.test", a, "owner"),
        "a_editor": await make_user(session, "editor@a.test", a, "editor"),
        "a_reviewer": await make_user(session, "reviewer@a.test", a, "reviewer"),
        "b_editor": await make_user(session, "editor@b.test", b, "editor"),
    }
    await session.commit()
    return {"a": a, "b": b, **users}


def uid() -> str:
    return str(uuid.uuid4())
