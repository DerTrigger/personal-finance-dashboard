r"""
month_summary.py
What it does: prints the end-of-close summary for a month: net worth and why it changed (if the month has a
  snapshot), the month's income, spending and net income, and card balances still owed.
Inputs: --month YYYY-MM (default: last month); reads FinanceData\finance.db.
Output: summary on screen (for Memo; nothing is written).
Used by: workflows/monthly-close.md (step 8)
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.lib import db  # noqa: E402
from app.lib import inbox as ib  # noqa: E402
from app.lib import metrics as mx  # noqa: E402
from app.lib.config import data_path, load_settings  # noqa: E402


def money(x):
    return f"-${abs(x):,.2f}" if x < 0 else f"${x:,.2f}"


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--month", default=ib.default_month(), help="YYYY-MM (default: last month)")
    args = ap.parse_args()

    s = load_settings()
    path = data_path(s, "database")
    snaps, tx = db.read_table(path, "snapshot_items"), db.read_table(path, "transactions")
    r = mx.month_summary(snaps, tx, s, args.month)

    print(f"Month {args.month}")
    if r["why"]:
        w = r["why"]
        print(f"  Net worth {money(r['net_worth'])} on {r['as_of']}: {money(r['change'])} vs. {r['previous']}")
        print(f"    money put in {money(w['put_in'])} · returns {money(w['returns'])} · "
              f"estimated returns {money(w['estimated_returns'])} · revaluation {money(w['revaluation'])}")
    else:
        print(f"  Net worth {money(r['net_worth'])} (latest snapshot, {r['as_of']}; no new snapshot this month)")
    rate = f"{r['savings_rate']:.1%}" if r["savings_rate"] == r["savings_rate"] and r["savings_rate"] is not None \
        else "–"
    print(f"  Income {money(r['income'])} · spending {money(r['expenses'])} · net income {money(r['net_income'])} "
          f"(savings rate {rate})")
    c = r["card_pending"]
    print(f"  Cards still to pay: {money(c['total'])} in {c['charges']} charges "
          f"({money(c['set_aside'])} set aside in Nu, {money(c['not_set_aside'])} not set aside)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
