"""The 3-month replay on fake data (baseline 30 Sep 2026, so Oct-Dec 2026): the monthly pipeline gets the right net
worth each month and flags every planted error. All data is fake (tests/snapdata.py, tests/test_metrics.py)."""
import copy
import hashlib

import pandas as pd
import pytest

from app.lib import replay
from tests.snapdata import SETTINGS, september
from tests.test_metrics import MM_ROWS


@pytest.fixture
def inputs(tmp_path, make_export):
    baseline = tmp_path / "investment-snapshots.csv"
    september().to_csv(baseline, index=False, encoding="utf-8-sig")
    export = make_export("Money Manager Report 2026.xlsx", MM_ROWS)
    return baseline, [export]


def run(tmp_path, inputs, settings=SETTINGS):
    baseline, exports = inputs
    return replay.run(tmp_path / "replay", baseline, exports, settings)


def test_every_check_passes(tmp_path, inputs):
    r = run(tmp_path, inputs)
    failed = [c for c in r.checks if not c["passed"]]
    assert not failed, failed
    assert list(r.truth["as_of"]) == r.months == ["2026-10-31", "2026-11-30", "2026-12-31"]


def test_months_after():
    assert replay.months_after("2026-09-28") == ["2026-10-31", "2026-11-30", "2026-12-31"]
    assert replay.months_after("2026-11-30") == ["2026-12-31", "2027-01-31", "2027-02-28"]
    assert replay.months_after("2028-01-31", 2) == ["2028-02-29", "2028-03-31"]  # leap year


def test_replay_follows_the_latest_saved_month(tmp_path, make_export):
    """Run months after the real ones exist: the replay starts after the latest snapshot, not in Oct 2026."""
    shift = pd.DateOffset(months=4)
    base = september("2027-01-31")
    for col in ("start_date", "end_date"):  # keep the deposits' timing relative to the snapshot
        base[col] = [None if pd.isna(v) else (pd.Timestamp(v) + shift).strftime("%Y-%m-%d") for v in base[col]]
    baseline = tmp_path / "later.csv"
    base.to_csv(baseline, index=False, encoding="utf-8-sig")
    r = replay.run(tmp_path / "replay", baseline, [make_export("Money Manager Report 2026.xlsx", MM_ROWS)], SETTINGS)
    assert r.months == ["2027-02-28", "2027-03-31", "2027-04-30"]
    failed = [c for c in r.checks if not c["passed"]]
    assert not failed, failed


def test_net_worth_matches_the_truth_every_month(tmp_path, inputs):
    r = run(tmp_path, inputs)
    for month in r.months:
        assert r.check(month, "net worth")["passed"]
    assert r.truth["net_worth"].notna().all()


def test_missing_screenshot_is_refused_then_the_fixed_month_saves(tmp_path, inputs):
    r = run(tmp_path, inputs)
    c = r.check("2026-10-31", "missing screenshot refused")
    assert c["passed"] and "Bitso" in c["detail"]
    assert r.check("2026-10-31", "saved")["passed"]


def test_matured_deposit_still_listed_is_warned(tmp_path, inputs):
    c = run(tmp_path, inputs).check("2026-10-31", "matured deposit still listed warned")
    assert c["passed"] and "Kubo Financiero" in c["detail"]


def test_duplicate_row_is_flagged(tmp_path, inputs):
    assert run(tmp_path, inputs).check("2026-10-31", "duplicate flagged")["passed"]


def test_logging_mistake_is_flagged(tmp_path, inputs):
    r = run(tmp_path, inputs)
    c = r.check("2026-11-30", "reconcile flags")
    assert c["passed"] and "GBM" in c["detail"]
    assert r.check("2026-11-30", "logging mistake flagged")["passed"]  # and the gap is exactly 10,000 - 1,000


def test_stock_sale_is_flagged_not_silent(tmp_path, inputs):
    r = run(tmp_path, inputs)
    assert r.check("2026-12-31", "reconcile flags")["passed"]
    assert r.check("2026-12-31", "stock sale flagged")["passed"]


def test_monthly_exports_keep_the_earlier_months(tmp_path, inputs):
    r = run(tmp_path, inputs)
    assert all(r.check(m, "earlier months kept")["passed"] for m in r.months)


def test_resent_month_with_a_removed_tag_is_not_double_counted(tmp_path, inputs):
    r = run(tmp_path, inputs)
    assert r.check("2026-12-31", "re-sent month not double counted")["passed"]
    c = r.check("2026-12-31", "vanished rows warned")
    assert c["passed"] and replay.DELETED_NOTE in c["detail"]


def test_card_pending_counts_only_the_latest_month(tmp_path, inputs):
    r = run(tmp_path, inputs)
    assert all(r.check(m, "card pending from the latest export only")["passed"] for m in r.months)


def test_new_category_account_and_refund_load(tmp_path, inputs):
    assert run(tmp_path, inputs).check("2026-12-31", "new category, account and refund loaded")["passed"]


def test_source_files_are_not_touched(tmp_path, inputs):
    baseline, exports = inputs
    before = [hashlib.sha256(p.read_bytes()).hexdigest() for p in [baseline, *exports]]
    run(tmp_path, inputs)
    assert [hashlib.sha256(p.read_bytes()).hexdigest() for p in [baseline, *exports]] == before


def test_replay_can_fail(tmp_path, inputs):
    """With the reconcile threshold set sky-high, the planted logging mistake goes unflagged: the check must fail."""
    blind = copy.deepcopy(SETTINGS)
    blind["checks"]["reconcile_gap_mxn"] = 10_000_000
    r = run(tmp_path, inputs, blind)
    assert not r.check("2026-11-30", "reconcile flags")["passed"]
