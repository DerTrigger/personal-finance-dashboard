"""
Check a month of screenshot readings before it's saved to investment-snapshots.csv.

The pending file has the same columns as investment-snapshots.csv and one date per file
(Allianz statement rows may carry their own statement date).
validate() returns (errors, warnings): errors block saving, warnings go in the confirm table for Memo.
"""
import shutil
from datetime import date
from pathlib import Path

import pandas as pd

from app.lib import config as cfg
from app.lib import interest as it
from app.lib.db import SNAP_REQUIRED

KEY = ["as_of", "platform", "item_type", "name"]
NUMERIC = ["units", "principal", "value", "gain", "gain_pct", "annual_rate", "term_days", "interest_total"]
TRACKED = ("holding", "cajita", "deposit", "on_demand", "subaccount")  # items compared month to month
NOT_PARTS = ("total", "statement")


def _clean(df):
    df = df.copy()
    df["as_of"] = df["as_of"].astype(str)
    for col in NUMERIC:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def _main(df):
    """Every row except statements (which carry the statement's own date)."""
    return df[df["item_type"] != "statement"]


def _is_date(text):
    try:
        date.fromisoformat(text)
        return len(text) == 10
    except ValueError:
        return False


def snapshot_dates(df):
    """Sorted snapshot dates, ignoring statement dates."""
    return sorted(_main(_clean(df))["as_of"].unique())


def platform_totals(df):
    """Total per platform: its 'total' row, or the sum of its manual assets."""
    m = _main(_clean(df))
    manual = m[m["item_type"] == "manual_asset"].groupby("platform")["value"].sum()
    totals = m[m["item_type"] == "total"].groupby("platform")["value"].sum()
    return {k: float(v) for k, v in {**manual.to_dict(), **totals.to_dict()}.items()}


def previous_snapshot(history, as_of):
    """(date, rows) of the latest snapshot before as_of, or (None, empty)."""
    hist = _main(_clean(history))
    earlier = [d for d in snapshot_dates(hist) if d < as_of]
    if not earlier:
        return None, hist.iloc[0:0]
    return earlier[-1], hist[hist["as_of"] == earlier[-1]]


