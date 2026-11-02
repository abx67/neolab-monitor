"""LLM-based job classification using Agnes AI API."""

import json
import os
import re
import time
from typing import List, Optional

import requests

from src.scraper.models import Job


# OpenAI-compatible endpoint for Agnes
AGNES_API_URL = "https://apihub.agnes-ai.com/v1/chat/completions"
AGNES_MODEL = "agnes-2.5-flash"

SYSTEM_PROMPT = """You are a job relevance classifier for AI research roles.
Given a job title and description, classify it into one of these categories:
- "relevant": The job is clearly related to AI/ML research (e.g., RL, LLMs, transformers, alignment, interpretability, AGI, agents, multimodal, scaling, pre-training, post-training, foundation models)
- "possibly_relevant": The job might be research-related but needs more info (e.g., generic "Research Engineer" without specifics, or borderline cases)
- "not_relevant": The job is not related to AI research (e.g., HR, marketing, sales, security engineering, platform engineering, general SWE)

Return ONLY a JSON object with no explanation:
{"category": "relevant|possibly_relevant|not_relevant", "confidence": 0.0-1.0, "reason": "brief reason"}"""

USER_PROMPT_TEMPLATE = """Job Title: {title}
Location: {location}
Company: {company}
Description: {description}

Classify this job."""


def _get_api_key() -> Optional[str]:
    """Get Agnes API key from environment."""
    # Ensure .env is loaded (in case caller didn't)
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
    return os.getenv("AGNES_API_KEY")


def _get_retry_after(response: requests.Response) -> Optional[float]:
    """Extract the Retry-After header value in seconds, if present.

    Handles the common case where the header is a number of seconds.
    Returns None if the header is absent or cannot be parsed.
    """
    retry_after = response.headers.get("Retry-After")
    if not retry_after:
        return None
    try:
        return float(retry_after)
    except ValueError:
        return None


def _extract_json_from_content(content: str) -> Optional[str]:
    """Extract JSON object from model response content.

    Handles the case where the model wraps JSON in markdown code blocks,
    adds extra text around the JSON, or returns pretty-printed JSON.

    Args:
        content: Raw model output string.

    Returns:
        Extracted JSON string, or None if extraction fails.
    """
    if not content:
        return None

    # Step 1: Strip markdown code block markers
    text = content.strip()
    if text.startswith("```"):
        # Remove opening ```[json]
        text = text[3:].lstrip()
        if text.lower().startswith("json"):
            text = text[4:].lstrip()
        # Remove closing ```
        if text.endswith("```"):
            text = text[:-3].rstrip()

    # Step 2: Try direct JSON parse
    try:
        json.loads(text)
        return text
    except json.JSONDecodeError:
        pass

    # Step 3: Find JSON object boundaries by matching braces
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidate = text[start:end + 1]
        try:
            json.loads(candidate)
            return candidate
        except json.JSONDecodeError:
            pass

    return None


