"""Thinking Machines AI job scraper - Ashby-hosted board with JSON data."""

import re
from typing import List

from bs4 import BeautifulSoup
from src.scraper.base import JobScraper, _parse_ashby_app_data
from src.scraper.models import Job


class ThinkingMachinesScraper(JobScraper):
    """Scraper for Thinking Machines AI jobs via Ashby."""

    def __init__(self):
        super().__init__("Thinking Machines", "https://jobs.ashbyhq.com/ThinkingMachines")
        self.session.headers.update({
            "Referer": "https://jobs.ashbyhq.com/",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "same-origin",
            "Upgrade-Insecure-Requests": "1",
        })

    def _parse_app_data(self, script_content: str):
        """Extract and parse window.__appData JSON.

        Delegates to the shared ``_parse_ashby_app_data`` helper in
        ``src.scraper.base`` to avoid duplicating the bracket-matching
        logic.
        """
        return _parse_ashby_app_data(script_content)

    def scrape(self, enrich_descriptions: bool = True) -> List[Job]:
        soup = self.fetch_page()
        if not soup:
            return []

        jobs: List[Job] = []
        script_tags = soup.find_all("script")

        for script in script_tags:
            script_content = script.string
            if not script_content or "window.__appData" not in script_content:
                continue

            app_data = self._parse_app_data(script_content)
            if not app_data:
                continue

            job_data = []
            if "jobBoard" in app_data and isinstance(app_data["jobBoard"], dict):
                job_board = app_data["jobBoard"]
                if "jobPostings" in job_board:
                    job_data = job_board["jobPostings"]

            for job in job_data:
                job_title = job.get("title", "").strip()
                location = job.get("locationName", "").strip()
                job_id = job.get("id", "").strip()

                if job_title and job_id:
                    jobs.append(Job(
                        title=job_title,
                        location=location or "San Francisco",
                        apply_link=f"https://jobs.ashbyhq.com/ThinkingMachines/{job_id}",
                        job_url=f"https://jobs.ashbyhq.com/ThinkingMachines/{job_id}",
                        company=self.company_name,
                    ))
            break

        print(f"  Found {len(jobs)} jobs from {self.company_name}")

        # Fetch descriptions for filtering improvement
        if enrich_descriptions:
            jobs = self.enrich_with_descriptions(jobs)

        return jobs
