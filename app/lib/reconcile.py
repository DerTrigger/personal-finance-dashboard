"""
Explain each platform's change between two snapshots: change = returns + contributions.

Returns come from each platform's own numbers (settings [platforms."Name"] returns); contributions are the rest.
Where a platform has a Money Manager account, the derived contributions are compared with the transfers
logged there. A gap above [checks] reconcile_gap_mxn is flagged for Memo; approved gaps are booked once
in adjustments.csv. The same split feeds the dashboard's "Why it changed" card.
"""
import csv
from datetime import date
from pathlib import Path

import pandas as pd

from app.lib import config as cfg
from app.lib import interest as it
from app.lib.db import ADJ_COLS
from app.lib.snapshots import _clean, _main, platform_totals

COLUMNS = ["platform", "start", "end", "method", "estimated", "change", "returns", "contributions",
           "logged_transfers", "booked", "gap", "flagged"]


def reconcile(history, start, end, transactions, settings, adjustments=None):
    """One row per platform for the window start < date <= end (snapshot dates, YYYY-MM-DD).
    `adjustments` (adjustments.csv): gaps Memo already approved count as logged, so a booked gap is settled."""
    h = _clean(history)
    main = _main(h)
    prev, curr = main[main["as_of"] == start], main[main["as_of"] == end]
    before, now = platform_totals(prev), platform_totals(curr)
    isr = settings["tax"]["isr_rate"]
    threshold = settings["checks"]["reconcile_gap_mxn"]

    rows = []
    for platform in sorted(set(before) | set(now)):
        change = round(now.get(platform, 0.0) - before.get(platform, 0.0), 2)
        method = cfg.returns_method(settings, platform)
        p0, p1 = prev[prev["platform"] == platform], curr[curr["platform"] == platform]
        account = cfg.mm_account(settings, platform)
        window = (start, end)

        if method == "gain_change":
            returns = _gains(p1) - _gains(p0)
        elif method == "interest":
            returns = _interest(p0, p1, start, end, isr)
        elif method == "statement":
            s0, s1 = _statement(h, platform, start), _statement(h, platform, end)
            if s0 is not None and s1 is not None and s0.as_of != s1.as_of:
                returns = change - (s1.principal - s0.principal)
                window = (s0.as_of, s1.as_of)  # contributions come from the statements' own period
            else:
                method = "estimated"  # no new statement this month
        elif method == "revaluation":
            returns = change
        else:
            method = "estimated"

        estimated = method == "estimated"
        logged = round(_logged(transactions, account, *window), 2) if account else None
        if estimated:
            returns = change - (logged or 0.0)
        returns = round(returns, 2)
        contributions = round(change - returns, 2)
        gap, flagged, booked = None, False, None
        if account and not estimated and method != "revaluation":
            booked = round(_booked(adjustments, account, start, end), 2)
            gap = round(contributions - logged - booked, 2)
            flagged = abs(gap) > threshold
        rows.append({"platform": platform, "start": start, "end": end, "method": method, "estimated": estimated,
                     "change": change, "returns": returns, "contributions": contributions,
                     "logged_transfers": logged, "booked": booked, "gap": gap, "flagged": flagged})
    return pd.DataFrame(rows, columns=COLUMNS)


def _gains(df):
    return float(df.loc[df["item_type"].isin(["holding", "cajita"]), "gain"].sum())


def _interest(p0, p1, start, end, isr):
    """After-tax interest paid by deposits in the window, plus interest on last month's on-demand balances."""
    d0, d1 = date.fromisoformat(start), date.fromisoformat(end)
    deposits = pd.concat([p0, p1])
    deposits = deposits[deposits["item_type"] == "deposit"].drop_duplicates(["name", "start_date"])
    total = 0.0
    for r in deposits.itertuples():
        s, e = date.fromisoformat(str(r.start_date)), date.fromisoformat(str(r.end_date))
        if r.payout == "monthly":
            total += sum(p["net"] for p in it.monthly_schedule(r.principal, r.annual_rate, s, e, isr)
                         if d0 < p["date"] <= d1)
        elif d0 < e <= d1:
            total += it.net_interest(r.principal, r.annual_rate, int(r.term_days), isr)
    days = (d1 - d0).days
    for r in p0[(p0["item_type"] == "on_demand") & p0["annual_rate"].notna()].itertuples():
        total += it.net_interest(r.value, r.annual_rate, days, isr)
    return total


def _statement(h, platform, when):
    s = h[(h["platform"] == platform) & (h["item_type"] == "statement") & (h["as_of"] <= when)]
    if s.empty:
        return None
    return next(s.sort_values("as_of").tail(1).itertuples())


def _booked(adjustments, account, start, end):
    """Approved adjustments for this account dated inside the window (booked on the window's end date)."""
    if adjustments is None or len(adjustments) == 0:
        return 0.0
    a = adjustments[(adjustments["account"] == account) & (adjustments["date"].astype(str) > start)
                    & (adjustments["date"].astype(str) <= end)]
    return float(a["amount"].sum())


def _logged(transactions, account, start, end):
    t = transactions[(transactions["account"] == account) & (transactions["date"] > start)
                     & (transactions["date"] <= end)]
    amounts = t.groupby("type")["amount"].sum()
    return float(amounts.get("transfer_in", 0.0) - amounts.get("transfer_out", 0.0))


def book_adjustment(path, row, settings, approved_on):
    """Append one approved gap to adjustments.csv. Refuses unflagged rows and duplicates (date + account + amount)."""
    if not row["flagged"]:
        raise ValueError(f"{row['platform']} no tiene una diferencia marcada para registrar.")
    account = cfg.mm_account(settings, row["platform"]) or row["platform"]
    gap = round(float(row["gap"]), 2)
    new = {
        "date": row["end"],
        "account": account,
        "amount": gap,
        "reason": (f"{'Depósito' if gap > 0 else 'Retiro'} no registrado entre {row['start']} y {row['end']}: "
                   f"{row['platform']} se movió {row['contributions']:,.2f} además de sus rendimientos; "
                   f"Money Manager registró {row['logged_transfers']:,.2f}."),
        "approved_on": approved_on,
    }
    path = Path(path)
    if path.exists():
        existing = pd.read_csv(path, encoding="utf-8-sig", dtype={"date": str})
        same = existing[(existing["date"] == new["date"]) & (existing["account"] == account)
                        & ((existing["amount"] - gap).abs() < 0.005)]
        if not same.empty:
            raise ValueError(f"Este ajuste ya está registrado: {account} {gap:,.2f} el {new['date']}.")
    is_new = not path.exists()
    with open(path, "a", encoding="utf-8-sig" if is_new else "utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=ADJ_COLS, lineterminator="\r\n")
        if is_new:
            w.writeheader()
        w.writerow(new)
    return new
