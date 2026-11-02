"""Data models for the job scraper system."""

from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime


@dataclass
class Job:
    """Represents a single job posting."""
    title: str
    location: str
    apply_link: str
    company: str
    job_url: Optional[str] = None
    description: str = ""

    def __eq__(self, other):
        if not isinstance(other, Job):
            return False
        return self.title == other.title and self.company == other.company

    def __hash__(self):
        return hash((self.title, self.company))

    def to_dict(self) -> dict:
        """Serialize to dictionary for storage."""
        return {
            "title": self.title,
            "location": self.location,
            "apply_link": self.apply_link,
            "company": self.company,
            "job_url": self.job_url,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Job":
        """Deserialize from dictionary."""
        return cls(
            title=data["title"],
            location=data.get("location", ""),
            apply_link=data["apply_link"],
            company=data.get("company", ""),
            job_url=data.get("job_url"),
            description=data.get("description", ""),
        )


@dataclass
class ScrapeResult:
    """Result of a scraping run."""
    jobs: List[Job]
    company: str
    scraped_at: datetime = field(default_factory=datetime.now)

    @property
    def new_count(self) -> int:
        return len(self.jobs)

    def to_dict(self) -> dict:
        return {
            "company": self.company,
            "scraped_at": self.scraped_at.isoformat(),
            "jobs": [job.to_dict() for job in self.jobs],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ScrapeResult":
        return cls(
            company=data["company"],
            scraped_at=datetime.fromisoformat(data["scraped_at"]),
            jobs=[Job.from_dict(j) for j in data["jobs"]],
        )


@dataclass
class DiffResult:
    """Difference between two scrape results."""
    new_jobs: List[Job] = field(default_factory=list)
    removed_jobs: List[Job] = field(default_factory=list)

    @property
    def has_changes(self) -> bool:
        return bool(self.new_jobs) or bool(self.removed_jobs)

    @property
    def new_count(self) -> int:
        return len(self.new_jobs)

    @property
    def removed_count(self) -> int:
        return len(self.removed_jobs)
