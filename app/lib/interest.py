"""
Fixed-yield interest math for SOFIPO deposits.

- Simple interest on a 360-day basis: principal x rate x days / 360.
- ISR withholding: principal x isr_rate x days / 360 (0.9% a year in 2026; set in settings.toml).
- FINSUS: gross amounts on screen, paid monthly on the start day of each month,
  moved to the next business day when that falls on a weekend or a Mexican bank holiday.
- Kubo: net amounts on screen, paid at maturity.
"""
import calendar
from datetime import date, timedelta
from functools import lru_cache

DAY_BASIS = 360


# --- Calendar --------------------------------------------------------------

def _easter(year):
    """Easter Sunday (Gregorian), anonymous algorithm."""
    a, b, c = year % 19, year // 100, year % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = (h + l - 7 * m + 114) % 31 + 1
    return date(year, month, day)


def _nth_monday(year, month, n):
    first = date(year, month, 1)
    offset = (7 - first.weekday()) % 7  # days until the first Monday
    return first + timedelta(days=offset + 7 * (n - 1))


@lru_cache(maxsize=None)
def mx_bank_holidays(year):
    """Days Mexican banks are closed (CNBV calendar). Presidential inauguration years are not included."""
    easter = _easter(year)
    return frozenset({
        date(year, 1, 1),
        _nth_monday(year, 2, 1),    # Constitution Day
        _nth_monday(year, 3, 3),    # Benito Juárez
        easter - timedelta(days=3),  # Holy Thursday
        easter - timedelta(days=2),  # Good Friday
        date(year, 5, 1),
        date(year, 9, 16),
        date(year, 11, 2),
        _nth_monday(year, 11, 3),   # Revolution Day
        date(year, 12, 12),
        date(year, 12, 25),
    })


def is_business_day(day):
    return day.weekday() < 5 and day not in mx_bank_holidays(day.year)


def next_business_day(day):
    """The same day if it's a business day, otherwise the next one."""
    while not is_business_day(day):
        day += timedelta(days=1)
    return day


def add_months(day, months):
    """Same day-of-month N months later, clamped to the month's last day."""
    y, m = divmod(day.month - 1 + months, 12)
    y, m = day.year + y, m + 1
    return date(y, m, min(day.day, calendar.monthrange(y, m)[1]))


# --- Interest --------------------------------------------------------------

def gross_interest(principal, rate, days):
    return round(principal * rate * days / DAY_BASIS, 2)


def isr_withheld(principal, days, isr_rate):
    return round(principal * isr_rate * days / DAY_BASIS, 2)


def net_interest(principal, rate, days, isr_rate):
    return round(gross_interest(principal, rate, days) - isr_withheld(principal, days, isr_rate), 2)


def deposit_interest(row, isr_rate):
    """Total interest of a deposit, the way its platform shows it.

    `row` has principal, annual_rate, start_date, end_date, term_days, payout, interest_basis.
    Monthly-payout deposits (FINSUS) earn on the actual days start->end; at-maturity deposits (Kubo)
    earn on the term days. "net" basis subtracts ISR.
    """
    start, end = date.fromisoformat(str(row.start_date)), date.fromisoformat(str(row.end_date))
    days = (end - start).days if row.payout == "monthly" else int(row.term_days)
    if row.interest_basis == "net":
        return net_interest(row.principal, row.annual_rate, days, isr_rate)
    return gross_interest(row.principal, row.annual_rate, days)


def upcoming_events(deposits, today, isr_rate, days=60):
    """Money arriving from deposits between today and today + days, soonest first.

    `deposits` is an iterable of rows like deposit_interest() takes, plus platform and name.
    Each event: date, platform, name, amount, what. Monthly payouts are after tax.
    """
    events = []
    for r in deposits:
        start, end = date.fromisoformat(str(r.start_date)), date.fromisoformat(str(r.end_date))
        if r.payout == "monthly":
            for p in monthly_schedule(r.principal, r.annual_rate, start, end, isr_rate):
                events.append((p["date"], r.platform, r.name, p["net"], "interest (after tax)"))
            events.append((end, r.platform, r.name, r.principal, "principal returned"))
        else:
            # The platform's own after-tax figure wins when it has one.
            shown = getattr(r, "interest_total", None)
            if r.interest_basis == "net" and shown == shown and shown is not None:
                interest = shown
            else:
                interest = net_interest(r.principal, r.annual_rate, int(r.term_days), isr_rate)
            events.append((end, r.platform, r.name, round(r.principal + interest, 2), "principal + interest"))
    return [{"date": d, "platform": p, "name": n, "amount": a, "what": w}
            for d, p, n, a, w in sorted(events, key=lambda e: (e[0], e[1], e[2], e[4]))
            if 0 <= (d - today).days <= days]


def accrued_gross(principal, rate, start, end, as_of):
    """Gross interest earned from start up to as_of (capped at end)."""
    days = (min(as_of, end) - start).days
    return gross_interest(principal, rate, max(days, 0))


def monthly_schedule(principal, rate, start, end, isr_rate=0.0):
    """Monthly payouts from start to end. Each item: date, days, gross, net."""
    payments, prev, k = [], start, 1
    while True:
        pay = next_business_day(add_months(start, k))
        if pay >= end:
            pay = end
        days = (pay - prev).days
        gross = gross_interest(principal, rate, days)
        payments.append({
            "date": pay,
            "days": days,
            "gross": gross,
            "net": round(gross - isr_withheld(principal, days, isr_rate), 2),
        })
        if pay == end:
            return payments
        prev, k = pay, k + 1
