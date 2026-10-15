"""Shared screen helpers that compute something: quick periods and tooltip shares."""
from datetime import date

import pytest

from app.lib import ui

FIRST, LAST = date(2025, 1, 1), date(2026, 9, 28)


@pytest.mark.parametrize("name, expected", [
    ("Último mes", (date(2026, 9, 1), LAST)),
    ("Mes anterior", (date(2026, 8, 1), date(2026, 8, 31))),
    ("3 meses", (date(2026, 7, 1), LAST)),
    ("12 meses", (date(2025, 10, 1), LAST)),
    ("Este año", (date(2026, 1, 1), LAST)),
    ("Todo", (FIRST, LAST)),
])
def test_preset_range(name, expected):
    assert ui.preset_range(name, FIRST, LAST) == expected


def test_preset_range_stays_inside_the_data():
    assert ui.preset_range("12 meses", date(2026, 5, 10), LAST) == (date(2026, 5, 10), LAST)
    assert ui.preset_range("Mes anterior", date(2026, 9, 3), LAST) is None  # no data in August
    assert ui.preset_range("Mes anterior", FIRST, date(2026, 1, 15)) == (date(2025, 12, 1), date(2025, 12, 31))


def test_shares():
    assert ui.shares([1, 3]) == pytest.approx([0.25, 0.75])
    assert ui.shares([1, 1, 2, 0], ["a", "a", "b", "c"]) == pytest.approx([0.5, 0.5, 1.0, 0.0])
    assert ui.shares([0, 0]) == [0.0, 0.0]
