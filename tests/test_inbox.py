"""Inbox, photo conversion, and screenshot cleanup. Everything happens in temporary folders."""
from datetime import date

import pytest
from PIL import Image

from app.lib import inbox as ib
from tests.snapdata import september


def touch(path, text="x"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


# --- Month folder ------------------------------------------------------------

def test_default_month_is_the_month_being_closed():
    assert ib.default_month(date(2026, 11, 1)) == "2026-10"
    assert ib.default_month(date(2027, 1, 1)) == "2026-12"


def test_month_folder(tmp_path):
    assert ib.month_folder(tmp_path, "2026-10") == tmp_path / "2026" / "2026-10"


def test_bad_month_is_refused(tmp_path):
    with pytest.raises(ValueError):
        ib.month_folder(tmp_path, "Oct 2026")


# --- Collect -----------------------------------------------------------------

def test_collect_moves_every_file(tmp_path):
    inbox, dest = tmp_path / "inbox", tmp_path / "data" / "2026" / "2026-10"
    touch(inbox / "IMG_1.png")
    touch(inbox / "Money Manager Report 2026-01-01 ~ 12-31.xlsx")
    moved, conflicts = ib.collect(inbox, dest)
    assert sorted(p.name for p in moved) == ["IMG_1.png", "Money Manager Report 2026-01-01 ~ 12-31.xlsx"]
    assert conflicts == []
    assert (dest / "IMG_1.png").exists()
    assert not (inbox / "IMG_1.png").exists()


def test_collect_dry_run_moves_nothing(tmp_path):
    inbox, dest = tmp_path / "inbox", tmp_path / "dest"
    touch(inbox / "IMG_1.png")
    moved, _ = ib.collect(inbox, dest, dry_run=True)
    assert [p.name for p in moved] == ["IMG_1.png"]
    assert (inbox / "IMG_1.png").exists()
    assert not dest.exists()


def test_collect_never_overwrites(tmp_path):
    inbox, dest = tmp_path / "inbox", tmp_path / "dest"
    touch(inbox / "IMG_1.png", "new")
    touch(dest / "IMG_1.png", "old")
    moved, conflicts = ib.collect(inbox, dest)
    assert moved == []
    assert [p.name for p in conflicts] == ["IMG_1.png"]
    assert (dest / "IMG_1.png").read_text() == "old"
    assert (inbox / "IMG_1.png").exists()


def test_collect_skips_system_files_and_folders(tmp_path):
    inbox, dest = tmp_path / "inbox", tmp_path / "dest"
    touch(inbox / "desktop.ini")
    touch(inbox / ".hidden")
    touch(inbox / "sub" / "IMG_2.png")
    moved, _ = ib.collect(inbox, dest)
    assert moved == []


def test_collect_from_missing_inbox_is_an_error(tmp_path):
    with pytest.raises(FileNotFoundError):
        ib.collect(tmp_path / "nope", tmp_path / "dest")


# --- Convert -----------------------------------------------------------------

def test_convert_heic_named_png(tmp_path):
    pillow_heif = pytest.importorskip("pillow_heif")
    src = tmp_path / "IMG_1.png"  # really HEIC, like the iPhone ones
    try:
        pillow_heif.from_pillow(Image.new("RGB", (40, 30), "red")).save(src, format="HEIF")
    except Exception as e:  # no HEIC encoder in this build
        pytest.skip(f"cannot write HEIC here: {e}")
    before = src.read_bytes()
    done, failed = ib.convert_images(tmp_path)
    out = tmp_path / "converted" / "IMG_1.png"
    assert done == [out]
    assert failed == []
    with Image.open(out) as img:
        assert img.format == "PNG"
        assert img.size == (40, 30)
    assert src.read_bytes() == before  # original untouched


def test_convert_real_png_and_jpg(tmp_path):
    Image.new("RGB", (10, 10)).save(tmp_path / "a.png")
    Image.new("RGB", (10, 10)).save(tmp_path / "b.JPG", format="JPEG")
    done, failed = ib.convert_images(tmp_path)
    assert sorted(p.name for p in done) == ["a.png", "b.png"]
    assert failed == []


def test_convert_skips_already_converted_and_non_images(tmp_path):
    Image.new("RGB", (10, 10)).save(tmp_path / "a.png")
    touch(tmp_path / "Money Manager Report.xlsx")
    ib.convert_images(tmp_path)
    done, failed = ib.convert_images(tmp_path)
    assert done == []
    assert failed == []


def test_convert_reports_unreadable_image(tmp_path):
    touch(tmp_path / "broken.png", "not an image")
    done, failed = ib.convert_images(tmp_path)
    assert done == []
    assert [p.name for p in failed] == ["broken.png"]


# --- Cleanup -----------------------------------------------------------------

def saved_month(tmp_path):
    """A month folder whose pending snapshot is already in the history."""
    folder = tmp_path / "2026" / "2026-09"
    folder.mkdir(parents=True)
    september().to_csv(folder / "pending-snapshot.csv", index=False)
    Image.new("RGB", (5, 5)).save(folder / "IMG_1.png")
    touch(folder / "IMG_2.HEIC")
    touch(folder / "converted" / "IMG_1.png")
    touch(folder / "Money Manager Report 2026-01-01 ~ 12-31.xlsx")
    return folder


def test_cleanup_lists_only_images(tmp_path):
    folder = saved_month(tmp_path)
    files = ib.plan_cleanup(folder, september())
    assert sorted(str(p.relative_to(folder)) for p in files) == sorted(
        ["IMG_1.png", "IMG_2.HEIC", str(folder.joinpath("converted", "IMG_1.png").relative_to(folder))])


def test_cleanup_deletes_images_and_keeps_the_rest(tmp_path):
    folder = saved_month(tmp_path)
    deleted = ib.cleanup(folder, september())
    assert len(deleted) == 3
    assert sorted(p.name for p in folder.iterdir() if p.is_file()) == [
        "Money Manager Report 2026-01-01 ~ 12-31.xlsx", "pending-snapshot.csv"]


def test_cleanup_refuses_when_month_not_saved(tmp_path):
    folder = saved_month(tmp_path)
    empty_history = september().iloc[0:0]
    with pytest.raises(ValueError, match="not saved"):
        ib.cleanup(folder, empty_history)
    assert (folder / "IMG_1.png").exists()


def test_cleanup_refuses_without_pending_snapshot(tmp_path):
    folder = saved_month(tmp_path)
    (folder / "pending-snapshot.csv").unlink()
    with pytest.raises(ValueError, match="pending"):
        ib.plan_cleanup(folder, september())
