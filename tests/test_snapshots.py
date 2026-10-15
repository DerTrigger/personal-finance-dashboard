"""Snapshot validation. All data here is fake (see tests/snapdata.py)."""
import copy

import pandas as pd
import pytest

from app.lib import snapshots as sn
from tests.snapdata import SETTINGS, SNAP_COLS, october, row, september

EMPTY = pd.DataFrame(columns=SNAP_COLS)


def check(pending, history=EMPTY):
    return sn.validate(pending, history, SETTINGS)


def has(messages, text):
    return any(text in m for m in messages)


# --- A good month passes -----------------------------------------------------

def test_valid_month_has_no_errors_or_warnings():
    errors, warnings = check(september())
    assert errors == []
    assert warnings == []


def test_valid_next_month_passes_against_history():
    errors, _ = check(october(), september())
    assert errors == []


# --- Errors: block saving ----------------------------------------------------

def test_missing_column_is_an_error():
    errors, _ = check(september().drop(columns=["value"]))
    assert has(errors, "faltan columnas")


def test_bad_date_is_an_error():
    p = september()
    p["as_of"] = "30/09/2026"
    errors, _ = check(p)
    assert has(errors, "fecha")


def test_two_dates_in_one_file_is_an_error():
    p = september()
    p.loc[0, "as_of"] = "2026-09-29"
    errors, _ = check(p)
    assert has(errors, "más de una fecha")


def test_month_already_saved_is_an_error():
    errors, _ = check(september(), september())
    assert has(errors, "ya está guardad")


def test_duplicate_row_is_an_error():
    p = september()
    p = pd.concat([p, p.iloc[[1]]], ignore_index=True)
    errors, _ = check(p)
    assert has(errors, "duplicada")


def test_missing_platform_is_an_error():
    p = september()
    errors, _ = check(p[p["platform"] != "Bitso"])
    assert has(errors, "Bitso")
    assert has(errors, "Falta")


def test_missing_total_row_is_an_error():
    p = september()
    p = p[~((p["platform"] == "GBM") & (p["item_type"] == "total"))]
    errors, _ = check(p)
    assert has(errors, "GBM")
    assert has(errors, "total")


def test_parts_not_adding_up_is_an_error():
    p = september()
    p.loc[p["name"] == "VOO", "value"] = 6010.0
    p.loc[p["name"] == "VOO", "gain"] = 1010.0
    p.loc[p["name"] == "VOO", "gain_pct"] = 0.2020
    errors, _ = check(p)
    assert has(errors, "GBM")
    assert has(errors, "suman")


def test_parts_off_by_less_than_a_peso_pass():
    p = september()
    p.loc[p["name"] == "Car", "value"] = 200000.0
    p.loc[(p["platform"] == "Nu") & (p["item_type"] == "total"), "value"] = 40000.60
    errors, _ = check(p)
    assert errors == []


def test_unknown_nu_cajita_is_an_error():
    p = september()
    p.loc[p["name"] == "Cajita Ahorro", "name"] = "Vacaciones"
    errors, _ = check(p)
    assert has(errors, "Vacaciones")


def test_wrong_gain_pct_is_an_error():
    p = september()
    p.loc[p["name"] == "VOO", "gain_pct"] = 0.25  # should be 1000 / 5000 = 0.20
    errors, _ = check(p)
    assert has(errors, "VOO")
    assert has(errors, "ganancia mostrada")


def test_missing_value_is_an_error():
    p = september()
    p.loc[p["name"] == "BTC", "value"] = None
    errors, _ = check(p)
    assert has(errors, "BTC")
    assert has(errors, "valor")


def test_statement_already_saved_is_an_error():
    hist = september()
    p = october()
    p.loc[p["item_type"] == "statement", "as_of"] = "2026-09-30"
    errors, _ = check(p, hist)
    assert has(errors, "ya está guardad")


# --- Warnings: shown in the confirm table ------------------------------------

def test_big_jump_is_a_warning():
    hist = september()
    p = october()
    p.loc[p["platform"] == "Bitso", "value"] = 9000.0  # +80%
    errors, warnings = check(p, hist)
    assert errors == []
    assert has(warnings, "Bitso")
    assert has(warnings, "%")


def test_item_gone_is_a_warning():
    # The Kubo deposit matured and is not in October.
    _, warnings = check(october(), september())
    assert has(warnings, "Plazo")
    assert has(warnings, "ya no aparece")


