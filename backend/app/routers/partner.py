"""Partner portal API. Every route is scoped by /institutions/{institution_id} and guarded by `tenant`
(server-side membership check). Roles: owner | editor | reviewer."""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.adapters import pdf_finding_aid
from app.adapters.base import NormalizedRecord
from app.config import get_settings
from app.db import get_session
from app.models import AuditLog, ImportBatch, Institution, Job, Membership, Record, ShelfScan, ShelfScanItem, User
from app.security import Tenant, hash_password, tenant
from app.services import audit, imports as imports_svc, jobs, publish
from app.services import shelf_jobs  # noqa: F401  (registers job handler)
from app.services.cards import institution_card, record_card
from app.services.normalize import RESOURCE_TYPES, parse_year_range
from app.services.repository import upsert_record

router = APIRouter(prefix="/api/partner/institutions/{institution_id}", tags=["partner"])
SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


async def _inst(session: AsyncSession, t: Tenant) -> Institution:
    inst = await session.get(Institution, t.institution_id)
    if inst is None:
        raise HTTPException(404, "Institution not found")
    return inst


async def _reload(session: AsyncSession, record_id: uuid.UUID) -> Record:
    return (await session.execute(select(Record).options(selectinload(Record.institution)).where(Record.id == record_id))).scalar_one()


async def _record(session: AsyncSession, t: Tenant, record_id: uuid.UUID) -> Record:
    r = (await session.execute(select(Record).options(selectinload(Record.institution)).where(Record.id == record_id, Record.institution_id == t.institution_id))).scalar_one_or_none()
    if r is None:
        raise HTTPException(404, "Record not found in this institution")
    return r


def _save_upload(institution_id: uuid.UUID, filename: str, content: bytes) -> tuple[Path, str]:
    s = get_settings()
    folder = s.upload_dir / str(institution_id)
    folder.mkdir(parents=True, exist_ok=True)
    safe = SAFE_NAME.sub("_", filename)[:120] or "file"
    name = f"{uuid.uuid4().hex[:8]}-{safe}"
    path = folder / name
    path.write_bytes(content)
    return path, f"/api/files/{institution_id}/{name}"


# --- dashboard -------------------------------------------------------------
@router.get("/dashboard")
async def dashboard(t: Tenant = Depends(tenant), session: AsyncSession = Depends(get_session)) -> dict:
    inst = await _inst(session, t)
    by_status = dict((await session.execute(select(Record.review_status, func.count()).where(Record.institution_id == inst.id).group_by(Record.review_status))).all())
    batches = (await session.execute(select(ImportBatch).where(ImportBatch.institution_id == inst.id).order_by(ImportBatch.created_at.desc()).limit(8))).scalars()
    scans = (await session.execute(select(ShelfScan).where(ShelfScan.institution_id == inst.id).order_by(ShelfScan.created_at.desc()).limit(8))).scalars()
    recent = (await session.execute(select(AuditLog).where(AuditLog.institution_id == inst.id).order_by(AuditLog.at.desc()).limit(12))).scalars()
    jobs_rows = (await session.execute(select(Job).order_by(Job.created_at.desc()).limit(20))).scalars()
    my_jobs = [j for j in jobs_rows if str(j.payload.get("institution_id")) == str(inst.id)]
    return {
        "institution": institution_card(inst),
        "role": t.role,
        "records_by_status": {s: by_status.get(s, 0) for s in ("draft", "in_review", "published", "withdrawn")},
        "import_batches": [imports_svc.batch_card(b) for b in batches],
        "shelf_scans": [_scan_card(s, items=False) for s in scans],
        "jobs": [{"id": str(j.id), "kind": j.kind, "status": j.status, "error": (j.error or "")[-300:] or None, "created_at": j.created_at.isoformat()} for j in my_jobs[:8]],
        "recent_audit": [_audit_card(a) for a in recent],
        "sync": {"mode": "manual uploads (CSV/JSON/PDF/photo) + API", "api_docs": "/docs", "last_import": next((b.created_at.isoformat() for b in await _latest_batches(session, inst.id)), None)},
    }


async def _latest_batches(session: AsyncSession, inst_id: uuid.UUID) -> list[ImportBatch]:
    return list((await session.execute(select(ImportBatch).where(ImportBatch.institution_id == inst_id, ImportBatch.status == "committed").order_by(ImportBatch.created_at.desc()).limit(1))).scalars())


