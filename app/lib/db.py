"""
Build finance.db from the source files. The database is derived: it's rebuilt from scratch
every time, so re-running never duplicates anything and fixing a source file fixes the dashboard.

Sources: Money Manager exports, investment-snapshots.csv, adjustments.csv (optional).
The new database is written to a temporary file first and only replaces the old one if the build succeeds.
"""
import hashlib
import os
import sqlite3
from contextlib import closing
from pathlib import Path

import pandas as pd

from app.lib import moneymanager as mm

SNAP_REQUIRED = ["as_of", "platform", "account_type", "item_type", "name", "value"]
ADJ_COLS = ["date", "account", "amount", "reason", "approved_on"]
IMPORT_FILE_COLS = ["name", "start", "end", "from_name", "rows_in_file", "rows_used"]

VIEWS = """
CREATE VIEW v_net_worth AS
    SELECT as_of, ROUND(SUM(value), 2) AS net_worth
    FROM snapshot_items
    WHERE item_type IN ('total', 'manual_asset')
    GROUP BY as_of;

CREATE VIEW v_net_worth_by_type AS
    SELECT as_of, account_type, platform, ROUND(SUM(value), 2) AS value
    FROM snapshot_items
    WHERE item_type IN ('total', 'manual_asset')
    GROUP BY as_of, account_type, platform;

CREATE VIEW v_monthly_cashflow AS
    SELECT month,
           ROUND(SUM(CASE WHEN type = 'income' THEN amount ELSE 0 END), 2) AS income,
           ROUND(SUM(CASE WHEN type = 'expense' THEN amount ELSE 0 END), 2) AS expenses,
           ROUND(SUM(CASE WHEN type = 'income' THEN amount WHEN type = 'expense' THEN -amount ELSE 0 END), 2)
               AS net_income,
           ROUND(SUM(CASE WHEN type = 'income' THEN amount WHEN type = 'expense' THEN -amount ELSE 0 END)
                 / NULLIF(SUM(CASE WHEN type = 'income' THEN amount ELSE 0 END), 0), 4) AS savings_rate
    FROM transactions
    GROUP BY month;

CREATE VIEW v_deposits AS
    SELECT as_of, platform, name, principal, annual_rate, term_days, start_date, end_date,
           payout, interest_total, interest_basis
    FROM snapshot_items
    WHERE item_type = 'deposit';
"""


def read_snapshots(path):
    df = pd.read_csv(path, encoding="utf-8-sig", dtype={"as_of": str})
    missing = [c for c in SNAP_REQUIRED if c not in df.columns]
    if missing:
        raise ValueError(f"{Path(path).name}: missing columns {missing}.")
    return df


def read_adjustments(path):
    if not Path(path).exists():
        return pd.DataFrame(columns=ADJ_COLS)
    df = pd.read_csv(path, encoding="utf-8-sig")
    missing = [c for c in ADJ_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"{Path(path).name}: missing columns {missing}.")
    return df[ADJ_COLS]


def accounts_table(settings, snapshots):
    rows = [{"name": n, "type": a["type"], "in_net_worth": int(a["in_net_worth"])}
            for n, a in settings.get("accounts", {}).items()]
    known = {r["name"] for r in rows}
    for platform, acc_type in snapshots[["platform", "account_type"]].drop_duplicates().itertuples(index=False):
        if platform not in known:
            rows.append({"name": platform, "type": acc_type, "in_net_worth": 1})
            known.add(platform)
    return pd.DataFrame(rows)


def build_database(db_path, export_paths, snapshots_csv, adjustments_csv, settings):
    """Rebuild the database. Returns a report of row counts and which exports were used."""
    db_path = Path(db_path)
    tx, mm_report = mm.load_exports(export_paths)
    snaps = read_snapshots(snapshots_csv)
    adj = read_adjustments(adjustments_csv)

    tmp = db_path.with_suffix(".building")
    if tmp.exists():
        tmp.unlink()
    # closing(): on Windows an open connection locks the file and blocks the replace below.
    with closing(sqlite3.connect(tmp)) as c:
        tx.assign(timestamp=tx["timestamp"].astype(str)).to_sql("transactions", c, index=False)
        snaps.to_sql("snapshot_items", c, index=False)
        adj.to_sql("adjustments", c, index=False)
        accounts_table(settings, snaps).to_sql("accounts", c, index=False)
        # How the exports were combined, for the Revisión screen: files and their dates, rows that vanished
        pd.DataFrame(mm_report["files"], columns=IMPORT_FILE_COLS).to_sql("import_files", c, index=False)
        gone = mm_report["vanished"]
        gone.assign(timestamp=gone["timestamp"].astype(str)).to_sql("import_vanished", c, index=False)
        pd.DataFrame({"message": mm_report["warnings"]}, dtype=str).to_sql("import_warnings", c, index=False)
        c.executescript(VIEWS)
        c.commit()
    os.replace(tmp, db_path)
    return {"transactions": len(tx), "snapshot_items": len(snaps), "adjustments": len(adj), **mm_report}


def read_optional(db_path, name, columns):
    """A table that older databases may not have yet (empty with these columns if missing)."""
    try:
        return read_table(db_path, name)
    except Exception:
        return pd.DataFrame(columns=columns)


def query(db_path, sql, params=()):
    """Run a read query and close the connection (read-only, so the file never stays locked)."""
    uri = Path(db_path).resolve().as_uri() + "?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as c:
        return c.execute(sql, params).fetchall()


def read_table(db_path, name):
    """A whole table or view as a DataFrame (read-only; the connection is closed right after)."""
    uri = Path(db_path).resolve().as_uri() + "?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as c:
        return pd.read_sql_query(f'SELECT * FROM "{name}"', c)


def fingerprint(db_path):
    """A hash of every table's contents, to prove two builds are identical."""
    h = hashlib.sha256()
    with closing(sqlite3.connect(db_path)) as c:
        tables = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        for t in tables:
            for row in sorted(c.execute(f'SELECT * FROM "{t}"').fetchall(), key=repr):
                h.update(repr((t, row)).encode("utf-8"))
    return h.hexdigest()
