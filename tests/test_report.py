"""Unit tests for the markdown run report renderer."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.report import render_run_report
from src.scraper.models import Job, DiffResult


def _job(title, company, location="SF", link=""):
    return Job(title=title, location=location, apply_link=link, company=company, job_url=None)


ALL_JOBS = {
    "CompanyA": [
        _job("Research Engineer", "CompanyA", "SF", "https://a.com/1"),
        _job("Foundations Engineer", "CompanyA", "NY", ""),
    ],
    "CompanyB": [],
}

DIFF = {
    "CompanyA": DiffResult(
        new_jobs=[_job("Brand New Role", "CompanyA", "SF", "https://a.com/new")],
        removed_jobs=[_job("Old Role", "CompanyA", "LA", "https://a.com/old")],
    )
}


class TestRenderRunReport:
    def test_header_and_summary(self):
        report = render_run_report(ALL_JOBS, DIFF)

        assert report.startswith("# AI Research Jobs Report — ")
        assert " UTC" in report.splitlines()[0]
        assert "**Total positions:** 2 | **New:** 1 | **Removed:** 1" in report

    def test_new_and_removed_sections(self):
        report = render_run_report(ALL_JOBS, DIFF)

        assert "## 🆕 New positions" in report
        assert "## ❌ Removed positions" in report
        new_section = report.split("## 🆕 New positions")[1].split("## ❌ Removed positions")[0]
        removed_section = report.split("## ❌ Removed positions")[1].split("## All positions")[0]

        assert "### CompanyA" in new_section
        assert "- **Brand New Role** — 📍 SF" in new_section
        assert "  [Apply](https://a.com/new)" in new_section
        assert "### CompanyA" in removed_section
        assert "- **Old Role** — 📍 LA" in removed_section
        assert "  [Apply](https://a.com/old)" in removed_section

    def test_no_apply_link_omits_apply_line(self):
        diff = {"CompanyA": DiffResult(new_jobs=[_job("No Link Role", "CompanyA", "SF", "")])}
        report = render_run_report(ALL_JOBS, diff)

        new_section = report.split("## 🆕 New positions")[1].split("## ❌ Removed positions")[0]
        assert "- **No Link Role** — 📍 SF" in new_section
        assert "[Apply]" not in new_section

    def test_no_new_and_no_removed_placeholders(self):
        report = render_run_report(ALL_JOBS, {})

        assert "_No new positions since last check._" in report
        assert "_No positions removed._" in report
        assert "### CompanyA" in report.split("## All positions")[1]

    def test_all_positions_table(self):
        report = render_run_report(ALL_JOBS, DIFF)

        all_section = report.split("## All positions")[1]
        assert "### CompanyA (2)" in all_section
        assert "| # | Title | Location | Apply |" in all_section
        assert "| 1 | Research Engineer | SF | [link](https://a.com/1) |" in all_section
        assert "| 2 | Foundations Engineer | NY |  |" in all_section

    def test_empty_all_jobs_renders_gracefully(self):
        report = render_run_report({}, {})

        assert "**Total positions:** 0 | **New:** 0 | **Removed:** 0" in report
        assert "## All positions" in report
        assert "_No new positions since last check._" in report
        assert "_No positions removed._" in report

    def test_zero_job_company_placeholder(self):
        report = render_run_report(ALL_JOBS, DIFF)

        assert "### CompanyB (0)" in report
        assert "_No positions currently listed._" in report

    def test_pipes_in_location_are_escaped(self):
        jobs = {
            "CompanyA": [
                _job("Research Engineer", "CompanyA", "San Francisco, CA | New York City, NY | Seattle, WA", "https://a.com/1"),
            ]
        }
        report = render_run_report(jobs, {})
        all_section = report.split("## All positions")[1]

        assert (
            "| 1 | Research Engineer | San Francisco, CA \\| New York City, NY \\| Seattle, WA | [link](https://a.com/1) |"
        ) in all_section

    def test_newlines_in_location_are_collapsed(self):
        jobs = {"CompanyA": [_job("Role", "CompanyA", "NY\nSF", "https://a.com/1")]}
        report = render_run_report(jobs, {})

        assert "| 1 | Role | NY SF | [link](https://a.com/1) |" in report.split("## All positions")[1]

    def test_pipe_in_title_is_escaped(self):
        jobs = {"CompanyA": [_job("Role | Senior", "CompanyA", "NY", "")]}
        report = render_run_report(jobs, {})

        assert "| 1 | Role \\| Senior | NY |  |" in report.split("## All positions")[1]

    def test_footer_snapshot_link(self):
        report = render_run_report(ALL_JOBS, DIFF)

        assert "Machine-readable snapshot: [ai_jobs_history.json]" in report
        assert "https://github.com/xj3048/frontierlab-jobs/blob/main/ai_jobs_history.json" in report
        assert report.rstrip().endswith("ai_jobs_history.json)*")
