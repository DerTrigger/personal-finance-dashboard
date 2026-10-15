# Plan: Personal Finance Dashboard

## Context

Memo logs every expense, income, and transfer in Money Manager and exports an Excel each month, but he has no single view of his net worth or how his investments are doing across eight platforms. He wants a filterable dashboard (by month, account, category) with separate views for expenses, income, and investments, fed by a monthly routine that is mostly automated. Investments are the hard part because they come in three shapes: fixed-term deposits (some pay monthly, some pay at maturity), variable holdings (GBM stocks/ETFs/FIBRAS, Bitso crypto), and retirement accounts (Afore, PPR). A testing phase has to prove the numbers are right before he relies on them.

### What Memo decided (2026-09-28)

- Scope: his personal money only. Dashboard in English. Everything in MXN.
- Platforms: SOFIPOs (Nu, FINSUS, Kubo Financiero), retirement (Afore Profuturo, PPR Allianz), GBM (stocks), Bitso (crypto). Net worth also includes bank/cash accounts and property/car. No debts tracked for now.
- Investment data arrives as **screenshots** from each app. GBM screenshots show, per holding: number of titles, amount invested, historical gain in % and $.
- Dashboard runs **locally** on his laptop, opens in the browser. Data never leaves the computer.
- Monthly run is **one command**: drop files in an inbox folder, run it, confirm anything flagged.
- Fixed yield: maturity calendar, handling both monthly-payout and pay-at-maturity deposits.
- Variable yield: monthly snapshot per holding, gain vs. money put in, mix by type. No live market prices.
- History: he'll provide real 2025 and 2026 Money Manager exports.
- Skills get designed and built in separate, step-by-step sessions.

## Recommended approach

