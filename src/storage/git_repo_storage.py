"""GitHub repo storage backend for job history (one git commit per run)."""

import base64
import json
import requests
from datetime import datetime, timezone
from typing import Dict, List, Optional

from src.storage.base import StorageABC


class GitRepoStorage(StorageABC):
    """Persist job history to a GitHub repo via the REST contents API."""

    def __init__(self, repo: str, token: str, branch: str = "main", filepath: str = "ai_jobs_history.json"):
        self.repo = repo
        self.token = token
        self.branch = branch
        self.filepath = filepath
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github.v3+json",
        }
        self.contents_url = f"https://api.github.com/repos/{self.repo}/contents/{self.filepath}"
        self.data_api = f"https://api.github.com/repos/{self.repo}"
        self.last_report_url: Optional[str] = None

    def load_previous_jobs(self) -> Dict[str, List[Dict[str, str]]]:
        try:
            resp = requests.get(
                f"{self.contents_url}?ref={self.branch}",
                headers=self.headers,
                timeout=10,
            )
            if resp.status_code == 404:
                print(f"No history file in {self.repo} yet — starting fresh.")
                return {}
            resp.raise_for_status()
            data = json.loads(base64.b64decode(resp.json()["content"]))
            job_history = data.get("job_history", {})
            total = sum(len(jobs) for jobs in job_history.values())
            print(f"Loaded {total} jobs from {self.repo}")
            return job_history
        except Exception as e:
            print(f"Warning: could not load from {self.repo}: {e}")
            return {}

    def get_report_url(self) -> Optional[str]:
        """URL of the latest rendered report, or None when no report was produced."""
        return self.last_report_url

    def save_jobs_history(
        self,
        jobs: Dict[str, List[Dict[str, str]]],
        report_md: Optional[str] = None,
    ) -> None:
        data = {
            "job_history": jobs,
            "last_updated": datetime.now().isoformat(),
            "total_jobs": sum(len(company_jobs) for company_jobs in jobs.values()),
        }
        json_text = json.dumps(data, indent=2, ensure_ascii=False)
        total = data["total_jobs"]

        if report_md is not None:
            try:
                committed = self._commit_with_report(json_text, report_md, total)
            except Exception as e:
                print(f"Warning: report commit failed at unknown step: {e}")
                committed = False
            if committed:
                return

        self._save_single_file(json_text, total)

    def _commit_with_report(self, json_text: str, report_md: str, total: int) -> bool:
        """Atomically commit the JSON snapshot plus the rendered report (git data API)."""
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M")
        report_path = f"reports/{ts}.md"

        try:
            resp = requests.get(
                f"{self.data_api}/git/ref/heads/{self.branch}",
                headers=self.headers,
                timeout=10,
            )
        except Exception as e:
            print(f"Warning: report commit failed at ref lookup: {e}")
            return False
        if resp.status_code == 404:
            print("Warning: branch not found — falling back to single-file commit")
            return False
        if resp.status_code != 200:
            print(f"Warning: report commit failed at ref lookup: {resp.status_code} {resp.text}")
            return False
        head_sha = resp.json()["object"]["sha"]

        blob_json = self._create_blob(json_text)
        if blob_json is None:
            return False
        blob_md = self._create_blob(report_md)
        if blob_md is None:
            return False

        tree_sha = self._create_tree(
            head_sha,
            [
                {"path": self.filepath, "mode": "100644", "type": "blob", "sha": blob_json},
                {"path": report_path, "mode": "100644", "type": "blob", "sha": blob_md},
            ],
        )
        if tree_sha is None:
            return False

        resp = requests.post(
            f"{self.data_api}/git/commits",
            json={
                "message": f"Update job history ({total} jobs) + run report {ts}",
                "tree": tree_sha,
                "parents": [head_sha],
            },
            headers=self.headers,
            timeout=10,
        )
        if resp.status_code not in (200, 201):
            print(f"Warning: report commit failed at create commit: {resp.status_code} {resp.text}")
            return False
        commit_sha = resp.json()["sha"]

        # POST /git/commits creates the commit object but does NOT move the branch ref.
        # Update the ref so the commit (and the report file) are actually reachable.
        try:
            ref_resp = requests.patch(
                f"{self.data_api}/git/refs/heads/{self.branch}",
                json={"sha": commit_sha},
                headers=self.headers,
                timeout=10,
            )
        except Exception as e:
            print(f"Warning: failed to update branch {self.branch} after creating commit {commit_sha}: {e}")
            return False
        if ref_resp.status_code not in (200, 201):
            print(f"Warning: failed to update branch {self.branch} after creating commit {commit_sha}: {ref_resp.status_code} {ref_resp.text}")
            return False

        self.last_report_url = f"https://github.com/{self.repo}/blob/{self.branch}/reports/{ts}.md"
        print(f"Committed job history to {self.repo} ({total} jobs)")
        print(f"Commit URL: https://github.com/{self.repo}/commit/{commit_sha}")
        return True

    def _create_blob(self, content: str) -> Optional[str]:
        """POST /git/blobs; returns the new blob sha or None (with a warning)."""
        resp = requests.post(
            f"{self.data_api}/git/blobs",
            json={"content": content, "encoding": "utf-8"},
            headers=self.headers,
            timeout=10,
        )
        if resp.status_code in (200, 201):
            return resp.json()["sha"]
        print(f"Warning: report commit failed at create blob: {resp.status_code} {resp.text}")
        return None

    def _create_tree(self, head_sha: str, tree_entries: List[dict]) -> Optional[str]:
        """POST /git/trees based on head_sha; returns the new tree sha or None (with a warning)."""
        resp = requests.post(
            f"{self.data_api}/git/trees",
            json={"base_tree": head_sha, "tree": tree_entries},
            headers=self.headers,
            timeout=10,
        )
        if resp.status_code in (200, 201):
            return resp.json()["sha"]
        print(f"Warning: report commit failed at create tree: {resp.status_code} {resp.text}")
        return None

    def _save_single_file(self, json_text: str, total: int) -> None:
        """Best-effort single-file commit of the JSON snapshot via the contents API."""
        self.last_report_url = None
        content_b64 = base64.b64encode(json_text.encode()).decode()

        # Determine if the file already exists (so we include "sha" when updating)
        sha = None
        try:
            resp = requests.get(
                f"{self.contents_url}?ref={self.branch}",
                headers=self.headers,
                timeout=10,
            )
            if resp.status_code == 200:
                sha = resp.json().get("sha")
            elif resp.status_code != 404:
                print(f"Warning: could not check existing file in {self.repo}: {resp.status_code} {resp.text}")
        except Exception as e:
            print(f"Warning: could not check existing file in {self.repo}: {e}")

        put_payload = {
            "message": f"Update job history ({total} jobs)",
            "content": content_b64,
            "branch": self.branch,
        }
        if sha:
            put_payload["sha"] = sha

        resp = requests.put(self.contents_url, json=put_payload, headers=self.headers, timeout=10)
        if resp.status_code in (200, 201):
            commit_sha = resp.json()["commit"]["sha"]
            print(f"Committed job history to {self.repo} ({total} jobs)")
            print(f"Commit URL: https://github.com/{self.repo}/commit/{commit_sha}")
        else:
            print(f"Failed to commit to {self.repo}: {resp.status_code} {resp.text}")
