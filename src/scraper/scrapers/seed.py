"""ByteDance Seed job scraper - scrapes multiple team pages."""

import re
from typing import List

from bs4 import BeautifulSoup
from src.scraper.base import JobScraper
from src.scraper.models import Job


class SeedScraper(JobScraper):
    """Scraper for ByteDance Seed jobs from their team pages."""

    TEAM_PAGES = [
        "https://seed.bytedance.com/en/direction/llm",
        "https://seed.bytedance.com/en/direction/vision",
        "https://seed.bytedance.com/en/direction/speech",
        "https://seed.bytedance.com/en/direction/multimodal",
        "https://seed.bytedance.com/en/direction/ai_for_science",
        "https://seed.bytedance.com/en/direction/robotics",
        "https://seed.bytedance.com/en/direction/infrastructures",
        "https://seed.bytedance.com/en/direction/responsible_ai",
    ]

    LOCATION_PATTERNS = [
        "San Jose", "Seattle", "Singapore", "Beijing", "Shanghai",
        "Palo Alto", "New York", "London", "Tokyo", "San Francisco",
    ]

    EMPLOYMENT_TYPES = ["Experienced Hiring", "Campus Recruitment", "Internship"]

    def __init__(self):
        super().__init__("ByteDance Seed", "https://seed.bytedance.com/en/career")

    def scrape(self, enrich_descriptions: bool = True) -> List[Job]:
        all_jobs: List[Job] = []

        for team_url in self.TEAM_PAGES:
            try:
                print(f"  Scraping {self.company_name} team page: {team_url}")
                response = self.session.get(team_url, timeout=10)
                response.raise_for_status()
                soup = BeautifulSoup(response.content, "html.parser")
                jobs = self._extract_jobs_from_page(soup, team_url)
                all_jobs.extend(jobs)
            except Exception as e:
                print(f"  Error scraping {team_url}: {e}")
                continue

        # Deduplicate by apply_link
        seen: set[str] = set()
        unique_jobs: List[Job] = []
        for job in all_jobs:
            if job.apply_link not in seen:
                unique_jobs.append(job)
                seen.add(job.apply_link)

        print(f"  Found {len(unique_jobs)} unique jobs from {self.company_name}")

        # Fetch descriptions for filtering improvement
        if enrich_descriptions:
            unique_jobs = self.enrich_with_descriptions(unique_jobs)

        return unique_jobs

    def _extract_jobs_from_page(self, soup: BeautifulSoup, team_url: str) -> List[Job]:
        jobs: List[Job] = []
        job_links = soup.find_all("a", href=True)

        for link in job_links:
            href = str(link.get("href", "") or "")
            if "job.toutiao.com" not in href and "jobs.toutiao.com" not in href:
                continue
            if "/position/" not in href:
                continue

            job_text = link.get_text(strip=True)
            if not job_text or "Apply Now" not in job_text:
                continue

            job_info = job_text.replace("Apply Now", "").strip()
            title = job_info
            location = ""

            for loc_pattern in self.LOCATION_PATTERNS:
                if loc_pattern in job_info:
                    parts = job_info.split(loc_pattern)
                    if len(parts) >= 2:
                        title = parts[0].strip()
                        location = loc_pattern
                        remaining = parts[1].strip()
                        if remaining and not any(
                            emp in remaining.lower() for emp in ["experienced", "campus", "internship"]
                        ):
                            location += remaining.split()[0] if remaining.split() else ""
                        break

            for emp_type in self.EMPLOYMENT_TYPES:
                title = title.replace(emp_type, "").strip()

            apply_url = href
            if apply_url.startswith("http://"):
                apply_url = apply_url.replace("http://", "https://")
            elif not apply_url.startswith("https://"):
                apply_url = "https://" + apply_url.lstrip("/")

            if title and apply_url:
                jobs.append(Job(
                    title=title,
                    location=location or "Multiple Locations",
                    apply_link=apply_url,
                    company=self.company_name,
                ))

        return jobs
