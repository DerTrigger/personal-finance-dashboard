"""
Every number the dashboard shows. Pure functions over DataFrames: the screens only draw what these return.

snaps: snapshot_items (same columns as investment-snapshots.csv). tx: Money Manager transactions.
Investment views use the latest snapshot unless an as_of date is given.
"""
import re
from datetime import date

import pandas as pd

from app.lib import interest as it
from app.lib import moneymanager as mm
from app.lib import reconcile as rc
from app.lib import snapshots as sn

NO_SUB = "(sin subcategoría)"  # label for entries logged without a subcategory


def _at(snaps, as_of=None):
    """Main rows (no statements) of one snapshot date, default the latest."""
    s = sn._main(sn._clean(snaps))
    as_of = as_of or max(s["as_of"])
    return s[s["as_of"] == as_of], as_of


# --- Net worth ---------------------------------------------------------------

def net_worth_series(snaps, dates=None):
    """Net worth per snapshot date, optionally only snapshots within dates=(start, end)."""
    s = sn._main(sn._clean(snaps))
    s = s[s["item_type"].isin(["total", "manual_asset"])]
    if dates:
        s = s[(s["as_of"] >= str(dates[0])) & (s["as_of"] <= str(dates[1]))]
    out = s.groupby("as_of", as_index=False)["value"].sum().rename(columns={"value": "net_worth"})
    out["net_worth"] = out["net_worth"].round(2)
    return out


def net_worth_by_date(snaps, by="account_type", dates=None):
    """Long table: as_of, <by> (account_type or platform), value. For stacked charts over time."""
    s = sn._main(sn._clean(snaps))
    s = s[s["item_type"].isin(["total", "manual_asset"])]
    if dates:
        s = s[(s["as_of"] >= str(dates[0])) & (s["as_of"] <= str(dates[1]))]
    return s.groupby(["as_of", by], as_index=False)["value"].sum().round(2)


def net_worth_by_type(snaps, as_of=None):
    s, _ = _at(snaps, as_of)
    s = s[s["item_type"].isin(["total", "manual_asset"])]
    return s.groupby(["account_type", "platform"], as_index=False)["value"].sum().groupby(
        "account_type", as_index=False)["value"].sum()


def net_worth_by_platform(snaps, as_of=None):
    s, _ = _at(snaps, as_of)
    s = s[s["item_type"].isin(["total", "manual_asset"])]
    return s.groupby(["platform", "account_type"], as_index=False)["value"].sum().sort_values(
        "value", ascending=False)


def why_changed(snaps, tx, settings):
    """Per pair of consecutive snapshots: change = put_in + returns + estimated_returns + revaluation."""
    dates = sn.snapshot_dates(snaps)
    rows = []
    for start, end in zip(dates, dates[1:]):
        r = rc.reconcile(snaps, start, end, tx, settings)
        reval = r["method"] == "revaluation"
        rows.append({
            "start": start, "end": end,
            "change": round(r["change"].sum(), 2),
            "put_in": round(r.loc[~reval, "contributions"].sum(), 2),
            "returns": round(r.loc[~reval & ~r["estimated"], "returns"].sum(), 2),
            "estimated_returns": round(r.loc[r["estimated"], "returns"].sum(), 2),
            "revaluation": round(r.loc[reval, "returns"].sum(), 2),
        })
    return pd.DataFrame(rows, columns=["start", "end", "change", "put_in", "returns", "estimated_returns",
                                       "revaluation"])


# --- Cash flow ---------------------------------------------------------------

def filter_tx(tx, months=None, accounts=None, categories=None, dates=None, subcategories=None):
    """Transactions filtered by any mix of: month range ('YYYY-MM', inclusive), calendar dates (start, end,
    inclusive), accounts, categories, subcategories. None = no filter."""
    f = tx
    if months:
        f = f[(f["month"] >= months[0]) & (f["month"] <= months[1])]
    if dates:
        f = f[(f["date"] >= str(dates[0])) & (f["date"] <= str(dates[1]))]
    if accounts:
        f = f[f["account"].isin(accounts)]
    if categories:
        f = f[f["category"].isin(categories)]
    if subcategories:
        f = f[f["subcategory"].isin(subcategories)]
    return f


