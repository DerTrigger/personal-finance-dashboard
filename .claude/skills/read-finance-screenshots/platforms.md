# Reading guide, one platform at a time

How each app's screen maps to the columns of `pending-snapshot.csv`. The draft already has every item from last
month with its name, type and fixed terms; you fill the blanks. Read the platform you're on, not the whole file.

## General rules (all platforms)

- **Amounts:** drop `$`, commas and `MXN`; keep two decimals. Profuturo prints the cents small (`$12,345.67` looks
  like `12,345` + `.67`): include them. (Every number in this guide is made up.)
- **Percentages become fractions:** 13.00% → `0.13`, 9.5% → `0.095`.
- **Dates become YYYY-MM-DD.** FINSUS writes them like `15 May 2026` / `18 Ago 2026` / `19 Oct 2026` and mixes
  Spanish and English month names: Ene/Jan, Feb, Mar, Abr/Apr, May, Jun, Jul, Ago/Aug, Sep, Oct, Nov, Dic/Dec.
  Kubo already writes `2026-10-19`.
- **Keep the draft's names exactly** (accents, spaces, capitals). A name that changes looks like one item gone and
  a new one added. Screen names sometimes carry decoration: drop emojis, `*` and ★ (`Cajita Ahorro 🚀` → `Cajita Ahorro`).
- **Every amount goes in `value`**, including each platform's `total` row. `principal` is only for deposits and
  statements.
- **Numbers carried over from the draft stay as they are** (e.g. `360.0` for a term): check them against the
  screen, but don't reformat them.
- **Read what's shown; compute only the totals this guide says to compute.**
- **If a number is cut off, blurry, or missing, leave it blank and list it** for Memo. A blank is caught; a guess
  isn't. Screenshots of long lists overlap: read each item once.
- **New item** (a new deposit, a new holding): add a row with every column you can read, in the same style as the
  rows around it. **Item not on the screens anymore** (sold, matured): delete its row and say so.

## Nu (`sofipo_on_demand`)

Screen: **Cajitas** list (usually two screenshots).

Only four Cajitas count: `Cajita Ahorro`, `Fondo de Emergencia`, `Inversión`, `Retiro`.
Every other Cajita (Available Money for the Month, Transportation, Renta y Servicios, $ Ya Gastado, Kass y Julia,
and any new one) is a spending envelope: skip it.

Per Cajita card:
- `value`: the balance under the name.
- `gain`: the green amount after the ↑ arrow (growth to date).
- `annual_rate`: the purple badge on the picture (13.00% → `0.13`).

Nu `total` row: **the sum of the four Cajitas.** Not "Total en Cajitas" at the top: that includes the envelopes.

Cross-check: every card on the screens (the four plus all the envelopes) should add up to "Total en Cajitas", and
their green amounts to "Así ha crecido tu saldo en Cajitas". If they don't, a card is hidden or cut off between two
screenshots (the second screenshot often starts with a card whose name is scrolled away).

## FINSUS (`sofipo_fixed`)

Screens: **Apartados** (one) and **Detalle inversión** (one per deposit).

Apartados → one `on_demand` row per box (`finsus +`, `#cosechamayo`, ...):
- `value`: "Saldo apartado".
- `annual_rate`: "Tu dinero en vista con rendimiento del X% anual".

Detalle inversión → one `deposit` row per deposit (name = the title at the top, e.g. `Plazo al 10%`):
- `principal` **and** `value`: "Monto de inversión" (a deposit's value is its principal; interest isn't added).
- `term_days`: "Plazo" (180 días → `180`).
- `payout`: "Pago de rendimientos: Mensual" → `monthly`.
- `start_date` / `end_date`: "Fecha de inicio" / "Fecha de fin".
- `annual_rate`: "Tasa anual".
- `interest_total`: "Rendimientos brutos" (gross: before tax). `interest_basis`: `gross`.
- Ignore "Días transcurridos" and the "Pago de rendimientos" payment list.

