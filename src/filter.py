"""Job filtering logic — title + description based classification."""

import json
import os
import re
from typing import List, Optional

from src.scraper.models import Job


# ── Positive signals: keywords/phrases that indicate a research role ─────────

# Must appear in title (gate) — any of these keeps the job in play
TITLE_GATE_KEYWORDS = [
    "research engineer",
    "research scientist",
    "research scientist/engineer",
    "research scientist / engineer",
    "machine learning engineer",
    "ml engineer",
    "research manager",
    "staff research engineer",
    "senior research engineer",
    "principal research engineer",
    "ai research",
    "research operations",
    "research recruiting",
    "human-ai collaboration research engineer",
    "lead research engineer",
    "researcher engineer",
    "member of technical staff",
    "research scientist, ",
    "research engineer, ",
    " research, ",  # catches "Software Engineer, Research" etc.
    " research.",  # catches "Research." at end
    "research ",   # catches "research" at start or standalone
    "research,",   # catches "Research, Audio Expertise" etc.
]

# Strong positive signals found in description or title — high relevance
DESCRIPTION_POSITIVE_KEYWORDS = [
    "reinforcement learning",
    "rl",
    "transformer",
    "large language model",
    "llm",
    "foundation model",
    "pre-training",
    "post-training",
    "alignment",
    "interpretability",
    "representational",
    "scaling law",
    "model training",
    "model evaluation",
    "multimodal",
    "computer vision",
    "reasoning",
    "language model",
    "natural language processing",
    "nlp",
    "generative model",
    "generative ai",
    "agent",
    "agentic",
    "safety research",
    "ai safety",
    "ai alignment",
    "rlhf",
    "constitutional ai",
    "pretrain",
    "backprop",
    "optimization algorithm",
    "training data",
    "inference engine",
    "kernel",
    "distributed training",
    "distributed system*",
    "system research",
    "computational",
    "code generation",
    "codex",
    "tool use",
    "function calling",
    "retrieval augmented generation",
    "rag",
    "personalization",
    "personality",
    "model behavior",
    "embodied",
    "robotics",
    "speech",
    "audio",
    "vision",
    "multimodal understanding",
    "media generation",
    "image generation",
    "video generation",
    "world model",
    "world modelling",
    "information literacy",
    "material science",
    "life science",
    "discovery",
    "tokens",
    "knowledge",
    "memory",
    "proactivity",
    "performance",
    "velocity",
    "infra",
    "infrastructure",
    "developer experience",
    "tinker",
    "supercomput",
    "cloud infra",
    "ads",
    "sandbox",
]

# Hard blacklist: these exclude regardless of context
HARD_BLACKLIST = [
    "safeguard",
    "recruit",
    "research operations",
    "research recruiting",
    "biology",
    "biological",
    "chemistry",
    "chemist",
    "atomistic",
    "computational biology",
    "honesty",
    "education",
    "investigat",
    "threat",
    "legal",
    "business development",
    "marketing",
    "sales",
    "finance",
    "people operations",
    "hr",
    "human resources",
    "intern",
    "trainee",
    "tutor",
    "trust and safety",
    "trust & safety",
    "deploy",
    "deployment engineer",
    "robust",
    "evaluator",
    "rater",
    "weather",
    "notification",
    "cyber",
    "biolog",
    "community manager",
    "graduate program",
    "graduate student",
]

# Soft blacklist: exclude unless description has a strong positive signal
SOFT_BLACKLIST = [
    "data",           # "data" alone is ambiguous; "research data" is OK
    "system",         # "systems" is ambiguous; "system research" is OK
    "comput",         # "comput" blocks "computational"
    "optim",          # "optim" blocks "optimization"
    "integr",         # "integr" blocks "integration"
    "security",       # security research can be valid; soft exclude
    "platform",       # platform engineering ≠ research
    "product",        # product roles ≠ research
    "design",         # design roles ≠ research
    "university",     # academic affiliations
    "phd",            # "phd" in title usually means "phd program" not research role
    "operation",      # operations ≠ research
    "manager",        # management ≠ individual research contributor
    "sre",            # site reliability
    "site reliability",
    "sourcer",
    "recruiting",
    "recruiter",
    "manager",
    "economi",
    "distributed",
    "business partner",
    "graduate",
    "governance",
    "endpoint",
    "business",
    "governance",
    "IT Engineer",
    "compliance",
    "safeguards",
    "scalabilit",
    "efficient",
    "inference",      # inference engineering (not research)
    "compil",         # compilation engineering
    "govern",
    "quant",
    "environment",
    "notif",
    "saf",
]