def validate(pending, history, settings):
    missing = [c for c in SNAP_REQUIRED if c not in pending.columns]
    if missing:
        return [f"Al archivo le faltan columnas {missing}."], []

    checks = settings["checks"]
    errors, warnings = [], []
    p, hist = _clean(pending), _clean(history)
    main = _main(p)

    # Dates
    for d in sorted(p["as_of"].unique()):
        if not _is_date(d):
            errors.append(f"'{d}' no es una fecha con formato AAAA-MM-DD.")
    dates = sorted(main["as_of"].unique())
    if len(dates) > 1:
        errors.append(f"El archivo tiene más de una fecha {dates}. Un mes por archivo.")
    as_of = dates[-1] if dates else ""
    if as_of in snapshot_dates(hist):
        errors.append(f"{as_of} ya está guardado en investment-snapshots.csv.")
    saved = set(map(tuple, hist[KEY].values.tolist()))
    for r in p[p["item_type"] == "statement"].itertuples():
        if (r.as_of, r.platform, r.item_type, r.name) in saved:
            errors.append(f"El estado de cuenta de {r.platform} del {r.as_of} ya está guardado.")

    # Duplicates and missing values
    for key in p[p.duplicated(KEY, keep=False)][KEY].drop_duplicates().itertuples(index=False):
        errors.append(f"Fila duplicada: {key.platform} {key.item_type} '{key.name}'.")
    for r in p[p["value"].isna()].itertuples():
        errors.append(f"{r.platform} '{r.name}' no tiene valor.")

    # Accounts: every account open on this date must be there
    known = set(cfg.platforms(settings))
    expected = cfg.expected_platforms(settings, as_of)
    found = set(main["platform"])
    for platform in expected:
        if platform not in found:
            errors.append(f"Falta {platform}. ¿Falta una captura de pantalla?")
    for platform in sorted(found - known):
        warnings.append(f"{platform} no es una cuenta registrada. Revisa el nombre o agrégala en settings.toml.")
    for platform in sorted((found & known) - set(expected)):
        warnings.append(f"{platform} aparece, pero en settings.toml está cerrada (o todavía no abierta) "
                        f"en {as_of}.")

    # Parts must add up to each platform's total
    for platform, g in main.groupby("platform"):
        if set(g["item_type"]) == {"manual_asset"}:
            continue
        n_totals = int((g["item_type"] == "total").sum())
        if n_totals != 1:
            errors.append(f"{platform} necesita exactamente una fila de total (hay {n_totals}).")
            continue
        parts = g[~g["item_type"].isin(NOT_PARTS)]
        if parts.empty:
            continue
        total = float(g.loc[g["item_type"] == "total", "value"].iloc[0])
        parts_sum = float(parts["value"].sum())
        if abs(parts_sum - total) > checks["sum_tolerance"]:
            errors.append(f"{platform}: las partes suman {parts_sum:,.2f} pero el total es {total:,.2f} "
                          f"(diferencia {parts_sum - total:,.2f}).")

    # Nu: only the four Cajitas that count
    for r in main[main["item_type"] == "cajita"].itertuples():
        if r.name not in settings["nu"]["cajitas"]:
            errors.append(f"La Cajita de Nu '{r.name}' no es una de las cuatro que cuentan.")

    # Holdings: gain % must match gain / amount invested
    h = main[(main["item_type"] == "holding") & main["gain"].notna() & main["gain_pct"].notna()]
    for r in h.itertuples():
        invested = r.value - r.gain
        if invested and abs(r.gain / invested - r.gain_pct) > checks["gain_pct_tolerance"]:
            errors.append(f"{r.platform} '{r.name}': la ganancia mostrada es {r.gain_pct:.2%} pero ganancia / "
                          f"monto invertido da {r.gain / invested:.2%}.")

    # Deposits: interest shown vs. calculated from the terms
    isr = settings["tax"]["isr_rate"]
    deposits = main[main["item_type"] == "deposit"].dropna(
        subset=["principal", "annual_rate", "start_date", "end_date", "interest_total"])
    for r in deposits.itertuples():
        calc = it.deposit_interest(r, isr)
        if abs(calc - r.interest_total) > checks["interest_tolerance"]:
            warnings.append(f"{r.platform} '{r.name}': interés mostrado {r.interest_total:,.2f}, "
                            f"calculado {calc:,.2f}. Revisa los términos.")
    for r in main[(main["item_type"] == "deposit") & main["end_date"].notna()].itertuples():
        if str(r.end_date) < r.as_of:
            warnings.append(f"{r.platform} '{r.name}' venció el {r.end_date} pero sigue en la lista. "
                            f"¿Se pagó o se renovó? Una renovación necesita las nuevas fechas de inicio y fin.")

    # Compared with last month
    prev_date, prev = previous_snapshot(hist, as_of)
    if prev_date:
        before, now = platform_totals(prev), platform_totals(main)
        for platform in sorted(now):
            if before.get(platform):
                change = (now[platform] - before[platform]) / abs(before[platform])
                if abs(change) > checks["jump_warn_pct"]:
                    warnings.append(f"{platform} cambió {change:+.0%} desde {prev_date} "
                                    f"({before[platform]:,.2f} -> {now[platform]:,.2f}). Revisa la captura.")
        keys_before = _items(prev)
        keys_now = _items(main)
        for platform, name in sorted(keys_before - keys_now):
            warnings.append(f"{platform} '{name}' estaba el {prev_date} y ya no aparece "
                            f"(¿vendido, vencido o faltó en la captura?).")
        for platform, name in sorted(keys_now - keys_before):
            warnings.append(f"{platform} '{name}' es nuevo este mes.")
        # Car and Activos carry over unchanged unless Memo gives a new value
        was = prev[prev["item_type"] == "manual_asset"].set_index(["platform", "name"])["value"]
        for r in main[main["item_type"] == "manual_asset"].itertuples():
            before_v = was.get((r.platform, r.name))
            if before_v is not None and abs(float(r.value) - float(before_v)) > checks["sum_tolerance"]:
                warnings.append(f"{r.platform} '{r.name}' cambió de {float(before_v):,.2f} a {float(r.value):,.2f}. "
                                f"Solo cambia si Memo dio un valor nuevo.")

    return errors, warnings


def _items(df):
    t = df[df["item_type"].isin(TRACKED)]
    return set(zip(t["platform"], t["name"]))


def confirm_table(pending, history):
    """One line per platform for Memo to confirm: total, last month's total, change, number of items read."""
    main = _main(_clean(pending))
    as_of = max(main["as_of"]) if len(main) else ""
    _, prev = previous_snapshot(history, as_of)
    now, before = platform_totals(main), platform_totals(prev)
    rows = []
    for platform in sorted(now):
        g = main[(main["platform"] == platform) & ~main["item_type"].isin(NOT_PARTS)]
        last = before.get(platform)
        rows.append({"platform": platform, "total": now[platform], "last_month": last,
                     "change": None if last is None else round(now[platform] - last, 2), "items": len(g)})
    return pd.DataFrame(rows, columns=["platform", "total", "last_month", "change", "items"])


