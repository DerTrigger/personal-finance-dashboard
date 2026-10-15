r"""
convert_heic.py
What it does: saves a readable PNG copy of every screenshot in a month folder (iPhone screenshots are
HEIC even when named .png). Originals are not changed.
Inputs: --month YYYY-MM (default: last month).
Output: PNG copies in FinanceData\YYYY\YYYY-MM\converted\; list on screen. Existing copies are skipped.
Exit code 1 if the folder is missing or any image can't be opened.
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
    args = ap.parse_args()

    s = load_settings()
    try:
        folder = ib.month_folder(s["paths"]["data_dir"], args.month)
    except ValueError as e:
        print(e)
        return 1
    if not folder.is_dir():
        print(f"No folder for {args.month}: {folder}. Run collect_inbox.py first.")
        return 1

    done, failed = ib.convert_images(folder)
    print(f"Converted {len(done)} image(s) into {folder / ib.CONVERTED}")
    for p in done:
        print(f"  {p.name}")
    if failed:
        print("\nCould not open (re-upload these):")
        for p in failed:
            print(f"  {p.name}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
