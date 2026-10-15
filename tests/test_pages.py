"""Every dashboard screen opens against a fake database, with no errors and the right headline numbers.
Fake data: snapshots 2026-09-30 and 2026-10-31 (tests/snapdata.py), Money Manager rows from tests/test_metrics.py."""
from datetime import date
from pathlib import Path

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from app.lib import db
from tests.snapdata import SETTINGS, october, september
from tests.test_metrics import MM_ROWS

APP = Path(__file__).resolve().parents[1] / "app"


@pytest.fixture
def fake_db(tmp_path, make_export, monkeypatch):
    snaps_csv = tmp_path / "snaps.csv"
    pd.concat([september(), october()]).to_csv(snaps_csv, index=False, encoding="utf-8-sig")
    path = tmp_path / "finance.db"
    db.build_database(path, [make_export("mm.xlsx", MM_ROWS)], snaps_csv, tmp_path / "adj.csv", SETTINGS)
    monkeypatch.setenv("FINANCE_DB", str(path))
    return path


def open_page(name):
    at = AppTest.from_file(str(APP / "views" / name), default_timeout=30).run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def card(at, label):
    """(value, exact figure on hover, note/delta) of the first card with this label."""
    m = next(m for m in at.metric if m.label == label)
    return m.value, m.help, m.delta


def test_entry_point_opens_resumen(fake_db):
    at = AppTest.from_file(str(APP / "dashboard.py"), default_timeout=30).run()
    assert not at.exception
    assert at.title[0].value == "Evolución y estado actual del patrimonio"


def test_menu_order():
    source = (APP / "dashboard.py").read_text(encoding="utf-8")
    titles = ["Resumen", "Ingresos", "Gastos", "Inversiones", "Revisión de datos"]
    assert sorted(titles, key=source.index) == titles


def test_resumen(fake_db):
    at = open_page("resumen.py")
    value, exact, delta = card(at, "Patrimonio")
    assert value == "$785.2k"
    assert exact == "$785,227.20 al 31 oct 2026"
    assert delta == "-\\$17.8k vs. 30 sep 2026"  # "$" escaped so the card doesn't read it as a formula
    assert not at.info  # two snapshots: the "what explains the change" chart shows, not the first-month note


def test_gastos_cards_follow_the_filters(fake_db):
    at = open_page("gastos.py")
    assert card(at, "Total")[:2] == ("$3.2k", "$3,200.00")  # 1,000 + 500 + 1,500 + 200
    assert card(at, "Gasto de oct 2026")[0] == "$1.7k"
    assert card(at, "Categoría principal")[0] == "Food"
    at.multiselect[1].select("Food").run()
    assert card(at, "Total")[1] == "$2,700.00"
    at.multiselect[0].select("Nubank").run()
    assert card(at, "Total")[1] == "$200.00"


def test_gastos_calendar_period(fake_db):
    at = open_page("gastos.py")
    at.date_input[0].set_value((date(2026, 10, 1), date(2026, 10, 31))).run()
    assert not at.exception
    assert card(at, "Total")[1] == "$1,700.00"


def test_gastos_same_month_last_year(fake_db):
    at = open_page("gastos.py")
    at.button_group(key="w_mode_exp").set_value("Mismo mes del año anterior").run()
    assert not at.exception
    assert any("oct 2026 vs. oct 2025" in h.value for h in at.subheader)


def test_quick_period_sets_the_calendar(fake_db):
    """The data runs to 31 oct 2026 (last snapshot), so "Último mes" is October; "Todo" brings September back."""
    def presets():  # its key changes with the range, so find it by its options
        return next(b for b in at.button_group if "Último mes" in b.options)

    at = open_page("gastos.py")
    presets().set_value("Último mes").run()
    assert not at.exception
    assert at.date_input[0].value == (date(2026, 10, 1), date(2026, 10, 31))
    assert card(at, "Total")[1] == "$1,700.00"
    assert presets().value == "Último mes"  # the matching quick period shows as selected
    presets().set_value("Todo").run()
    assert card(at, "Total")[1] == "$3,200.00"


def test_resumen_click_a_month_in_income(fake_db):
    at = AppTest.from_file(str(APP / "views" / "resumen.py"), default_timeout=30)
    at.session_state["resumen_income_v0"] = {"selection": {"points": [{"customdata": ["2026-09", "Salary", 1.0]}]}}
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert card(at, "Ingreso neto")[1] == "$8,500.00 en sep 2026"  # 10,000 - 1,000 - 500
    assert card(at, "Tarjetas por pagar")[:3:2] == ("$0", "Nada pendiente")


def test_gastos_click_a_category(fake_db):
    at = AppTest.from_file(str(APP / "views" / "gastos.py"), default_timeout=30)
    at.session_state["gastos_by_category_v0"] = {"selection": {"points": [{"customdata": "Transport"}]}}
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert card(at, "Total")[1] == "$500.00"


def test_ingresos(fake_db):
    at = open_page("ingresos.py")
    assert card(at, "Total")[1] == "$20,100.00"
    assert card(at, "Ingreso neto")[1] == "$16,900.00"  # 20,100 - 3,200


def test_inversiones(fake_db):
    at = open_page("inversiones.py")
    assert card(at, "Total invertido")[:2] == ("$595.2k", "$595,227.20 al 31 oct 2026")  # without the car
    assert card(at, "Rendimiento del último mes")[0] == "+$5.1k"  # 3,237.20 reported + 1,900 estimated
    assert card(at, "Intereses por cobrar")[1].startswith("$1,647.10")
    assert card(at, "GBM")[0] == "$13.5k"
    assert card(at, "Aportado")[0] == "$105.0k"
    assert card(at, "Vivienda (Infonavit)")[0] == "$50.5k"


def test_inversiones_earlier_cutoff_date(fake_db):
    at = open_page("inversiones.py")
    at.selectbox[0].select("2026-09-30").run()
    assert card(at, "Total invertido")[1] == "$603,000.00 al 30 sep 2026"
    assert card(at, "Valor actual")[0] == "$120.0k"


def test_revision_flags_the_planted_gaps(fake_db):
    at = open_page("revision.py")
    warnings = " ".join(w.value for w in at.warning)
    assert "Plazo" in warnings                        # matured Kubo deposit no longer listed
    assert "GBM: el dinero aportado" in warnings      # October transfers not logged in the fake export
    assert "Allianz PPR: el dinero aportado" in warnings
    assert card(at, "Cortes mensuales")[0] == "2"
