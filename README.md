# Neolab Monitor

A Python scraper that monitors AI research engineer job postings from six leading companies, detects new and removed positions, and sends email notifications.

## Quick Start

```bash
# Install dependencies (creates .venv + uv.lock)
uv sync

# Configure environment
cp .env.example .env
# Edit .env with your credentials

# Run once
python main.py

# Run with email
python main.py --email

# Run with scheduler (daily at 9:00 AM)
python main.py --schedule
```

## Features

- **Multi-Company Scraping**: Anthropic, OpenAI, DeepMind, X.ai, ByteDance Seed, Thinking Machines
- **Smart Filtering**: Research engineer/scientist positions, with configurable blacklists
- **New Job Detection**: Persistent history via GitHub repo, Gist (free) or local file
- **Removed Job Tracking**: Know when positions are taken down
- **Email Notifications**: Formatted HTML emails containing only the new/removed job highlights, plus a link to the latest live GitHub report (when using the git-repo backend)
- **Zero-Cost Deployment**: Runs free on Heroku with no paid addons

## Project Structure

```
neolab-monitor/
├── src/                    # Application code
│   ├── scraper/           # Scraper framework + company implementations
│   │   ├── base.py        # JobScraper ABC
│   │   ├── models.py      # Job, ScrapeResult, DiffResult
│   │   └── scrapers/      # Per-company scrapers
│   ├── storage/           # Storage backends
│   │   ├── base.py        # StorageABC interface
│   │   ├── file_storage.py
│   │   ├── gist_storage.py
│   │   └── git_repo_storage.py
│   ├── config.py          # Environment configuration
│   ├── filter.py          # Job filtering logic
│   ├── engine.py          # Orchestration
│   └── notifier.py        # Email notifications
├── tests/                  # Unit tests
├── doc/                    # Documentation
│   ├── README.md
│   ├── architecture.md
│   ├── setup.md
│   └── contributing.md
├── main.py                 # CLI entry point
├── pyproject.toml          # uv project definition (dependencies)
├── uv.lock                 # Locked dependency versions
├── .python-version         # Pinned Python version (3.12)
├── Procfile               # Heroku worker config
└── .env.example
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `RESULTS_GIT_REPO` | No | GitHub repo (`owner/name`) to commit results to (preferred) |
| `RESULTS_GIT_TOKEN` | No | Fine-grained PAT for the repo (falls back to `GITHUB_TOKEN`) |
| `RESULTS_GIT_BRANCH` | No | Branch to commit to (default: `main`) |
| `GITHUB_TOKEN` | No | GitHub token for persistent storage (creates private Gist) |
| `GITHUB_GIST_ID` | No | Existing Gist ID (set after first run) |
| `SENDER_EMAIL` | No | Sender email for notifications |
| `SENDER_PASSWORD` | No | App password (Gmail: use App Password, not account password) |
| `RECIPIENT_EMAIL` | No | Recipient email |
| `SMTP_SERVER` | No | SMTP server (default: smtp.gmail.com) |
| `SMTP_PORT` | No | SMTP port (default: 587) |
| `SCRAPER_DEBUG` | No | Enable debug logging (1/true/yes/on) |
| `BLACKLIST_KEYWORDS` | No | Extra comma-separated words to exclude |

Without `GITHUB_TOKEN`, the scraper uses local file storage (`ai_jobs_history.json`). This works locally but is lost on Heroku restarts.

## Versioning results in a git repo

The preferred persistent backend is a plain GitHub repo. Each run creates **one git commit** containing both the machine-readable `ai_jobs_history.json` snapshot and a rendered markdown report under `reports/` (the commit URL is printed to the logs).

- Set `RESULTS_GIT_REPO=owner/name` and `RESULTS_GIT_TOKEN` (a fine-grained PAT with `contents: write` on that repo; falls back to `GITHUB_TOKEN` if unset) and optionally `RESULTS_GIT_BRANCH` (default `main`).
- To track the latest results, open the newest commit at `https://github.com/{repo}/commits`, or browse the `reports/` directory on the configured branch for the human-readable markdown report; fetch the raw JSON via the raw URL for `ai_jobs_history.json`.
- `FileStorage` and GitHub Gist storage backends persist only the JSON snapshot — they ignore the rendered report.
- Gist storage remains the fallback when `RESULTS_GIT_REPO` is not set.
- Because state lives in the repo, results survive Heroku dyno restarts.

## Running Tests

```bash
uv run pytest tests/ -v
```

`uv sync` installs both the runtime and dev (test) dependencies into `.venv`.

## Deployment

See [doc/setup.md](doc/setup.md) for full Heroku deployment instructions.

## Documentation

- [Architecture](doc/architecture.md) — system design and component responsibilities
- [Setup & Deployment](doc/setup.md) — Heroku deploy, env vars, troubleshooting
- [GitHub Token Guide](doc/github-token-guide.md) — step-by-step gist token setup
- [Contributing](doc/contributing.md) — adding new companies, code style

## License

MIT
