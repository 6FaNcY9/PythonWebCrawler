"""Orchestration pipeline for crawling and normalizing records."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Iterable, List, Sequence

from ..adapters.base import BaseAdapter
from ..settings import AppSettings
from .models import Kind, Record
from .utils import stable_hash

logger = logging.getLogger(__name__)


async def _run_adapter(adapter: BaseAdapter, query: str, limit: int) -> List[Record]:
    results: List[Record] = []
    try:
        discovered = await adapter.discover(query)
        for url in discovered[:limit]:
            raw = await adapter.fetch(url)
            parsed = await adapter.parse(raw)
            for item in parsed:
                if len(results) >= limit:
                    break
                results.append(item)
            if len(results) >= limit:
                break
    except Exception:
        logger.exception("Adapter %s failed", adapter.name)
    return results


def deduplicate(records: Sequence[Record]) -> List[Record]:
    seen = {}
    deduped: List[Record] = []
    for record in records:
        key = (record.kind, record.provider, record.title.lower(), record.year, record.price.get("sku"))
        stable = stable_hash(key)
        if stable in seen:
            continue
        seen[stable] = True
        deduped.append(record)
    return deduped


async def crawl(*, kind: Kind, query: str, limit: int, settings: AppSettings) -> List[Record]:
    adapters = [adapter for adapter in settings.instantiate_adapters() if adapter.supports_kind(kind)]
    adapter_limit = max(1, limit // max(1, len(adapters)))

    tasks = [asyncio.create_task(_run_adapter(adapter, query, adapter_limit)) for adapter in adapters]
    results: List[Record] = []
    for task in asyncio.as_completed(tasks):
        records = await task
        results.extend(records)

    deduped = deduplicate(results)
    limited = deduped[:limit]
    now = datetime.utcnow()
    for record in limited:
        record.ingested_at = now
    return limited


def crawl_sync(kind: Kind, query: str, limit: int, settings: AppSettings) -> Iterable[Record]:
    return asyncio.run(crawl(kind=kind, query=query, limit=limit, settings=settings))
