# Personal Finance Dashboard: Build Tasks
*Small, ordered, one job each. Tick a task only after it's verified.*

## Step 3: data foundation (done 2026-09-28)
- [x] 1. Setup: environment, requirements.txt, git init, .gitignore blocking data | Verified 2026-09-28
- [x] 2. Money Manager import, tests first | Verified 2026-09-28: 11 tests pass; real totals match exactly; 0 duplicates, 0 unmatched transfers
- [x] 3. Interest math, tests first | Verified 2026-09-28: 20 tests pass; 7 of 7 deposit totals within 0.01; 12 of 12 FINSUS payments match date and amount
- [x] 4. Build the database from exports + CSV | Verified 2026-09-28: 7 tests pass; real net worth 1,234,567.89; two rebuilds give the same fingerprint
- [x] 5. Opening balances check | Done 2026-09-28: gap list shown to Memo (all gaps = history before Money Manager tracking). Decision: no opening adjustments; the 2026-09-28 snapshot is the opening balance. `check_opening_balances.py` dropped.

## Step 4a: readings format, validation, reconciliation (done 2026-09-28)
- [x] 6a. Pending CSV format (same columns as `investment-snapshots.csv`; replaces the per-platform JSON), `validate_snapshot.py`, `append_snapshots.py`, `reconcile.py` | Verified 2026-09-28: 78 tests pass; real opening snapshot validates with 0 errors / 0 warnings; dry run on a copy of real data: planted GBM gap flagged and booked once, clean platforms not flagged, double save refused, matured Kubo deposit warned

- [x] 6b. Step 4b: `collect_inbox.py`, `convert_heic.py`, `cleanup_screenshots.py` | Verified 2026-09-28: 94 tests pass (incl. a real HEIC named .png converted; no overwrite; cleanup refused until the month is saved); real Drive inbox reachable

## Now
- [x] 7. Step 5: dashboard screens (7) and filters | Built 2026-09-28: 122 tests pass (9 page tests on a fake database); on real data net worth 1,234,567.89, expense/income totals match the exports, 5 filter combinations match direct counts, Fixed yield calendar matches `check_deposits.py` (12 of 12).
  - Round 2 (2026-09-28, Memo's review): Spanish UI, 5 screens, light/dark themes, compact numbers, calendar period, click-to-filter, drill-down, month comparisons, one settings block per account. 159 tests pass; screenshots checked at 760/1100/1400/1600 px in both themes.
  - Round 3 (2026-09-29, Memo's review): quick periods, menu order, % on hover, light-mode fix, Resumen income by source + expense donut + cross-filter, unpaid card cards (IN NU / NPY), Variable top/bottom picker, Retiro chart. 173 tests pass. Memo: "in a pretty good state." Ticked 2026-09-29.
  - Parking lot: subtract card debt from net worth (frozen at monthly close); see memory.md Open Questions.

## Next
- [x] 8. Step 6: testing phase and evals (plan approved 2026-09-29) | Done 2026-09-29: 213 tests pass; `tools/run_evals.py` 7 of 7 on real data
  - [x] 8a. Replay engine (`app/lib/replay.py`) + tests on fake data: Oct–Dec 2026, planted errors | Verified 2026-09-29: 10 replay tests pass (183 total), incl. one proving a check can fail; trial on a copy of real data: every check passes. Planted Oct matured deposit moved from Nov to Oct (real and fake Kubo deposits mature in Oct).
  - [x] 8b. Eval checks 1–4 (`app/lib/evals.py`) + `tools/run_evals.py` + tests | Verified 2026-09-29: 12 eval tests pass (195 total); each check has a planted-fault test that makes it fail
  - [x] 8c. Run on real data, fix findings, write both reports | Verified 2026-09-29: 7 of 7 checks pass on real data (nothing to fix); report without amounts in Outputs/, full one in FinanceData\evals; tampered copy of the real database fails check 1 as it should
  - [x] 8d. Verifier subagent; open issues fixed or accepted by Memo | Done 2026-09-29: round 1 found 6 issues (all fixed; issues 1–2 led to the monthly-export redesign, plan in `C:\Users\<you>\.claude\plans\cached-launching-kurzweil.md`). Round 2: issues 1–2 resolved; new gaps fixed (holes between exports and old files saved again now warned, and fail eval check 1); card pending counting only the latest export is Memo's choice, logged. Also fixed: `find_exports` picked up files in the `_replay` scratch folder.
- [x] 9. Step 7: skill sessions (read-finance-screenshots, monthly-finance-close) | Done 2026-09-29
  - [x] 9a. Skill 1 `read-finance-screenshots` (`.claude/skills/` in this project) + `tools/draft_pending.py`, `tools/compare_readings.py` | Verified 2026-09-29: blind practice run by a fresh agent on the 17 Sep 28 screenshots: 211 of 214 fields right first pass (the 3 misses = screenshots not taken: GBM total/cash, Allianz current total; now on the checklist); 214/214 after the confirm step; 0 validation errors. Guide improved from the run. 217 tests pass.
  - [x] 9b. Skill 2 `monthly-finance-close` + `workflows/monthly-close.md` (full and export-only closes) | Verified 2026-09-29: sandbox rehearsal by a fresh agent, both modes: every step in order, all 4 yes-points asked, evals 7/7 each time, real files byte-for-byte unchanged. Fixes from it: booked gaps read as settled, car/Activos changes warned, `month_summary.py`, checklist in the workflow. Also: replay months follow the latest snapshot; run_evals removes its scratch; FINANCE_DATA_DIR/FINANCE_INBOX_DIR sandbox overrides. 224 tests pass.
- [ ] 10. Step 8: first live monthly run

## Done
- [x] Setup, opening snapshot, Part A design, spec, technical plan (2026-09-28)
