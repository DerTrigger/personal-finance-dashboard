"""Database build. All data here is fake."""
import csv

import pytest

from app.lib import db
from tests.conftest import mm_row

SNAP_COLS = ["as_of", "platform", "account_type", "item_type", "name", "ticker", "asset_type", "market",
             "units", "principal", "value", "gain", "gain_pct", "annual_rate", "term_days", "start_date",
             "end_date", "payout", "interest_total", "interest_basis", "confirmed_on", "notes"]

SETTINGS = {"accounts": {"Card A": {"type": "credit_card", "in_net_worth": False},
                         "GBM": {"type": "variable", "in_net_worth": True}}}


def snap(as_of, platform, item_type, name, value, **kw):
    r = {c: "" for c in SNAP_COLS}
    r.update(as_of=as_of, platform=platform, item_type=item_type, name=name, value=value, **kw)
    return r


def write_csv(path, cols, rows):
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    return path


@pytest.fixture
def sources(tmp_path, make_export):
    export = make_export("mm2026.xlsx", [
        mm_row("2026-08-05 12:00", "Card A", "Food", 1000, "Exp."),
        mm_row("2026-08-15 09:00", "Payroll Account", "Salary", 10000, "Income"),
        mm_row("2026-08-20 18:00", "Nubank", "GBM", 3000, "Transfer-Out"),
        mm_row("2026-08-20 18:00", "GBM", "Nubank", 3000, "Transfer-In"),
        mm_row("2026-09-05 12:00", "Card A", "Food", 2500, "Exp."),
        mm_row("2026-09-15 09:00", "Payroll Account", "Salary", 10000, "Income"),
    ])
    snaps = write_csv(tmp_path / "snaps.csv", SNAP_COLS, [
        snap("2026-08-31", "GBM", "total", "GBM", 5000),
        snap("2026-08-31", "GBM", "holding", "VOO", 5000, ticker="VOO", gain=500),
        snap("2026-08-31", "Manual", "manual_asset", "Car", 100000),
        snap("2026-09-28", "GBM", "total", "GBM", 8200),
        snap("2026-09-28", "GBM", "holding", "VOO", 8200, ticker="VOO", gain=700),
        snap("2026-09-28", "Manual", "manual_asset", "Car", 98000),
    ])
    return {"exports": [export], "snapshots": snaps, "adjustments": tmp_path / "adjustments.csv"}


def build(tmp_path, sources):
    return db.build_database(tmp_path / "finance.db", sources["exports"], sources["snapshots"],
                             sources["adjustments"], SETTINGS)


def test_tables_loaded(tmp_path, sources):
    report = build(tmp_path, sources)
    assert report["transactions"] == 6
    assert report["snapshot_items"] == 6
    assert report["adjustments"] == 0  # missing file is fine: no adjustments yet


def test_net_worth_counts_totals_only(tmp_path, sources):
    build(tmp_path, sources)
    nw = dict(db.query(tmp_path / "finance.db", "SELECT as_of, net_worth FROM v_net_worth ORDER BY as_of"))
    # Holdings are detail inside the GBM total, so they must not be added again.
    assert nw == {"2026-08-31": 105000.0, "2026-09-28": 106200.0}


def test_monthly_cashflow_excludes_transfers(tmp_path, sources):
    build(tmp_path, sources)
    rows = db.query(tmp_path / "finance.db", "SELECT month, income, expenses, net_income, savings_rate "
                                            "FROM v_monthly_cashflow ORDER BY month")
    assert rows == [("2026-08", 10000.0, 1000.0, 9000.0, 0.9),
                    ("2026-09", 10000.0, 2500.0, 7500.0, 0.75)]


def test_rebuild_is_identical(tmp_path, sources):
    build(tmp_path, sources)
    first = db.fingerprint(tmp_path / "finance.db")
    build(tmp_path, sources)
    assert db.fingerprint(tmp_path / "finance.db") == first


def test_adjustments_loaded(tmp_path, sources):
    write_csv(sources["adjustments"], db.ADJ_COLS,
              [{"date": "2026-09-28", "account": "FINSUS", "amount": 5408.50,
                "reason": "Logged as 60,000 in Money Manager", "approved_on": "2026-09-28"}])
    assert build(tmp_path, sources)["adjustments"] == 1


def test_accounts_table_from_settings(tmp_path, sources):
    build(tmp_path, sources)
    acc = dict(db.query(tmp_path / "finance.db", "SELECT name, in_net_worth FROM accounts"))
    assert acc["Card A"] == 0 and acc["GBM"] == 1


def test_failed_build_keeps_old_database(tmp_path, sources):
    build(tmp_path, sources)
    before = db.fingerprint(tmp_path / "finance.db")
    sources["snapshots"].write_text("not,a,snapshot\n1,2,3\n", encoding="utf-8")
    with pytest.raises(ValueError):
        build(tmp_path, sources)
    assert db.fingerprint(tmp_path / "finance.db") == before
