"""Unit tests for the email notification HTML builder."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.config import Config
from src.notifier import EmailNotifier
from src.scraper.models import Job


def _job(title, company, location="SF", link=""):
    return Job(title=title, location=location, apply_link=link, company=company, job_url=None)


REPORT_URL = "https://github.com/x/repo/blob/main/reports/2026-01-01_0000.md"


class TestBuildHtml:
    def setup_method(self):
        config = Config(sender_email="a@x.com", sender_password="p", recipient_email="r@x.com")
        self.notifier = EmailNotifier(config)
        self.all_jobs = {
            "CompanyA": [_job("Legacy Staff Engineer", "CompanyA", "SF", "https://a.com/1")],
        }
        self.new_jobs = {"CompanyA": [_job("Brand New Role", "CompanyA", "SF", "https://a.com/new")]}
        self.removed_jobs = {"CompanyA": [_job("Old Role", "CompanyA", "LA", "")]}

    def test_new_and_removed_sections_present(self):
        html = self.notifier._build_html(self.all_jobs, self.new_jobs, self.removed_jobs)

        assert "🆕 New Jobs" in html
        assert "Brand New Role" in html
        assert "Removed Jobs" in html
        assert "Old Role" in html

    def test_all_positions_listing_removed(self):
        html = self.notifier._build_html(self.all_jobs, self.new_jobs, self.removed_jobs)

        assert "All Research Engineer Positions" not in html
        # header "Total Positions" still reflects all_jobs
        assert "<strong>Total Positions:</strong> 1" in html
        # listing-only title (present only in all_jobs) must not appear
        assert "Legacy Staff Engineer" not in html

    def test_report_url_link_rendered(self):
        html = self.notifier._build_html(self.all_jobs, self.new_jobs, self.removed_jobs, REPORT_URL)

        assert f'<a href="{REPORT_URL}"' in html
        assert "📊 View the full live report on GitHub →" in html

    def test_no_report_url_no_link(self):
        html = self.notifier._build_html(self.all_jobs, self.new_jobs, self.removed_jobs, None)

        assert "View the full live report on GitHub" not in html

    def test_no_changes_shows_notice_and_omits_sections(self):
        html = self.notifier._build_html(self.all_jobs, {}, {}, REPORT_URL)

        assert "✅ No changes" in html
        assert "No new or removed positions since the last check" in html
        assert "🆕 New Jobs" not in html
        assert "Removed Jobs" not in html
        # live report link still attached
        assert f'<a href="{REPORT_URL}"' in html

    def test_changes_hide_no_changes_notice(self):
        html = self.notifier._build_html(self.all_jobs, self.new_jobs, self.removed_jobs)

        assert "✅ No changes" not in html
