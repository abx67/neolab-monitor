#!/usr/bin/env python3
"""CLI entry point for neolab-monitor.

Usage:
    python main.py              # run once, console output
    python main.py --email      # run once + send email
    python main.py --schedule   # run daily on Heroku scheduler
"""

import argparse
import sys
import time
import schedule

from src.config import Config
from src.storage import create_storage
from src.engine import JobEngine
from src.notifier import EmailNotifier


def run_once(email: bool) -> None:
    config = Config.from_env()
    warnings = config.validate()
    for w in warnings:
        print(f"  ⚠️  {w}")

    storage = create_storage(config)
    engine = JobEngine(config, storage)
    engine.run(send_email=email)


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


def main() -> None:
    parser = argparse.ArgumentParser(description="AI Research Jobs Scraper")
    parser.add_argument("--email", action="store_true", help="Send email notification after scraping")
    parser.add_argument("--schedule", action="store_true", help="Run daily on a schedule (for Heroku)")
    args = parser.parse_args()

    if args.schedule:
        run_scheduler()
    else:
        run_once(email=args.email)


if __name__ == "__main__":
    main()
