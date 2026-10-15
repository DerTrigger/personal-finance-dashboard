---
name: monthly-finance-close
description: Run Memo's monthly finance update for the Personal Finance Dashboard end to end - collect the Finance Inbox, check the Money Manager export, read and confirm the investment screenshots, save the month, reconcile, run the evals, clean up, and summarize. Use this whenever Memo says "run the monthly finance update", "monthly close", "update the dashboard with last month", "I uploaded this month's files", or anything that means bringing his finance dashboard up to date for a new month, including a run with only the Money Manager export.
---

# Monthly finance close

The one command behind the calendar reminder. The procedure lives in
[workflows/monthly-close.md](../../../workflows/monthly-close.md) (plain language, so Memo can read and edit it):
**open it and follow it step by step.** This file only adds the judgment around it.

Project folder: `C:\Users\<you>\OneDrive\Documentos\Claude OS\Projects\Personal Finance Dashboard`. Financial data
stays in `C:\Users\<you>\FinanceData\`. Never write amounts into the project folder or memory.

## What matters most

- **Four yes-points, each asked separately:** moving the inbox files, saving the readings (the confirm table),
  booking an adjustment, deleting the screenshots. A yes to one isn't a yes to the next. These change or remove
  Memo's data, and he approves each one.
- **Stop rather than push through.** An eval FAIL, a missing screenshot, a hole in the export dates, or a month
  that's already saved means something is off. Explain it in plain words and fix the cause. A close that finishes
  with a wrong number is worse than one that pauses.
- **Full or export-only** is decided by the inbox: screenshots mean full, the export alone means export-only.
  Export-only skips reading, reconciling and cleanup.
- **Reading** is its own skill (`read-finance-screenshots`): use it whole, don't improvise the reading.
- **Keep Memo oriented:** one line before each step ("Step 3 of 8: reading the screenshots"), and a short summary
  at the end with the time it took. The goal is under 20 minutes.

If a step fails because the workflow was wrong or unclear, fix the workflow (and its change log) after the close,
per the self-improvement loop in the project's `CLAUDE.md`.
