"""Load config/settings.toml and resolve data paths."""
import os
import re
import tomllib
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[2]
SETTINGS_FILE = PROJECT_DIR / "config" / "settings.toml"


def load_settings(path=SETTINGS_FILE):
    """settings.toml. FINANCE_DATA_DIR / FINANCE_INBOX_DIR, when set, point every tool at another data folder
    and inbox (a sandbox copy for a rehearsal), without touching the real ones."""
    with open(path, "rb") as f:
        s = tomllib.load(f)
    for env, key in (("FINANCE_DATA_DIR", "data_dir"), ("FINANCE_INBOX_DIR", "inbox_dir")):
        if os.environ.get(env):
            s["paths"][key] = os.environ[env]
    return s


def data_path(settings, key):
    """Full path to a file in the data folder, e.g. data_path(s, 'database')."""
    return Path(settings["paths"]["data_dir"]) / settings["paths"][key]


_EXPORT_RANGE = re.compile(r"^\d{4}-\d{2}-\d{2}\s*~\s*(?:\d{4}-)?\d{2}-\d{2}")


def _is_export(name):
    """Money Manager's names: "Money Manager Report 2026-09-01 ~ 09-30.xlsx", or since Oct 2026 just
    "2026-09-01 ~ 09-30.xlsx" (the phone export)."""
    return name.startswith("Money Manager Report") or bool(_EXPORT_RANGE.match(name))


def find_exports(data_dir):
    """Every Money Manager export under the data folder, except in scratch folders whose name starts with "_"
    (e.g. _replay, _dryrun: their files are simulations, not Memo's data)."""
    root = Path(data_dir)
    return sorted(p for p in root.rglob("*.xlsx")
                  if _is_export(p.name)
                  and not any(part.startswith("_") for part in p.relative_to(root).parts[:-1]))


PENDING_NAME = "pending-snapshot.csv"


# --- Investment accounts ([platforms."Name"] blocks) -------------------------

def platforms(settings):
    return settings.get("platforms", {})


def returns_method(settings, name):
    return platforms(settings).get(name, {}).get("returns", "estimated")


def mm_account(settings, name):
    return platforms(settings).get(name, {}).get("mm_account", "")


def platform_type(settings, name):
    return platforms(settings).get(name, {}).get("type", "")


def expected_platforms(settings, as_of):
    """Accounts that should have a screenshot on as_of: opened by then and not closed by then."""
    out = []
    for name, p in platforms(settings).items():
        if p.get("opened") and p["opened"] > as_of:
            continue
        if p.get("status") == "closed" and (not p.get("closed") or p["closed"] <= as_of):
            continue
        out.append(name)
    return out


def find_pending(data_dir):
    """The newest month's pending snapshot (FinanceData\\YYYY\\YYYY-MM\\pending-snapshot.csv), or None."""
    found = sorted(Path(data_dir).glob(f"*/*/{PENDING_NAME}"), key=lambda p: p.parent.name)
    return found[-1] if found else None