def _audit_card(a: AuditLog) -> dict:
    return {"id": str(a.id), "at": a.at.isoformat(), "actor": a.actor_label, "action": a.action, "entity_type": a.entity_type, "entity_id": a.entity_id, "before": a.before, "after": a.after}


@router.get("/audit")
async def audit_log(limit: int = Query(50, le=200), t: Tenant = Depends(tenant), session: AsyncSession = Depends(get_session)) -> dict:
    rows = (await session.execute(select(AuditLog).where(AuditLog.institution_id == t.institution_id).order_by(AuditLog.at.desc()).limit(limit))).scalars()
    return {"entries": [_audit_card(a) for a in rows]}


# --- profile ---------------------------------------------------------------
class ProfileIn(BaseModel):
    name: str | None = Field(None, max_length=200)
    kind: str | None = None
    description: str | None = None
    website_url: str | None = None
    catalogue_url: str | None = None
    address: str | None = None
    city: str | None = None
    region: str | None = None
    country: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    access_requirements: str | None = None
    collection_summary: str | None = None
    latitude: float | None = Field(None, ge=-90, le=90)
    longitude: float | None = Field(None, ge=-180, le=180)
    verify_location: bool = False


@router.get("/profile")
async def get_profile(t: Tenant = Depends(tenant), session: AsyncSession = Depends(get_session)) -> dict:
    return {**institution_card(await _inst(session, t)), "role": t.role}


@router.put("/profile")
async def update_profile(body: ProfileIn, t: Tenant = Depends(tenant), session: AsyncSession = Depends(get_session)) -> dict:
    t.require("owner", "editor")
    inst = await _inst(session, t)
    before = institution_card(inst)
    for k, v in body.model_dump(exclude_unset=True, exclude={"verify_location", "latitude", "longitude"}).items():
        setattr(inst, k, v)
    coords_changed = False
    if "latitude" in body.model_fields_set or "longitude" in body.model_fields_set:
        if (body.latitude is None) != (body.longitude is None):
            raise HTTPException(400, "Provide both latitude and longitude, or neither")
        inst.latitude, inst.longitude = body.latitude, body.longitude
        coords_changed = True
        if body.latitude is None:
            inst.location_precision = "unknown"
            inst.location_source = None
    if body.verify_location:
        t.require("owner")
        if inst.latitude is None:
            raise HTTPException(400, "Set coordinates before verifying the location")
        inst.location_precision = "partner_verified"
        inst.location_source = f"Verified by {t.user.email} on {datetime.now(timezone.utc).date().isoformat()}"
        inst.location_verified_by = t.user.id
        inst.location_verified_at = datetime.now(timezone.utc)
    elif coords_changed and inst.location_precision == "partner_verified":
        inst.location_precision = "building"
        inst.location_source = f"Coordinates edited by {t.user.email} (not yet re-verified by an owner)"
    if inst.partner_status == "link_only":
        inst.partner_status = "partner"
    await session.flush()
    await audit.log(session, institution_id=inst.id, actor=t.user, action="profile.update", entity_type="institution", entity_id=inst.id, before=before, after=institution_card(inst))
    await session.commit()
    return {**institution_card(inst), "role": t.role}


# --- members ---------------------------------------------------------------
class MemberIn(BaseModel):
    email: str
    display_name: str = ""
    role: str = Field(pattern="^(owner|editor|reviewer)$")
    password: str | None = Field(None, min_length=8)


@router.get("/members")
async def members(t: Tenant = Depends(tenant), session: AsyncSession = Depends(get_session)) -> dict:
    rows = (await session.execute(select(Membership).options(selectinload(Membership.user)).where(Membership.institution_id == t.institution_id))).scalars()
    return {"members": [{"id": str(m.id), "user_id": str(m.user.id), "email": m.user.email, "display_name": m.user.display_name, "role": m.role} for m in rows], "role": t.role}


