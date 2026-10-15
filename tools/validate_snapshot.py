r"""
validate_snapshot.py
What it does: checks a month's screenshot readings and prints the confirm table for Memo.
Inputs: a pending snapshot CSV (default: the newest FinanceData\YYYY\YYYY-MM\pending-snapshot.csv);
        investment-snapshots.csv for last month's numbers.
Output: confirm table, errors, and warnings on screen. Writes nothing.
Exit code 1 if there's any error (the month can't be saved until it's fixed).
Used by: workflows/monthly-close.md
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.lib import snapshots as sn  # noqa: E402
from app.lib.config import data_path, find_pending, load_settings  # noqa: E402


def money(x):
    return "" if x is None or x != x else f"{x:,.2f}"


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("pending", nargs="?", help="pending snapshot CSV (default: newest month's)")
    args = ap.parse_args()

    s = load_settings()
    pending_path = Path(args.pending) if args.pending else find_pending(s["paths"]["data_dir"])
    if not pending_path or not pending_path.exists():
        print("No pending snapshot found.")
        return 1

    pending = sn.read_csv(pending_path).replace("", None)
    history = sn.read_csv(data_path(s, "snapshots_csv")).replace("", None)
    errors, warnings = sn.validate(pending, history, s)
    table = sn.confirm_table(pending, history)

    print(f"Readings in {pending_path}\n")
    print(f"{'Platform':<18}{'Total':>16}{'Last month':>16}{'Change':>14}{'Items':>7}")
    for r in table.itertuples():
        print(f"{r.platform:<18}{money(r.total):>16}{money(r.last_month):>16}{money(r.change):>14}{r.items:>7}")
    print(f"{'Net worth':<18}{money(table['total'].sum()):>16}")

    print(f"\nErrors ({len(errors)}): must be fixed before saving")
    for e in errors:
        print(f"  - {e}")
    print(f"\nWarnings ({len(warnings)}): check, then confirm or fix")
    for w in warnings:
        print(f"  - {w}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
