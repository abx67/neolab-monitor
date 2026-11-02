# neolab-monitor Project Tracking

## Goal
Monitor AI research/engineering job openings at top companies (Anthropic, OpenAI, DeepMind, X.ai, ByteDance Seed, Thinking Machines) and surface roles relevant to the user's background so they can apply.

## Milestone: v0.2 — Description-Aware Filtering
**Date:** 2026-08-11

### What's Done
- [x] Added `description` field to `Job` model
- [x] Added `fetch_job_description()` to base scraper (fetches full job page, extracts description from Greenhouse-hosted pages)
- [x] Updated Anthropic, DeepMind, XAI scrapers to fetch descriptions (up to 10 jobs per company)
- [x] Rewrote `filter.py` with title-gate + description scoring:
  - Two-stage filter: title gate → description scoring
  - Hard blacklist (word-boundary regex) — catches "biology", "chemistry", "recruit" etc.
  - Soft blacklist (word-boundary for short words, substring for phrases) — "data", "system", "product" etc.
  - 50+ positive research keywords (RL, transformers, alignment, etc.)
  - User interests bonus from `interests.json`
  - Jobs without descriptions fall back to title-only logic
- [x] Added `interests.json` to repo root for user preferences
- [x] Updated storage to handle new `description` field
- [x] All 35 tests pass

### Results (89 → 139 positions, +50%)
| Company | Before | After | Δ |
|---------|--------|-------|---|
| Anthropic | 24 | 46 | +22 |
| OpenAI | 13 | 28 | +15 |
| DeepMind | 2 | 3 | +1 |
| X.ai | 11 | 18 | +7 |
| ByteDance Seed | 4 | 9 | +5 |
| Thinking Machines | 35 | 35 | 0 |
| **Total** | **89** | **139** | **+50** |

### Files Changed
`src/filter.py`, `src/scraper/models.py`, `src/scraper/base.py`,
`src/scraper/scrapers/{anthropic,deepmind,xai}.py`,
`src/config.py`, `src/engine.py`, `tests/test_filter.py`

---

## Roadmap

### Phase 1: Quick Wins (✅ Done — Milestone v0.2)
- [x] Fetch job descriptions from individual posting pages
- [x] Fix aggressive blacklist (word-boundary matching, removed "data", "system", "comput" false positives)
- [x] Add description-aware scoring (positive signals + soft blacklist)
- [x] Add user interests file (`interests.json`)
- [x] Fallback to title-only for jobs without descriptions

### Phase 2: Medium Effort (✅ Done — Milestone v0.2.1)
- [x] **LLM-based classification** — `llm_classifier.py`, `--llm` flag, Agnes API integration
- [x] **Per-company description fetching** — Now all 6 companies fetch descriptions via platform-aware routing (Greenhouse/Ashby/Toutiao). Batch limit increased to 20.
- [x] **Description caching** — `desc_cache.py` with 24h TTL, persisted in `.slim/desc_cache.json`
- [x] **Ranking/sorting** — `rank_jobs()` scores by positive signals + soft blacklist + interest bonus
- [x] **Bug fix**: Enrichment moved after filtering so descriptions save to relevant jobs (not discarded ones)
- [x] **Bug fix**: Added "tutor" to hard blacklist, removing X.ai AI Tutor false positives

### Phase 3: Long Term (✅ Done — Milestone v0.3)
- [x] **Feedback loop** — `python main.py --feedback --relevant/--irrelevant --title "<job>"` stores signals in `.slim/feedback.json`; `--list`, `--stats`, `--reset`
- [x] **Auto-blacklist/whitelist** — Irrelevant jobs auto-extract and blacklist keywords; relevant jobs suggest keywords for interests
- [x] **Multi-signal scoring** — `score_job()` now incorporates feedback bias (auto-interests +0.5, auto-blacklist -0.5)
- [ ] Semantic similarity (deferred — needs embedding API)
- [ ] Expand company list (deferred — separate PR)
- [ ] Apply tracker (deferred — separate feature)

---

## How to Resume
Reference this doc and the current `interests.json` for personalization context.
The `baseline_jobs.json` file contains the last known job snapshot for comparison.
