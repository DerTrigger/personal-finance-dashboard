"""Ingresos: where the money came from. Click a month or a source to filter the whole view."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import plotly.graph_objects as go  # noqa: E402
import streamlit as st  # noqa: E402

from app.lib import fmt, ui  # noqa: E402
from app.lib import metrics as mx  # noqa: E402

PAGE, KIND = "ingresos", "income"
MODES = {"Mes anterior": "prev_month", "Mismo mes del año anterior": "prev_year"}

snaps, tx, _ = ui.load()
c = ui.colors()
st.title("Ingresos")

scope = tx[tx["type"] == KIND]
f1, f2, f3 = st.columns([2, 2, 2])
with f1:
    period = ui.period_picker(snaps, tx)
with f2:
    accounts = ui.multi("Cuentas", sorted(scope["account"].unique()), "accounts_inc", "Todas las cuentas")
with f3:
    sources = ui.multi("Fuentes", sorted(scope["category"].unique()), "categories_inc", "Todas las fuentes")
ui.period_presets()

base = mx.filter_tx(tx, dates=period, accounts=accounts)
inc = mx.filter_tx(base, categories=sources)
inc = inc[inc["type"] == KIND]
if inc.empty:
    st.info("No hay ingresos con estos filtros.", icon=":material/filter_alt_off:")
    st.stop()

click_months = ui.picked(PAGE, "by_month", 0)
click_sources = list(dict.fromkeys(ui.picked(PAGE, "by_month", 1) + ui.picked(PAGE, "by_source", 0)))
click_sources = [x for x in click_sources if x != ui.OTHER]
ui.active_filters(PAGE, {"Mes": [fmt.month(m) for m in click_months], "Fuente": click_sources})


def narrow(df, months=True, sources_=True):
    if months and click_months:
        df = df[df["month"].isin(click_months)]
    if sources_ and click_sources:
        df = df[df["category"].isin(click_sources)]
    return df


view = narrow(inc)
months_in_period = sorted(base["month"].unique())
monthly = view.groupby("month")["amount"].sum().reindex(months_in_period, fill_value=0.0)

# --- Cards --------------------------------------------------------------------
mode = MODES[st.segmented_control("Comparar con", list(MODES), default="Mes anterior", key="w_mode_inc")
             or "Mes anterior"]
focus = click_months[-1] if click_months else months_in_period[-1]
other = mx.other_month(focus, mode)
all_inc = narrow(mx.filter_tx(scope, accounts=accounts, categories=sources), months=False)
this_amt = all_inc.loc[all_inc["month"] == focus, "amount"].sum()
other_amt = all_inc.loc[all_inc["month"] == other, "amount"].sum()
n_months = len(click_months) or len(months_in_period)
# Net income ignores the source filter and clicks on sources: it needs every expense in the same months.
flow = mx.cashflow(narrow(base, sources_=False))
rate = flow["net_income"].sum() / flow["income"].sum() if flow["income"].sum() else None

with ui.card_row():
    ui.card("Total", fmt.compact(view["amount"].sum()), help=fmt.exact(view["amount"].sum()),
            note=f"{len(view):,} movimientos", spark=list(monthly.values))
    ui.card("Promedio mensual", fmt.compact(view["amount"].sum() / n_months),
            help=fmt.exact(view["amount"].sum() / n_months), note=f"{n_months} meses")
    ui.card(f"Ingreso de {fmt.month(focus)}", fmt.compact(this_amt), help=fmt.exact(this_amt),
            delta=f"{fmt.signed(this_amt - other_amt)} vs. {fmt.month(other)}" if other_amt else None,
            note=None if other_amt else f"Sin datos en {fmt.month(other)}")
    ui.card("Ingreso neto", fmt.compact(flow["net_income"].sum()), help=fmt.exact(flow["net_income"].sum()),
            note=f"Tasa de ahorro {fmt.pct(rate)}", spark=list(flow["net_income"]))

# --- By month, stacked by source ----------------------------------------------
mapping = ui.category_colors(tx, KIND)
by_month = ui.fold(mx.income_by_source(narrow(inc, months=False, sources_=bool(ui.picked(PAGE, "by_source", 0)))),
                   "category", mapping).groupby(["month", "category"], as_index=False)["amount"].sum()
by_month["share"] = ui.shares(by_month["amount"], by_month["month"])
fig = go.Figure()
for src, color in mapping.items():
    d = by_month[by_month["category"] == src]
    if d.empty:
        continue
    fig.add_bar(name=src, x=[fmt.month(m) for m in d["month"]], y=d["amount"], marker_color=color,
                customdata=list(zip(d["month"], d["category"], d["share"])),
                hovertemplate=f"{src}<br>%{{x}}: %{{y:$,.0f}} · %{{customdata[2]:.1%}} del mes<extra></extra>")
totals = by_month.groupby("month")["amount"].sum()
fig.add_scatter(x=[fmt.month(m) for m in totals.index], y=totals.values, mode="text",
                text=[fmt.compact(v) for v in totals.values], textposition="top center",
                textfont=dict(size=11), showlegend=False, hoverinfo="skip")
fig.update_layout(title="Ingreso por mes y fuente (MXN)", barmode="stack")
ui.style(fig, height=400, x_title="Mes", y_title="Ingreso", money_axis="y")
fig.update_xaxes(categoryorder="array", categoryarray=[fmt.month(m) for m in months_in_period])
ui.headroom(fig, "y", totals.max(), 0.12)
ui.draw(fig, key=ui.chart_key(PAGE, "by_month"), clickable=True)

left, right = st.columns(2)
with left:
    src_totals = narrow(inc, sources_=False).groupby("category")["amount"].sum().sort_values()
    fig = go.Figure(go.Bar(
        y=src_totals.index, x=src_totals.values, orientation="h",
        customdata=list(zip(src_totals.index, ui.shares(src_totals.values))),
        marker_color=[mapping.get(x, c["neutral"]) for x in src_totals.index],
        text=[fmt.compact(v) for v in src_totals.values], textposition="outside", cliponaxis=False,
        hovertemplate="%{y}: %{x:$,.0f} · %{customdata[1]:.1%} del total<extra></extra>"))
    fig.update_layout(title="Por fuente · clic para filtrar (MXN)")
    ui.style(fig, height=max(300, 30 * len(src_totals) + 90), x_title="Ingreso", money_axis="x", legend=False)
    ui.headroom(fig, "x", src_totals.max(), 0.4)
    ui.draw(fig, key=ui.chart_key(PAGE, "by_source"), clickable=True)
with right:
    fig = go.Figure(go.Scatter(
        x=[fmt.month(m) for m in flow["month"]], y=flow["savings_rate"], mode="lines+markers",
        line=dict(color=c["series"][0], width=2), marker=dict(size=8, color=c["series"][0]),
        hovertemplate="%{x}: %{y:.1%}<extra></extra>"))
    fig.update_layout(title="Tasa de ahorro por mes")
    ui.style(fig, height=320, x_title="Mes", y_title="Tasa de ahorro", legend=False)
    fig.update_yaxes(tickformat=".0%")
    ui.draw(fig)

st.subheader(f"Detalle: {', '.join(click_sources) or 'todos los ingresos'}")
detail = fmt.whole(view.sort_values("timestamp", ascending=False), ["amount"])
st.dataframe(detail[["date", "account", "category", "subcategory", "note", "amount"]], hide_index=True,
             height=min(420, 38 + 35 * len(detail)), column_config={
                 "date": "Fecha", "account": "Cuenta", "category": "Fuente", "subcategory": "Subcategoría",
                 "note": "Nota", "amount": st.column_config.NumberColumn("Monto", format=fmt.TABLE_MONEY)})
st.caption(f"{len(detail):,} movimientos · {fmt.money(view['amount'].sum())}")

st.subheader(f"{fmt.month(focus)} vs. {fmt.month(other)}")
comp = mx.compare_months(mx.filter_tx(tx, accounts=accounts, categories=sources), focus, mode, kind=KIND)
comp = fmt.whole(comp.assign(change_pct=comp["change_pct"].map(fmt.change_pct)), ["this", "other", "change"])
st.dataframe(comp, hide_index=True, column_config={
    "category": "Fuente",
    "this": st.column_config.NumberColumn(fmt.month(focus), format=fmt.TABLE_MONEY),
    "other": st.column_config.NumberColumn(fmt.month(other), format=fmt.TABLE_MONEY),
    "change": st.column_config.NumberColumn("Cambio ($)", format=fmt.TABLE_SIGNED),
    "change_pct": st.column_config.TextColumn("Cambio (%)")})
st.caption("Haz clic en un mes de la gráfica para cambiar el mes que se compara.")
