# -*- coding: utf-8 -*-
"""
Tests migrate_from_excel.py against the REAL, checked-in Equipment_
Inspection_Tracker.xlsx (same "prove it against the real file, not a
synthetic stand-in" precedent this project already set for the
Instrumentation Master List reader) - real reads on the Excel side
(read-only, never modifies that file), a SQLite-backed connection on
the Access side (same "SQLite proves the Python logic, real Access
dialect only provable via Windows CI" split as every other test here).

Doesn't hardcode exact row counts (the real workbook's own content can
legitimately change over time) - instead checks that whatever's really
in Equipment_Inspection_Tracker.xlsx right now round-trips into the
Access-shaped connection exactly: same series (with the same display
names), same per-series/per-kind row counts, and every field value +
status on a real row surviving the trip unchanged.
"""
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from access_schema import TABLES, CORE_TABLES

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
def migrated():
    """Runs the real migration (against the real checked-in tracker
    file) into a fresh SQLite-backed connection, and hands back the
    (mig, da, eda, excel_da, excel_eda) modules used to inspect the
    result - one full migration per test, same isolation the other
    fixtures in this folder already give."""
    import access_db as db
    import migrate_from_excel as mig
    db.set_connection_for_testing(_build_sqlite_db())
    mig.migrate_instrumentation(dry_run=False)
    mig.migrate_electrical(dry_run=False)
    import access_data_access as da
    import access_electrical_data_access as eda
    import data_access as excel_da
    import electrical_data_access as excel_eda
    yield mig, da, eda, excel_da, excel_eda
    db.set_connection_for_testing(None)


def test_every_series_and_row_count_matches_the_real_workbook(migrated):
    _mig, da, _eda, excel_da, _excel_eda = migrated
    assert da.list_series() == excel_da.list_series()
    assert da.list_series(), "the real Equipment_Inspection_Tracker.xlsx has no series - nothing was tested"
    for series_number in da.list_series():
        assert da.series_display_label(series_number) == (excel_da.get_series_name(series_number) or str(series_number))
        for equip_key in da.EQUIPMENT_TYPES:
            src_count = len(excel_da.read_index_rows(series_number, equip_key))
            dst_count = len(da.read_index_rows(series_number, equip_key))
            assert src_count == dst_count, (series_number, equip_key, src_count, dst_count)


def test_a_real_rows_fields_and_status_survive_the_trip_unchanged(migrated):
    _mig, da, _eda, excel_da, _excel_eda = migrated
    series_number = da.list_series()[0]
    src_rows = excel_da.read_index_rows(series_number, "transmitter")
    assert src_rows, "expected at least one real transmitter row to spot-check"
    src_row_num = src_rows[0]["row"]
    src_full = excel_da.read_full_row(series_number, "transmitter", src_row_num)
    src_key = src_full["tag"]
    src_status = excel_da.get_status(series_number, "transmitter", src_key)

    dst_full = None
    for r in da.read_index_rows(series_number, "transmitter"):
        if r.get("tag") == src_key:
            dst_full = da.read_full_row(series_number, "transmitter", r["id"])
            break
    assert dst_full is not None, "migrated row not found by tag in the Access-shaped connection"
    for field_id, value in src_full.items():
        assert dst_full.get(field_id) == value, (field_id, value, dst_full.get(field_id))

    dst_status = da.get_status(series_number, "transmitter", src_key)
    assert dst_status["installed"] == src_status["installed"]
    assert dst_status["submitted"] == src_status["submitted"]
    assert dst_status["accepted"] == src_status["accepted"]


def test_migration_never_writes_to_the_source_workbook():
    """The whole point of a migration tool is read-only on the source
    side - if this ever started writing to Equipment_Inspection_Tracker.
    xlsx, that would be a serious regression a full-file hash check
    guards against (openpyxl's own read path never mutates it, but this
    proves that at the file-bytes level, not just "no exception").
    Deliberately doesn't use the `migrated` fixture above - the hash has
    to be taken BEFORE migration runs, not after."""
    import hashlib
    import access_db as db
    import data_access as excel_da
    import migrate_from_excel as mig

    before = hashlib.sha256(excel_da.WORKBOOK_PATH.read_bytes()).hexdigest()
    db.set_connection_for_testing(_build_sqlite_db())
    try:
        mig.migrate_instrumentation(dry_run=False)
        mig.migrate_electrical(dry_run=False)
    finally:
        db.set_connection_for_testing(None)
    after = hashlib.sha256(excel_da.WORKBOOK_PATH.read_bytes()).hexdigest()
    assert before == after, "Equipment_Inspection_Tracker.xlsx changed on disk during migration"


def test_dry_run_writes_nothing(monkeypatch):
    import access_db as db
    import migrate_from_excel as mig
    db.set_connection_for_testing(_build_sqlite_db())
    try:
        import access_data_access as da
        import access_electrical_data_access as eda
        mig.migrate_instrumentation(dry_run=True)
        mig.migrate_electrical(dry_run=True)
        assert da.list_series() == []
        assert eda.list_zones() == []
    finally:
        db.set_connection_for_testing(None)
