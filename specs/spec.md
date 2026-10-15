# Personal Finance Dashboard: Product Spec
*One page. If something isn't here, it isn't in the MVP.*
*Status: Approved by Memo on 2026-09-28.*

## What It Does
It shows Memo his true net worth each month, and explains why it moved.

## Who It's For
Memo, for his personal money only. He logs spending in Money Manager and holds investments across seven platforms with no single view of them.

## The Core Loop
**Viewing (under 30 seconds):** open the dashboard, see net worth, the change vs. last month split into money put in / returns / estimated returns / revaluation, net income beside it, and the next maturity. (Changed 2026-09-28: spending isn't a part of the change because bank and cash accounts are outside net worth.)
**Monthly update (under 20 minutes):** Memo uploads screenshots + Money Manager export from his phone to the Google Drive "Finance Inbox" (synced to `G:\Mi unidad\Finance Inbox`). One command moves them into `FinanceData\2026\YYYY-MM\`, reads them, shows one confirm table, appends the readings to `investment-snapshots.csv`, refreshes the dashboard, and (after Memo's yes) deletes the screenshots.

## Screens
1. Resumen · 2. Gastos · 3. Ingresos · 4. Inversiones (summary + tabs: Plazo fijo y ahorro, Variable, Retiro) · 5. Revisión de datos
(Changed 2026-09-28 after Memo's review: dashboard in Spanish; the three investment screens merged into one with a summary. Every chart is click-to-filter; a calendar date range carries across screens.)

Global filters on every screen where they apply: month range, account, category.

## Must-Have Features
- Net worth card and monthly trend, starting from the opening snapshot (2026-09-28: 1,234,567.89).
- "Why it changed" split. Returns come from each platform's own numbers; contributions are the rest of the change; Bitso and Profuturo are labeled "estimated."
- Net income (income minus expenses, transfers excluded) and savings rate, from January 2025.
- Expenses by category/subcategory and month; income by source and month.
- Fixed yield: every deposit with rate, term, payout type (monthly or at maturity), after-tax interest, and a maturity calendar.
- Variable: holdings with titles, value, gain $ and %, amount invested (value minus gain), mix by type.
- Retirement: Allianz PPR (current value; statement detail when available) and Profuturo (three subaccounts, housing on its own line).
- Manual assets: car and household goods, edited by hand.
- Monthly update: HEIC conversion, Money Manager import with duplicate check, screenshot reading into a fixed JSON format, validation, a confirm table, then load.
- Data check screen: last run, flags, untracked adjustments.
- Recurring Google Calendar reminder with the screenshot checklist.

## Business Rules
- Money Manager exports cover last month only (from October 2026; the first ones were annual). Each export owns the dates it covers; a newer export of the same dates replaces the older one, so edits (e.g. removing "IN NU") never double count. Rows that vanish from a newer export are warned. Possible duplicates = same date + amount + account + category, shown for review. (Decided 2026-09-29.)
- The platform number wins over Money Manager. Differences become one "untracked adjustment," approved by Memo.
- Nu counts only four Cajitas: Cajita Ahorro, Fondo de Emergencia, Inversión, Retiro.
- Credit card spending counts as expenses; card balances are not debt in this MVP.
- Interest on a 360-day basis. After-tax = gross minus ISR withholding (0.9% a year on principal in 2026; kept as a setting so it can change).
- FINSUS monthly interest stays in FINSUS.
- All amounts in MXN.

## Done Means
- [x] Money Manager 2025 and 2026 load with row counts and totals per month and category matching the Excel exactly; loading twice adds zero rows. (2026-09-29, eval report)
- [x] The opening snapshot loads, and net worth on the dashboard equals 1,234,567.89. (2026-09-29)
- [x] Fixed-yield math reproduces every FINSUS and Kubo figure in the screenshots within 1 peso. (2026-09-29: 7 of 7 deposit totals; monthly payments checked in step 3)
- [x] Each filter combination's totals match a direct database query. (2026-09-29: 72 in code + 18 on screens)
- [x] A replay of 3 simulated months (with planted errors: missing screenshot, logging mistake, matured deposit, stock sale, duplicate) produces the right net worth each month, and every planted error is flagged. (2026-09-29: 38 of 38; also monthly exports, a re-sent month, new category/account/refund)
- [x] Screenshot reading: first-pass accuracy logged; 100% after the confirm step. (2026-09-29, blind practice run: 211 of 214 first pass, the 3 misses being screenshots not taken; 214/214 after confirm. Logged every month from now on in `FinanceData\reading-accuracy.csv`.)
- [x] A fresh verifier agent checks the results against this spec and finds no open issues. (2026-09-29: two rounds; everything fixed or accepted by Memo)
- [ ] Memo runs one real monthly update end to end in under 20 minutes.

## Out of Scope
Bank/cash accounts, debts, live prices, budgets, alerts, projections, backfilling history, phone view, household or business money, hosting, non-MXN currencies.

## Risks and Rules
- Financial data stays in `C:\Users\<you>\FinanceData\` (not synced). Nothing online. Code and docs hold no balances or account numbers.
- `FinanceData\` has no backup yet. Needs a plan before the first live month (open question).
- Misread screenshot: mitigated by internal checks (parts must add to totals) and Memo's confirmation.
- Unlogged contributions make Bitso/Profuturo returns look higher; labeled "estimated."
