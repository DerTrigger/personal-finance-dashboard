"""Revisión de datos: what's loaded, anything flagged, and the untracked adjustments."""
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import streamlit as st  # noqa: E402

from app.lib import db, fmt, ui  # noqa: E402
from app.lib import metrics as mx  # noqa: E402
from app.lib import snapshots as sn  # noqa: E402

METHODS = {"gain_change": "Ganancia reportada", "interest": "Intereses calculados", "statement": "Estado de cuenta",
           "estimated": "Estimado", "revaluation": "Revaluación"}

snaps, tx, adj = ui.load()
s = ui.settings()
st.title("Revisión de datos")

built = datetime.fromtimestamp(ui.db_file().stat().st_mtime)
dates = sn.snapshot_dates(snaps)
with ui.card_row():
    # The database is rebuilt on every monthly run (full or export-only), so its build time is the last update.
    ui.card("Última actualización", f"{built:%d/%m/%y}", help=f"{built:%d/%m/%Y %H:%M}",
            note=f"A las {built:%H:%M}")
    ui.card("Cortes mensuales", str(len(dates)), note=f"Saldos al {fmt.day(dates[-1])}")
    ui.card("Movimientos", f"{len(tx):,}", note=f"{fmt.month(tx['month'].min())} a {fmt.month(tx['month'].max())}")
    ui.card("Ajustes registrados", str(len(adj)), note="Diferencias aprobadas")

check = mx.data_check(snaps, tx, s, adj)

st.subheader(f"Saldos de inversión · {fmt.day(check['latest'])}")
if not check["errors"] and not check["warnings"]:
    st.success("Todo cuadra: están todas las cuentas, las partes suman el total y las ganancias e intereses "
               "coinciden.", icon=":material/check_circle:")
for e in check["errors"]:
    st.error(e, icon=":material/error:")
for w in check["warnings"]:
    st.warning(w, icon=":material/warning:")

st.subheader("Cambios de saldo vs. Money Manager")
recon = check["reconcile"]
if recon is None:
    ui.first_month_note()
else:
    flagged = recon[recon["flagged"]]
    if flagged.empty:
        st.success("El cambio de cada cuenta se explica por sus rendimientos y las transferencias registradas.",
                   icon=":material/check_circle:")
    for r in flagged.itertuples():
        st.warning(f"{r.platform}: el dinero aportado parece ser {fmt.money(r.contributions)}, pero Money Manager "
                   f"registró {fmt.money(r.logged_transfers)} (diferencia {fmt.signed(r.gap)}). Registra la "
                   f"transferencia que falta o aprueba anotarla como ajuste.", icon=":material/warning:")
    view = recon.assign(status=["Revisar" if f else ("Estimado" if e else "OK")
                                for f, e in zip(recon["flagged"], recon["estimated"])],
                        method=recon["method"].map(METHODS))
    view = fmt.whole(view, ["change", "returns", "contributions", "logged_transfers", "gap"])
    st.dataframe(view[["platform", "status", "method", "change", "returns", "contributions", "logged_transfers",
                       "gap"]], hide_index=True, column_config={
        "platform": "Cuenta", "status": "Estado", "method": "Rendimiento según",
        "change": st.column_config.NumberColumn("Cambio ($)", format=fmt.TABLE_SIGNED),
        "returns": st.column_config.NumberColumn("Rendimiento ($)", format=fmt.TABLE_SIGNED),
        "contributions": st.column_config.NumberColumn("Aportado ($)", format=fmt.TABLE_SIGNED),
        "logged_transfers": st.column_config.NumberColumn("Registrado ($)", format=fmt.TABLE_SIGNED),
        "gap": st.column_config.NumberColumn("Diferencia ($)", format=fmt.TABLE_SIGNED)})
    st.caption(f"{fmt.day(recon['start'].iloc[0])} a {fmt.day(recon['end'].iloc[0])}. Se marcan diferencias "
               f"mayores a {fmt.money(s['checks']['reconcile_gap_mxn'])}. Solo las cuentas con cuenta en Money "
               "Manager se pueden comparar.")

