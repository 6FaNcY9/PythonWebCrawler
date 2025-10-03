"""Adapter for CKAN-based government open data portals."""

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
    name = "gov_open_data"
    kinds = (Kind.DOCUMENT,)

    def __init__(self, *, settings: Dict[str, Any] | None = None) -> None:
        super().__init__(settings=settings)
        app_settings = self.settings.get("app_settings")
        if app_settings is None:
            raise ValueError("App settings are required")
        self.app_settings = app_settings
        self.base_url = self.settings.get("base_url", "https://catalog.data.gov/api/3/action")
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
        url = f"{self.base_url}/package_search"
        params = {"q": query, "rows": 50}
        async with self._client() as http:
            response = await http.get(url, params=params)
        data = response.json()
        results = data.get("result", {}).get("results", [])
        return [result["id"] for result in results]

    async def fetch(self, package_id: str) -> Dict[str, Any]:
        url = f"{self.base_url}/package_show"
        params = {"id": package_id}
        async with self._client() as http:
            response = await http.get(url, params=params)
        return response.json()

    async def parse(self, raw: Dict[str, Any]) -> List[Record]:
        result = raw.get("result")
        if not result:
            return []
        resources = result.get("resources", [])
        records: List[Record] = []
        for resource in resources:
            if resource.get("state") != "active":
                continue
            source_url = resource.get("url")
            if not source_url:
                continue
            record = Record(
                id=stable_hash({"provider": self.name, "resource_id": resource.get("id")}),
                kind=Kind.DOCUMENT,
                title=resource.get("name") or result.get("title"),
                description=result.get("notes"),
                creators=[org.get("title")] if (org := result.get("organization")) else None,
                year=None,
                language=None,
                topics=[tag["name"] for tag in result.get("tags", [])],
                provider=self.name,
                source_url=source_url,
                license=result.get("license_url") or result.get("license_title"),
                media={"type": "page", "format": resource.get("format")},
                availability={"is_free": True, "regions": None, "expires_at": None},
                price={},
                extra={"raw": resource},
                ingested_at=datetime.utcnow(),
            )
            records.append(record)
        return records
