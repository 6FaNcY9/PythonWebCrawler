"""Top-level package for the modular, policy-compliant web crawler."""

from .settings import AppSettings, load_settings
from .cli import app
from .core.models import Record
from .core.pipeline import crawl

__all__ = ["AppSettings", "Record", "load_settings", "crawl", "app"]
