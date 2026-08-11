"""Base scraper class defining the interface for all company scrapers."""

from abc import ABC, abstractmethod
from typing import List
import requests
from bs4 import BeautifulSoup

from src.scraper.models import Job


class JobScraper(ABC):
    """Base class for all job scrapers."""

    def __init__(self, company_name: str, base_url: str):
        self.company_name = company_name
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update(self._default_headers)

    @property
    def _default_headers(self) -> dict:
        return {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
        }

    def fetch_page(self) -> BeautifulSoup | None:
        """Fetch a URL and return a BeautifulSoup object."""
        try:
            print(f"  Fetching {self.company_name}: {self.base_url}")
            response = self.session.get(self.base_url, timeout=15)
            response.raise_for_status()
            return BeautifulSoup(response.content, "html.parser")
        except requests.RequestException as e:
            print(f"  Error fetching {self.company_name}: {e}")
            return None

    @abstractmethod
    def scrape(self) -> List[Job]:
        """Scrape jobs from the company's career page. Must be implemented by subclasses."""
        ...

    def _tag_company(self, jobs: List[Job]) -> List[Job]:
        """Attach company name to each job."""
        for job in jobs:
            job.company = self.company_name
        return jobs
