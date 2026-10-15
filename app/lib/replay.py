"""
Replay: three simulated months (the three month-ends after the latest saved snapshot) run through the real monthly
pipeline, with planted errors.

A truth table records what happens to each platform each month: money put in, what it earned, deposits that
mature, a stock sale. From it the replay writes each month's inputs the way the monthly close receives them: a
pending snapshot (as if read from screenshots) and new Money Manager rows. Then it runs the real pipeline
(validate -> append -> build the database -> reconcile / why it changed / data check) and compares the results
with the truth table.

Planted errors
- Month 1: a missing screenshot and a matured deposit still listed (first attempt: must be refused and warned;
  the fixed month then saves), and two possible duplicates in Money Manager.
- Month 2: a transfer logged with the wrong amount.
- Month 3: a stock sale, a new category, a new account, a refund logged as income, and month 2 re-sent with a tag
  removed and one row deleted.
Monthly Money Manager exports cover one month each, as Memo sends them from October 2026.

Works on any baseline: the fake one in the tests, or a copy of the real opening snapshot (tools/run_evals.py).
Everything is written inside `workdir`; the source files are only read.

Interest credited here uses the same formulas the pipeline uses (app/lib/interest.py). Those formulas are checked
separately against the platforms' own figures (tools/check_deposits.py), so the replay tests the plumbing:
that every peso ends up in the right place.
"""
import calendar
import os
import shutil
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

import pandas as pd
from openpyxl import Workbook

from app.lib import config as cfg
from app.lib import db
from app.lib import interest as it
from app.lib import metrics as mx
from app.lib import moneymanager as mm
from app.lib import reconcile as rc
from app.lib import snapshots as sn

N_MONTHS = 3  # the three month-ends after the latest saved snapshot, so the replay works whatever month it is

# What happens each month (deterministic, so every run gives the same answer)
HOLDING_GROWTH = 0.02    # GBM holdings with a gain shown
ESTIMATED_GROWTH = 0.01  # Bitso, Profuturo (no returns shown)
STATEMENT_GROWTH = 0.008  # Allianz
REVALUATION = -0.01      # car and household goods
CONTRIB = {"Nu": 1000.0, "FINSUS": 2000.0, "GBM": 3000.0, "Allianz PPR": 2500.0}
PAYER = "Payroll Account"   # where the money for contributions comes from

# Planted errors by month: 1st month (index 0), 2nd (1), 3rd (2)
MISSING = "Bitso"                          # month 1: its screenshot "didn't arrive"
MISLOG_AT = 1                              # month 2: a transfer logged with the wrong amount
MISLOGGED = ("GBM", 10_000.0, 1_000.0)     #   put in 10,000, logged as 1,000
SALE_AT = 2                                # month 3: the GBM holding with the biggest gain is sold; month 2 re-sent
NEW_ACCOUNT, NEW_CATEGORY = "Mercado Pago", "Regalos de fin de año"
REFUND_NOTE = "Reembolso replay"
TAGGED_NOTE = "Replay tacos IN NU"   # each month: a card charge with the money set aside, card not paid yet
DELETED_NOTE = "Replay gasolina"     # month 3: month 2 is re-sent with this row deleted and the tag above removed

# Same column layout as a real Money Manager export (the second "Accounts" column repeats the amount)
MM_HEADER = ["Period", "Accounts", "Category", "Subcategory", "Note", "MXN",
             "Income/Expense", "Description", "Amount", "Currency", "Accounts"]


@dataclass
class Result:
    checks: list          # dicts: month, name, passed, detail
    truth: pd.DataFrame   # as_of, net_worth, put_in, returns, estimated, revaluation
    db: Path
    workdir: Path
    months: list          # the replayed month-ends

    def check(self, month, name):
        return next(c for c in self.checks if c["month"] == month and c["name"] == name)

    @property
    def ok(self):
        return all(c["passed"] for c in self.checks)


