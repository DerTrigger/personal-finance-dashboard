"""Dashboard numbers. All data here is fake (see tests/snapdata.py and tests/conftest.py)."""
import sqlite3
from contextlib import closing
from datetime import date

import pandas as pd
import pytest

from app.lib import db, metrics as mx, moneymanager as mm
from app.lib import interest as it
from tests.conftest import mm_row
from tests.snapdata import SETTINGS, october, september


def november():
    """October plus 200 of GBM gain; nothing else moves."""
    n = october().assign(as_of="2026-11-30")
    n.loc[n["name"] == "VOO", ["value", "gain"]] += 200.0
    n.loc[(n["platform"] == "GBM") & (n["item_type"] == "total"), "value"] += 200.0
    return n


SNAPS = pd.concat([september(), october()], ignore_index=True)
SNAPS3 = pd.concat([SNAPS, november()], ignore_index=True)

MM_ROWS = [
    mm_row("2026-09-05 12:00", "Card A", "Food", 1000, "Exp.", subcategory="Groceries"),
    mm_row("2026-09-06 12:00", "Nubank", "Transport", 500, "Exp."),
    mm_row("2026-09-15 09:00", "Payroll Account", "Salary", 10000, "Income"),
    mm_row("2026-09-20 18:00", "Nubank", "GBM", 3000, "Transfer-Out"),
    mm_row("2026-09-20 18:00", "GBM", "Nubank", 3000, "Transfer-In"),
    mm_row("2026-10-05 12:00", "Card A", "Food", 1500, "Exp.", subcategory="Restaurants"),
    mm_row("2026-10-06 12:00", "Nubank", "Food", 200, "Exp.", subcategory="Groceries"),
    mm_row("2026-10-15 09:00", "Payroll Account", "Salary", 10000, "Income"),
    mm_row("2026-10-20 09:00", "Nubank", "Interest", 100, "Income"),
]


@pytest.fixture
def tx(make_export):
    table, _ = mm.load_exports([make_export("mm2026.xlsx", MM_ROWS)])
    return table


# --- Net worth ---------------------------------------------------------------

def test_net_worth_series():
    s = mx.net_worth_series(SNAPS3)
    assert list(s["as_of"]) == ["2026-09-30", "2026-10-31", "2026-11-30"]
    assert list(s["net_worth"]) == pytest.approx([803_000.0, 785_227.20, 785_427.20])


def test_net_worth_by_type():
    t = mx.net_worth_by_type(september()).set_index("account_type")["value"]
    assert t["retirement"] == pytest.approx(420_000.0)
    assert t["variable"] == pytest.approx(15_000.0)
    assert t["manual_asset"] == pytest.approx(200_000.0)
    assert t.sum() == pytest.approx(803_000.0)


def test_why_changed_parts_add_up(tx):
    w = mx.why_changed(SNAPS3, tx, SETTINGS)
    assert list(w["end"]) == ["2026-10-31", "2026-11-30"]
    parts = w["put_in"] + w["returns"] + w["estimated_returns"] + w["revaluation"]
    assert (parts - w["change"]).abs().max() == pytest.approx(0, abs=0.005)


def test_month_summary_full_close(tx):
    s = mx.month_summary(SNAPS, tx, SETTINGS, "2026-10")
    assert s["as_of"] == "2026-10-31" and s["previous"] == "2026-09-30"
    assert s["net_worth"] == pytest.approx(785_227.20)
    assert s["change"] == pytest.approx(-17_772.80)
    assert s["why"]["returns"] == pytest.approx(3_237.20)
    assert s["why"]["revaluation"] == pytest.approx(-10_000.0)
    assert s["income"] == pytest.approx(10_100.0) and s["expenses"] == pytest.approx(1_700.0)
    assert s["net_income"] == pytest.approx(8_400.0)
    assert s["card_pending"]["total"] == pytest.approx(0.0)


def test_month_summary_export_only(tx):
    """No snapshot in the month (an export-only close): cash flow only, net worth as of the latest snapshot."""
    s = mx.month_summary(SNAPS[SNAPS["as_of"] == "2026-09-30"], tx, SETTINGS, "2026-10")
    assert s["why"] is None and s["change"] is None
    assert s["as_of"] == "2026-09-30"
    assert s["income"] == pytest.approx(10_100.0)


