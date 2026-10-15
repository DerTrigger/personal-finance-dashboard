from datetime import datetime

import pytest

from app.lib import moneymanager as mm
from tests.conftest import mm_row


def basic_rows():
    return [
        mm_row("2026-03-05 12:30", "Card A", "Food", 347.88, "Exp.", "Eating out", "Los Cócteles"),
        mm_row("2026-03-15 09:00", "Payroll Account", "Salary", 40000, "Income"),
        mm_row("2026-03-20 18:00", "Nubank", "GBM", 30000, "Transfer-Out", note="Stock Investment"),
        mm_row("2026-03-20 18:00", "GBM", "Nubank", 30000, "Transfer-In", note="Stock Investment"),
    ]


def test_types_amounts_and_dates(make_export):
    df = mm.read_export(make_export("2026.xlsx", basic_rows()))
    assert list(df["type"]) == ["expense", "income", "transfer_out", "transfer_in"]
    assert df["amount"].tolist() == [347.88, 40000.0, 30000.0, 30000.0]
    assert df["date"].iloc[0] == "2026-03-05"
    assert df["month"].iloc[0] == "2026-03"


def test_accents_preserved(make_export):
    df = mm.read_export(make_export("2026.xlsx", basic_rows()))
    assert df["note"].iloc[0] == "Los Cócteles"


def test_transfer_counterpart_and_blank_text(make_export):
    df = mm.read_export(make_export("2026.xlsx", basic_rows()))
    assert df["counterpart"].tolist() == ["", "", "GBM", "Nubank"]
    # Empty cells become empty strings, never "nan".
    assert df["subcategory"].iloc[1] == ""
    assert df["note"].iloc[1] == ""


def test_transfer_pairs_all_matched(make_export):
    df = mm.read_export(make_export("2026.xlsx", basic_rows()))
    assert mm.unmatched_transfers(df).empty


def test_transfer_missing_its_other_half_is_reported(make_export):
    rows = basic_rows()[:3]  # drop the Transfer-In side
    df = mm.read_export(make_export("2026.xlsx", rows))
    bad = mm.unmatched_transfers(df)
    assert len(bad) == 1
    assert bad["account"].iloc[0] == "Nubank"


def test_identical_rows_flagged_not_dropped(make_export):
    rows = basic_rows() + [basic_rows()[0]]
    df = mm.read_export(make_export("2026.xlsx", rows))
    assert len(df) == 5
    dups = mm.find_duplicates(df)
    assert len(dups) == 2


def test_row_key_is_stable(make_export):
    a = mm.read_export(make_export("a.xlsx", basic_rows()))
    b = mm.read_export(make_export("b.xlsx", basic_rows()))
    assert a["row_key"].tolist() == b["row_key"].tolist()
    assert a["row_key"].nunique() == 4


# --- Combining exports: each file owns the dates it covers ------------------------

ANNUAL = "Money Manager Report 2026-01-01 ~ 12-31.xlsx"
SEP = "Money Manager Report 2026-09-01 ~ 09-30.xlsx"
OCT = "Money Manager Report 2026-10-01 ~ 10-31.xlsx"
OLD, NEW, NEWER = 1_000_000_000, 2_000_000_000, 3_000_000_000


def sep_rows(note="Tacos IN NU"):
    return [mm_row("2026-09-10 12:00", "Card A", "Food", 300, "Exp.", note=note),
            mm_row("2026-09-28 12:00", "Card A", "Transport", 200, "Exp.")]


NOV_1 = datetime(2026, 11, 1, 9).timestamp()
SEP_28 = datetime(2026, 9, 28, 19).timestamp()


def oct_rows():
    return [mm_row("2026-10-03 12:00", "Cash", "Food", 100, "Exp."), mm_row("2026-10-29 12:00", "Cash", "Food", 100, "Exp.")]


def test_coverage_is_the_range_in_the_file_name(make_export):
    p = make_export(OCT, oct_rows(), mtime=NOV_1)  # saved after October ended: it speaks for all of October
    assert mm.export_coverage(p, mm.read_export(p)) == ("2026-10-01", "2026-10-31", True)