def run(workdir, baseline_csv, export_paths, settings):
    workdir = Path(workdir)
    if workdir.exists() and any(workdir.iterdir()):
        raise ValueError(f"{workdir} ya tiene archivos. Usa una carpeta vacía (no borro nada por mi cuenta).")
    workdir.mkdir(parents=True, exist_ok=True)
    csv_path = workdir / "investment-snapshots.csv"
    shutil.copy2(baseline_csv, csv_path)
    db_path, adj_path = workdir / "finance.db", workdir / "adjustments.csv"
    columns = list(sn.read_csv(csv_path).columns)

    base = _read(baseline_csv)
    prev_date = sn.snapshot_dates(base)[-1]
    prev = _rows(base[(base["as_of"] == prev_date) & (base["item_type"] != "statement")])
    stmts = {r["platform"]: r for r in _rows(
        base[(base["item_type"] == "statement") & (base["as_of"] <= prev_date)].sort_values("as_of"))}
    tx, _ = mm.load_exports(export_paths)
    source_tx = tx
    truth_nw = float(mx.net_worth_series(base).set_index("as_of")["net_worth"][prev_date])

    months = months_after(prev_date)
    resent_month = months[MISLOG_AT][:7]
    checks, truth_rows, monthly, month_rows = [], [], [], {}
    for i, d in enumerate(months):  # i = 0, 1, 2: which month of the replay
        m = _month(prev, stmts, prev_date, d, settings, tx, i)
        folder = workdir / d[:4] / d[:7]
        folder.mkdir(parents=True, exist_ok=True)

        def add(name, passed, detail):
            checks.append({"month": d, "name": name, "passed": bool(passed), "detail": detail})

        # First attempt (month 1): stale screenshots
        if m["first"] is not None:
            first = folder / "pending-first.csv"
            _write(m["first"], columns, first)
            errors, warnings = sn.validate(_read(first), _read(csv_path), settings)
            try:
                sn.append_snapshot(first, csv_path, settings, d)
                refused = False
            except ValueError:
                refused = True
            add("missing screenshot refused", refused and any(f"Falta {m['missing']}" in e for e in errors),
                f"Falta la captura de {m['missing']}: {'rechazado' if refused else 'SE GUARDÓ'}; errores: {errors}")
            if m["stale"]:
                wanted = [f"{p} '{n}' venció" for p, n in m["stale"]]
                hit = [w for w in wanted if any(w in x for x in warnings)]
                add("matured deposit still listed warned", hit == wanted,
                    f"Esperadas {wanted}; avisos: {warnings}")

        # The month as it should be read
        pending = folder / cfg.PENDING_NAME
        _write(m["rows"] + m["new_stmts"], columns, pending)
        errors, warnings = sn.validate(_read(pending), _read(csv_path), settings)
        expected = _expected_warnings(m, prev, settings)
        unexplained = [w for w in warnings if not any(f in w for f in expected)]
        unseen = [f for f in expected if not any(f in w for w in warnings)]
        add("validation", not errors and not unexplained and not unseen,
            f"errores {errors}; avisos sin explicar {unexplained}; avisos esperados que no salieron {unseen}")
        try:
            added = sn.append_snapshot(pending, csv_path, settings, d)
            add("saved", True, f"{added} filas guardadas")
        except ValueError as e:
            add("saved", False, str(e))

        # Money Manager: one export per month (last month only), as Memo sends them from October 2026
        month = d[:7]
        month_rows[month] = _raw_month(source_tx, month) + [_raw(*r) for r in m["mm"]]
        monthly.append(_export(workdir / _name(month), month_rows[month], _saved(d)))
        if i == SALE_AT:  # month 2 re-sent: its tag removed after paying the card, one row deleted
            resent = [r[:4] + ["Replay tacos"] + r[5:] if r[4] == TAGGED_NOTE else r
                      for r in month_rows[resent_month] if r[4] != DELETED_NOTE]
            monthly.append(_export(workdir / _name(resent_month, " (1)"), resent, _saved(d) + 3600))
        db.build_database(db_path, list(export_paths) + monthly, csv_path, adj_path, settings)
        snaps, tx = db.read_table(db_path, "snapshot_items"), db.read_table(db_path, "transactions")
        gone = db.read_table(db_path, "import_vanished")

        before = tx[tx["date"] < f"{months[0][:7]}-01"]
        src_before = source_tx[source_tx["date"] < f"{months[0][:7]}-01"]
        add("earlier months kept", len(before) == len(src_before)
            and abs(before["amount"].sum() - src_before["amount"].sum()) < 0.01,
            f"{len(before)} movimientos antes de {months[0][:7]} (fuente: {len(src_before)})")
        want_gone = [DELETED_NOTE] if i == SALE_AT else []
        add("vanished rows warned", gone["note"].tolist() == want_gone,
            f"desaparecieron {gone['note'].tolist()} (esperado {want_gone})")
        owed = mx.card_pending(tx)
        add("card pending from the latest export only",
            owed["note"].tolist() == [TAGGED_NOTE] and owed["date"].str.startswith(month).all(),
            f"cargos por pagar: {list(zip(owed['date'], owed['note']))}")
        if i == SALE_AT:
            again = tx[tx["month"] == resent_month]
            want = len(month_rows[resent_month]) - 1
            ok = len(again) == want and TAGGED_NOTE not in set(again["note"]) and "Replay tacos" in set(again["note"])
            add("re-sent month not double counted", ok,
                f"{resent_month}: {len(again)} movimientos (esperados {want}); "
                f"etiqueta quitada: {TAGGED_NOTE not in set(again['note'])}")

        # Net worth
        t = m["truth"]
        truth_nw = round(truth_nw + sum(v["put_in"] + v["returns"] for v in t.values()), 2)
        rows_nw = round(sum(r["value"] for r in m["rows"] if r["item_type"] in ("total", "manual_asset")), 2)
        got = mx.net_worth_series(snaps).set_index("as_of")["net_worth"].get(d)
        add("truth table adds up", abs(rows_nw - truth_nw) < 0.01,
            f"suma de las filas {rows_nw:,.2f} vs. tabla de la verdad {truth_nw:,.2f}")
        add("net worth", got is not None and abs(got - truth_nw) < 0.01,
            f"dashboard {got if got is None else f'{got:,.2f}'} vs. verdad {truth_nw:,.2f}")

        # Why it changed
        parts = {
            "put_in": sum(v["put_in"] for v in t.values() if v["kind"] != "revaluation"),
            "returns": sum(v["returns"] for v in t.values() if v["kind"] not in ("estimated", "revaluation")),
            "estimated_returns": sum(v["returns"] for v in t.values() if v["kind"] == "estimated"),
            "revaluation": sum(v["returns"] for v in t.values() if v["kind"] == "revaluation"),
        }
        sale = m["sale"]
        shown = dict(parts)  # what the dashboard should show, which differs from the truth after a sale:
        if sale:             # a sale's realized gain leaves the shown gains, so it reads as money put in
            shown["put_in"] += sale["gain"]
            shown["returns"] -= sale["gain"]
        why = mx.why_changed(snaps, tx, settings)
        why = why[why["end"] == d]
        tol = 0.01 + 1.0 * m["maturities"]  # the platform's own net interest may differ from the formula by < 1
        diffs = {k: (None if why.empty else round(float(why[k].iloc[0]) - v, 2)) for k, v in shown.items()}
        add("why it changed", not why.empty and all(abs(x) <= tol for x in diffs.values()),
            "diferencia vs. verdad: " + ", ".join(f"{k} {v}" for k, v in diffs.items()))

        # Reconciliation flags
        r = rc.reconcile(snaps, prev_date, d, tx, settings)
        flagged = set(r.loc[r["flagged"], "platform"])
        want = set()
        if i == MISLOG_AT:
            want.add(MISLOGGED[0])
        threshold = settings["checks"]["reconcile_gap_mxn"]
        if sale and abs(sale["gain"]) > threshold:
            want.add(sale["platform"])
        gaps = r.loc[r["flagged"], ["platform", "gap"]].to_dict("records")
        add("reconcile flags", flagged == want, f"marcadas {sorted(flagged)} (esperadas {sorted(want)}); {gaps}")
        if i == MISLOG_AT:
            p, put, logged = MISLOGGED
            gap = r.set_index("platform").loc[p, "gap"]
            add("logging mistake flagged", abs(gap - (put - logged)) < 0.01,
                f"{p}: aportado {put:,.2f}, registrado {logged:,.2f}; diferencia marcada {gap} "
                f"(esperada {put - logged:,.2f})")
        if sale:
            row = r.set_index("platform").loc[sale["platform"]]
            ok = (not abs(sale["gain"]) > threshold) or (bool(row["flagged"]) and abs(row["gap"] - sale["gain"]) < 0.01)
            add("stock sale flagged", ok,
                f"{sale['platform']} vendió {sale['name']} (ganancia realizada {sale['gain']:,.2f}); "
                f"diferencia marcada {row['gap']}")

        # Money Manager checks
        dups = mm.find_duplicates(tx)
        if i == 0:
            add("duplicate flagged", len(dups) == 3,
                f"{len(dups)} posibles duplicados (esperados 3: el original, una copia exacta y otra con otra hora "
                f"y nota)")
        unmatched = mm.unmatched_transfers(tx)
        add("transfers matched", unmatched.empty, f"{len(unmatched)} transferencias sin su otra mitad")
        if i == SALE_AT:
            month_tx = tx[tx["month"] == d[:7]]
            new_ok = (NEW_ACCOUNT in set(month_tx["account"]) and NEW_CATEGORY in set(month_tx["category"])
                      and month_tx["note"].eq(REFUND_NOTE).any())
            flow = mx.cashflow(tx).set_index("month")
            synthetic_income = sum(a for w, _, _, a, k, *_ in m["mm"] if k == "Income")
            real_income = float(tx[(tx["month"] == d[:7]) & (tx["type"] == "income")]["amount"].sum())
            add("new category, account and refund loaded",
                new_ok and abs(flow.loc[d[:7], "income"] - real_income) < 0.01
                and abs(real_income - synthetic_income) < 0.01,
                f"cuenta {NEW_ACCOUNT}, categoría {NEW_CATEGORY}, reembolso como ingreso; ingreso del mes "
                f"{real_income:,.2f} (esperado {synthetic_income:,.2f})")

        truth_rows.append({"as_of": d, "net_worth": truth_nw, **{k: round(v, 2) for k, v in parts.items()}})
        prev, prev_date = m["rows"], d
        for s in m["new_stmts"]:
            stmts[s["platform"]] = s

    return Result(checks, pd.DataFrame(truth_rows), db_path, workdir, months)


