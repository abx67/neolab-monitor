# Adaptive Feedback System

The feedback system lets you teach the scraper what you care about. Over time, it learns from your signals and automatically adjusts which jobs rank higher or lower.

## Quick Start

```bash
# Run the scraper first to populate job history
python main.py

# Mark a job as relevant
python main.py --feedback --relevant --title "Research Engineer, RL"

# Mark a job as irrelevant
python main.py --feedback --irrelevant --title "Recruiter"

# View your signals
python main.py --feedback --list

# See statistics
python main.py --feedback --stats

# Clear all feedback
python main.py --feedback --reset
```

## How It Works

### Step 1: Run the Scraper

Before giving feedback, run the scraper at least once to populate `ai_jobs_history.json`:

```bash
python main.py
```

This creates a history of all current jobs across all companies. The feedback system matches your title against this history to find the exact job.

### Step 2: Give Feedback

**Mark relevant:**
```bash
python main.py --feedback --relevant --title "Research Engineer, Performance RL"
```

The system finds the matching job, extracts keywords from its title and description, and stores them as **auto-interests**. Future jobs matching these keywords get a +0.5 score bonus.

**Mark irrelevant:**
```bash
python main.py --feedback --irrelevant --title "Engineering Manager"
```

The system extracts keywords and stores them as **auto-blacklist**. Future jobs matching these keywords get a -0.5 score penalty AND are harder-filtered.

### Step 3: Automatic Learning

On every subsequent `python main.py` run, the feedback data is loaded and merged into the filtering pipeline:

- **Auto-interests** are passed to `rank_jobs()` — boosting relevant-sounding jobs
- **Auto-blacklist** is merged into `filter_jobs()` — suppressing unwanted keywords

You don't need to do anything manually. The system improves with each signal you give.

## Data Structure

Feedback is stored in `feedback.json` at the project root:

```json
{
  "signals": [
    {
      "title": "Recruiter, AI Research",
      "company": "Anthropic",
      "signal": "irrelevant",
      "timestamp": "2026-08-12T21:26:06.361397",
      "keywords": ["ai research"]
    },
    {
      "title": "Research Engineer, Performance RL",
      "company": "Anthropic",
      "signal": "relevant",
      "timestamp": "2026-08-12T22:15:00.123456",
      "keywords": ["research engineer", "performance rl"]
    }
  ],
  "auto_blacklist": ["ai research"],
  "auto_interests": ["research engineer", "performance rl"]
}
```

### Fields

| Field | Description |
|-------|-------------|
| `signals` | List of all feedback entries, newest last |
| `signals[].title` | The job title you marked |
| `signals[].company` | The company (auto-matched from history) |
| `signals[].signal` | `"relevant"` or `"irrelevant"` |
| `signals[].timestamp` | ISO 8601 timestamp |
| `signals[].keywords` | Extracted phrases from title + description |
| `auto_blacklist` | Union of all keywords from irrelevant signals |
| `auto_interests` | Union of all keywords from relevant signals |

## Keyword Extraction

When you mark a job, the system extracts meaningful phrases from the title and description:

### From Title
Extracts 2–4 word noun phrases, skipping common stop words ("the", "a", "and", "Research", "Engineer", "Scientist", etc.):

```
"Research Engineer, Machine Learning (Reinforcement Learning)"
→ ["research engineer", "machine learning", "reinforcement learning"]
```

### From Description
Extracts frequent long words (4+ chars) that aren't common boilerplate:

```
"Work on RL algorithms for large language models and alignment..."
→ ["reinforcement", "algorithms", "language", "models", "alignment"]
```

### Combined
Title and description keywords are merged, deduplicated, and limited to the top phrases.

## Scoring Impact

Feedback affects the relevance score in `score_job()`:

```
score = positive_signals
      - soft_blacklist_penalty * 0.5
      + interest_bonus * 0.5
      + feedback_score          ← new
      + description_bonus (if desc > 20 chars)
```

Where `feedback_score` is:
- **+0.5** for each auto-interest keyword match
- **-0.5** for each auto-blacklist keyword match

### Example

Without feedback:
```
"Research Engineer, RL" → score = 3 (from positive signals)
```

After marking "RL engineering" as relevant:
```
"Research Engineer, RL" → score = 3 + 0.5 = 3.5  (boosted)
"Data Engineer, ETL"    → score = 1 + 0.5 = 1.5  (boosted by "data engineer")
"Marketing Manager"     → score = 0 - 0.5 = -0.5  (suppressed by blacklist)
```

## CLI Reference

| Command | Description |
|---------|-------------|
| `--feedback --relevant --title "<query>"` | Mark a job as relevant; extracts and saves keywords |
| `--feedback --irrelevant --title "<query>"` | Mark a job as irrelevant; extracts and blacklists keywords |
| `--feedback --list` | Show all feedback signals with keywords |
| `--feedback --stats` | Show total signals, relevant/irrelevant counts, keyword counts |
| `--feedback --reset` | Clear all feedback data |

### Title Matching

The `--title` argument does a **case-insensitive partial match** against job titles in `ai_jobs_history.json`. You don't need to type the full title:

```bash
# These all work:
python main.py --feedback --relevant --title "Research Engineer RL"
python main.py --feedback --relevant --title "RL"
python main.py --feedback --irrelevant --title "Recruiter"
```

If multiple jobs match, the first one found wins. If no job matches, you'll see an error提示.

## Files

| File | Purpose |
|------|---------|
| `src/feedback.py` | `FeedbackStore` class — load/save signals, extract keywords, compute stats |
| `feedback.json` | Persisted feedback data (gitignored) |
| `tests/test_feedback.py` | Unit tests for all feedback operations |

## Best Practices

1. **Be specific** — Use as much of the title as possible for accurate matching
2. **Run the scraper first** — `python main.py` must have run to populate history
3. **Give both signals** — Mark some relevant AND some irrelevant for best results
4. **Review periodically** — Use `--stats` to see how many signals you have
5. **Reset if needed** — Use `--reset` to start fresh if feedback goes wrong
