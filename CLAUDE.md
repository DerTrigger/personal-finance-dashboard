# Personal Finance Dashboard: Project Instructions
*Created: 2026-09-28 · Add-ons: app-build, automation-wat*

## What This Project Is

A local dashboard that shows Memo's net worth, spending, net income, and every investment account in one place, refreshed by a one-command monthly routine. Done means: he drops his Money Manager export and platform screenshots in a folder, runs one command, confirms what was read, and the dashboard is current and correct.

## Current Status

Setup. See the "Current state" block in `memory.md`. Full approved plan: `specs/project-plan.md`.

## Rules for Claude in This Project

- Before any work: read `Projects/CLAUDE.md`, then this file, then `memory.md`.
- Save deliverables to `Outputs/`, named `Personal Finance Dashboard - [What it is].[ext]`.
- Log every decision in `memory.md` with the date.
- Language: the dashboard itself is in Spanish (changed 2026-09-28). Chat with Memo, docs, code, code comments, and technical specs stay in English. All amounts in MXN, shown as $45.6k in charts and cards, $12,345 in tables.
- Follow Memo's safety rules: nothing sent, published, deployed, or deleted without his yes.
- **Memo approves every file edit manually.** Don't batch edits to get around this.
- **Financial data never goes in this folder.** This folder syncs to OneDrive. Raw exports, screenshots, and the database live in `C:\Users\<you>\FinanceData\`, which is not synced. Only code and docs live here. Never paste balances or account numbers into memory or docs.
- **Money Manager is incomplete.** Not every expense, income, or investment is logged. The real account balance (from Memo or a screenshot) is the truth. Differences get booked once as an "untracked adjustment" after Memo approves, never as invented transactions.
- **Check for duplicates before adding any row** (match on date, amount, and account), since the same money can appear in the export and a screenshot.
- Any number read from a screenshot is shown to Memo in a summary table and confirmed before it's saved.
- Skills are designed and built in separate, step-by-step sessions with Memo. Don't build a skill inside a regular work session.

## Data Folder (outside OneDrive)

```
G:\Mi unidad\Finance Inbox\     ← Google Drive (desktop app). Memo uploads from his phone. Temporary only.
C:\Users\<you>\FinanceData\
├── investment-snapshots.csv    ← confirmed readings from every screenshot, one row per item per month. Permanent.
├── initial-setup\              ← first batch: 2025 + 2026 exports, opening snapshot JSON
└── 2026\YYYY-MM\               ← each month's files, moved here from the inbox
```

**Screenshot retention:** once Memo confirms a month's readings and they're appended to `investment-snapshots.csv`, the screenshots are deleted from the month folder and from the Drive inbox. Ask Memo once per run before deleting. Money Manager exports are kept (they're small).

## Accounts in Scope

SOFIPOs: Nu, FINSUS, Kubo Financiero (fixed yield; some pay monthly, some at maturity). **Nu: only count these four Cajitas:** "Cajita Ahorro", "Fondo de Emergencia", "Inversión", "Retiro". The other Cajitas are spending envelopes and are ignored. Retirement: Afore Profuturo, PPR Allianz. Variable: GBM (stocks, ETFs, FIBRAS), Bitso (crypto). Profuturo's housing subaccount counts, shown on its own line. Manual assets: car and "Activos" (appliances and furniture). Bank/cash accounts are out for now. Credit card spending counts as expenses; card balances are not tracked as debt. When Money Manager and a platform disagree, the platform wins.

## Files

- `brief.md`: the goal, scope, constraints, and success criteria. The source of truth for what this project is.
- `memory.md`: current state, decisions log, lessons, open questions.
- `specs/project-plan.md`: the approved plan, including the testing phase and evals.
- `Outputs/`: finished deliverables only.

## How This Project Gets Built: App Build Framework

This project follows `Projects/App-Build-Framework.md`. Read it in full before any design or build work.

- **Part A (design):** Core Function, Core Loop, Accessory Features, Surface Area Check, Retention Hook. Work them in order in `specs/mvp-design.md` and pass each gate before moving on. Save a clean copy to `Outputs/` when Memo signs off.
- **Part B (build):** Spec, Plan, Tasks, Implement, Verify, using `specs/spec.md`, `specs/plan.md`, and `specs/tasks.md`.

### Build Rules

1. No code before Memo signs off the MVP design (end of Part A) and the spec.
2. Plan mode before any non-trivial build step. Memo approves the stack before it's used.
3. Work one task from `specs/tasks.md` at a time. Tick it off when it's verified, not when it's written.
4. Test first on any real logic: write the check ("given this input, the answer must be exactly this"), then build until it passes. All money math counts as real logic.
5. Small commits, so any mistake is easy to undo.
6. Verify against the spec with fresh eyes. The code that was just written doesn't get to grade itself.
7. Nothing deployed, published, or released without Memo's explicit yes. This dashboard stays local.

### Current Build Context

- **Stack (proposed, not yet approved):** Python, Streamlit, pandas, SQLite, Plotly. All local and free.
- **Where the code lives:** `app/` inside this project folder
- **Current task:** see `specs/tasks.md`

## How This Project Works: WAT (Workflows, Agents, Tools)

This project keeps three layers separate:

- **Workflows** (`workflows/`): plain-language, step-by-step instructions in markdown, one file per process. Each one says what to do, in what order, with what inputs, and what comes out. Written so Memo can read and edit them.
- **Agent** (Claude): reads the right workflow, runs the tools in order, handles surprises, and asks when something is unclear. Claude makes the judgment calls; it doesn't redo by hand what a tool already does.
- **Tools** (`tools/`): small scripts (Python by default) that each do one job the same way every time: call an API, clean a file, build a report. Same input, same output.

Why it's split this way: AI is good at judgment and bad at repeating a long process exactly. If each of five steps is 90% reliable, the whole chain is only about 59% reliable. Moving the repeatable steps into scripts keeps the result dependable, and leaves Claude to handle the parts that need thinking.

### WAT Rules

1. **Workflow first.** Before a task, check `workflows/` for a matching workflow and follow it. If none exists and the task will happen again, draft one from the workflow template in `Projects/_Templates/automation-wat/workflows/` and show Memo before relying on it.
2. **Reuse tools before writing new ones.** Check `tools/README.md` first. A new tool does one job, has a `verb_noun.py` name, starts with a short header (what it does, inputs, outputs), and gets added to `tools/README.md`.
3. **Secrets only in `.env`.** Never in workflows, tools, chat, or memory files. `.env.example` lists the variable names with no values.
4. **Scratch goes in `.tmp/`.** Downloads, intermediate files, and test runs go there and can be thrown away. Finished deliverables go to `Outputs/`. Anything containing real financial data goes to `FinanceData\`, not `.tmp/`.
5. **Human in the loop.** Anything that sends a message, spends money, posts publicly, or changes a client's live system waits for Memo's yes, even when a workflow says to do it.
6. **Plan mode before building or changing a tool.**

### Self-Improvement Loop

When something fails:

1. Find which layer broke: the instructions (workflow), the judgment (agent), or the script (tool).
2. Fix it at the source. Edit the workflow or the tool, not just this one run.
3. Run it again to confirm the fix works.
4. Add a line to Lessons learned in `memory.md`, and a line to the workflow's change log.

If a workflow ends up being used in more than one project, suggest turning it into a Claude skill so it's available everywhere.

### Files Added by This Add-on

- `workflows/`: one markdown SOP per process.
- `tools/`: scripts, indexed in `tools/README.md`.
- `.tmp/`: disposable scratch files (no real financial data).
- `.env` (create from `.env.example`): API keys and secrets. Never share or commit.
- `.gitignore`: keeps `.env` and `.tmp/` out of version control.

## End of Every Session

Update the "Current state" block in `memory.md`, log decisions, and add a lesson if something broke or worked well.