def months_after(last, n=N_MONTHS):
    """The n month-ends after the month of `last` (YYYY-MM-DD). '2026-09-28' -> Oct 31, Nov 30, Dec 31."""
    y, m = int(last[:4]), int(last[5:7])
    out = []
    for _ in range(n):
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
        out.append(f"{y}-{m:02d}-{calendar.monthrange(y, m)[1]:02d}")
    return out


# --- One month -----------------------------------------------------------------

def _month(prev, stmts, prev_date, d, settings, tx, nth):
    """Next month's rows from last month's, plus the truth, the events the validator should warn about,
    and the Money Manager rows."""
    isr = settings["tax"]["isr_rate"]
    d0, d1 = date.fromisoformat(prev_date), date.fromisoformat(d)
    days = (d1 - d0).days
    rows = [dict(r, as_of=d, confirmed_on=None) for r in prev]
    truth, events, transfers, new_stmts, stale = {}, [], {}, [], []
    maturities, sale = 0, None

    for p in dict.fromkeys(r["platform"] for r in rows):
        g = [r for r in rows if r["platform"] == p]
        parts = [r for r in g if r["item_type"] not in ("total", "statement")]
        method = cfg.returns_method(settings, p)
        t = truth[p] = {"put_in": 0.0, "returns": 0.0, "kind": method}
        c, logged = CONTRIB.get(p, 0.0), CONTRIB.get(p, 0.0)
        if nth == MISLOG_AT and p == MISLOGGED[0]:
            c, logged = MISLOGGED[1], MISLOGGED[2]

        if method == "revaluation":
            for r in parts:
                delta = round(r["value"] * REVALUATION, 2)
                r["value"] = round(r["value"] + delta, 2)
                t["returns"] += delta
            c = logged = 0.0

        elif method == "gain_change":
            for r in parts:
                if _has(r.get("gain")) and r.get("asset_type") != "cash":
                    rate = (r["annual_rate"] / 12 if _has(r.get("annual_rate")) else 0.0) \
                        if r["item_type"] == "cajita" else HOLDING_GROWTH
                    delta = round(r["value"] * rate, 2)
                    r["value"], r["gain"] = round(r["value"] + delta, 2), round(r["gain"] + delta, 2)
                    t["returns"] += delta
            if nth == SALE_AT and any(r["item_type"] == "holding" for r in parts):
                sale = _sell(rows, parts, p, events)
                parts = [r for r in rows if r["platform"] == p and r["item_type"] not in ("total", "statement")]
            if c and parts:
                target = next((r for r in parts if r.get("asset_type") == "cash"), parts[0])
                target["value"] = round(target["value"] + c, 2)
                t["put_in"] += c
            else:
                c = logged = 0.0
            for r in parts:
                if r["item_type"] == "holding" and _has(r.get("gain_pct")) and _has(r.get("gain")):
                    r["gain_pct"] = round(r["gain"] / (r["value"] - r["gain"]), 6)

        elif method == "interest":
            od = [r for r in parts if r["item_type"] == "on_demand"]
            for r in od:
                if _has(r.get("annual_rate")):
                    interest = it.net_interest(r["value"], r["annual_rate"], days, isr)
                    r["value"] = round(r["value"] + interest, 2)
                    t["returns"] += interest
            dest = od[0] if od else None
            for r in [x for x in parts if x["item_type"] == "deposit"]:
                s, e = date.fromisoformat(str(r["start_date"])), date.fromisoformat(str(r["end_date"]))
                paid, back = 0.0, 0.0
                if r["payout"] == "monthly":
                    paid = sum(x["net"] for x in it.monthly_schedule(r["principal"], r["annual_rate"], s, e, isr)
                               if d0 < x["date"] <= d1)
                    back = r["principal"] if d0 < e <= d1 else 0.0
                elif d0 < e <= d1:
                    net_shown = r.get("interest_basis") == "net" and _has(r.get("interest_total"))
                    paid = r["interest_total"] if net_shown else it.net_interest(
                        r["principal"], r["annual_rate"], int(r["term_days"]), isr)
                    back = r["principal"]
                    maturities += 1
                t["returns"] += paid
                if back:
                    rows.remove(r)
                    events.append(("gone", p, r["name"]))
                    stale.append((p, r["name"]))
                if dest:
                    dest["value"] = round(dest["value"] + paid + back, 2)
                else:  # nowhere to land inside the platform: paid out to a bank account
                    t["put_in"] -= paid + back
            if c and dest:
                dest["value"] = round(dest["value"] + c, 2)
                t["put_in"] += c
            else:
                c = logged = 0.0

        elif method == "statement" and p in stmts:
            total = next(r for r in g if r["item_type"] == "total")
            growth = round(total["value"] * STATEMENT_GROWTH, 2)
            total["value"] = round(total["value"] + growth + c, 2)
            s0 = stmts[p]
            # Contributions come from the statements' own period (decided 2026-09-28): money logged after the
            # last statement but before last month's snapshot shows up in this month's statement.
            lag = rc._logged(tx, cfg.mm_account(settings, p), s0["as_of"], prev_date) \
                if cfg.mm_account(settings, p) else 0.0
            new_stmts.append(dict(s0, as_of=d, value=total["value"], principal=round(s0["principal"] + lag + c, 2),
                                  confirmed_on=None))
            t["put_in"] += c + lag
            t["returns"] += growth - lag

        else:  # estimated (Bitso, Profuturo) or a statement platform with no statement yet
            t["kind"] = "estimated"
            targets = parts or [r for r in g if r["item_type"] == "total"]
            for r in targets:
                delta = round(r["value"] * ESTIMATED_GROWTH, 2)
                r["value"] = round(r["value"] + delta, 2)
                t["returns"] += delta
            c = logged = 0.0

        # Totals: the sum of the parts (Allianz has no parts: its total was set above)
        live = [r for r in rows if r["platform"] == p and r["item_type"] not in ("total", "statement", "manual_asset")]
        for r in rows:
            if r["platform"] == p and r["item_type"] == "total" and (live or method == "interest"):
                r["value"] = round(sum(x["value"] for x in live), 2)
        t["put_in"], t["returns"] = round(t["put_in"], 2), round(t["returns"], 2)
        account = cfg.mm_account(settings, p)
        if logged and account:
            transfers[account] = logged

    first, missing = None, None
    if nth == 0:
        # First attempt: one screenshot missing, and platforms with a deposit that matured show last month's
        # screen (the deposit still listed)
        missing = MISSING if any(r["platform"] == MISSING for r in rows) else None
        stale_set = {p for p, _ in stale}
        first = [r for r in rows if r["platform"] not in stale_set and r["platform"] != missing]
        first += [dict(r, as_of=d, confirmed_on=None) for r in prev if r["platform"] in stale_set]
        first += new_stmts
    else:
        stale = []

    return {"rows": rows, "new_stmts": new_stmts, "truth": truth, "events": events, "sale": sale,
            "maturities": maturities, "first": first, "missing": missing, "stale": stale,
            "mm": _mm_rows(d, transfers, nth)}


