from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog, User


async def log(session: AsyncSession, *, institution_id: uuid.UUID | None, actor: User | None, action: str, entity_type: str, entity_id: Any, before: dict | None = None, after: dict | None = None) -> AuditLog:
    entry = AuditLog(
        institution_id=institution_id,
        actor_id=actor.id if actor else None,
        actor_label=(actor.email if actor else "system"),
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id is not None else None,
        before=before,
        after=after,
    )
    session.add(entry)
    await session.flush()
    return entry
