"""Unit tests for the GitHub repo storage backend."""

import base64
import json
import os
import re
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


class TestGitRepoStorageWithReport:
    """save_jobs_history with a rendered markdown report (git data API path)."""

    def setup_method(self):
        self.storage = GitRepoStorage("xj3048/frontierlab-jobs", "test-token")

    def test_save_with_report_happy_path(self, capsys):
        with patch("src.storage.git_repo_storage.requests") as mock_requests:
            mock_requests.get.return_value = _resp(200, {"object": {"sha": "HEAD123"}})
            mock_requests.post.side_effect = [
                _resp(200, {"sha": "BLOBJSON"}),   # json blob
                _resp(200, {"sha": "BLOBMD"}),     # report blob
                _resp(200, {"sha": "TREE1"}),      # tree
                _resp(201, {"sha": "COMMIT1"}),    # commit
            ]
            report = "# AI Research Jobs Report — 2026-11-02 12:00 UTC\n\n**Total positions:** 1"
            mock_requests.patch.return_value = _resp(200, {"ref": "refs/heads/main", "object": {"sha": "COMMIT1"}})
            self.storage.save_jobs_history(JOBS, report)

        # 1) ref lookup happened against the git data API
        ref_url = mock_requests.get.call_args[0][0]
        assert ref_url == "https://api.github.com/repos/xj3048/frontierlab-jobs/git/ref/heads/main"
        # 2) no single-file PUT on the happy path
        mock_requests.put.assert_not_called()

        # branch ref is advanced exactly once, after the 4th (commits) POST
        mock_requests.patch.assert_called_once()
        patch_args, patch_kwargs = mock_requests.patch.call_args
        assert patch_args[0] == "https://api.github.com/repos/xj3048/frontierlab-jobs/git/refs/heads/main"
        assert patch_kwargs["json"] == {"sha": "COMMIT1"}
        call_order = [m[0] for m in mock_requests.method_calls]
        assert call_order.count("post") == 4
        assert call_order.index("patch") > call_order.index("post")

        posts = [(c[0][0], c[1]["json"]) for c in mock_requests.post.call_args_list]
        urls = [u for u, _ in posts]
        payloads = [p for _, p in posts]

        # two blob uploads
        assert urls.count("https://api.github.com/repos/xj3048/frontierlab-jobs/git/blobs") == 2
        # json blob round-trips
        assert payloads[0]["encoding"] == "utf-8"
        decoded = json.loads(payloads[0]["content"])
        assert decoded["job_history"] == JOBS
        assert decoded["total_jobs"] == 1
        # report blob passes through verbatim
        assert payloads[1] == {"content": report, "encoding": "utf-8"}

        # tree carries base_tree + both entries with 100644
        tree_url, tree_payload = posts[2]
        assert tree_url.endswith("/git/trees")
        assert tree_payload["base_tree"] == "HEAD123"
        entries = {e["path"]: e for e in tree_payload["tree"]}
        assert entries["ai_jobs_history.json"] == {
            "path": "ai_jobs_history.json", "mode": "100644", "type": "blob", "sha": "BLOBJSON"}
        report_entry = [e for p, e in entries.items() if p.startswith("reports/")][0]
        assert report_entry["path"].startswith("reports/")
        assert report_entry["mode"] == "100644"
        assert report_entry["type"] == "blob"
        assert report_entry["sha"] == "BLOBMD"

        # commit payload
        commit_url, commit_payload = posts[3]
        assert commit_url.endswith("/git/commits")
        assert commit_payload["tree"] == "TREE1"
        assert commit_payload["parents"] == ["HEAD123"]
        assert re.fullmatch(
            r"Update job history \(1 jobs\) \+ run report \d{4}-\d{2}-\d{2}_\d{4}",
            commit_payload["message"],
        )

        out = capsys.readouterr().out
        assert "Committed job history to xj3048/frontierlab-jobs (1 jobs)" in out
        assert "Commit URL: https://github.com/xj3048/frontierlab-jobs/commit/COMMIT1" in out

    def test_save_with_report_branch_not_found_falls_back(self, capsys):
        with patch("src.storage.git_repo_storage.requests") as mock_requests:
            mock_requests.get.return_value = _resp(404)
            mock_requests.put.return_value = _resp(201, {"commit": {"sha": "P1"}})
            self.storage.save_jobs_history(JOBS, "# report")

        mock_requests.post.assert_not_called()
        mock_requests.put.assert_called_once()
        put_payload = mock_requests.put.call_args[1]["json"]
        assert "sha" not in put_payload
        decoded = json.loads(base64.b64decode(put_payload["content"]))
        assert decoded["job_history"] == JOBS
        assert "branch not found" in capsys.readouterr().out

    def test_save_with_report_commit_fails_falls_back(self, capsys):
        with patch("src.storage.git_repo_storage.requests") as mock_requests:
            mock_requests.get.side_effect = [
                _resp(200, {"object": {"sha": "HEAD123"}}),                # ref lookup
                _resp(200, {"sha": "abc123", "content": _b64({})}),        # single-file check
            ]
            mock_requests.post.side_effect = [
                _resp(200, {"sha": "BLOBJSON"}),
                _resp(200, {"sha": "BLOBMD"}),
                _resp(200, {"sha": "TREE1"}),
                _resp(500, text="boom"),                                    # commit fails
            ]
            mock_requests.put.return_value = _resp(200, {"commit": {"sha": "P2"}})
            self.storage.save_jobs_history(JOBS, "# report")  # must not raise

        out = capsys.readouterr().out
        assert "Warning: report commit failed at create commit: 500 boom" in out
        mock_requests.put.assert_called_once()
        put_payload = mock_requests.put.call_args[1]["json"]
        assert put_payload["sha"] == "abc123"
        decoded = json.loads(base64.b64decode(put_payload["content"]))
        assert decoded["job_history"] == JOBS

    def test_save_with_report_ref_update_fails_falls_back(self, capsys):
        with patch("src.storage.git_repo_storage.requests") as mock_requests:
            mock_requests.get.side_effect = [
                _resp(200, {"object": {"sha": "HEAD123"}}),                # ref lookup
                _resp(200, {"sha": "abc123", "content": _b64({})}),        # single-file check
            ]
            mock_requests.post.side_effect = [
                _resp(200, {"sha": "BLOBJSON"}),
                _resp(200, {"sha": "BLOBMD"}),
                _resp(200, {"sha": "TREE1"}),
                _resp(201, {"sha": "COMMIT1"}),
            ]
            mock_requests.patch.return_value = _resp(500, text="boom")
            mock_requests.put.return_value = _resp(200, {"commit": {"sha": "P3"}})
            self.storage.save_jobs_history(JOBS, "# report")  # must not raise

        out = capsys.readouterr().out
        assert "Warning: failed to update branch main after creating commit COMMIT1: 500 boom" in out
        mock_requests.put.assert_called_once()
        put_payload = mock_requests.put.call_args[1]["json"]
        assert put_payload["sha"] == "abc123"
        decoded = json.loads(base64.b64decode(put_payload["content"]))
        assert decoded["job_history"] == JOBS

    def test_save_without_report_uses_single_file_path(self, capsys):
        with patch("src.storage.git_repo_storage.requests") as mock_requests:
            mock_requests.get.return_value = _resp(200, {"sha": "abc123", "content": _b64({})})
            mock_requests.put.return_value = _resp(200, {"commit": {"sha": "def456"}})
            self.storage.save_jobs_history(JOBS)

        mock_requests.post.assert_not_called()
        mock_requests.put.assert_called_once()
        out = capsys.readouterr().out
        assert "Committed job history to xj3048/frontierlab-jobs (1 jobs)" in out
