"""Inversiones: summary of every investment account, then tabs for fixed yield, variable, and retirement.
Click a type or an account to filter the whole view (tabs included)."""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pandas as pd  # noqa: E402
import plotly.graph_objects as go  # noqa: E402
import streamlit as st  # noqa: E402

from app.lib import fmt, ui  # noqa: E402
from app.lib import metrics as mx  # noqa: E402
from app.lib import snapshots as sn  # noqa: E402

PAGE = "inversiones"
INVEST_TYPES = [t for t in ui.TYPE_ORDER if t != "manual_asset"]
ASSET_LABELS = {"etf": "ETF", "fibra": "FIBRA", "stock": "Acción", "crypto": "Cripto", "fund": "Fondo",
                "cash": "Efectivo"}
WHAT = {"interest (after tax)": "Interés (neto)", "principal returned": "Regreso de capital",
        "principal + interest": "Capital + interés"}
HOUSING = "vivienda"  # Profuturo's housing (Infonavit) subaccount name contains this

snaps, tx, _ = ui.load()
s = ui.settings()
c = ui.colors()
tc = ui.type_colors()
isr = s["tax"]["isr_rate"]
st.title("Inversiones")

dates = sn.snapshot_dates(snaps)
f1, f2 = st.columns([2, 2])
with f1:
    period = ui.period_picker(snaps, tx)
with f2:
    as_of = ui.snapshot_picker(dates)
ui.period_presets()

click_types = ui.picked(PAGE, "by_type", 0)
click_platforms = ui.picked(PAGE, "by_platform", 0)
ui.active_filters(PAGE, {"Tipo": [ui.TYPE_LABELS.get(t, t) for t in click_types], "Cuenta": click_platforms})

plat_all = mx.net_worth_by_platform(snaps, as_of)
plat_all = plat_all[plat_all["account_type"].isin(INVEST_TYPES)]
plat = plat_all[plat_all["account_type"].isin(click_types)] if click_types else plat_all
chosen = click_platforms or list(plat["platform"])  # the accounts every visual below shows


def only(df, col="platform"):
    return df[df[col].isin(chosen)]


# --- Summary cards -----------------------------------------------------------------
by_date = mx.net_worth_by_date(snaps, "platform", dates=period)
by_date = by_date[by_date["platform"].isin(chosen)]
series = by_date.groupby("as_of")["value"].sum()
total = plat[plat["platform"].isin(chosen)]["value"].sum()
earlier = [d for d in dates if d < as_of]
prev_total = None
if earlier:
    prev = mx.net_worth_by_platform(snaps, earlier[-1])
    prev_total = prev[prev["platform"].isin(chosen)]["value"].sum()
deps = only(mx.deposits_table(snaps, isr, as_of))
events = [e for e in mx.upcoming(snaps[snaps["as_of"].astype(str) <= as_of], isr,
                                 max(date.today(), date.fromisoformat(as_of)), days=365)
          if e["platform"] in chosen]
next30 = sum(e["amount"] for e in events if (e["date"] - date.today()).days <= 30)

with ui.card_row():
    ui.card("Total invertido", fmt.compact(total), help=f"{fmt.exact(total)} al {fmt.day(as_of)}",
            delta=f"{fmt.signed(total - prev_total)} vs. {fmt.day(earlier[-1])}" if prev_total is not None else None,
            note=None if prev_total is not None else f"{fmt.day(as_of)} · primer mes", spark=list(series.values))
    why = mx.why_changed(snaps, tx, s)
    why = why[why["end"] <= as_of]
    if len(why):
        w = why.iloc[-1]
        ret = w["returns"] + w["estimated_returns"]
        ui.card("Rendimiento del último mes", fmt.signed(ret), help=f"{fmt.day(w['start'])} a {fmt.day(w['end'])}: "
                f"{fmt.exact(w['returns'])} reportado + {fmt.exact(w['estimated_returns'])} estimado",
                note=f"Incluye {fmt.compact(w['estimated_returns'])} estimado")
    else:
        ui.card("Rendimiento del último mes", "–", note="Desde el próximo mes",
                help="Aparece cuando haya dos cortes mensuales para comparar.")
    ui.card("Intereses por cobrar", fmt.compact(deps["interest_after_tax"].sum()),
            help=f"{fmt.exact(deps['interest_after_tax'].sum())}, después de impuestos, de {len(deps)} depósitos",
            note=f"{len(deps)} depósitos a plazo")
    ui.card("Entra en 30 días", fmt.compact(next30), help=fmt.exact(next30),
            note=f"{sum(1 for e in events if (e['date'] - date.today()).days <= 30)} pagos o vencimientos")

