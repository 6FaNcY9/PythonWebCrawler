"""Application configuration using Pydantic settings."""

from __future__ import annotations

import json
import logging
from importlib import import_module
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Type

try:
    import yaml
except ModuleNotFoundError:  # pragma: no cover - optional dependency for config files
    yaml = None

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from .adapters.base import BaseAdapter
from .core.storage import OutputSettings

logger = logging.getLogger(__name__)


class ConcurrencySettings(BaseModel):
    global_max_tasks: int = 20
    per_domain_rps: float = 1.5


class AdapterConfig(BaseModel):
    name: str
    options: Dict[str, object] = Field(default_factory=dict)


class FiltersConfig(BaseModel):
    language: List[str] = Field(default_factory=list)
    min_year: Optional[int] = None


class AppOutputSettings(OutputSettings):
    pass


class AppSettings(BaseSettings):
    user_agent: str = "MyCrawler/1.0 (+contact@example.com)"
    cache_dir: str = ".cache"
    concurrency: ConcurrencySettings = ConcurrencySettings()
    adapters: Sequence[AdapterConfig] = Field(default_factory=list)
    filters: FiltersConfig = FiltersConfig()
    output: AppOutputSettings = AppOutputSettings()

    model_config = SettingsConfigDict(env_prefix="CRAWLER_", arbitrary_types_allowed=True)

    def instantiate_adapters(self) -> List[BaseAdapter]:
        instances: List[BaseAdapter] = []
        for config in self.adapters:
            module = import_module(f"crawler.adapters.{config.name}")
            adapter_cls: Type[BaseAdapter] = getattr(module, "Adapter")
            instances.append(adapter_cls(settings=config.options | {"app_settings": self}))
        return instances


def load_settings(path: Optional[Path] = None) -> AppSettings:
    data = {}
    if path and path.exists():
        logger.info("Loading configuration from %s", path)
        if yaml is None:
            raise RuntimeError("PyYAML is required to load configuration files")
        with path.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
    return AppSettings(**data)
