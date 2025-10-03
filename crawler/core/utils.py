"""Utility helpers for the crawler."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Iterable

from difflib import SequenceMatcher

SLUGIFY_PATTERN = re.compile(r"[^a-z0-9]+")


def stable_hash(value: object) -> str:
    """Create a deterministic hash for the given value."""

    serialized = json.dumps(value, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(serialized).hexdigest()


def slugify(value: str) -> str:
    """Return a simple slug for filenames/logging."""

    value = value.lower()
    value = SLUGIFY_PATTERN.sub("-", value).strip("-")
    return value or "item"


def now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def fuzzy_equal(a: str, b: str, threshold: float = 0.8) -> bool:
    """Return True if strings are sufficiently similar."""

    ratio = SequenceMatcher(a=a.lower(), b=b.lower()).ratio()
    return ratio >= threshold


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def batched(iterable: Iterable, size: int):
    batch = []
    for item in iterable:
        batch.append(item)
        if len(batch) == size:
            yield batch
            batch = []
    if batch:
        yield batch
