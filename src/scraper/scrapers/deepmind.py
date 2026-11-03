"""DeepMind job scraper - Google's careers platform.

DeepMind left Greenhouse; jobs are now listed on Google's careers platform.
The results page (``?company=DeepMind``) is server-rendered with 20 jobs per
page and 1-based ``&page=N`` pagination. Job records are embedded in the HTML
as JSON arrays inside ``AF_initDataCallback`` data blobs; each record's
leading element is an 18-19 digit job id string. Public apply links are
built from ``careers.google.com/jobs/results/{job_id}-{slug}`` (no login
required).
"""

import json
import re
from typing import List

import requests

from src.scraper.base import JobScraper
from src.scraper.models import Job

_USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
_MAX_PAGES = 10


def _extract_job_records(html: str) -> List[list]:
    """Extract embedded job records from a Google careers results page.

    Records start with ``["<15+ digit job id>"``; we walk forward with
    balanced-bracket matching to pull out the full top-level JSON array and
    ``json.loads`` it, tolerating schema drift better than parsing
    obfuscated CSS classes. Unbalanced (partial) records and balanced-but-
    invalid JSON are skipped silently.
    """
    records: List[list] = []
    for match in re.finditer(r'\["\d{15,}"', html):
        start = match.start()
        depth = 0
        in_string = False
        escaped = False
        end = -1
        for i in range(start, len(html)):
            ch = html[i]
            if in_string:
                if escaped:
                    escaped = False
                elif ch == "\\":
                    escaped = True
                elif ch == '"':
                    in_string = False
            elif ch == '"':
                in_string = True
            elif ch == "[":
                depth += 1
            elif ch == "]":
                depth -= 1
                if depth == 0:
                    end = i
                    break
        if end == -1:
            continue  # partial record, no closing bracket
        try:
            records.append(json.loads(html[start:end + 1]))
        except ValueError:
            continue  # balanced but corrupt JSON
    return records


def _slugify(title: str) -> str:
    """Slug for the public detail URL: lowercase, non-alphanumeric runs to '-'."""
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")


class DeepMindScraper(JobScraper):
    """Scraper for DeepMind jobs via Google's careers platform."""

    def __init__(self):
        super().__init__(
            "DeepMind",
            "https://www.google.com/about/careers/applications/jobs/results",
        )

    def scrape(self) -> List[Job]:
        """Fetch jobs from DeepMind's Google careers results pages."""
        try:
            print(f"  Fetching {self.company_name} jobs from Google careers platform...")
            jobs: List[Job] = []
            seen_ids = set()

            for page in range(1, _MAX_PAGES + 1):
                url = f"{self.base_url}?company={self.company_name}&page={page}"
                response = requests.get(
                    url,
                    headers={"User-Agent": _USER_AGENT},
                    timeout=20,
                )
                response.raise_for_status()

                new_ids = 0
                for record in _extract_job_records(response.text):
                    if not isinstance(record, list) or len(record) < 2:
                        continue
                    job_id = record[0]
                    title = str(record[1]).strip()
                    if not isinstance(job_id, str) or not title:
                        continue  # skip records missing id/title
                    if job_id in seen_ids:
                        continue
                    seen_ids.add(job_id)
                    new_ids += 1

                    location = ""
                    if len(record) > 9 and isinstance(record[9], list):
                        try:
                            # Each location entry is [display, [display], city, ..., state, country];
                            # element 0 holds the display string ("London, UK", ...).
                            location = " | ".join(
                                str(loc[0]) for loc in record[9] if loc and loc[0]
                            )
                        except (IndexError, TypeError):
                            location = ""

                    apply_link = f"https://careers.google.com/jobs/results/{job_id}-{_slugify(title)}"
                    jobs.append(Job(
                        title=title,
                        location=location,
                        apply_link=apply_link,
                        company=self.company_name,
                    ))

                # Stop when a page yields no new job ids: covers both the
                # past-the-end case and the pagenum-style failure where a
                # follow-up page just repeats earlier data.
                if new_ids == 0:
                    break

            print(f"  Found {len(jobs)} jobs from {self.company_name}")
            return jobs

        except requests.RequestException as e:
            print(f"  Error fetching jobs from {self.company_name}: {e}")
            return []
        except Exception as e:
            print(f"  Unexpected error scraping {self.company_name}: {e}")
            return []
