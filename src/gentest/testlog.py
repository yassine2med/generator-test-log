"""Summarize emergency generator test runs and flag weak or missing tests."""
from __future__ import annotations

import csv
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

REQUIRED = ("generator", "test_date", "runtime_min", "load_pct", "result")
MIN_RUNTIME_MIN = 30     # a test shorter than this does not count as a full test
MIN_LOAD_PCT = 30        # a test below this load does not count as a full test
MAX_GAP_DAYS = 35        # more days than this since the last full test is a missed test


class GenLogError(ValueError):
    """Raised when the input file or a row is not valid."""


@dataclass(frozen=True)
class Run:
    """One recorded test run."""

    generator: str
    day: date
    runtime_min: int
    load_pct: float
    passed: bool

    @property
    def full(self) -> bool:
        """True when the run passed and met the minimum runtime and load."""
        return self.passed and self.runtime_min >= MIN_RUNTIME_MIN and self.load_pct >= MIN_LOAD_PCT


@dataclass
class Summary:
    """Totals and flags for one generator."""

    generator: str
    runs: int = 0
    total_hours: float = 0.0
    avg_load: float = 0.0
    failures: int = 0
    last_full: date | None = None
    flags: list[str] = field(default_factory=list)


def load_runs(path: str | Path) -> list[Run]:
    """Read the CSV into runs, validating every row."""
    with open(path, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        missing = [c for c in REQUIRED if c not in (reader.fieldnames or [])]
        if missing:
            raise GenLogError("missing columns: " + ", ".join(missing))
        runs = []
        for line, row in enumerate(reader, start=2):
            try:
                day = date.fromisoformat(row["test_date"].strip())
                minutes = int(row["runtime_min"])
                load = float(row["load_pct"])
            except ValueError as exc:
                raise GenLogError(f"line {line}: bad value ({exc})") from exc
            if minutes < 0 or not 0 <= load <= 100:
                raise GenLogError(f"line {line}: runtime must be 0 or more and load 0 to 100")
            result = row["result"].strip().lower()
            if result not in {"pass", "fail"}:
                raise GenLogError(f"line {line}: result must be pass or fail")
            runs.append(Run(row["generator"].strip(), day, minutes, load, result == "pass"))
    return runs


def summarize(runs: list[Run], today: date) -> list[Summary]:
    """Build one summary per generator, with flags as of today."""
    by_gen: dict[str, list[Run]] = {}
    for run in runs:
        by_gen.setdefault(run.generator, []).append(run)
    out = []
    for name in sorted(by_gen):
        group = sorted(by_gen[name], key=lambda r: r.day)
        s = Summary(name, runs=len(group))
        s.total_hours = round(sum(r.runtime_min for r in group) / 60, 1)
        s.avg_load = round(sum(r.load_pct for r in group) / len(group), 1)
        s.failures = sum(1 for r in group if not r.passed)
        fulls = [r.day for r in group if r.full]
        s.last_full = fulls[-1] if fulls else None
        if group[-1].passed is False:
            s.flags.append("LAST TEST FAILED")
        if s.last_full is None:
            s.flags.append("NO FULL TEST")
        elif (today - s.last_full).days > MAX_GAP_DAYS:
            s.flags.append(f"MISSED TEST ({(today - s.last_full).days} days)")
        if any(r.passed and r.load_pct < MIN_LOAD_PCT for r in group[-3:]):
            s.flags.append("LOW LOAD")
        out.append(s)
    return out


def format_report(summaries: list[Summary]) -> str:
    """Plain text table."""
    lines = [f"{'Generator':<10}{'Runs':>5}{'Hours':>7}{'AvgLoad':>9}{'Fails':>6}  {'LastFull':<11}Flags"]
    for s in summaries:
        last = s.last_full.isoformat() if s.last_full else "-"
        lines.append(f"{s.generator:<10}{s.runs:>5}{s.total_hours:>7}{s.avg_load:>8}%{s.failures:>6}  "
                     f"{last:<11}{'; '.join(s.flags) or 'ok'}")
    return "\n".join(lines)