# --- Summary charts ------------------------------------------------------------------
left, right = st.columns(2)
with left:
    by_type = plat_all.groupby("account_type", as_index=False)["value"].sum()
    by_type = by_type.set_index("account_type").reindex([t for t in INVEST_TYPES if t in set(by_type[
        "account_type"])]).reset_index().iloc[::-1]
    fig = go.Figure(go.Bar(
        y=[ui.TYPE_LABELS[t] for t in by_type["account_type"]], x=by_type["value"], orientation="h",
        customdata=list(zip(by_type["account_type"], ui.shares(by_type["value"]))),
        marker_color=[tc[t] for t in by_type["account_type"]],
        text=[f"{fmt.compact(v)} · {fmt.pct(v / by_type['value'].sum(), 0)}" for v in by_type["value"]],
        textposition="outside", cliponaxis=False,
        hovertemplate="%{y}: %{x:$,.0f} · %{customdata[1]:.1%} del total<extra></extra>"))
    fig.update_layout(title="Por tipo · clic para filtrar (MXN)")
    ui.style(fig, height=300, x_title="Saldo", money_axis="x", legend=False)
    ui.headroom(fig, "x", by_type["value"].max(), 0.55)
    ui.draw(fig, key=ui.chart_key(PAGE, "by_type"), clickable=True)
with right:
    p = plat.sort_values("value")
    fig = go.Figure(go.Bar(
        y=p["platform"], x=p["value"], orientation="h", customdata=list(zip(p["platform"], ui.shares(p["value"]))),
        marker_color=[tc.get(t, c["neutral"]) for t in p["account_type"]],
        text=[fmt.compact(v) for v in p["value"]], textposition="outside", cliponaxis=False,
        hovertemplate="%{y}: %{x:$,.0f} · %{customdata[1]:.1%} del total<extra></extra>"))
    fig.update_layout(title="Por cuenta · clic para filtrar (MXN)")
    ui.style(fig, height=300, x_title="Saldo", money_axis="x", legend=False)
    ui.headroom(fig, "x", p["value"].max(), 0.4)
    ui.draw(fig, key=ui.chart_key(PAGE, "by_platform"), clickable=True)

evo = mx.net_worth_by_date(snaps, "platform", dates=period)
evo = evo[evo["platform"].isin(chosen)]
evo["account_type"] = evo["platform"].map(dict(zip(plat_all["platform"], plat_all["account_type"])))
evo = evo.groupby(["as_of", "account_type"], as_index=False)["value"].sum()
evo["share"] = ui.shares(evo["value"], evo["as_of"])
fig = go.Figure()
for t in INVEST_TYPES:
    d = evo[evo["account_type"] == t]
    if len(d):
        fig.add_bar(name=ui.TYPE_LABELS[t], x=[fmt.day(x) for x in d["as_of"]], y=d["value"], marker_color=tc[t],
                    customdata=d["share"],
                    hovertemplate=f"{ui.TYPE_LABELS[t]}<br>%{{x}}: %{{y:$,.0f}} · %{{customdata:.1%}} del total"
                                  "<extra></extra>")
tot = evo.groupby("as_of")["value"].sum()
fig.add_scatter(x=[fmt.day(x) for x in tot.index], y=tot.values, mode="text", text=[fmt.compact(v) for v in tot],
                textposition="top center", textfont=dict(size=12), showlegend=False,
                hoverinfo="skip")
fig.update_layout(title="Evolución por tipo (MXN)", barmode="stack")
ui.style(fig, height=340, x_title="Fecha de corte", y_title="Saldo", money_axis="y")
ui.headroom(fig, "y", tot.max() if len(tot) else 0, 0.12)
ui.draw(fig)
if len(dates) < 2:
    st.caption("La evolución crece con cada actualización mensual.")

# --- Tabs ---------------------------------------------------------------------------
tab_fixed, tab_var, tab_ret = st.tabs(["Plazo fijo y ahorro", "Variable", "Retiro"])

