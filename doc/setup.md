# Setup & Deployment

## Prerequisites

- Python 3.12 (pinned via `.python-version`)
- [uv](https://docs.astral.sh/uv/) (recommended) or pip
- Heroku CLI (for deployment)
- GitHub account (for persistent storage)
- Gmail account (for email notifications)

## Local Development

```bash
# Install dependencies (creates .venv and locks versions in uv.lock)
uv sync

# Copy environment template
cp .env.example .env
# Edit .env with your credentials

# Run once
uv run python main.py

# Run with email
uv run python main.py --email

# Run with scheduler (for local testing)
uv run python main.py --schedule

# Run tests
uv run pytest tests/ -v
```

<details>
<summary>Prefer pip?</summary>

```bash
pip install -r requirements.txt
pip install -r requirements-test.txt
python main.py
python -m pytest tests/ -v
```
</details>

## Heroku Deployment

### Step 1: Create a GitHub Gist Token

1. Go to https://github.com/settings/tokens
2. Click "Generate new token" → "Generate new token (classic)"
3. Note: "AI Jobs Scraper Token"
4. Expiration: "No expiration"
5. Scopes: check only **gist**
6. Click "Generate token" and copy the token (starts with `ghp_`)

### Step 2: Deploy

```bash
# Create Heroku app
heroku create your-app-name

# Set environment variables
heroku config:set GITHUB_TOKEN=ghp_your_token_here
heroku config:set SENDER_EMAIL=your-email@gmail.com
heroku config:set SENDER_PASSWORD=your-app-password
heroku config:set RECIPIENT_EMAIL=recipient@gmail.com

# Deploy
git push heroku main
```

### Step 3: First Run — Save Gist ID

After the first run, the log will show:
```
Created new Gist: abc123...
Set GITHUB_GIST_ID=abc123 to reuse this Gist
```

Capture this ID and set it:
```bash
heroku config:set GITHUB_GIST_ID=abc123
```

### Step 4: Set Up Daily Schedule

```bash
# Add scheduler addon (free)
heroku addons:create scheduler:standard

# Open scheduler dashboard
heroku addons:open scheduler

# Add job: Command = `python main.py --schedule`, Frequency = Daily at 9:00 AM UTC
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GITHUB_TOKEN` | No | GitHub token for persistent storage |
| `GITHUB_GIST_ID` | No | Existing Gist ID (set after first run) |
| `SENDER_EMAIL` | No | Sender email for notifications |
| `SENDER_PASSWORD` | No | App password (not regular Gmail password) |
| `RECIPIENT_EMAIL` | No | Recipient email |
| `SMTP_SERVER` | No | SMTP server (default: smtp.gmail.com) |
| `SMTP_PORT` | No | SMTP port (default: 587) |
| `SCRAPER_DEBUG` | No | Enable debug logging (1/true/yes/on) |
| `BLACKLIST_KEYWORDS` | No | Comma-separated additional blacklist words |

## Gmail Setup

1. Enable 2-factor authentication on your Google account
2. Go to https://myaccount.google.com/apppasswords
3. Generate an app password for "Mail"
4. Use this app password as `SENDER_PASSWORD`

## File-Based Storage (No GitHub Token)

If you don't set `GITHUB_TOKEN`, the scraper falls back to local file storage
(`ai_jobs_history.json`). This works for local development but **will be lost
on Heroku restarts** since the filesystem is ephemeral.

## Adding a New Company

1. Create `src/scraper/scrapers/<company>.py`
2. Subclass `JobScraper` and implement `scrape() -> List[Job]`
3. Add the scraper to `JobEngine._init_scrapers()` in `src/engine.py`
4. Optionally add to `Config.no_filter_companies` if all positions should be included

## Troubleshooting

### Storage Issues
```bash
heroku config -a your-app-name
heroku logs --tail -a your-app-name
```
Look for: `Created new Gist: abc123...` then set `GITHUB_GIST_ID`.

### Email Issues
- Use a Gmail app password, not your regular password
- Check spam folder
- Verify all three email vars are set: `SENDER_EMAIL`, `SENDER_PASSWORD`, `RECIPIENT_EMAIL`

### Scraper Issues
- Set `SCRAPER_DEBUG=1` to see raw HTML/JSON parsing details
- Check company career pages manually to verify selectors are still valid