def _llm_classify_job(job: Job, api_key: str) -> Optional[dict]:
    """Call Agnes API to classify a single job.

    Retries with exponential backoff on transient failures (HTTP 429 and
    5xx server errors, empty responses, and malformed model output).
    After exhausting all retries, returns None so the caller can apply
    fallback logic.
    """
    description = (job.description or "").strip()
    if len(description) > 3000:
        description = description[:3000] + "..."

    user_prompt = USER_PROMPT_TEMPLATE.format(
        title=job.title,
        location=job.location,
        company=job.company,
        description=description or "(no description available)",
    )

    payload = {
        "model": AGNES_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.1,
        "max_tokens": 200,
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    max_attempts = 3
    initial_delay = 1.0

    for attempt in range(max_attempts):
        try:
            resp = requests.post(AGNES_API_URL, headers=headers, json=payload, timeout=30)

            # Handle non-200 status codes
            if resp.status_code != 200:
                # Retry on 429 (rate limit) or 5xx (server errors)
                if resp.status_code == 429 or (500 <= resp.status_code < 600):
                    if attempt < max_attempts - 1:
                        retry_after = _get_retry_after(resp)
                        delay = retry_after if retry_after is not None else initial_delay * (2 ** attempt)
                        print(f"  LLM rate-limited/server error (HTTP {resp.status_code}), "
                              f"retrying in {delay}s (attempt {attempt + 1}/{max_attempts})...")
                        time.sleep(delay)
                        continue
                    else:
                        print(f"  LLM classification failed after {max_attempts} attempts "
                              f"(HTTP {resp.status_code}) for '{job.title}'")
                        return None
                else:
                    # Non-retryable HTTP error (e.g. 400, 401, 403, 404)
                    print(f"  LLM classification error for '{job.title}': HTTP {resp.status_code}")
                    return None

            # Check content type — some errors return HTML despite 200 status
            content_type = resp.headers.get("Content-Type", "")
            if "text/html" in content_type or "text/plain" in content_type:
                if attempt < max_attempts - 1:
                    delay = initial_delay * (2 ** attempt)
                    print(f"  LLM unexpected content type ({content_type}), "
                          f"retrying in {delay}s (attempt {attempt + 1}/{max_attempts})...")
                    time.sleep(delay)
                    continue
                else:
                    print(f"  LLM classification failed: unexpected content type {content_type} "
                          f"for '{job.title}'")
                    return None

            data = resp.json()
            raw_content = data["choices"][0]["message"]["content"].strip()

            if not raw_content:
                # Empty response — transient, retry
                if attempt < max_attempts - 1:
                    delay = initial_delay * (2 ** attempt)
                    print(f"  LLM empty response, retrying in {delay}s "
                          f"(attempt {attempt + 1}/{max_attempts}) for '{job.title}'...")
                    time.sleep(delay)
                    continue
                else:
                    print(f"  LLM classification failed: empty response for '{job.title}'")
                    return None

            # Extract JSON from content (handles markdown code blocks)
            json_content = _extract_json_from_content(raw_content)
            if json_content is None:
                # Malformed model output — transient, retry
                if attempt < max_attempts - 1:
                    delay = initial_delay * (2 ** attempt)
                    print(f"  LLM malformed output, retrying in {delay}s "
                          f"(attempt {attempt + 1}/{max_attempts}) for '{job.title}'...")
                    time.sleep(delay)
                    continue
                else:
                    print(f"  LLM classification error for '{job.title}': "
                          f"model returned invalid JSON: {raw_content[:100]}...")
                    return None

            result = json.loads(json_content)
            return {
                "category": result.get("category", "possibly_relevant"),
                "confidence": float(result.get("confidence", 0.5)),
                "reason": result.get("reason", ""),
            }

        except requests.RequestException as e:
            # Network-level errors (timeouts, connection errors) — retry with backoff
            if attempt < max_attempts - 1:
                delay = initial_delay * (2 ** attempt)
                print(f"  LLM request error (attempt {attempt + 1}/{max_attempts}): {e}. "
                      f"Retrying in {delay}s...")
                time.sleep(delay)
                continue
            else:
                print(f"  LLM classification error for '{job.title}': {e}")
                return None
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            # Response parsing errors — retry for transient issues
            if attempt < max_attempts - 1:
                delay = initial_delay * (2 ** attempt)
                print(f"  LLM parse error (attempt {attempt + 1}/{max_attempts}): {e}. "
                      f"Retrying in {delay}s for '{job.title}'...")
                time.sleep(delay)
                continue
            else:
                print(f"  LLM classification error for '{job.title}': {e}")
                return None


def classify_jobs_llm(
    jobs: List[Job],
    api_key: Optional[str] = None,
    limit: int = 20,
) -> List[Job]:
    """Classify jobs using LLM and attach classification results.

    Args:
        jobs: Jobs to classify.
        api_key: Agnes API key. Falls back to AGNES_API_KEY env var.
        limit: Maximum number of jobs to classify per run.

    Returns:
        Jobs with 'llm_classification' attribute attached.
    """
    key = api_key or _get_api_key()
    if not key:
        print("  ⚠️  AGNES_API_KEY not set. Skipping LLM classification.")
        return jobs

    to_classify = jobs[:limit]
    classified_count = 0

    print(f"  🤖 LLM classifying {len(to_classify)} jobs via Agnes...")

    for i, job in enumerate(to_classify):
        result = _llm_classify_job(job, key)
        if result:
            job.llm_classification = result  # type: ignore[attr-defined]
            classified_count += 1
            status = "✓" if result["category"] == "relevant" else "✗" if result["category"] == "not_relevant" else "?"
            print(f"    [{i+1}/{len(to_classify)}] {status} {result['category']} "
                  f"(conf={result['confidence']:.2f}) — {job.title[:50]}...")
        else:
            # Mark as error but don't drop — filter_with_llm will fall back
            job.llm_classification = {"category": "error", "confidence": 0.0, "reason": "API error"}  # type: ignore[attr-defined]
            print(f"    [{i+1}/{len(to_classify)}] ✗ error — {job.title[:50]}...")

        # Rate limiting: delay between requests
        if i < len(to_classify) - 1:
            time.sleep(1.0)

    print(f"  ✓ LLM classified {classified_count}/{len(to_classify)} jobs")
    return jobs


def filter_with_llm(
    jobs: List[Job],
    api_key: Optional[str] = None,
    include_possible: bool = True,
    fallback_to_rule_based: bool = True,
) -> List[Job]:
    """Filter jobs using LLM classification results.

    Args:
        jobs: Already-classified jobs (with llm_classification attribute).
        api_key: Not used here, classification should be done first.
        include_possible: Whether to include 'possibly_relevant' jobs.
        fallback_to_rule_based: When True, jobs with LLM errors fall back to
            being included (rule-based filter already ran). When False, they
            are excluded.

    Returns:
        Filtered list of relevant jobs.
    """
    result = []
    for job in jobs:
        classification = getattr(job, "llm_classification", None)
        if classification is None:
            # No LLM classification — keep (rule-based filter already ran)
            result.append(job)
            continue

        category = classification.get("category", "")
        if category == "relevant":
            result.append(job)
        elif category == "possibly_relevant" and include_possible:
            result.append(job)
        elif category == "error" and fallback_to_rule_based:
            # LLM failed — fall back to keeping the job (rule-based filter already passed it)
            result.append(job)
        # "not_relevant" is excluded; "error" without fallback is excluded

    return result
