"""ByteDance Seed job scraper - Seed's JSON API.

Seed's team pages (seed.bytedance.com/en/direction/*) are a JS-rendered
React app, so the static HTML is no longer parseable. Instead, the app
calls a plain JSON API (no auth/cookies required) that returns all
open jobs in a single call:

    GET https://seed.bytedance.com/api/get_job_list_v2

Each record carries parallel English (``SubJobEn``) and Chinese
(``SubJobZh``) sub-objects; English fields are preferred, with Chinese
as fallback. Records whose external links are empty fall back to a
link built from the ``JobMeta.Position`` id.
"""

from typing import List

import requests

from src.scraper.base import JobScraper
from src.scraper.models import Job

_USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"


class SeedScraper(JobScraper):
    """Scraper for ByteDance Seed jobs via Seed's JSON API."""

    def __init__(self):
        super().__init__(
            "ByteDance Seed",
            "https://seed.bytedance.com/api/get_job_list_v2",
        )

    def scrape(self) -> List[Job]:
        """Fetch jobs from Seed's job list API."""
        try:
            print(f"  Fetching {self.company_name} jobs from Seed API...")
            response = requests.get(
                self.base_url,
                headers={"User-Agent": _USER_AGENT},
                timeout=20,
            )
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as e:
            print(f"  Error fetching jobs from {self.company_name}: {e}")
            return []
        except ValueError as e:
            print(f"  Unexpected error parsing {self.company_name} response: {e}")
            return []

        base_resp = data.get("BaseResp") or {}
        if base_resp.get("StatusCode", 0) != 0:
            print(
                f"  Warning: {self.company_name} API returned StatusCode "
                f"{base_resp.get('StatusCode')} ({base_resp.get('StatusMessage', '')})"
            )
            return []

        try:
            jobs: List[Job] = []
            for record in data.get("job_list", []):
                job_meta = record.get("JobMeta") or {}
                status = job_meta.get("Status")
                if status is not None and status != 2:
                    continue  # closed/inactive position

                sub_en = record.get("SubJobEn") or {}
                sub_zh = record.get("SubJobZh") or {}

                title = (sub_en.get("JobName") or "").strip() or (sub_zh.get("JobName") or "").strip()
                if not title:
                    continue

                location = (sub_en.get("City") or "").strip() or (sub_zh.get("City") or "").strip()
                apply_link = (sub_en.get("ExternalLink") or "").strip() or (sub_zh.get("ExternalLink") or "").strip()
                if not apply_link:
                    position = job_meta.get("Position")
                    if position:
                        apply_link = f"https://jobs.bytedance.com/experienced/position/{position}/detail"
                if not apply_link:
                    continue

                jobs.append(Job(
                    title=title,
                    location=location,
                    apply_link=apply_link,
                    company=self.company_name,
                ))
        except Exception as e:
            print(f"  Unexpected error scraping {self.company_name}: {e}")
            return []

        print(f"  Found {len(jobs)} jobs from {self.company_name}")
        return jobs
