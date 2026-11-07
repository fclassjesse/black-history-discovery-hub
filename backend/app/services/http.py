"""Shared outbound HTTP: honest User-Agent, per-source rate limit, retry/backoff, on-disk cache, provenance."""
from __future__ import annotations

import asyncio
import hashlib
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.config import get_settings


class RetryableHttpError(Exception):
    pass


class BlockedError(Exception):
    """A 403 that looks like a bot challenge; never retried, never worked around."""

    def __init__(self, url: str, status_code: int, detail: str):
        super().__init__(detail)
        self.url = url
        self.status_code = status_code
        self.detail = detail


@dataclass
class FetchResult:
    url: str
    status_code: int
    text: str
    fetched_at: datetime
    from_cache: bool = False
    headers: dict[str, str] = field(default_factory=dict)

    def json(self) -> Any:
        return json.loads(self.text)

    @property
    def ok(self) -> bool:
        return 200 <= self.status_code < 300

    def provenance(self, adapter: str, query: str | None = None) -> dict:
        return {
            "adapter": adapter,
            "request_url": self.url,
            "fetched_at": self.fetched_at.isoformat(),
            "from_cache": self.from_cache,
            "query": query,
        }


class HttpClient:
    def __init__(self) -> None:
        s = get_settings()
        self.user_agent = s.http_user_agent
        self.cache_dir: Path = s.http_cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.default_ttl = s.http_cache_ttl_seconds
        self.timeout = s.http_timeout_seconds
        self._client: httpx.AsyncClient | None = None
        self._locks: dict[str, asyncio.Lock] = {}
        self._last_call: dict[str, float] = {}

    def _client_for(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                headers={"User-Agent": self.user_agent, "Accept": "*/*"},
                timeout=self.timeout,
                follow_redirects=True,
            )
        return self._client

    async def aclose(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    # --- cache ----------------------------------------------------------
    def _cache_path(self, url: str) -> Path:
        return self.cache_dir / (hashlib.sha256(url.encode()).hexdigest() + ".json")

    def _read_cache(self, url: str, ttl: int) -> FetchResult | None:
        p = self._cache_path(url)
        if not p.exists():
            return None
        try:
            data = json.loads(p.read_text())
        except json.JSONDecodeError:
            return None
        fetched_at = datetime.fromisoformat(data["fetched_at"])
        if (datetime.now(timezone.utc) - fetched_at).total_seconds() > ttl:
            return None
        return FetchResult(url=url, status_code=data["status_code"], text=data["text"], fetched_at=fetched_at, from_cache=True, headers=data.get("headers", {}))

    def _write_cache(self, result: FetchResult) -> None:
        self._cache_path(result.url).write_text(
            json.dumps({"url": result.url, "status_code": result.status_code, "text": result.text, "fetched_at": result.fetched_at.isoformat(), "headers": result.headers})
        )

    # --- rate limit -----------------------------------------------------
    async def _throttle(self, source: str, min_interval: float) -> None:
        lock = self._locks.setdefault(source, asyncio.Lock())
        async with lock:
            now = time.monotonic()
            wait = self._last_call.get(source, 0.0) + min_interval - now
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_call[source] = time.monotonic()

    # --- public ---------------------------------------------------------
    async def get(
        self,
        url: str,
        params: dict[str, Any] | None = None,
        *,
        source: str,
        min_interval: float = 1.0,
        cache: bool = True,
        ttl: int | None = None,
        headers: dict[str, str] | None = None,
        allow_statuses: tuple[int, ...] = (),
    ) -> FetchResult:
        req = httpx.Request("GET", url, params=params)
        full_url = str(req.url)
        if cache:
            hit = self._read_cache(full_url, ttl or self.default_ttl)
            if hit is not None:
                return hit

        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=1, max=8),
            retry=retry_if_exception_type((RetryableHttpError, httpx.TransportError)),
            reraise=True,
        ):
            with attempt:
                await self._throttle(source, min_interval)
                resp = await self._client_for().get(full_url, headers=headers)
                if resp.status_code in (429, 500, 502, 503, 504):
                    raise RetryableHttpError(f"{resp.status_code} from {full_url}")
                if resp.status_code == 403 and _looks_like_bot_challenge(resp):
                    raise BlockedError(full_url, 403, "Server returned a browser challenge (Cloudflare) to this client")
                result = FetchResult(
                    url=full_url,
                    status_code=resp.status_code,
                    text=resp.text,
                    fetched_at=datetime.now(timezone.utc),
                    headers={k: v for k, v in resp.headers.items() if k.lower() in ("content-type", "etag", "last-modified")},
                )
                if cache and (result.ok or result.status_code in allow_statuses):
                    self._write_cache(result)
                return result
        raise RuntimeError("unreachable")


def _looks_like_bot_challenge(resp: httpx.Response) -> bool:
    server = resp.headers.get("server", "").lower()
    body = resp.text[:4000].lower()
    return "cloudflare" in server or "cf-mitigated" in resp.headers or "just a moment" in body or "challenge-platform" in body


_http: HttpClient | None = None


def get_http() -> HttpClient:
    global _http
    if _http is None:
        _http = HttpClient()
    return _http
