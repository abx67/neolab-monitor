"""Factory for creating storage backend instances."""

from typing import Optional

from src.config import Config
from src.storage.base import StorageABC
from src.storage.file_storage import FileStorage
from src.storage.git_repo_storage import GitRepoStorage
from src.storage.gist_storage import GistStorage


def create_storage(config: Config) -> StorageABC:
    """Create the appropriate storage backend based on config.

    Priority: git repo (if repo + token available) > GitHub Gist (if token available) > file-based fallback.
    """
    if config.git_repo and config.git_token:
        return GitRepoStorage(config.git_repo, config.git_token, config.git_branch)
    if config.github_token:
        try:
            return GistStorage(config.github_token, config.github_gist_id)
        except Exception as e:
            print(f"Warning: Gist storage failed: {e}")

    print("Using file-based storage (data will be lost on Heroku restarts)")
    print("For persistent storage, set RESULTS_GIT_REPO + RESULTS_GIT_TOKEN (or GITHUB_TOKEN)")
    return FileStorage(config.jobs_history_file)