def test_why_changed_october(tx):
    w = mx.why_changed(SNAPS, tx, SETTINGS).iloc[0]
    assert w["change"] == pytest.approx(-17_772.80)
    # Nu 300 + FINSUS 527.20 + Kubo 910 + GBM 500 + Allianz 1,000
    assert w["returns"] == pytest.approx(3_237.20)
    # Bitso 400 + Profuturo 1,500
    assert w["estimated_returns"] == pytest.approx(1_900.0)
    assert w["revaluation"] == pytest.approx(-10_000.0)
    # GBM 3,000 + Kubo -20,910 + Allianz 5,000
    assert w["put_in"] == pytest.approx(-12_910.0)


def test_why_changed_needs_two_snapshots(tx):
    assert mx.why_changed(september(), tx, SETTINGS).empty


# --- Cash flow and filters ---------------------------------------------------

def test_cashflow(tx):
    c = mx.cashflow(tx).set_index("month")
    assert c.loc["2026-09", "income"] == pytest.approx(10_000.0)
    assert c.loc["2026-09", "expenses"] == pytest.approx(1_500.0)
    assert c.loc["2026-09", "net_income"] == pytest.approx(8_500.0)
    assert c.loc["2026-09", "savings_rate"] == pytest.approx(0.85)
    assert c.loc["2026-10", "income"] == pytest.approx(10_100.0)
    assert c.loc["2026-10", "savings_rate"] == pytest.approx(round(8_400 / 10_100, 4))  # shown as 83.17%


def test_filter_by_account(tx):
    c = mx.cashflow(mx.filter_tx(tx, accounts=["Card A"])).set_index("month")
    assert list(c["expenses"]) == pytest.approx([1_000.0, 1_500.0])
    assert c["income"].sum() == 0
    assert c["savings_rate"].isna().all()


def test_filter_by_month_and_category(tx):
    f = mx.filter_tx(tx, months=("2026-10", "2026-10"), categories=["Food"])
    assert set(f["month"]) == {"2026-10"}
    assert mx.cashflow(f)["expenses"].sum() == pytest.approx(1_700.0)


def test_no_filters_keeps_everything(tx):
    assert len(mx.filter_tx(tx)) == len(tx)


def test_expenses_by_category_and_subcategory(tx):
    e = mx.expenses_by(tx, "category")
    food = e[(e["month"] == "2026-10") & (e["category"] == "Food")]
    assert food["amount"].sum() == pytest.approx(1_700.0)
    s = mx.expenses_by(mx.filter_tx(tx, categories=["Food"]), "subcategory")
    assert s[s["subcategory"] == "Groceries"]["amount"].sum() == pytest.approx(1_200.0)


def test_month_over_month(tx):
    m = mx.month_over_month(tx, "category").set_index("category")
    assert m.loc["Food", "this_month"] == pytest.approx(1_700.0)
    assert m.loc["Food", "last_month"] == pytest.approx(1_000.0)
    assert m.loc["Food", "change"] == pytest.approx(700.0)
    assert m.loc["Transport", "this_month"] == pytest.approx(0.0)
    assert m.loc["Transport", "change"] == pytest.approx(-500.0)


def test_income_by_source(tx):
    i = mx.income_by_source(tx)
    oct_ = i[i["month"] == "2026-10"].set_index("category")["amount"]
    assert oct_["Salary"] == pytest.approx(10_000.0)
    assert oct_["Interest"] == pytest.approx(100.0)


def test_payment_tags():
    assert mx.payment_tag("Tianguis IN NU") == mx.SET_ASIDE
    assert mx.payment_tag("in nu") == mx.SET_ASIDE
    assert mx.payment_tag("Los Cócteles NPY") == mx.NOT_SET_ASIDE
    assert mx.payment_tag("($200 IN NU)") == mx.PARTIAL
    assert mx.payment_tag("Menu nuevo") == ""   # "nu" inside a word is not a tag
    assert mx.payment_tag(None) == ""