def _sell(rows, parts, platform, events):
    """Sell the holding with the biggest gain; the money lands in the platform's cash."""
    held = [r for r in parts if r["item_type"] == "holding" and r.get("asset_type") != "cash" and _has(r.get("gain"))]
    if not held:
        return None
    sold = max(held, key=lambda r: r["gain"])
    rows.remove(sold)
    events.append(("gone", platform, sold["name"]))
    cash = next((r for r in parts if r.get("asset_type") == "cash"), None)
    if cash is None:
        cash = {k: None for k in sold}
        cash.update(as_of=sold["as_of"], platform=platform, account_type=sold["account_type"], item_type="holding",
                    name="CASH", asset_type="cash", value=0.0)
        rows.append(cash)
        events.append(("new", platform, "CASH"))
    cash["value"] = round(cash["value"] + sold["value"], 2)
    return {"platform": platform, "name": sold["name"], "gain": round(sold["gain"], 2)}


def _mm_rows(d, transfers, i):
    """This month's Money Manager rows: (when, account, category, amount, kind, note). i = month of the replay."""
    m = d[:7]
    rows = [
        (f"{m}-05 12:00", "Card A", "Food", 1200.0, "Exp.", "Replay súper"),
        (f"{m}-08 12:00", "Card A", "Transportation", 800.0, "Exp.", DELETED_NOTE),
        (f"{m}-15 09:00", PAYER, "Salary", 40_000.0, "Income", "Replay nómina"),
        (f"{m}-20 14:00", "Card A", "Food", 450.0, "Exp.", TAGGED_NOTE),  # card not paid yet
    ]
    for account, amount in transfers.items():
        rows.append((f"{m}-10 10:00", PAYER, account, amount, "Transfer-Out", "Replay aportación"))
        rows.append((f"{m}-10 10:00", account, PAYER, amount, "Transfer-In", "Replay aportación"))
    if i == 0:
        rows.append(rows[0])  # planted duplicate: an exact copy
        rows.append((f"{m}-05 19:30", "Card A", "Food", 1200.0, "Exp.", "Replay súper otra vez"))  # later, other note
    if i == SALE_AT:
        rows.append((f"{m}-12 12:00", NEW_ACCOUNT, NEW_CATEGORY, 650.0, "Exp.", "Replay cuenta nueva"))
        rows.append((f"{m}-18 12:00", PAYER, "Other", 300.0, "Income", REFUND_NOTE))
    return rows


