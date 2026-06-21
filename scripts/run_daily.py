"""Daily scheduler: produce N videos per day.

Run it once and leave it running (it sleeps until the scheduled time):
    python scripts/run_daily.py            # uses config time, default 09:00
    python scripts/run_daily.py --now      # produce a batch immediately, then exit
    python scripts/run_daily.py --at 18:30 # run every day at 18:30

For a hands-off setup, prefer a macOS launchd/cron job calling:
    python -m src.orchestrator --batch
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import schedule  # noqa: E402

from src.orchestrator import Pipeline  # noqa: E402
from src.utils import get_logger  # noqa: E402

log = get_logger("scheduler")


def job() -> None:
    log.info("Scheduled run starting.")
    Pipeline().run_batch()
    log.info("Scheduled run finished.")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--now", action="store_true", help="Run a batch immediately and exit.")
    ap.add_argument("--at", default="09:00", help="Daily run time HH:MM (24h).")
    args = ap.parse_args()

    if args.now:
        job()
        return

    schedule.every().day.at(args.at).do(job)
    log.info("Scheduler armed. Producing a daily batch at %s. Ctrl-C to stop.", args.at)
    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == "__main__":
    main()
