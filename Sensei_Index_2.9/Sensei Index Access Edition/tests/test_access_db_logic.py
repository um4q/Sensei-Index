# -*- coding: utf-8 -*-
"""
Validates access_db.py's own generic CRUD/parent-table/settings/
activity-log/status logic against SQLite instead of real Access - see
access_db.py's own docstring for why (no Windows/pyodbc/Access Database
Engine exists in this dev environment at all, so this is the only local
testing possible; the real Access dialect itself is only ever actually
exercised by .github/workflows/build-access-edition.yml, on a real
Windows runner).

This does NOT prove the app works against real Access - it proves the
PYTHON logic around row marshaling, parent lookups, and duplicate-key
handling is sound, using a same-shaped SQLite database as a stand-in.
Both pyodbc's Access driver and sqlite3 are DB-API 2.0 (PEP 249) with
"?" positional parameters, which is what makes this possible at all -
every access_db.py function takes its connection as a parameter rather
than opening one itself, specifically so a test can hand it a sqlite3
connection instead of a real pyodbc one.

ONE KNOWN GAP: read_activity_log()'s own `limit` uses Access's
"SELECT TOP N" syntax, which SQLite doesn't support (it uses LIMIT N
instead) - the TOP-clause path itself is untestable here for that
reason and is skipped below; only real Access CI proves that specific
line works.
"""
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import access_db as db


def _sqlite_conn():
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE Zones (id INTEGER PRIMARY KEY AUTOINCREMENT, "
                  "zone_name TEXT, created_at TEXT)")
    conn.execute("CREATE TABLE Series (id INTEGER PRIMARY KEY AUTOINCREMENT, "
                  "series_number INTEGER, display_name TEXT, created_at TEXT)")
    conn.execute("CREATE TABLE Settings (id INTEGER PRIMARY KEY AUTOINCREMENT, "
                  "setting_key TEXT, setting_value TEXT)")
    conn.execute("CREATE TABLE ActivityLog (id INTEGER PRIMARY KEY AUTOINCREMENT, "
                  "domain TEXT, equip_key TEXT, parent_label TEXT, row_id INTEGER, "
                  "key_value TEXT, action TEXT, details TEXT, source TEXT, timestamp TEXT)")
    conn.execute("CREATE TABLE RowStatus (id INTEGER PRIMARY KEY AUTOINCREMENT, "
                  "domain TEXT, equip_key TEXT, key_value TEXT, installed INTEGER, "
                  "submitted INTEGER, accepted INTEGER, updated_at TEXT)")
    conn.execute("CREATE TABLE TestEquip (id INTEGER PRIMARY KEY AUTOINCREMENT, "
                  "zone_id INTEGER, tag TEXT, notes TEXT, created_at TEXT, updated_at TEXT)")
    conn.commit()
    return conn


def test_insert_and_get_row_round_trips():
    conn = _sqlite_conn()
    new_id = db.insert_row(conn, "TestEquip", {"zone_id": 1, "tag": "T-001", "notes": "hi"})
    assert isinstance(new_id, int) and new_id > 0
    row = db.get_row(conn, "TestEquip", new_id)
    assert row["tag"] == "T-001"
    assert row["notes"] == "hi"


def test_update_row_only_touches_given_columns():
    conn = _sqlite_conn()
    new_id = db.insert_row(conn, "TestEquip", {"zone_id": 1, "tag": "T-001", "notes": "hi"})
    db.update_row(conn, "TestEquip", new_id, {"notes": "updated"})
    row = db.get_row(conn, "TestEquip", new_id)
    assert row["tag"] == "T-001"  # untouched
    assert row["notes"] == "updated"


def test_list_rows_filters_by_parent():
    conn = _sqlite_conn()
    db.insert_row(conn, "TestEquip", {"zone_id": 1, "tag": "A"})
    db.insert_row(conn, "TestEquip", {"zone_id": 1, "tag": "B"})
    db.insert_row(conn, "TestEquip", {"zone_id": 2, "tag": "C"})
    rows = db.list_rows(conn, "TestEquip", parent_field="zone_id", parent_id=1)
    assert {r["tag"] for r in rows} == {"A", "B"}