# --- Next month's draft, and scoring a first pass -------------------------------------

# Numbers that change every month and are read from the screens again. Everything else carries over:
# item names, deposit terms (a deposit's value is its principal), manual assets (changed only when Memo says).
TO_READ = {
    "total": ["value"],
    "cajita": ["value", "gain", "annual_rate"],
    "on_demand": ["value", "annual_rate"],
    "holding": ["units", "value", "gain", "gain_pct"],
    "subaccount": ["value"],
}
COMPARED = NUMERIC + ["ticker", "asset_type", "start_date", "end_date", "payout", "interest_basis"]


def draft(history, as_of, from_date=None):
    """Next month's pending snapshot, drafted from the last one before `as_of` (or from `from_date`):
    same items and names, terms carried over, the numbers to read blanked. Statements aren't copied."""
    h = _main(_clean(history))
    if from_date is None:
        earlier = [d for d in snapshot_dates(h) if d < as_of]
        if not earlier:
            raise ValueError(f"No hay un corte anterior a {as_of} para empezar el borrador.")
        from_date = earlier[-1]
    rows = h[h["as_of"] == from_date].copy()
    rows["as_of"], rows["confirmed_on"] = as_of, None
    if "notes" in rows:
        rows["notes"] = None
    for item_type, cols in TO_READ.items():
        rows.loc[rows["item_type"] == item_type, [c for c in cols if c in rows]] = None
    return rows.reset_index(drop=True)


def compare(first, final):
    """How the first reading did against the confirmed one, per platform: items, fields compared, fields
    corrected, items missed, items read that aren't there. Numbers within half a cent count as equal."""
    key = ["platform", "item_type", "name"]
    a, b = _clean(first).set_index(key), _clean(final).set_index(key)  # statements count too (read from a screen)
    out = []
    for platform in sorted(set(a.index.get_level_values(0)) | set(b.index.get_level_values(0))):
        fa = a[a.index.get_level_values(0) == platform]
        fb = b[b.index.get_level_values(0) == platform]
        both = fa.index.intersection(fb.index)
        fields = corrected = 0
        for k in both:
            for col in [c for c in COMPARED if c in fb.columns]:
                x, y = fa.at[k, col] if col in fa.columns else None, fb.at[k, col]
                if _blank(x) and _blank(y):
                    continue
                fields += 1
                if col in NUMERIC:
                    same = not _blank(x) and not _blank(y) and abs(float(x) - float(y)) < 0.005
                else:
                    same = str(x).strip() == str(y).strip()
                corrected += not same
        out.append({"platform": platform, "items": len(fb), "fields": fields, "corrected": corrected,
                    "missing": len(fb.index.difference(fa.index)), "extra": len(fa.index.difference(fb.index))})
    return pd.DataFrame(out, columns=["platform", "items", "fields", "corrected", "missing", "extra"])


def _blank(x):
    return x is None or (isinstance(x, float) and x != x) or (isinstance(x, str) and not x.strip())


def read_csv(path):
    """Read a snapshot CSV as text, so values are saved exactly as written."""
    return pd.read_csv(path, encoding="utf-8-sig", dtype=str, keep_default_na=False)


def append_snapshot(pending_path, csv_path, settings, confirmed_on):
    """Validate a pending month and append it to investment-snapshots.csv.

    Raises ValueError (and changes nothing) if there's any error. Keeps the previous file as .bak.
    Returns the number of rows added.
    """
    pending, history = read_csv(pending_path), read_csv(csv_path)
    errors, _ = validate(pending.replace("", None), history.replace("", None), settings)
    extra = [c for c in pending.columns if c not in history.columns]
    if extra:
        errors.append(f"El archivo pendiente tiene columnas que el guardado no tiene: {extra}.")
    if errors:
        raise ValueError("No se guardó. " + " ".join(errors))

    rows = pending.reindex(columns=history.columns, fill_value="")
    rows["confirmed_on"] = confirmed_on
    csv_path = Path(csv_path)
    shutil.copy2(csv_path, csv_path.with_name(csv_path.name + ".bak"))
    needs_newline = csv_path.read_bytes()[-1:] not in (b"\n", b"")
    with open(csv_path, "a", encoding="utf-8", newline="") as f:
        if needs_newline:
            f.write("\r\n")
        rows.to_csv(f, header=False, index=False, lineterminator="\r\n")
    return len(rows)
