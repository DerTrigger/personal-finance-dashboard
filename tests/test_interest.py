"""Interest math. Dates mirror real deposits (to test weekends and holidays); amounts are fake.

Fake principal 36,000 at 10% on a 360-day basis earns exactly 10.00 a day,
so every expected amount below is simply 10 x days.
"""
from datetime import date

import pytest

from app.lib import interest as it

P, R = 36_000.0, 0.10  # 10.00 per day


def d(s):
    return date.fromisoformat(s)


# --- Business days -------------------------------------------------------

@pytest.mark.parametrize("day,expected", [
    ("2026-08-15", "2026-08-17"),  # Saturday -> Monday
    ("2026-10-18", "2026-10-19"),  # Sunday -> Monday
    ("2026-09-16", "2026-09-17"),  # Independence Day
    ("2026-11-16", "2026-11-17"),  # Revolution Day (3rd Monday of November)
    ("2026-11-14", "2026-11-17"),  # Saturday -> Monday holiday -> Tuesday
    ("2026-11-02", "2026-11-03"),  # Day of the Dead (bank holiday)
    ("2026-12-12", "2026-12-14"),  # Saturday anyway -> Monday
    ("2026-12-25", "2026-12-28"),  # Christmas (Friday) -> Monday
    ("2027-03-25", "2027-03-29"),  # Holy Thursday -> Good Friday -> weekend -> Monday
    ("2026-06-15", "2026-06-15"),  # ordinary Monday stays
])
def test_next_business_day(day, expected):
    assert it.next_business_day(d(day)) == d(expected)


def test_movable_holidays_2027():
    h = it.mx_bank_holidays(2027)
    assert d("2027-02-01") in h   # Constitution Day, 1st Monday of Feb
    assert d("2027-03-15") in h   # Benito Juárez, 3rd Monday of March
    assert d("2027-03-25") in h and d("2027-03-26") in h  # Holy Thursday, Good Friday
    assert d("2027-11-15") in h   # Revolution Day, 3rd Monday of November


# --- Simple interest -----------------------------------------------------

def test_gross_interest():
    assert it.gross_interest(P, R, 31) == 310.00


def test_isr_withholding():
    # 0.9% a year on principal, 360-day basis: 36,000 * 0.009 / 360 = 0.90 a day
    assert it.isr_withheld(P, 100, isr_rate=0.009) == 90.00


def test_net_interest():
    assert it.net_interest(P, R, 100, isr_rate=0.009) == 1000.00 - 90.00


# --- FINSUS monthly schedule (real date patterns) --------------------------

def test_schedule_12_month_deposit():
    # Real pattern: 15 May 2026 -> 17 May 2027, first payments 15 Jun, 15 Jul, 17 Aug.
    s = it.monthly_schedule(P, R, d("2026-05-15"), d("2027-05-17"))
    assert [p["date"] for p in s[:3]] == [d("2026-06-15"), d("2026-07-15"), d("2026-08-17")]
    assert [p["days"] for p in s[:3]] == [31, 30, 33]
    assert [p["gross"] for p in s[:3]] == [310.00, 300.00, 330.00]
    assert s[-1]["date"] == d("2027-05-17")
    assert sum(p["days"] for p in s) == 367
    assert sum(p["gross"] for p in s) == pytest.approx(it.gross_interest(P, R, 367), abs=0.05)


def test_schedule_holiday_in_september():
    # Real pattern: 16 Jul 2026 -> 17 Nov 2026; 16 Aug is Sunday, 16 Sep is a holiday.
    s = it.monthly_schedule(P, R, d("2026-07-16"), d("2026-11-17"))
    assert [p["date"] for p in s] == [d("2026-08-17"), d("2026-09-17"), d("2026-10-16"), d("2026-11-17")]
    assert [p["days"] for p in s] == [32, 31, 29, 32]


def test_schedule_revolution_day():
    # Real pattern: 14 Sep 2026 -> 14 Apr 2027; 14 Nov is Saturday and 16 Nov a holiday.
    s = it.monthly_schedule(P, R, d("2026-09-14"), d("2027-04-14"))
    assert [p["date"] for p in s[:3]] == [d("2026-10-14"), d("2026-11-17"), d("2026-12-14")]
    assert [p["days"] for p in s[:3]] == [30, 34, 27]
    assert s[-1]["date"] == d("2027-04-14")


def test_schedule_month_end_start():
    # Started on the 31st: pays on the last day of shorter months.
    s = it.monthly_schedule(P, R, d("2027-01-31"), d("2027-04-30"))
    assert s[0]["date"] == d("2027-03-01")  # 28 Feb 2027 is Sunday -> Monday 1 Mar
    assert s[1]["date"] == d("2027-03-31")
    assert s[-1]["date"] == d("2027-04-30")


def test_schedule_net_column():
    s = it.monthly_schedule(P, R, d("2026-05-15"), d("2027-05-17"), isr_rate=0.009)
    assert s[0]["net"] == pytest.approx(282.10)  # 310.00 minus 31 days x 0.90 ISR


# --- Accrued to a date ------------------------------------------------------

def test_accrued_before_during_after():
    start, end = d("2026-01-16"), d("2026-10-16")
    assert it.accrued_gross(P, R, start, end, d("2026-01-01")) == 0.0
    assert it.accrued_gross(P, R, start, end, d("2026-02-15")) == 300.00
    assert it.accrued_gross(P, R, start, end, d("2027-01-01")) == it.gross_interest(P, R, 273)
