"""Job handler: shelf scan image → vision proposals → Open Library candidates (proposed items, never published)."""
from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ShelfScan, ShelfScanItem
from app.services import vision
from app.services.jobs import handler
from app.services.llm import LLMNotConfigured


@handler("shelf_scan")
async def process_shelf_scan(session: AsyncSession, payload: dict[str, Any]) -> None:
    scan = await session.get(ShelfScan, uuid.UUID(payload["scan_id"]))
    if scan is None:
        return
    scan.status = "processing"
    await session.commit()
    try:
        data = Path(scan.image_path).read_bytes()
        proposed = await vision.propose_books(data, scan.image_mime or "image/jpeg")
        scan.model = proposed["model"]
        for pos, it in enumerate(proposed["items"]):
            cands = await vision.candidates_for(it)
            session.add(ShelfScanItem(
                scan_id=scan.id, position=pos, spine_text=it["spine_text"], proposed_title=it["title"], proposed_author=it["author"],
                proposed_isbn=it["isbn"], confidence=it["confidence"], uncertainties=it["uncertainties"], candidates=cands,
            ))
        scan.status = "proposed"
        scan.error = None if proposed["items"] else "Vision found no legible book spines in this photo."
    except LLMNotConfigured as e:
        scan.status = "failed"
        scan.error = f"vision unconfigured: {e}"
    except Exception as e:  # noqa: BLE001
        scan.status = "failed"
        scan.error = f"{type(e).__name__}: {str(e)[:500]}"
    await session.commit()
