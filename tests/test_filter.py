"""Unit tests for job filtering and diffing logic."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.scraper.models import Job
from src.filter import filter_jobs, diff_jobs, RESEARCH_KEYWORDS, BLACKLIST_KEYWORDS


class TestFilterJobs:
    def test_research_engineer_included(self):
        jobs = [Job(title="Research Engineer", location="SF", apply_link="https://x.com/1", company="A")]
        assert filter_jobs(jobs) == jobs

    def test_research_scientist_included(self):
        jobs = [Job(title="Research Scientist", location="NY", apply_link="https://x.com/2", company="A")]
        assert filter_jobs(jobs) == jobs

    def test_ml_engineer_included(self):
        jobs = [Job(title="ML Engineer", location="Remote", apply_link="https://x.com/3", company="A")]
        assert filter_jobs(jobs) == jobs

    def test_recruiter_excluded(self):
        jobs = [Job(title="Recruiter", location="NY", apply_link="https://x.com/1", company="A")]
        assert filter_jobs(jobs) == []

    def test_sales_excluded(self):
        jobs = [Job(title="Sales Manager", location="NY", apply_link="https://x.com/1", company="A")]
        assert filter_jobs(jobs) == []

    def test_mixed_list(self):
        jobs = [
            Job(title="Research Engineer", location="SF", apply_link="https://x.com/1", company="A"),
            Job(title="Recruiter", location="NY", apply_link="https://x.com/2", company="A"),
            Job(title="ML Engineer", location="Remote", apply_link="https://x.com/3", company="A"),
            Job(title="Marketing Lead", location="LA", apply_link="https://x.com/4", company="A"),
        ]
        result = filter_jobs(jobs)
        assert len(result) == 2
        titles = {j.title for j in result}
        assert "Research Engineer" in titles
        assert "ML Engineer" in titles

    def test_blacklist_keyword(self):
        jobs = [Job(title="Research Operations Manager", location="SF", apply_link="https://x.com/1", company="A")]
        assert filter_jobs(jobs) == []

    def test_custom_blacklist(self):
        jobs = [
            Job(title="Research Engineer", location="SF", apply_link="https://x.com/1", company="A"),
            Job(title="Security Research Engineer", location="NY", apply_link="https://x.com/2", company="A"),
        ]
        result = filter_jobs(jobs, blacklist=["security"])
        assert len(result) == 1
        assert result[0].title == "Research Engineer"

    def test_empty_list(self):
        assert filter_jobs([]) == []

    def test_short_title_excluded_by_filter(self):
        """Short titles that don't match research keywords are filtered out."""
        jobs = [Job(title="AI", location="SF", apply_link="https://x.com/1", company="A")]
        result = filter_jobs(jobs)
        # 'AI' doesn't match any research keyword (standalone 'ai' is not in the list)
        assert result == []


class TestDiffJobs:
    def test_no_changes(self):
        jobs = [Job(title="Research Engineer", location="SF", apply_link="https://x.com/1", company="A")]
        new, removed = diff_jobs(jobs, jobs)
        assert new == []
        assert removed == []

    def test_one_new_job(self):
        prev = [Job(title="Research Engineer", location="SF", apply_link="https://x.com/1", company="A")]
        curr = prev + [Job(title="ML Engineer", location="Remote", apply_link="https://x.com/2", company="A")]
        new, removed = diff_jobs(curr, prev)
        assert len(new) == 1
        assert new[0].title == "ML Engineer"
        assert removed == []

    def test_one_removed_job(self):
        prev = [
            Job(title="Research Engineer", location="SF", apply_link="https://x.com/1", company="A"),
            Job(title="ML Engineer", location="Remote", apply_link="https://x.com/2", company="A"),
        ]
        curr = [prev[0]]
        new, removed = diff_jobs(curr, prev)
        assert new == []
        assert len(removed) == 1
        assert removed[0].title == "ML Engineer"

    def test_both_new_and_removed(self):
        prev = [Job(title="Old Research Engineer", location="SF", apply_link="https://x.com/1", company="A")]
        curr = [Job(title="New Research Engineer", location="NY", apply_link="https://x.com/2", company="A")]
        new, removed = diff_jobs(curr, prev)
        assert len(new) == 1
        assert new[0].title == "New Research Engineer"
        assert len(removed) == 1
        assert removed[0].title == "Old Research Engineer"

    def test_empty_prev(self):
        curr = [Job(title="Research Engineer", location="SF", apply_link="https://x.com/1", company="A")]
        new, removed = diff_jobs(curr, [])
        assert len(new) == 1
        assert removed == []

    def test_empty_curr(self):
        prev = [Job(title="Research Engineer", location="SF", apply_link="https://x.com/1", company="A")]
        new, removed = diff_jobs([], prev)
        assert new == []
        assert len(removed) == 1
