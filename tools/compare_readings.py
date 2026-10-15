r"""
compare_readings.py
What it does: scores the first reading of a month's screenshots against what Memo confirmed, per platform, and logs it.
Inputs: FIRST (first-pass.csv) and FINAL (the confirmed pending-snapshot.csv); --month YYYY-MM for the log;
  --log path (default: FinanceData\reading-accuracy.csv); --no-log to only print.
Output: summary on screen; one row per platform appended to the log (counts only, no amounts).
Used by: the read-finance-screenshots skill (spec item 6: first-pass accuracy logged)
"""
import argparse
import csv
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.lib import snapshots as sn  # noqa: E402
from app.lib.config import load_settings  # noqa: E402

LOG_COLS = ["month", "platform", "items", "fields", "corrected", "missing", "extra", "logged_on"]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("first")
    ap.add_argument("final")
    ap.add_argument("--month", required=True, help="YYYY-MM, for the log")
    ap.add_argument("--log", help="log file (default: FinanceData\\reading-accuracy.csv)")
    ap.add_argument("--no-log", action="store_true")
    args = ap.parse_args()

    summary = sn.compare(sn.read_csv(args.first).replace("", None), sn.read_csv(args.final).replace("", None))
    print(f"{'Platform':<18}{'Items':>6}{'Fields':>8}{'Corrected':>11}{'Missed':>8}{'Extra':>7}")
    for r in summary.itertuples():
        print(f"{r.platform:<18}{r.items:>6}{r.fields:>8}{r.corrected:>11}{r.missing:>8}{r.extra:>7}")
    fields, fixed = int(summary["fields"].sum()), int(summary["corrected"].sum())
    misses = int(summary["missing"].sum() + summary["extra"].sum())
    rate = (fields - fixed) / fields if fields else 0.0
    print(f"\nFirst pass: {fields - fixed} of {fields} fields right ({rate:.1%}); {misses} items missed or extra.")

    if not args.no_log:
        log = Path(args.log) if args.log else Path(load_settings()["paths"]["data_dir"]) / "reading-accuracy.csv"
        new = not log.exists()
        with open(log, "a", encoding="utf-8-sig" if new else "utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=LOG_COLS, lineterminator="\r\n")
            if new:
                w.writeheader()
            for r in summary.to_dict("records"):
                w.writerow({**r, "month": args.month, "logged_on": date.today().isoformat()})
        print(f"Logged to {log}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
