"""
Read Money Manager Excel exports into one clean table.

Each export is one sheet. Transfers appear as two rows (Transfer-Out and Transfer-In)
with the same timestamp; the Category column holds the other account.

Combining exports (decided 2026-09-29): each export owns the dates it covers, read from Money Manager's file name
("Money Manager Report 2026-10-01 ~ 10-31.xlsx") and cut off at its last transaction. Newer files replace older
copies of the same dates, so an expense edited between exports (e.g. an "IN NU" tag removed) is never counted twice.
The first exports were annual; from October 2026 Memo sends one file per month (last month only).
"""
import hashlib
import os
import re
from datetime import datetime
from pathlib import Path

import pandas as pd

TYPE_MAP = {
    "Exp.": "expense",
    "Income": "income",
    "Transfer-Out": "transfer_out",
    "Transfer-In": "transfer_in",
}
TEXT_COLS = {"Accounts": "account", "Category": "category", "Subcategory": "subcategory",
             "Note": "note", "Description": "description"}
REQUIRED = ["Period", "Income/Expense", "Amount", "Currency", *TEXT_COLS]
COLUMNS = ["timestamp", "date", "month", "year", "account", "category", "subcategory",
           "note", "description", "amount", "type", "counterpart", "source_file", "row_key"]


def read_export(path):
    """Read one export. Raises ValueError with a plain message if something is off."""
    path = Path(path)
    raw = pd.read_excel(path)
    missing = [c for c in REQUIRED if c not in raw.columns]
    if missing:
        raise ValueError(f"{path.name}: missing columns {missing}. Is this a Money Manager export?")

    currencies = set(raw["Currency"].dropna().unique())
    if currencies - {"MXN"}:
        raise ValueError(f"{path.name}: found currency {sorted(currencies - {'MXN'})}; only MXN is supported.")

    unknown = set(raw["Income/Expense"].dropna().unique()) - set(TYPE_MAP)
    if unknown:
        raise ValueError(f"{path.name}: unknown transaction type {sorted(unknown)}.")

    df = pd.DataFrame()
    df["timestamp"] = pd.to_datetime(raw["Period"])
    df["date"] = df["timestamp"].dt.strftime("%Y-%m-%d")
    df["month"] = df["timestamp"].dt.strftime("%Y-%m")
    df["year"] = df["timestamp"].dt.year
    for src, dst in TEXT_COLS.items():
        df[dst] = raw[src].fillna("").astype(str).str.strip()
    df["amount"] = raw["Amount"].astype(float).round(2)
    df["type"] = raw["Income/Expense"].map(TYPE_MAP)
    is_transfer = df["type"].isin(["transfer_out", "transfer_in"])
    df["counterpart"] = df["category"].where(is_transfer, "")
    df["source_file"] = path.name
    df["row_key"] = df.apply(_row_key, axis=1)
    return df[COLUMNS]


def _row_key(r):
    raw = f"{r.timestamp.isoformat()}|{r.account}|{r.type}|{r.amount:.2f}|{r.category}|{r.note}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


_RANGE = re.compile(r"(\d{4})-(\d{2})-(\d{2})\s*~\s*(?:(\d{4})-)?(\d{2})-(\d{2})")
MATCH = ["timestamp", "account", "type", "amount", "category"]  # an edit to note/subcategory/description is the same row


def export_coverage(path, df):
    """(start, end, from_name): the dates an export speaks for. The range comes from the file name (the end year
    is the start's, +1 if it wraps). If that range runs past the day the file was saved (an annual file saved in
    September), it stops at the file's last transaction, so it never claims months it couldn't contain.
    Without a readable name: its first and last transaction. end is None when there's nothing to claim."""
    first, last = (df["date"].min(), df["date"].max()) if len(df) else (None, None)
    m = _RANGE.search(Path(path).name)
    if not m:
        return first, last, False
    y, mo, d, y2, mo2, d2 = m.groups()
    end_year = int(y2) if y2 else int(y) + (1 if (mo2, d2) < (mo, d) else 0)
    end = f"{end_year}-{mo2}-{d2}"
    saved = datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d")
    if end > saved:
        end = last
    return f"{y}-{mo}-{d}", end, True