def test_delete_rows_removes_only_given_ids():
    conn = _sqlite_conn()
    id1 = db.insert_row(conn, "TestEquip", {"zone_id": 1, "tag": "A"})
    id2 = db.insert_row(conn, "TestEquip", {"zone_id": 1, "tag": "B"})
    db.delete_rows(conn, "TestEquip", [id1])
    remaining = db.list_rows(conn, "TestEquip")
    assert [r["id"] for r in remaining] == [id2]


def test_count_rows_respects_parent_filter():
    conn = _sqlite_conn()
    db.insert_row(conn, "TestEquip", {"zone_id": 1, "tag": "A"})
    db.insert_row(conn, "TestEquip", {"zone_id": 2, "tag": "B"})
    assert db.count_rows(conn, "TestEquip") == 2
    assert db.count_rows(conn, "TestEquip", parent_field="zone_id", parent_id=1) == 1


def test_find_by_field_excludes_given_id():
    conn = _sqlite_conn()
    id1 = db.insert_row(conn, "TestEquip", {"zone_id": 1, "tag": "DUPE"})
    id2 = db.insert_row(conn, "TestEquip", {"zone_id": 1, "tag": "DUPE"})
    all_matches = db.find_by_field(conn, "TestEquip", "tag", "DUPE")
    assert {r["id"] for r in all_matches} == {id1, id2}
    excluding_id1 = db.find_by_field(conn, "TestEquip", "tag", "DUPE", exclude_id=id1)
    assert {r["id"] for r in excluding_id1} == {id2}


def test_add_parent_is_idempotent_by_name():
    conn = _sqlite_conn()
    id1, created1 = db.add_parent(conn, "Zones", "zone_name", "K1B Well Pad")
    id2, created2 = db.add_parent(conn, "Zones", "zone_name", "K1B Well Pad")
    assert id1 == id2
    assert created1 is True
    assert created2 is False


def test_list_parents_orders_by_name():
    conn = _sqlite_conn()
    db.add_parent(conn, "Zones", "zone_name", "Zebra Zone")
    db.add_parent(conn, "Zones", "zone_name", "Alpha Zone")
    names = [p["zone_name"] for p in db.list_parents(conn, "Zones", "zone_name")]
    assert names == ["Alpha Zone", "Zebra Zone"]


def test_settings_round_trip_and_update():
    conn = _sqlite_conn()
    assert db.get_setting(conn, "theme") is None
    assert db.get_setting(conn, "theme", "light") == "light"
    db.set_setting(conn, "theme", "dark")
    assert db.get_setting(conn, "theme") == "dark"
    db.set_setting(conn, "theme", "light")  # update path, not insert
    assert db.get_setting(conn, "theme") == "light"


def test_activity_log_records_and_filters():
    conn = _sqlite_conn()
    db.log_activity(conn, "electrical", "transformer_test", "K1B Well Pad", 1, "TAG-1", "save_row")
    db.log_activity(conn, "instrumentation", "valve", "100", 2, "TAG-2", "save_row")
    all_entries = db.read_activity_log(conn)
    assert len(all_entries) == 2
    electrical_only = db.read_activity_log(conn, domain="electrical")
    assert len(electrical_only) == 1
    assert electrical_only[0]["equip_key"] == "transformer_test"


def test_status_defaults_and_round_trips():
    conn = _sqlite_conn()
    default = db.get_status(conn, "electrical", "transformer_test", "TAG-1")
    assert default == {"installed": False, "submitted": False, "accepted": False}

    db.set_status(conn, "electrical", "transformer_test", "TAG-1", installed=True)
    status = db.get_status(conn, "electrical", "transformer_test", "TAG-1")
    assert status["installed"] is True
    assert status["submitted"] is False

    db.set_status(conn, "electrical", "transformer_test", "TAG-1", submitted=True)
    status = db.get_status(conn, "electrical", "transformer_test", "TAG-1")
    assert status["installed"] is True  # still true - update shouldn't reset it
    assert status["submitted"] is True
