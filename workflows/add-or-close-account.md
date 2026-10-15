# Add or close an account

Everything about an investment account lives in one block in `config/settings.toml`. No code changes.

## New income source or expense category

Nothing to do. Add it in Money Manager; it shows up on Gastos / Ingresos after the next monthly update. Colors go to the 7 biggest categories; the rest are grouped as "Otros".

## Open a new investment account

1. Copy any `[platforms."..."]` block in `config/settings.toml` and change the name to exactly what the snapshot file will use (e.g. `[platforms."Cetes"]`).
2. Set:
   - `type`: `sofipo_fixed` (deposits), `sofipo_on_demand` (savings you can pull any time), `variable` (stocks, crypto), `retirement`, or `manual_asset`. This picks its tab in Inversiones.
   - `returns`: how its monthly return is measured: `interest` (fixed-rate deposits), `gain_change` (the app shows gains), `statement` (monthly statements with contributions), or `estimated` (no return figure).
   - `mm_account`: its Money Manager account name, if you log transfers to it; otherwise `""`.
   - `status = "open"`, `opened = "YYYY-MM-DD"`.
3. From the next monthly update on, its screenshot is expected (a missing one blocks saving).

## Close an account

1. In its block: `status = "closed"`, `closed = "YYYY-MM-DD"` (the date it reached zero).
2. Its history stays on every chart. Snapshots after that date no longer expect it; if it still appears, you get a warning.

## Check

Ask Claude to run `tools/validate_snapshot.py` on the next pending month; it confirms the account list.

## Change log
- 2026-09-28: Created (accounts moved to one block each).
