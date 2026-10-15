"""
Finance dashboard entry point. Run: streamlit run app/dashboard.py (or "Start Finance Dashboard.bat").
Local only: see .streamlit/config.toml.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import streamlit as st  # noqa: E402

st.set_page_config(page_title="Finanzas", page_icon=":material/account_balance:", layout="wide")

# Screens live in app/views/ (not "pages/", which Streamlit would also list on its own).
pages = [
    st.Page("views/resumen.py", title="Resumen", icon=":material/home:", default=True),
    st.Page("views/ingresos.py", title="Ingresos", icon=":material/payments:"),
    st.Page("views/gastos.py", title="Gastos", icon=":material/shopping_cart:"),
    st.Page("views/inversiones.py", title="Inversiones", icon=":material/savings:"),
    st.Page("views/revision.py", title="Revisión de datos", icon=":material/fact_check:"),
]
st.navigation(pages).run()
