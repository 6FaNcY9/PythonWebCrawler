# Legal, Modular Python Web Crawler

This project provides a policy-compliant, modular crawling framework for aggregating:

- Public documents from vetted sources (e.g., Internet Archive, government open data portals)
- Free-to-watch movies via official metadata APIs
- Product pricing from retailer APIs that allow aggregation

The architecture emphasizes compliance with robots.txt, rate limits, and terms of service. Each data source is implemented as an adapter that encapsulates discovery, fetching, and parsing logic.

## Features

- **Async HTTP client** with caching, robots.txt enforcement, exponential backoff, and per-domain rate limiting
- **Pydantic models** that normalize results into a consistent schema
- **Modular adapter system** for extending supported sources without modifying the core pipeline
- **Audit logging** for requests, including adapter decisions and payload sizes
- **Storage utilities** to persist results in JSONL and SQLite formats
- **CLI** powered by Typer for running crawls from the command line
- **Configuration system** using YAML/Pydantic with environment overrides

## Getting Started

1. Create and activate a Python 3.11+ virtual environment.
2. Install dependencies:

   ```bash
   pip install -e .[dev]
   ```

3. Create a `config.yaml` (optional) to override defaults such as API keys, adapter options, and output paths.
4. Run the crawler:

   ```bash
   python -m crawler.cli crawl --kind docs --query "machine learning" --max-results 100
   ```

Results are written to the configured JSONL and SQLite outputs. Audit logs and HTTP caches live under `.cache/` by default.

## Testing

Execute the test suite with:

```bash
pytest
```

Network calls are mocked in tests; live HTTP smoke tests can be added and toggled via environment flags when needed.
