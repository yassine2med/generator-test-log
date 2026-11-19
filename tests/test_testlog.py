from datetime import date

import pytest

from gentest.__main__ import main
from gentest.testlog import (Run, GenLogError, format_report, load_runs,
                             summarize)

TODAY = date(2026, 11, 19)
HEADER = "generator,test_date,runtime_min,load_pct,result\n"


def make(tmp_path, body, header=HEADER):
    p = tmp_path / "r.csv"
    p.write_text(header + body)
    return p


def test_run_full_requires_pass_time_and_load():
    assert Run("G", TODAY, 30, 30, True).full
    assert not Run("G", TODAY, 29, 40, True).full
    assert not Run("G", TODAY, 40, 29, True).full
    assert not Run("G", TODAY, 40, 40, False).full


def test_totals_and_average(tmp_path):
    runs = load_runs(make(tmp_path, "G,2026-11-01,30,40,pass\nG,2026-11-10,90,50,pass\n"))
    s = summarize(runs, TODAY)[0]
    assert (s.runs, s.total_hours, s.avg_load, s.failures) == (2, 2.0, 45.0, 0)
    assert s.flags == []


def test_missed_test_flag(tmp_path):
    runs = load_runs(make(tmp_path, "G,2026-10-01,30,40,pass\n"))
    assert summarize(runs, TODAY)[0].flags == ["MISSED TEST (49 days)"]


def test_gap_of_35_days_is_not_missed(tmp_path):
    runs = load_runs(make(tmp_path, "G,2026-10-15,30,40,pass\n"))  # 35 days
    assert summarize(runs, TODAY)[0].flags == []


def test_last_test_failed_flag(tmp_path):
    runs = load_runs(make(tmp_path, "G,2026-11-01,30,40,pass\nG,2026-11-15,10,40,fail\n"))
    assert "LAST TEST FAILED" in summarize(runs, TODAY)[0].flags


def test_no_full_test_flag(tmp_path):
    runs = load_runs(make(tmp_path, "G,2026-11-10,10,40,pass\n"))
    assert "NO FULL TEST" in summarize(runs, TODAY)[0].flags


def test_low_load_flag(tmp_path):
    runs = load_runs(make(tmp_path, "G,2026-11-10,40,20,pass\nG,2026-11-12,40,50,pass\n"))
    assert "LOW LOAD" in summarize(runs, TODAY)[0].flags


def test_unsorted_input_uses_dates(tmp_path):
    runs = load_runs(make(tmp_path, "G,2026-11-15,30,40,pass\nG,2026-11-01,10,10,fail\n"))
    s = summarize(runs, TODAY)[0]
    assert s.last_full == date(2026, 11, 15) and "LAST TEST FAILED" not in s.flags


@pytest.mark.parametrize("row", [
    "G,2026-13-01,30,40,pass", "G,2026-11-01,abc,40,pass", "G,2026-11-01,30,140,pass",
    "G,2026-11-01,-5,40,pass", "G,2026-11-01,30,40,maybe",
])
def test_bad_rows(tmp_path, row):
    with pytest.raises(GenLogError):
        load_runs(make(tmp_path, row + "\n"))


def test_missing_column(tmp_path):
    with pytest.raises(GenLogError, match="missing columns"):
        load_runs(make(tmp_path, "G,2026-11-01\n", header="generator,test_date\n"))


def test_report_and_cli(capsys):
    assert main(["data/runs.csv", "--today", "2026-11-19"]) == 2
    out = capsys.readouterr().out
    assert "GEN-A" in out and "GEN-C" in out and "LAST TEST FAILED" in out


def test_cli_missing_file():
    assert main(["nope.csv"]) == 1
