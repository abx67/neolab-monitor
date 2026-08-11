"""Factory for creating storage backend instances."""

from typing import Optional

from src.config import Config
from src.storage.base import StorageABC
from src.storage.file_storage import FileStorage
from src.storage.gist_storage import GistStorage


def create_storage(config: Config) -> StorageABC:
    """Create the appropriate storage backend based on config.

    Priority: GitHub Gist (if token available) > file-based fallback.
    """
    if config.github_token:
        try:
            return GistStorage(config.github_token, config.github_gist_id)
        except Exception as e:
            print(f"Warning: Gist storage failed: {e}")

    print("Using file-based storage (data will be lost on Heroku restarts)")
    print("For persistent storage, set GITHUB_TOKEN and GITHUB_GIST_ID")
    return FileStorage(config.jobs_history_file)
