r"""
append_snapshots.py
What it does: saves a confirmed month of screenshot readings to investment-snapshots.csv, then rebuilds the database.
Inputs: a pending snapshot CSV (default: the newest month's); --confirmed, added only after Memo says yes
        to the confirm table.
Output: rows appended to FinanceData\investment-snapshots.csv (old file kept as .bak); finance.db rebuilt.
Exit code 1 if the month has errors, is already saved, or --confirmed is missing. Nothing changes in that case.
Used by: workflows/monthly-close.md
"""
import argparse
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.lib import db  # noqa: E402
from app.lib import snapshots as sn  # noqa: E402
from app.lib.config import data_path, find_exports, find_pending, load_settings  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("pending", nargs="?", help="pending snapshot CSV (default: newest month's)")
    ap.add_argument("--confirmed", action="store_true", help="Memo confirmed the readings")
    args = ap.parse_args()

    s = load_settings()
    pending_path = Path(args.pending) if args.pending else find_pending(s["paths"]["data_dir"])
    if not pending_path or not pending_path.exists():
        print("No pending snapshot found.")
        return 1
    if not args.confirmed:
        print("Not saved: run validate_snapshot.py, show Memo the confirm table, and add --confirmed after his yes.")
        return 1

    csv_path = data_path(s, "snapshots_csv")
    try:
        added = sn.append_snapshot(pending_path, csv_path, s, confirmed_on=date.today().isoformat())
    except ValueError as e:
        print(e)
        return 1
    print(f"Saved {added} rows from {pending_path.name} to {csv_path.name} (previous version: {csv_path.name}.bak).")

    try:
        report = db.build_database(data_path(s, "database"), find_exports(s["paths"]["data_dir"]), csv_path,
                                   data_path(s, "adjustments_csv"), s)
    except PermissionError:
        print("Readings saved, but the database is in use. Close the dashboard and run build_db.py.")
        return 1
    print(f"Database rebuilt: {report['snapshot_items']} snapshot items, {report['transactions']} transactions.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
