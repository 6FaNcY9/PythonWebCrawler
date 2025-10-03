"""Adapter for the Internet Archive documents API."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from ..core.http import AsyncHttpClient
from ..core.models import Kind, Record
from ..core.utils import stable_hash
from .base import BaseAdapter

logger = logging.getLogger(__name__)


class Adapter(BaseAdapter):
    name = "internet_archive_docs"
    kinds = (Kind.DOCUMENT,)

    def __init__(self, *, settings: Dict[str, Any] | None = None) -> None:
        super().__init__(settings=settings)
        app_settings = self.settings.get("app_settings")
        if app_settings is None:
            raise ValueError("App settings are required")
        self.app_settings = app_settings
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
        params = {
            "q": query,
            "fl[]": ["identifier", "title", "creator", "description", "language", "year"],
            "rows": 50,
            "output": "json",
        }
        async with self._client() as http:
            response = await http.get("https://archive.org/advancedsearch.php", params=params)
        data = response.json()
        docs = data.get("response", {}).get("docs", [])
        return [doc["identifier"] for doc in docs]

    async def fetch(self, identifier: str) -> Dict[str, Any]:
        url = f"https://archive.org/metadata/{identifier}"
        async with self._client() as http:
            response = await http.get(url)
        return response.json()

    async def parse(self, raw: Dict[str, Any]) -> List[Record]:
        metadata = raw.get("metadata", {})
        identifier = metadata.get("identifier")
        if not identifier:
            return []
        record = Record(
            id=stable_hash({"provider": self.name, "identifier": identifier}),
            kind=Kind.DOCUMENT,
            title=metadata.get("title", identifier),
            description=metadata.get("description"),
            creators=[metadata.get("creator")] if metadata.get("creator") else None,
            year=int(metadata["year"]) if metadata.get("year") else None,
            language=metadata.get("language"),
            topics=metadata.get("subject"),
            provider=self.name,
            source_url=f"https://archive.org/details/{identifier}",
            license=metadata.get("licenseurl") or metadata.get("rights"),
            media={"type": "pdf", "format": metadata.get("format")},
            availability={"is_free": True, "regions": None, "expires_at": None},
            price={},
            extra={"raw": metadata},
            ingested_at=datetime.utcnow(),
        )
        return [record]
