"""X.ai job scraper - uses Greenhouse public API."""

import requests
from typing import List

from src.scraper.base import JobScraper
from src.scraper.models import Job


class XAIScraper(JobScraper):
    """Scraper for X.ai jobs via their Greenhouse API."""

    def __init__(self):
        super().__init__(
            "X.ai",
            "https://boards-api.greenhouse.io/v1/boards/xai/jobs",
        )

    def scrape(self, enrich_descriptions: bool = True) -> List[Job]:
        """Fetch jobs from X.ai's Greenhouse API."""
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

            # Fetch descriptions for filtering improvement
            if enrich_descriptions:
                jobs = self.enrich_with_descriptions(jobs)

            return jobs

        except requests.RequestException as e:
            print(f"  Error fetching jobs from {self.company_name}: {e}")
            return []
        except Exception as e:
            print(f"  Unexpected error scraping {self.company_name}: {e}")
            return []
