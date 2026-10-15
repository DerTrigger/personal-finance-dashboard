"""Number and date formats shown on the dashboard."""
from datetime import date

import pytest

from app.lib import fmt


@pytest.mark.parametrize("value, shown", [
    (512_345, "$512.3k"),
    (210_987.65, "$211.0k"),
    (45_612.34, "$45.6k"),
    (1_234_567.89, "$1.23M"),
    (999_960, "$1.00M"),   # rounds up into millions, never "$1000.0k"
    (1_000, "$1.0k"),
    (850.4, "$850"),
    (0, "$0"),
    (-1_234, "-$1.2k"),
    (None, "–"),
    (float("nan"), "–"),
])
def test_compact(value, shown):
    assert fmt.compact(value) == shown


def test_signed_compact():
    assert fmt.signed(3_456.7) == "+$3.5k"
    assert fmt.signed(-16_543.2) == "-$16.5k"
    assert fmt.signed(0) == "+$0"


@pytest.mark.parametrize("value, shown", [
    (12_345.4, "$12,345"),
    (12_345.6, "$12,346"),
    (-500, "-$500"),
    (1_234_567.89, "$1,234,568"),
    (None, "–"),
])
def test_money(value, shown):
    assert fmt.money(value) == shown


def test_exact_keeps_cents_for_tooltips():
    assert fmt.exact(1_234_567.89) == "$1,234,567.89"


def test_pct():
    assert fmt.pct(0.8317) == "83.2%"
    assert fmt.pct(-0.05) == "-5.0%"
    assert fmt.pct(None) == "–"


def test_text_columns_show_a_dash_for_missing_values():
    import pandas as pd
    s = pd.Series([89_960.4, -2_369, None])
    assert list(fmt.text(s)) == ["$89,960", "-$2,369", "–"]
    assert list(fmt.text(s, "signed")) == ["+89,960", "-2,369", "–"]
    assert list(fmt.text(pd.Series([0.687, None]), "pct")) == ["+68.7%", "–"]


def test_change_pct():
    assert fmt.change_pct(0.705) == "+70%"
    assert fmt.change_pct(-0.1) == "-10%"
    assert fmt.change_pct(float("nan")) == "nuevo"


def test_spanish_months():
    assert fmt.month("2026-09") == "sep 2026"
    assert fmt.month("2025-01") == "ene 2025"
    assert fmt.day(date(2026, 10, 19)) == "19 oct 2026"
    assert fmt.day("2026-12-01") == "1 dic 2026"


def test_round_for_tables():
    import pandas as pd
    df = pd.DataFrame({"a": [1.4, 2.6], "b": ["x", "y"]})
    out = fmt.whole(df, ["a"])
    assert list(out["a"]) == [1, 3]
    assert list(df["a"]) == [1.4, 2.6]  # original untouched
