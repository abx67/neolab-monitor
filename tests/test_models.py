"""Unit tests for Job model serialization and equality."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.scraper.models import Job, DiffResult, ScrapeResult


class TestJob:
    def test_creation(self):
        j = Job(title="Research Engineer", location="SF", apply_link="https://x.com/1", company="A")
        assert j.title == "Research Engineer"
        assert j.company == "A"
        assert j.job_url is None

    def test_equality(self):
        j1 = Job(title="RE", location="SF", apply_link="a", company="A")
        j2 = Job(title="RE", location="NY", apply_link="b", company="A")
        assert j1 == j2  # same title + company

    def test_inequality_different_title(self):
        j1 = Job(title="RE", location="SF", apply_link="a", company="A")
        j2 = Job(title="ML Engineer", location="SF", apply_link="a", company="A")
        assert j1 != j2

    def test_inequality_different_company(self):
        j1 = Job(title="RE", location="SF", apply_link="a", company="A")
        j2 = Job(title="RE", location="SF", apply_link="a", company="B")
        assert j1 != j2

    def test_hash(self):
        j1 = Job(title="RE", location="SF", apply_link="a", company="A")
        j2 = Job(title="RE", location="NY", apply_link="b", company="A")
        assert hash(j1) == hash(j2)

    def test_to_dict_roundtrip(self):
        j = Job(title="RE", location="SF", apply_link="https://x.com/1", company="A", job_url="https://x.com/1")
        d = j.to_dict()
        j2 = Job.from_dict(d)
        assert j2.title == j.title
        assert j2.location == j.location
        assert j2.apply_link == j.apply_link
        assert j2.company == j.company
        assert j2.job_url == j.job_url

    def test_from_dict_missing_optional(self):
        d = {"title": "RE", "location": "SF", "apply_link": "https://x.com/1", "company": "A"}
        j = Job.from_dict(d)
        assert j.job_url is None


class TestDiffResult:
    def test_empty(self):
        d = DiffResult()
        assert d.new_jobs == []
        assert d.removed_jobs == []
        assert not d.has_changes
        assert d.new_count == 0
        assert d.removed_count == 0

    def test_with_jobs(self):
        j1 = Job(title="New", location="SF", apply_link="a", company="A")
        j2 = Job(title="Removed", location="NY", apply_link="b", company="A")
        d = DiffResult(new_jobs=[j1], removed_jobs=[j2])
        assert d.has_changes
        assert d.new_count == 1
        assert d.removed_count == 1


class TestScrapeResult:
    def test_basic(self):
        j = Job(title="RE", location="SF", apply_link="a", company="A")
        r = ScrapeResult(jobs=[j], company="TestCo")
        assert r.company == "TestCo"
        assert r.new_count == 1

    def test_to_dict_roundtrip(self):
        j = Job(title="RE", location="SF", apply_link="https://x.com/1", company="A", job_url="https://x.com/1")
        r = ScrapeResult(jobs=[j], company="TestCo")
        d = r.to_dict()
        r2 = ScrapeResult.from_dict(d)
        assert r2.company == r.company
        assert len(r2.jobs) == 1
        assert r2.jobs[0].title == j.title
