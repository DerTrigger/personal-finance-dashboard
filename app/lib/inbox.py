"""
Monthly file handling: move files from the Drive inbox into the month folder, convert iPhone photos
into readable PNG copies, and delete screenshots once the month's readings are saved.

Month folders: FinanceData\\YYYY\\YYYY-MM\\ (the month being closed). Converted copies go in a
"converted" subfolder; originals are never changed. Only image files are ever deleted.
"""
import re
import shutil
from datetime import date
from pathlib import Path

from PIL import Image

from app.lib.config import PENDING_NAME
from app.lib.snapshots import read_csv, snapshot_dates

IMAGE_EXT = {".png", ".jpg", ".jpeg", ".heic", ".heif"}
SYSTEM_FILES = {"desktop.ini", "thumbs.db"}
CONVERTED = "converted"

try:
    import pillow_heif
    pillow_heif.register_heif_opener()  # lets Pillow open HEIC, whatever the file is named
except ImportError:  # pragma: no cover
    pillow_heif = None


def default_month(today=None):
    """The month being closed: the one before today's."""
    today = today or date.today()
    y, m = (today.year, today.month - 1) if today.month > 1 else (today.year - 1, 12)
    return f"{y}-{m:02d}"


def month_folder(data_dir, month):
    if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", month):
        raise ValueError(f"'{month}' is not a month in YYYY-MM format.")
    return Path(data_dir) / month[:4] / month


def _inbox_files(inbox):
    return sorted(p for p in Path(inbox).iterdir()
                  if p.is_file() and not p.name.startswith(".") and p.name.lower() not in SYSTEM_FILES)


def collect(inbox, dest, dry_run=False):
    """Move every file from the inbox to dest. Never overwrites: a name clash stays in the inbox.

    Returns (moved, conflicts) as lists of source paths.
    """
    inbox, dest = Path(inbox), Path(dest)
    if not inbox.is_dir():
        raise FileNotFoundError(f"Inbox not found: {inbox}. Is Google Drive for desktop running?")
    moved, conflicts = [], []
    for src in _inbox_files(inbox):
        if (dest / src.name).exists():
            conflicts.append(src)
            continue
        if not dry_run:
            dest.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dest / src.name))
        moved.append(src)
    return moved, conflicts


def _images(folder):
    return sorted(p for p in Path(folder).iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXT)


def convert_images(folder):
    """Save a PNG copy of every image in folder to folder\\converted\\. Skips copies that already exist.

    Returns (converted, failed): new PNG paths, and source images that couldn't be opened.
    """
    folder = Path(folder)
    out_dir = folder / CONVERTED
    done, failed = [], []
    for src in _images(folder):
        out = out_dir / f"{src.stem}.png"
        if out.exists():
            continue
        try:
            with Image.open(src) as img:
                out_dir.mkdir(exist_ok=True)
                img.convert("RGB").save(out, format="PNG")
        except Exception:
            failed.append(src)
            continue
        done.append(out)
    return done, failed


def plan_cleanup(folder, history):
    """Image files that can be deleted: only if the folder's pending snapshot is already saved."""
    folder = Path(folder)
    pending = folder / PENDING_NAME
    if not pending.exists():
        raise ValueError(f"No {PENDING_NAME} in {folder}; can't tell whether this month is saved.")
    dates = snapshot_dates(read_csv(pending))
    saved = set(snapshot_dates(history))
    missing = [d for d in dates if d not in saved]
    if not dates or missing:
        raise ValueError(f"Readings for {', '.join(missing) or folder.name} are not saved yet. Nothing deleted.")
    converted = folder / CONVERTED
    return _images(folder) + (_images(converted) if converted.is_dir() else [])


def cleanup(folder, history):
    """Delete the files plan_cleanup lists. Returns them."""
    files = plan_cleanup(folder, history)
    for f in files:
        f.unlink()
    converted = Path(folder) / CONVERTED
    if converted.is_dir() and not any(converted.iterdir()):
        converted.rmdir()
    return files