def _expected_warnings(m, prev, settings):
    """Text the validator should show for this month's events: items gone or new, and big jumps."""
    out = [f"{p} '{n}' estaba el" for kind, p, n in m["events"] if kind == "gone"]
    out += [f"{p} '{n}' es nuevo" for kind, p, n in m["events"] if kind == "new"]
    # The replay revalues the car and Activos every month, as if Memo gave new values: the check shows each change
    was = {(r["platform"], r["name"]): r["value"] for r in prev if r["item_type"] == "manual_asset"}
    out += [f"{r['platform']} '{r['name']}' cambió de" for r in m["rows"] if r["item_type"] == "manual_asset"
            and (r["platform"], r["name"]) in was and abs(r["value"] - was[(r["platform"], r["name"])]) > 1.0]
    before, now = sn.platform_totals(pd.DataFrame(prev)), sn.platform_totals(pd.DataFrame(m["rows"]))
    for p, v in now.items():
        if before.get(p) and abs((v - before[p]) / abs(before[p])) > settings["checks"]["jump_warn_pct"]:
            out.append(f"{p} cambió")
    return out


# --- Files -----------------------------------------------------------------------

def _read(path):
    df = pd.read_csv(path, encoding="utf-8-sig", dtype={"as_of": str, "start_date": str, "end_date": str})
    return sn._clean(df)


