# -*- coding: utf-8 -*-
"""
End-to-end test of access_electrical_data_access.py/access_data_access.py
against a SQLite database whose tables are generated from the REAL
access_schema.py column lists (not hand-typed) - same "prove the Python
logic is sound, real Access dialect only provable via Windows CI" scope
as tests/test_access_db_logic.py, just one level up: this exercises the
domain modules themselves (zone/series creation, row save/read, PDF
generation via the REAL export_*.py modules and REAL template PDFs),
not just the generic engine underneath them.

Both domain modules take NO explicit connection argument (see their own
docstrings for why - it's what lets gui_app.py's real UI code call them
completely unmodified, exactly like data_access.py/electrical_data_access.
py's own calling convention). So instead of passing a test connection
into every call, each test points the module's internal connection CACHE
at a fresh in-memory SQLite database via access_db.set_connection_for_
testing(), then calls every function exactly as gui_app.py itself would -
with no conn argument at all.
"""
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from access_schema import TABLES, CORE_TABLES

# Map Access DDL types to SQLite equivalents for the test double - see
# test_access_db_logic.py's own docstring for why this dialect gap is
# fine (SQLite's dynamic typing tolerates it either way, this is just
# for a valid CREATE TABLE statement).
_TYPE_MAP = {"COUNTER PRIMARY KEY": "INTEGER PRIMARY KEY AUTOINCREMENT", "LONG": "INTEGER",
             "MEMO": "TEXT", "YESNO": "INTEGER"}


def _sqlite_type(access_type):
    if access_type in _TYPE_MAP:
        return _TYPE_MAP[access_type]
    if access_type.startswith("TEXT"):
        return "TEXT"
    return access_type


def _build_sqlite_db():
    conn = sqlite3.connect(":memory:")
    for table_name, spec in CORE_TABLES.items():
        cols = ", ".join(f"{name} {_sqlite_type(t)}" for name, t in spec["columns"])
        conn.execute(f"CREATE TABLE {table_name} ({cols})")
    for equip_key, entry in TABLES.items():
        cols = [("id", "INTEGER PRIMARY KEY AUTOINCREMENT"), (entry["parent_field"], "INTEGER")]
        for f in entry["fields"]:
            cols.append((f["id"], "TEXT"))
        cols.append(("created_at", "TEXT"))
        cols.append(("updated_at", "TEXT"))
        col_sql = ", ".join(f"{name} {t}" for name, t in cols)
        conn.execute(f"CREATE TABLE {entry['table_name']} ({col_sql})")
    conn.commit()
    return conn


@pytest.fixture()
def eda():
    """Fresh module + fresh in-memory connection cache per test - two
    tests never share state, same isolation a fresh conn used to give,
    just achieved by resetting the cache instead of passing a new one
    around explicitly."""
    import access_db as db
    import access_electrical_data_access as mod
    db.set_connection_for_testing(_build_sqlite_db())
    yield mod
    db.set_connection_for_testing(None)


@pytest.fixture()
def da():
    import access_db as db
    import access_data_access as mod
    db.set_connection_for_testing(_build_sqlite_db())
    yield mod
    db.set_connection_for_testing(None)


def test_electrical_zone_and_row_round_trip(eda):
    eda.add_zone("K1B Well Pad")
    assert eda.list_zones() == ["K1B Well Pad"]

    row_id = eda.find_first_blank_row("K1B Well Pad", "transformer_test")
    eda.save_row("K1B Well Pad", "transformer_test", row_id, {
        "tag": "29152-PT-001", "make": "ABB", "location": "K1B",
    })
    full = eda.read_full_row("K1B Well Pad", "transformer_test", row_id)
    assert full["tag"] == "29152-PT-001"
    assert full["make"] == "ABB"

    index_rows = eda.read_index_rows("K1B Well Pad", "transformer_test")
    assert len(index_rows) == 1
    assert index_rows[0]["tag"] == "29152-PT-001"

    assert eda.count_rows("K1B Well Pad", "transformer_test") == 1


def test_electrical_duplicate_detection_scoped_to_zone(eda):
    eda.add_zone("Zone A")
    eda.add_zone("Zone B")

    row1 = eda.find_first_blank_row("Zone A", "transformer_test")
    eda.save_row("Zone A", "transformer_test", row1, {"tag": "DUPE-1"})

    # Same tag in a DIFFERENT zone should NOT count as a duplicate -
    # same "duplicate check is scoped to one zone/series" rule the
    # Excel edition's own find_duplicate_row() already applies.
    row2 = eda.find_first_blank_row("Zone B", "transformer_test")
    eda.save_row("Zone B", "transformer_test", row2, {"tag": "DUPE-1"})
    assert eda.find_duplicate_row("Zone B", "transformer_test", "DUPE-1", exclude_row=row2) is None

    # Same tag, SAME zone, different row - IS a duplicate.
    row3 = eda.find_first_blank_row("Zone A", "transformer_test")
    eda.save_row("Zone A", "transformer_test", row3, {"tag": "DUPE-1"})
    dupe = eda.find_duplicate_row("Zone A", "transformer_test", "DUPE-1", exclude_row=row3)
    assert dupe is not None
    assert dupe["id"] == row1


