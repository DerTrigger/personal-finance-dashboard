import os
import sys
from datetime import datetime

import pytest
from openpyxl import Workbook

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Same header as a real Money Manager export, including the repeated "Accounts" column.
MM_HEADER = ["Period", "Accounts", "Category", "Subcategory", "Note", "MXN",
             "Income/Expense", "Description", "Amount", "Currency", "Accounts"]


def mm_row(when, account, category, amount, kind, subcategory=None, note=None,
           description=None, currency="MXN"):
    """One export row. `when` is 'YYYY-MM-DD HH:MM'."""
    ts = datetime.strptime(when, "%Y-%m-%d %H:%M")
    return [ts, account, category, subcategory, note, amount, kind, description,
            amount, currency, amount]


@pytest.fixture
def make_export(tmp_path):
    """Write a fake Money Manager export and return its path."""
    def _make(name, rows, mtime=None):
        wb = Workbook()
        ws = wb.active
        ws.append(MM_HEADER)
        for r in rows:
            ws.append(r)
        path = tmp_path / name
        wb.save(path)
        if mtime is not None:
            os.utime(path, (mtime, mtime))
        return path
    return _make