st.subheader("Ajustes no registrados")
if adj.empty:
    st.write("Ninguno.")
else:
    st.dataframe(fmt.whole(adj, ["amount"]), hide_index=True, column_config={
        "date": "Fecha", "account": "Cuenta", "reason": "Motivo", "approved_on": "Aprobado",
        "amount": st.column_config.NumberColumn("Monto ($)", format=fmt.TABLE_SIGNED)})

st.subheader("Money Manager")
dups, unmatched = check["duplicates"], check["unmatched"]
files = db.read_optional(ui.db_file(), "import_files", db.IMPORT_FILE_COLS)
gone = db.read_optional(ui.db_file(), "import_vanished", ["date", "account", "category", "note", "amount"])
notes = db.read_optional(ui.db_file(), "import_warnings", ["message"])
for msg in notes["message"]:  # holes between exports, an old file saved again
    st.warning(msg, icon=":material/warning:")
if dups.empty and unmatched.empty and gone.empty and notes.empty:
    st.success("Sin posibles duplicados, cada transferencia tiene sus dos partes y no desapareció ningún movimiento "
               "entre exportaciones.", icon=":material/check_circle:")
if not files.empty:
    st.markdown("**Archivos usados**")
    st.dataframe(files.assign(start=files["start"].map(lambda d: fmt.day(d) if d else fmt.EMPTY),
                              end=files["end"].map(lambda d: fmt.day(d) if d else fmt.EMPTY),
                              from_name=files["from_name"].astype(int).map({1: "Nombre del archivo",
                                                                            0: "Sus movimientos"})),
                 hide_index=True, column_config={
                     "name": "Archivo", "start": "Desde", "end": "Hasta", "from_name": "Fechas según",
                     "rows_in_file": st.column_config.NumberColumn("Movimientos", format="%d"),
                     "rows_used": st.column_config.NumberColumn("Usados", format="%d")})
    st.caption("Cada archivo cuenta para sus fechas. Si dos cubren las mismas fechas, gana el más reciente, así que "
               "un movimiento editado (por ejemplo, al quitar IN NU) no se cuenta dos veces.")
if not gone.empty:
    st.warning(f"{len(gone)} movimientos estaban en una exportación anterior y ya no aparecen en la más reciente. "
               "Si los borraste o cambiaste en Money Manager, está bien; si no, revisa la exportación.",
               icon=":material/warning:")
    st.dataframe(fmt.whole(gone, ["amount"])[["date", "account", "category", "note", "amount"]], hide_index=True,
                 column_config={"date": "Fecha", "account": "Cuenta", "category": "Categoría", "note": "Nota",
                                "amount": st.column_config.NumberColumn("Monto", format=fmt.TABLE_MONEY)})
if not dups.empty:
    st.warning(f"{len(dups)} movimientos tienen la misma fecha, monto, cuenta y categoría que otro. Revisa si de "
               "verdad se repitieron (no se borra nada solo).", icon=":material/warning:")
    st.dataframe(fmt.whole(dups, ["amount"])[["date", "account", "category", "note", "amount"]], hide_index=True,
                 column_config={"date": "Fecha", "account": "Cuenta", "category": "Categoría", "note": "Nota",
                                "amount": st.column_config.NumberColumn("Monto", format=fmt.TABLE_MONEY)})
if not unmatched.empty:
    st.warning(f"A {len(unmatched)} transferencias les falta su otra mitad.", icon=":material/warning:")
    st.dataframe(fmt.whole(unmatched, ["amount"])[["date", "account", "counterpart", "amount"]], hide_index=True,
                 column_config={"date": "Fecha", "account": "Cuenta", "counterpart": "Contraparte",
                                "amount": st.column_config.NumberColumn("Monto", format=fmt.TABLE_MONEY)})
