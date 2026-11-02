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
├── filter.py          # Pure filtering, scoring + diff logic
├── engine.py          # Orchestration: scrape → diff → save → notify
├── notifier.py        # Email notification (HTML)
├── llm_classifier.py  # Agnes AI LLM classification
├── desc_cache.py      # Description caching (file-based, 24h TTL)
└── feedback.py        # Adaptive feedback loop
└── scraper/
    ├── __init__.py
    ├── base.py        # JobScraper ABC + platform-specific fetchers
    ├── models.py      # Job, ScrapeResult, DiffResult
    └── scrapers/      # Company-specific implementations
        ├── anthropic.py
        ├── openai.py
        ├── deepmind.py
        ├── xai.py
        ├── seed.py
        └── thinking_machines.py
└── storage/
    ├── __init__.py    # create_storage() factory
    ├── base.py        # StorageABC interface
    ├── file_storage.py
    └── gist_storage.py
tests/
├── __init__.py
├── test_filter.py     # filter_jobs, score_job, rank_jobs + diff_jobs
├── test_models.py     # Job serialization + DiffResult
└── test_storage.py    # FileStorage roundtrip
main.py                # CLI entry point
interests.json         # User interest preferences
desc_cache.json  # Cached job descriptions (generated)
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

**Platform-specific description fetching:**
- `fetch_job_description()` — Greenhouse-hosted pages (Anthropic, DeepMind, X.ai)
- `fetch_job_description_ashby()` — Ashby-hosted pages (OpenAI, Thinking Machines); parses `window.__appData` JSON for `posting.descriptionHtml`
- `fetch_job_description_toutiao()` — Toutiao-hosted pages (ByteDance Seed)
- `_fetch_description_for_url()` — Auto-detects platform from URL domain and routes to appropriate fetcher via `PLATFORM_FETCHERS` registry
- `enrich_with_descriptions()` — Fetches descriptions for a batch of jobs (limited to 10 per call)

**Description caching:**
- `desc_cache.py` provides file-based caching at `desc_cache.json`
- Cache key: `{company}:{url}`, TTL configurable via `DESC_CACHE_TTL_HOURS` (default 24h)
- Auto-populated on first fetch; subsequent runs check cache before requesting

### Companies and their data sources
| Company | Platform | Scraping Method | Description Fetching |
|---------|----------|----------------|---------------------|
| Anthropic | Greenhouse | HTML parsing | ✅ CSS selectors |
| OpenAI | Ashby | `window.__appData` JSON | ✅ JSON extraction |
| DeepMind | Greenhouse API | JSON API | ✅ CSS selectors |
| X.ai | Greenhouse API | JSON API | ✅ CSS selectors |
| ByteDance Seed | Toutiao | Multi-page HTML | ⚠️ Title-only (platform limitation) |
| Thinking Machines | Ashby | `window.__appData` JSON | ✅ JSON extraction |

### `filter_jobs` (src/filter.py)
Pure function. Two-stage filtering:
1. **Title gate**: Job title must contain a research keyword
2. **Description scoring**: If description exists, score using:
   - Positive signals (RL, transformers, alignment, etc.)
   - Soft blacklist penalty (platform, product, SRE, etc.)
   - Hard blacklist exclusion (HR, marketing, sales, etc.)
   - User interest bonus from `interests.json`
3. **Ranking**: `rank_jobs()` sorts filtered jobs by relevance score descending

Also exports `score_job()` for per-job relevance scoring.

### `diff_jobs` (src/filter.py)
Pure function. Compares current vs previous snapshots, returns `(new, removed)`.

### `JobEngine` (src/engine.py)
Wires together scrapers, storage, filter, and display. Public methods:
- `scrape_all(llm_enabled=False)` — scrapes all companies, filters, ranks, and optionally runs LLM classification
- `run(send_email=False, llm_enabled=False)` — full pipeline: scrape → diff → display → save → notify
- `compute_diff(current, previous)` — returns per-company new/removed job lists

### `llm_classifier` (src/llm_classifier.py)
Optional LLM-based classification using Agnes AI (`agnes-2.5-flash`).
- `classify_jobs_llm(jobs, limit=20)` — classifies jobs with retry/backoff (max 3 attempts)
- `filter_with_llm(jobs, include_possible=True)` — filters by LLM results
- Classification categories: `relevant`, `possibly_relevant`, `not_relevant`
- Requires `AGNES_API_KEY` env var; disabled by default (use `--llm` CLI flag)

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
3. **Pure filter functions** — `filter_jobs`, `score_job`, and `diff_jobs` have no side
   effects, making them trivially testable.
4. **Immutable Config** — `Config` is a frozen dataclass loaded once at startup.
5. **Lazy notifier import** — `EmailNotifier` is imported only when email is
   requested to avoid SMTP dependency in normal runs.
6. **Platform-agnostic description fetching** — URL-domain detection routes to
   the appropriate fetcher (Greenhouse, Ashby, or Toutiao) via a registry pattern.
7. **Description caching** — avoids re-fetching on every run; cached descriptions
   are stored in `desc_cache.json` with configurable TTL.
8. **Optional LLM classification** — LLM pass is opt-in (`--llm` flag) and runs
   after rule-based filtering, providing a safety net for borderline cases.
9. **Adaptive feedback** — user signals (`--feedback`) learn over time, adjusting
   relevance scores via auto-interests and auto-blacklist keywords.
