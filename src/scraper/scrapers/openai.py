"""OpenAI job scraper - scrapes Ashby-hosted job board with JSON data extraction."""

import re
import time
from typing import List, Optional

import requests
from bs4 import BeautifulSoup

from src.scraper.base import JobScraper, _parse_ashby_app_data
from src.scraper.models import Job


class OpenAIScraper(JobScraper):
    """Scraper for OpenAI job listings via Ashby."""

    def __init__(self):
        super().__init__("OpenAI", "https://jobs.ashbyhq.com/openai")
        self.session.headers.update({
            "Referer": "https://jobs.ashbyhq.com/",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "same-origin",
            "Upgrade-Insecure-Requests": "1",
        })

    def fetch_page(self) -> Optional[BeautifulSoup]:
        for attempt in range(3):
            try:
                if attempt > 0:
                    time.sleep(2 * attempt)
                response = self.session.get(self.base_url, timeout=15)
                if response.status_code == 403:
                    print(f"  Attempt {attempt + 1}: Access forbidden (403). Trying alternative approach...")
                    if attempt < 2:
                        continue
                    else:
                        print("  OpenAI jobs could not be fetched due to access restrictions.")
                        print("  Check manually: https://jobs.ashbyhq.com/openai")
                        return None
                response.raise_for_status()
                return BeautifulSoup(response.content, "html.parser")
            except requests.RequestException as e:
                if attempt < 2:
                    print(f"  Attempt {attempt + 1} failed: {e}. Retrying...")
                    continue
                else:
                    print("  All attempts failed. Using cached data...")
                    return None
        return None

    def _parse_app_data_json(self, script_content: str):
        """Extract and parse window.__appData JSON from a script tag.

        Delegates to the shared ``_parse_ashby_app_data`` helper in
        ``src.scraper.base`` to avoid duplicating the bracket-matching
        logic.
        """
        return _parse_ashby_app_data(script_content)

    def _extract_jobs_from_app_data(self, app_data: dict) -> List[Job]:
        """Extract job dicts from parsed __appData."""
        jobs: List[Job] = []
        job_data = None

        research_keywords = [
            "research", "scientist", "engineer", "ml",
            "machine learning", "ai", "artificial intelligence",
        ]

        if "jobs" in app_data:
            job_data = app_data["jobs"]
        elif "jobBoard" in app_data:
            job_board = app_data["jobBoard"]
            if isinstance(job_board, dict):
                if "jobs" in job_board:
                    job_data = job_board["jobs"]
                elif "jobPostings" in job_board:
                    job_data = job_board["jobPostings"]

        if job_data:
            for job in job_data:
                job_title = job.get("title", "")
                if not job_title or len(job_title) < 5:
                    continue
                if not any(kw.lower() in job_title.lower() for kw in research_keywords):
                    continue

                location = job.get("locationName", "San Francisco")
                job_id = job.get("id", "")
                jobs.append(Job(
                    title=job_title,
                    location=location,
                    apply_link=f"https://jobs.ashbyhq.com/openai/{job_id}",
                    job_url=f"https://jobs.ashbyhq.com/openai/{job_id}",
                    company=self.company_name,
                ))

        return jobs

    def _fallback_html_scraper(self, soup: BeautifulSoup) -> List[Job]:
        """Fallback HTML-based extraction if JSON parsing failed."""
        jobs: List[Job] = []
        research_keywords = [
            "research", "scientist", "engineer", "ml",
            "machine learning", "ai", "artificial intelligence",
        ]
        location_indicators = [
            "San Francisco", "New York", "Seattle", "Remote", "London",
            "Dublin", "Tokyo", "Singapore", "Washington", "Paris", "Munich",
        ]

        job_links = soup.find_all("a", href=re.compile(r"/openai/[a-f0-9-]+$"))
        for job_link in job_links:
            job_title = job_link.get_text(strip=True)
            if not job_title or len(job_title) < 5:
                continue
            if not any(kw.lower() in job_title.lower() for kw in research_keywords):
                continue

            location = "San Francisco, CA"
            parent_text = job_link.parent.get_text() if job_link.parent else ""
            for loc in location_indicators:
                if loc in parent_text:
                    location = loc
                    break

            href = job_link.get("href", "")
            job_url = f"https://jobs.ashbyhq.com{href}" if href else ""
            jobs.append(Job(
                title=job_title,
                location=location,
                apply_link=job_url,
                job_url=job_url,
                company=self.company_name,
            ))
        return jobs

    def scrape(self, enrich_descriptions: bool = True) -> List[Job]:
        soup = self.fetch_page()
        if not soup:
            return []

        jobs: List[Job] = []
        script_tags = soup.find_all("script")
        print(f"  Found {len(script_tags)} script tags to search")

        for i, script in enumerate(script_tags):
            script_content = script.string
            if script_content and "window.__appData" in script_content:
                print(f"  Script {i}: Contains window.__appData")
                app_data = self._parse_app_data_json(script_content)
                if app_data:
                    jobs = self._extract_jobs_from_app_data(app_data)
                    print(f"  Found {len(jobs)} research jobs from JSON")
                    if jobs:
                        return jobs

        # Fallback
        if not jobs:
            print("  JSON parsing yielded no results, trying HTML fallback...")
            jobs = self._fallback_html_scraper(soup)

        # Fetch descriptions for filtering improvement
        if enrich_descriptions:
            jobs = self.enrich_with_descriptions(jobs)

        return jobs
