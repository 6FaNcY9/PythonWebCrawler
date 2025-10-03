"""Adapter for YouTube Data API focusing on Creative Commons/free movies."""

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
    name = "youtube_free"
    kinds = (Kind.MOVIE,)

    def __init__(self, *, settings: Dict[str, Any] | None = None) -> None:
        super().__init__(settings=settings)
        app_settings = self.settings.get("app_settings")
        if app_settings is None:
            raise ValueError("App settings are required")
        self.app_settings = app_settings
        self.api_key = self.settings.get("api_key") or os.getenv("YOUTUBE_API_KEY")
        if not self.api_key:
            raise ValueError("YouTube API key must be provided via settings or YOUTUBE_API_KEY env")
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

    async def discover(self, query: str) -> List[str]:
        url = "https://www.googleapis.com/youtube/v3/search"
        params = {
            "q": query,
            "key": self.api_key,
            "part": "snippet",
            "type": "video",
            "videoDuration": "long",
            "videoLicense": "creativeCommon",
            "maxResults": 25,
        }
        async with self._client() as http:
            response = await http.get(url, params=params)
        data = response.json()
        items = data.get("items", [])
        return [item["id"]["videoId"] for item in items]

    async def fetch(self, video_id: str) -> Dict[str, Any]:
        url = "https://www.googleapis.com/youtube/v3/videos"
        params = {
            "id": video_id,
            "part": "snippet,contentDetails,topicDetails",
            "key": self.api_key,
        }
        async with self._client() as http:
            response = await http.get(url, params=params)
        data = response.json()
        items = data.get("items", [])
        return items[0] if items else {}

    async def parse(self, raw: Dict[str, Any]) -> List[Record]:
        if not raw:
            return []
        snippet = raw.get("snippet", {})
        content_details = raw.get("contentDetails", {})
        duration = _parse_iso_duration(content_details.get("duration"))
        record = Record(
            id=stable_hash({"provider": self.name, "video_id": raw.get("id")}),
            kind=Kind.MOVIE,
            title=snippet.get("title"),
            description=snippet.get("description"),
            creators=[snippet.get("channelTitle")] if snippet.get("channelTitle") else None,
            year=int(snippet["publishedAt"][:4]) if snippet.get("publishedAt") else None,
            language=None,
            topics=raw.get("topicDetails", {}).get("topicCategories"),
            provider=self.name,
            source_url=f"https://www.youtube.com/watch?v={raw.get('id')}",
            license="Creative Commons",
            media={"type": "video", "duration_sec": duration, "format": "mp4"},
            availability={"is_free": True, "regions": None, "expires_at": None},
            price={},
            extra={"raw": raw},
            ingested_at=datetime.utcnow(),
        )
        return [record]


def _parse_iso_duration(value: str | None) -> int:
    if not value:
        return 0
    # Minimal ISO8601 duration parser for PT#H#M#S
    hours = minutes = seconds = 0
    value = value.replace("PT", "")
    number = ""
    for char in value:
        if char.isdigit():
            number += char
        else:
            if char == "H":
                hours = int(number)
            elif char == "M":
                minutes = int(number)
            elif char == "S":
                seconds = int(number)
            number = ""
    return hours * 3600 + minutes * 60 + seconds
