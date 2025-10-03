"""Base definitions for crawler adapters."""

from __future__ import annotations

import abc
from typing import Any, Iterable, List

from ..core.models import Kind, Record


class BaseAdapter(abc.ABC):
    """Abstract base class describing adapter contract."""

    name: str
    kinds: Iterable[Kind]

    def __init__(self, *, settings: dict | None = None) -> None:
        self.settings = settings or {}

    @abc.abstractmethod
    async def discover(self, query: str) -> List[str]:
        """Return candidate URLs for the given query."""

    @abc.abstractmethod
    async def fetch(self, url: str) -> Any:
        """Fetch raw data for the URL."""

    @abc.abstractmethod
    async def parse(self, raw: Any) -> List[Record]:
        """Parse raw data into normalized records."""

    def supports_kind(self, kind: Kind) -> bool:
        return kind in self.kinds or kind is Kind.ALL
