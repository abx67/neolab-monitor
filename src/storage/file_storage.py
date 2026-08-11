"""File-based storage backend for job history."""

import json
import os
from typing import Dict, List

from src.storage.base import StorageABC


class FileStorage(StorageABC):
    """Persist job history to a local JSON file."""

    def __init__(self, filepath: str = "ai_jobs_history.json"):
        self.filepath = filepath

    def load_previous_jobs(self) -> Dict[str, List[Dict[str, str]]]:
        if not os.path.exists(self.filepath):
            return {}
        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            print(f"Warning: could not load history from {self.filepath}: {e}")
            return {}

    def save_jobs_history(self, jobs: Dict[str, List[Dict[str, str]]]) -> None:
        try:
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump(jobs, f, indent=2, ensure_ascii=False)
        except OSError as e:
            print(f"Error saving job history to {self.filepath}: {e}")