with tab_fixed:
    if events:
        ev = pd.DataFrame(events)
        ev["month"] = [d.strftime("%Y-%m") for d in ev["date"]]
        ev["kind"] = ["Intereses" if w == "interest (after tax)" else "Vencimientos" for w in ev["what"]]
        by = ev.groupby(["month", "kind"], as_index=False)["amount"].sum()
        fig = go.Figure([
            go.Bar(name=k, x=[fmt.month(m) for m in by.loc[by["kind"] == k, "month"]],
                   y=by.loc[by["kind"] == k, "amount"], marker_color=col,
                   hovertemplate=f"{k}<br>%{{x}}: %{{y:$,.0f}}<extra></extra>")
            for k, col in (("Vencimientos", tc["sofipo_fixed"]), ("Intereses", c["series"][1]))
            if k in set(by["kind"])])
        mt = by.groupby("month")["amount"].sum()
        fig.add_scatter(x=[fmt.month(m) for m in mt.index], y=mt.values, mode="text",
                        text=[fmt.compact(v) for v in mt.values], textposition="top center",
                        textfont=dict(size=11), showlegend=False, hoverinfo="skip")
        fig.update_layout(title="Dinero que regresa, próximos 12 meses (MXN)", barmode="stack")
        ui.style(fig, height=320, x_title="Mes", y_title="Monto", money_axis="y")
        fig.update_xaxes(categoryorder="array", categoryarray=[fmt.month(m) for m in sorted(set(by["month"]))])
        ui.headroom(fig, "y", mt.max(), 0.15)
        ui.draw(fig)
        table = fmt.whole(ev.assign(what=ev["what"].map(WHAT), date=[fmt.day(d) for d in ev["date"]]), ["amount"])
        st.dataframe(table[["date", "platform", "name", "what", "amount"]], hide_index=True,
                     height=min(360, 38 + 35 * len(table)), column_config={
                         "date": "Fecha", "platform": "Cuenta", "name": "Depósito", "what": "Concepto",
                         "amount": st.column_config.NumberColumn("Monto", format=fmt.TABLE_MONEY)})
    else:
        st.info("No hay pagos ni vencimientos en los próximos 12 meses para estas cuentas.",
                icon=":material/event_busy:")

    st.markdown("**Depósitos a plazo**")
    if deps.empty:
        st.caption("Ninguno en las cuentas elegidas.")
    else:
        d = fmt.whole(deps.assign(
            payout=deps["payout"].map({"monthly": "Mensual", "at_maturity": "Al vencimiento"}),
            annual_rate=deps["annual_rate"] * 100, end_date=deps["end_date"].map(fmt.day)),
            ["principal", "interest_after_tax"]).drop(columns=["start_date"])
        st.dataframe(d, hide_index=True, column_config={
            "platform": "Cuenta", "name": "Depósito",
            "principal": st.column_config.NumberColumn("Capital", format=fmt.TABLE_MONEY),
            "annual_rate": st.column_config.NumberColumn("Tasa", format="%.2f%%"),
            "term_days": st.column_config.NumberColumn("Plazo (días)", format="%d"),
            "end_date": "Vence", "payout": "Paga",
            "interest_after_tax": st.column_config.NumberColumn("Interés neto", format=fmt.TABLE_MONEY),
            "days_left": st.column_config.NumberColumn("Días restantes", format="%d")})

    st.markdown("**Ahorro disponible (sin plazo)**")
    od = only(mx.on_demand(snaps, as_of))
    if od.empty:
        st.caption("Ninguno en las cuentas elegidas.")
    else:
        # FINSUS doesn't report accumulated growth: show "–" there, not "None".
        od = fmt.whole(od.assign(annual_rate=od["annual_rate"] * 100, gain=od["gain"].map(fmt.money)), ["value"])
        st.dataframe(od, hide_index=True, column_config={
            "platform": "Cuenta", "name": "Cajita / subcuenta",
            "value": st.column_config.NumberColumn("Saldo", format=fmt.TABLE_MONEY),
            "annual_rate": st.column_config.NumberColumn("Tasa", format="%.2f%%"),
            "gain": st.column_config.TextColumn("Rendimiento acumulado", alignment="right")})
        st.caption("Nu: solo las cuatro Cajitas que cuentan. Los intereses mensuales de FINSUS llegan a finsus +.")

