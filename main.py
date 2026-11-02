#!/usr/bin/env python3
"""CLI entry point for neolab-monitor.

Usage:
    python main.py              # run once, console output
    python main.py --email      # run once + send email
    python main.py --schedule   # run daily on Heroku scheduler
    python main.py --feedback --relevant "<title>"
    python main.py --feedback --irrelevant "<title>"
    python main.py --feedback --list
    python main.py --feedback --stats
    python main.py --feedback --reset
"""

import argparse
import sys
import time
import schedule

from src.config import Config
from src.storage import create_storage
from src.engine import JobEngine
from src.notifier import EmailNotifier


def run_once(email: bool, llm: bool) -> None:
    config = Config.from_env()
    warnings = config.validate()
    for w in warnings:
        print(f"  ⚠️  {w}")

    storage = create_storage(config)
    engine = JobEngine(config, storage)
    engine.run(send_email=email, llm_enabled=llm)


def run_scheduler() -> None:
    config = Config.from_env()
    warnings = config.validate()
    for w in warnings:
        print(f"  ⚠️  {w}")

    storage = create_storage(config)
    engine = JobEngine(config, storage)
    notifier = EmailNotifier(config)

    print("  Starting daily scheduler (runs at 09:00 UTC)")
    print("  Press Ctrl+C to stop")
    print()

    def _scheduled_run():
        print(f"\n  Running scheduled scan at {time.strftime('%Y-%m-%d %H:%M:%S')}")
        engine.run(send_email=True)

    schedule.every().day.at("09:00").do(_scheduled_run)

    # Initial run
    _scheduled_run()

    try:
        while True:
            schedule.run_pending()
            time.sleep(60)
    except KeyboardInterrupt:
        print("\n  Scheduler stopped.")


def run_feedback(args) -> None:
    """Handle --feedback CLI commands."""
    from src.feedback import FeedbackStore

    store = FeedbackStore()

    if args.feedback_list:
        signals = store.get_signals()
        if not signals:
            print("  No feedback signals recorded yet.")
            return
        print(f"\n  {'='*60}")
        print(f"  FEEDBACK SIGNALS ({len(signals)} total)")
        print(f"  {'='*60}")
        for s in signals[:20]:
            marker = "✓" if s["signal"] == "relevant" else "✗"
            print(f"  {marker} [{s['signal']}] {s['title'][:50]}... "
                  f"({s['company'] or 'any company'}) — {s['timestamp'][:10]}")
            if s.get("keywords"):
                print(f"     Keywords: {', '.join(s['keywords'][:5])}")
        return

    if args.feedback_stats:
        stats = store.get_stats()
        print(f"\n  {'='*60}")
        print(f"  FEEDBACK STATISTICS")
        print(f"  {'='*60}")
        print(f"  Total signals:     {stats['total_signals']}")
        print(f"  Relevant:          {stats['relevant']}")
        print(f"  Irrelevant:        {stats['irrelevant']}")
        print(f"  Auto-blacklist:    {stats['auto_blacklist_count']} keywords")
        print(f"  Auto-interests:    {stats['auto_interests_count']} keywords")
        return

    if args.reset_feedback:
        store.reset()
        print("  Feedback data cleared.")
        return

    if not args.feedback_title:
        print("  Error: please provide a job title (use --title)")
        sys.exit(1)

    # Search for the job in history
    config = Config.from_env()
    storage = create_storage(config)
    history = storage.load_previous_jobs()

    # Find matching job (case-insensitive partial match on title)
    matched = None
    for company, jobs in history.items():
        for j in jobs:
            if args.feedback_title.lower() in j.get("title", "").lower():
                matched = (j["title"], company, j.get("description", ""))
                break
        if matched:
            break

    if not matched:
        print(f"  Job not found in history: '{args.feedback_title}'")
        print("  Tip: run 'python main.py' first to fetch current jobs.")
        sys.exit(1)

    title, company, description = matched

    if args.relevant:
        keywords = store.mark_relevant(title, company, description)
        print(f"  ✓ Marked relevant: {title}")
        if keywords:
            print(f"    Suggested keywords: {', '.join(keywords[:5])}")
            print(f"    Add these to interests.json for stronger matching.")
    elif args.irrelevant:
        blacklisted = store.mark_irrelevant(title, company, description)
        print(f"  ✗ Marked irrelevant: {title}")
        if blacklisted:
            print(f"    Auto-blacklisted: {', '.join(blacklisted)}")
    else:
        print("  Error: use --relevant or --irrelevant")
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="AI Research Jobs Scraper")
    parser.add_argument("--email", action="store_true", help="Send email notification after scraping")
    parser.add_argument("--schedule", action="store_true", help="Run daily on a schedule (for Heroku)")
    parser.add_argument("--llm", action="store_true", help="Enable LLM-based classification (requires AGNES_API_KEY)")

    # Feedback subcommands
    feedback_group = parser.add_argument_group("feedback")
    feedback_group.add_argument("--feedback", action="store_true",
                                help="Enable feedback mode (use with --relevant/--irrelevant/--list/--stats/--reset)")
    feedback_group.add_argument("--relevant", action="store_true",
                                help="Mark a job as relevant (requires --feedback and --title)")
    feedback_group.add_argument("--irrelevant", action="store_true",
                                help="Mark a job as irrelevant (requires --feedback and --title)")
    feedback_group.add_argument("--title", dest="feedback_title",
                                help="Job title to mark (partial match against history)")
    feedback_group.add_argument("--list", dest="feedback_list", action="store_true",
                                help="List feedback signals")
    feedback_group.add_argument("--stats", dest="feedback_stats", action="store_true",
                                help="Show feedback statistics")
    feedback_group.add_argument("--reset", dest="reset_feedback", action="store_true",
                                help="Clear all feedback data")

    args = parser.parse_args()

    if args.reset_feedback:
        run_feedback(args)
        return

    if args.feedback:
        run_feedback(args)
        return

    if args.schedule:
        run_scheduler()
    else:
        run_once(email=args.email, llm=args.llm)


if __name__ == "__main__":
    main()
