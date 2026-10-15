# Personal Finance Dashboard: Eval Report

Run 2026-10-01 14:46. **7 of 7 checks pass.** This copy has no amounts; the full one is in FinanceData\evals.

Numbers from the spec's "Done Means" list. Re-run any time with `tools/run_evals.py`.

| # | Check | Result | Detail |
|---|---|---|---|
| 1 | Money Manager import matches the Excel | PASS | 867 rows from 3 files (48 replaced by a newer export of the same dates), 320 month × type × category groups; 0 differ; 0 import warnings (holes between exports, old files saved again) |
| 1 | Loading twice adds nothing | PASS | built twice: identical contents; rows transactions 867 then 867, snapshot_items 47 then 47, adjustments 0 then 0; with every export listed twice: 867 transactions |
| 2 | Opening net worth | PASS | 2026-09-28: matches the spec |
| 2 | Net worth card on the dashboard | PASS | Resumen card for 2026-09-28: matches the database |
| 3 | Fixed-yield math | PASS | 7 of 7 deposit interest figures within 1 peso of the platform's; 0 deposits had no figure to compare |
| 4 | Filters match the database | PASS | 72 filter combinations in code and 18 on the Gastos/Ingresos screens (Total, net income and savings rate cards) vs. direct SQL; 0 differ |
| 5 | Replay of 3 months with planted errors | PASS | 38 of 38 replay checks pass over 3 months (2026-10-31 to 2026-12-31), incl. net worth each month vs. the truth table. Planted errors: missing screenshot (2026-10: caught); matured deposit still listed (2026-10: caught); duplicate row (2026-10: caught); transfer logged with the wrong amount (2026-11: caught); stock sale (2026-12: caught); new category, new account and refund (2026-12: caught); month re-sent with a tag removed (2026-12: caught); row deleted in a re-sent month (2026-12: caught). |
| 6 | Screenshot reading accuracy | not in this run | Moved to step 7: measured once the reading skill exists. |
| 7 | Independent verifier | not in this run | Runs after this report (step 6d). |
| 8 | Real monthly update under 20 minutes | not in this run | Step 8, the first live run. |