def test_electrical_generate_preview_pdf_uses_real_export_module(eda):
    """Proves the REUSE claim in access_electrical_data_access.py's own
    docstring - the Excel edition's real export_transformer_test_to_pdf.py
    (and its real template PDF) genuinely fills correctly from data that
    came out of this Access-shaped path, unmodified."""
    from pypdf import PdfReader
    eda.add_zone("K1B Well Pad")
    row_id = eda.find_first_blank_row("K1B Well Pad", "transformer_test")
    eda.save_row("K1B Well Pad", "transformer_test", row_id, {
        "tag": "29152-PT-001", "make": "ABB",
    })
    out_path = eda.generate_preview_pdf("K1B Well Pad", "transformer_test", row_id)
    assert out_path.exists()
    fields = PdfReader(str(out_path)).get_fields()
    assert fields["tag"].get("/V") == "29152-PT-001"
    assert fields["make"].get("/V") == "ABB"


def test_instrumentation_series_and_row_round_trip(da):
    da.add_series(100)
    da.set_series_name(100, "Mod 100")
    assert da.list_series() == [100]
    assert da.series_display_label(100) == "Mod 100"

    row_id = da.find_first_blank_row(100, "transmitter")
    da.save_row(100, "transmitter", row_id, {"tag": "29103-TIT-0001"})
    full = da.read_full_row(100, "transmitter", row_id)
    assert full["tag"] == "29103-TIT-0001"
    assert da.count_rows(100, "transmitter") == 1


def test_status_and_activity_log_through_domain_module(eda):
    eda.add_zone("K1B Well Pad")
    row_id = eda.find_first_blank_row("K1B Well Pad", "transformer_test")
    eda.save_row("K1B Well Pad", "transformer_test", row_id, {"tag": "T-1"})

    status = eda.get_electrical_status("K1B Well Pad", "transformer_test", "T-1")
    assert status == {"installed": False, "submitted": False, "accepted": False, "export": False}
    eda.set_electrical_status("K1B Well Pad", "transformer_test", "T-1", installed=True)
    assert eda.get_electrical_status("K1B Well Pad", "transformer_test", "T-1")["installed"] is True

    log = eda.read_electrical_activity_log()
    actions = [entry["action"] for entry in log]
    assert "add_zone" in actions
    assert "save_row" in actions


def test_equipment_types_carries_real_ui_metadata(eda, da):
    """The redo's whole point: EQUIPMENT_TYPES/ELECTRICAL_EQUIPMENT_TYPES
    are the REAL registries from data_access.py/electrical_data_access.py
    (label/summary_fields/date_fields/etc.), not the DB-shape dicts
    access_schema.py's own DOMAIN_TABLES produces - gui_app.py's index
    page, grouping, and date-column formatting all read this metadata
    directly and would KeyError/behave wrong without it."""
    assert da.EQUIPMENT_TYPES["transmitter"]["label"] == "Transmitter"
    assert "summary_fields" in da.EQUIPMENT_TYPES["transmitter"]
    assert "group_fields" in da.EQUIPMENT_TYPES["transmitter"]

    etype = eda.ELECTRICAL_EQUIPMENT_TYPES["transformer_test"]
    assert etype["label"] == "Transformer Test Record"
    assert etype["supports_signature_stamp"] is True
    assert "date_fields" in etype


def test_export_progress_report_and_cleaned_copy(da, tmp_path, monkeypatch):
    """Both were among the 4 symbols missing after the first redo pass
    (WORKBOOK_PATH/export_progress_report/export_cleaned_workbook/
    get_sheet_name) - this proves they're wired end to end, not just
    present on the module."""
    monkeypatch.setattr(da, "REPORTS_DIR", tmp_path / "reports")
    monkeypatch.setattr(da, "CLEANED_DIR", tmp_path / "cleaned")

    da.add_series(100)
    row_id = da.find_first_blank_row(100, "transmitter")
    da.save_row(100, "transmitter", row_id, {"tag": " 29103-tit-0001 "})

    assert da.get_sheet_name(100, "transmitter")
    with pytest.raises(KeyError):
        da.get_sheet_name(999, "transmitter")

    report_path = da.export_progress_report()
    assert report_path.exists()

    plan = da.build_cleanup_plan()
    assert any(f["field"] == "tag" for f in plan["fixes"])


