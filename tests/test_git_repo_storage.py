"""Unit tests for the GitHub repo storage backend."""

import base64
import json
import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.storage.git_repo_storage import GitRepoStorage


def _resp(status_code, payload=None, text=""):
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = text
    resp.json.return_value = payload
    resp.raise_for_status.return_value = None
    return resp


def _b64(payload):
    return base64.b64encode(json.dumps(payload).encode()).decode()


JOBS = {
    "CompanyA": [
        {"title": "Research Engineer", "location": "SF", "apply_link": "https://a.com/1", "company": "CompanyA"},
    ]
}


class TestGitRepoStorage:
    def setup_method(self):
        self.storage = GitRepoStorage("xj3048/frontierlab-jobs", "test-token")

    def test_load_success(self):
        payload = {"job_history": JOBS, "total_jobs": 1, "last_updated": "2026-01-01T00:00:00"}
        with patch("src.storage.git_repo_storage.requests") as mock_requests:
            mock_requests.get.return_value = _resp(200, {"content": _b64(payload)})
            result = self.storage.load_previous_jobs()

        assert result == JOBS
        url = mock_requests.get.call_args[0][0]
        assert url.startswith("https://api.github.com/repos/xj3048/frontierlab-jobs/contents/")
        assert "ref=main" in url

    def test_load_404_returns_empty(self):
        with patch("src.storage.git_repo_storage.requests") as mock_requests:
            mock_requests.get.return_value = _resp(404)
            result = self.storage.load_previous_jobs()

        assert result == {}

    def test_save_file_missing_omits_sha(self):
        with patch("src.storage.git_repo_storage.requests") as mock_requests:
            mock_requests.get.return_value = _resp(404)
            mock_requests.put.return_value = _resp(201, {"commit": {"sha": "newsha1"}})

            self.storage.save_jobs_history(JOBS)

        put_payload = mock_requests.put.call_args[1]["json"]
        assert "sha" not in put_payload
        assert put_payload["branch"] == "main"
        decoded = json.loads(base64.b64decode(put_payload["content"]))
        assert decoded["job_history"] == JOBS
        assert "last_updated" in decoded
        assert decoded["total_jobs"] == 1
        assert put_payload["message"] == "Update job history (1 jobs)"

    def test_save_file_exists_includes_sha(self):
        with patch("src.storage.git_repo_storage.requests") as mock_requests:
            mock_requests.get.return_value = _resp(200, {"sha": "abc123", "content": _b64({})})
            mock_requests.put.return_value = _resp(200, {"commit": {"sha": "def456"}})

            self.storage.save_jobs_history(JOBS)

        put_payload = mock_requests.put.call_args[1]["json"]
        assert put_payload["sha"] == "abc123"

    def test_save_put_failure_no_exception(self):
        with patch("src.storage.git_repo_storage.requests") as mock_requests:
            mock_requests.get.return_value = _resp(200, {"sha": "abc123", "content": _b64({})})
            mock_requests.put.return_value = _resp(500, text="Internal Server Error")

            self.storage.save_jobs_history(JOBS)  # must not raise

        mock_requests.put.assert_called_once()
