"""Job scraper package."""

from src.scraper.base import JobScraper
from src.scraper.models import Job, ScrapeResult, DiffResult

__all__ = ["JobScraper", "Job", "ScrapeResult", "DiffResult"]
