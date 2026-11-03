"""GitHub Gist storage backend for job history."""

import json
import os
import requests
from typing import Dict, List, Optional

from src.storage.base import StorageABC


class GistStorage(StorageABC):
    """Persist job history to a private GitHub Gist."""

    def __init__(self, token: str, gist_id: Optional[str] = None):
        self.token = token
        self.gist_id = gist_id
        self.headers = {
            "Authorization": f"token {self.token}",
            "Accept": "application/vnd.github.v3+json",
        }

    def _get_gist_file_content(self) -> str:
        """Fetch and return the content of the history file from the gist."""
        if not self.gist_id:
            return ""
        resp = requests.get(
            f"https://api.github.com/gists/{self.gist_id}",
            headers=self.headers,
            timeout=10,
        )
        resp.raise_for_status()
        gist_data = resp.json()
        return gist_data["files"]["ai_jobs_history.json"]["content"]

    def load_previous_jobs(self) -> Dict[str, List[Dict[str, str]]]:
        if not self.gist_id:
            print("No Gist ID configured — starting fresh.")
            return {}
        try:
            content = self._get_gist_file_content()
            if not content:
                return {}
            data = json.loads(content)
            job_history = data.get("job_history", {})
            total = sum(len(jobs) for jobs in job_history.values())
            print(f"Loaded {total} jobs from GitHub Gist")
            return job_history
        except Exception as e:
            print(f"Warning: could not load from Gist: {e}")
            return {}

    def save_jobs_history(self, jobs: Dict[str, List[Dict[str, str]]], report_md: Optional[str] = None) -> None:
        data = {
            "job_history": jobs,
            "last_updated": __import__("datetime").datetime.now().isoformat(),
            "total_jobs": sum(len(company_jobs) for company_jobs in jobs.values()),
        }
        content = json.dumps(data, indent=2, ensure_ascii=False)

        if not self.gist_id:
            gist_payload = {
                "description": "AI Jobs Scraper - Job History",
                "public": False,
                "files": {"ai_jobs_history.json": {"content": content}},
            }
            resp = requests.post(
                "https://api.github.com/gists",
                json=gist_payload,
                headers=self.headers,
                timeout=10,
            )
            if resp.status_code == 201:
                result = resp.json()
                self.gist_id = result["id"]
                print(f"Created new Gist: {self.gist_id}")
                print(f"Set GITHUB_GIST_ID={self.gist_id} to reuse this Gist")
            else:
                print(f"Failed to create Gist: {resp.status_code} {resp.text}")
            return

        update_payload = {
            "files": {"ai_jobs_history.json": {"content": content}},
        }
        resp = requests.patch(
            f"https://api.github.com/gists/{self.gist_id}",
            json=update_payload,
            headers=self.headers,
            timeout=10,
        )
        if resp.status_code == 200:
            total = data["total_jobs"]
            print(f"Updated Gist with {total} jobs")
        else:
            print(f"Failed to update Gist: {resp.status_code}")
