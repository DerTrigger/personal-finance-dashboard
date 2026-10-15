# Personal Finance Dashboard

A local dashboard that shows my net worth month by month across eight investment platforms in Mexico (SOFIPOs, a brokerage, crypto, and two retirement accounts), plus my spending and income from Money Manager exports.

I built it with Claude Code. I have an engineering background but hadn't written code in years, so this repo is as much about the process as the app: how I set up Claude to plan, build, test, and run a monthly routine with me in the loop.

> **Privacy note.** This is a cleaned-up public copy. Every amount in it is invented, account names are generic, and real data never lived in the repo: raw exports, screenshots, and the database stay in a separate folder on my machine that isn't synced or committed. The original commit history stays private because early commits recorded real balances.

## What it does

- **Five screens (in Spanish):** Resumen (net worth and why it changed), Ingresos, Gastos (category → subcategory → transaction drill-down), Inversiones (fixed yield, variable, retirement), and Revisión de datos (data checks and warnings).
- **One monthly routine:** I drop a Money Manager export and phone screenshots of each platform in a folder. Claude reads the screenshots, shows me a table of every number, and saves only what I confirm. The database is rebuilt from those sources every run.
- **Interest math that matches the banks to the cent:** business-day rules with Mexican bank holidays, 360-day bases, and ISR withholding (`app/lib/interest.py`).
- **Reconciliation:** compares what each platform says I earned with the transfers I logged, and flags gaps for me to approve instead of fixing them silently.

Stack: Python, Streamlit, Plotly, pandas, SQLite, pytest. Everything runs locally.

## How I worked with Claude Code

**Instructions and memory in plain files.** `CLAUDE.md` holds the rules for this project (where data may live, what needs my approval, language, test-first). `memory.md` is a dated log of every decision and lesson, which Claude reads at the start of each session so nothing is lost between sessions. It's worth skimming: it records the mistakes too, and what changed because of them.

**Design before code.** The project followed a two-part framework. First the MVP design (`specs/mvp-design.md`): the one core function, the monthly loop, a cap on screens. Then the build: `specs/spec.md` → `specs/plan.md` → `specs/tasks.md`, one task at a time, ticked off only after it was verified. Claude worked in plan mode before every non-trivial step, and I approved the stack before it was used.

**Test first on anything involving money.** Each piece of logic started with a check like "given this input, the answer must be exactly this." There are 225 tests, including page tests that click through the Streamlit screens and compare filtered totals with direct database queries.

**Evals and a replay.** `tools/run_evals.py` replays three future months with planted errors (a missing screenshot, a duplicated row, a mislogged transfer, a stock sale) and confirms each one gets caught. A separate Claude subagent then reviewed the work against the spec with fresh eyes.

**Workflows, agent, tools.** Repeatable steps live in small scripts (`tools/`, indexed in `tools/README.md`), the steps themselves are written in plain language (`workflows/`), and Claude handles the judgment in between. Two Claude skills in `.claude/skills/` run the monthly close: one reads platform screenshots, the other walks through the close with four points where it stops for my yes.

**Human in the loop.** Claude never saves a screenshot reading, books an adjustment, or deletes a file without my confirmation.

## Repo map

```
app/            dashboard (Streamlit) and all calculation logic in app/lib/
tools/          one-job scripts: import, build the database, validate, reconcile, evals
tests/          pytest suite on invented data
workflows/      plain-language steps for the monthly close and account changes
.claude/skills/ the two Claude skills used each month
specs/          MVP design, spec, plan, tasks
config/         settings.toml: accounts, return methods, check tolerances
CLAUDE.md       project rules for Claude
memory.md       decision and lesson log
```

## Running it

The dashboard expects my data folder layout and file formats, so it won't show anything useful without similar data. To look around or run the tests:

```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m pytest
```

Set `data_dir` in `config/settings.toml` to your own folder, build the database with `python tools/build_db.py`, then start the dashboard with `streamlit run app/dashboard.py`.
