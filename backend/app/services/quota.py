"""In-memory usage guards for a public deployment: a daily cap on AI-written answers and a login throttle.

Privacy: a visitor is counted by a salted hash of their IP address that lives only in this process's memory.
The salt changes every UTC day and nothing is written to the database or logs, so counts cannot be tied back
to a person and vanish at midnight or on restart.

Limits are per process. The deployment runs a single API process; with several, each enforces its own share.
"""
from __future__ import annotations

import hashlib
import secrets
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone

from fastapi import Request

from app.config import get_settings

LOGIN_WINDOW_SECONDS = 15 * 60
LOGIN_MAX_ATTEMPTS = 10


def client_ip(request: Request) -> str:
    """The visitor's IP. Behind the Next.js proxy the socket peer is the web server, so the first
    X-Forwarded-For entry is used when TRUST_PROXY_HEADERS is on (a spoofed header only moves a visitor
    into another per-visitor bucket; the global daily cap still holds)."""
    if get_settings().trust_proxy_headers:
        fwd = request.headers.get("x-forwarded-for", "")
        first = fwd.split(",")[0].strip()
        if first:
            return first
    return request.client.host if request.client else "unknown"


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


@dataclass
class _Day:
    day: str = ""
    salt: str = ""
    total: int = 0
    per_visitor: dict[str, int] = field(default_factory=dict)


class AnswerQuota:
    """Daily cap on questions answered by the AI model (global and per visitor)."""

    def __init__(self) -> None:
        self._d = _Day()

    def _roll(self) -> _Day:
        today = _today()
        if self._d.day != today:
            self._d = _Day(day=today, salt=secrets.token_hex(16))
        return self._d

    def visitor_key(self, ip: str) -> str:
        d = self._roll()
        return hashlib.sha256(f"{d.salt}:{ip}".encode()).hexdigest()[:16]

    def try_take(self, visitor: str | None) -> bool:
        """Reserve one AI answer. False when today's global or per-visitor allowance is used up."""
        s = get_settings()
        d = self._roll()
        if s.guide_daily_limit and d.total >= s.guide_daily_limit:
            return False
        if visitor and s.guide_daily_limit_per_visitor and d.per_visitor.get(visitor, 0) >= s.guide_daily_limit_per_visitor:
            return False
        d.total += 1
        if visitor:
            d.per_visitor[visitor] = d.per_visitor.get(visitor, 0) + 1
        return True

    def usage(self) -> dict[str, int | str]:
        d = self._roll()
        return {"day": d.day, "answers": d.total, "limit": get_settings().guide_daily_limit, "visitors": len(d.per_visitor)}


class LoginThrottle:
    """At most LOGIN_MAX_ATTEMPTS failed logins per (visitor, email) per 15 minutes."""

    def __init__(self) -> None:
        self._fails: dict[str, list[float]] = {}

    @staticmethod
    def _key(ip: str, email: str) -> str:
        return hashlib.sha256(f"{ip}|{email.strip().lower()}".encode()).hexdigest()[:24]

    def blocked(self, ip: str, email: str) -> bool:
        now = time.monotonic()
        k = self._key(ip, email)
        recent = [t for t in self._fails.get(k, []) if now - t < LOGIN_WINDOW_SECONDS]
        self._fails[k] = recent
        return len(recent) >= LOGIN_MAX_ATTEMPTS

    def fail(self, ip: str, email: str) -> None:
        self._fails.setdefault(self._key(ip, email), []).append(time.monotonic())
        if len(self._fails) > 10_000:  # bound memory under a spray attack
            self._fails.clear()

    def success(self, ip: str, email: str) -> None:
        self._fails.pop(self._key(ip, email), None)


answer_quota = AnswerQuota()
login_throttle = LoginThrottle()
