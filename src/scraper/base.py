"""Base scraper class defining the interface for all company scrapers."""

from abc import ABC, abstractmethod
from typing import List
import json
import re

import requests
from bs4 import BeautifulSoup

from src.scraper.models import Job
from src.desc_cache import get_cached_description, set_cached_description


def _parse_ashby_app_data(content: str) -> dict | None:
    """Parse the ``window.__appData`` JSON blob from a script tag's content.

    This is the shared parsing logic used by both the base class
    ``_extract_ashby_json`` method and the individual Ashby scrapers
    (OpenAI, Thinking Machines). It locates the ``window.__appData``
    assignment, extracts the JSON object using bracket-matching, and
    returns the parsed dict.

    Args:
        content: The raw text content of a ``<script>`` tag.

    Returns:
        The parsed app data dict, or ``None`` if parsing fails.
    """
    try:
        start = content.find("window.__appData = ")
        if start == -1:
            start = content.find("window.__appData=")
            pattern = "window.__appData="
        else:
            pattern = "window.__appData = "

        if start == -1:
            return None

        start += len(pattern)
        bracket_count = 0
        in_string = False
        escape_next = False
        end = start

        for i, char in enumerate(content[start:], start):
            if escape_next:
                escape_next = False
                continue
            if char == "\\":
                escape_next = True
                continue
            if char == '"' and not escape_next:
                in_string = not in_string
                continue
            if not in_string:
                if char == "{":
                    bracket_count += 1
                elif char == "}":
                    bracket_count -= 1
                    if bracket_count == 0:
                        end = i + 1
                        break

        json_str = content[start:end]
        return json.loads(json_str)
    except (json.JSONDecodeError, ValueError, KeyError):
        return None


# Registry mapping domain substrings to fetcher method names.
# The first matching domain wins. Order matters for overlapping domains.
PLATFORM_FETCHERS = {
    "ashbyhq.com": "fetch_job_description_ashby",
    "toutiao.com": "fetch_job_description_toutiao",
}


