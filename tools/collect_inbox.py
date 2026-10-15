r"""
collect_inbox.py
What it does: moves this month's files (screenshots, Money Manager export) from the Google Drive
"Finance Inbox" into FinanceData\YYYY\YYYY-MM\.
Inputs: inbox_dir from settings.toml; --month YYYY-MM (default: last month, the one being closed);
        --move to actually move (without it, only shows what would move).
Output: files moved (removed from the Drive inbox); list on screen. Never overwrites a file.
Exit code 1 if the inbox is missing or any file name already exists in the month folder.
Used by: workflows/monthly-close.md
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.lib import inbox as ib  # noqa: E402
from app.lib.config import load_settings  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--month", default=ib.default_month(), help="YYYY-MM (default: last month)")
    ap.add_argument("--move", action="store_true", help="move the files (default: dry run)")
    args = ap.parse_args()

    s = load_settings()
    try:
        dest = ib.month_folder(s["paths"]["data_dir"], args.month)
        moved, conflicts = ib.collect(s["paths"]["inbox_dir"], dest, dry_run=not args.move)
    except (ValueError, FileNotFoundError) as e:
        print(e)
        return 1

    verb = "Moved" if args.move else "Would move"
    print(f"{verb} {len(moved)} file(s) to {dest}")
    for p in moved:
        print(f"  {p.name}")
    if conflicts:
        print(f"\nLeft in the inbox, a file with the same name is already in {dest.name}:")
        for p in conflicts:
            print(f"  {p.name}")
    if not args.move and moved:
        print("\nDry run. Add --move to move them.")
    return 1 if conflicts else 0


if __name__ == "__main__":
    sys.exit(main())
