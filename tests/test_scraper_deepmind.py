"""Unit tests for the DeepMind scraper (Google careers platform)."""

import json
import os
import sys
from unittest import mock

import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.scraper.scrapers.deepmind import DeepMindScraper, _extract_job_records, _slugify


def _location(display, city, state, country):
    """One entry of a record's locations field (rec[9])."""
    return [display, [display], city, state, country]


def _record(job_id, title, locations):
    """A 20-field record matching the embedded JSON structure (only 0, 1, 9 are used)."""
    rec = [""] * 20
    rec[0] = job_id
    rec[1] = title
    rec[3] = "x"
    rec[4] = "y"
    rec[7] = "DeepMind"
    rec[9] = locations
    rec[10] = "z"
    rec[19] = "tail"
    return rec


REC1 = _record(
    "91166074854089414",
    "Research Scientist, Robotics, DeepMind",
    [_location("London, UK", "London", "England", "United Kingdom")],
)
REC2 = _record(
    "91166074854089415",
    "Machine Learning Engineer, DeepMind",
    [_location("New York, US", "New York", "NY", "United States")],
)
REC3 = _record(
    "91166074854089416",
    "Software Engineer, DeepMind",
    [_location("Paris, FR", "Paris", "IDF", "France")],
)
REC_MULTI = _record(
    "91166074854089417",
    "Research Scientist, DeepMind",
    [
        _location("London, UK", "London", "England", "United Kingdom"),
        _location("New York, US", "New York", "NY", "United States"),
    ],
)

# Corrupt records: one balanced-but-invalid JSON array (trailing comma),
# one partial record whose closing bracket never appears.
CORRUPT = '["1234567890123456789", "Broken Job, DeepMind", ]'
PARTIAL = '["9876543210987654321", "Partial Job, DeepMind", "never closed'

PAGE_1 = (
    '<html><head><script>'
    "AF_initDataCallback({key: 'jobData', data: ["
    + json.dumps(REC1)
    + ", "
    + json.dumps(REC2)
    + ']})</script></head><body></body></html>'
)
PAGE_2 = (
    '<html><script>AF_initDataCallback({data: ['
    + json.dumps(REC3)
    + ']})</script></html>'
)
PAGE_MULTI = '<html><script>AF_initDataCallback({data: [' + json.dumps(REC_MULTI) + ']})</script></html>'
PAGE_CORRUPT = '<html><script>' + CORRUPT + " " + PARTIAL + " " + json.dumps(REC1) + '</script></html>'


def _page_response(text):
    resp = mock.Mock()
    resp.text = text
    resp.raise_for_status = mock.Mock()
    return resp


class TestExtractJobRecords:
    def test_returns_expected_records(self):
        records = _extract_job_records(PAGE_1)
        assert len(records) == 2
        assert records[0][0] == "91166074854089414"
        assert records[0][1] == "Research Scientist, Robotics, DeepMind"
        assert records[1][0] == "91166074854089415"
        assert records[1][1] == "Machine Learning Engineer, DeepMind"

    def test_corrupt_and_partial_records_are_skipped(self):
        records = _extract_job_records(PAGE_CORRUPT)
        assert len(records) == 1
        assert records[0][0] == "91166074854089414"

    def test_empty_html_returns_no_records(self):
        assert _extract_job_records("") == []


class TestSlug:
    def test_slug_derived_from_title(self):
        assert _slugify("Research Scientist, Robotics, DeepMind") == "research-scientist-robotics-deepmind"
        assert _slugify("Machine Learning Engineer, DeepMind") == "machine-learning-engineer-deepmind"


class TestDeepMindScrape:
    def test_repeated_page_yields_no_new_ids_and_stops(self):
        scraper = DeepMindScraper()
        with mock.patch(
            "src.scraper.scrapers.deepmind.requests.get",
            side_effect=[_page_response(PAGE_1), _page_response(PAGE_1)],
        ) as mock_get:
            jobs = scraper.scrape()

        assert len(jobs) == 2
        assert mock_get.call_count == 2
        assert "page=1" in mock_get.call_args_list[0][0][0]

        job1, job2 = jobs
        assert job1.title == "Research Scientist, Robotics, DeepMind"
        assert job1.location == "London, UK"
        assert job1.company == "DeepMind"
        assert job1.apply_link == "https://careers.google.com/jobs/results/91166074854089414-research-scientist-robotics-deepmind"

        assert job2.title == "Machine Learning Engineer, DeepMind"
        assert job2.location == "New York, US"
        assert job2.apply_link == "https://careers.google.com/jobs/results/91166074854089415-machine-learning-engineer-deepmind"

    def test_second_page_with_one_new_record_yields_three_jobs(self):
        scraper = DeepMindScraper()
        # Page 2 brings one new id, so the loop advances to page 3,
        # which returns page 2 data again -> no new ids -> stop.
        with mock.patch(
            "src.scraper.scrapers.deepmind.requests.get",
            side_effect=[_page_response(PAGE_1), _page_response(PAGE_2), _page_response(PAGE_2)],
        ) as mock_get:
            jobs = scraper.scrape()

        assert len(jobs) == 3
        assert mock_get.call_count == 3
        assert jobs[2].title == "Software Engineer, DeepMind"
        assert jobs[2].location == "Paris, FR"
        assert jobs[2].apply_link == "https://careers.google.com/jobs/results/91166074854089416-software-engineer-deepmind"

    def test_network_error_returns_empty_list(self):
        scraper = DeepMindScraper()
        with mock.patch(
            "src.scraper.scrapers.deepmind.requests.get",
            side_effect=requests.RequestException("connection failed"),
        ):
            jobs = scraper.scrape()

        assert jobs == []

    def test_multiple_locations_joined_with_pipe(self):
        scraper = DeepMindScraper()
        with mock.patch(
            "src.scraper.scrapers.deepmind.requests.get",
            side_effect=[_page_response(PAGE_MULTI), _page_response(PAGE_MULTI)],
        ):
            jobs = scraper.scrape()

        assert len(jobs) == 1
        assert jobs[0].location == "London, UK | New York, US"

    def test_corrupt_records_do_not_break_scrape(self):
        scraper = DeepMindScraper()
        with mock.patch(
            "src.scraper.scrapers.deepmind.requests.get",
            side_effect=[_page_response(PAGE_CORRUPT), _page_response(PAGE_CORRUPT)],
        ):
            jobs = scraper.scrape()

        assert len(jobs) == 1
        assert jobs[0].title == "Research Scientist, Robotics, DeepMind"
