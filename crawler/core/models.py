"""Data models for normalized crawler output."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, HttpUrl


class Kind(str, Enum):
    """Kinds of records supported by the crawler."""

    DOCUMENT = "docs"
    MOVIE = "movies"
    PRICE = "prices"
    ALL = "all"

    @classmethod
    def for_output(cls, value: str) -> "Kind":
        try:
            return cls(value)
        except ValueError as exc:
            raise ValueError(f"Unsupported kind: {value}") from exc


class MediaType(str, Enum):
    PDF = "pdf"
    VIDEO = "video"
    PAGE = "page"
    PRODUCT = "product"


class Record(BaseModel):
    """Normalized representation of crawler results."""

    id: str
    kind: Kind
    title: str
    description: Optional[str] = None
    creators: Optional[List[str]] = None
    year: Optional[int] = None
    language: Optional[str] = None
    topics: Optional[List[str]] = None
    provider: str
    source_url: HttpUrl
    license: Optional[str] = None
    media: Dict[str, Any] = Field(default_factory=dict)
    availability: Dict[str, Any] = Field(default_factory=dict)
    price: Dict[str, Any] = Field(default_factory=dict)
    extra: Dict[str, Any] = Field(default_factory=dict)
    ingested_at: datetime



class AuditEntry(BaseModel):
    """Structured audit log entry."""

    timestamp: datetime
    adapter: str
    url: HttpUrl
    status_code: int
    bytes: int
    decision: str
    notes: Optional[str] = None
