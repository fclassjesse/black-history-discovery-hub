"""Draft → in_review → published → withdrawn workflow with role checks and audit trail."""
from __future__ import annotations

from fastapi import HTTPException

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Record, User
from app.security import Tenant
from app.services import audit

# action → (allowed from states, allowed roles, target state)
TRANSITIONS: dict[str, tuple[tuple[str, ...], tuple[str, ...], str]] = {
    "submit": (("draft",), ("owner", "editor", "reviewer"), "in_review"),
    "return": (("in_review",), ("owner", "reviewer"), "draft"),
    "publish": (("draft", "in_review"), ("owner", "reviewer"), "published"),
    "withdraw": (("published", "in_review"), ("owner", "reviewer"), "withdrawn"),
    "reopen": (("withdrawn",), ("owner", "editor", "reviewer"), "draft"),
}


def record_snapshot(r: Record) -> dict:
    return {"title": r.title, "review_status": r.review_status, "holding_verification": r.holding_verification, "call_number": r.call_number, "institution_id": str(r.institution_id) if r.institution_id else None}


async def transition(session: AsyncSession, record: Record, action: str, t: Tenant, note: str | None = None) -> Record:
    if action not in TRANSITIONS:
        raise HTTPException(400, f"Unknown action {action}")
    from_states, roles, target = TRANSITIONS[action]
    if record.institution_id != t.institution_id:
        raise HTTPException(404, "Record not found in this institution")
    if record.review_status not in from_states:
        raise HTTPException(409, f"Cannot {action} a record in state {record.review_status}")
    t.require(*roles)
    before = record_snapshot(record)
    record.review_status = target
    await session.flush()
    await audit.log(session, institution_id=t.institution_id, actor=t.user, action=f"record.{action}", entity_type="record", entity_id=record.id, before=before, after={**record_snapshot(record), "note": note})
    return record


async def edit(session: AsyncSession, record: Record, changes: dict, t: Tenant) -> Record:
    if record.institution_id != t.institution_id:
        raise HTTPException(404, "Record not found in this institution")
    t.require("owner", "editor", "reviewer")
    before = record_snapshot(record) | {k: getattr(record, k) for k in changes if hasattr(record, k)}
    for k, v in changes.items():
        setattr(record, k, v)
    from app.services.dedupe import dedupe_key_for

    record.dedupe_key = dedupe_key_for(record.title, record.creators, record.date_start)
    await session.flush()
    await audit.log(session, institution_id=t.institution_id, actor=t.user, action="record.edit", entity_type="record", entity_id=record.id, before=before, after={k: getattr(record, k) for k in changes if hasattr(record, k)})
    return record


def can(role: str, action: str) -> bool:
    return role in TRANSITIONS.get(action, ((), (), ""))[1]


__all__ = ["transition", "edit", "can", "TRANSITIONS", "User"]
