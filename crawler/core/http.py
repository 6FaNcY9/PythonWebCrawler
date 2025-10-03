"""Async HTTP utilities with caching, rate limiting, and robots awareness."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx
from aiolimiter import AsyncLimiter

logger = logging.getLogger(__name__)


@dataclass
class CachedResponse:
    status_code: int
    headers: Dict[str, str]
    content: bytes
    timestamp: float

    def to_bytes(self) -> bytes:
        return json.dumps(
            {
                "status_code": self.status_code,
                "headers": self.headers,
                "timestamp": self.timestamp,
                "content": self.content.decode("latin1"),
            }
        ).encode("utf-8")

    @classmethod
    def from_bytes(cls, data: bytes) -> "CachedResponse":
        payload = json.loads(data.decode("utf-8"))
        return cls(
            status_code=payload["status_code"],
            headers={k: str(v) for k, v in payload["headers"].items()},
            content=payload["content"].encode("latin1"),
            timestamp=payload["timestamp"],
        )


class DiskCache:
    """Simple on-disk cache keyed by URL."""

    def __init__(self, cache_dir: Path) -> None:
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _path_for(self, key: str) -> Path:
        safe = httpx.URL(key).raw_path.replace("/", "_")
        return self.cache_dir / f"{hash(key)}_{safe}.json"

    def get(self, key: str) -> Optional[CachedResponse]:
        path = self._path_for(key)
        if not path.exists():
            return None
        try:
            return CachedResponse.from_bytes(path.read_bytes())
        except Exception:
            logger.exception("Failed to read cache entry for %s", key)
            return None

    def set(self, key: str, response: CachedResponse) -> None:
        path = self._path_for(key)
        try:
            path.write_bytes(response.to_bytes())
        except Exception:
            logger.exception("Failed to write cache entry for %s", key)


class RobotsManager:
    """Manages per-domain robots.txt parsing."""

    def __init__(self, user_agent: str, timeout: float = 10.0) -> None:
        self.user_agent = user_agent
        self.timeout = timeout
        self._parsers: Dict[str, RobotFileParser] = {}
        self._lock = asyncio.Lock()

    async def allowed(self, client: httpx.AsyncClient, url: str) -> bool:
        parsed = urlparse(url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        async with self._lock:
            parser = self._parsers.get(base)
            if parser is None:
                robots_url = f"{base}/robots.txt"
                try:
                    response = await client.get(robots_url, timeout=self.timeout)
                except httpx.HTTPError:
                    logger.warning("Failed to fetch robots.txt from %s", robots_url)
                    parser = RobotFileParser()
                    parser.parse([])
                else:
                    parser = RobotFileParser()
                    parser.set_url(robots_url)
                    parser.parse(response.text.splitlines())
                self._parsers[base] = parser
        return parser.can_fetch(self.user_agent, url)


class RateLimiterRegistry:
    """Registry of per-domain rate limiters."""

    def __init__(self, per_domain_limit: float) -> None:
        self.per_domain_limit = per_domain_limit
        self._limiters: Dict[str, AsyncLimiter] = {}
        self._lock = asyncio.Lock()

    async def limiter_for(self, url: str) -> AsyncLimiter:
        domain = httpx.URL(url).netloc
        async with self._lock:
            limiter = self._limiters.get(domain)
            if limiter is None:
                limiter = AsyncLimiter(max_rate=self.per_domain_limit, time_period=1)
                self._limiters[domain] = limiter
            return limiter


class AsyncHttpClient:
    """High-level HTTP client with caching, robots, and retry support."""

    def __init__(
        self,
        *,
        user_agent: str,
        cache_dir: Path,
        timeout: float = 30.0,
        max_retries: int = 3,
        backoff_base: float = 0.5,
        per_domain_limit: float = 2.0,
        audit_path: Path | None = None,
        adapter_name: str | None = None,
    ) -> None:
        headers = {"User-Agent": user_agent}
        self._client = httpx.AsyncClient(headers=headers, timeout=timeout)
        self.cache = DiskCache(cache_dir)
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self.robots = RobotsManager(user_agent=user_agent)
        self.limiters = RateLimiterRegistry(per_domain_limit)
        self.audit_path = audit_path
        self.adapter_name = adapter_name

    async def close(self) -> None:
        await self._client.aclose()

    async def _request(self, method: str, url: str, **kwargs) -> httpx.Response:
        limiter = await self.limiters.limiter_for(url)
        async with limiter:
            retries = 0
            while True:
                try:
                    response = await self._client.request(method, url, **kwargs)
                except httpx.HTTPError as exc:
                    if retries >= self.max_retries:
                        raise
                    await asyncio.sleep(self._backoff_delay(retries))
                    retries += 1
                    continue
                if response.status_code in {429, 500, 502, 503, 504} and retries < self.max_retries:
                    await asyncio.sleep(self._backoff_delay(retries))
                    retries += 1
                    continue
                return response

    def _backoff_delay(self, retries: int) -> float:
        return self.backoff_base * (2 ** retries)

    async def get(self, url: str, *, use_cache: bool = True, **kwargs) -> httpx.Response:
        if use_cache:
            cached = self.cache.get(url)
            if cached:
                headers = kwargs.setdefault("headers", {})
                if "ETag" in cached.headers:
                    headers["If-None-Match"] = cached.headers["ETag"]
                if "Last-Modified" in cached.headers:
                    headers["If-Modified-Since"] = cached.headers["Last-Modified"]
        else:
            cached = None

        if not await self.robots.allowed(self._client, url):
            raise PermissionError(f"Robots disallow fetching {url}")

        response = await self._request("GET", url, **kwargs)
        if response.status_code == 304 and cached:
            self._log_audit(url, response.status_code, len(cached.content), "cache-hit")
            return httpx.Response(200, headers=cached.headers, content=cached.content)

        if use_cache and response.status_code == 200:
            self.cache.set(
                url,
                CachedResponse(
                    status_code=response.status_code,
                    headers=dict(response.headers),
                    content=response.content,
                    timestamp=time.time(),
                ),
            )
        self._log_audit(url, response.status_code, len(response.content), "fetched")
        return response

    async def head(self, url: str, **kwargs) -> httpx.Response:
        if not await self.robots.allowed(self._client, url):
            raise PermissionError(f"Robots disallow fetching {url}")
        response = await self._request("HEAD", url, **kwargs)
        self._log_audit(url, response.status_code, 0, "head")
        return response

    def _log_audit(self, url: str, status_code: int, size: int, decision: str) -> None:
        if not self.audit_path or not self.adapter_name:
            return
        try:
            from .audit import record_request

            record_request(
                adapter=self.adapter_name,
                url=url,
                status_code=status_code,
                bytes_count=size,
                decision=decision,
                path=self.audit_path,
            )
        except Exception:
            logger.exception("Failed to record audit entry for %s", url)

    async def __aenter__(self) -> "AsyncHttpClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()