def other_month(month, mode):
    """The month to compare with: 'prev_month' (Sep -> Aug) or 'prev_year' (Sep 2026 -> Sep 2025)."""
    y, m = int(month[:4]), int(month[5:7])
    if mode == "prev_year":
        return f"{y - 1}-{m:02d}"
    return f"{y - 1}-12" if m == 1 else f"{y}-{m - 1:02d}"


def compare_months(tx, month, mode, kind="expense", by="category"):
    """Per category: this month, the comparison month, change in $ and %. Sorted by this month, biggest first."""
    other = other_month(month, mode)
    t = tx[(tx["type"] == kind) & tx["month"].isin([month, other])].copy()
    t[by] = t[by].replace("", NO_SUB)
    p = t.pivot_table(index=by, columns="month", values="amount", aggfunc="sum", fill_value=0.0)
    out = pd.DataFrame({"this": p[month] if month in p else 0.0, "other": p[other] if other in p else 0.0},
                       index=p.index)
    out["change"] = out["this"] - out["other"]
    out["change_pct"] = out["change"] / out["other"].where(out["other"] != 0)
    return out.round({"this": 2, "other": 2, "change": 2, "change_pct": 4}) \
        .sort_values("this", ascending=False).reset_index()


def cashflow(tx):
    """Per month: income, expenses, net income, savings rate. Transfers are excluded."""
    months = sorted(tx["month"].unique())
    amt = tx[tx["type"].isin(["income", "expense"])].pivot_table(
        index="month", columns="type", values="amount", aggfunc="sum", fill_value=0.0)
    out = pd.DataFrame(index=pd.Index(months, name="month"))
    out["income"] = amt["income"] if "income" in amt else 0.0
    out["expenses"] = amt["expense"] if "expense" in amt else 0.0
    out = out.fillna(0.0).round(2)
    out["net_income"] = (out["income"] - out["expenses"]).round(2)
    out["savings_rate"] = (out["net_income"] / out["income"].where(out["income"] != 0)).round(4)
    return out.reset_index()


def expenses_by(tx, by="category"):
    e = tx[tx["type"] == "expense"].copy()
    e[by] = e[by].replace("", NO_SUB)
    return e.groupby(["month", by], as_index=False)["amount"].sum().round(2)


def month_over_month(tx, by="category"):
    """Latest month vs. the one before, per category (or subcategory)."""
    e = expenses_by(tx, by)
    if e.empty:
        return pd.DataFrame(columns=[by, "this_month", "last_month", "change"])
    months = sorted(tx["month"].unique())
    this, last = months[-1], (months[-2] if len(months) > 1 else None)
    p = e.pivot_table(index=by, columns="month", values="amount", aggfunc="sum", fill_value=0.0)
    out = pd.DataFrame({"this_month": p[this] if this in p else 0.0,
                        "last_month": p[last] if last in p else 0.0})
    out["change"] = out["this_month"] - out["last_month"]
    return out.round(2).sort_values("this_month", ascending=False).reset_index()


def income_by_source(tx):
    i = tx[tx["type"] == "income"]
    return i.groupby(["month", "category"], as_index=False)["amount"].sum().round(2)


# --- Card balances not paid yet ------------------------------------------------
# Memo's Money Manager notes: "IN NU" = money already set aside in Nu, card not paid yet; "NPY" = not set aside
# yet. "$200 IN NU" = only $200 of that charge is set aside. He deletes the tag once the card is paid, so
# whatever is tagged now is still owed.

SET_ASIDE, NOT_SET_ASIDE, PARTIAL = "Apartado en Nu", "Sin apartar", "Apartado en parte"
_IN_NU = r"(?i)\bIN\s+NU\b"
_NPY = r"(?i)\bNPY\b"
_PARTIAL = r"(?i)\$\s*([\d,]+(?:\.\d+)?)\s*IN\s+NU\b"


def payment_tag(note):
    """The note's tag as a label, or "" when it has none."""
    note = str(note or "")
    if re.search(_PARTIAL, note):
        return PARTIAL
    if re.search(_IN_NU, note):
        return SET_ASIDE
    if re.search(_NPY, note):
        return NOT_SET_ASIDE
    return ""


