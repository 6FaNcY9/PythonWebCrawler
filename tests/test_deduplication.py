from datetime import datetime

from crawler.core.models import Kind, Record
from crawler.core.pipeline import deduplicate


def build_record(title: str, sku: str | None = None) -> Record:
    return Record(
        id=title,
        kind=Kind.DOCUMENT,
        title=title,
        description=None,
        creators=None,
        year=2020,
        language="en",
        topics=None,
        provider="adapter",
        source_url="https://example.com",
        license=None,
        media={},
        availability={},
        price={"sku": sku} if sku else {},
        extra={},
        ingested_at=datetime.utcnow(),
    )


def test_deduplicate_merges_similar_records():
    records = [build_record("Title", None), build_record("Title", None)]
    result = deduplicate(records)
    assert len(result) == 1