with tab_var:
    h = only(mx.holdings(snaps, as_of))
    if h.empty:
        st.info("No hay inversiones variables en las cuentas elegidas.", icon=":material/filter_alt_off:")
    else:
        known = h.dropna(subset=["gain"])
        known = known[known["asset_type"] != "cash"]
        with ui.card_row():
            for name in [p for p in ("GBM", "Bitso") if p in chosen]:
                v = plat_all.set_index("platform")["value"].get(name, 0.0)
                ui.card(name, fmt.compact(v), help=fmt.exact(v), note=fmt.day(as_of))
            if len(known):
                g, inv = known["gain"].sum(), known["invested"].sum()
                ui.card("Ganancia", fmt.signed(g), help=f"{fmt.exact(g)} sobre {fmt.exact(inv)} invertidos",
                        note=f"{fmt.pct(g / inv)} sobre lo invertido" if inv else None)

        ranked = known.sort_values("gain", ascending=False)
        views = {"3 mejores y 3 peores": lambda r: pd.concat([r.head(3), r.tail(3)]).loc[
                     lambda x: ~x.index.duplicated()],
                 "5 mejores": lambda r: r.head(5), "5 peores": lambda r: r.tail(5), "Todas": lambda r: r}
        shown = st.segmented_control("Posiciones a mostrar", list(views), default="3 mejores y 3 peores",
                                     key="w_holdings_view") or "3 mejores y 3 peores"
        g = views[shown](ranked).sort_values("gain")
        left, right = st.columns(2)
        with left:
            # The figure goes in the label ("VNQ · -$2.4k (-19.6%)"): text beside a negative bar would
            # run into the names.
            fig = go.Figure(go.Bar(
                y=[f"{n} · {fmt.signed(v)} ({fmt.pct(p)})" for n, v, p in zip(g["name"], g["gain"], g["gain_pct"])],
                x=g["gain"], orientation="h",
                marker_color=[c["up"] if v >= 0 else c["down"] for v in g["gain"]],
                hovertemplate="%{y}<extra></extra>"))
            fig.update_layout(title="Ganancia por posición (MXN)")
            ui.style(fig, height=max(260, 34 * len(g) + 90), x_title="Ganancia", money_axis="x", legend=False)
            ui.draw(fig)
        with right:
            mix = h.groupby("asset_type", as_index=False)["value"].sum().sort_values("value")
            fig = go.Figure(go.Bar(
                y=[ASSET_LABELS.get(t, t) for t in mix["asset_type"]], x=mix["value"], orientation="h",
                marker_color=tc["variable"], customdata=ui.shares(mix["value"]),
                text=[f"{fmt.compact(v)} · {fmt.pct(v / mix['value'].sum(), 0)}" for v in mix["value"]],
                textposition="outside", cliponaxis=False,
                hovertemplate="%{y}: %{x:$,.0f} · %{customdata:.1%} del total<extra></extra>"))
            fig.update_layout(title="Mezcla por tipo de activo (MXN)")
            ui.style(fig, height=max(260, 34 * len(mix) + 90), x_title="Valor", money_axis="x", legend=False)
            ui.headroom(fig, "x", mix["value"].max(), 0.6)
            ui.draw(fig)

        st.markdown("**Posiciones**")
        # Bitso reports no gain: those cells show "–", not "None".
        view = fmt.whole(h.assign(asset_type=h["asset_type"].map(lambda t: ASSET_LABELS.get(t, t)),
                                  gain=fmt.text(h["gain"], "signed"), invested=fmt.text(h["invested"]),
                                  gain_pct=fmt.text(h["gain_pct"], "pct")), ["value"])
        right_text = {"alignment": "right"}
        st.dataframe(view.drop(columns=["ticker"]), hide_index=True, column_config={
            "platform": "Cuenta", "name": "Posición", "asset_type": "Tipo",
            "units": st.column_config.NumberColumn("Títulos", format="%,.4g"),
            "value": st.column_config.NumberColumn("Valor", format=fmt.TABLE_MONEY),
            "gain": st.column_config.TextColumn("Ganancia ($)", **right_text),
            "invested": st.column_config.TextColumn("Invertido", **right_text),
            "gain_pct": st.column_config.TextColumn("Ganancia (%)", **right_text)})
        st.caption("Invertido = valor menos la ganancia que muestra la app. Bitso no muestra ganancia.")

