"""Orchestration engine — wires scrapers, storage, filter, and notifier."""

from __future__ import annotations

from typing import Dict, List

from src.config import Config
from src.scraper.models import Job, DiffResult
from src.scraper.scrapers.anthropic import AnthropicScraper
from src.scraper.scrapers.deepmind import DeepMindScraper
from src.scraper.scrapers.openai import OpenAIScraper
from src.scraper.scrapers.seed import SeedScraper
from src.scraper.scrapers.thinking_machines import ThinkingMachinesScraper
from src.scraper.scrapers.xai import XAIScraper
from src.storage.base import StorageABC
from src.filter import filter_jobs, diff_jobs


class JobEngine:
    """Orchestrates scraping, diffing, persistence, and display."""

    def __init__(self, config: Config, storage: StorageABC):
        self.config = config
        self.storage = storage
        self._init_scrapers()

    def _init_scrapers(self) -> None:
        self.scrapers: List = [
            AnthropicScraper(),
            OpenAIScraper(),
            DeepMindScraper(),
            XAIScraper(),
            SeedScraper(),
            ThinkingMachinesScraper(),
        ]

    # ── public API ──────────────────────────────────────────────────────

    def scrape_all(self) -> Dict[str, List[Job]]:
        """Scrape every company; apply research filter unless company is whitelisted."""
        results: Dict[str, List[Job]] = {}

        for scraper in self.scrapers:
            print(f"\n  Scraping {scraper.company_name}...")
            try:
                jobs = scraper.scrape()
            except Exception as e:
                print(f"  Error scraping {scraper.company_name}: {e}")
                jobs = []

            if not jobs:
                results[scraper.company_name] = []
                print(f"  No jobs found")
                continue

            if scraper.company_name in self.config.no_filter_companies:
                results[scraper.company_name] = jobs
                print(f"  Found {len(jobs)} total jobs, all positions included")
            else:
                filtered = filter_jobs(jobs, self.config.blacklist_keywords)
                results[scraper.company_name] = filtered
                print(f"  Found {len(jobs)} total jobs, {len(filtered)} research positions")

        return results

    def compute_diff(
        self,
        current: Dict[str, List[Job]],
        previous: Dict[str, List[Job]],
    ) -> Dict[str, DiffResult]:
        """Return per-company new/removed job lists."""
        diff: Dict[str, DiffResult] = {}
        for company, curr_jobs in current.items():
            prev_jobs = previous.get(company, [])
            new_jobs, removed_jobs = diff_jobs(curr_jobs, prev_jobs)
            if new_jobs or removed_jobs:
                diff[company] = DiffResult(new_jobs=new_jobs, removed_jobs=removed_jobs)
        return diff

    def run(self, send_email: bool = False) -> None:
        """Full pipeline: scrape → diff → display → save → (optionally) email."""
        print("=" * 60)
        print("  AI Research Engineer Jobs Scraper")
        print("  Companies: Anthropic, OpenAI, DeepMind, X.ai, ByteDance Seed, Thinking Machines")
        print("=" * 60)

        all_jobs = self.scrape_all()

        previous_jobs_raw = self.storage.load_previous_jobs()
        previous_jobs: Dict[str, List[Job]] = {
            company: [Job.from_dict(j) for j in jobs]
            for company, jobs in previous_jobs_raw.items()
        }
        diff_result = self.compute_diff(all_jobs, previous_jobs)

        total_new = sum(d.new_count for d in diff_result.values())
        total_removed = sum(d.removed_count for d in diff_result.values())

        if total_new > 0:
            print(f"\n  🆕 Found {total_new} new job(s)!")
        else:
            print("\n  ℹ️ No new jobs since last check.")
        if total_removed > 0:
            print(f"  ❎ {total_removed} position(s) removed since last check.")

        self._display_results(all_jobs, diff_result)
        self._save(all_jobs)

        if send_email:
            new_jobs_by_company = {
                c: d.new_jobs for c, d in diff_result.items() if d.new_jobs
            }
            removed_jobs_by_company = {
                c: d.removed_jobs for c, d in diff_result.items() if d.removed_jobs
            }
            if new_jobs_by_company or removed_jobs_by_company:
                from src.notifier import EmailNotifier
                notifier = EmailNotifier(self.config)
                notifier.send(all_jobs, new_jobs_by_company or None, removed_jobs_by_company or None)

    # ── internals ───────────────────────────────────────────────────────

    def _display_results(self, all_jobs: Dict[str, List[Job]],
                         diff_result: Dict[str, DiffResult]) -> None:
        total = sum(len(jobs) for jobs in all_jobs.values())
        print(f"\n{'=' * 60}")
        print(f"  AI RESEARCH ENGINEER JOBS — {total} positions found")
        new_count = sum(d.new_count for d in diff_result.values())
        if new_count > 0:
            print(f"  🆕 {new_count} new positions since last check!")
        print(f"{'=' * 60}")

        for company, jobs in all_jobs.items():
            if not jobs:
                continue
            d = diff_result.get(company, DiffResult())
            new_titles = {j.title for j in d.new_jobs}
            print(f"\n  🏢 {company.upper()} — {len(jobs)} positions")
            print("  " + "-" * 50)
            for i, job in enumerate(jobs, 1):
                indicator = " 🆕" if job.title in new_titles else ""
                print(f"  {i}. {job.title}{indicator}")
                print(f"     📍 Location: {job.location}")
                if job.apply_link:
                    print(f"     🔗 Apply: {job.apply_link}")
            print()

    def _save(self, all_jobs: Dict[str, List[Job]]) -> None:
        serialized: Dict[str, List[Dict[str, str]]] = {}
        for company, jobs in all_jobs.items():
            serialized[company] = [j.to_dict() for j in jobs]
        self.storage.save_jobs_history(serialized)
        total = sum(len(j) for j in serialized.values())
        print(f"\n  💾 Saved {total} jobs to storage")
