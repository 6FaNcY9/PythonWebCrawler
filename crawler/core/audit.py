"""Audit logging utilities."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Iterable

from .models import AuditEntry


class AuditLogger:
    """Persists structured audit entries to disk."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def log(self, entry: AuditEntry) -> None:
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry.dict()) + "\n")


def record_request(*, adapter: str, url: str, status_code: int, bytes_count: int, decision: str, path: Path) -> None:
    logger = AuditLogger(path)
    entry = AuditEntry(
        timestamp=datetime.utcnow(),
        adapter=adapter,
        url=url,
        status_code=status_code,
        bytes=bytes_count,
        decision=decision,
    )
    logger.log(entry)
