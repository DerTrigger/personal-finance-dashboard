---
name: read-finance-screenshots
description: Read Memo's monthly investment screenshots (Nu, FINSUS, Kubo, GBM, Bitso, Allianz PPR, Profuturo) into the month's pending-snapshot.csv for the Personal Finance Dashboard, check them, get Memo's confirmation, and log first-pass accuracy. Use this whenever the month's screenshots are in FinanceData\YYYY\YYYY-MM\ (or the Finance Inbox) and need to be read, whenever Memo says "read the screenshots", "run the monthly finance update", "update my investments", or sends app screenshots of his balances, and as the reading step inside the monthly finance close. Also use it to re-read a single platform after a correction.
---

# Read the month's finance screenshots

Turns about 17 app screenshots into `pending-snapshot.csv`: one row per account item, in the same columns as
`FinanceData\investment-snapshots.csv`. It ends when **Memo has confirmed every number**. Saving the month to history,
rebuilding the database and deleting the screenshots come after, in the monthly close. Don't do them here.

Why the care: these numbers become Memo's net worth. A misread peso shows up on his dashboard as money that doesn't
exist, so the procedure is built to catch misreads (a draft with fixed names, internal checks, his confirmation)
and to measure how often the first reading was right.

Project folder: `C:\Users\<you>\OneDrive\Documentos\Claude OS\Projects\Personal Finance Dashboard`. Run tools with
`PYTHONIOENCODING=utf-8 C:\Users\<you>\.venvs\finance-dashboard\Scripts\python tools\<tool>.py` from there.
Financial data only ever goes in `C:\Users\<you>\FinanceData\` (not synced). Never write amounts into the project
folder, memory or chat summaries beyond the confirm table shown to Memo.

## Steps

**1. Screenshots readable.** The month folder is `FinanceData\YYYY\YYYY-MM\` (the month being closed: on 1 Nov
that's October). Run `tools/convert_heic.py --month YYYY-MM`: iPhone screenshots are often HEIC even when named
`.png`. Read the copies in `converted\`; never change the originals.

**2. Draft.** Run `tools/draft_pending.py --month YYYY-MM`. It writes `pending-snapshot.csv` in the month folder with
last month's items: same names, deposit terms and the car/Activos values carried over, and the numbers that change
left blank. `as_of` is set by the draft (the month's last day unless told otherwise): keep it. It never overwrites
an existing file: if one exists, ask Memo before moving it.

**3. Read, one platform at a time.** Open [platforms.md](platforms.md) at the platform you're reading. It says
which screen holds which number, what to skip, and the traps (Nu's envelopes, GBM's red losses, which totals to
compute). Fill the blanks in `pending-snapshot.csv` with the Edit tool; add rows for new items; delete rows for
items that are gone. A number you can't read clearly stays blank and goes on a list for Memo.

**4. Save the first pass as it is.** Before any check or fix, copy `pending-snapshot.csv` to `first-pass.csv` in the
same folder. It's how accuracy is measured honestly, so don't touch it afterwards.

**5. Check.** Run `tools/validate_snapshot.py <month folder>\pending-snapshot.csv`. It prints the confirm table,
then errors and warnings.
- *Errors* block saving. "Parts don't add up" or a wrong gain % almost always mean a misread: look at that screenshot
  again. "Missing platform" means a screenshot didn't arrive: ask Memo for it.
- *Warnings* (an item gone or new, a big jump, a deposit past its end date) aren't necessarily wrong: they go to
  Memo with the table.
Fixes made here go in `pending-snapshot.csv`, never in `first-pass.csv`.

**6. Confirm with Memo.** Show him the confirm table (one line per platform: total, last month, change, items read),
every warning in plain words, and the list of blanks with what you need from him (e.g. "GBM's portfolio total isn't
in the screenshots: what does the app show?"). Apply his corrections to `pending-snapshot.csv` and run the check
again until there are no errors and he says yes. Nothing is saved to history in this skill.

**7. Log accuracy.** Run
`tools/compare_readings.py <folder>\first-pass.csv <folder>\pending-snapshot.csv --month YYYY-MM`. It prints fields
right on the first pass per platform and appends the counts (no amounts) to `FinanceData\reading-accuracy.csv`.
Tell Memo the headline ("214 of 220 fields right the first time; the misses were GBM gains") and, if a platform
keeps getting misread, suggest the line in `platforms.md` to fix.

Then hand over to the monthly close: the confirmed `pending-snapshot.csv` is ready for `tools/append_snapshots.py`.

## When something's off

- **A screenshot is cut off or a list is incomplete** (GBM without "Ver más instrumentos" expanded, a Kubo deposit
  split across two images with one missing): say exactly which items are missing and ask for that screen.
- **A platform isn't in the settings** (a new account): stop and point Memo to `workflows/add-or-close-account.md`.
- **Two screens disagree** (e.g. Kubo "Monto a recibir" ≠ principal + interest): trust neither, flag it.
