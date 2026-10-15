r"""
draft_pending.py
What it does: drafts a month's pending-snapshot.csv from the last saved month: same items and names, deposit terms
  and manual assets carried over, the numbers to read from the screenshots left blank.
Inputs: --month YYYY-MM (default: last month); --as-of date (default: the month's last day);
  --from-date (default: the latest saved snapshot before --as-of); --out (default: the month folder).
Output: FinanceData\YYYY\YYYY-MM\pending-snapshot.csv. Refuses to overwrite an existing file.
Used by: the read-finance-screenshots skill
"""
import argparse
import calendar
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.lib import inbox as ib  # noqa: E402
from app.lib import snapshots as sn  # noqa: E402
from app.lib.config import PENDING_NAME, data_path, load_settings  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--month", default=ib.default_month(), help="YYYY-MM (default: last month)")
    ap.add_argument("--as-of", help="snapshot date YYYY-MM-DD (default: the month's last day)")
    ap.add_argument("--from-date", help="saved snapshot to start from (default: the latest before --as-of)")
    ap.add_argument("--out", help="where to write (default: the month folder's pending-snapshot.csv)")
    args = ap.parse_args()

    s = load_settings()
    y, m = map(int, args.month.split("-"))
    as_of = args.as_of or f"{args.month}-{calendar.monthrange(y, m)[1]:02d}"
    out = Path(args.out) if args.out else ib.month_folder(s["paths"]["data_dir"], args.month) / PENDING_NAME
    if out.exists():
        print(f"{out} already exists. Not overwriting it (it may hold readings). Move or rename it first.")
        return 1

    history = sn.read_csv(data_path(s, "snapshots_csv"))
    try:
        rows = sn.draft(history.replace("", None), as_of, args.from_date)
    except ValueError as e:
        print(e)
        return 1
    out.parent.mkdir(parents=True, exist_ok=True)
    rows.reindex(columns=history.columns).to_csv(out, index=False, encoding="utf-8-sig")

    blank = rows["item_type"].isin(list(sn.TO_READ))
    print(f"Draft for {as_of} written to {out}")
    print(f"  {len(rows)} items from {args.from_date or 'the latest saved month'}; {int(blank.sum())} need numbers "
          "from the screenshots.")
    for platform, g in rows[blank].groupby("platform"):
        print(f"  {platform}: {', '.join(g['name'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
