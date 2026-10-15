# Workflow: Monthly close

- **Objective:** bring the dashboard up to date with last month: Money Manager movements, and (in a full close) every
  investment balance, checked and confirmed by Memo.
- **Trigger:** Memo says "run the monthly finance update" (the calendar reminder on the 1st of each month).
- **Inputs:** whatever Memo uploaded to Google Drive › Finance Inbox (`G:\Mi unidad\Finance Inbox`): the Money
  Manager export for last month and, in a full close, the app screenshots on the reminder's checklist.
- **Tools used:** `collect_inbox.py`, `ingest_moneymanager.py`, the `read-finance-screenshots` skill (which uses
  `convert_heic.py`, `draft_pending.py`, `validate_snapshot.py`, `compare_readings.py`), `append_snapshots.py`,
  `build_db.py`, `reconcile.py`, `run_evals.py`, `cleanup_screenshots.py`, `month_summary.py`.
- **Output:** `FinanceData\investment-snapshots.csv` with the new month (full close), a rebuilt `finance.db`, the
  eval report, and a short summary for Memo.
- **Needs Memo's yes before:** moving the inbox files, saving the readings, booking any adjustment, deleting the
  screenshots.

Run every tool from the project folder with
`PYTHONIOENCODING=utf-8 C:\Users\<you>\.venvs\finance-dashboard\Scripts\python tools\<tool>.py`.

**Two kinds of close.** *Full*: screenshots + export (the normal month). *Export-only*: just the Money Manager
export (e.g. 1 Oct 2026, three days after the opening snapshot). The inbox decides which one it is.

---

## Steps

**0. Start.** The month being closed is last month (`M` = `YYYY-MM`; on 1 Nov it's October). Note the time: the
target is under 20 minutes. If the dashboard is open, ask Memo to close it: it locks the database.

**1. Collect.** Run `collect_inbox.py --month M`. It only lists what it would move. Tell Memo what's there
(export yes/no, how many screenshots per platform) and what's missing from the checklist below. With his OK, run
it again with `--move`: the files go to `FinanceData\YYYY\M\` and leave the Drive inbox.
- Screenshots present → **full close**. Only the export → **export-only**. No export → ask for it before going on.

The checklist (same as the calendar reminder):
1. Money Manager export: last month only, Excel.
2. Nu: the 4 Cajitas (Ahorro, Fondo de Emergencia, Inversión, Retiro).
3. FINSUS: every deposit (Detalle inversión) + Apartados.
4. Kubo: every active deposit.
5. GBM: the account's total value + portfolio, with "Ver más instrumentos" open so every holding shows.
6. Bitso: wallet.
7. Allianz: the app's current total (and the latest statement if there's a new one).
8. Profuturo: Saldos.

**2. Money Manager check.** Run `ingest_moneymanager.py`. Look for:
- the new file covering all of month `M` (a "missing days" warning means a hole: usually an export saved before the
  month ended, or a month skipped);
- possible duplicates, rows that vanished from a re-sent month, transfers missing their other half.
Explain anything flagged in plain words. Memo fixes it in Money Manager and re-exports, or says it's fine.

**3. Full close only: read the screenshots.** Use the `read-finance-screenshots` skill from start to finish. It
ends with Memo's yes on the confirm table and the accuracy log.

**4. Save.**
- Full close: `append_snapshots.py <month folder>\pending-snapshot.csv --confirmed` (only after step 3's yes).
  It saves the month and rebuilds the database.
- Export-only: `build_db.py`.
Either one prints any import warning; it should be the same as step 2.

**5. Full close only: reconcile.** Run `reconcile.py`. For each flagged platform ("money put in doesn't match what
Money Manager logged"), give Memo two choices:
- the transfer is missing or wrong in Money Manager → he fixes it there and re-exports (back to step 1 for the
  export);
- book it once as an adjustment: `reconcile.py --book PLATFORM`, only with his yes. That's for money that was
  never logged, or logged wrong when he'd rather not fix Money Manager (then say it stays wrong there). After any
  booking, run `build_db.py`; the gap then reads as settled.
A stock sale also shows up here (the sold position's gain reads as money put in): say so and book it only if he
agrees. Money that leaves for an account outside net worth (e.g. a Kubo deposit paid to the bank) isn't flagged
here: mention it in the summary if net worth dropped because of it.

**6. Check the numbers.** Run `run_evals.py` (about a minute). Every check must pass. A FAIL stops the close:
read the full report in `FinanceData\evals\`, find the cause, and fix it at the source before going on.

**7. Full close only: clean up.** `cleanup_screenshots.py --month M` lists the images it would delete; with Memo's
yes, run it with `--yes`. The export and the readings stay.

**8. Summary.** Run `month_summary.py --month M` and tell Memo, in a few lines:
- net worth now and the change vs. last month, split into money put in / returns / estimated returns /
  revaluation (full close);
- the month's income, spending, net income, and "Tarjetas por pagar";
- reading accuracy (full close), anything flagged or booked, and how long the close took.
Offer to open the dashboard (`Start Finance Dashboard.bat`). Update the project `memory.md` "Current state"
(date, kind of close, duration, accuracy: counts only, never amounts).

## Edge Cases

- **`G:\Mi unidad\Finance Inbox` doesn't exist:** Google Drive for desktop isn't running or isn't signed in. Ask
  Memo to open it, then retry step 1.
- **The month is already saved** (`append_snapshots.py` refuses): don't save twice. Ask Memo whether this is a
  correction; corrections need a plan, not a second append.
- **A screenshot is missing** (the check says "Falta PLATFORM"): ask for that screen; don't save the month without it.
- **A new account appears:** stop and follow `workflows/add-or-close-account.md` before saving.
- **The database is in use** (build or save fails with a permission error): ask Memo to close the dashboard, retry.
- **A tool fails:** stop, report the error in plain words, follow the self-improvement loop in `CLAUDE.md`.

## Change Log

- 2026-09-29: Created with the `monthly-finance-close` skill. Two kinds of close (full / export-only).
- 2026-09-29: After the sandbox rehearsal: checklist added to step 1; rebuild after booking and the "book it
  anyway" path in step 5 (booked gaps now read as settled); `month_summary.py` for step 8; car/Activos changes
  are now warned by the check.
- 2026-10-01: First live run (export-only). The export came named "2026-09-01 ~ 09-30.xlsx" and step 2 didn't list
  it; the tools now accept that name too. In step 2, always confirm the new file appears in the list.
