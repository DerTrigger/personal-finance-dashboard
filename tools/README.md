# Tools Index
*Every script in this folder, what it does, and which workflow uses it. Check here before writing a new tool.*

| Tool | What it does | Inputs | Output | Used by |
|------|-------------|--------|--------|---------|
| `build_db.py` | Rebuilds `finance.db` from scratch from exports + snapshots CSV + adjustments CSV (exports found under FinanceData, skipping "_" scratch folders) | settings.toml paths | `FinanceData\finance.db` (replaced only on success); summary on screen | monthly-close |
| `check_deposits.py` | Recalculates every fixed-term deposit's interest and compares it with the platform; lists payouts in the next 60 days | `investment-snapshots.csv` (optional `--as-of`) | Report on screen; writes nothing | monthly-close |
| `validate_snapshot.py` | Checks a month's screenshot readings (platforms present, parts add to totals, gain %, deposit interest, changes vs. last month) and prints the confirm table | Pending CSV (default: newest `FinanceData\YYYY\YYYY-MM\pending-snapshot.csv`) | Confirm table, errors, warnings on screen; writes nothing | monthly-close |
| `append_snapshots.py` | Saves a confirmed month to `investment-snapshots.csv` and rebuilds the database. Refuses on any error or without `--confirmed` | Pending CSV; `--confirmed` after Memo's yes | Rows appended (old file kept as `.bak`); `finance.db` rebuilt | monthly-close |
| `reconcile.py` | Splits each platform's change between the last two snapshots into returns and contributions; flags gaps vs. Money Manager transfers. `--book PLATFORM` saves an approved gap | `investment-snapshots.csv`, exports (optional `--start`/`--end`) | Report on screen; with `--book`, one row in `FinanceData\adjustments.csv` (duplicates refused) | monthly-close |
| `collect_inbox.py` | Moves the month's files from the Drive "Finance Inbox" into `FinanceData\YYYY\YYYY-MM\`. Never overwrites | `--month` (default: last month); `--move` to act (default: dry run) | Files moved; list on screen | monthly-close |
| `convert_heic.py` | Saves a readable PNG copy of every screenshot (iPhone HEIC, even when named .png); originals untouched | `--month` (default: last month) | PNGs in the month's `converted\` folder | monthly-close |
| `cleanup_screenshots.py` | Deletes a month's screenshots once its readings are saved. Images only | `--month`; `--yes` after Memo approves (default: dry run) | Image files deleted from the month folder | monthly-close |
| `draft_pending.py` | Drafts a month's `pending-snapshot.csv` from the last saved month: same items and names, deposit terms and manual assets carried over, numbers to read left blank | `--month` (default last month), `--as-of`, `--from-date`, `--out` | The draft CSV in the month folder (never overwrites) | read-finance-screenshots skill |
| `compare_readings.py` | Scores the first reading against the confirmed one, per platform (fields corrected, items missed/extra) | `first-pass.csv`, confirmed pending CSV, `--month` | Summary on screen; counts appended to `FinanceData\reading-accuracy.csv` (no amounts) | read-finance-screenshots skill |
| `month_summary.py` | The end-of-close summary: net worth and why it changed (if the month has a snapshot), the month's income/spending/net income, cards still to pay | `--month` (default last month) | Summary on screen; writes nothing | monthly-close (step 8) |
| `run_evals.py` | Runs every eval check on the real files (Money Manager vs. Excel, rebuild, opening net worth, dashboard card, deposit math, filters vs. SQL, 3-month replay with planted errors) | settings.toml paths (reads only) | Report without amounts in `Outputs/` (in `FinanceData\evals\` when pointed at a sandbox); full report in `FinanceData\evals\`; its scratch folder in `FinanceData\_replay\` is removed when it ends (`--keep` to keep it). Exit 1 on any failure | step 6; re-run after any change to the numbers |
| `ingest_moneymanager.py` | Checks Money Manager exports: combines them by the dates each covers (newer wins), lists replaced and vanished rows, totals, possible duplicates, unmatched transfers | Export paths (default: all under FinanceData) | Report on screen; writes nothing | monthly-close, build_db |

Run every tool with the project environment and UTF-8 output:
`PYTHONIOENCODING=utf-8 C:\Users\<you>\.venvs\finance-dashboard\Scripts\python tools\<tool>.py`

Shared logic lives in `app/lib/` (tested in `tests/`); tools are thin wrappers around it.

---

## Conventions

- One job per tool. If the description needs an "and", split it.
- Name: `verb_noun.py` (e.g., `fetch_leads.py`, `send_report.py`).
- Read secrets from `.env` with `python-dotenv`; never hard-code them.
- Write scratch files to `.tmp/`, final files to `Outputs/`.
- On failure, print a plain-language error and exit with a non-zero code, so Claude knows it failed.
- Anything that sends, posts, or spends should have a `--dry-run` option that shows what it would do without doing it.

## Header to Start Every Tool With

```python
"""
fetch_leads.py
What it does: [one sentence]
Inputs: [arguments, files, .env variables]
Output: [what it writes and where]
Used by: workflows/[name].md
"""
```
