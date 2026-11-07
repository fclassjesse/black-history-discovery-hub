"""FastAPI-native auth: argon2 password hashes, JWT in an httpOnly cookie, server-side membership checks."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.models import Membership, User

COOKIE_NAME = "bhdh_session"
_ph = PasswordHasher()


def hash_password(pw: str) -> str:
    return _ph.hash(pw)


def verify_password(pw: str, hashed: str) -> bool:
    try:
        return _ph.verify(hashed, pw)
    except VerifyMismatchError:
        return False


def issue_token(user_id: uuid.UUID) -> str:
    s = get_settings()
    exp = datetime.now(timezone.utc) + timedelta(minutes=s.jwt_expire_minutes)
    return jwt.encode({"sub": str(user_id), "exp": exp}, s.jwt_secret, algorithm="HS256")


def set_session_cookie(response: Response, token: str) -> None:
    s = get_settings()
    response.set_cookie(COOKIE_NAME, token, httponly=True, samesite="lax", secure=s.cookie_secure, max_age=s.jwt_expire_minutes * 60, path="/")


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(COOKIE_NAME, path="/")


async def current_user(request: Request, session: AsyncSession = Depends(get_session)) -> User:
    token = request.cookies.get(COOKIE_NAME)
    auth = request.headers.get("authorization", "")
    if not token and auth.lower().startswith("bearer "):
        token = auth[7:].strip()
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not signed in")
    try:
        payload = jwt.decode(token, get_settings().jwt_secret, algorithms=["HS256"])
        user_id = uuid.UUID(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session invalid or expired") from None
    user = await session.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found")
    return user


class Tenant:
    """Resolved membership for the institution in the URL. Every partner endpoint depends on this."""

    def __init__(self, user: User, membership: Membership):
        self.user = user
        self.membership = membership
        self.institution_id = membership.institution_id
        self.role = membership.role

    def require(self, *roles: str) -> None:
        if self.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"Requires role {' or '.join(roles)} (you are {self.role})")


async def tenant(institution_id: uuid.UUID, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)) -> Tenant:
    m = (
        await session.execute(select(Membership).where(Membership.user_id == user.id, Membership.institution_id == institution_id))
    ).scalar_one_or_none()
    if m is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You are not a member of this institution")
    return Tenant(user, m)


def require_roles(*roles: str):
    async def dep(t: Tenant = Depends(tenant)) -> Tenant:
        t.require(*roles)
        return t

    return dep
