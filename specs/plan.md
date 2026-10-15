# Personal Finance Dashboard: Technical Plan
*Made in plan mode. Status: Approved by Memo on 2026-09-28*

## Stack
| Part | Choice | Why (one line) |
|------|--------|----------------|
| Language | Python 3.14 | One language for scripts and dashboard; already installed |
| Front end | Streamlit 1.64 + Plotly | Local web page with filters and interactive charts, no web coding |
| Back end | Python scripts in `tools/`, logic in `app/lib/` | WAT: one job per script |
| Data handling | pandas + openpyxl | Excel reading and table math |
| Data storage | SQLite file `FinanceData\finance.db` | One file, nothing to run |
| Tests | pytest | Standard test runner |
| Screenshots | Pillow + pillow-heif | Converts iPhone HEIC |
| Version history | git, local only | Small checkpoints; no online copy |
| Hosting | None. `localhost` only, usage stats off | Data never leaves the laptop |

Python environment: `C:\Users\<you>\.venvs\finance-dashboard` (outside OneDrive).

## Folder Structure
```
Projects/Personal Finance Dashboard/   (OneDrive: code and docs only)
├── app/
│   ├── dashboard.py            ← Streamlit entry (Overview)
│   ├── pages/                  ← 2_Expenses.py … 7_Data_check.py
│   └── lib/                    ← db.py, metrics.py, interest.py, filters.py, config.py
├── tools/                      ← one-job scripts, indexed in tools/README.md
├── tests/                      ← pytest; fixtures/ hold fake data only
├── config/settings.toml        ← paths, ISR rate, Nu Cajitas, account types, category fixes
├── requirements.txt
└── workflows/monthly-close.md
```

## Data
All real data lives in `C:\Users\<you>\FinanceData\` (not synced). Only Memo's laptop can see it.

`finance.db` is **derived**: rebuilt from scratch every run from three sources, so re-running can never duplicate anything:
1. Money Manager exports (latest export per year wins; each export repeats the year so far).
2. `investment-snapshots.csv` (confirmed screenshot readings).
3. `adjustments.csv` (untracked adjustments Memo approved).

Identical rows inside a source (same timestamp, account, amount, type, note) are flagged for Memo, never silently dropped.

Tables: `transactions`, `snapshot_items`, `adjustments`, `accounts`, plus views for monthly net worth, monthly income/expense, and the deposit calendar.

`.gitignore` blocks `*.db`, `*.csv`, `*.xlsx`, `*.json` under data paths, and images, so real data can't be committed.

## Outside Services and Keys
None. No APIs, no keys. Google Drive for desktop syncs the inbox folder; the code only reads `G:\Mi unidad\Finance Inbox`.

## Testing Approach
Test first on all money logic: Money Manager import, interest math (FINSUS gross, Kubo net of ISR, 360-day basis), net worth and the "why it changed" split, and filter totals. Tests use fake fixture data only. Real-file checks compare against known totals from the Excel.
