from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any, Dict, List

import pytest

from crawler.core.models import Kind, Record
from crawler.core.pipeline import crawl
from crawler.settings import AppSettings, AdapterConfig


class DummyAdapter:
    name = "dummy"
    kinds = (Kind.DOCUMENT,)

    def __init__(self, *, settings: Dict[str, Any] | None = None) -> None:
        self.settings = settings or {}

    async def discover(self, query: str) -> List[str]:
        return [f"http://example.com/{query}"]

    async def fetch(self, url: str) -> Dict[str, Any]:
        return {"url": url}

    async def parse(self, raw: Dict[str, Any]) -> List[Record]:
        return [
            Record(
                id="dummy",
                kind=Kind.DOCUMENT,
                title="Example",
                description="",
                creators=None,
                year=None,
                language="en",
                topics=None,
                provider=self.name,
                source_url="https://example.com",
                license="Public Domain",
                media={"type": "pdf"},
                availability={"is_free": True},
                price={},
                extra={"raw": raw},
                ingested_at=datetime.utcnow(),
            )
        ]

    def supports_kind(self, kind: Kind) -> bool:
        return kind in self.kinds


@pytest.mark.asyncio
async def test_crawl_uses_adapters(monkeypatch):
    settings = AppSettings(adapters=[AdapterConfig(name="dummy", options={})])

    def fake_instantiate(self):
        return [DummyAdapter()]

    monkeypatch.setattr(AppSettings, "instantiate_adapters", fake_instantiate)

    records = await crawl(kind=Kind.DOCUMENT, query="test", limit=10, settings=settings)
    assert len(records) == 1
    assert records[0].provider == "dummy"
