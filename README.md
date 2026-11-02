# Neolab Monitor

A Python scraper that monitors AI research engineer job postings from six leading companies, detects new and removed positions, and sends email notifications.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

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
- **Multi-Platform Description Fetching**: Auto-detects Greenhouse, Ashby, and Toutiao job boards; fetches full descriptions for better filtering
- **Smart Filtering**: Two-stage filter — title gate + description scoring with positive signals, soft/hard blacklists, and user interests
- **Relevance Ranking**: Jobs ranked by relevance score within each company (positive keywords + interest bonus - soft blacklist penalty)
- **Description Caching**: Fetched descriptions cached in `.slim/desc_cache.json` (24h TTL) to avoid re-fetching
- **LLM Classification** (optional): Use Agnes AI to classify jobs as relevant/possibly_relevant/not_relevant with confidence scores
- **Adaptive Feedback Loop**: Mark jobs as relevant or irrelevant via CLI; auto-learning improves filtering over time
- **New Job Detection**: Persistent history via GitHub Gist (free) or local file
- **Removed Job Tracking**: Know when positions are taken down
- **Email Notifications**: Formatted HTML emails with new/removed job highlights
- **Zero-Cost Deployment**: Runs free on Heroku with no paid addons

## Project Structure

```
neolab-monitor/
├── src/                    # Application code
│   ├── scraper/           # Scraper framework + company implementations
│   │   ├── base.py        # JobScraper ABC + platform-specific fetchers
│   │   ├── models.py      # Job, ScrapeResult, DiffResult
│   │   └── scrapers/      # Per-company scrapers
│   ├── storage/           # Storage backends
│   │   ├── base.py        # StorageABC interface
│   │   ├── file_storage.py
│   │   └── gist_storage.py
│   ├── config.py          # Environment configuration
│   ├── filter.py          # Job filtering + relevance scoring
│   ├── engine.py          # Orchestration pipeline
│   ├── notifier.py        # Email notifications
│   ├── llm_classifier.py  # Agnes AI LLM classification
│   ├── desc_cache.py      # Description caching
│   └── feedback.py        # Adaptive feedback loop
├── tests/                  # Unit tests
├── doc/                    # Documentation
│   ├── README.md
│   ├── architecture.md
│   ├── setup.md
│   └── contributing.md
├── main.py                 # CLI entry point
├── interests.json          # User interest preferences
├── requirements.txt
├── requirements-test.txt
├── Procfile               # Heroku worker config
└── .env.example
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GITHUB_TOKEN` | No | GitHub token for persistent storage (creates private Gist) |
| `GITHUB_GIST_ID` | No | Existing Gist ID (set after first run) |
| `SENDER_EMAIL` | No | Sender email for notifications |
| `SENDER_PASSWORD` | No | App password (Gmail: use App Password, not account password) |
| `RECIPIENT_EMAIL` | No | Recipient email |
| `SMTP_SERVER` | No | SMTP server (default: smtp.gmail.com) |
| `SMTP_PORT` | No | SMTP port (default: 587) |
| `SCRAPER_DEBUG` | No | Enable debug logging (1/true/yes/on) |
| `BLACKLIST_KEYWORDS` | No | Extra comma-separated words to exclude |
| `AGNES_API_KEY` | No | Agnes AI API key for LLM classification (`python main.py --llm`) |
| `DESC_CACHE_TTL_HOURS` | No | Description cache TTL in hours (default: 24) |
| `USER_INTERESTS_FILE` | No | Path to interests JSON file (default: `interests.json`) |

Without `GITHUB_TOKEN`, the scraper uses local file storage (`ai_jobs_history.json`). This works locally but is lost on Heroku restarts.

## User Interests

Create an `interests.json` file in the project root to personalize filtering:

```json
{
  "interests": [
    "reinforcement learning",
    "rl",
    "large language model",
    "llm",
    "transformer",
    "alignment",
    "interpretability",
    "reasoning"
  ]
}
```

Jobs matching your interests receive a scoring bonus in the relevance ranking.

## How It Works

### Filtering Pipeline

1. **Scrape**: Fetch job listings from each company's career page
2. **Title Gate**: Jobs must contain research-related keywords in the title
3. **Hard Blacklist**: Jobs with excluded roles (HR, marketing, sales, etc.) are filtered out
4. **Description Scoring**: For jobs with descriptions:
   - Count positive signals (RL, transformers, alignment, etc.)
   - Penalize soft-blacklisted terms (platform, product, SRE, etc.)
   - Bonus for user interest matches
5. **Ranking**: Filtered jobs are sorted by relevance score
6. **LLM Classification** (optional): Jobs can be classified via Agnes AI for additional accuracy

### Platform Support

| Company | Platform | Description Fetching |
|---------|----------|---------------------|
| Anthropic | Greenhouse | ✅ |
| DeepMind | Greenhouse | ✅ |
| X.ai | Greenhouse | ✅ |
| OpenAI | Ashby | ✅ |
| Thinking Machines | Ashby | ✅ |
| ByteDance Seed | Toutiao | ⚠️ Title-only (platform limitation) |

## Adaptive Feedback Loop

Learn from your signals to improve filtering over time. Mark jobs as relevant or irrelevant, and the system auto-extracts keywords to refine future runs.

### Usage

```bash
# First, run the scraper to populate job history:
python main.py

# Mark a job as relevant (suggests keywords to add):
python main.py --feedback --relevant --title "Research Engineer, RL"

# Mark a job as irrelevant (auto-blacklists keywords):
python main.py --feedback --irrelevant --title "Recruiter"

# View your feedback signals:
python main.py --feedback --list

# See feedback statistics:
python main.py --feedback --stats

# Clear all feedback:
python main.py --feedback --reset
```

### How It Works

1. **Run the scraper** to populate `ai_jobs_history.json` with current jobs
2. **Mark relevant jobs** — the system extracts keywords and adds them to auto-interests (boosts similar jobs)
3. **Mark irrelevant jobs** — the system extracts keywords and adds them to auto-blacklist (suppresses similar jobs)
4. **Future runs** automatically incorporate your feedback into relevance scoring

### Keywords

| Signal | Effect |
|--------|--------|
| `--relevant` | Adds extracted keywords to auto-interests (+0.5 score per match) |
| `--irrelevant` | Adds extracted keywords to auto-blacklist (-0.5 score per match) |

The title and description are scanned for meaningful phrases (2-4 words) to extract contextually relevant keywords.

## Known Limitations

- **ByteDance Seed**: Job descriptions cannot be fetched due to Toutiao's custom React structure. Filtering relies on titles only. LLM classification still works with title+location if enabled.

## Running Tests

```bash
pip install -r requirements-test.txt
python -m pytest tests/ -v
```

## Deployment

See [doc/setup.md](doc/setup.md) for full Heroku deployment instructions.

## Documentation

- [Architecture](doc/architecture.md) — system design and component responsibilities
- [Setup & Deployment](doc/setup.md) — Heroku deploy, env vars, troubleshooting
- [GitHub Token Guide](doc/github-token-guide.md) — step-by-step gist token setup
- [Contributing](doc/contributing.md) — adding new companies, code style

## License

MIT
