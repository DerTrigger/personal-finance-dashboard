"""
check_deposits.py
What it does: recalculates each fixed-term deposit's interest from its terms and compares it with what the platform showed.
Inputs: investment-snapshots.csv in FinanceData (optional --as-of date; default: latest snapshot).
Output: report on screen, one line per deposit, plus upcoming payouts. Writes nothing.
Exit code 1 if any deposit is off by more than 1 peso.
Rules: monthly-payout deposits (FINSUS) earn on the actual days start->end and show gross interest;
at-maturity deposits (Kubo) earn on the term days and show interest net of ISR.
Used by: workflows/monthly-close.md
"""
import argparse
import sys
from datetime import date
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.lib import interest as it  # noqa: E402
from app.lib.config import data_path, load_settings  # noqa: E402

TOLERANCE = 1.00


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--as-of", help="snapshot date YYYY-MM-DD (default: latest)")
    args = ap.parse_args()

    s = load_settings()
    isr = s["tax"]["isr_rate"]
    df = pd.read_csv(data_path(s, "snapshots_csv"), encoding="utf-8-sig")
    deps = df[df["item_type"] == "deposit"]
    as_of = args.as_of or deps["as_of"].max()
    deps = deps[deps["as_of"] == as_of]
    if deps.empty:
        print(f"No deposits found for {as_of}.")
        return 1

    print(f"Deposits as of {as_of} (tolerance {TOLERANCE:.2f})\n")
    print(f"{'Platform':<16}{'Deposit':<28}{'Basis':<7}{'Shown':>12}{'Calculated':>12}{'Diff':>8}")
    bad = 0
    for r in deps.itertuples():
        exp = it.deposit_interest(r, isr)
        diff = round(exp - r.interest_total, 2)
        flag = "" if abs(diff) <= TOLERANCE else "  <-- CHECK"
        bad += bool(flag)
        print(f"{r.platform:<16}{r.name[:27]:<28}{r.interest_basis:<7}{r.interest_total:>12,.2f}{exp:>12,.2f}{diff:>8.2f}{flag}")

    print("\nNext 60 days:")
    for e in it.upcoming_events(deps.itertuples(), date.fromisoformat(as_of), isr, days=60):
        print(f"  {e['date']}  {e['platform']:<16}{e['name'][:27]:<28}{e['amount']:>12,.2f}  {e['what']}")

    print(f"\n{len(deps) - bad} of {len(deps)} deposits match.")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