def test_new_item_is_a_warning():
    hist = september()
    p = october()
    extra = pd.DataFrame([row("2026-10-31", "Bitso", "variable", "holding", "ETH", 0.0, asset_type="crypto")])
    p = pd.concat([p, extra], ignore_index=True)
    _, warnings = check(p, hist)
    assert has(warnings, "ETH")
    assert has(warnings, "nuevo")


def test_deposit_interest_mismatch_is_a_warning():
    p = september()
    p.loc[p["name"] == "Casita", "interest_total"] = 1900.0  # should be 1810.00
    errors, warnings = check(p)
    assert errors == []
    assert has(warnings, "Casita")
    assert has(warnings, "interés")


def test_deposit_past_its_end_date_is_a_warning():
    # Kubo "Plazo" ended 2026-10-17 but is still listed on 2026-10-31.
    sep = september()
    kubo = sep[sep["platform"] == "Kubo Financiero"].assign(as_of="2026-10-31")
    p = october()
    p = pd.concat([p[p["platform"] != "Kubo Financiero"], kubo], ignore_index=True)
    errors, warnings = check(p, sep)
    assert errors == []
    assert has(warnings, "Plazo")
    assert has(warnings, "venció")


def test_unexpected_platform_is_a_warning():
    p = september()
    extra = pd.DataFrame([row("2026-09-30", "Cetes", "sofipo_fixed", "total", "Cetes", 1000.0)])
    _, warnings = check(pd.concat([p, extra], ignore_index=True))
    assert has(warnings, "Cetes")


# --- Opening and closing accounts --------------------------------------------

def with_platform(name, **changes):
    s = copy.deepcopy(SETTINGS)
    s["platforms"][name].update(changes)
    return s


def test_closed_account_is_no_longer_expected():
    s = with_platform("Bitso", status="closed", closed="2026-09-15")
    p = september()
    errors, warnings = sn.validate(p[p["platform"] != "Bitso"], EMPTY, s)
    assert errors == []
    assert warnings == []


def test_account_closed_after_the_date_is_still_expected():
    s = with_platform("Bitso", status="closed", closed="2026-10-15")
    p = september()
    errors, _ = sn.validate(p[p["platform"] != "Bitso"], EMPTY, s)
    assert any("Falta Bitso" in e for e in errors)


def test_closed_account_that_still_appears_is_a_warning():
    s = with_platform("Bitso", status="closed", closed="2026-09-15")
    errors, warnings = sn.validate(september(), EMPTY, s)
    assert errors == []
    assert has(warnings, "cerrada")


def test_account_not_yet_opened_is_not_expected():
    s = with_platform("Bitso", opened="2026-10-01")
    p = september()
    errors, _ = sn.validate(p[p["platform"] != "Bitso"], EMPTY, s)
    assert errors == []


def test_new_account_added_to_settings_is_expected():
    s = copy.deepcopy(SETTINGS)
    s["platforms"]["Cetes"] = dict(SETTINGS["platforms"]["Kubo Financiero"])
    errors, _ = sn.validate(september(), EMPTY, s)
    assert any("Falta Cetes" in e for e in errors)


# --- Helpers used by the tools -----------------------------------------------

def test_snapshot_dates_ignore_statements():
    hist = pd.concat([september(), october()], ignore_index=True)
    hist.loc[hist["item_type"] == "statement", "as_of"] = "2026-08-31"
    assert sn.snapshot_dates(hist) == ["2026-09-30", "2026-10-31"]


def test_platform_totals():
    t = sn.platform_totals(september())
    assert t["GBM"] == pytest.approx(10000.0)
    assert t["Manual"] == pytest.approx(200000.0)


def test_confirm_table_shows_change_vs_last_month():
    t = sn.confirm_table(october(), september()).set_index("platform")
    assert t.loc["GBM", "total"] == pytest.approx(13500.0)
    assert t.loc["GBM", "last_month"] == pytest.approx(10000.0)
    assert t.loc["GBM", "change"] == pytest.approx(3500.0)
    assert t.loc["GBM", "items"] == 2
    assert t["total"].sum() == pytest.approx(785_227.20)


# --- Saving ------------------------------------------------------------------

def write(df, path):
    df.to_csv(path, index=False, encoding="utf-8-sig")
    return path


def test_append_adds_rows_and_keeps_a_backup(tmp_path):
    csv_path = write(september(), tmp_path / "snaps.csv")
    pending = write(october(), tmp_path / "pending.csv")
    added = sn.append_snapshot(pending, csv_path, SETTINGS, confirmed_on="2026-11-01")
    assert added == len(october())
    saved = pd.read_csv(csv_path, encoding="utf-8-sig")
    assert len(saved) == len(september()) + len(october())
    assert list(saved.columns) == SNAP_COLS
    assert (saved[saved["as_of"] == "2026-10-31"]["confirmed_on"] == "2026-11-01").all()
    backup = pd.read_csv(tmp_path / "snaps.csv.bak", encoding="utf-8-sig")
    assert len(backup) == len(september())