def test_coverage_stops_at_the_last_transaction_if_saved_before_the_range_ends(make_export):
    p = make_export(ANNUAL, basic_rows() + sep_rows(), mtime=SEP_28)  # the annual file, saved 28 Sep
    assert mm.export_coverage(p, mm.read_export(p)) == ("2026-01-01", "2026-09-28", True)


def test_coverage_wraps_into_the_next_year(make_export):
    p = make_export("Money Manager Report 2025-12-01 ~ 01-31.xlsx",
                    [mm_row("2025-12-05 12:00", "Cash", "Food", 100, "Exp."),
                     mm_row("2026-01-20 12:00", "Cash", "Food", 100, "Exp.")], mtime=NOV_1)
    assert mm.export_coverage(p, mm.read_export(p)) == ("2025-12-01", "2026-01-31", True)
    df, _ = mm.load_exports([p])  # a file may span two years
    assert len(df) == 2


def test_coverage_without_a_readable_name_uses_the_transactions(make_export):
    p = make_export("mm.xlsx", basic_rows())
    assert mm.export_coverage(p, mm.read_export(p)) == ("2026-03-05", "2026-03-20", False)


def test_annual_file_then_monthly_files_keep_the_whole_year(make_export):
    annual = make_export(ANNUAL, basic_rows() + sep_rows(), mtime=OLD)
    oct_ = make_export(OCT, [mm_row("2026-10-05 12:00", "Cash", "Food", 100, "Exp.")], mtime=NEW)
    df, report = mm.load_exports([annual, oct_])
    assert len(df) == 7
    assert report["replaced"] == 0 and report["vanished"].empty
    assert report["files_used"] == [OCT, ANNUAL]


def test_a_newer_file_replaces_the_dates_it_covers(make_export):
    """September re-sent after the annual file: September comes from the new file, March from the annual one."""
    annual = make_export(ANNUAL, basic_rows() + sep_rows(), mtime=OLD)
    sep = make_export(SEP, sep_rows(note="Tacos") + [mm_row("2026-09-30 12:00", "Cash", "Food", 50, "Exp.")],
                      mtime=NEW)
    df, report = mm.load_exports([annual, sep])
    assert len(df) == 4 + 3                           # no September row counted twice
    assert (df["note"] == "Tacos IN NU").sum() == 0   # the tag removed in Money Manager is gone
    assert report["replaced"] == 2
    assert report["vanished"].empty                   # a changed note is an edit, not a missing row


def test_a_row_missing_from_the_newer_file_is_reported(make_export):
    old = make_export(SEP, sep_rows(), mtime=OLD)
    new = make_export(SEP.replace(".xlsx", " (1).xlsx"), sep_rows()[:1], mtime=NEW)
    df, report = mm.load_exports([old, new])
    assert len(df) == 1
    assert report["vanished"]["category"].tolist() == ["Transport"]


def test_the_newest_file_wins_whatever_the_order_given(make_export):
    old = make_export(SEP, sep_rows(), mtime=OLD)
    new = make_export(SEP.replace(".xlsx", " (1).xlsx"), sep_rows(note="Tacos"), mtime=NEWER)
    for paths in ([old, new], [new, old]):
        df, _ = mm.load_exports(paths)
        assert sorted(df["note"]) == ["", "Tacos"]


def test_a_hole_between_exports_is_warned(make_export):
    """The annual file stops at 28 Sep; if the first monthly file is October, 29-30 Sep are missing."""
    annual = make_export(ANNUAL, basic_rows() + sep_rows(), mtime=SEP_28)
    oct_ = make_export(OCT, oct_rows(), mtime=NOV_1)
    _, report = mm.load_exports([annual, oct_])
    assert report["gaps"] == [("2026-09-29", "2026-09-30")]
    assert any("29 sep" in w or "2026-09-29" in w for w in report["warnings"])


def test_exports_that_join_up_have_no_hole(make_export):
    annual = make_export(ANNUAL, basic_rows() + sep_rows(), mtime=SEP_28)
    sep = make_export(SEP, sep_rows(), mtime=datetime(2026, 10, 1, 9).timestamp())
    oct_ = make_export(OCT, oct_rows(), mtime=NOV_1)
    _, report = mm.load_exports([annual, sep, oct_])
    assert report["gaps"] == [] and report["warnings"] == []


