from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import get_session
from app.models import Membership, User
from app.security import clear_session_cookie, current_user, issue_token, set_session_cookie, verify_password
from app.services.quota import client_ip, login_throttle

router = APIRouter(prefix="/api/partner/auth", tags=["partner-auth"])


class LoginIn(BaseModel):
    email: str = Field(max_length=320)
    password: str


def _me(user: User, memberships: list[Membership]) -> dict:
    return {
        "id": str(user.id), "email": user.email, "display_name": user.display_name,
        "memberships": [{"institution_id": str(m.institution_id), "institution_name": m.institution.name, "institution_slug": m.institution.slug, "role": m.role} for m in memberships],
    }


async def _memberships(session: AsyncSession, user: User) -> list[Membership]:
    rows = await session.execute(select(Membership).options(selectinload(Membership.institution)).where(Membership.user_id == user.id))
    return list(rows.scalars())


@router.post("/login")
async def login(body: LoginIn, request: Request, response: Response, session: AsyncSession = Depends(get_session)) -> dict:
    ip = client_ip(request)
    if login_throttle.blocked(ip, body.email):
        raise HTTPException(429, "Too many failed sign-in attempts. Try again in 15 minutes.")
    user = (await session.execute(select(User).where(User.email == body.email.lower()))).scalar_one_or_none()
    if user is None or not user.is_active or not verify_password(body.password, user.password_hash):
        login_throttle.fail(ip, body.email)
        raise HTTPException(401, "Invalid email or password")
    login_throttle.success(ip, body.email)
    set_session_cookie(response, issue_token(user.id))
    return _me(user, await _memberships(session, user))


@router.post("/logout")
async def logout(response: Response) -> dict:
    clear_session_cookie(response)
    return {"ok": True}


@router.get("/me")
async def me(user: User = Depends(current_user), session: AsyncSession = Depends(get_session)) -> dict:
    return _me(user, await _memberships(session, user))
