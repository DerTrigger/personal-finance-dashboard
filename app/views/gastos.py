"""Gastos: where the money went. Click a month, category or subcategory to filter the whole view."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import plotly.graph_objects as go  # noqa: E402
import streamlit as st  # noqa: E402

from app.lib import fmt, ui  # noqa: E402
from app.lib import metrics as mx  # noqa: E402

PAGE, KIND = "gastos", "expense"
MODES = {"Mes anterior": "prev_month", "Mismo mes del año anterior": "prev_year"}

snaps, tx, _ = ui.load()
c = ui.colors()
st.title("Gastos")

scope = tx[tx["type"] == KIND]
f1, f2, f3 = st.columns([2, 2, 2])
with f1:
    period = ui.period_picker(snaps, tx)
with f2:
    accounts = ui.multi("Cuentas", sorted(scope["account"].unique()), "accounts_exp", "Todas las cuentas")
with f3:
    categories = ui.multi("Categorías", sorted(scope["category"].unique()), "categories_exp", "Todas las categorías")
ui.period_presets()

base = mx.filter_tx(tx, dates=period, accounts=accounts, categories=categories)
spend = base[base["type"] == KIND]
if spend.empty:
    st.info("No hay gastos con estos filtros.", icon=":material/filter_alt_off:")
    st.stop()

# --- Clicks: read first so every visual can use them --------------------------
click_months = ui.picked(PAGE, "by_month", 0)
click_cats = list(dict.fromkeys(ui.picked(PAGE, "by_month", 1) + ui.picked(PAGE, "by_category", 0)))
click_cats = [x for x in click_cats if x != ui.OTHER]
click_subs = ui.picked(PAGE, "by_sub", 0)
ui.active_filters(PAGE, {"Mes": [fmt.month(m) for m in click_months], "Categoría": click_cats,
                         "Subcategoría": click_subs})


def narrow(df, months=True, cats=True, subs=True):
    """Apply the clicks, except the ones a chart makes itself (it keeps showing all its bars)."""
    if months and click_months:
        df = df[df["month"].isin(click_months)]
    if cats and click_cats:
        df = df[df["category"].isin(click_cats)]
    if subs and click_subs:
        df = df[df["subcategory"].replace("", mx.NO_SUB).isin(click_subs)]
    return df


view = narrow(spend)
months_in_period = sorted(spend["month"].unique())
monthly = view.groupby("month")["amount"].sum().reindex(months_in_period, fill_value=0.0)

# --- Cards --------------------------------------------------------------------
mode_label = st.segmented_control("Comparar con", list(MODES), default="Mes anterior", key="w_mode_exp") \
    or "Mes anterior"
mode = MODES[mode_label]
focus = click_months[-1] if click_months else months_in_period[-1]
other = mx.other_month(focus, mode)
narrowed_all = narrow(mx.filter_tx(tx[tx["type"] == KIND], accounts=accounts, categories=categories), months=False)
this_amt = narrowed_all.loc[narrowed_all["month"] == focus, "amount"].sum()
other_amt = narrowed_all.loc[narrowed_all["month"] == other, "amount"].sum()
n_months = len(click_months) or len(months_in_period)
top = view.groupby("category")["amount"].sum().sort_values(ascending=False)

with ui.card_row():
    ui.card("Total", fmt.compact(view["amount"].sum()), help=fmt.exact(view["amount"].sum()),
            note=f"{len(view):,} movimientos", spark=list(monthly.values))
    ui.card("Promedio mensual", fmt.compact(view["amount"].sum() / n_months),
            help=fmt.exact(view["amount"].sum() / n_months), note=f"{n_months} meses")
    ui.card(f"Gasto de {fmt.month(focus)}", fmt.compact(this_amt), help=fmt.exact(this_amt),
            delta=f"{fmt.signed(this_amt - other_amt)} vs. {fmt.month(other)}" if other_amt else None,
            delta_color="inverse", note=None if other_amt else f"Sin datos en {fmt.month(other)}")
    if len(top):
        ui.card("Categoría principal", top.index[0], help=fmt.exact(top.iloc[0]),
                note=f"{fmt.compact(top.iloc[0])} · {fmt.pct(top.iloc[0] / top.sum(), 0)} del total")

# --- By month, stacked by category --------------------------------------------
mapping = ui.category_colors(tx, KIND)
by_month = ui.fold(mx.expenses_by(narrow(spend, months=False, cats=bool(ui.picked(PAGE, "by_category", 0))),
                                  "category"), "category", mapping)
by_month = by_month.groupby(["month", "category"], as_index=False)["amount"].sum()
by_month["share"] = ui.shares(by_month["amount"], by_month["month"])
fig = go.Figure()
for cat, color in mapping.items():
    d = by_month[by_month["category"] == cat]
    if d.empty:
        continue
    fig.add_bar(name=cat, x=[fmt.month(m) for m in d["month"]], y=d["amount"], marker_color=color,
                customdata=list(zip(d["month"], d["category"], d["share"])),
                hovertemplate=f"{cat}<br>%{{x}}: %{{y:$,.0f}} · %{{customdata[2]:.1%}} del mes<extra></extra>")
totals = by_month.groupby("month")["amount"].sum()
fig.add_scatter(x=[fmt.month(m) for m in totals.index], y=totals.values, mode="text",
                text=[fmt.compact(v) for v in totals.values], textposition="top center",
                textfont=dict(size=11), showlegend=False, hoverinfo="skip")
fig.update_layout(title="Gasto por mes y categoría (MXN)", barmode="stack")
ui.style(fig, height=400, x_title="Mes", y_title="Gasto", money_axis="y")
fig.update_xaxes(categoryorder="array", categoryarray=[fmt.month(m) for m in months_in_period])
ui.headroom(fig, "y", totals.max(), 0.12)
ui.draw(fig, key=ui.chart_key(PAGE, "by_month"), clickable=True)

# --- Level 1 and 2: category -> subcategory -> detail --------------------------
left, right = st.columns(2)
with left:
    cat_totals = narrow(spend, cats=False).groupby("category")["amount"].sum().sort_values()
    fig = go.Figure(go.Bar(
        y=cat_totals.index, x=cat_totals.values, orientation="h",
        customdata=list(zip(cat_totals.index, ui.shares(cat_totals.values))),
        marker_color=[mapping.get(x, c["neutral"]) for x in cat_totals.index],
        text=[fmt.compact(v) for v in cat_totals.values], textposition="outside", cliponaxis=False,
        hovertemplate="%{y}: %{x:$,.0f} · %{customdata[1]:.1%} del total<extra></extra>"))
    fig.update_layout(title="Por categoría · clic para ver subcategorías (MXN)")
    ui.style(fig, height=max(320, 28 * len(cat_totals) + 90), x_title="Gasto", money_axis="x", legend=False)
    ui.headroom(fig, "x", cat_totals.max(), 0.4)
    ui.draw(fig, key=ui.chart_key(PAGE, "by_category"), clickable=True)
with right:
    chosen = click_cats or (categories or [])
    if len(chosen) != 1:
        st.markdown("**Subcategorías**")
        st.info("Haz clic en una categoría (o elige una en el filtro) para ver sus subcategorías.",
                icon=":material/touch_app:")
    else:
        cat = chosen[0]
        subs = mx.expenses_by(narrow(spend, subs=False), "subcategory").groupby("subcategory")["amount"] \
            .sum().sort_values()
        fig = go.Figure(go.Bar(
            y=subs.index, x=subs.values, orientation="h", customdata=list(zip(subs.index, ui.shares(subs.values))),
            marker_color=mapping.get(cat, c["neutral"]),
            text=[fmt.compact(v) for v in subs.values], textposition="outside", cliponaxis=False,
            hovertemplate=f"%{{y}}: %{{x:$,.0f}} · %{{customdata[1]:.1%}} de {cat}<extra></extra>"))
        fig.update_layout(title=f"{cat} por subcategoría · clic para ver el detalle (MXN)")
        ui.style(fig, height=max(320, 28 * len(subs) + 90), x_title="Gasto", money_axis="x", legend=False)
        ui.headroom(fig, "x", subs.max(), 0.4)
        ui.draw(fig, key=ui.chart_key(PAGE, "by_sub"), clickable=True)

detail_title = " › ".join(click_cats[:1] + click_subs[:1]) if (click_cats or click_subs) else "todos los gastos"
st.subheader(f"Detalle: {detail_title}")
detail = view.sort_values("timestamp", ascending=False)
detail = fmt.whole(detail.assign(subcategory=detail["subcategory"].replace("", mx.NO_SUB),
                                  card=detail["note"].map(mx.payment_tag)), ["amount"])
cols = ["date", "account", "category", "subcategory", "note", "description", "card", "amount"]
cols = [x for x in cols if x != "description" or detail["description"].astype(str).str.strip().any()]
cols = [x for x in cols if x != "card" or detail["card"].ne("").any()]
st.dataframe(detail[cols],
             hide_index=True, height=min(420, 38 + 35 * len(detail)), column_config={
                 "date": "Fecha", "account": "Cuenta", "category": "Categoría", "subcategory": "Subcategoría",
                 "note": "Nota", "description": "Descripción",
                 "card": st.column_config.TextColumn("Tarjeta por pagar",
                                                     help="De la nota: IN NU = apartado en Nu; NPY = sin apartar"),
                 "amount": st.column_config.NumberColumn("Monto", format=fmt.TABLE_MONEY)})
st.caption(f"{len(detail):,} movimientos · {fmt.money(view['amount'].sum())}")

# --- Month comparison -----------------------------------------------------------
st.subheader(f"{fmt.month(focus)} vs. {fmt.month(other)}")
comp = mx.compare_months(mx.filter_tx(tx, accounts=accounts, categories=categories), focus, mode, kind=KIND)
comp = fmt.whole(comp.assign(change_pct=comp["change_pct"].map(fmt.change_pct)), ["this", "other", "change"])
st.dataframe(comp, hide_index=True, column_config={
    "category": "Categoría",
    "this": st.column_config.NumberColumn(fmt.month(focus), format=fmt.TABLE_MONEY),
    "other": st.column_config.NumberColumn(fmt.month(other), format=fmt.TABLE_MONEY),
    "change": st.column_config.NumberColumn("Cambio ($)", format=fmt.TABLE_SIGNED),
    "change_pct": st.column_config.TextColumn("Cambio (%)")})
st.caption("Haz clic en un mes de la gráfica para cambiar el mes que se compara.")
