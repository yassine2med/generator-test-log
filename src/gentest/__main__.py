"""Command line: python -m gentest runs.csv [--today YYYY-MM-DD]."""
from __future__ import annotations

import argparse
import sys
from datetime import date

from .testlog import GenLogError, format_report, load_runs, summarize


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="gentest", description=__doc__)
    parser.add_argument("csv_file")
    parser.add_argument("--today", help="YYYY-MM-DD, default is today")
    args = parser.parse_args(argv)
    try:
        today = date.fromisoformat(args.today) if args.today else date.today()
        summaries = summarize(load_runs(args.csv_file), today)
    except (GenLogError, OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(format_report(summaries))
    flagged = sum(1 for s in summaries if s.flags)
    print(f"\n{len(summaries)} generators, {flagged} with flags")
    return 2 if flagged else 0


if __name__ == "__main__":
    sys.exit(main())
