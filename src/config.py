"""Configuration management - centralized environment variable handling."""

from __future__ import annotations
import os
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass(frozen=True)
class Config:
    """Immutable configuration loaded from environment variables."""

    # Storage
    github_token: Optional[str] = None
    github_gist_id: Optional[str] = None
    git_repo: Optional[str] = None
    git_token: Optional[str] = None
    git_branch: str = "main"

    # Email
    smtp_server: str = "smtp.gmail.com"
    smtp_port: int = 587
    sender_email: Optional[str] = None
    sender_password: Optional[str] = None
    recipient_email: Optional[str] = None

    # Scraper
    debug_mode: bool = False
    no_filter_companies: List[str] = field(default_factory=lambda: ["Thinking Machines"])
    blacklist_keywords: List[str] = field(default_factory=list)

    # Paths
    jobs_history_file: str = "ai_jobs_history.json"

    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment variables."""
        # Try to load from .env file
        try:
            from dotenv import load_dotenv
            load_dotenv()
        except ImportError:
            pass

        # GitHub token: env var or file fallback
        github_token = os.getenv("GITHUB_TOKEN")
        if not github_token:
            token_file = os.path.expanduser("~/.github_token")
            if os.path.exists(token_file):
                with open(token_file) as f:
                    github_token = f.read().strip()

        # Git repo storage: token falls back to GITHUB_TOKEN
        git_token = os.getenv("RESULTS_GIT_TOKEN") or os.getenv("GITHUB_TOKEN")

        debug_mode = os.getenv("SCRAPER_DEBUG", "").lower() in ("1", "true", "yes", "on")

        return cls(
            github_token=github_token,
            github_gist_id=os.getenv("GITHUB_GIST_ID"),
            git_repo=os.getenv("RESULTS_GIT_REPO"),
            git_token=git_token,
            git_branch=os.getenv("RESULTS_GIT_BRANCH", "main"),
            smtp_server=os.getenv("SMTP_SERVER", "smtp.gmail.com"),
            smtp_port=int(os.getenv("SMTP_PORT", "587")),
            sender_email=os.getenv("SENDER_EMAIL"),
            sender_password=os.getenv("SENDER_PASSWORD"),
            recipient_email=os.getenv("RECIPIENT_EMAIL"),
            debug_mode=debug_mode,
            blacklist_keywords=[
                kw.strip()
                for kw in os.getenv("BLACKLIST_KEYWORDS", "").split(",")
                if kw.strip()
            ],
        )

    @property
    def email_configured(self) -> bool:
        return all([self.sender_email, self.sender_password, self.recipient_email])

    @property
    def storage_available(self) -> bool:
        # git_token falls back to GITHUB_TOKEN, so this covers gist + git repo storage
        return self.git_token is not None

    def validate(self) -> List[str]:
        """Return list of validation warnings. Empty list means all good."""
        warnings = []
        if not self.email_configured:
            warnings.append(
                "Email configuration incomplete. "
                "Required: SENDER_EMAIL, SENDER_PASSWORD, RECIPIENT_EMAIL"
            )
        return warnings
