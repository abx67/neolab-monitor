"""Job filtering logic - pure functions for research position classification."""

from typing import List

from src.scraper.models import Job

# Keywords that indicate a research engineering position
RESEARCH_KEYWORDS = [
    "research engineer",
    "research scientist",
    "research scientist/engineer",
    "research scientist / engineer",
    "machine learning engineer",
    "ml engineer",
    "model engineer",
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
]

# Keywords that exclude non-research roles
BLACKLIST_KEYWORDS = [
    "safeguards",
    "recruit",
    "operation",
    "manager",
    "biology",
    "scaling",
    "honesty",
    "education",
    "protection",
    "investigat",
    "threat",
    "security",
    "legal",
    "business",
    "marketing",
    "sales",
    "finance",
    "people",
    "data",
    "intern",
    "comput",
    "trust",
    "deploy",
    "strate",
    "robust",
    "safe",
    "health",
    "eval",
    "environment",
    "weather",
    "energy",
    "human",
    "notif",
    "cyber",
    "integr",
    "biolog",
    "chemic",
    "community",
    "cuda",
    "optim",
    "efficien",
    "quanti",
    "inference",
    "govern",
    "compil",
    "product",
    "design",
    "university",
    "platform",
    "graduate",
    "atomistic",
    "system",
    "responsible",
    "phd",
]


def filter_jobs(jobs: List[Job], blacklist: List[str] | None = None) -> List[Job]:
    """Filter jobs to keep only research engineer related positions.

    Args:
        jobs: List of jobs to filter.
        blacklist: Optional additional blacklist keywords to exclude.

    Returns:
        Filtered list of research-related jobs.
    """
    keywords_lower = [k.lower() for k in RESEARCH_KEYWORDS]
    blacklist_words = [w.lower() for w in BLACKLIST_KEYWORDS]
    if blacklist:
        blacklist_words.extend([w.lower() for w in blacklist])

    filtered: List[Job] = []
    for job in jobs:
        title_lower = job.title.lower()
        if any(kw in title_lower for kw in keywords_lower):
            if not any(bw in title_lower for bw in blacklist_words):
                filtered.append(job)
    return filtered


def diff_jobs(current: List[Job], previous: List[Job]) -> tuple[List[Job], List[Job]]:
    """Find new and removed jobs by comparing two snapshots.

    Args:
        current: Jobs from the latest scrape.
        previous: Jobs from the previous scrape.

    Returns:
        Tuple of (new_jobs, removed_jobs).
    """
    previous_titles = {job.title for job in previous}
    current_titles = {job.title for job in current}

    new_jobs = [job for job in current if job.title not in previous_titles]
    removed_jobs = [job for job in previous if job.title not in current_titles]

    return new_jobs, removed_jobs