def test_an_old_file_saved_again_later_is_warned(make_export):
    """The annual file re-saved after October's: it now wins October. Warn, since that's almost never meant."""
    oct_ = make_export(OCT, oct_rows(), mtime=NOV_1)
    annual = make_export(ANNUAL, basic_rows() + sep_rows() + oct_rows()[:1], mtime=NOV_1 + 86_400 * 70)
    _, report = mm.load_exports([annual, oct_])
    assert any(ANNUAL in w and OCT in w for w in report["warnings"])


def test_settings_can_point_at_a_sandbox(tmp_path, monkeypatch):
    from app.lib.config import data_path, load_settings
    real = load_settings()
    monkeypatch.setenv("FINANCE_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("FINANCE_INBOX_DIR", str(tmp_path / "inbox"))
    s = load_settings()
    assert data_path(s, "database") == tmp_path / "data" / real["paths"]["database"]
    assert s["paths"]["inbox_dir"] == str(tmp_path / "inbox")
    monkeypatch.delenv("FINANCE_DATA_DIR")
    monkeypatch.delenv("FINANCE_INBOX_DIR")
    assert load_settings()["paths"]["data_dir"] == real["paths"]["data_dir"]


def test_find_exports_skips_scratch_folders(tmp_path):
    from app.lib.config import find_exports
    keep = [tmp_path / "initial-setup" / ANNUAL, tmp_path / "2026" / "2026-10" / OCT]
    skip = [tmp_path / "_replay" / "2026-09-29-1911" / OCT, tmp_path / "_dryrun" / SEP]
    for p in keep + skip:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.touch()
    assert find_exports(tmp_path) == sorted(keep)


def test_find_exports_accepts_bare_date_names(tmp_path):
    # Since Oct 2026 the phone export arrives as "2026-09-01 ~ 09-30.xlsx", without the "Money Manager Report" prefix.
    from app.lib.config import find_exports
    keep = [tmp_path / "initial-setup" / ANNUAL, tmp_path / "2026" / "2026-09" / "2026-09-01 ~ 09-30.xlsx",
            tmp_path / "2026" / "2026-10" / "2026-10-01 ~ 10-31 (1).xlsx"]
    skip = [tmp_path / "2026" / "2026-09" / "budget.xlsx", tmp_path / "_replay" / "x" / "2026-09-01 ~ 09-30.xlsx"]
    for p in keep + skip:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.touch()
    assert find_exports(tmp_path) == sorted(keep)


def test_possible_duplicates_match_date_amount_account_and_category(make_export):
    rows = basic_rows() + [
        mm_row("2026-03-05 20:00", "Card A", "Food", 347.88, "Exp.", note="logged again later"),  # same day
        mm_row("2026-03-15 10:00", "Payroll Account", "Bonus", 40000, "Income"),  # same day and amount, other category
    ]
    dups = mm.find_duplicates(mm.read_export(make_export("2026.xlsx", rows)))
    assert sorted(dups["note"]) == ["Los Cócteles", "logged again later"]


def test_rejects_other_currency(make_export):
    rows = [mm_row("2026-03-05 12:30", "Card B", "Travel", 100, "Exp.", currency="USD")]
    with pytest.raises(ValueError, match="MXN"):
        mm.read_export(make_export("usd.xlsx", rows))


def test_rejects_unknown_type(make_export):
    rows = [mm_row("2026-03-05 12:30", "Cash", "Food", 100, "Refund")]
    with pytest.raises(ValueError, match="Refund"):
        mm.read_export(make_export("odd.xlsx", rows))


def test_summary_totals(make_export):
    df = mm.read_export(make_export("2026.xlsx", basic_rows()))
    s = mm.summarize(df)
    assert s[2026]["rows"] == 4
    assert s[2026]["expenses"] == 347.88
    assert s[2026]["income"] == 40000.0
    assert s[2026]["transfers_net"] == 0.0