def _load_user_interests(path: Optional[str] = None) -> List[str]:
    """Load user interests from a JSON file.

    Defaults to `interests.json` in the current working directory (the repo root).
    Falls back to `~/.neolab_interests.json` if the default path doesn't exist.
    """
    if path is None:
        path = "interests.json"
    if not path or not os.path.exists(path):
        # Fallback to home directory for backwards compatibility
        fallback = os.path.expanduser("~/.neolab_interests.json")
        if os.path.exists(fallback):
            path = fallback
        else:
            return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        interests = data.get("interests", [])
        if isinstance(interests, list):
            return [i.lower().strip() for i in interests if isinstance(i, str)]
        return []
    except (json.JSONDecodeError, OSError):
        return []


def _title_matches_gate(title: str) -> bool:
    """Check if the title passes the research gate."""
    title_lower = title.lower()
    return any(kw in title_lower for kw in TITLE_GATE_KEYWORDS)


def _count_positive_matches(text: str) -> int:
    """Count how many positive signals appear in text."""
    text_lower = text.lower()
    count = 0
    for kw in DESCRIPTION_POSITIVE_KEYWORDS:
        if kw in text_lower:
            count += 1
    return count


def _count_soft_blacklist_matches(text: str) -> int:
    """Count how many soft-blacklist signals appear in text.

    Uses word-boundary matching for short ambiguous words (≤3 chars)
    to avoid false positives from boilerplate text.
    """
    text_lower = text.lower()
    count = 0
    for kw in SOFT_BLACKLIST:
        if len(kw) <= 3:
            # Short words: use word boundaries to avoid substring matches
            if re.search(r'\b' + re.escape(kw) + r'\b', text_lower):
                count += 1
        else:
            # Longer phrases: substring matching is fine
            if kw in text_lower:
                count += 1
    return count


def _has_hard_blacklist(text: str) -> bool:
    """Check if hard-blacklisted content is present (word-boundary matching)."""
    text_lower = text.lower()
    for kw in HARD_BLACKLIST:
        # Use word boundary regex to avoid substring false positives
        # e.g. "hr" should not match "ehr" in "behavior"
        if re.search(r'\b' + re.escape(kw) + r'\b', text_lower):
            return True
    return False


def _interest_bonus(text: str, interests: List[str]) -> int:
    """Return bonus points for user-interest matches."""
    text_lower = text.lower()
    return sum(1 for interest in interests if interest in text_lower)


def _feedback_bonus(text: str, interests: List[str]) -> int:
    """Return bonus points for user-interest matches.
    
    Also checks auto-interests from feedback and gives extra bonus.
    """
    text_lower = text.lower()
    bonus = 0
    for interest in interests:
        if interest in text_lower:
            bonus += 1
    return bonus


def _feedback_signal_score(text: str, auto_interests: List[str], auto_blacklist: List[str]) -> float:
    """Compute feedback-based score adjustment.
    
    Positive signals boost score; negative signals penalize.
    """
    text_lower = text.lower()
    score = 0.0
    
    # Bonus for auto-interests
    for kw in auto_interests:
        if kw in text_lower:
            score += 0.5
    
    # Penalty for auto-blacklist
    for kw in auto_blacklist:
        if re.search(r'\b' + re.escape(kw) + r'\b', text_lower):
            score -= 0.5
    
    return score


