"""
Shared pieces for every dashboard screen: data, filters, click-to-filter, chart style. All text in Spanish.

Data comes from finance.db (read-only). Set FINANCE_DB to point at another database (the page tests do).
Chart colors: the validated dataviz palette, with its own light and dark steps.
"""
import os
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import streamlit as st

from app.lib import db, fmt
from app.lib.config import data_path, load_settings, platforms

PALETTE = {
    "light": {
        "series": ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"],
        "up": "#2a78d6", "down": "#e34948", "neutral": "#898781",
        "ink": "#0b0b0b", "ink2": "#52514e", "muted": "#6f6e69", "grid": "#e9e8e2", "axis": "#c3c2b7",
        "surface": "#fcfcfb",
    },
    "dark": {
        "series": ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300", "#9085e9", "#e66767"],
        "up": "#3987e5", "down": "#e66767", "neutral": "#898781",
        "ink": "#f5f5f2", "ink2": "#c3c2b7", "muted": "#a3a29b", "grid": "#2c2c2a", "axis": "#4a4a46",
        "surface": "#1a1a19",
    },
}
FONT = '"Segoe UI Variable Text", "Segoe UI", system-ui, sans-serif'
OTHER = "Resto"  # not "Otros": Money Manager already has a category called "Other"
TOP_CATEGORIES = 7  # 7 colors + "Resto"; never more than 8 hues
GAP = "rgba(128,128,128,0.35)"  # line between stacked bar segments; readable on light and dark

TYPE_ORDER = ["sofipo_fixed", "sofipo_on_demand", "variable", "retirement", "manual_asset"]
TYPE_LABELS = {
    "sofipo_fixed": "Plazo fijo",
    "sofipo_on_demand": "Ahorro disponible",
    "variable": "Variable",
    "retirement": "Retiro",
    "manual_asset": "Bienes (auto y hogar)",
}


# --- Data --------------------------------------------------------------------

@st.cache_data
def settings():
    return load_settings()


def db_file():
    return Path(os.environ.get("FINANCE_DB") or data_path(settings(), "database"))


@st.cache_data
def _load(path, mtime):
    return {t: db.read_table(path, t) for t in ("snapshot_items", "transactions", "adjustments")}


def load():
    """Tables from finance.db, re-read whenever the file changes (after build_db.py)."""
    path = db_file()
    if not path.exists():
        st.error(f"No encontré la base de datos en {path}. Corre tools\\build_db.py primero.")
        st.stop()
    data = _load(str(path), path.stat().st_mtime)
    return data["snapshot_items"], data["transactions"], data["adjustments"]


# --- Colors ------------------------------------------------------------------

def colors():
    mode = None
    try:
        mode = st.context.theme.type
    except Exception:
        pass
    return PALETTE.get(mode or "light", PALETTE["light"])


def type_colors():
    c = colors()
    return {t: c["series"][i] for i, t in enumerate(TYPE_ORDER)}


def platform_colors():
    """Each investment account takes its type's color, so every chart agrees (Allianz and Profuturo are
    both "Retiro")."""
    tc = type_colors()
    return {n: tc.get(p.get("type"), colors()["neutral"]) for n, p in platforms(settings()).items()}


def platform_label(name):
    return "Bienes (auto y hogar)" if name == "Manual" else name


def category_colors(tx, kind="expense", by="category"):
    """Fixed color per category by all-time size (not the filtered view), so filtering never repaints.
    The top 7 get a color; the rest are "Otros"."""
    t = tx[tx["type"] == kind]
    ranked = t.groupby(by)["amount"].sum().sort_values(ascending=False).index.tolist()
    c = colors()
    mapping = {name: c["series"][i] for i, name in enumerate(ranked[:TOP_CATEGORIES])}
    mapping[OTHER] = c["neutral"]
    return mapping


def fold(df, col, mapping):
    df = df.copy()
    df[col] = df[col].where(df[col].isin(mapping), OTHER)
    return df


# --- Chart style -------------------------------------------------------------