def card_pending(tx):
    """Tagged charges still owed on credit cards: one row each with how much is set aside and how much isn't.
    Expenses and transfers out count (a PPR contribution paid by card is a tagged transfer); the matching
    transfer in is skipped so nothing counts twice.
    Only the latest export counts (the file with the latest transaction): exports cover last month only, so an
    older month's tags are never updated after Memo removes them (decided 2026-09-29)."""
    if tx.empty:
        return tx.assign(tag="", set_aside=0.0, not_set_aside=0.0)[
            ["date", "account", "category", "note", "amount", "tag", "set_aside", "not_set_aside"]]
    latest = tx.loc[tx["date"].idxmax(), "source_file"]
    t = tx[tx["type"].isin(["expense", "transfer_out"]) & (tx["source_file"] == latest)].copy()
    t["tag"] = t["note"].map(payment_tag)
    t = t[t["tag"] != ""]
    partial = t["note"].astype(str).str.extract(_PARTIAL)[0].str.replace(",", "").astype(float)
    t["set_aside"] = 0.0
    t.loc[t["tag"] == SET_ASIDE, "set_aside"] = t["amount"]
    t.loc[t["tag"] == PARTIAL, "set_aside"] = partial.clip(upper=t["amount"])
    t["set_aside"] = t["set_aside"].round(2)
    t["not_set_aside"] = (t["amount"] - t["set_aside"]).round(2)
    cols = ["date", "account", "category", "note", "amount", "tag", "set_aside", "not_set_aside"]
    return t[cols].sort_values("date", ascending=False).reset_index(drop=True)


# --- Investments -------------------------------------------------------------

def deposits_table(snaps, isr_rate, as_of=None):
    """Every fixed-term deposit with after-tax interest on the same basis for all platforms."""
    s, as_of = _at(snaps, as_of)
    d = s[s["item_type"] == "deposit"].copy()
    if d.empty:
        return pd.DataFrame(columns=["platform", "name", "principal", "annual_rate", "term_days", "start_date",
                                     "end_date", "payout", "interest_after_tax", "days_left"])

    def after_tax(r):
        start, end = date.fromisoformat(str(r.start_date)), date.fromisoformat(str(r.end_date))
        days = (end - start).days if r.payout == "monthly" else int(r.term_days)
        if r.interest_basis == "net" and pd.notna(r.interest_total):
            return float(r.interest_total)  # the platform's own after-tax figure wins
        return it.net_interest(r.principal, r.annual_rate, days, isr_rate)

    d["interest_after_tax"] = [after_tax(r) for r in d.itertuples()]
    d["days_left"] = [(date.fromisoformat(str(e)) - date.fromisoformat(as_of)).days for e in d["end_date"]]
    cols = ["platform", "name", "principal", "annual_rate", "term_days", "start_date", "end_date", "payout",
            "interest_after_tax", "days_left"]
    return d[cols].sort_values("end_date").reset_index(drop=True)


def on_demand(snaps, as_of=None):
    """Balances that aren't locked in a deposit: Nu Cajitas and FINSUS on-demand."""
    s, _ = _at(snaps, as_of)
    return s[s["item_type"].isin(["cajita", "on_demand"])][["platform", "name", "value", "annual_rate", "gain"]]


def upcoming(snaps, isr_rate, today, days=60):
    s, _ = _at(snaps)
    return it.upcoming_events(s[s["item_type"] == "deposit"].itertuples(), today, isr_rate, days)


def holdings(snaps, as_of=None):
    s, _ = _at(snaps, as_of)
    h = s[s["item_type"] == "holding"].copy()
    h["invested"] = h["value"] - h["gain"]
    h["gain_pct"] = h["gain"] / h["invested"]
    return h[["platform", "name", "ticker", "asset_type", "units", "value", "gain", "invested", "gain_pct"]] \
        .sort_values("value", ascending=False).reset_index(drop=True)


def holdings_mix(snaps, as_of=None):
    h = holdings(snaps, as_of)
    return h.groupby("asset_type", as_index=False)["value"].sum().sort_values("value", ascending=False)


