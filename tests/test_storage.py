"""Unit tests for storage backends."""

import sys
import os
import json
import tempfile
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.storage.file_storage import FileStorage


class TestFileStorage:
    def test_load_empty(self, tmp_path):
        storage = FileStorage(str(tmp_path / "empty.json"))
        result = storage.load_previous_jobs()
        assert result == {}

    def test_save_and_load(self, tmp_path):
        filepath = str(tmp_path / "jobs.json")
        storage = FileStorage(filepath)

        jobs = {
            "CompanyA": [
                {"title": "Research Engineer", "location": "SF", "apply_link": "https://a.com/1", "company": "CompanyA"},
            ]
        }
        storage.save_jobs_history(jobs)

        loaded = storage.load_previous_jobs()
        assert loaded == jobs

    def test_overwrite(self, tmp_path):
        filepath = str(tmp_path / "jobs.json")
        storage = FileStorage(filepath)

        storage.save_jobs_history({"A": [{"title": "Job1", "location": "SF", "apply_link": "a", "company": "A"}]})
        storage.save_jobs_history({"B": [{"title": "Job2", "location": "NY", "apply_link": "b", "company": "B"}]})

        loaded = storage.load_previous_jobs()
        assert "A" not in loaded
        assert "B" in loaded
        assert loaded["B"][0]["title"] == "Job2"

    def test_corrupted_file_returns_empty(self, tmp_path):
        filepath = str(tmp_path / "bad.json")
        with open(filepath, "w") as f:
            f.write("not valid json {{{")
        storage = FileStorage(filepath)
        result = storage.load_previous_jobs()
        assert result == {}