def test_card_pending(make_export):
    rows = MM_ROWS + [
        mm_row("2026-10-21 12:00", "Card A", "Food", 300, "Exp.", note="Tacos IN NU"),
        mm_row("2026-10-22 12:00", "Card A", "Transport", 600, "Exp.", note="($200 IN NU)"),
        mm_row("2026-10-23 12:00", "Card B", "Food", 150, "Exp.", note="Cena NPY"),
        # A PPR contribution charged to the card: counted once, from the transfer out
        mm_row("2026-10-24 12:00", "Card A", "Allianz PPR", 5000, "Transfer-Out", note="PPR IN NU"),
        mm_row("2026-10-24 12:00", "Allianz PPR", "Card A", 5000, "Transfer-In", note="PPR IN NU"),
    ]
    table, _ = mm.load_exports([make_export("mm.xlsx", rows)])
    p = mx.card_pending(table)
    assert len(p) == 4
    assert p["amount"].sum() == pytest.approx(6_050.0)
    assert p["set_aside"].sum() == pytest.approx(5_500.0)       # 300 + 200 + 5,000
    assert p["not_set_aside"].sum() == pytest.approx(550.0)     # 400 + 150
    assert mx.card_pending(mm.load_exports([make_export("clean.xlsx", MM_ROWS)])[0]).empty


def test_card_pending_counts_only_the_latest_export(make_export):
    """September's tags can't be updated once October's file arrives (exports cover last month only)."""
    sep = make_export("Money Manager Report 2026-09-01 ~ 09-30.xlsx",
                      [mm_row("2026-09-21 12:00", "Card A", "Food", 300, "Exp.", note="Tacos IN NU")],
                      mtime=1_000_000_000)
    oct_ = make_export("Money Manager Report 2026-10-01 ~ 10-31.xlsx",
                       [mm_row("2026-10-21 12:00", "Card A", "Food", 150, "Exp.", note="Cena NPY")],
                       mtime=2_000_000_000)
    table, _ = mm.load_exports([sep, oct_])
    p = mx.card_pending(table)
    assert p["note"].tolist() == ["Cena NPY"]


def test_filter_by_calendar_dates(tx):
    f = mx.filter_tx(tx, dates=(date(2026, 9, 6), date(2026, 10, 5)))
    assert sorted(f["date"]) == ["2026-09-06", "2026-09-15", "2026-09-20", "2026-09-20", "2026-10-05"]


def test_filter_by_subcategory(tx):
    f = mx.filter_tx(tx, categories=["Food"], subcategories=["Groceries"])
    assert f["amount"].sum() == pytest.approx(1_200.0)


def test_other_month():
    assert mx.other_month("2026-09", "prev_month") == "2026-08"
    assert mx.other_month("2026-01", "prev_month") == "2025-12"
    assert mx.other_month("2026-09", "prev_year") == "2025-09"


def test_compare_months_vs_previous_month(tx):
    c = mx.compare_months(tx, "2026-10", "prev_month", kind="expense").set_index("category")
    assert c.loc["Food", "this"] == pytest.approx(1_700.0)
    assert c.loc["Food", "other"] == pytest.approx(1_000.0)
    assert c.loc["Food", "change"] == pytest.approx(700.0)
    assert c.loc["Food", "change_pct"] == pytest.approx(0.70)
    assert c.loc["Transport", "change_pct"] == pytest.approx(-1.0)


def test_compare_months_vs_same_month_last_year(tx):
    # No data a year earlier: every "other" is 0 and the % change is empty (not infinite).
    c = mx.compare_months(tx, "2026-10", "prev_year", kind="expense").set_index("category")
    assert c.loc["Food", "other"] == pytest.approx(0.0)
    assert pd.isna(c.loc["Food", "change_pct"])


def test_compare_months_income(tx):
    c = mx.compare_months(tx, "2026-10", "prev_month", kind="income").set_index("category")
    assert c.loc["Interest", "change"] == pytest.approx(100.0)


def test_net_worth_by_date_and_type():
    t = mx.net_worth_by_date(SNAPS3, "account_type")
    per_date = t.groupby("as_of")["value"].sum()
    assert list(per_date) == pytest.approx([803_000.0, 785_227.20, 785_427.20])
    oct_var = t[(t["as_of"] == "2026-10-31") & (t["account_type"] == "variable")]["value"].sum()
    assert oct_var == pytest.approx(18_900.0)  # GBM 13,500 + Bitso 5,400
    by_platform = mx.net_worth_by_date(SNAPS3, "platform", dates=(date(2026, 11, 1), date(2026, 11, 30)))
    assert set(by_platform["as_of"]) == {"2026-11-30"}


def test_net_worth_series_in_a_date_range():
    s = mx.net_worth_series(SNAPS3, dates=(date(2026, 10, 1), date(2026, 12, 31)))
    assert list(s["as_of"]) == ["2026-10-31", "2026-11-30"]


