# Architecture

## System Overview

Neolab Monitor scrapes AI research engineer job postings from six companies,
filters for research-relevant positions, detects new and removed jobs by
comparing against persisted history, and optionally sends email notifications.

## Package Structure

```
src/
├── __init__.py
├── config.py          # Environment configuration (Config dataclass)
├── filter.py          # Pure filtering and diff logic
├── engine.py          # Orchestration: scrape → diff → save → notify
├── notifier.py        # Email notification (HTML)
├── scraper/
│   ├── __init__.py
│   ├── base.py        # JobScraper ABC
│   ├── models.py      # Job, ScrapeResult, DiffResult
│   └── scrapers/      # Company-specific implementations
│       ├── anthropic.py
│       ├── openai.py
│       ├── deepmind.py
│       ├── xai.py
│       ├── seed.py
│       └── thinking_machines.py
└── storage/
    ├── __init__.py    # create_storage() factory
    ├── base.py        # StorageABC interface
    ├── file_storage.py
    └── gist_storage.py
tests/
├── __init__.py
├── test_filter.py     # filter_jobs + diff_jobs
├── test_models.py     # Job serialization + DiffResult
└── test_storage.py    # FileStorage roundtrip
main.py                # CLI entry point
```

## Data Flow

```
main.py (CLI)
    │
    ▼
Config.from_env() ──► Config dataclass
    │
    ▼
create_storage(config) ──► FileStorage | GistStorage
    │
    ▼
JobEngine(config, storage)
    │
    ├── scrape_all() ──► List[JobScraper].scrape() ──► Dict[str, List[Job]]
    │
    ├── load_previous_jobs() ──► Dict[str, List[Dict]] ──► convert to List[Job]
    │
    ├── compute_diff() ──► Dict[str, DiffResult]
    │
    ├── _display_results() ──► console output
    │
    ├── _save() ──► storage.save_jobs_history()
    │
    └── send_email() ──► EmailNotifier.send() ──► SMTP
```

## Component Responsibilities

### `Job` (src/scraper/models.py)
Immutable dataclass representing a single job posting. Serializes to/from dict
for storage persistence. Equality is based on `(title, company)`.

### `JobScraper` (src/scraper/base.py)
Abstract base class. Subclasses implement `scrape() -> List[Job]`. Each scraper
uses its own HTTP client session with appropriate headers.

### Companies and their data sources
| Company | Source | Method |
|---------|--------|--------|
| Anthropic | greenhouse.io | HTML parsing |
| OpenAI | ashbyhq.com | JSON from `window.__appData` |
| DeepMind | greenhouse.io API | JSON API |
| X.ai | greenhouse.io API | JSON API |
| ByteDance Seed | seed.bytedance.com | Multi-page HTML |
| Thinking Machines | ashbyhq.com | JSON from `window.__appData` |

### `filter_jobs` (src/filter.py)
Pure function. Takes `List[Job]` and optional blacklist, returns jobs whose
titles match any research keyword and no blacklist keyword.

### `diff_jobs` (src/filter.py)
Pure function. Compares current vs previous snapshots, returns `(new, removed)`.

### `JobEngine` (src/engine.py)
Wires together scrapers, storage, filter, and display. Single public method
`run(send_email=False)` drives the full pipeline.

### Storage
Two backends share the `StorageABC` interface:
- `FileStorage`: local JSON file (development / short-lived)
- `GistStorage`: private GitHub Gist (persistent across Heroku restarts)

### `EmailNotifier` (src/notifier.py)
Composes HTML email with sections for new jobs (green), removed jobs (red),
and full listings by company (blue).

## Design Decisions

1. **No external framework dependency** — the project runs on Python stdlib +
   `requests`, `beautifulsoup4`, `schedule`, `python-dotenv`.
2. **Abstract storage interface** — swapping backends (e.g. adding S3) requires
   only a new `StorageABC` implementation.
3. **Pure filter functions** — `filter_jobs` and `diff_jobs` have no side
   effects, making them trivially testable.
4. **Immutable Config** — `Config` is a frozen dataclass loaded once at startup.
5. **Lazy notifier import** — `EmailNotifier` is imported only when email is
   requested to avoid SMTP dependency in normal runs.
