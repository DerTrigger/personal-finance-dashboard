"""
ingest_moneymanager.py
What it does: finds every Money Manager export in the data folder, combines them by the dates each covers, and prints a check report.
Inputs: optional list of export paths (default: search FinanceData, skipping "_" scratch folders).
Output: report on screen (files and their dates, replaced and vanished rows, totals per year, possible duplicates, unmatched transfers). Writes nothing.
Exit code 1 if an export can't be read, or with --strict if duplicates or unmatched transfers exist.
Used by: workflows/monthly-close.md, tools/build_db.py (via app.lib.moneymanager)
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.lib import moneymanager as mm  # noqa: E402
from app.lib.config import find_exports, load_settings  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("paths", nargs="*", help="export files (default: all under FinanceData)")
    ap.add_argument("--strict", action="store_true", help="fail if duplicates or unmatched transfers exist")
    args = ap.parse_args()

    paths = args.paths or find_exports(load_settings()["paths"]["data_dir"])
    if not paths:
        print("No Money Manager exports found.")
        return 1
    try:
        df, report = mm.load_exports(paths)
    except ValueError as e:
        print(f"Could not read an export: {e}")
        return 1

    print("Files (newest first; each counts for its dates, a newer one wins where they overlap):")
    for f in report["files"]:
        how = "file name" if f["from_name"] else "its transactions"
        print(f"  {f['name']}: {f['start']} to {f['end']} (dates from {how}), {f['rows_used']} of "
              f"{f['rows_in_file']} rows used")
    for w in report["warnings"]:
        print(f"WARNING: {w}")
    print(f"Rows replaced by a newer export: {report['replaced']}")
    vanished = report["vanished"]
    print(f"Rows that vanished from a newer export: {len(vanished)}")
    for _, r in vanished.iterrows():
        print(f"  {r.date} {r.account} {r.type} {r.amount:,.2f} {r.category} {r.note}  (was in {r.source_file})")
    print(f"\n{'Year':<6}{'Rows':>6}{'Expenses':>16}{'Income':>16}{'Transfers net':>15}")
    for year, s in mm.summarize(df).items():
        print(f"{year:<6}{s['rows']:>6}{s['expenses']:>16,.2f}{s['income']:>16,.2f}{s['transfers_net']:>15,.2f}")

    dups, unmatched = mm.find_duplicates(df), mm.unmatched_transfers(df)
    print(f"\nPossible duplicates (same date, amount, account and category): {len(dups)}")
    for _, r in dups.iterrows():
        print(f"  {r.date} {r.account} {r.type} {r.amount:,.2f} {r.category} {r.note}")
    print(f"Transfers missing their other half: {len(unmatched)}")
    for _, r in unmatched.iterrows():
        print(f"  {r.date} {r.account} -> {r.counterpart} {r.type} {r.amount:,.2f}")

    if args.strict and (len(dups) or len(unmatched)):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
