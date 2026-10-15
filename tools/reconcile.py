r"""
reconcile.py
What it does: splits each platform's change between the last two snapshots into returns and contributions,
and flags where the contributions don't match the transfers logged in Money Manager.
Inputs: investment-snapshots.csv and the Money Manager exports in FinanceData (optional --start/--end dates);
        --book PLATFORM to save that platform's flagged gap to adjustments.csv, only after Memo approves it.
Output: report on screen. With --book: one row appended to FinanceData\adjustments.csv.
Exit code 1 if fewer than two snapshots exist, or --book is refused (no flagged gap, or already booked).
Used by: workflows/monthly-close.md
"""
import argparse
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.lib import moneymanager as mm  # noqa: E402
from app.lib import reconcile as rc  # noqa: E402
from app.lib import snapshots as sn  # noqa: E402
from app.lib.config import data_path, find_exports, load_settings  # noqa: E402
from app.lib.db import read_adjustments  # noqa: E402


def money(x):
    return "" if x is None or x != x else f"{x:,.2f}"


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--start", help="earlier snapshot date (default: second latest)")
    ap.add_argument("--end", help="later snapshot date (default: latest)")
    ap.add_argument("--book", metavar="PLATFORM", help="book this platform's flagged gap (after Memo approves)")
    args = ap.parse_args()

    s = load_settings()
    history = sn.read_csv(data_path(s, "snapshots_csv")).replace("", None)
    dates = sn.snapshot_dates(history)
    end = args.end or (dates[-1] if dates else None)
    earlier = [d for d in dates if end and d < end]
    start = args.start or (earlier[-1] if earlier else None)
    if not start or not end:
        print(f"Need two snapshots to reconcile; found {len(dates)} ({', '.join(dates)}).")
        return 1

    transactions, _ = mm.load_exports(find_exports(s["paths"]["data_dir"]))
    booked = read_adjustments(data_path(s, "adjustments_csv"))  # approved gaps count as settled
    result = rc.reconcile(history, start, end, transactions, s, adjustments=booked)

    if args.book:
        match = result[result["platform"] == args.book]
        if match.empty:
            print(f"No platform called '{args.book}'.")
            return 1
        try:
            new = rc.book_adjustment(data_path(s, "adjustments_csv"), match.iloc[0], s,
                                     approved_on=date.today().isoformat())
        except ValueError as e:
            print(e)
            return 1
        print(f"Booked in adjustments.csv: {new['account']} {new['amount']:,.2f} on {new['date']}.")
        print("Run build_db.py to refresh the dashboard; the gap then reads as settled.")
        return 0

    print(f"Why each platform changed, {start} to {end}\n")
    print(f"{'Platform':<18}{'Change':>14}{'Returns':>14}{'Contributions':>15}{'Logged':>14}{'Gap':>12}  Note")
    for r in result.itertuples():
        note = "CHECK: gap" if r.flagged else ("estimated" if r.estimated else
                                                ("revaluation" if r.method == "revaluation" else ""))
        print(f"{r.platform:<18}{money(r.change):>14}{money(r.returns):>14}{money(r.contributions):>15}"
              f"{money(r.logged_transfers):>14}{money(r.gap):>12}  {note}")
    print(f"{'Total':<18}{money(result['change'].sum()):>14}{money(result['returns'].sum()):>14}"
          f"{money(result['contributions'].sum()):>15}")

    flagged = result[result["flagged"]]
    print(f"\n{len(flagged)} gap(s) to review.")
    for r in flagged.itertuples():
        print(f"  - {r.platform}: contributions {money(r.contributions)} vs. logged {money(r.logged_transfers)}. "
              f"If Memo approves: reconcile.py --book \"{r.platform}\"")
    return 0


if __name__ == "__main__":
    sys.exit(main())
