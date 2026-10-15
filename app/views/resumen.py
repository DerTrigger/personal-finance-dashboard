"""Resumen: net worth today, how it evolved, what explains the change, cash flow. Click to filter."""
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

PAGE = "resumen"
TOP_DONUT = 5  # donut slices: the top 5 categories + "Resto"
DIM = 0.3  # opacity of the months not clicked, so the clicked one stands out
snaps, tx, _ = ui.load()
s = ui.settings()
c = ui.colors()
tcolors = ui.type_colors()

st.title("Evolución y estado actual del patrimonio")
dates_all = sn.snapshot_dates(snaps)
f1, _ = st.columns([2, 3])
with f1:
    period = ui.period_picker(snaps, tx)
ui.period_presets()

# Clicks (read first, so every visual can use them)
click_dates = ui.picked(PAGE, "evolution", 0)
click_types = ui.picked(PAGE, "evolution", 1)
click_months = list(dict.fromkeys(ui.picked(PAGE, "cashflow", 0) + ui.picked(PAGE, "income", 0)))
click_sources = [x for x in ui.picked(PAGE, "income", 1) if x != ui.OTHER]
ui.active_filters(PAGE, {"Fecha": [fmt.day(d) for d in click_dates],
                         "Tipo": [ui.TYPE_LABELS.get(t, t) for t in click_types],
                         "Mes": [fmt.month(m) for m in sorted(click_months)],
                         "Fuente": click_sources})

series = mx.net_worth_series(snaps, dates=period)
if series.empty:  # no snapshot inside the period: use the latest one before it
    series = mx.net_worth_series(snaps).tail(1)
by_type = mx.net_worth_by_date(snaps, "account_type", dates=(series["as_of"].min(), series["as_of"].max()))
as_of = click_dates[-1] if click_dates else series["as_of"].iloc[-1]
earlier = [d for d in dates_all if d < as_of]

period_tx = mx.filter_tx(tx, dates=period)
cf_all = mx.cashflow(period_tx)
this_month = date.today().strftime("%Y-%m")
full = cf_all[cf_all["month"] < this_month]
month = sorted(click_months)[-1] if click_months else (full["month"].iloc[-1] if len(full) else None)
events = [e for e in mx.upcoming(snaps, s["tax"]["isr_rate"], date.today(), days=365)
          if e["what"] != "interest (after tax)"]
owed = mx.card_pending(tx)


def dim(months):
    """Bar opacity: full for clicked months (or all, when none is clicked)."""
    return [1.0 if not click_months or m in click_months else DIM for m in months]


# --- Estado actual ------------------------------------------------------------
st.subheader("Estado actual")
with ui.card_row():
    nw = by_type[(by_type["as_of"] == as_of) & (by_type["account_type"].isin(click_types) if click_types else True)]
    value = nw["value"].sum() if click_types else float(series.set_index("as_of")["net_worth"].get(
        as_of, mx.net_worth_series(snaps).set_index("as_of")["net_worth"][as_of]))
    delta, note = None, f"{fmt.day(as_of)} · primer mes"
    if earlier and not click_types:
        prev = mx.net_worth_series(snaps).set_index("as_of")["net_worth"][earlier[-1]]
        delta = f"{fmt.signed(value - prev)} vs. {fmt.day(earlier[-1])}"
    elif click_types:
        note = f"{fmt.day(as_of)} · solo " + ", ".join(ui.TYPE_LABELS[t] for t in click_types)
    ui.card("Patrimonio", fmt.compact(value), help=f"{fmt.exact(value)} al {fmt.day(as_of)}", delta=delta,
            note=note, spark=list(series["net_worth"]))
    if events:
        e = events[0]
        ui.card("Próximo vencimiento", fmt.compact(e["amount"]),
                help=f"{fmt.exact(e['amount'])} · {e['platform']} · {e['name']} · {fmt.day(e['date'])}",
                note=f"{fmt.day(e['date'])} · {e['platform']}")
    else:
        ui.card("Próximo vencimiento", "–", note="Ninguno en 12 meses")
    if month:
        row = cf_all.set_index("month").reindex([month]).iloc[0]
        ui.card("Ingreso neto", fmt.compact(row["net_income"]),
                help=f"{fmt.exact(row['net_income'])} en {fmt.month(month)}",
                note=f"{fmt.month(month)} · ahorro {fmt.pct(row['savings_rate'])}",
                spark=list(cf_all["net_income"]))
    inc, exp_ = cf_all["income"].sum(), cf_all["expenses"].sum()
    rate = (inc - exp_) / inc if inc else None
    ui.card("Tasa de ahorro", fmt.pct(rate), help=f"Del periodo. Ingresos {fmt.exact(inc)} · gastos {fmt.exact(exp_)}",
            note="Del periodo elegido", spark=list(cf_all["savings_rate"].fillna(0)))

