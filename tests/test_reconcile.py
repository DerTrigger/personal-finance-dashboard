"""Reconciliation: change = returns + contributions, checked against Money Manager transfers. All data is fake."""
import pandas as pd
import pytest

from app.lib import reconcile as rc
from tests.snapdata import SETTINGS, october, september

HISTORY = pd.concat([september(), october()], ignore_index=True)


def tx(date, account, kind, amount):
    return {"date": date, "account": account, "type": kind, "amount": amount}


LOGGED = pd.DataFrame([
    tx("2026-09-30", "GBM", "transfer_in", 999.0),       # on the start date: belongs to last month
    tx("2026-10-10", "GBM", "transfer_in", 3000.0),
    tx("2026-10-12", "Nubank", "transfer_out", 3000.0),  # other half of the GBM transfer; not a platform
    tx("2026-10-31", "Allianz PPR", "transfer_in", 5000.0),  # on the end date: counts
    tx("2026-10-20", "GBM", "expense", 50.0),            # not a transfer; ignored
])


def run(transactions=LOGGED, history=HISTORY):
    out = rc.reconcile(history, "2026-09-30", "2026-10-31", transactions, SETTINGS)
    return out.set_index("platform")


def test_every_platform_splits_its_change():
    r = run()
    assert (r["change"] - r["returns"] - r["contributions"]).abs().max() == pytest.approx(0, abs=0.005)
    assert r["change"].sum() == pytest.approx(785_227.20 - 803_000.0)


def test_gain_change_platforms():
    r = run()
    assert r.loc["Nu", "returns"] == pytest.approx(300.0)
    assert r.loc["Nu", "contributions"] == pytest.approx(0.0)
    assert r.loc["GBM", "returns"] == pytest.approx(500.0)
    assert r.loc["GBM", "contributions"] == pytest.approx(3000.0)


def test_finsus_interest_payout_and_on_demand():
    # Casita pays 273.00 net on 2026-10-15; finsus + earns 310.00 gross - 55.80 ISR = 254.20 over 31 days.
    r = run()
    assert r.loc["FINSUS", "returns"] == pytest.approx(527.20)
    assert r.loc["FINSUS", "contributions"] == pytest.approx(0.0)


def test_kubo_matured_deposit():
    # Matured 2026-10-17: earned 910.00 net, principal + interest (20,910) paid out of Kubo.
    r = run()
    assert r.loc["Kubo Financiero", "returns"] == pytest.approx(910.0)
    assert r.loc["Kubo Financiero", "contributions"] == pytest.approx(-20910.0)


def test_allianz_uses_the_statement():
    r = run()
    assert r.loc["Allianz PPR", "contributions"] == pytest.approx(5000.0)
    assert r.loc["Allianz PPR", "returns"] == pytest.approx(1000.0)
    assert not r.loc["Allianz PPR", "estimated"]


def test_estimated_and_revaluation():
    r = run()
    assert r.loc["Bitso", "returns"] == pytest.approx(400.0)
    assert r.loc["Bitso", "estimated"]
    assert r.loc["Profuturo", "returns"] == pytest.approx(1500.0)
    assert r.loc["Profuturo", "estimated"]
    assert r.loc["Manual", "method"] == "revaluation"
    assert r.loc["Manual", "returns"] == pytest.approx(-10000.0)


def test_logged_transfers_match_so_nothing_is_flagged():
    r = run()
    assert r.loc["GBM", "logged_transfers"] == pytest.approx(3000.0)
    assert r.loc["GBM", "gap"] == pytest.approx(0.0)
    assert r.loc["Allianz PPR", "logged_transfers"] == pytest.approx(5000.0)
    assert r.loc["FINSUS", "gap"] == pytest.approx(0.0)
    assert not r["flagged"].any()


def test_missing_transfer_is_flagged():
    r = run(LOGGED[LOGGED["amount"] != 3000.0])
    assert r.loc["GBM", "gap"] == pytest.approx(3000.0)
    assert r.loc["GBM", "flagged"]
    assert r["flagged"].sum() == 1


def test_small_gap_is_not_flagged():
    logged = LOGGED.copy()
    logged.loc[logged["amount"] == 3000.0, "amount"] = 2800.0
    r = run(logged)
    assert r.loc["GBM", "gap"] == pytest.approx(200.0)
    assert not r.loc["GBM", "flagged"]


def test_unmapped_platforms_have_no_gap():
    r = run()
    assert pd.isna(r.loc["Nu", "gap"])
    assert pd.isna(r.loc["Kubo Financiero", "logged_transfers"])


def test_platform_new_this_month_starts_from_zero():
    extra = october().iloc[[0]].assign(platform="Cetes", name="Cetes", value=1000.0)
    r = run(history=pd.concat([HISTORY, extra], ignore_index=True))
    assert r.loc["Cetes", "change"] == pytest.approx(1000.0)
    assert r.loc["Cetes", "estimated"]


# --- Booking an approved gap -------------------------------------------------

def test_book_adjustment_creates_the_file_and_refuses_a_duplicate(tmp_path):
    path = tmp_path / "adjustments.csv"
    r = rc.reconcile(HISTORY, "2026-09-30", "2026-10-31", LOGGED[LOGGED["amount"] != 3000.0], SETTINGS)
    gbm = r[r["platform"] == "GBM"].iloc[0]
    rc.book_adjustment(path, gbm, SETTINGS, approved_on="2026-11-01")
    with pytest.raises(ValueError, match="ya está registrado"):
        rc.book_adjustment(path, gbm, SETTINGS, approved_on="2026-11-02")
    saved = pd.read_csv(path, encoding="utf-8-sig")
    assert list(saved.columns) == ["date", "account", "amount", "reason", "approved_on"]
    assert len(saved) == 1
    assert saved.loc[0, "date"] == "2026-10-31"
    assert saved.loc[0, "account"] == "GBM"
    assert saved.loc[0, "amount"] == pytest.approx(3000.0)


def test_a_booked_gap_is_settled(tmp_path):
    """Once Memo books the gap, it no longer reads as something to check (on reconcile.py and Revisión)."""
    path = tmp_path / "adjustments.csv"
    short = LOGGED[LOGGED["amount"] != 3000.0]
    r = rc.reconcile(HISTORY, "2026-09-30", "2026-10-31", short, SETTINGS)
    rc.book_adjustment(path, r[r["platform"] == "GBM"].iloc[0], SETTINGS, approved_on="2026-11-01")
    booked = pd.read_csv(path, encoding="utf-8-sig", dtype={"date": str})
    r = rc.reconcile(HISTORY, "2026-09-30", "2026-10-31", short, SETTINGS, adjustments=booked).set_index("platform")
    assert r.loc["GBM", "booked"] == pytest.approx(3000.0)
    assert r.loc["GBM", "gap"] == pytest.approx(0.0)
    assert not r.loc["GBM", "flagged"]
    # An adjustment from another month doesn't count here
    other = booked.assign(date="2026-12-31")
    assert rc.reconcile(HISTORY, "2026-09-30", "2026-10-31", short, SETTINGS, adjustments=other) \
        .set_index("platform").loc["GBM", "flagged"]


def test_book_adjustment_refuses_an_unflagged_row(tmp_path):
    r = run().reset_index()
    with pytest.raises(ValueError):
        rc.book_adjustment(tmp_path / "adjustments.csv", r[r["platform"] == "GBM"].iloc[0], SETTINGS,
                           approved_on="2026-11-01")
