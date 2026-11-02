# LLM Classification

The optional LLM classification pass uses Agnes AI (`agnes-2.5-flash`) to classify jobs as `relevant`, `possibly_relevant`, or `not_relevant`. It runs after rule-based filtering and can filter out borderline cases that pass the keyword system.

## When It Runs

LLM classification is **disabled by default**. Enable it with:

```bash
python main.py --llm
```

Or with email notifications:
```bash
python main.py --email --llm
```

## Pipeline Position

```
scrape_all()
    ├── scrape each company → List[Job]
    ├── filter_jobs()        → rule-based filter (title gate + scoring)
    ├── rank_jobs()          → sort by relevance score
    ├── enrich_with_descriptions() → fetch job descriptions (after filter!)
    │
    └── [if --llm] classify_jobs_llm() → LLM classification
            └── filter_with_llm() → re-filter by LLM results
```

Key point: LLM classification runs **after** rule-based filtering. It sees only jobs that already passed the keyword filter, so it focuses on refining the signal rather than doing the heavy lifting.

## API Details

### Endpoint
- **URL**: `https://apihub.agnes-ai.com/v1/chat/completions`
- **Model**: `agnes-2.5-flash`
- **Auth**: Bearer token from `AGNES_API_KEY` env var
- **Format**: OpenAI-compatible chat completions API

### Request
```json
{
  "model": "agnes-2.5-flash",
  "messages": [
    {
      "role": "system",
      "content": "You are a job relevance classifier for AI research roles..."
    },
    {
      "role": "user",
      "content": "Job Title: Research Engineer, Performance RL\nLocation: San Francisco, CA\nCompany: Anthropic\nDescription: ...classified this job."
    }
  ],
  "temperature": 0.1,
  "max_tokens": 200
}
```

### Response
```json
{
  "choices": [{
    "message": {
      "content": "```json\n{\"category\": \"relevant\", \"confidence\": 0.98, \"reason\": \"...\"}\n```"
    }
  }]
}
```

The model may wrap JSON in markdown code blocks. The parser handles this automatically.

## Classification Categories

| Category | Description | Action |
|----------|-------------|--------|
| `relevant` | Clearly related to AI/ML research | Kept in results (marked with ⭐) |
| `possibly_relevant` | Might be research-related but uncertain | Kept if `include_possible=True` (default) |
| `not_relevant` | Not related to AI research (HR, marketing, etc.) | Excluded from results (marked with ✗) |
| `error` | LLM API failed to return valid classification | Falls back to rule-based (kept) |

## Retry Logic

Each job gets up to **3 retry attempts** with exponential backoff:

| Failure Mode | Behavior |
|-------------|----------|
| HTTP 429 (rate limit) | Retry after `Retry-After` header or 1s → 2s → 4s |
| HTTP 5xx (server error) | Retry with same backoff |
| Empty response body | Retry with same backoff |
| Invalid JSON from model | Retry with same backoff |
| Non-JSON Content-Type | Retry with same backoff |
| HTTP 400/401/403/404 | Fail immediately (non-retryable) |
| Network timeout/error | Retry with same backoff |

After 3 failed attempts, the job is marked with `category: "error"` and falls back to rule-based filtering (kept in results).

## Rate Limiting

A **1-second delay** is enforced between consecutive API calls to respect rate limits:

```python
if i < len(to_classify) - 1:
    time.sleep(1.0)
```

With the default limit of 10 jobs per company, this adds ~10 seconds per company.

## Job Limit Per Company

Only the **first 10 jobs** per company are classified via LLM. This is configurable via the `limit` parameter:

```python
classified = classify_jobs_llm(jobs, limit=10)
```

The 10-job limit exists because:
1. Rule-based filtering already reduced the pool to research-relevant jobs
2. LLM calls cost money per request
3. Top-ranked jobs are the most important to classify accurately

## JSON Extraction

The model may return responses in various formats. The parser handles all of them:

```python
# Direct JSON (preferred)
{"category": "relevant", "confidence": 0.95, "reason": "..."}

# Markdown code block
```json
{"category": "relevant", "confidence": 0.95, "reason": "..."}
```

# With extra text
Here's the classification: {"category": "relevant", "confidence": 0.95, "reason": "..."}
```

Extraction steps:
1. Strip ` ```json ` and ` ``` ` markers if present
2. Try direct `json.loads()`
3. Find `{` and `}` boundaries and extract the object
4. Return `None` if all attempts fail → triggers retry

## Error Handling

Failed classifications don't drop jobs. Instead:

1. Job gets `llm_classification = {"category": "error", ...}` attached
2. `filter_with_llm()` with `fallback_to_rule_based=True` keeps the job
3. Console shows `✗ error` for the failed job

```python
# In engine.py:
llm_filtered = filter_with_llm(classified, include_possible=True, fallback_to_rule_based=True)
```

## System Prompt

```
You are a job relevance classifier for AI research roles.
Given a job title and description, classify it into one of these categories:
- "relevant": The job is clearly related to AI/ML research (e.g., RL, LLMs, transformers, alignment, interpretability, AGI, agents, multimodal, scaling, pre-training, post-training, foundation models)
- "possibly_relevant": The job might be research-related but needs more info (e.g., generic "Research Engineer" without specifics, or borderline cases)
- "not_relevant": The job is not related to AI research (e.g., HR, marketing, sales, security engineering, platform engineering, general SWE)

Return ONLY a JSON object with no explanation:
{"category": "relevant|possibly_relevant|not_relevant", "confidence": 0.0-1.0, "reason": "brief reason"}
```

## User Prompt Template

```
Job Title: {title}
Location: {location}
Company: {company}
Description: {description}

Classify this job.
```

The description is truncated to 3000 characters to control token usage.

## Cost Estimation

At ~350 tokens per request (system + user prompt) and ~50 tokens response:
- 60 jobs per run × ~$0.0001 per 1K tokens ≈ **~$0.006 per full run**
- With 10-job limit per company: ~60 calls × ~$0.0001 = **~$0.006 per run**

Actual costs depend on the Agnes API pricing.

## Files

| File | Purpose |
|------|---------|
| `src/llm_classifier.py` | LLM classification logic, retry, JSON extraction |
| `AGNES_API_KEY` env var | API authentication |

## Integration with Filtering

The LLM pass is additive — it refines rather than replaces rule-based filtering:

```
Rule-based filter:     49 jobs → LLM filter:           48 jobs (1 dropped)
Rule-based filter:     28 jobs → LLM filter:           28 jobs (0 dropped)
Rule-based filter:      5 jobs → LLM filter:            5 jobs (0 dropped, 2 errors fallback)
Rule-based filter:     18 jobs → LLM filter:           17 jobs (1 dropped, 3 errors fallback)
```

Jobs that fail LLM classification are **kept** (fallback), so the LLM pass can only reduce the result set, never increase it.