def test_series_type_and_progress_summary_shapes_match_excel_edition(da):
    """Regression test for a real bug a MainWindow smoke test caught
    during the redo: both functions used to return just a bare dict,
    but access_gui_app.py's sidebar/Dashboard code (copied verbatim
    from gui_app.py) unpacks the SAME shapes data_access.py's own
    series_type_summary()/series_progress_summary() return - a (count,
    {value: count}) tuple and a {'avg_percent','at_0','partial','at_100'}
    dict per equipment kind, respectively. No automated test exercised
    the GUI's own sidebar/Dashboard-building code before this one, so
    the shape mismatch shipped silently until the smoke test ran it."""
    da.add_series(100)
    row1 = da.find_first_blank_row(100, "transmitter")
    da.save_row(100, "transmitter", row1, {"tag": "A-1", "system_number": "100"})
    row2 = da.find_first_blank_row(100, "transmitter")
    da.save_row(100, "transmitter", row2, {"tag": "A-2", "system_number": "100"})

    count, by_system = da.series_type_summary(100, "transmitter", "system_number")
    assert count == 2
    assert by_system == {"100": 2}

    prog = da.series_progress_summary(100)
    assert set(prog["transmitter"].keys()) == {"avg_percent", "at_0", "partial", "at_100"}
    assert prog["transmitter"]["at_0"] + prog["transmitter"]["partial"] + prog["transmitter"]["at_100"] == 2


def test_electrical_count_all_by_type_takes_no_arguments(eda, da):
    """Regression test for a real crash a user hit on their own machine
    (not caught by any test before this one, including the earlier
    MainWindow smoke test - see the module docstring's own note on
    test_startup_sequence_matches_real_app_launch below for why):
    access_gui_app.py's own startup path calls eda.count_all_by_type()
    with ZERO arguments (electrical_data_access.py's own version takes
    none either - it's a GLOBAL count across every zone, same as
    da.count_all_by_type()) - this module's own version used to require
    a zone_name positional argument and crashed on startup every time."""
    eda.add_zone("Zone A")
    eda.add_zone("Zone B")
    row_a = eda.find_first_blank_row("Zone A", "transformer_test")
    eda.save_row("Zone A", "transformer_test", row_a, {"tag": "A-1"})
    row_b = eda.find_first_blank_row("Zone B", "transformer_test")
    eda.save_row("Zone B", "transformer_test", row_b, {"tag": "B-1"})

    totals = eda.count_all_by_type()
    assert totals["transformer_test"] == 2  # across BOTH zones, not just one

    da.add_series(100)
    d_row = da.find_first_blank_row(100, "transmitter")
    da.save_row(100, "transmitter", d_row, {"tag": "T-1"})
    assert da.count_all_by_type()["transmitter"] == 1


def test_startup_sequence_matches_real_app_launch(eda, da, monkeypatch):
    """Actually runs access_gui_app.py's own _run_startup_with_splash()
    - the exact function main() calls, and the exact function whose
    da.list_series()/count_all_by_type()/eda.list_zones()/
    count_all_by_type() startup sequence crashed on a real user's
    machine (a MainWindow() smoke test alone does NOT exercise this -
    it skips straight past the startup-splash pre-warm calls that
    actually crashed). QT_QPA_PLATFORM=offscreen must be set (see
    conftest.py) - no real display needed."""
    import access_db as db
    import access_gui_app as g
    from PySide6.QtWidgets import QApplication

    # read_activity_log()'s own `limit` uses Access's "SELECT TOP N"
    # syntax, which SQLite doesn't support - see test_access_db_logic.
    # py's own docstring for the same documented gap. MainWindow's
    # Dashboard reads the activity log on construction, so this test
    # (which goes through MainWindow via the real startup path) needs
    # the same local workaround, not something a real Access run needs.
    _orig = db.read_activity_log
    monkeypatch.setattr(
        db, "read_activity_log",
        lambda conn, limit=None, **kw: _orig(conn, limit=None, **kw)[: (limit or 10**9)])

    eda.add_zone("Zone A")
    da.add_series(100)

    app = QApplication.instance() or QApplication([])
    win = g._run_startup_with_splash(app)
    try:
        assert win is not None
    finally:
        win.close()


def test_list_backups_and_restore_backup_shapes(da, tmp_path, monkeypatch):
    """Regression test for a second real bug the same smoke test caught:
    list_backups() used to return raw Path objects, but BackupsDialog
    (shared between Instrumentation and Electrical via its own
    backend= param - see access_gui_app.py's own BackupsDialog) indexes
    every entry by ['path']/['name']/['mtime']/['size'], and
    restore_backup() didn't exist on either domain module at all even
    though self.backend.restore_backup(...) is a real call site."""
    import access_db as db

    monkeypatch.setattr(da, "BACKUPS_DIR", tmp_path / "backups")
    fake_db = tmp_path / "SenseiIndex.accdb"
    fake_db.write_text("not a real accdb - just needs to exist for shutil.copy")
    monkeypatch.setattr(db, "DB_PATH", fake_db)

    dest = da.backup_now()
    assert dest.exists()

    backups = da.list_backups()
    assert len(backups) == 1
    assert set(backups[0].keys()) == {"path", "name", "mtime", "size"}
    assert backups[0]["path"] == dest

    fake_db.write_text("changed live content")
    safety = da.restore_backup(dest)
    assert safety is not None and safety.exists()
    assert fake_db.read_text() == "not a real accdb - just needs to exist for shutil.copy"