def style(fig, height=340, x_title=None, y_title=None, money_axis=None, legend=True):
    """House style: hairline grid, axis titles, compact money ticks, room for labels, no toolbar.
    Text, grid and axis colors are left to Streamlit's chart theme (see draw()), which repaints them when the
    light/dark theme is switched. Setting them here froze them in the theme the page was loaded with."""
    axis = dict(showline=True, automargin=True, title_font=dict(size=12))
    fig.update_layout(
        height=height, margin=dict(l=8, r=16, t=12, b=8, autoexpand=True), autosize=True,
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family=FONT, size=13),
        showlegend=legend,
        # The chart title is drawn above the figure by draw(), so a wrapping legend has room here.
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0, title_text=""),
        hoverlabel=dict(font_family=FONT), bargroupgap=0.1, legend_traceorder="normal",
        separators=".,",
    )
    # Few bars would stretch into slabs: widen the gap a little, but keep them wide enough to read.
    n = max((len(t.x) if getattr(t, "orientation", None) != "h" else len(t.y))
            for t in fig.data if t.type == "bar") if any(t.type == "bar" for t in fig.data) else 0
    fig.update_layout(bargap=0.3 if n > 4 else 0.3 + 0.06 * (5 - max(n, 1)))
    fig.update_xaxes(**axis, title_text=x_title)
    fig.update_yaxes(**axis, title_text=y_title)
    if money_axis in ("x", "y"):
        # Horizontal money axes get fewer ticks so they never turn sideways on a narrow window.
        getattr(fig, f"update_{money_axis}axes")(tickprefix="$", tickformat="~s", tickangle=0,
                                                 nticks=4 if money_axis == "x" else 6)
    # Gap between stacked segments: a half-transparent gray reads as a divider on both themes.
    fig.update_traces(selector=dict(type="bar"), marker_line_width=1.5, marker_line_color=GAP)
    return fig


def shares(values, groups=None):
    """Each value as a share of its group's total (or of the whole list): for "xx.x%" in tooltips."""
    v = pd.Series(list(values), dtype=float)
    if groups is None:
        total = v.sum()
        return list(v / total) if total else [0.0] * len(v)
    g = pd.Series(list(groups))
    totals = v.groupby(g).transform("sum")
    return list((v / totals.where(totals != 0)).fillna(0.0))


def headroom(fig, axis, top, share=0.18):
    """Horizontal bars need more room (labels are wide): pass share=0.4 for those."""
    """Leave space past the biggest bar so outside labels never get cut off when the window narrows."""
    if top and top > 0:
        getattr(fig, f"update_{axis}axes")(range=[0, top * (1 + share)])
    return fig


def draw(fig, key=None, clickable=False):
    """Draw a chart. Its title goes above it as page text (wraps cleanly on narrow windows)."""
    title = fig.layout.title.text
    if title:
        st.markdown(f"**{title.replace('$', chr(92) + '$')}**")
        fig.update_layout(title_text=None)
    config = {"displayModeBar": False, "responsive": True}
    # theme="streamlit": the browser paints text and grid in the current theme and repaints on a switch.
    if not clickable:
        st.plotly_chart(fig, theme="streamlit", config=config, key=key)
        return
    st.plotly_chart(fig, theme="streamlit", config=config, key=key, on_select="rerun", selection_mode="points")


# --- Click-to-filter ---------------------------------------------------------
# Each clickable chart puts an identity in customdata (e.g. the category). A click is read back from
# session state at the top of the page, before anything is drawn, so every visual can use it.

def chart_key(page, chart):
    return f"{page}_{chart}_v{st.session_state.get(f'_clicks_version_{page}', 0)}"


def picked(page, chart, part=0):
    """Values clicked in a chart (customdata[part] of each selected point)."""
    ev = st.session_state.get(chart_key(page, chart))
    try:
        points = ev["selection"]["points"]
    except (KeyError, TypeError):
        return []
    out = []
    for p in points:
        cd = p.get("customdata")
        if cd is None:
            continue
        value = cd[part] if isinstance(cd, (list, tuple)) else cd
        if value not in out:
            out.append(value)
    return out


def clear_clicks(page):
    st.session_state[f"_clicks_version_{page}"] = st.session_state.get(f"_clicks_version_{page}", 0) + 1


def active_filters(page, labels):
    """Chips for what's been clicked, and a button to clear it. labels: {"Mes": [...], "Categoría": [...]}."""
    shown = {k: v for k, v in labels.items() if v}
    if not shown:
        st.caption("Haz clic en una barra para filtrar toda la vista.")
        return
    left, right = st.columns([5, 1], vertical_alignment="center")
    with left:
        st.markdown(" ".join(f":blue-badge[{k}: {', '.join(map(str, v))}]" for k, v in shown.items()))
    with right:
        st.button("Quitar filtros", key=f"clear_{page}", on_click=clear_clicks, args=(page,),
                  icon=":material/filter_alt_off:", width="stretch")


# --- Filters -----------------------------------------------------------------

def _saved(key, default, valid=None):
    """A filter's value from the last screen, or the default. Streamlit forgets widget values between
    screens, so each filter keeps a copy under "_<key>" and passes it back as the starting value."""
    saved = st.session_state.get("_" + key, default)
    return saved if valid is None or valid(saved) else default


def _keep(key, value):
    st.session_state["_" + key] = value
    return value


def month_start(d, months_back=0):
    """First day of d's month, or of the month `months_back` months earlier."""
    y, m = d.year, d.month - months_back
    while m < 1:
        y, m = y - 1, m + 12
    return date(y, m, 1)


# Quick periods, counted back from the latest date with data (the last monthly update), not from today:
# the dashboard is updated on the 1st, so "today's" month is usually still empty.
PRESETS = ["Último mes", "Mes anterior", "3 meses", "12 meses", "Este año", "Todo"]