def retirement(snaps, as_of=None):
    s, as_of = _at(snaps, as_of)
    all_rows = sn._clean(snaps)
    allianz_total = s.loc[(s["platform"] == "Allianz PPR") & (s["item_type"] == "total"), "value"].sum()
    st = all_rows[(all_rows["platform"] == "Allianz PPR") & (all_rows["item_type"] == "statement")
                  & (all_rows["as_of"] <= as_of)].sort_values("as_of")
    allianz = {"total": float(allianz_total), "statement_date": None, "statement_value": None,
               "contributions": None, "statement_gain": None}
    if not st.empty:
        last = st.iloc[-1]
        allianz.update(statement_date=last["as_of"], statement_value=float(last["value"]),
                       contributions=float(last["principal"]),
                       statement_gain=round(float(last["value"] - last["principal"]), 2))
    prof = s[(s["platform"] == "Profuturo") & (s["item_type"] == "subaccount")][["name", "value"]]
    prof_total = s.loc[(s["platform"] == "Profuturo") & (s["item_type"] == "total"), "value"].sum()
    return {"allianz": allianz, "profuturo": prof.reset_index(drop=True), "profuturo_total": float(prof_total)}


def retirement_parts(snaps, as_of=None):
    """Where the retirement money is: account, part, value. Allianz splits into what was put in (last statement)
    and the growth on top of it (today's value minus that); Profuturo into its subaccounts."""
    r = retirement(snaps, as_of)
    a = r["allianz"]
    rows = []
    if a["total"]:
        if a["contributions"] is not None:
            rows += [("Allianz PPR", "Aportado", a["contributions"]),
                     ("Allianz PPR", "Rendimiento", round(a["total"] - a["contributions"], 2))]
        else:
            rows.append(("Allianz PPR", "Valor", a["total"]))
    rows += [("Profuturo", n, float(v)) for n, v in zip(r["profuturo"]["name"], r["profuturo"]["value"])]
    return pd.DataFrame(rows, columns=["account", "part", "value"])


# --- Data check --------------------------------------------------------------

def month_summary(snaps, tx, settings, month):
    """What the monthly close tells Memo at the end: net worth and why it changed (when the month has a snapshot),
    the month's cash flow, and card balances still owed."""
    series = net_worth_series(snaps)
    in_month = series[series["as_of"].str.startswith(month)]
    latest = series.iloc[-1]
    out = {"month": month, "as_of": latest["as_of"], "net_worth": float(latest["net_worth"]),
           "previous": None, "change": None, "why": None}
    if len(in_month) and len(series) > 1:
        as_of = in_month["as_of"].iloc[-1]
        prev = series[series["as_of"] < as_of].iloc[-1]
        why = why_changed(snaps, tx, settings)
        w = why[why["end"] == as_of].iloc[0]
        out.update(as_of=as_of, net_worth=float(in_month["net_worth"].iloc[-1]), previous=prev["as_of"],
                   change=round(float(in_month["net_worth"].iloc[-1]) - float(prev["net_worth"]), 2),
                   why={k: float(w[k]) for k in ("put_in", "returns", "estimated_returns", "revaluation")})
    flow = cashflow(tx[tx["month"] == month])
    row = flow.iloc[0] if len(flow) else {"income": 0.0, "expenses": 0.0, "net_income": 0.0, "savings_rate": None}
    owed = card_pending(tx)
    out.update(income=float(row["income"]), expenses=float(row["expenses"]), net_income=float(row["net_income"]),
               savings_rate=row["savings_rate"],
               card_pending={"total": float(owed["amount"].sum()), "set_aside": float(owed["set_aside"].sum()),
                             "not_set_aside": float(owed["not_set_aside"].sum()), "charges": len(owed)})
    return out


def data_check(snaps, tx, settings, adjustments=None):
    """Checks re-run on what's loaded: the latest month vs. the one before, reconciliation (booked gaps count as
    settled), Money Manager."""
    s = sn._clean(snaps)
    dates = sn.snapshot_dates(s)
    latest = dates[-1] if dates else None
    pending, history = s[s["as_of"] == latest], s[s["as_of"] != latest]
    errors, warnings = sn.validate(pending, history, settings) if latest else ([], [])
    recon = rc.reconcile(s, dates[-2], latest, tx, settings, adjustments) if len(dates) > 1 else None
    return {"latest": latest, "errors": errors, "warnings": warnings, "reconcile": recon,
            "duplicates": mm.find_duplicates(tx), "unmatched": mm.unmatched_transfers(tx)}