class JobScraper(ABC):
    """Base class for all job scrapers."""

    # Greenhouse job posting CSS selectors (varies by company theme)
    GREENHOUSE_SELECTORS = [
        "div.task-list",
        "div.job-posting__description",
        "div.description",
        "div#job_description",
        "div.posting",
        "div.job-content",
        "section.job-description",
    ]

    # Ashby-specific selectors
    ASHBY_SELECTORS = [
        "div[data-testid='job-description']",
        "div.job-description",
        "div#job-description",
        "div.description",
        "[data-testid='description']",
    ]

    # Toutiao/Seed-specific selectors
    TOUTIAO_SELECTORS = [
        "div.job-detail",
        "div.description",
        "div.content",
        "div.job-desc",
        "section.job-detail",
    ]

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

    def fetch_job_description(self, url: str) -> str:
        """Fetch a single job page and extract its description text.

        Handles Greenhouse-hosted job boards (Anthropic, DeepMind, XAI, etc.)
        by trying multiple CSS selectors.
        """
        if not url:
            return ""
        try:
            resp = self.session.get(url, timeout=10)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.content, "html.parser")

            for selector in self.GREENHOUSE_SELECTORS:
                el = soup.select_one(selector)
                if el and el.get_text(strip=True):
                    text = el.get_text(separator=" ", strip=True)
                    # Collapse whitespace
                    text = re.sub(r"\s+", " ", text).strip()
                    if len(text) > 50:
                        return text[:5000]

            # Fallback: try the main content area
            main = soup.find("main") or soup.find("article") or soup.find("div", class_=re.compile(r"job|posting|description", re.I))
            if main:
                text = main.get_text(separator=" ", strip=True)
                text = re.sub(r"\s+", " ", text).strip()
                if len(text) > 50:
                    return text[:5000]

            return ""
        except requests.RequestException:
            return ""
        except Exception:
            return ""

    def fetch_job_description_ashby(self, url: str) -> str:
        """Fetch a job description from an Ashby-hosted job page.

        Ashby pages embed job data in ``window.__appData`` JSON. This method
        extracts the description from that JSON, falling back to HTML selectors.
        """
        if not url:
            return ""
        try:
            print(f"  Fetching Ashby job description: {url}")
            resp = self.session.get(url, timeout=10)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.content, "html.parser")

            # Try to extract from window.__appData JSON (most reliable for Ashby)
            description = self._extract_ashby_json(soup)
            if description:
                return description[:5000]

            # Fallback: try CSS selectors
            text = self._extract_from_selectors(soup, self.ASHBY_SELECTORS)
            if text:
                return text[:5000]

            # Fallback: main content area
            main = soup.find("main") or soup.find("article") or soup.find("div", class_=re.compile(r"job|posting|description", re.I))
            if main:
                text = main.get_text(separator=" ", strip=True)
                text = re.sub(r"\s+", " ", text).strip()
                if len(text) > 50:
                    return text[:5000]

            return ""
        except requests.RequestException:
            return ""
        except Exception:
            return ""

    def fetch_job_description_toutiao(self, url: str) -> str:
        """Fetch a job description from a Toutiao job page.

        Toutiao pages may be server-rendered or use client-side JSON data.
        This method tries CSS selectors, ``__NEXT_DATA__`` JSON, and main
        content area extraction.
        """
        if not url:
            return ""
        try:
            resp = self.session.get(url, timeout=10)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.content, "html.parser")

            # Try common CSS selectors
            text = self._extract_from_selectors(soup, self.TOUTIAO_SELECTORS)
            if text:
                return text[:5000]

            # Try __NEXT_DATA__ JSON (Next.js)
            next_data_script = soup.find("script", id="__NEXT_DATA__")
            if next_data_script and next_data_script.string:
                try:
                    data = json.loads(next_data_script.string)
                    desc = self._find_description_in_json(data)
                    if desc:
                        return desc[:5000]
                except (json.JSONDecodeError, ValueError):
                    pass

            # Fallback: main content area
            main = soup.find("main") or soup.find("article") or soup.find("div", class_=re.compile(r"job|detail|description|content", re.I))
            if main:
                text = main.get_text(separator=" ", strip=True)
                text = re.sub(r"\s+", " ", text).strip()
                if len(text) > 50:
                    return text[:5000]

            return ""
        except requests.RequestException:
            return ""
        except Exception:
            return ""

    def _extract_from_selectors(self, soup: BeautifulSoup, selectors: list) -> str:
        """Try a list of CSS selectors and return the first non-empty text."""
        for selector in selectors:
            el = soup.select_one(selector)
            if el and el.get_text(strip=True):
                text = el.get_text(separator=" ", strip=True)
                text = re.sub(r"\s+", " ", text).strip()
                if len(text) > 50:
                    return text
        return ""

    def _extract_ashby_json(self, soup: BeautifulSoup) -> str:
        """Try to extract job description from window.__appData JSON on Ashby pages."""
        script_tags = soup.find_all("script")
        for script in script_tags:
            content = script.string
            if not content or "window.__appData" not in content:
                continue
            app_data = _parse_ashby_app_data(content)
            if app_data is None:
                continue

            # Try to find description in job postings
            if "jobBoard" in app_data and isinstance(app_data["jobBoard"], dict):
                job_board = app_data["jobBoard"]
                # Check for single jobPosting (job detail page)
                if "jobPosting" in job_board and isinstance(job_board["jobPosting"], dict):
                    desc = job_board["jobPosting"].get("description", "") or job_board["jobPosting"].get("longDescription", "")
                    if desc:
                        text = self._clean_description(desc)
                        if len(text) > 50:
                            return text
                # Check for jobPostings list (job listing page)
                for posting in job_board.get("jobPostings", []):
                    desc = posting.get("description", "") or posting.get("longDescription", "")
                    if desc:
                        text = self._clean_description(desc)
                        if len(text) > 50:
                            return text

            # Fallback: recursive search for description field
            desc = self._find_description_in_json(app_data)
            if desc:
                return desc
        return ""

    def _find_description_in_json(self, data, depth: int = 0) -> str:
        """Recursively search for a description field in JSON data."""
        if depth > 15:
            return ""
        if isinstance(data, dict):
            for key, value in data.items():
                if (
                    key.lower()
                    in ("description", "jobdescription", "descriptionhtml", "content")
                    and isinstance(value, str)
                    and len(value) > 50
                ):
                    return self._clean_description(value)
            for value in data.values():
                desc = self._find_description_in_json(value, depth + 1)
                if desc:
                    return desc
        elif isinstance(data, list):
            for item in data:
                desc = self._find_description_in_json(item, depth + 1)
                if desc:
                    return desc
        return ""

    def _clean_description(self, text: str) -> str:
        """Clean a description string — strip HTML if present, collapse whitespace."""
        if "<" in text and ">" in text:
            text = BeautifulSoup(text, "html.parser").get_text(separator=" ", strip=True)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def _fetch_description_for_url(self, url: str) -> str:
        """Route to the appropriate description fetcher based on URL domain.

        Uses the ``PLATFORM_FETCHERS`` registry to match the URL against known
        platform domains. Falls back to the generic Greenhouse fetcher for
        unrecognized domains.

        Also checks and updates the description cache.
        """
        if not url:
            return ""

        # Check cache first
        cache_key = f"{self.company_name}:{url}"
        cached = get_cached_description(cache_key)
        if cached:
            return cached

        # Look up the appropriate fetcher from the registry
        fetcher_name = None
        for domain, method_name in PLATFORM_FETCHERS.items():
            if domain in url:
                fetcher_name = method_name
                break

        if fetcher_name:
            fetcher = getattr(self, fetcher_name, None)
            if fetcher:
                text = fetcher(url)
            else:
                text = self.fetch_job_description(url)
        else:
            text = self.fetch_job_description(url)

        if text and len(text) > 50:
            # Truncate to avoid huge payloads
            text = text[:5000]
            set_cached_description(cache_key, text)

        return text

    def enrich_with_descriptions(self, jobs: List[Job]) -> List[Job]:
        """Fetch and attach descriptions for a batch of jobs.

        Auto-detects the platform based on the job URL domain and uses the
        appropriate description fetcher (Ashby, Toutiao, or Greenhouse).
        Skips jobs that already have a description.
        Limits to 20 jobs to avoid excessive requests.
        """
        to_fetch = [j for j in jobs if not j.description and j.apply_link]
        # Limit to avoid too many requests
        to_fetch = to_fetch[:20]

        for job in to_fetch:
            desc = self._fetch_description_for_url(job.apply_link)
            if desc:
                job.description = desc
                print(f"  Fetched description for: {job.title[:60]}...")
            else:
                print(f"  No description found for: {job.title[:60]}...")
        return jobs