# Unpaid card charges, from the IN NU / NPY tags in Money Manager notes. Always today's, whatever the period.
with ui.card_row(align="left"):
    total_owed, aside, not_aside = owed["amount"].sum(), owed["set_aside"].sum(), owed["not_set_aside"].sum()
    ui.card("Tarjetas por pagar", fmt.compact(total_owed),
            help=f"{fmt.exact(total_owed)} en {len(owed)} cargos con IN NU o NPY en la nota, del último archivo de "
                 "Money Manager (hoy, sin importar el periodo)",
            note=f"{len(owed)} cargos" if len(owed) else "Nada pendiente")
    ui.card("Apartado en Nu", fmt.compact(aside), help=f"{fmt.exact(aside)} · notas con IN NU",
            note=fmt.pct(aside / total_owed, 0) + " del total" if total_owed else None)
    ui.card("Sin apartar", fmt.compact(not_aside), help=f"{fmt.exact(not_aside)} · notas con NPY, o la parte no "
            "apartada de un \"$200 IN NU\"", note=fmt.pct(not_aside / total_owed, 0) + " del total" if total_owed
            else None)

# --- Evolución -----------------------------------------------------------------
left, right = st.columns([3, 2])
with left:
    by_type["share"] = ui.shares(by_type["value"], by_type["as_of"])
    fig = go.Figure()
    for t in ui.TYPE_ORDER:
        d = by_type[by_type["account_type"] == t]
        if d.empty:
            continue
        fig.add_bar(name=ui.TYPE_LABELS[t], x=[fmt.day(x) for x in d["as_of"]], y=d["value"],
                    marker_color=tcolors[t], customdata=list(zip(d["as_of"], d["account_type"], d["share"])),
                    hovertemplate=f"{ui.TYPE_LABELS[t]}<br>%{{x}}: %{{y:$,.0f}} · "
                                  f"%{{customdata[2]:.1%}} del patrimonio<extra></extra>")
    totals = by_type.groupby("as_of")["value"].sum()
    fig.add_scatter(x=[fmt.day(x) for x in totals.index], y=totals.values, mode="text",
                    text=[fmt.compact(v) for v in totals.values], textposition="top center",
                    textfont=dict(size=13), showlegend=False, hoverinfo="skip")
    fig.update_layout(title="Patrimonio por tipo (MXN)", barmode="stack")
    ui.style(fig, height=380, x_title="Fecha de corte", y_title="Patrimonio", money_axis="y")
    ui.headroom(fig, "y", totals.max(), 0.12)
    ui.draw(fig, key=ui.chart_key(PAGE, "evolution"), clickable=True)
with right:
    plat = mx.net_worth_by_platform(snaps, as_of)
    if click_types:
        plat = plat[plat["account_type"].isin(click_types)]
    plat = plat.sort_values("value")
    pcolors = ui.platform_colors()
    fig = go.Figure(go.Bar(
        y=[ui.platform_label(p) for p in plat["platform"]], x=plat["value"], orientation="h",
        marker_color=[pcolors.get(p, c["neutral"]) for p in plat["platform"]],
        customdata=ui.shares(plat["value"]),
        text=[fmt.compact(v) for v in plat["value"]], textposition="outside", cliponaxis=False,
        hovertemplate="%{y}: %{x:$,.0f} · %{customdata:.1%} del total<extra></extra>"))
    fig.update_layout(title=f"Dónde está · {fmt.day(as_of)} (MXN)")
    ui.style(fig, height=380, x_title="Saldo", money_axis="x", legend=False)
    ui.headroom(fig, "x", plat["value"].max(), 0.4)
    ui.draw(fig)

# --- Qué explica el cambio ------------------------------------------------------
st.subheader("Qué explica el cambio")
why = mx.why_changed(snaps, tx, s)
if click_dates:  # a clicked date: the change that ends on it
    why = why[why["end"] == as_of]
else:
    why = why[(why["end"] >= str(period[0])) & (why["end"] <= str(period[1]))]
if why.empty:
    ui.first_month_note()
else:
    parts = [("Dinero aportado", why["put_in"].sum()), ("Rendimientos", why["returns"].sum()),
             ("Rendimientos estimados", why["estimated_returns"].sum()), ("Revaluación", why["revaluation"].sum())]
    fig = go.Figure(go.Bar(
        y=[p[0] for p in parts][::-1], x=[p[1] for p in parts][::-1], orientation="h",
        marker_color=[c["up"] if p[1] >= 0 else c["down"] for p in parts][::-1],
        text=[fmt.signed(p[1]) for p in parts][::-1], textposition="outside", cliponaxis=False,
        hovertemplate="%{y}: %{x:$,.0f}<extra></extra>"))
    fig.update_layout(title=f"{fmt.day(why['start'].iloc[0])} a {fmt.day(why['end'].iloc[-1])}: "
                            f"{fmt.signed(why['change'].sum())} (MXN)")
    ui.style(fig, height=260, x_title="Cambio en el patrimonio", money_axis="x", legend=False)
    ui.draw(fig)
    st.caption("Rendimientos: lo que reporta cada plataforma. Estimados: Bitso y Profuturo no muestran rendimiento, "
               "así que todo su cambio cuenta como rendimiento. Revaluación: auto y bienes del hogar. "
               "Dinero aportado: el resto del cambio.")

