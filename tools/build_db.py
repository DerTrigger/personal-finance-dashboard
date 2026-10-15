"""
build_db.py
What it does: rebuilds FinanceData\finance.db from scratch from the Money Manager exports, investment-snapshots.csv, and adjustments.csv.
Inputs: settings.toml paths (no arguments needed).
Output: FinanceData\finance.db (replaced only if the build succeeds) and a summary on screen.
Exit code 1 if a source file can't be read or the database is in use (close the dashboard and retry).
Used by: workflows/monthly-close.md
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.lib import db  # noqa: E402
from app.lib.config import data_path, find_exports, load_settings  # noqa: E402


def main():
    s = load_settings()
    db_file = data_path(s, "database")
    exports = find_exports(s["paths"]["data_dir"])
    if not exports:
        print("No Money Manager exports found.")
        return 1
    try:
        report = db.build_database(db_file, exports, data_path(s, "snapshots_csv"),
                                   data_path(s, "adjustments_csv"), s)
    except ValueError as e:
        print(f"Build stopped, old database kept: {e}")
        return 1
    except PermissionError:
        print("The database is in use. Close the dashboard and run this again. Old database kept.")
        return 1

    print(f"Built {db_file}")
    print(f"  Transactions: {report['transactions']}")
    for f in report["files"]:
        print(f"    {f['name']}: {f['start']} to {f['end']}, {f['rows_used']} of {f['rows_in_file']} rows used")
    if report["replaced"]:
        print(f"  {report['replaced']} rows replaced by a newer export of the same dates")
    if len(report["vanished"]):
        print(f"  WARNING: {len(report['vanished'])} rows vanished from a newer export (see Revisión de datos)")
    for w in report["warnings"]:
        print(f"  WARNING: {w}")
    print(f"  Snapshot items: {report['snapshot_items']}")
    print(f"  Adjustments: {report['adjustments']}")
    print("\nNet worth by snapshot date:")
    for as_of, nw in db.query(db_file, "SELECT as_of, net_worth FROM v_net_worth ORDER BY as_of"):
        print(f"  {as_of}  {nw:,.2f}")
    print(f"\nFingerprint: {db.fingerprint(db_file)[:16]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