with tab_ret:
    r = mx.retirement(snaps, as_of)
    a = r["allianz"]
    parts = mx.retirement_parts(snaps, as_of)
    parts = parts[parts["account"].isin(chosen)]
    if len(parts):
        total_ret = parts["value"].sum()
        with ui.card_row():
            ui.card("Total para el retiro", fmt.compact(total_ret), help=fmt.exact(total_ret),
                    note=f"{fmt.day(as_of)} · {parts['account'].nunique()} cuentas")
        parts = parts.assign(label=parts["part"].str.replace("Ahorro para la vivienda (Infonavit)",
                                                             "Vivienda (Infonavit)", regex=False),
                             share=ui.shares(parts["value"]))
        order = list(dict.fromkeys(parts["label"]))
        fig = go.Figure()
        for i, lab in enumerate(order):  # fixed palette order; the legend names each part
            d = parts[parts["label"] == lab]
            fig.add_bar(name=lab, y=d["account"], x=d["value"], orientation="h", marker_color=c["series"][i % 8],
                        customdata=d["share"],
                        hovertemplate=f"%{{y}} · {lab}: %{{x:$,.0f}} · %{{customdata:.1%}} del retiro<extra></extra>")
        acc = parts.groupby("account", sort=False)["value"].sum()
        fig.add_scatter(y=acc.index, x=acc.values, mode="text", text=[f"  {fmt.compact(v)}" for v in acc.values],
                        textposition="middle right", showlegend=False, hoverinfo="skip", cliponaxis=False)
        fig.update_layout(title=f"Dónde está el dinero del retiro · {fmt.day(as_of)} (MXN)", barmode="stack")
        ui.style(fig, height=110 * len(acc) + 120, x_title="Saldo", money_axis="x")
        fig.update_yaxes(categoryorder="array", categoryarray=list(acc.index)[::-1])
        ui.headroom(fig, "x", acc.max(), 0.2)
        ui.draw(fig)
    if "Allianz PPR" in chosen:
        st.markdown("**Allianz PPR**")
        with ui.card_row():
            ui.card("Valor actual", fmt.compact(a["total"]), help=fmt.exact(a["total"]), note=fmt.day(as_of))
            if a["statement_date"]:
                ui.card("Aportado", fmt.compact(a["contributions"]),
                        help=f"{fmt.exact(a['contributions'])}, según el estado de cuenta del "
                             f"{fmt.day(a['statement_date'])}", note=f"Al {fmt.day(a['statement_date'])}")
                ui.card("Ganancia", fmt.signed(a["statement_gain"]),
                        help=f"{fmt.exact(a['statement_gain'])}, según el estado de cuenta del "
                             f"{fmt.day(a['statement_date'])}",
                        note=f"{fmt.pct(a['statement_gain'] / a['contributions'])} sobre lo aportado"
                        if a["contributions"] else None)
        st.caption("El valor es el total actual de la app; lo aportado y la ganancia vienen del último estado de "
                   "cuenta, así que pueden ir unas semanas atrás.")
    if "Profuturo" in chosen:
        st.markdown("**Profuturo (Afore)**")
        prof = r["profuturo"]
        housing = prof[prof["name"].str.contains(HOUSING, case=False)]["value"].sum()
        with ui.card_row():
            ui.card("Total", fmt.compact(r["profuturo_total"]), help=fmt.exact(r["profuturo_total"]),
                    note=fmt.day(as_of))
            ui.card("Ahorro para el retiro", fmt.compact(r["profuturo_total"] - housing),
                    help=fmt.exact(r["profuturo_total"] - housing), note="Retiro y voluntario")
            ui.card("Vivienda (Infonavit)", fmt.compact(housing), help=fmt.exact(housing), note="Subcuenta aparte")
        st.dataframe(fmt.whole(prof, ["value"]), hide_index=True, column_config={
            "name": "Subcuenta", "value": st.column_config.NumberColumn("Saldo", format=fmt.TABLE_MONEY)})
        st.caption("Profuturo no muestra rendimiento, así que su rendimiento mensual es estimado.")
    if "Allianz PPR" not in chosen and "Profuturo" not in chosen:
        st.info("No hay cuentas de retiro en la selección.", icon=":material/filter_alt_off:")
