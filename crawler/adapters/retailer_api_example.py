"""Example adapter for retailer pricing via official API or feed."""

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
    name = "retailer_api_example"
    kinds = (Kind.PRICE,)

    def __init__(self, *, settings: Dict[str, Any] | None = None) -> None:
        super().__init__(settings=settings)
        app_settings = self.settings.get("app_settings")
        if app_settings is None:
            raise ValueError("App settings are required")
        self.app_settings = app_settings
        self.api_endpoint = self.settings.get("api_endpoint")
        if not self.api_endpoint:
            raise ValueError("api_endpoint must be configured for retailer adapter")
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
        # For official APIs we assume search endpoint is provided.
        params = {"q": query, "limit": 50}
        async with self._client() as http:
            response = await http.get(self.api_endpoint, params=params)
        data = response.json()
        items = data.get("items", [])
        return [item.get("id") for item in items if item.get("id")]

    async def fetch(self, item_id: str) -> Dict[str, Any]:
        url = f"{self.api_endpoint.rstrip('/')}/{item_id}"
        async with self._client() as http:
            response = await http.get(url)
        return response.json()

    async def parse(self, raw: Dict[str, Any]) -> List[Record]:
        if not raw:
            return []
        record = Record(
            id=stable_hash({"provider": self.name, "sku": raw.get("sku") or raw.get("id")}),
            kind=Kind.PRICE,
            title=raw.get("title") or raw.get("name"),
            description=raw.get("description"),
            creators=None,
            year=None,
            language=None,
            topics=raw.get("categories"),
            provider=self.name,
            source_url=raw.get("url"),
            license=raw.get("license"),
            media={"type": "product", "format": "json"},
            availability={"is_free": False, "regions": raw.get("regions"), "expires_at": None},
            price={
                "currency": raw.get("currency"),
                "amount": raw.get("price"),
                "sku": raw.get("sku"),
                "retailer": raw.get("retailer"),
                "collected_at": datetime.utcnow().isoformat(),
            },
            extra={"raw": raw},
            ingested_at=datetime.utcnow(),
        )
        return [record]