# --- Flujo ----------------------------------------------------------------------
st.subheader("Ingresos y gastos")
spent_share = (cf_all["expenses"] / cf_all["income"].where(cf_all["income"] != 0)).fillna(0.0)
months_x = [fmt.month(m) for m in cf_all["month"]]
fig = go.Figure([
    go.Bar(name="Ingresos", x=months_x, y=cf_all["income"], marker_color=c["series"][0],
           marker_opacity=dim(cf_all["month"]), customdata=cf_all["month"],
           hovertemplate="%{x}<br>Ingresos: %{y:$,.0f}<extra></extra>"),
    go.Bar(name="Gastos", x=months_x, y=cf_all["expenses"], marker_color=c["series"][1],
           marker_opacity=dim(cf_all["month"]), customdata=list(zip(cf_all["month"], spent_share)),
           hovertemplate="%{x}<br>Gastos: %{y:$,.0f} · %{customdata[1]:.1%} del ingreso<extra></extra>"),
])
fig.update_layout(title="Por mes, sin transferencias entre cuentas (MXN)", barmode="group")
ui.style(fig, height=340, x_title="Mes", y_title="Monto", money_axis="y")
ui.draw(fig, key=ui.chart_key(PAGE, "cashflow"), clickable=True)

left, right = st.columns([3, 2])
with left:
    mapping = ui.category_colors(tx, "income")
    src = ui.fold(mx.income_by_source(period_tx), "category", mapping) \
        .groupby(["month", "category"], as_index=False)["amount"].sum()
    src["share"] = ui.shares(src["amount"], src["month"])
    fig = go.Figure()
    for name, color in mapping.items():
        d = src[src["category"] == name]
        if d.empty:
            continue
        fig.add_bar(name=name, x=[fmt.month(m) for m in d["month"]], y=d["amount"], marker_color=color,
                    marker_opacity=dim(d["month"]), customdata=list(zip(d["month"], d["category"], d["share"])),
                    hovertemplate=f"{name}<br>%{{x}}: %{{y:$,.0f}} · %{{customdata[2]:.1%}} del mes<extra></extra>")
    fig.update_layout(title="Ingresos por fuente (MXN)", barmode="stack")
    ui.style(fig, height=360, x_title="Mes", y_title="Ingreso", money_axis="y")
    # Half-width chart: label every other month (always the latest) so labels stay flat.
    fig.update_xaxes(categoryorder="array", categoryarray=months_x, tickangle=0,
                     tickvals=months_x[::-2] if len(months_x) > 6 else months_x)
    ui.draw(fig, key=ui.chart_key(PAGE, "income"), clickable=True)
with right:
    spend = period_tx[period_tx["type"] == "expense"]
    if click_months:
        spend = spend[spend["month"].isin(click_months)]
    cmap = ui.category_colors(tx, "expense")
    cats = ui.fold(spend, "category", cmap).groupby("category")["amount"].sum().sort_values(ascending=False)
    named = cats.drop(ui.OTHER, errors="ignore")
    top = named.head(TOP_DONUT)
    rest = cats.sum() - top.sum()
    slices = top if rest <= 0.005 else pd.concat([top, pd.Series({ui.OTHER: rest})])
    when = ", ".join(fmt.month(m) for m in sorted(click_months)) if click_months else "el periodo"
    if slices.empty:
        st.markdown(f"**Gastos por categoría · {when}**")
        st.caption("No hay gastos en este periodo.")
    else:
        fig = go.Figure(go.Pie(
            labels=slices.index, values=slices.values, hole=0.62, sort=False, direction="clockwise",
            marker=dict(colors=[cmap.get(x, c["neutral"]) for x in slices.index], line=dict(color=ui.GAP, width=2)),
            # Labels only on slices big enough to hold one; the small ones show theirs on hover.
            text=[f"{v / slices.sum():.0%}" if v / slices.sum() >= 0.05 else "" for v in slices.values],
            textinfo="text", textposition="outside",
            hovertemplate="%{label}: %{value:$,.0f} · %{percent:.1%}<extra></extra>"))
        fig.update_layout(title=f"Gastos por categoría · {when} (MXN)",
                          annotations=[dict(text=f"<b>{fmt.compact(slices.sum())}</b><br>gasto", showarrow=False,
                                            font=dict(size=15), x=0.5, y=0.5, xref="paper", yref="paper")])
        ui.style(fig, height=360)
        # Room around the ring for the outside labels (pies get no automatic margins).
        fig.update_layout(legend=dict(orientation="v", y=0.5, yanchor="middle", x=1.02),
                          margin=dict(l=40, r=16, t=36, b=36))
        ui.draw(fig)
        st.caption("Las 5 categorías más grandes; el resto se agrupa en \"Resto\". Haz clic en un mes para verlo solo.")
