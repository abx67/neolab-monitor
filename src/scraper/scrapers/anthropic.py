"""Anthropic job scraper - scrapes Greenhouse-hosted job cards."""

import os
import re
from typing import List

from src.scraper.base import JobScraper
from src.scraper.models import Job


class AnthropicScraper(JobScraper):
    """Scraper for Anthropic job listings via their Greenhouse career page."""

    def __init__(self):
        super().__init__("Anthropic", "https://www.anthropic.com/jobs")

    def scrape(self, enrich_descriptions: bool = True) -> List[Job]:
        soup = self.fetch_page()
        if not soup:
            return []

        debug_mode = os.getenv("SCRAPER_DEBUG", "").lower() in ("1", "true", "yes", "on")
        max_debug_samples = 5

        job_elements = soup.find_all("a", href=re.compile(r"job-boards\.greenhouse\.io/anthropic/jobs"))
        print(f"  Found {len(job_elements)} job elements to process")
        if debug_mode:
            print(f"  Debug mode on: showing up to {max_debug_samples} raw elements")

        jobs: List[Job] = []
        for idx, job_element in enumerate(job_elements):
            if debug_mode and idx < max_debug_samples:
                raw = job_element.prettify() if hasattr(job_element, "prettify") else str(job_element)
                snippet = raw[:600].replace("\n", " ")
                print(f"  Raw job element #{idx}: {snippet}{'...' if len(raw) > 600 else ''}")

            title_elem = job_element.find(class_=re.compile("jobRole"))
            job_title = title_elem.get_text(strip=True) if title_elem else job_element.get_text(strip=True)
            if debug_mode:
                print(f"  Processing job title: {job_title}")

            if not job_title or len(job_title) < 5:
                continue

            location = ""
            location_elem = job_element.find(class_=re.compile("jobLocation"))
            if location_elem:
                location = location_elem.get_text(strip=True)

            apply_link = str(job_element.get("href", "") or "")
            jobs.append(Job(title=job_title, location=location, apply_link=apply_link, company=self.company_name))

        print(f"  Extracted {len(jobs)} jobs from Anthropic page")

        # Fetch descriptions for filtering improvement
        if enrich_descriptions:
            jobs = self.enrich_with_descriptions(jobs)

        return jobs
