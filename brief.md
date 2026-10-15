# Personal Finance Dashboard: Brief
*The source of truth for what this project is. If something isn't here, it isn't in scope.*
*Last updated: 2026-09-28*

---

## The Goal

Give Memo one local dashboard that shows his true net worth month by month.

## Who It's For and Why It Matters

Memo, for his personal money only. Today he logs expenses, income, and transfers in Money Manager and exports an Excel each month, but he can't see how his investments are doing across eight platforms, or what his net worth is. The money is spread across fixed-yield SOFIPO deposits, a stock account, crypto, and retirement accounts, each with its own app.

## What Done Looks Like

- The monthly update takes one command plus a quick confirm, under 20 minutes including taking screenshots.
- Net worth on the dashboard matches the real account balances to the peso for every replayed test month.
- He can filter by month, account, and category, and each filtered total matches a direct database query.
- He sees every fixed-term deposit's maturity date and expected payout before it happens.

## Scope

**In:**
- Money Manager Excel export (expenses, income, transfers), 2025 onward.
- Monthly screenshots from each investment platform, read by Claude and confirmed by Memo.
- Fixed yield: Nu, FINSUS, Kubo Financiero. Handles deposits that pay monthly and ones that pay at maturity. Maturity calendar.
- Variable yield: GBM (per holding: titles, amount invested, historical gain in % and $) and Bitso. Mix by type (ETF, FIBRA, stock, crypto). Gain vs. money put in.
- Retirement: Afore Profuturo, PPR Allianz.
- Car and household goods ("Activos") at an estimated value. Profuturo housing subaccount on its own line.
- Five views: Overview, Expenses, Income, Investments, Data check.
- A monthly workflow plus two Claude skills, built in separate sessions.
- A testing phase that replays 2026 month by month and runs evals.

**Out (for now):**
- Live market prices.
- Debts and credit card balances in net worth (card spending still counts as expenses).
- Bank/cash accounts (Memo revisits later in 2026).
- Household or business finances.
- Anything online: no hosting, no sharing, no cloud database.
- Currencies other than MXN.

## Constraints

- **Time:** Memo's side time; work goes one session per step.
- **Money:** free tools only.
- **Tools:** local Python stack (proposed: Streamlit, pandas, SQLite, Plotly). Memo approves before build.
- **Privacy:** raw data lives in `C:\Users\<you>\FinanceData\`, outside OneDrive. No data in the project folder or memory files.
- **People:** Memo only. He approves every file edit manually.

## People Involved

| Name | Role | Notes |
|------|------|-------|
| Memo | Owner and only user | Approves every edit and every screenshot reading |

## Inputs We Already Have

- Money Manager exports for 2025 and 2026 (Memo will drop them in `FinanceData\initial-setup\`).
- One month of screenshots per platform (to be dropped in the same folder).
- Current balance of every account (Memo will provide at setup).

## Open Questions

- How often to update the car and "Activos" values.
