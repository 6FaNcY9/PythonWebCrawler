"""Command line interface for the web crawler."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Optional

import typer

from .core.pipeline import crawl
from .settings import AppSettings, load_settings
from .core.storage import ResultWriter
from .core.models import Kind

app = typer.Typer(add_completion=False, no_args_is_help=True)


@app.command()
def crawl_command(
    kind: Kind = typer.Option(..., "--kind", case_sensitive=False, help="Type of content to crawl."),
    query: str = typer.Option(..., "--query", help="Search query."),
    max_results: int = typer.Option(200, "--max-results", help="Maximum results to collect."),
    out: Path = typer.Option(Path("data/results.jsonl"), "--out", help="Path to output JSONL file."),
    config: Optional[Path] = typer.Option(None, "--config", help="Path to configuration YAML file."),
) -> None:
    """Entry point for the crawler CLI."""

    settings = load_settings(config)
    settings = settings.model_copy(update={"output": settings.output.model_copy(update={"jsonl_path": str(out)})})

    records = asyncio.run(crawl(kind=kind, query=query, limit=max_results, settings=settings))

    out.parent.mkdir(parents=True, exist_ok=True)
    with ResultWriter(settings.output) as writer:
        for record in records:
            writer.write_record(record)
    typer.echo(json.dumps({"count": len(records), "output": str(out)}, indent=2))


if __name__ == "__main__":
    app()