def test_filters_match_a_direct_database_query(tmp_path, make_export):
    snaps_csv = tmp_path / "snaps.csv"
    SNAPS.to_csv(snaps_csv, index=False, encoding="utf-8-sig")
    db_file = tmp_path / "finance.db"
    db.build_database(db_file, [make_export("mm.xlsx", MM_ROWS)], snaps_csv, tmp_path / "adj.csv", SETTINGS)
    tx = db.read_table(db_file, "transactions")
    for accounts in (None, ["Nubank"], ["Card A", "Nubank"]):
        for months in (None, ("2026-10", "2026-10")):
            got = mx.cashflow(mx.filter_tx(tx, months=months, accounts=accounts))["expenses"].sum()
            sql = "SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE type = 'expense'"
            params = []
            if accounts:
                sql += f" AND account IN ({','.join('?' * len(accounts))})"
                params += accounts
            if months:
                sql += " AND month BETWEEN ? AND ?"
                params += list(months)
            assert got == pytest.approx(db.query(db_file, sql, params)[0][0])
    with closing(sqlite3.connect(db_file)):
        pass  # read_table must have closed its own connection; replacing the file must work
    db_file.unlink()


# --- Investments -------------------------------------------------------------

def test_upcoming_events_move_past_holidays():
    deps = september()
    deps = deps[deps["item_type"] == "deposit"]
    ev = it.upcoming_events(deps.itertuples(), date(2026, 9, 30), 0.009, days=60)
    assert [(e["date"], e["name"], e["amount"]) for e in ev] == [
        (date(2026, 10, 15), "Casita", 273.00),
        (date(2026, 10, 17), "Plazo", 20_910.00),
        # Nov 15 is a Sunday and Nov 16 is Revolution Day: paid Nov 17, 33 days -> 330.00 - 29.70
        (date(2026, 11, 17), "Casita", 300.30),
    ]


def test_deposits_table_after_tax():
    d = mx.deposits_table(september(), 0.009).set_index("name")
    # FINSUS shows gross 1,810.00; after ISR (36,000 x 0.9% x 181/360 = 162.90) it's 1,647.10
    assert d.loc["Casita", "interest_after_tax"] == pytest.approx(1_647.10)
    assert d.loc["Plazo", "interest_after_tax"] == pytest.approx(910.0)
    assert d.loc["Plazo", "days_left"] == 17


def test_holdings():
    h = mx.holdings(september()).set_index("name")
    assert h.loc["VOO", "invested"] == pytest.approx(5_000.0)
    assert h.loc["VOO", "gain_pct"] == pytest.approx(0.20)
    assert pd.isna(h.loc["BTC", "invested"])
    mix = mx.holdings_mix(september()).set_index("asset_type")["value"]
    assert mix["etf"] == pytest.approx(10_000.0)
    assert mix["crypto"] == pytest.approx(5_000.0)


def test_retirement():
    r = mx.retirement(september())
    assert r["allianz"]["total"] == pytest.approx(120_000.0)
    assert r["allianz"]["contributions"] == pytest.approx(100_000.0)
    assert r["allianz"]["statement_gain"] == pytest.approx(19_000.0)
    sub = r["profuturo"].set_index("name")["value"]
    assert sub["Ahorro para la vivienda (Infonavit)"] == pytest.approx(50_000.0)
    assert r["profuturo_total"] == pytest.approx(300_000.0)


def test_retirement_parts():
    p = mx.retirement_parts(september()).set_index(["account", "part"])["value"]
    assert p["Allianz PPR", "Aportado"] == pytest.approx(100_000.0)
    assert p["Allianz PPR", "Rendimiento"] == pytest.approx(20_000.0)  # today's 120k minus the 100k put in
    assert p["Profuturo"].sum() == pytest.approx(300_000.0)


def test_investment_views_use_the_latest_snapshot():
    assert mx.holdings(SNAPS).set_index("name").loc["VOO", "value"] == pytest.approx(9_300.0)


# --- Data check --------------------------------------------------------------

def test_data_check(tx):
    c = mx.data_check(SNAPS, tx, SETTINGS)
    assert c["latest"] == "2026-10-31"
    assert c["errors"] == []
    assert any("Plazo" in w for w in c["warnings"])
    flagged = set(c["reconcile"].loc[c["reconcile"]["flagged"], "platform"])
    assert flagged == {"GBM", "Allianz PPR"}  # October transfers weren't logged in the fake export
    assert c["duplicates"].empty
    assert c["unmatched"].empty
