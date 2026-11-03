"""Unit tests for the ByteDance Seed scraper (Seed JSON API)."""

import os
import sys
from unittest import mock

import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.scraper.scrapers.seed import SeedScraper


def _record(job_name_en="", city_en="", ext_en="",
            job_name_zh="", city_zh="", ext_zh="",
            status=2, position=100):
    """One record of the job_list_v2 API response."""
    return {
        "JobMeta": {
            "ID": 10073,
            "Status": status,
            "Position": position,
            "CreatedTime": 0,
            "UpdatedTime": 0,
            "IsOversea": False,
        },
        "SubJobEn": {"JobName": job_name_en, "JobTypeName": "", "City": city_en, "ExternalLink": ext_en},
        "SubJobZh": {"JobName": job_name_zh, "JobTypeName": "", "City": city_zh, "ExternalLink": ext_zh},
    }


def _api_payload(job_list, status_code=0, status_message="success"):
    return {"job_list": job_list, "BaseResp": {"StatusMessage": status_message, "StatusCode": status_code}}


PAGE_OK = _api_payload([
    # English-only record
    _record(
        job_name_en="Research Scientist (Seed Model - LLM)",
        city_en="San Jose",
        ext_en="https://jobs.bytedance.com/en/position/7233349076828490043/detail",
        position=7233349076828490043,
    ),
    # Chinese-only record
    _record(
        job_name_zh="大语言模型Code Agent算法工程师-Seed",
        city_zh="北京/上海",
        ext_zh="https://jobs.bytedance.com/experienced/position/7631215609552636165/detail",
        position=7631215609552636165,
    ),
    # Both external links empty -> fallback link built from Position id
    _record(
        job_name_en="Intern, Seed",
        city_en="Singapore",
        position=7100000000000000111,
    ),
])


def _mock_get_with(payload):
    """Context manager: patch the module's requests.get to return a response whose .json() yields payload."""
    resp = mock.Mock()
    resp.json.return_value = payload
    resp.raise_for_status = mock.Mock()
    return mock.patch("src.scraper.scrapers.seed.requests.get", return_value=resp)


class TestSeedScrape:
    def test_mixed_en_zh_records(self):
        scraper = SeedScraper()
        with _mock_get_with(PAGE_OK):
            jobs = scraper.scrape()

        assert len(jobs) == 3
        assert all(j.company == "ByteDance Seed" for j in jobs)

        # English record uses English fields
        assert jobs[0].title == "Research Scientist (Seed Model - LLM)"
        assert jobs[0].location == "San Jose"
        assert jobs[0].apply_link == "https://jobs.bytedance.com/en/position/7233349076828490043/detail"

        # Chinese-only record falls back to Chinese fields
        assert jobs[1].title == "大语言模型Code Agent算法工程师-Seed"
        assert jobs[1].location == "北京/上海"
        assert jobs[1].apply_link == "https://jobs.bytedance.com/experienced/position/7631215609552636165/detail"

        # Empty external links -> fallback link from Position id
        assert jobs[2].title == "Intern, Seed"
        assert jobs[2].location == "Singapore"
        assert jobs[2].apply_link == "https://jobs.bytedance.com/experienced/position/7100000000000000111/detail"

    def test_nonzero_status_code_returns_empty(self):
        scraper = SeedScraper()
        payload = _api_payload(PAGE_OK["job_list"], status_code=500, status_message="internal error")
        with _mock_get_with(payload):
            jobs = scraper.scrape()

        assert jobs == []

    def test_network_error_returns_empty(self):
        scraper = SeedScraper()
        with mock.patch(
            "src.scraper.scrapers.seed.requests.get",
            side_effect=requests.RequestException("connection failed"),
        ):
            jobs = scraper.scrape()

        assert jobs == []

    def test_empty_title_record_is_skipped(self):
        scraper = SeedScraper()
        payload = _api_payload([
            _record(job_name_en="Valid Job", city_en="Beijing"),
            _record(position=123),  # both JobName fields empty
        ])
        with _mock_get_with(payload):
            jobs = scraper.scrape()

        assert len(jobs) == 1
        assert jobs[0].title == "Valid Job"

    def test_closed_status_record_is_skipped(self):
        scraper = SeedScraper()
        payload = _api_payload([
            _record(job_name_en="Open Job", city_en="Shanghai"),
            _record(job_name_en="Closed Job", city_en="Beijing", status=0),
        ])
        with _mock_get_with(payload):
            jobs = scraper.scrape()

        assert len(jobs) == 1
        assert jobs[0].title == "Open Job"