def filter_jobs(
    jobs: List[Job],
    blacklist: Optional[List[str]] = None,
    interests: Optional[List[str]] = None,
) -> List[Job]:
    """Filter jobs to keep only research-engineer-related positions.

    Uses a two-stage filter:
      1. Title gate: must contain a research keyword in the title.
      2. Description scoring: title + description are scored using positive
         signals, soft blacklist, and hard blacklist.

    Args:
        jobs: List of jobs to filter.
        blacklist: Optional additional soft-blacklist keywords to exclude.
        interests: Optional list of user interest phrases (from config or
            ~/.neolab_interests.json). When provided, jobs matching interests
            get a scoring bonus.

    Returns:
        Filtered list of research-related jobs.
    """
    extra_soft = [w.lower() for w in (blacklist or [])]

    # Load interests if not provided
    if interests is None:
        interests = _load_user_interests()

    filtered: List[Job] = []

    for job in jobs:
        title_lower = job.title.lower()
        desc_lower = (job.description or "").lower()
        full_text = f"{job.title} {job.description}"
        full_lower = full_text.lower()

        # A meaningful description is at least 20 chars of non-whitespace
        has_description = len(desc_lower.strip()) > 20

        # Stage 1: title gate
        if not _title_matches_gate(title_lower):
            continue

        # Stage 2: hard blacklist — always excludes
        if _has_hard_blacklist(full_lower):
            continue

        # No description: fall back to old title-only logic
        if not has_description:
            if any(kw in title_lower for kw in extra_soft):
                continue
            filtered.append(job)
            continue

        # Stage 2b: description-aware scoring
        soft_count = _count_soft_blacklist_matches(full_lower)
        for kw in extra_soft:
            if kw in full_lower:
                soft_count += 1

        positive_count = _count_positive_matches(full_lower)
        interest_bonus = _interest_bonus(full_lower, interests)

        # A job is kept if positive signals outweigh soft blacklist hits,
        # OR if it has strong interest alignment
        if positive_count > 0 and positive_count >= soft_count:
            filtered.append(job)
        elif soft_count == 0 and interest_bonus >= 1:
            # No soft blacklist hits but matches user interests — include
            filtered.append(job)
        elif positive_count >= 2:
            # Multiple strong positives override soft blacklist
            filtered.append(job)

    return filtered


def score_job(job: Job, interests: Optional[List[str]] = None,
              auto_interests: Optional[List[str]] = None,
              auto_blacklist: Optional[List[str]] = None) -> float:
    """Compute a relevance score for a single job.

    Positive signals add points; soft-blacklist hits subtract points.
    User interests provide a bonus. Jobs without descriptions get a
    lower base score. Feedback signals provide additional bias.

    Returns:
        Float score (higher = more relevant).
    """
    if interests is None:
        interests = _load_user_interests()
    if auto_interests is None:
        auto_interests = []
    if auto_blacklist is None:
        auto_blacklist = []

    desc_lower = (job.description or "").lower()
    full_text = f"{job.title} {job.description}"
    full_lower = full_text.lower()

    positive_count = _count_positive_matches(full_lower)
    soft_count = _count_soft_blacklist_matches(full_lower)
    interest_bonus = _interest_bonus(full_lower, interests)
    feedback_score = _feedback_signal_score(full_lower, auto_interests, auto_blacklist)

    # Base score from positive signals
    score = positive_count

    # Penalty from soft blacklist
    score -= soft_count * 0.5

    # Interest bonus
    score += interest_bonus * 0.5

    # Feedback bias
    score += feedback_score

    # Bonus for having a description (more signal available)
    if len(desc_lower.strip()) > 20:
        score += 1.0

    return score


def rank_jobs(
    jobs: List[Job],
    interests: Optional[List[str]] = None,
    auto_interests: Optional[List[str]] = None,
    auto_blacklist: Optional[List[str]] = None,
) -> List[Job]:
    """Sort jobs by relevance score (highest first).

    Args:
        jobs: List of jobs to rank.
        interests: Optional list of user interest phrases.
        auto_interests: Optional list of auto-discovered interest keywords
            from feedback signals.
        auto_blacklist: Optional list of auto-discovered blacklist keywords
            from feedback signals.

    Returns:
        New list of jobs sorted by relevance descending.
    """
    if interests is None:
        interests = _load_user_interests()
    if auto_interests is None:
        auto_interests = []
    if auto_blacklist is None:
        auto_blacklist = []

    scored = [(score_job(job, interests, auto_interests, auto_blacklist), job) 
              for job in jobs]
    scored.sort(key=lambda x: x[0], reverse=True)
    return [job for _, job in scored]


def diff_jobs(current: List[Job], previous: List[Job]) -> tuple[List[Job], List[Job]]:
    """Find new and removed jobs by comparing two snapshots.

    Args:
        current: Jobs from the latest scrape.
        previous: Jobs from the previous scrape.

    Returns:
        Tuple of (new_jobs, removed_jobs).
    """
    previous_titles = {(job.title, job.company) for job in previous}
    current_titles = {(job.title, job.company) for job in current}

    new_jobs = [job for job in current if (job.title, job.company) not in previous_titles]
    removed_jobs = [job for job in previous if (job.title, job.company) not in current_titles]

    return new_jobs, removed_jobs
