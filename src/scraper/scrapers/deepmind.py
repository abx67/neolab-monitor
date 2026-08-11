"""DeepMind job scraper - uses Greenhouse public API."""

import requests
from typing import List

from src.scraper.base import JobScraper
from src.scraper.models import Job


class DeepMindScraper(JobScraper):
    """Scraper for DeepMind jobs via their Greenhouse API."""

    def __init__(self):
        super().__init__(
            "DeepMind",
            "https://boards-api.greenhouse.io/v1/boards/deepmind/jobs",
        )

    def scrape(self) -> List[Job]:
        """Fetch jobs from DeepMind's Greenhouse API."""
        try:
            print(f"  Fetching {self.company_name} jobs from API...")
            response = requests.get(self.base_url, timeout=10)
            response.raise_for_status()
            data = response.json()

            jobs: List[Job] = []
            for job in data.get("jobs", []):
                job_title = job.get("title", "").strip()
                location = job.get("location", {}).get("name", "").strip()
                apply_url = job.get("absolute_url", "").strip()

                if job_title and apply_url:
                    jobs.append(Job(
                        title=job_title,
                        location=location,
                        apply_link=apply_url,
                        company=self.company_name,
                    ))

            print(f"  Found {len(jobs)} jobs from {self.company_name}")
            return jobs

        except requests.RequestException as e:
            print(f"  Error fetching jobs from {self.company_name}: {e}")
            return []
        except Exception as e:
            print(f"  Unexpected error scraping {self.company_name}: {e}")
            return []
