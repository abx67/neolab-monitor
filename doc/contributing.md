# Contributing

## Project Structure

```
neolab-monitor/
├── src/                    # Application code
│   ├── scraper/           # Scraper framework + company implementations
│   ├── storage/           # Storage backends
│   ├── engine.py          # Orchestration
│   ├── notifier.py        # Email notifications
│   ├── config.py          # Configuration
│   └── filter.py          # Job filtering logic
├── tests/                  # Unit tests
├── doc/                    # Documentation
├── main.py                 # CLI entry point
├── requirements.txt        # Production dependencies
├── requirements-test.txt   # Test dependencies
└── Procfile               # Heroku worker config
```

## Running Tests

```bash
python -m pytest tests/ -v
```

## Adding a New Company Scraper

1. Create `src/scraper/scrapers/<company>.py`
2. Subclass `JobScraper`:

```python
from src.scraper.base import JobScraper
from src.scraper.models import Job
from typing import List

class MyCompanyScraper(JobScraper):
    def __init__(self):
        super().__init__("MyCompany", "https://careers.mycompany.com/jobs")

    def scrape(self) -> List[Job]:
        soup = self.fetch_page()
        if not soup:
            return []
        # ... parse and return List[Job]
```

3. Register in `src/engine.py` `JobEngine._init_scrapers()`:

```python
from src.scraper.scrapers.my_company import MyCompanyScraper

self.scrapers = [
    AnthropicScraper(),
    # ...
    MyCompanyScraper(),
]
```

4. Add tests in `tests/`

## Code Style

- Follow PEP 8
- Use type hints
- Keep scrapers focused: one company per file
- Keep filter logic pure (no side effects)
- No logging libraries — use `print()` for console output (Heroku-friendly)

## Commit Convention

Use concise commit messages:
- `feat: add XAI scraper`
- `fix: handle 403 from OpenAI`
- `docs: update architecture doc`
- `test: add diff_jobs edge cases`
