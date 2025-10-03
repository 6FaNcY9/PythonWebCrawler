"""Adapter for TMDB free-to-watch metadata."""

from __future__ import annotations

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from ..core.http import AsyncHttpClient
from ..core.models import Kind, Record
from ..core.utils import stable_hash
from .base import BaseAdapter

logger = logging.getLogger(__name__)


class Adapter(BaseAdapter):
    name = "tmdb_free"
    kinds = (Kind.MOVIE,)

    def __init__(self, *, settings: Dict[str, Any] | None = None) -> None:
        super().__init__(settings=settings)
        app_settings = self.settings.get("app_settings")
        if app_settings is None:
            raise ValueError("App settings are required")
        self.app_settings = app_settings
        self.api_key = self.settings.get("api_key") or os.getenv("TMDB_API_KEY")
        if not self.api_key:
            raise ValueError("TMDB API key must be provided via settings or TMDB_API_KEY env")
        self.cache_dir = Path(app_settings.cache_dir) / self.name
        self.audit_path = Path(app_settings.cache_dir) / "audit.log"

    def _client(self) -> AsyncHttpClient:
        return AsyncHttpClient(
            user_agent=self.app_settings.user_agent,
            cache_dir=self.cache_dir,
            per_domain_limit=self.app_settings.concurrency.per_domain_rps,
            audit_path=self.audit_path,
            adapter_name=self.name,
        )

    async def discover(self, query: str) -> List[int]:
        url = "https://api.themoviedb.org/3/search/movie"
        params = {"query": query, "api_key": self.api_key, "include_adult": False}
        async with self._client() as http:
            response = await http.get(url, params=params)
        data = response.json()
        results = data.get("results", [])
        return [result["id"] for result in results]

    async def fetch(self, movie_id: int) -> Dict[str, Any]:
        url = f"https://api.themoviedb.org/3/movie/{movie_id}"
        params = {"api_key": self.api_key, "append_to_response": "watch/providers"}
        async with self._client() as http:
            response = await http.get(url, params=params)
        return response.json()

    async def parse(self, raw: Dict[str, Any]) -> List[Record]:
        providers = raw.get("watch/providers", {}).get("results", {})
        free_regions = []
        for region, info in providers.items():
            flatrate = info.get("flatrate", [])
            ads = info.get("ads", [])
            if flatrate or ads:
                free_regions.append(region)
        if not free_regions:
            return []
        record = Record(
            id=stable_hash({"provider": self.name, "tmdb_id": raw.get("id")}),
            kind=Kind.MOVIE,
            title=raw.get("title"),
            description=raw.get("overview"),
            creators=None,
            year=int(raw["release_date"].split("-")[0]) if raw.get("release_date") else None,
            language=raw.get("original_language"),
            topics=[genre.get("name") for genre in raw.get("genres", [])],
            provider=self.name,
            source_url=f"https://www.themoviedb.org/movie/{raw.get('id')}",
            license=None,
            media={"type": "video", "duration_sec": raw.get("runtime", 0) * 60, "format": "video"},
            availability={"is_free": True, "regions": free_regions, "expires_at": None},
            price={},
            extra={"raw": raw},
            ingested_at=datetime.utcnow(),
        )
        return [record]