def load_exports(paths):
    """Read several exports and combine them: newest file first, each taking the dates no newer file covers.

    Returns (table, report). report: files (newest first: name, start, end, from_name, rows_in_file, rows_used),
    files_used / files_skipped (names), replaced (older rows superseded by a newer file), vanished (older rows,
    inside a newer file's dates, with no match there: deleted or changed in Money Manager).
    """
    files = []
    for p in paths:
        df = read_export(p)
        start, end, named = export_coverage(p, df)
        files.append({"name": Path(p).name, "df": df, "start": start, "end": end, "named": named,
                      "mtime": os.path.getmtime(p)})
    files.sort(key=lambda f: (f["mtime"], f["end"] or "", f["name"]), reverse=True)

    claimed, taken, info, replaced, vanished = [], [], [], 0, []
    for f in files:
        df = f["df"]
        covered = pd.Series(False, index=df.index)
        for start, end in claimed:
            covered |= (df["date"] >= start) & (df["date"] <= end)
        superseded = df[covered]
        if len(superseded):
            replaced += len(superseded)
            vanished.append(_unmatched(superseded, pd.concat(taken, ignore_index=True)))
        taken.append(df[~covered])
        if f["end"]:
            claimed.append((f["start"], f["end"]))
        info.append({"name": f["name"], "start": f["start"], "end": f["end"], "from_name": f["named"],
                     "rows_in_file": len(df), "rows_used": int((~covered).sum())})

    table = pd.concat(taken, ignore_index=True) if taken else pd.DataFrame(columns=COLUMNS)
    table = table.sort_values("timestamp", kind="stable").reset_index(drop=True)
    gone = pd.concat(vanished, ignore_index=True) if vanished else pd.DataFrame(columns=COLUMNS)
    gaps = _gaps(info)
    warnings = [f"Faltan movimientos del {a} al {b}: ninguna exportación cubre esas fechas. ¿Falta un archivo, "
                f"o se guardó antes de que terminara el mes?" for a, b in gaps]
    warnings += _overrides(info)
    return table, {"files": info, "files_used": [i["name"] for i in info if i["rows_used"]],
                   "files_skipped": [i["name"] for i in info if not i["rows_used"]],
                   "replaced": replaced, "vanished": gone, "gaps": gaps, "warnings": warnings}


def _gaps(files):
    """Stretches of days between the first and last covered date that no export covers."""
    spans = sorted((f["start"], f["end"]) for f in files if f["end"])
    out, reach = [], None
    for start, end in spans:
        if reach and start > _next_day(reach):
            out.append((_next_day(reach), _prev_day(start)))
        reach = end if reach is None else max(reach, end)
    return out


def _overrides(files):
    """A file treated as newer that starts before an older file it overlaps: usually an old export saved again."""
    out = []
    for i, new in enumerate(files):  # newest first
        for old in files[i + 1:]:
            if new["end"] and old["end"] and new["start"] < old["start"] <= new["end"]:
                out.append(f"{new['name']} ({new['start']} a {new['end']}) se guardó después de {old['name']} y le "
                           f"gana sus fechas desde {old['start']}. ¿Se volvió a guardar un archivo viejo?")
    return out


def _next_day(d):
    return (pd.Timestamp(d) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")


def _prev_day(d):
    return (pd.Timestamp(d) - pd.Timedelta(days=1)).strftime("%Y-%m-%d")


def _unmatched(older, newer):
    """Rows of `older` with no counterpart in `newer` (matched on MATCH, one for one)."""
    a, b = older.copy(), newer[MATCH].copy()
    a["_n"] = a.groupby(MATCH).cumcount()
    b["_n"] = b.groupby(MATCH).cumcount()
    m = a.merge(b, on=MATCH + ["_n"], how="left", indicator=True)
    return m[m["_merge"] == "left_only"][COLUMNS]


def find_duplicates(df):
    """Possible duplicates: rows sharing date, amount, account and category with another row (all copies).
    For Memo to review; never removed automatically. (Decided 2026-09-29.)"""
    return df[df.duplicated(["date", "amount", "account", "category"], keep=False)]


def unmatched_transfers(df):
    """Transfer rows whose other half (same time, amount, swapped accounts) is missing."""
    t = df[df["type"].isin(["transfer_out", "transfer_in"])].copy()
    t["_i"] = t.index
    outs, ins = t[t["type"] == "transfer_out"], t[t["type"] == "transfer_in"]
    pairs = outs.merge(
        ins,
        left_on=["timestamp", "amount", "account", "counterpart"],
        right_on=["timestamp", "amount", "counterpart", "account"],
        suffixes=("_out", "_in"),
    )
    matched = set(pairs["_i_out"]) | set(pairs["_i_in"])
    return t[~t["_i"].isin(matched)].drop(columns="_i")


def summarize(df):
    """Per-year totals used to check the import against the Excel."""
    out = {}
    for year, g in df.groupby("year"):
        amt = g.groupby("type")["amount"].sum()
        out[int(year)] = {
            "rows": len(g),
            "expenses": round(float(amt.get("expense", 0.0)), 2),
            "income": round(float(amt.get("income", 0.0)), 2),
            "transfers_net": round(float(amt.get("transfer_in", 0.0) - amt.get("transfer_out", 0.0)), 2),
        }
    return out