def test_append_refuses_when_there_are_errors(tmp_path):
    csv_path = write(september(), tmp_path / "snaps.csv")
    before = csv_path.read_bytes()
    pending = write(september(), tmp_path / "pending.csv")  # same month again
    with pytest.raises(ValueError, match="ya está guardad"):
        sn.append_snapshot(pending, csv_path, SETTINGS, confirmed_on="2026-11-01")
    assert csv_path.read_bytes() == before
    assert not (tmp_path / "snaps.csv.bak").exists()


def test_manual_asset_change_is_a_warning():
    """The car and Activos change only when Memo gives a new value: any change is shown for him to confirm."""
    _, warnings = check(october(), september())
    assert has(warnings, "Manual 'Car'")  # october() revalues the car
    same = october().copy()
    same.loc[same["item_type"] == "manual_asset", "value"] = 200000.0
    _, warnings = check(same, september())
    assert not has(warnings, "Manual 'Car'")


# --- Draft for next month, and scoring a first pass --------------------------------

def test_draft_copies_last_month_and_blanks_what_must_be_read():
    history = pd.concat([september(), october()], ignore_index=True)
    d = sn.draft(history, "2026-11-30").set_index(["platform", "item_type", "name"])
    assert (d["as_of"] == "2026-11-30").all()
    # Numbers read from the screens again are blank
    assert d.loc[("GBM", "holding", "VOO"), ["value", "gain", "gain_pct"]].isna().all()
    assert pd.isna(d.loc[("Nu", "total", "Nu"), "value"])
    assert d.loc[("Nu", "cajita", "Cajita Ahorro"), ["value", "gain", "annual_rate"]].isna().all()
    assert d.loc[("FINSUS", "on_demand", "finsus +"), ["value", "annual_rate"]].isna().all()
    assert pd.isna(d.loc[("Profuturo", "subaccount", "Ahorro para el retiro"), "value"])
    # Deposit terms and manual assets carry over
    casita = d.loc[("FINSUS", "deposit", "Casita")]
    assert casita["principal"] == 36000.0 and casita["end_date"] == "2027-03-15" and casita["value"] == 36000.0
    assert d.loc[("Manual", "manual_asset", "Car"), "value"] == 190000.0
    # Statements come only when there's a new one
    assert "statement" not in set(d.reset_index()["item_type"])


def test_draft_from_a_chosen_month():
    history = pd.concat([september(), october()], ignore_index=True)
    d = sn.draft(history, "2026-09-30", from_date="2026-09-30")
    assert len(d) == len(september()) - 1  # all but the statement
    assert (d["as_of"] == "2026-09-30").all()


def test_compare_a_perfect_first_pass():
    s = sn.compare(october(), october())
    assert s["corrected"].sum() == 0 and s["missing"].sum() == 0 and s["extra"].sum() == 0
    assert s.set_index("platform").loc["GBM", "fields"] > 0


def test_compare_counts_corrections_misses_and_extras():
    first = october().copy()
    first.loc[first["name"] == "VOO", "value"] = 9_310.0          # misread
    first.loc[first["name"] == "FUNO11", "gain"] = -100.004        # within rounding: not a correction
    first = first[first["name"] != "BTC"]                          # missed
    extra = first[first["name"] == "VOO"].assign(name="QQQ")       # read something that isn't there
    first = pd.concat([first, extra], ignore_index=True)
    s = sn.compare(first, october()).set_index("platform")
    assert s.loc["GBM", "corrected"] == 1
    assert s.loc["GBM", "extra"] == 1
    assert s.loc["Bitso", "missing"] == 1
    assert s.loc["Nu", "corrected"] == 0


def test_append_twice_adds_nothing_the_second_time(tmp_path):
    csv_path = write(september(), tmp_path / "snaps.csv")
    pending = write(october(), tmp_path / "pending.csv")
    sn.append_snapshot(pending, csv_path, SETTINGS, confirmed_on="2026-11-01")
    with pytest.raises(ValueError):
        sn.append_snapshot(pending, csv_path, SETTINGS, confirmed_on="2026-11-01")
    assert len(pd.read_csv(csv_path, encoding="utf-8-sig")) == len(september()) + len(october())
