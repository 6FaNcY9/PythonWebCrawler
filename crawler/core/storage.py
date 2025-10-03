"""Storage utilities for persisting crawler results."""

from __future__ import annotations

import json
import logging
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional

import sqlite3

from .models import Record
from .utils import ensure_dir

logger = logging.getLogger(__name__)


@dataclass
class OutputSettings:
    sqlite_path: str = "data/results.db"
    jsonl_path: str = "data/results.jsonl"


class ResultWriter(AbstractContextManager):
    """Context manager that writes records to JSONL and SQLite."""

    def __init__(self, settings: OutputSettings) -> None:
        self.settings = settings
        self.jsonl_path = Path(settings.jsonl_path)
        self.sqlite_path = Path(settings.sqlite_path)
        ensure_dir(self.jsonl_path.parent)
        ensure_dir(self.sqlite_path.parent)
        self._jsonl_file = None
        self._conn: Optional[sqlite3.Connection] = None

    def __enter__(self) -> "ResultWriter":
        self._jsonl_file = self.jsonl_path.open("a", encoding="utf-8")
        self._conn = sqlite3.connect(self.sqlite_path)
        self._apply_migrations()
        return self

    def _apply_migrations(self) -> None:
        assert self._conn is not None
        cursor = self._conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS records (
                id TEXT PRIMARY KEY,
                kind TEXT,
                title TEXT,
                description TEXT,
                data JSON,
                created_at TEXT
            )
            """
        )
        self._conn.commit()

    def write_record(self, record: Record) -> None:
        payload = json.loads(record.json())
        line = json.dumps(payload, ensure_ascii=False)
        assert self._jsonl_file is not None and self._conn is not None
        self._jsonl_file.write(line + "\n")
        cursor = self._conn.cursor()
        cursor.execute(
            """
            INSERT OR REPLACE INTO records (id, kind, title, description, data, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                record.id,
                record.kind.value,
                record.title,
                record.description,
                json.dumps(payload, ensure_ascii=False),
                datetime.utcnow().isoformat(),
            ),
        )
        self._conn.commit()

    def close(self) -> None:
        if self._jsonl_file:
            self._jsonl_file.close()
        if self._conn:
            self._conn.close()

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()


def write_records(records: Iterable[Record], settings: OutputSettings) -> None:
    with ResultWriter(settings) as writer:
        for record in records:
            writer.write_record(record)
