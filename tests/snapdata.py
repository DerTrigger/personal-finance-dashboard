"""Fake monthly snapshots for the validation and reconciliation tests. All numbers are made up."""
import pandas as pd

SNAP_COLS = ["as_of", "platform", "account_type", "item_type", "name", "ticker", "asset_type", "market",
             "units", "principal", "value", "gain", "gain_pct", "annual_rate", "term_days", "start_date",
             "end_date", "payout", "interest_total", "interest_basis", "confirmed_on", "notes"]

CAJITAS = ["Cajita Ahorro", "Fondo de Emergencia", "Inversión", "Retiro"]

def platform(type_, returns, mm_account="", status="open", opened="", closed=""):
    return {"type": type_, "returns": returns, "mm_account": mm_account, "status": status, "opened": opened,
            "closed": closed}


SETTINGS = {
    "tax": {"isr_rate": 0.009},
    "nu": {"cajitas": CAJITAS},
    "checks": {
        "sum_tolerance": 1.0,
        "gain_pct_tolerance": 0.0005,
        "interest_tolerance": 1.0,
        "jump_warn_pct": 0.20,
        "reconcile_gap_mxn": 500,
    },
    "platforms": {
        "Nu": platform("sofipo_on_demand", "gain_change"),
        "FINSUS": platform("sofipo_fixed", "interest", "FINSUS"),
        "Kubo Financiero": platform("sofipo_fixed", "interest"),
        "GBM": platform("variable", "gain_change", "GBM"),
        "Bitso": platform("variable", "estimated"),
        "Allianz PPR": platform("retirement", "statement", "Allianz PPR"),
        "Profuturo": platform("retirement", "estimated"),
        "Manual": platform("manual_asset", "revaluation"),
    },
}


def row(as_of, platform, account_type, item_type, name, value, **kw):
    r = {c: None for c in SNAP_COLS}
    r.update(as_of=as_of, platform=platform, account_type=account_type, item_type=item_type, name=name,
             value=value, **kw)
    return r


def holding(as_of, name, value, gain):
    return row(as_of, "GBM", "variable", "holding", name, value, asset_type="etf", gain=gain,
               gain_pct=round(gain / (value - gain), 4))


def september(as_of="2026-09-30"):
    """A complete, valid month. Every part adds up to its platform total."""
    rows = [
        row(as_of, "Nu", "sofipo_on_demand", "total", "Nu", 40000.0),
        row(as_of, "Nu", "sofipo_on_demand", "cajita", CAJITAS[0], 10000.0, gain=500.0, annual_rate=0.13),
        row(as_of, "Nu", "sofipo_on_demand", "cajita", CAJITAS[1], 30000.0, gain=900.0, annual_rate=0.065),
        row(as_of, "FINSUS", "sofipo_fixed", "total", "FINSUS", 108000.0),
        row(as_of, "FINSUS", "sofipo_fixed", "on_demand", "finsus +", 72000.0, annual_rate=0.05),
        # 30 days to 2026-10-15: gross 300.00, ISR 27.00, net 273.00
        row(as_of, "FINSUS", "sofipo_fixed", "deposit", "Casita", 36000.0, principal=36000.0, annual_rate=0.10,
            term_days=181, start_date="2026-09-15", end_date="2027-03-15", payout="monthly",
            interest_total=1810.0, interest_basis="gross"),
        row(as_of, "Kubo Financiero", "sofipo_fixed", "total", "Kubo Financiero", 20000.0),
        # 180 days: gross 1000.00, ISR 90.00, net 910.00
        row(as_of, "Kubo Financiero", "sofipo_fixed", "deposit", "Plazo", 20000.0, principal=20000.0,
            annual_rate=0.10, term_days=180, start_date="2026-04-20", end_date="2026-10-17",
            payout="at_maturity", interest_total=910.0, interest_basis="net"),
        row(as_of, "GBM", "variable", "total", "GBM", 10000.0),
        holding(as_of, "VOO", 6000.0, 1000.0),
        holding(as_of, "FUNO11", 4000.0, -200.0),
        row(as_of, "Bitso", "variable", "total", "Bitso", 5000.0),
        row(as_of, "Bitso", "variable", "holding", "BTC", 5000.0, asset_type="crypto"),
        row(as_of, "Allianz PPR", "retirement", "total", "Allianz PPR", 120000.0),
        row(as_of, "Allianz PPR", "retirement", "statement", "Monthly statement", 119000.0, principal=100000.0),
        row(as_of, "Profuturo", "retirement", "total", "Profuturo", 300000.0),
        row(as_of, "Profuturo", "retirement", "subaccount", "Ahorro para el retiro", 250000.0),
        row(as_of, "Profuturo", "retirement", "subaccount", "Ahorro para la vivienda (Infonavit)", 50000.0),
        row(as_of, "Manual", "manual_asset", "manual_asset", "Car", 200000.0),
    ]
    return pd.DataFrame(rows, columns=SNAP_COLS)


def october():
    """The month after september(), with known movements:
    Nu +300 gain; FINSUS +273 payout and +254.20 on-demand interest; Kubo deposit matured and was paid out
    (910 interest earned, 20,910 withdrawn); GBM +3,000 contributed and +500 gain; Bitso +400;
    Allianz statement shows +5,000 contributed, total +6,000; Profuturo +1,500; car -10,000."""
    d = "2026-10-31"
    rows = [
        row(d, "Nu", "sofipo_on_demand", "total", "Nu", 40300.0),
        row(d, "Nu", "sofipo_on_demand", "cajita", CAJITAS[0], 10100.0, gain=600.0, annual_rate=0.13),
        row(d, "Nu", "sofipo_on_demand", "cajita", CAJITAS[1], 30200.0, gain=1100.0, annual_rate=0.065),
        row(d, "FINSUS", "sofipo_fixed", "total", "FINSUS", 108527.20),
        row(d, "FINSUS", "sofipo_fixed", "on_demand", "finsus +", 72527.20, annual_rate=0.05),
        row(d, "FINSUS", "sofipo_fixed", "deposit", "Casita", 36000.0, principal=36000.0, annual_rate=0.10,
            term_days=181, start_date="2026-09-15", end_date="2027-03-15", payout="monthly",
            interest_total=1810.0, interest_basis="gross"),
        row(d, "Kubo Financiero", "sofipo_fixed", "total", "Kubo Financiero", 0.0),
        row(d, "GBM", "variable", "total", "GBM", 13500.0),
        holding(d, "VOO", 9300.0, 1400.0),
        holding(d, "FUNO11", 4200.0, -100.0),
        row(d, "Bitso", "variable", "total", "Bitso", 5400.0),
        row(d, "Bitso", "variable", "holding", "BTC", 5400.0, asset_type="crypto"),
        row(d, "Allianz PPR", "retirement", "total", "Allianz PPR", 126000.0),
        row(d, "Allianz PPR", "retirement", "statement", "Monthly statement", 125500.0, principal=105000.0),
        row(d, "Profuturo", "retirement", "total", "Profuturo", 301500.0),
        row(d, "Profuturo", "retirement", "subaccount", "Ahorro para el retiro", 251000.0),
        row(d, "Profuturo", "retirement", "subaccount", "Ahorro para la vivienda (Infonavit)", 50500.0),
        row(d, "Manual", "manual_asset", "manual_asset", "Car", 190000.0),
    ]
    return pd.DataFrame(rows, columns=SNAP_COLS)