def _rows(df):
    return [{k: (None if isinstance(v, float) and v != v else v) for k, v in r.items()}
            for r in df.to_dict("records")]


def _has(x):
    return x is not None and x == x


def _write(rows, columns, path):
    pd.DataFrame(rows).reindex(columns=columns).to_csv(path, index=False, encoding="utf-8-sig")


KINDS = {"expense": "Exp.", "income": "Income", "transfer_out": "Transfer-Out", "transfer_in": "Transfer-In"}


def _raw(when, account, category, amount, kind, note, subcategory=None, description=None):
    """One export row in Money Manager's layout."""
    ts = when if isinstance(when, datetime) else datetime.strptime(when, "%Y-%m-%d %H:%M")
    return [ts, account, category, subcategory, note, amount, kind, description, amount, "MXN", amount]


def _raw_month(tx, month):
    """Rows already in the source exports for this month (Money Manager's export of the month includes them)."""
    t = tx[tx["month"] == month]
    return [_raw(pd.Timestamp(r.timestamp).to_pydatetime(), r.account, r.category, r.amount, KINDS[r.type],
                 r.note or None, r.subcategory or None, r.description or None) for r in t.itertuples()]


def _name(month, suffix=""):
    """Money Manager's file name for one month, e.g. 'Money Manager Report 2026-10-01 ~ 10-31.xlsx'."""
    y, m = int(month[:4]), int(month[5:7])
    last = (date(y + (m == 12), m % 12 + 1, 1) - date.resolution).day
    return f"Money Manager Report {month}-01 ~ {month[5:]}-{last:02d}{suffix}.xlsx"


def _saved(month_end):
    """When Memo saves the month's export: the 1st of the next month, 9:00."""
    d = date.fromisoformat(month_end) + date.resolution
    return datetime(d.year, d.month, d.day, 9).timestamp()


def _export(path, rows, saved):
    wb = Workbook()
    ws = wb.active
    ws.append(MM_HEADER)
    for r in rows:
        ws.append(r)
    wb.save(path)
    os.utime(path, (saved, saved))
    return Path(path)
