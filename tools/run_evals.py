"""
run_evals.py
What it does: runs every eval check on the real files (spec, "Done Means") and writes the eval report.
Inputs: settings.toml paths (Money Manager exports, investment-snapshots.csv, finance.db). Reads only.
Output: Outputs/Personal Finance Dashboard - Eval Report.md (no amounts; syncs to OneDrive) and
  FinanceData\\evals\\eval-YYYY-MM-DD-HHMM.md (with amounts). Scratch builds and the replay go in a temporary
  FinanceData\\_replay\\ folder, removed when the run ends (it holds only the run's own simulation files);
  --keep keeps it for debugging.
Exit code 1 if any check fails.
Used by: step 6 (testing phase); re-run after any change to the numbers.
"""
import argparse
import os
import shutil
import sys
import tempfile
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.lib import evals  # noqa: E402
from app.lib.config import PROJECT_DIR, load_settings  # noqa: E402

PUBLIC_REPORT = PROJECT_DIR / "Outputs" / "Personal Finance Dashboard - Eval Report.md"


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--keep", action="store_true", help="keep the scratch folder (for debugging)")
    args = ap.parse_args()

    s = load_settings()
    stamp = datetime.now().strftime("%Y-%m-%d-%H%M")
    data_dir = Path(s["paths"]["data_dir"])
    (data_dir / "_replay").mkdir(exist_ok=True)
    workdir = Path(tempfile.mkdtemp(prefix=f"{stamp}-", dir=data_dir / "_replay"))

    print("Running evals (about a minute)...\n")
    try:
        checks = evals.run_all(s, workdir)
    finally:
        # The scratch folder holds only this run's own simulation files: remove it unless asked to keep it
        if not args.keep:
            shutil.rmtree(workdir, ignore_errors=True)
            if not any((data_dir / "_replay").iterdir()):
                (data_dir / "_replay").rmdir()
    for c in checks:
        print(f"{'PASS' if c['passed'] else 'FAIL'}  {c['item']}. {c['name']}: {c['public']}")

    when = datetime.now().strftime("%Y-%m-%d %H:%M")
    private = data_dir / "evals" / f"eval-{stamp}.md"
    private.parent.mkdir(exist_ok=True)
    private.write_text(evals.report(checks, with_amounts=True, when=when), encoding="utf-8")
    # A sandbox run (FINANCE_DATA_DIR set) keeps its report in the sandbox, never over the real one in Outputs
    public = private.with_name(f"eval-{stamp}-no-amounts.md") if os.environ.get("FINANCE_DATA_DIR") else PUBLIC_REPORT
    public.write_text(evals.report(checks, with_amounts=False, when=when), encoding="utf-8")

    passed = sum(c["passed"] for c in checks)
    print(f"\n{passed} of {len(checks)} checks pass.")
    print(f"Report (no amounts): {public}")
    print(f"Full report:         {private}")
    print(f"Scratch folder:      {workdir}  (kept, --keep)" if args.keep else "Scratch folder removed.")
    return 0 if passed == len(checks) else 1


if __name__ == "__main__":
    sys.exit(main())
