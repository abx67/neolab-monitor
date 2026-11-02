"""GitHub repo storage backend for job history (one git commit per run)."""

import base64
import json
import requests
from datetime import datetime
from typing import Dict, List

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

    def save_jobs_history(self, jobs: Dict[str, List[Dict[str, str]]]) -> None:
        data = {
            "job_history": jobs,
            "last_updated": datetime.now().isoformat(),
            "total_jobs": sum(len(company_jobs) for company_jobs in jobs.values()),
        }
        content_b64 = base64.b64encode(
            json.dumps(data, indent=2, ensure_ascii=False).encode()
        ).decode()

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
            "message": f"Update job history ({data['total_jobs']} jobs)",
            "content": content_b64,
            "branch": self.branch,
        }
        if sha:
            put_payload["sha"] = sha

        resp = requests.put(self.contents_url, json=put_payload, headers=self.headers, timeout=10)
        if resp.status_code in (200, 201):
            result = resp.json()
            sha = result["commit"]["sha"]
            print(f"Committed job history to {self.repo} ({data['total_jobs']} jobs)")
            print(f"Commit URL: https://github.com/{self.repo}/commit/{sha}")
        else:
            print(f"Failed to commit to {self.repo}: {resp.status_code} {resp.text}")
