r"""
cleanup_screenshots.py
What it does: deletes a month's screenshots (originals and converted copies) once its readings are saved
in investment-snapshots.csv. Only image files are deleted; the export and pending snapshot stay.
Inputs: --month YYYY-MM (default: last month); --yes to delete, added only after Memo says yes
        (without it, only lists what would be deleted).
Output: image files deleted from FinanceData\YYYY\YYYY-MM\; list on screen.
Exit code 1 if the month's readings aren't saved yet (nothing is deleted).
Used by: workflows/monthly-close.md
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.lib import inbox as ib  # noqa: E402
from app.lib import snapshots as sn  # noqa: E402
from app.lib.config import data_path, load_settings  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--month", default=ib.default_month(), help="YYYY-MM (default: last month)")
    ap.add_argument("--yes", action="store_true", help="delete (Memo approved)")
    args = ap.parse_args()

    s = load_settings()
    history = sn.read_csv(data_path(s, "snapshots_csv"))
    try:
        folder = ib.month_folder(s["paths"]["data_dir"], args.month)
        files = ib.cleanup(folder, history) if args.yes else ib.plan_cleanup(folder, history)
    except ValueError as e:
        print(e)
        return 1

    verb = "Deleted" if args.yes else "Would delete"
    print(f"{verb} {len(files)} screenshot(s) from {folder}")
    for f in files:
        print(f"  {f.relative_to(folder)}")
    if not args.yes and files:
        print("\nDry run. Add --yes after Memo approves.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
