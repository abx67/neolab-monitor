"""Abstract base class for storage backends."""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional


class StorageABC(ABC):
    """Interface for job history storage backends."""

    @abstractmethod
    def load_previous_jobs(self) -> Dict[str, List[Dict[str, str]]]:
        """Load previous job snapshot from storage.

        Returns:
            Dictionary mapping company names to lists of job dicts.
        """
        ...

    @abstractmethod
    def save_jobs_history(
        self,
        jobs: Dict[str, List[Dict[str, str]]],
        report_md: Optional[str] = None,
    ) -> None:
        """Save current job snapshot to storage.

        Args:
            jobs: Dictionary mapping company names to lists of job dicts.
            report_md: Optional rendered markdown report for this run.
                Backends may ignore report_md (e.g. file/gist backends).
        """
        ...

    def get_report_url(self) -> Optional[str]:
        """URL of the latest rendered report (backends without one return None)."""
        return None