@router.post("/members")
async def add_member(body: MemberIn, t: Tenant = Depends(tenant), session: AsyncSession = Depends(get_session)) -> dict:
    t.require("owner")
    email = body.email.strip().lower()
    user = (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if user is None:
        if not body.password:
            raise HTTPException(400, "New user: a password (≥ 8 characters) is required")
        user = User(email=email, display_name=body.display_name or email.split("@")[0], password_hash=hash_password(body.password))
        session.add(user)
        await session.flush()
    m = (await session.execute(select(Membership).where(Membership.user_id == user.id, Membership.institution_id == t.institution_id))).scalar_one_or_none()
    before = {"role": m.role} if m else None
    if m is None:
        m = Membership(user_id=user.id, institution_id=t.institution_id, role=body.role)
        session.add(m)
    else:
        m.role = body.role
    await session.flush()
    await audit.log(session, institution_id=t.institution_id, actor=t.user, action="member.upsert", entity_type="membership", entity_id=m.id, before=before, after={"email": email, "role": body.role})
    await session.commit()
    return {"id": str(m.id), "email": email, "role": m.role}


@router.delete("/members/{membership_id}")
async def remove_member(membership_id: uuid.UUID, t: Tenant = Depends(tenant), session: AsyncSession = Depends(get_session)) -> dict:
    t.require("owner")
    m = (await session.execute(select(Membership).where(Membership.id == membership_id, Membership.institution_id == t.institution_id))).scalar_one_or_none()
    if m is None:
        raise HTTPException(404, "Membership not found")
    if m.user_id == t.user.id:
        raise HTTPException(400, "You cannot remove yourself")
    await audit.log(session, institution_id=t.institution_id, actor=t.user, action="member.remove", entity_type="membership", entity_id=m.id, before={"user_id": str(m.user_id), "role": m.role})
    await session.delete(m)
    await session.commit()
    return {"ok": True}


# --- records ---------------------------------------------------------------
class RecordIn(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    creators: list[str] = []
    description: str | None = None
    subjects: list[str] = []
    date_text: str | None = None
    resource_type: str = "other"
    language: list[str] = []
    identifiers: dict[str, Any] = {}
    original_url: str | None = None
    digital_url: str | None = None
    rights: str | None = None
    access_type: str = Field("physical", pattern="^(online|physical|both|unknown)$")
    access_note: str | None = None
    call_number: str | None = None
    shelf_label: str | None = None
    holding_verification: str | None = Field(None, pattern="^(verified_partner|unverified)$")
    confirm_holding: bool = False  # must be true to set holding_verification=verified_partner


def _check_holding_confirmation(holding_verification: str | None, confirm: bool) -> None:
    if holding_verification == "verified_partner" and not confirm:
        raise HTTPException(422, "To mark a holding as partner-verified you must confirm that your institution physically holds this item (confirm_holding=true)")


@router.get("/records")
async def list_records(status: str | None = None, q: str | None = None, page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100), t: Tenant = Depends(tenant), session: AsyncSession = Depends(get_session)) -> dict:
    stmt = select(Record).options(selectinload(Record.institution)).where(Record.institution_id == t.institution_id)
    if status:
        stmt = stmt.where(Record.review_status == status)
    if q:
        stmt = stmt.where(Record.title.ilike(f"%{q}%"))
    total = (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    rows = (await session.execute(stmt.order_by(Record.updated_at.desc()).offset((page - 1) * page_size).limit(page_size))).scalars()
    return {"total": total, "page": page, "page_size": page_size, "role": t.role, "results": [record_card(r) for r in rows], "actions": {a: publish.can(t.role, a) for a in publish.TRANSITIONS}}


@router.post("/records")
async def create_record(body: RecordIn, t: Tenant = Depends(tenant), session: AsyncSession = Depends(get_session)) -> dict:
    t.require("owner", "editor", "reviewer")
    _check_holding_confirmation(body.holding_verification, body.confirm_holding)
    inst = await _inst(session, t)
    ds, de = parse_year_range(body.date_text)
    rec = NormalizedRecord(
        source_system=f"partner:{inst.slug}", source_record_id=f"manual:{uuid.uuid4()}", title=body.title.strip(), creators=body.creators, description=body.description,
        subjects=body.subjects, date_text=body.date_text, date_start=ds, date_end=de, resource_type=body.resource_type if body.resource_type in RESOURCE_TYPES else "other",
        language=body.language, identifiers=body.identifiers, original_url=body.original_url or inst.catalogue_url or inst.website_url or f"/institutions/{inst.slug}",
        digital_url=body.digital_url, rights=body.rights, access_type=body.access_type, access_note=body.access_note,
        holding_verification=body.holding_verification or "unverified", call_number=body.call_number, shelf_label=body.shelf_label,
        raw_metadata={"entry": "manual", "holding_confirmed_by": t.user.email if body.confirm_holding else None}, provenance={"adapter": "manual_entry", "created_by": t.user.email, "created_at": datetime.now(timezone.utc).isoformat()}, review_status="draft",
    )
    r, _ = await upsert_record(session, rec, institution_id=inst.id)
    await audit.log(session, institution_id=inst.id, actor=t.user, action="record.create", entity_type="record", entity_id=r.id, after=publish.record_snapshot(r))
    await session.commit()
    return record_card(await _reload(session, r.id))


@router.get("/records/{record_id}")
async def get_partner_record(record_id: uuid.UUID, t: Tenant = Depends(tenant), session: AsyncSession = Depends(get_session)) -> dict:
    r = await _record(session, t, record_id)
    return {**record_card(r), "raw_metadata": r.raw_metadata, "actions": {a: publish.can(t.role, a) and r.review_status in publish.TRANSITIONS[a][0] for a in publish.TRANSITIONS}}


class RecordPatch(BaseModel):
    title: str | None = None
    creators: list[str] | None = None
    description: str | None = None
    subjects: list[str] | None = None
    date_text: str | None = None
    resource_type: str | None = None
    language: list[str] | None = None
    original_url: str | None = None
    digital_url: str | None = None
    rights: str | None = None
    access_type: str | None = Field(None, pattern="^(online|physical|both|unknown)$")
    access_note: str | None = None
    call_number: str | None = None
    shelf_label: str | None = None
    holding_verification: str | None = Field(None, pattern="^(verified_partner|unverified|demo)$")
    confirm_holding: bool = False


@router.patch("/records/{record_id}")
async def patch_record(record_id: uuid.UUID, body: RecordPatch, t: Tenant = Depends(tenant), session: AsyncSession = Depends(get_session)) -> dict:
    r = await _record(session, t, record_id)
    changes = body.model_dump(exclude_unset=True, exclude={"confirm_holding"})
    if changes.get("holding_verification") == "verified_partner" and r.holding_verification != "verified_partner":
        _check_holding_confirmation("verified_partner", body.confirm_holding)
    if "date_text" in changes:
        changes["date_start"], changes["date_end"] = parse_year_range(changes["date_text"])
    if "resource_type" in changes and changes["resource_type"] not in RESOURCE_TYPES:
        changes["resource_type"] = "other"
    await publish.edit(session, r, changes, t)
    await session.commit()
    return record_card(await _reload(session, r.id))


class ActionIn(BaseModel):
    note: str | None = None


@router.post("/records/{record_id}/{action}")
async def record_action(record_id: uuid.UUID, action: str, body: ActionIn | None = None, t: Tenant = Depends(tenant), session: AsyncSession = Depends(get_session)) -> dict:
    r = await _record(session, t, record_id)
    await publish.transition(session, r, action, t, body.note if body else None)
    await session.commit()
    return record_card(await _reload(session, r.id))


# --- imports ---------------------------------------------------------------
@router.get("/imports")
async def list_imports(t: Tenant = Depends(tenant), session: AsyncSession = Depends(get_session)) -> dict:
    rows = (await session.execute(select(ImportBatch).where(ImportBatch.institution_id == t.institution_id).order_by(ImportBatch.created_at.desc()).limit(50))).scalars()
    return {"batches": [imports_svc.batch_card(b) for b in rows]}


@router.post("/imports")
async def create_import(file: UploadFile = File(...), t: Tenant = Depends(tenant), session: AsyncSession = Depends(get_session)) -> dict:
    t.require("owner", "editor", "reviewer")
    inst = await _inst(session, t)
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(413, "File too large (10 MB max)")
    batch = await imports_svc.create_preview(session, institution=inst, user=t.user, filename=file.filename or "upload.csv", content=content)
    await session.commit()
    return imports_svc.batch_card(batch, include_preview=True)


@router.get("/imports/{batch_id}")
async def get_import(batch_id: uuid.UUID, t: Tenant = Depends(tenant), session: AsyncSession = Depends(get_session)) -> dict:
    b = await _batch(session, t, batch_id)
    return imports_svc.batch_card(b, include_preview=True)


async def _batch(session: AsyncSession, t: Tenant, batch_id: uuid.UUID) -> ImportBatch:
    b = (await session.execute(select(ImportBatch).where(ImportBatch.id == batch_id, ImportBatch.institution_id == t.institution_id))).scalar_one_or_none()
    if b is None:
        raise HTTPException(404, "Import batch not found in this institution")
    return b


class MappingIn(BaseModel):
    fields: dict[str, str | None]


@router.put("/imports/{batch_id}/mapping")
async def update_mapping(batch_id: uuid.UUID, body: MappingIn, t: Tenant = Depends(tenant), session: AsyncSession = Depends(get_session)) -> dict:
    t.require("owner", "editor", "reviewer")
    b = await _batch(session, t, batch_id)
    if b.status != "preview":
        raise HTTPException(409, "Mapping can only change while the batch is in preview")
    await imports_svc.remap(session, b, await _inst(session, t), body.fields)
    await session.commit()
    return imports_svc.batch_card(b, include_preview=True)


class CommitIn(BaseModel):
    skip_duplicates: bool = True


@router.post("/imports/{batch_id}/commit")
async def commit_import(batch_id: uuid.UUID, body: CommitIn | None = None, t: Tenant = Depends(tenant), session: AsyncSession = Depends(get_session)) -> dict:
    t.require("owner", "editor", "reviewer")
    b = await _batch(session, t, batch_id)
    inst = await _inst(session, t)
    out = await imports_svc.commit(session, b, inst, t.user, skip_duplicates=(body.skip_duplicates if body else True), demo=(inst.partner_status == "demo"))
    await session.commit()
    return out


# --- finding aids ----------------------------------------------------------
@router.post("/finding-aids")
async def upload_finding_aid(file: UploadFile = File(...), title: str | None = Form(None), description: str | None = Form(None), original_url: str | None = Form(None), t: Tenant = Depends(tenant), session: AsyncSession = Depends(get_session)) -> dict:
    t.require("owner", "editor", "reviewer")
    inst = await _inst(session, t)
    content = await file.read()
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(400, "Upload a PDF finding aid")
    if len(content) > 25 * 1024 * 1024:
        raise HTTPException(413, "File too large (25 MB max)")
    path, public_url = _save_upload(inst.id, file.filename or "finding-aid.pdf", content)
    batch = ImportBatch(institution_id=inst.id, created_by=t.user.id, kind="pdf", filename=file.filename, status="committed", row_count=1)
    session.add(batch)
    await session.flush()
    try:
        rec = pdf_finding_aid.build_record(filename=file.filename or "finding-aid.pdf", content=content, institution_slug=inst.slug, title=title, description=description, original_url=original_url, batch_id=str(batch.id), actor=t.user.email, public_file_url=public_url)
    except Exception as e:  # noqa: BLE001
        batch.status = "failed"
        batch.error = f"{type(e).__name__}: {e}"
        await session.commit()
        raise HTTPException(400, f"Could not read PDF: {e}") from e
    r, _ = await upsert_record(session, rec, institution_id=inst.id)
    batch.committed_count = 1
    await audit.log(session, institution_id=inst.id, actor=t.user, action="finding_aid.upload", entity_type="record", entity_id=r.id, after={"filename": file.filename, "pages": rec.identifiers.get("pages"), "chunks": len(rec.chunks)})
    await session.commit()
    r = await _reload(session, r.id)
    return {**record_card(r), "pages": rec.identifiers.get("pages"), "chunks": len(rec.chunks), "file_url": public_url}


# --- shelf scans -----------------------------------------------------------
def _item_card(i: ShelfScanItem) -> dict:
    return {
        "id": str(i.id), "position": i.position, "spine_text": i.spine_text, "proposed_title": i.proposed_title, "proposed_author": i.proposed_author,
        "proposed_isbn": i.proposed_isbn, "confidence": i.confidence, "uncertainties": i.uncertainties, "candidates": i.candidates,
        "selected_candidate": i.selected_candidate, "call_number": i.call_number, "shelf_label": i.shelf_label, "confirmed_holding": i.confirmed_holding,
        "status": i.status, "record_id": str(i.record_id) if i.record_id else None,
    }


def _scan_card(s: ShelfScan, items: bool = True) -> dict:
    d = {"id": str(s.id), "status": s.status, "model": s.model, "error": s.error, "created_at": s.created_at.isoformat(), "image_url": f"/api/files/{s.institution_id}/{Path(s.image_path).name}"}
    if items:
        d["items"] = [_item_card(i) for i in s.items]
    return d


async def _scan(session: AsyncSession, t: Tenant, scan_id: uuid.UUID) -> ShelfScan:
    s = (await session.execute(select(ShelfScan).options(selectinload(ShelfScan.items)).where(ShelfScan.id == scan_id, ShelfScan.institution_id == t.institution_id))).scalar_one_or_none()
    if s is None:
        raise HTTPException(404, "Shelf scan not found in this institution")
    return s


@router.get("/shelf-scans")
async def list_scans(t: Tenant = Depends(tenant), session: AsyncSession = Depends(get_session)) -> dict:
    rows = (await session.execute(select(ShelfScan).options(selectinload(ShelfScan.items)).where(ShelfScan.institution_id == t.institution_id).order_by(ShelfScan.created_at.desc()).limit(30))).scalars()
    return {"scans": [_scan_card(s) for s in rows]}


@router.post("/shelf-scans")
async def create_scan(image: UploadFile = File(...), t: Tenant = Depends(tenant), session: AsyncSession = Depends(get_session)) -> dict:
    t.require("owner", "editor", "reviewer")
    from app.services.llm import provider_info

    if not provider_info()["configured"]:
        raise HTTPException(503, "vision unconfigured: set OPENAI_API_KEY (PRD default) or ANTHROPIC_API_KEY to enable shelf-photo reading.")
    content = await image.read()
    mime = image.content_type or "image/jpeg"
    if not mime.startswith("image/"):
        raise HTTPException(400, "Upload an image (JPEG/PNG/WebP)")
    if len(content) > 15 * 1024 * 1024:
        raise HTTPException(413, "Image too large (15 MB max)")
    path, _ = _save_upload(t.institution_id, image.filename or "shelf.jpg", content)
    scan = ShelfScan(institution_id=t.institution_id, created_by=t.user.id, image_path=str(path), image_mime=mime, status="queued")
    session.add(scan)
    await session.flush()
    job = await jobs.enqueue(session, "shelf_scan", {"scan_id": str(scan.id), "institution_id": str(t.institution_id)})
    await audit.log(session, institution_id=t.institution_id, actor=t.user, action="shelf_scan.create", entity_type="shelf_scan", entity_id=scan.id, after={"filename": image.filename})
    scan_id, job_id = scan.id, job.id
    await session.commit()
    await jobs.maybe_run_inline(job)
    session.expire_all()
    s = await _scan(session, t, scan_id)
    return {**_scan_card(s), "job_id": str(job_id)}


@router.get("/shelf-scans/{scan_id}")
async def get_scan(scan_id: uuid.UUID, t: Tenant = Depends(tenant), session: AsyncSession = Depends(get_session)) -> dict:
    return _scan_card(await _scan(session, t, scan_id))


class ItemPatch(BaseModel):
    proposed_title: str | None = None
    proposed_author: str | None = None
    proposed_isbn: str | None = None
    selected_candidate: dict[str, Any] | None = None  # {} / None = "none of these"
    call_number: str | None = None
    shelf_label: str | None = None
    confirmed_holding: bool | None = None
    refresh_candidates: bool = False


@router.patch("/shelf-scans/{scan_id}/items/{item_id}")
async def patch_item(scan_id: uuid.UUID, item_id: uuid.UUID, body: ItemPatch, t: Tenant = Depends(tenant), session: AsyncSession = Depends(get_session)) -> dict:
    t.require("owner", "editor", "reviewer")
    s = await _scan(session, t, scan_id)
    item = next((i for i in s.items if i.id == item_id), None)
    if item is None:
        raise HTTPException(404, "Item not found")
    for k, v in body.model_dump(exclude_unset=True, exclude={"refresh_candidates"}).items():
        setattr(item, k, v)
    if body.refresh_candidates:
        from app.services.vision import candidates_for

        item.candidates = await candidates_for({"title": item.proposed_title, "author": item.proposed_author, "isbn": item.proposed_isbn, "spine_text": item.spine_text})
    await session.commit()
    return _item_card(await session.get(ShelfScanItem, item.id))


class ConfirmIn(BaseModel):
    confirmed_holding: bool = False
    selected_candidate: dict[str, Any] | None = None
    manual_title: str | None = None
    manual_author: str | None = None
    call_number: str | None = None
    shelf_label: str | None = None
    edition_note: str | None = None


@router.post("/shelf-scans/{scan_id}/items/{item_id}/confirm")
async def confirm_item(scan_id: uuid.UUID, item_id: uuid.UUID, body: ConfirmIn, t: Tenant = Depends(tenant), session: AsyncSession = Depends(get_session)) -> dict:
    """Human confirmation gate. Creates a DRAFT record only; publishing still goes through review."""
    t.require("owner", "editor", "reviewer")
    s = await _scan(session, t, scan_id)
    inst = await _inst(session, t)
    item = next((i for i in s.items if i.id == item_id), None)
    if item is None:
        raise HTTPException(404, "Item not found")
    if item.status == "confirmed":
        raise HTTPException(409, "Item already confirmed")
    if not body.confirmed_holding:
        raise HTTPException(422, "You must confirm that your institution physically holds this item")
    cand = body.selected_candidate if body.selected_candidate is not None else item.selected_candidate
    title = (body.manual_title or (cand or {}).get("title") or "").strip()
    if not cand and not body.manual_title:
        raise HTTPException(422, "Select a catalogue candidate or enter the title manually")
    if not title:
        raise HTTPException(422, "A title is required")
    authors = [a for a in ([body.manual_author] if body.manual_author else (cand or {}).get("authors", [])) if a]
    identifiers: dict[str, Any] = {}
    if cand:
        identifiers = {k: v for k, v in {"openlibrary_work_key": cand.get("openlibrary_work_key"), "isbn": cand.get("isbns", [])[:3] or None}.items() if v}
    if item.proposed_isbn:
        identifiers.setdefault("isbn", [item.proposed_isbn])
    year = (cand or {}).get("first_publish_year")
    rec = NormalizedRecord(
        source_system=f"partner_shelf_scan:{inst.slug}", source_record_id=f"scan:{s.id}:item:{item.id}", title=title, creators=authors,
        description=(f"Edition: {body.edition_note}. " if body.edition_note else "") + "Identified from a shelf photograph and confirmed by staff. " + (f"Bibliographic reference: Open Library {cand.get('openlibrary_url')}." if cand and cand.get("openlibrary_url") else ""),
        date_text=str(year) if year else None, date_start=year, date_end=year, resource_type="book", identifiers=identifiers,
        original_url=inst.catalogue_url or inst.website_url or f"/institutions/{inst.slug}", rights=None, rights_status="unknown", access_type="physical",
        access_note=inst.access_requirements or f"Held physically by {inst.name}.", holding_verification="verified_partner",
        call_number=body.call_number or item.call_number, shelf_label=body.shelf_label or item.shelf_label,
        raw_metadata={"shelf_scan_id": str(s.id), "spine_text": item.spine_text, "vision_confidence": item.confidence, "uncertainties": item.uncertainties, "openlibrary_candidate": cand, "bibliographic_reference": "Open Library (candidate chosen by staff)" if cand else "manual entry"},
        provenance={"adapter": "partner_shelf_scan", "created_by": t.user.email, "confirmed_at": datetime.now(timezone.utc).isoformat(), "scan_id": str(s.id)}, review_status="draft",
    )
    r, _ = await upsert_record(session, rec, institution_id=inst.id)
    item.status = "confirmed"
    item.confirmed_holding = True
    item.selected_candidate = cand
    item.call_number = rec.call_number
    item.shelf_label = rec.shelf_label
    item.record_id = r.id
    if all(i.status != "proposed" for i in s.items):
        s.status = "reviewed"
    await audit.log(session, institution_id=inst.id, actor=t.user, action="shelf_scan.confirm_item", entity_type="record", entity_id=r.id, after={"title": title, "call_number": rec.call_number, "review_status": "draft", "scan_item": str(item.id)})
    await session.commit()
    return {"item": _item_card(await session.get(ShelfScanItem, item.id)), "record": record_card(await _reload(session, r.id))}


@router.post("/shelf-scans/{scan_id}/items/{item_id}/reject")
async def reject_item(scan_id: uuid.UUID, item_id: uuid.UUID, t: Tenant = Depends(tenant), session: AsyncSession = Depends(get_session)) -> dict:
    t.require("owner", "editor", "reviewer")
    s = await _scan(session, t, scan_id)
    item = next((i for i in s.items if i.id == item_id), None)
    if item is None:
        raise HTTPException(404, "Item not found")
    item.status = "rejected"
    if all(i.status != "proposed" for i in s.items):
        s.status = "reviewed"
    await audit.log(session, institution_id=t.institution_id, actor=t.user, action="shelf_scan.reject_item", entity_type="shelf_scan_item", entity_id=item.id)
    await session.commit()
    return _item_card(await session.get(ShelfScanItem, item.id))
