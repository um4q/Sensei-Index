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
"""
import sqlite3
import sys
from pathlib import Path

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


def test_electrical_zone_and_row_round_trip():
    import access_electrical_data_access as eda
    conn = _build_sqlite_db()

    eda.add_zone(conn, "K1B Well Pad")
    assert eda.list_zones(conn) == ["K1B Well Pad"]

    row_id = eda.find_first_blank_row(conn, "K1B Well Pad", "transformer_test")
    eda.save_row(conn, "K1B Well Pad", "transformer_test", row_id, {
        "tag": "29152-PT-001", "make": "ABB", "location": "K1B",
    })
    full = eda.read_full_row(conn, "K1B Well Pad", "transformer_test", row_id)
    assert full["tag"] == "29152-PT-001"
    assert full["make"] == "ABB"

    index_rows = eda.read_index_rows(conn, "K1B Well Pad", "transformer_test")
    assert len(index_rows) == 1
    assert index_rows[0]["tag"] == "29152-PT-001"

    assert eda.count_rows(conn, "K1B Well Pad", "transformer_test") == 1


def test_electrical_duplicate_detection_scoped_to_zone():
    import access_electrical_data_access as eda
    conn = _build_sqlite_db()
    eda.add_zone(conn, "Zone A")
    eda.add_zone(conn, "Zone B")

    row1 = eda.find_first_blank_row(conn, "Zone A", "transformer_test")
    eda.save_row(conn, "Zone A", "transformer_test", row1, {"tag": "DUPE-1"})

    # Same tag in a DIFFERENT zone should NOT count as a duplicate -
    # same "duplicate check is scoped to one zone/series" rule the
    # Excel edition's own find_duplicate_row() already applies.
    row2 = eda.find_first_blank_row(conn, "Zone B", "transformer_test")
    eda.save_row(conn, "Zone B", "transformer_test", row2, {"tag": "DUPE-1"})
    assert eda.find_duplicate_row(conn, "Zone B", "transformer_test", "DUPE-1", exclude_row=row2) is None

    # Same tag, SAME zone, different row - IS a duplicate.
    row3 = eda.find_first_blank_row(conn, "Zone A", "transformer_test")
    eda.save_row(conn, "Zone A", "transformer_test", row3, {"tag": "DUPE-1"})
    dupe = eda.find_duplicate_row(conn, "Zone A", "transformer_test", "DUPE-1", exclude_row=row3)
    assert dupe is not None
    assert dupe["id"] == row1


def test_electrical_generate_preview_pdf_uses_real_export_module():
    """Proves the REUSE claim in access_electrical_data_access.py's own
    docstring - the Excel edition's real export_transformer_test_to_pdf.py
    (and its real template PDF) genuinely fills correctly from data that
    came out of this Access-shaped path, unmodified."""
    import access_electrical_data_access as eda
    from pypdf import PdfReader
    conn = _build_sqlite_db()
    eda.add_zone(conn, "K1B Well Pad")
    row_id = eda.find_first_blank_row(conn, "K1B Well Pad", "transformer_test")
    eda.save_row(conn, "K1B Well Pad", "transformer_test", row_id, {
        "tag": "29152-PT-001", "make": "ABB",
    })
    out_path = eda.generate_preview_pdf(conn, "K1B Well Pad", "transformer_test", row_id)
    assert out_path.exists()
    fields = PdfReader(str(out_path)).get_fields()
    assert fields["tag"].get("/V") == "29152-PT-001"
    assert fields["make"].get("/V") == "ABB"


def test_instrumentation_series_and_row_round_trip():
    import access_data_access as da
    conn = _build_sqlite_db()

    da.add_series(conn, 100, "Mod 100")
    assert da.list_series(conn) == [100]
    assert da.series_display_label(conn, 100) == "Mod 100"

    row_id = da.find_first_blank_row(conn, 100, "transmitter")
    da.save_row(conn, 100, "transmitter", row_id, {"tag": "29103-TIT-0001"})
    full = da.read_full_row(conn, 100, "transmitter", row_id)
    assert full["tag"] == "29103-TIT-0001"
    assert da.count_rows(conn, 100, "transmitter") == 1


def test_status_and_activity_log_through_domain_module():
    import access_electrical_data_access as eda
    conn = _build_sqlite_db()
    eda.add_zone(conn, "K1B Well Pad")
    row_id = eda.find_first_blank_row(conn, "K1B Well Pad", "transformer_test")
    eda.save_row(conn, "K1B Well Pad", "transformer_test", row_id, {"tag": "T-1"})

    status = eda.get_electrical_status(conn, "transformer_test", "T-1")
    assert status == {"installed": False, "submitted": False, "accepted": False}
    eda.set_electrical_status(conn, "transformer_test", "T-1", installed=True)
    assert eda.get_electrical_status(conn, "transformer_test", "T-1")["installed"] is True

    log = eda.read_electrical_activity_log(conn)
    actions = [entry["action"] for entry in log]
    assert "add_zone" in actions
    assert "save_row" in actions