def preset_range(name, first, last):
    """(start, end) for a quick period, kept inside the data's limits; None if it has no data."""
    if name == "Último mes":
        start, end = month_start(last), last
    elif name == "Mes anterior":
        end = month_start(last) - timedelta(days=1)
        start = month_start(end)
    elif name == "3 meses":
        start, end = month_start(last, 2), last
    elif name == "12 meses":
        start, end = month_start(last, 11), last
    elif name == "Este año":
        start, end = date(last.year, 1, 1), last
    else:
        start, end = first, last
    start, end = max(first, start), min(last, end)
    return (start, end) if start <= end else None


def _use_preset(key, widget):
    name = st.session_state.get(widget)
    rng = preset_range(name, *st.session_state[f"_{key}_limits"]) if name else None
    if rng:
        st.session_state["_" + key] = rng
        # A new calendar widget, so it opens on the new range (a drawn widget ignores a new starting value).
        st.session_state[f"_{key}_v"] = st.session_state.get(f"_{key}_v", 0) + 1


def date_range(first, last, default_months=12, key="dates"):
    """Calendar start/end picker, shared across screens. Returns (start, end) as dates.
    Quick periods: draw period_presets() anywhere on the same screen."""
    first, last = date.fromisoformat(str(first)[:10]), date.fromisoformat(str(last)[:10])
    st.session_state[f"_{key}_limits"] = (first, last)
    default = (max(first, month_start(last, default_months - 1)), last)
    saved = _saved(key, default, lambda v: len(v) == 2 and first <= v[0] <= v[1] <= last)
    value = st.date_input("Periodo", value=saved, min_value=first, max_value=last, format="DD/MM/YYYY",
                          key=f"w_{key}_v{st.session_state.get(f'_{key}_v', 0)}")
    if isinstance(value, (list, tuple)) and len(value) == 2:
        return tuple(_keep(key, tuple(value)))
    return saved  # the second date isn't picked yet


def period_presets(key="dates"):
    """One-click periods under the filters. The one matching the current range shows as selected."""
    first, last = st.session_state[f"_{key}_limits"]
    current = st.session_state.get("_" + key)
    match = next((p for p in PRESETS if preset_range(p, first, last) == current), None)
    # The key includes the range: when the calendar changes the range, the highlight follows.
    widget = f"w_{key}_preset_{current[0]}_{current[1]}" if current else f"w_{key}_preset"
    st.pills("Periodo rápido", PRESETS, default=match, key=widget, label_visibility="collapsed",
             on_change=_use_preset, args=(key, widget))


def period_picker(snaps, tx):
    """The shared 'Periodo' picker. Its limits come from all the data (transactions and snapshots), the same on
    every screen, so a period never cuts off one kind of data early."""
    snap_dates = snaps["as_of"].astype(str)
    return date_range(min(tx["date"].min(), snap_dates.min()), max(tx["date"].max(), snap_dates.max()))


def multi(label, options, key, placeholder):
    chosen = st.multiselect(label, options, key=f"w_{key}", placeholder=placeholder,
                            default=[x for x in _saved(key, []) if x in options])
    return _keep(key, chosen) or None


def snapshot_picker(dates, key="as_of"):
    dates = sorted(dates, reverse=True)
    saved = _saved(key, dates[0], lambda v: v in dates)
    return _keep(key, st.selectbox("Fecha de corte", dates, index=dates.index(saved), key=f"w_{key}",
                                   format_func=fmt.day))


# --- Cards and notes ---------------------------------------------------------

CARD_WIDTH = 210  # px; four fit beside the menu on a laptop; on narrower windows they wrap instead of squeezing


def card_row(align="distribute"):
    """A row of KPI cards that wraps onto more lines on a narrow window (use as a `with` block).
    align="left" for a short row under a full one, so it doesn't spread out."""
    return st.container(horizontal=True, gap="small", horizontal_alignment=align)


def card(label, value, help=None, delta=None, delta_color="normal", spark=None, note=None):
    """KPI card: compact value, exact figure on hover, optional trend line.
    `delta` is a change (colored, with arrow); `note` is plain context shown in the same spot, in gray."""
    if note is not None and delta is None:
        delta, delta_color, arrow = note, "off", "off"
    else:
        arrow = "auto"
    # Card text is Markdown: a pair of "$" would turn into a math formula. Escape them.
    label = label.replace("$", "\\$")
    delta = delta.replace("$", "\\$") if isinstance(delta, str) else delta
    st.metric(label, value, delta=delta, delta_color=delta_color, help=help, border=True, width=CARD_WIDTH,
              delta_arrow=arrow, chart_data=spark if spark is not None and len(spark) > 1 else None,
              chart_type="area")


def first_month_note():
    st.info("Es el primer mes registrado. Los cambios de mes a mes aparecen después de la próxima "
            "actualización mensual.", icon=":material/info:")
