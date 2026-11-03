"""Render a human-readable markdown report for each scrape run."""

from datetime import datetime, timezone
from typing import Dict, List

from src.scraper.models import DiffResult, Job


def _md_cell(text: str) -> str:
    """Normalize text and escape pipes so markdown table columns stay aligned."""
    normalized = " ".join(text.replace("\n", " ").split())
    return normalized.replace("|", "\\|")


def _job_bullet(job: Job) -> List[str]:
    """Render one job as a markdown bullet (plus indented apply link when present)."""
    lines = [f"- **{job.title}** — 📍 {_md_cell(job.location)}"]
    if job.apply_link:
        lines.append(f"  [Apply]({job.apply_link})")
    return lines


def render_run_report(
    all_jobs: Dict[str, List[Job]],
    diff_result: Dict[str, DiffResult],
) -> str:
    """Render a deterministic, GitHub-renderable markdown report for this run."""
    now = datetime.now(timezone.utc)
    total_jobs = sum(len(jobs) for jobs in all_jobs.values())
    new_jobs = [job for diff in diff_result.values() for job in diff.new_jobs]
    removed_jobs = [job for diff in diff_result.values() for job in diff.removed_jobs]

    lines: List[str] = [
        f"# AI Research Jobs Report — {now.strftime('%Y-%m-%d %H:%M')} UTC",
        "",
        f"**Total positions:** {total_jobs} | **New:** {len(new_jobs)} | **Removed:** {len(removed_jobs)}",
        "",
        "## 🆕 New positions",
        "",
    ]

    if new_jobs:
        for company, diff in diff_result.items():
            if not diff.new_jobs:
                continue
            lines.append(f"### {company}")
            lines.append("")
            for job in diff.new_jobs:
                lines.extend(_job_bullet(job))
            lines.append("")
    else:
        lines.append("_No new positions since last check._")
        lines.append("")

    lines += ["## ❌ Removed positions", ""]
    if removed_jobs:
        for company, diff in diff_result.items():
            if not diff.removed_jobs:
                continue
            lines.append(f"### {company}")
            lines.append("")
            for job in diff.removed_jobs:
                lines.extend(_job_bullet(job))
            lines.append("")
    else:
        lines.append("_No positions removed._")
        lines.append("")

    lines += ["## All positions", ""]
    for company, jobs in all_jobs.items():
        lines.append(f"### {company} ({len(jobs)})")
        lines.append("")
        if not jobs:
            lines.append("_No positions currently listed._")
            lines.append("")
            continue
        lines.append("| # | Title | Location | Apply |")
        lines.append("| --- | --- | --- | --- |")
        for i, job in enumerate(jobs, 1):
            apply_cell = f"[link]({_md_cell(job.apply_link)})" if job.apply_link else ""
            lines.append(f"| {i} | {_md_cell(job.title)} | {_md_cell(job.location)} | {apply_cell} |")
        lines.append("")

    lines.append("---")
    lines.append(
        "*Machine-readable snapshot: "
        "[ai_jobs_history.json](https://github.com/xj3048/frontierlab-jobs/blob/main/ai_jobs_history.json)*"
    )

    return "\n".join(lines)