Existing deposits already carry their terms; just check they're still listed and the terms match. FINSUS `total`:
**the sum of its on_demand boxes and deposits** (the app doesn't show one).

## Kubo Financiero (`sofipo_fixed`)

Screen: **Inversión → Mis inversiones → Inversiones activas**, one block per "Meta" (a block can continue on the
next screenshot).

One `deposit` row per Meta (name = the green Meta name):
- `principal` **and** `value`: "Monto invertido".
- `interest_total`: "Intereses a recibir" (already net of tax). `interest_basis`: `net`.
- `annual_rate`: "Tasa". `term_days`: "Plazo".
- `start_date`: "Fecha de inicio". `end_date`: "Fecha Disponiblidad".
- `payout`: "Al vencimiento" → `at_maturity`.
- "Monto a recibir" is principal + interest: don't store it; use it to check your two numbers add up.

Kubo `total`: **the sum of its deposits.** A deposit whose end date has passed and isn't on the screen anymore was
paid out: delete its row. If one past its end date *is* still shown, keep it and flag it (paid or renewed?).

## GBM (`variable`)

Screens: **Mi portafolio**. The first screen shows only the top few holdings of each market; the expanded lists
("Ver más instrumentos", usually titled "Mi portafolio" with a market picker) show the rest. Read every holding once.
A market that shows a "Ver más instrumentos" link needs its expanded list; one without the link is already complete.
Compare against the draft: a holding in the draft but on no screen is either sold or on a screen that's missing, so
ask before deleting it.

Per holding line (`ABC *  ★   12 • $3,456.78 MXN` / `↗ 25.00% • $691.36`):
- `name`: the ticker as shown, without `*` or ★ (`DANHOS 13`, `PE&OLES`, `GBMINT BO`).
- `units`: the number before the •.
- `value`: the MXN amount.
- `gain`: the amount after the percentage. **Green with ↗ is a gain; red with ↙ is a loss: write it negative.**
- `gain_pct`: the percentage as a fraction, same sign as the gain (red 12.34% → `-0.1234`).
- `ticker`, `asset_type`, `market`: carried over for existing holdings. For a new one: the section tells the market
  (Mercado de Capitales Global (SIC) → ETF or stock; Nacional → FIBRA or stock; Fondos de Inversión → fund).

GBM `total` and `CASH` (the "Liquidez" section): the portfolio screens show Liquidez only as a percentage. Since
2026-09-29 the monthly checklist includes **a screenshot of the account's total value**: read `total` from it, then
**CASH = total − the sum of the holdings** (a small amount, near the Liquidez % of the total; if it's far off, a
holding was misread). If that screenshot is missing, leave both blank and ask Memo for it.

## Bitso (`variable`)

Screen: **Wallet**.
- `total`: "Combined balance".
- One `holding` per coin card (`BTC`, `ETH`): `value` = the MXN amount on the right; `units` = the coin amount
  (`0.00123456 BTC` → `0.00123456`). Bitso shows no gain: leave `gain` and `gain_pct` blank.

## Allianz PPR (`retirement`)

- `total`: **the app's current total**, from its own screenshot (on the checklist since 2026-09-29; decided
  2026-09-28: the current total wins over the last statement). If only a statement arrived, leave `total` blank and
  ask Memo for the current-total screenshot.
- **A statement** ("Edo. Cuenta YYYY-MM") adds one extra row: `item_type` `statement`, `name` `Monthly statement`,
  `account_type` `retirement`, `as_of` = the statement's period end ("Fechas de Corte" second date, `31/08/2026` →
  `2026-08-31`), `value` = "Valor Total", `principal` = "Aportaciones Acumuladas". The draft never includes
  statements, so you can't see whether it's new: add it anyway. The check refuses one that's already saved, and
  then you just remove the row.

## Profuturo (`retirement`)

Screen: **Saldos**.
- `total`: "Saldo total".
- `subaccount` rows: `Ahorro para el retiro`, `Ahorro voluntario`, and "Ahorro para la vivienda", which is stored as
  `Ahorro para la vivienda (Infonavit)` (keep the draft's name).

## Manual (`manual_asset`)

Car and "Activos" have no screenshot. They carry over unchanged unless Memo gives a new value.
