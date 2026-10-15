# Personal Finance Dashboard: MVP Design (Part A)
*One section per stage. Don't start a stage until the one before it passes its gate.*
*Status: Signed off by Memo, 2026-09-28.*

---

## A1. Core Function

**It shows Memo his true net worth each month.**

Everything else (expenses, income, investment detail) exists to explain why that number moved.

**Gate:** One sentence, no "and"? **Pass**

## A2. Core Loop

This product has two loops, and they run at different speeds. The 30-second rule applies to the one he repeats most: looking.

**Viewing loop (the core loop):**
1. Memo opens the dashboard (one shortcut on his desktop).
2. The top of the Overview shows: net worth today, change vs. last month, and that change split into three parts: money he put in, what his investments earned, and what he spent beyond his income.
3. Below it: the next money event (for example, "Kubo, 150,000.00 matures Oct 19").
4. He gets an answer to "am I better off than last month, and why?" Done.

Time: under 30 seconds.

**Update loop (once a month):**
1. Memo takes the screenshots (about 17) and exports Money Manager.
2. Drops them in that month's folder, e.g. `FinanceData\2026\2026-10\`.
3. Runs one command in Claude Code.
4. Claude converts, reads, checks, and shows one confirm table with anything flagged.
5. Memo says yes (or corrects a number). The dashboard refreshes.

Time: about 15 to 20 minutes, most of it taking screenshots. This loop can't meet 30 seconds, because the platforms offer no way to pull data automatically. The honest target is "under 20 minutes, one command, one confirmation."

**Gate:** Repeatable and under 30 seconds? **Pass** for the viewing loop. The update loop is monthly by design, with a 20-minute target noted as an exception.

## A3. Accessory Features

**Must-have (goes in the MVP):**
- Net worth card and trend line (monthly points, starting 2026-09-28).
- **"Why it changed" breakdown**: contributions, investment returns, and net spending, month by month. Money Manager transfer logs are incomplete, so **returns come from what each platform reports**, and contributions are the rest of the balance change:
  - GBM: change in reported gain $ per holding.
  - Nu: change in each Cajita's reported growth.
  - FINSUS and Kubo: interest calculated from the deposit terms (rate, days, 360-day basis, after tax).
  - Allianz PPR: statement value minus contributions to date, when a statement is available.
  - Bitso and Profuturo: no reported return. Balance change minus logged transfers, labeled "estimated."
  - Money Manager transfers become a cross-check, not the source.
- Net income per month (income minus expenses, transfers excluded) and savings rate.
- Expenses by category and subcategory, by month, with month-over-month change.
- Income by source, by month.
- Investments by platform and by type (fixed, variable, retirement, manual assets).
- Fixed yield: maturity calendar with expected payouts, monthly vs. at-maturity handled, interest shown on the same after-tax basis for every platform.
- Variable: holdings with value, gain vs. money put in, mix by type (ETF, FIBRA, stock, crypto, fund, cash).
- Retirement: Allianz PPR and Profuturo, with the housing subaccount on its own line.
- Filters: month range, account, category.
- Data check view: what the last run loaded, flags, and untracked adjustments.
- The one-command monthly update with a confirm step (built as the two skills). Files go in `FinanceData\2026\YYYY-MM\`, one folder per month.
- Monthly reminder: a recurring Google Calendar event with the screenshot checklist.

**Parked for later:**
- *Should:* Bank and cash accounts in net worth (Memo revisits later in 2026).
- *Could:* Budgets or spending targets per category. Payout alerts before a maturity date. Backfilling investment history from old statements. A phone-friendly view. Projections (where net worth could be in 5 or 10 years).
- *Won't (for now):* Live market prices. Debts and credit card balances. Household or business money. Anything hosted online. Currencies other than MXN.

**Gate:** Every must-have serves the core loop? **Pass.** Each one either shows net worth or explains a part of its change. The confirm step and data check protect the accuracy of the number itself.

## A4. Surface Area Check

| # | Screen | Purpose |
|---|--------|---------|
| 1 | Overview | Net worth, why it changed, net income, next money event |
| 2 | Expenses | Where the money went |
| 3 | Income | Where the money came from |
| 4 | Investments: Fixed yield | SOFIPO deposits, rates, maturity calendar |
| 5 | Investments: Variable | GBM and Bitso holdings, gains, mix |
| 6 | Investments: Retirement | Allianz PPR, Profuturo |
| 7 | Data check | Last run, flags, adjustments |

The monthly confirm step happens in the chat with Claude, not on a screen.

**Gate:** Seven screens or fewer? **Pass, exactly at the limit.** Any new screen means another one merges or goes.

*Update 2026-09-28 (Memo's review):* he asked for an investments summary. Instead of an 8th screen, screens 4–6 merged into one "Inversiones" screen (summary on top, three tabs). Now 5 screens: Resumen, Gastos, Ingresos, Inversiones, Revisión de datos. Gate still passes.

## A5. Retention Hook

**Every month the Overview shows what changed since last month and what comes due next, so there's always a decision waiting, like where to put the 150,000.00 from Kubo on October 19.**

The unfinished state is the maturity calendar: money arriving soon needs a decision. The monthly trend line is the investment: each run adds a point, and a gap in the line is visible.

**Gate:** Clear reason to return? **Pass**

---

## Decisions at sign-off (2026-09-28)

1. Core function confirmed as written.
2. Monthly reminder is a must-have: recurring Google Calendar event.
3. Breakdown split confirmed, but it doesn't rely on Money Manager logs. Platform-reported returns first.
4. Monthly folders: `FinanceData\2026\YYYY-MM\`.

---

**Memo's sign-off:** 2026-09-28 [x]
