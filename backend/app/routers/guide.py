from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.services import guide
from app.services.quota import answer_quota, client_ip
from app.services.search import SearchFilters

router = APIRouter(prefix="/api/guide", tags=["guide"])


class Turn(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    answer: str | None = Field(None, max_length=4000)
    record_ids: list[str] = Field(default_factory=list, max_length=20)


class AskIn(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    input_mode: str = Field("text", pattern="^(text|voice)$")
    filters: dict[str, str] | None = Field(None, description="Same names as /api/search query params (country, institution, types, …)")
    history: list[Turn] = Field(default_factory=list, max_length=6, description="Previous turns, oldest first; the last 3 are used")
    locale: str = Field("en", pattern="^(en|fr)$", description="UI language. The guide answers in the question's language and falls back to this; generated messages use it.")


@router.post("/ask")
async def ask(body: AskIn, request: Request, session: AsyncSession = Depends(get_session)) -> dict:
    filters = SearchFilters.from_params(body.filters)
    visitor = answer_quota.visitor_key(client_ip(request))
    out = await guide.ask(session, body.question.strip(), filters=filters, history=[t.model_dump() for t in body.history], locale=body.locale, visitor=visitor)
    out["question"] = body.question.strip()
    out["input_mode"] = body.input_mode
    out["locale"] = body.locale
    return out
