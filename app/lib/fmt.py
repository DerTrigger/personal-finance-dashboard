"""
How numbers and dates look on the dashboard (Spanish labels, MXN with $ and commas).

- compact: charts and KPI cards ($45.6k, $548.4k, $1.23M)
- money: tables and text, whole pesos ($12,345)
- exact: tooltips, to the cent ($1,234,567.89)
"""
from datetime import date

MONTHS = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
EMPTY = "–"

# st.column_config formats. Tables get whole pesos (round first with whole()); these ignore the browser's
# language, so it's always $12,345 and never 22.260,00 $.
TABLE_MONEY = "$%,d"
TABLE_SIGNED = "%+,d"   # for columns that can be negative: +1,200 / -500 (the header says "($)")
TABLE_PCT = "%.1f%%"    # pass values already multiplied by 100


def _missing(x):
    return x is None or x != x


def compact(x):
    if _missing(x):
        return EMPTY
    sign, a = ("-" if x < 0 else ""), abs(x)
    if round(a / 1_000, 1) >= 1_000:
        return f"{sign}${a / 1_000_000:.2f}M"
    if a >= 1_000:
        return f"{sign}${a / 1_000:.1f}k"
    return f"{sign}${a:.0f}"


def signed(x):
    if _missing(x):
        return EMPTY
    return compact(x) if x < 0 else "+" + compact(x)


def money(x):
    if _missing(x):
        return EMPTY
    return f"-${abs(x):,.0f}" if round(x) < 0 else f"${x:,.0f}"


def exact(x):
    if _missing(x):
        return EMPTY
    return f"-${abs(x):,.2f}" if x < 0 else f"${x:,.2f}"


def pct(x, digits=1):
    return EMPTY if _missing(x) else f"{x * 100:.{digits}f}%"


def text(series, kind="money"):
    """A table column as text, for columns with missing values (shown as "–", not "None").
    kind: money ($12,345), signed (+1,200), pct (+68.7%)."""
    def one(x):
        if _missing(x):
            return EMPTY
        if kind == "signed":
            return f"{x:+,.0f}"
        if kind == "pct":
            return f"{x * 100:+.1f}%"
        return money(x)
    return series.map(one)


def change_pct(x):
    """For comparison tables: '+71%', '-10%', or 'nuevo' when there was nothing to compare with."""
    return "nuevo" if _missing(x) else f"{x * 100:+.0f}%"


def month(ym):
    """'2026-09' -> 'sep 2026'."""
    y, m = str(ym)[:7].split("-")
    return f"{MONTHS[int(m) - 1]} {y}"


def day(d):
    """date(2026, 10, 19) or '2026-10-19' -> '19 oct 2026'."""
    d = d if isinstance(d, date) else date.fromisoformat(str(d)[:10])
    return f"{d.day} {MONTHS[d.month - 1]} {d.year}"


def whole(df, cols):
    """A copy with money columns rounded to whole pesos (for the table formats above)."""
    out = df.copy()
    for c in cols:
        out[c] = out[c].round(0).astype("Int64")
    return out
