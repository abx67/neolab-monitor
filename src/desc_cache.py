"""Description cache for job scrapers — avoids re-fetching on every run."""

import json
import os
import time
from typing import Optional


CACHE_FILE = "desc_cache.json"
DEFAULT_TTL_HOURS = 24


def _load_cache() -> dict:
    """Load the description cache from disk."""
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def _save_cache(cache: dict) -> None:
    """Persist the description cache to disk."""
    os.makedirs(os.path.dirname(CACHE_FILE) or ".", exist_ok=True)
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2)


def get_cached_description(key: str) -> Optional[str]:
    """Retrieve a cached description if it's still valid.

    Args:
        key: Cache key (e.g. "OpenAI:https://jobs.ashbyhq.com/openai/uuid").

    Returns:
        Cached description text, or None if not found or expired.
    """
    ttl_hours = int(os.getenv("DESC_CACHE_TTL_HOURS", DEFAULT_TTL_HOURS))
    cache = _load_cache()
    entry = cache.get(key)
    if not entry:
        return None
    cached_at = entry.get("cached_at", 0)
    if time.time() - cached_at > ttl_hours * 3600:
        # Expired
        del cache[key]
        _save_cache(cache)
        return None
    return entry.get("description", "")


def set_cached_description(key: str, description: str) -> None:
    """Store a fetched description in the cache.

    Args:
        key: Cache key (e.g. "OpenAI:https://jobs.ashbyhq.com/openai/uuid").
        description: The fetched description text.
    """
    cache = _load_cache()
    cache[key] = {
        "description": description,
        "cached_at": time.time(),
    }
    _save_cache(cache)