### Project setup
- Folder: `Projects/Personal Finance Dashboard/` from the templates, add-ons **app-build** (the dashboard) + **automation-wat** (the monthly routine). Register it in the three project lists. Create `CLAUDE.md`, `memory.md`, `brief.md`, `Outputs/`.
- **Where the raw data lives (flag):** the Claude OS folder syncs to OneDrive. I recommend keeping the actual financial data (exports, screenshots, database) in a non-synced folder such as `C:\Users\<you>\FinanceData\`, with only code and docs in the project folder. Memo confirms at setup.

### Stack (Memo approves at Build step B2)
Python, Streamlit (turns a Python script into a local web dashboard with filters), pandas for data, SQLite as the single database file, Plotly for charts. All free, all local.

### Data model (one SQLite file)
- `transactions`: every Money Manager row (date, account, category, subcategory, amount, type: expense / income / transfer), with a stable ID so re-importing never duplicates.
- `accounts`: each account with its type (bank, SOFIPO, retirement, variable, crypto, property) and platform.
- `balance_snapshots`: month-end balance per account.
- `holdings`: per GBM/Bitso position each month (ticker, asset type ETF/FIBRA/stock/crypto, titles, amount invested, value, gain $ and %).
- `fixed_deposits`: each term deposit (platform, principal, annual rate, start date, term, maturity date, payout type monthly or at maturity, status).
- `manual_assets`: property and car at an estimated value, updated when Memo chooses.
- Transfers from bank accounts into investment accounts count as **contributions**, so we can separate "money I put in" from "money it earned."

### Starting balances and gaps in the history
Not every expense, income, or investment is logged in Money Manager. So the history can't be trusted to add up on its own.
- At setup, I ask Memo for the **current balance of every account** (bank, each SOFIPO, Afore, PPR, GBM, Bitso).
- `check_opening_balances.py` compares each real balance with the balance the 2025–2026 data implies, and lists the gap per account.
- Memo reviews each gap. It gets booked once as a single **"untracked adjustment"** for that account, never as new made-up transactions, so nothing is counted twice.
- Before any row is added, a duplicate check matches on date, amount, and account (not just the row ID), because the same money could show up in both the export and a screenshot.
- The same check runs every month: the screenshot balance is the truth, and any difference from what Money Manager recorded goes to the Data check view for Memo to approve.

### Dashboard (5 views, passes the 7-screen gate)
1. **Overview**: net worth over time and by account type, net income per month (income minus expenses, transfers excluded), savings rate.
2. **Expenses**: by category and month, top categories, month-over-month change.
3. **Income**: by source and month.
4. **Investments**: total by platform and type; fixed-yield tab (maturity calendar, payouts expected, rate per deposit); variable tab (holdings, gain vs. contributions, mix by type); retirement tab.
5. **Data check**: what the last run loaded, anything flagged, reconciliation gaps.

Global filters: month range, account, category.

### Monthly workflow (WAT)
`workflows/monthly-close.md` describes the steps; small scripts in `tools/` do the repeatable parts:
- `ingest_moneymanager.py`: read the Excel, clean it, add new rows only.
- Screenshot reading: Claude reads each image in-session and writes one JSON file per platform in a fixed format. No API key needed because Claude Code does the reading.
- `validate_snapshot.py`: checks each JSON (sum of holdings equals account total, gain $ matches gain %, no missing platforms, balance jump over a threshold gets flagged).
- `calc_fixed_deposits.py`: interest, payouts, and maturity dates for both payout types.
- `reconcile.py`: compares each account's balance change with the transfers Money Manager recorded, and flags gaps.
- `load_db.py`: writes the confirmed data to SQLite.
- Memo confirms a short summary table ("here's what I read from each screenshot") before anything is saved.

### Skills and agents
Two skills, each designed and built in its own session with Memo:
1. `read-finance-screenshots`: turns a platform screenshot into the standard JSON, with the confirm step.
2. `monthly-finance-close`: the one command that runs the whole workflow.

On agents: honest pushback, a team of agents isn't needed here. One skill calling scripts is more reliable. The one place a separate agent earns its keep is the **verifier** in testing: a fresh subagent that checks results without having written the code.

## Build sequence (one session each, roughly)

Working rule: Memo approves every file edit manually before it's made.

1. **Setup + samples**: create the project; Memo drops the 2025–2026 exports and one month of screenshots for all 8 platforms plus bank accounts in the inbox, and gives the current balance of every account.
2. **Design (Part A)**: quick pass through the five gates in `specs/mvp-design.md`, then the one-page spec.
3. **Data foundation**: data model, Money Manager ingestion (test first), category and account mapping.
4. **Investments logic**: screenshot JSON format, validation, fixed-deposit math (test first against real statements), reconciliation.
5. **Dashboard**: the five views and filters.
6. **Testing phase** (below).
7. **Skill sessions**: build skill 1, then skill 2.
8. **First live run** with the real month, then a short lessons-learned update.

## Testing phase and evaluations

Replay: load 2025 as history, then feed 2026 one month at a time as if each were a new monthly run, including screenshots. For months without real screenshots, generate synthetic snapshots from a known "truth" table so we know the right answer.

| What we test | How | Pass mark |
|---|---|---|
| Money Manager ingestion | Row counts and totals per month/category match the Excel | Exact match |
| Re-running the same month | Load the same file twice | Zero duplicates |
| Opening balances | Real current balances vs. balances implied by 2025–2026 data | Every gap listed and booked once as an adjustment; ending balances match reality |
| Overlap between sources | Same movement planted in the export and a screenshot | Caught as a duplicate, counted once |
| Screenshot reading | Memo's real screenshots hand-labeled once as the answer key; compare every field | 100% after confirm step; log first-pass accuracy |
| Fixed-deposit math | Known deposits from real statements, both payout types | Within 1 peso |
| Reconciliation | Planted gaps (missing transfer, wrong balance) | Every planted gap flagged |
| Dashboard filters | Each filter combination vs. a direct database query | Exact match |
| Net worth series | 3 replayed months vs. hand-calculated totals | Exact match |
| Edge cases | Refund, new category, new account, matured deposit, stock sale, missing screenshot, blurry screenshot | Handled or clearly flagged, never silent |
| Independent check | Fresh verifier subagent reviews results against the spec | No open issues |

Results go in an eval report in `Outputs/` so we can re-run it after any change.

## Open items (resolved during the sessions, not blockers)

- Data folder inside or outside OneDrive (recommend outside).
- How often to update property and car values.
- Whether bank/cash balances come from Money Manager (it tracks account balances) or screenshots. Likely Money Manager, which saves work.
- Credit cards: not in net worth for now. If a card is in Money Manager, its spending still shows in expenses.

## Verification (end to end)

Run the full replay for 2026 with one command, open the dashboard locally, click through all five views with several filter combinations, compare totals to the eval report, and have the verifier subagent sign off before the first live monthly run.
