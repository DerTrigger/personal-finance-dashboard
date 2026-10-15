"""Eval checks: each passes on good data and fails when a fault is planted, so none can pass by accident.
All data is fake (tests/snapdata.py, tests/test_metrics.py)."""
import re
import sqlite3
from contextlib import closing

import pandas as pd
import pytest

from app.lib import db, evals
from app.lib import metrics as mx
from tests.snapdata import SETTINGS, october, september
from tests.test_metrics import MM_ROWS


@pytest.fixture
def src(tmp_path, make_export):
    snaps_csv = tmp_path / "investment-snapshots.csv"
    pd.concat([september(), october()]).to_csv(snaps_csv, index=False, encoding="utf-8-sig")
    export = make_export("Money Manager Report 2026.xlsx", MM_ROWS)
    db_path = tmp_path / "finance.db"
    db.build_database(db_path, [export], snaps_csv, tmp_path / "adjustments.csv", SETTINGS)
    return {"snaps": snaps_csv, "exports": [export], "db": db_path, "adj": tmp_path / "adjustments.csv"}


def tamper(db_path, sql):
    with closing(sqlite3.connect(db_path)) as c:
        c.execute(sql)
        c.commit()


def test_mm_import(src):
    assert evals.mm_import(src["exports"], src["db"])["passed"]


def test_mm_import_catches_a_changed_amount(src):
    tamper(src["db"], "UPDATE transactions SET amount = amount + 1 WHERE rowid = 1")
    c = evals.mm_import(src["exports"], src["db"])
    assert not c["passed"]


def test_mm_import_catches_a_lost_row(src):
    tamper(src["db"], "DELETE FROM transactions WHERE rowid = 1")
    assert not evals.mm_import(src["exports"], src["db"])["passed"]


def test_mm_import_agrees_with_overlapping_monthly_exports(src, tmp_path, make_export):
    """Annual file + October + October re-sent with an edited note: the eval's own rule and the import agree."""
    from datetime import datetime
    from tests.conftest import mm_row
    nov1 = datetime(2026, 11, 1, 9).timestamp()
    annual = make_export("Money Manager Report 2026-01-01 ~ 09-30.xlsx", MM_ROWS[:5], mtime=datetime(2026, 10, 1).timestamp())
    oct_rows = [mm_row("2026-10-05 12:00", "Card A", "Food", 1500, "Exp.", note="IN NU"),
                mm_row("2026-10-15 09:00", "Payroll Account", "Salary", 10000, "Income")]
    first = make_export("Money Manager Report 2026-10-01 ~ 10-31.xlsx", oct_rows, mtime=nov1)
    again = make_export("Money Manager Report 2026-10-01 ~ 10-31 (1).xlsx",
                        [mm_row("2026-10-05 12:00", "Card A", "Food", 1500, "Exp.")] + oct_rows[1:], mtime=nov1 + 60)
    exports = [annual, first, again]
    db_path = tmp_path / "overlap.db"
    db.build_database(db_path, exports, src["snaps"], src["adj"], SETTINGS)
    c = evals.mm_import(exports, db_path)
    assert c["passed"], c["private"]
    assert "(2 replaced" in c["public"]


def test_mm_import_fails_on_a_missing_month(src, tmp_path, make_export):
    """September never exported: the rows that exist all match, but the hole must fail the check."""
    from datetime import datetime
    from tests.conftest import mm_row
    aug = make_export("Money Manager Report 2026-08-01 ~ 08-31.xlsx",
                      [mm_row("2026-08-10 12:00", "Cash", "Food", 100, "Exp.")], mtime=datetime(2026, 9, 1).timestamp())
    oct_ = make_export("Money Manager Report 2026-10-01 ~ 10-31.xlsx",
                       [mm_row("2026-10-10 12:00", "Cash", "Food", 100, "Exp.")], mtime=datetime(2026, 11, 1).timestamp())
    db_path = tmp_path / "hole.db"
    db.build_database(db_path, [aug, oct_], src["snaps"], src["adj"], SETTINGS)
    c = evals.mm_import([aug, oct_], db_path)
    assert not c["passed"] and "1 import warnings" in c["public"]


def test_rebuild_is_stable(src, tmp_path):
    c = evals.rebuild(src["exports"], src["snaps"], src["adj"], SETTINGS, tmp_path / "rebuild")
    assert c["passed"]


def test_opening_net_worth(src):
    assert evals.opening_net_worth(src["db"], "2026-09-30", 803_000.00)["passed"]
    assert not evals.opening_net_worth(src["db"], "2026-09-30", 803_000.01)["passed"]


def test_latest_net_worth_on_the_dashboard(src):
    assert evals.dashboard_net_worth(src["db"])["passed"]  # Resumen card vs. the database


def test_deposit_math(src):
    assert evals.deposit_math(src["snaps"], SETTINGS)["passed"]


def test_deposit_math_catches_a_wrong_figure(src, tmp_path):
    bad = tmp_path / "bad.csv"
    s = pd.read_csv(src["snaps"], encoding="utf-8-sig")
    s.loc[(s["name"] == "Casita") & (s["as_of"] == "2026-10-31"), "interest_total"] += 2
    s.to_csv(bad, index=False, encoding="utf-8-sig")
    assert not evals.deposit_math(bad, SETTINGS)["passed"]


def test_filters(src):
    c = evals.filters(src["db"])
    assert c["passed"], c["private"]
    runs = int(re.search(r"and (\d+) on the Gastos/Ingresos screens", c["public"]).group(1))
    assert runs >= 10, c["public"]  # the screens were really opened, not skipped


def test_filters_catch_a_filter_that_drops_rows(src, monkeypatch):
    real = mx.filter_tx
    monkeypatch.setattr(mx, "filter_tx", lambda tx, **kw: real(tx, **kw).iloc[1:])
    assert not evals.filters(src["db"], pages=False)["passed"]


def test_replay(src, tmp_path):
    september().to_csv(tmp_path / "base.csv", index=False, encoding="utf-8-sig")
    c = evals.replay_check(tmp_path / "replay", tmp_path / "base.csv", src["exports"], SETTINGS)
    assert c["passed"], c["private"]


def test_report_without_amounts_has_no_amounts(src, tmp_path):
    checks = [evals.mm_import(src["exports"], src["db"]), evals.opening_net_worth(src["db"], "2026-09-30", 803_000.0),
              evals.deposit_math(src["snaps"], SETTINGS), evals.filters(src["db"], pages=False)]
    public = evals.report(checks, with_amounts=False)
    no_dates = re.sub(r"\d{4}-\d{2}(-\d{2})?", "", public)
    assert "$" not in no_dates
    assert not re.search(r"\d[\d,]{3,}", no_dates), no_dates  # no number with 4+ digits
    assert "803,000" in evals.report(checks, with_amounts=True)
