# -*- coding: utf-8 -*-
"""
The generic database engine both access_data_access.py (Instrumentation)
and access_electrical_data_access.py (Electrical) are built on. Neither
domain module talks to pyodbc directly - they call the generic
CRUD/parent-table/settings/activity-log/status functions here, the same
way data_access.py/electrical_data_access.py in the Excel edition share
a lot of structural similarity but aren't literally the same file. This
module IS shared, on purpose: "list series" and "list zones" are the
same operation against a different parent table, and duplicating that
logic twice would just be two copies to keep in sync.

TESTABILITY, GIVEN THIS CAN'T RUN IN A LINUX DEV ENVIRONMENT AT ALL
------------------------------------------------------------------------
Real Access needs pyodbc + the Microsoft Access Database Engine, both
Windows-only - there's no way to exercise this against a REAL .accdb
anywhere but Windows (see build_access_database.py's own docstring, and
.github/workflows/build-access-edition.yml, which is the only place this
ever actually runs against real Access). To still catch ordinary Python
bugs (typos, wrong dict keys, off-by-one row handling) before that,
every function here takes its connection via get_connection() rather
than hardcoding pyodbc - swap get_connection() for one that returns a
sqlite3 connection (same DB-API 2.0 shape, same "?" parameter
placeholder style pyodbc's Access driver also uses) and every function
below runs unmodified against SQLite for local logic testing. See
tests/test_access_db_logic.py for exactly that - it is NOT a
"this proves Access works" test, only a "this proves the Python logic
around row marshaling/parent lookups/duplicate keys is sound" test.
"""
import datetime
import json
import sys
from pathlib import Path

HERE = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) \
    else Path(__file__).resolve().parent
DB_PATH = HERE / "SenseiIndex.accdb"

_ACCESS_CONN_STR = (
    r"Driver={{Microsoft Access Driver (*.mdb, *.accdb)}};"
    r"Dbq={path};"
)


def get_connection(path=None):
    """Real callers (the app itself) never pass `path` - it always
    resolves to DB_PATH, next to the exe/script, same frozen-aware
    pattern every Excel-edition module already uses. Tests pass an
    open sqlite3 connection directly to every function instead of
    calling this at all - see this module's own docstring."""
    import pyodbc
    target = path or DB_PATH
    if not target.exists():
        raise FileNotFoundError(
            f"No database found at {target}. Run build_access_database.py once "
            "(or copy a real SenseiIndex.accdb next to the app) before using it."
        )
    conn_str = _ACCESS_CONN_STR.format(path=target)
    return pyodbc.connect(conn_str, autocommit=False)


# ------------------------------------------------------------ Cached connection
# access_data_access.py/access_electrical_data_access.py's own public
# functions match data_access.py/electrical_data_access.py's real
# calling convention exactly - gui_app.py calls da.list_series() with NO
# connection argument, the same way it always has - so something has to
# hold the one open connection those domain functions reach for
# internally. This mirrors data_access.py's own _get_cached_workbook()
# (open once, reuse, invalidate on demand) rather than opening a fresh
# connection per call.
_cached_conn = None


def get_cached_connection():
    global _cached_conn
    if _cached_conn is None:
        _cached_conn = get_connection()
    return _cached_conn


def set_connection_for_testing(conn):
    """Test-only override - hands every domain function a sqlite3
    connection instead of a real pyodbc one, the same way data_access.py's
    own tests point HERE/WORKBOOK_PATH at an isolated tmp_path rather than
    the real workbook. See tests/test_domain_modules_integration.py."""
    global _cached_conn
    _cached_conn = conn


def invalidate_connection_cache():
    global _cached_conn
    if _cached_conn is not None:
        try:
            _cached_conn.close()
        except Exception:
            pass
    _cached_conn = None


def now_str():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _quoted(name):
    return f"[{name}]"


def _row_to_dict(cursor, row):
    return {desc[0]: value for desc, value in zip(cursor.description, row)}


# --------------------------------------------------------------- Generic CRUD

def insert_row(conn, table_name, values):
    """values: {column: value} - INSERTs one new row, returns its real
    autoincrement id. sqlite3's own Cursor always has a lastrowid
    attribute (populated after an INSERT); pyodbc's Access driver's own
    Cursor has NO such attribute AT ALL - not just unpopulated, genuinely
    missing, so a bare cursor.lastrowid raises AttributeError rather than
    returning None (confirmed the hard way, via
    .github/workflows/build-access-edition.yml's own real-Access run -
    this is exactly the class of dialect gap the local SQLite-backed
    tests can't catch, see this module's own docstring). getattr(...,
    None) covers both drivers uniformly; @@IDENTITY is the fallback
    every real Access connection needs."""
    columns = list(values.keys())
    placeholders = ", ".join("?" for _ in columns)
    col_sql = ", ".join(_quoted(c) for c in columns)
    sql = f"INSERT INTO {_quoted(table_name)} ({col_sql}) VALUES ({placeholders})"
    cursor = conn.cursor()
    cursor.execute(sql, list(values.values()))
    new_id = getattr(cursor, "lastrowid", None)
    if new_id is None:
        # @@IDENTITY is the reliable way to get a COUNTER column's
        # just-inserted value back from Access via ODBC.
        cursor.execute("SELECT @@IDENTITY")
        new_id = cursor.fetchone()[0]
    conn.commit()
    return int(new_id)


def update_row(conn, table_name, row_id, values):
    if not values:
        return
    set_sql = ", ".join(f"{_quoted(c)} = ?" for c in values.keys())
    sql = f"UPDATE {_quoted(table_name)} SET {set_sql} WHERE id = ?"
    cursor = conn.cursor()
    cursor.execute(sql, list(values.values()) + [row_id])
    conn.commit()


def get_row(conn, table_name, row_id):
    sql = f"SELECT * FROM {_quoted(table_name)} WHERE id = ?"
    cursor = conn.cursor()
    cursor.execute(sql, [row_id])
    row = cursor.fetchone()
    if row is None:
        return None
    return _row_to_dict(cursor, row)


def list_rows(conn, table_name, parent_field=None, parent_id=None, order_by="id"):
    sql = f"SELECT * FROM {_quoted(table_name)}"
    params = []
    if parent_field is not None:
        sql += f" WHERE {_quoted(parent_field)} = ?"
        params.append(parent_id)
    sql += f" ORDER BY {_quoted(order_by)}"
    cursor = conn.cursor()
    cursor.execute(sql, params)
    rows = cursor.fetchall()
    return [_row_to_dict(cursor, r) for r in rows]


def delete_rows(conn, table_name, row_ids):
    if not row_ids:
        return
    placeholders = ", ".join("?" for _ in row_ids)
    sql = f"DELETE FROM {_quoted(table_name)} WHERE id IN ({placeholders})"
    cursor = conn.cursor()
    cursor.execute(sql, list(row_ids))
    conn.commit()


def count_rows(conn, table_name, parent_field=None, parent_id=None):
    sql = f"SELECT COUNT(*) FROM {_quoted(table_name)}"
    params = []
    if parent_field is not None:
        sql += f" WHERE {_quoted(parent_field)} = ?"
        params.append(parent_id)
    cursor = conn.cursor()
    cursor.execute(sql, params)
    return cursor.fetchone()[0]


def find_by_field(conn, table_name, field_name, value, parent_field=None, parent_id=None, exclude_id=None):
    """Used for duplicate-key checks - same 'advisory, not hard-enforced'
    duplicate handling the Excel edition's own find_duplicate_row()
    functions already do (a real UNIQUE constraint would be more
    correct in the abstract, but would break the exact same legitimate
    "temporarily has 2 rows with the same tag while data gets sorted
    out" workflows those functions were built to tolerate - see their
    own docstrings)."""
    sql = f"SELECT * FROM {_quoted(table_name)} WHERE {_quoted(field_name)} = ?"
    params = [value]
    if parent_field is not None:
        sql += f" AND {_quoted(parent_field)} = ?"
        params.append(parent_id)
    if exclude_id is not None:
        sql += " AND id <> ?"
        params.append(exclude_id)
    cursor = conn.cursor()
    cursor.execute(sql, params)
    rows = cursor.fetchall()
    return [_row_to_dict(cursor, r) for r in rows]


# ------------------------------------------------------------- Parent tables
# (Series for Instrumentation, Zones for Electrical - same shape, just a
# different table/column name, which is exactly why this is generic
# instead of living twice in the two domain modules.)

def list_parents(conn, parent_table, name_column):
    cursor = conn.cursor()
    cursor.execute(f"SELECT * FROM {_quoted(parent_table)} ORDER BY {_quoted(name_column)}")
    rows = cursor.fetchall()
    return [_row_to_dict(cursor, r) for r in rows]


def get_parent_by_name(conn, parent_table, name_column, name_value):
    cursor = conn.cursor()
    cursor.execute(
        f"SELECT * FROM {_quoted(parent_table)} WHERE {_quoted(name_column)} = ?",
        [name_value],
    )
    row = cursor.fetchone()
    if row is None:
        return None
    return _row_to_dict(cursor, row)


def add_parent(conn, parent_table, name_column, name_value):
    existing = get_parent_by_name(conn, parent_table, name_column, name_value)
    if existing is not None:
        return existing["id"], False
    new_id = insert_row(conn, parent_table, {name_column: name_value, "created_at": now_str()})
    return new_id, True


# ------------------------------------------------------------------ Settings

def get_setting(conn, key, default=None):
    cursor = conn.cursor()
    cursor.execute("SELECT setting_value FROM [Settings] WHERE setting_key = ?", [key])
    row = cursor.fetchone()
    return row[0] if row is not None else default


def set_setting(conn, key, value):
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM [Settings] WHERE setting_key = ?", [key])
    row = cursor.fetchone()
    if row is None:
        insert_row(conn, "Settings", {"setting_key": key, "setting_value": value})
    else:
        update_row(conn, "Settings", row[0], {"setting_value": value})


# --------------------------------------------------------------- Activity log

def log_activity(conn, action, domain=None, equip_key=None, parent_label=None, row_id=None,
                  key_value=None, fields=None, source="app", note=None, ts=None):
    """Matches data_access.py's own log_activity(action, series=..., ...)
    shape (parent_label here covers both series and zone - domain says
    which) - fields: {field_id: {'old': ..., 'new': ...}}, stored as JSON
    text in fields_json (Access has no native JSON/dict column type,
    same "one JSON object' worth of text" idea activity_log.jsonl's own
    per-line format already uses)."""
    insert_row(conn, "ActivityLog", {
        "domain": domain, "equip_key": equip_key, "parent_label": parent_label,
        "row_id": row_id, "key_value": key_value, "action": action,
        "fields_json": json.dumps(fields or {}), "note": note,
        "source": source, "timestamp": ts or now_str(),
    })


def read_activity_log(conn, limit=None, domain=None, equip_key=None, row_id=None):
    sql = "SELECT * FROM [ActivityLog]"
    clauses = []
    params = []
    if domain is not None:
        clauses.append("domain = ?")
        params.append(domain)
    if equip_key is not None:
        clauses.append("equip_key = ?")
        params.append(equip_key)
    if row_id is not None:
        clauses.append("row_id = ?")
        params.append(row_id)
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY id DESC"
    if limit:
        sql = sql.replace("SELECT *", f"SELECT TOP {int(limit)} *")
    cursor = conn.cursor()
    cursor.execute(sql, params)
    rows = cursor.fetchall()
    entries = [_row_to_dict(cursor, r) for r in rows]
    for entry in entries:
        try:
            entry["fields"] = json.loads(entry.get("fields_json") or "{}")
        except (TypeError, ValueError):
            entry["fields"] = {}
    return entries


# ------------------------------------------------------------------- Status

DEFAULT_STATUS = {"installed": False, "submitted": False, "accepted": False, "export": False}


def get_status(conn, domain, equip_key, key_value):
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM [RowStatus] WHERE domain = ? AND equip_key = ? AND key_value = ?",
        [domain, equip_key, key_value],
    )
    row = cursor.fetchone()
    if row is None:
        return dict(DEFAULT_STATUS)
    d = _row_to_dict(cursor, row)
    return {"installed": bool(d["installed"]), "submitted": bool(d["submitted"]),
            "accepted": bool(d["accepted"]), "export": bool(d["export"])}


def set_status(conn, domain, equip_key, key_value, **fields):
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id FROM [RowStatus] WHERE domain = ? AND equip_key = ? AND key_value = ?",
        [domain, equip_key, key_value],
    )
    row = cursor.fetchone()
    fields["updated_at"] = now_str()
    if row is None:
        insert_row(conn, "RowStatus", {"domain": domain, "equip_key": equip_key,
                                        "key_value": key_value, **fields})
    else:
        update_row(conn, "RowStatus", row[0], fields)


def bulk_set_status(conn, domain, keys, **fields):
    """keys: [(equip_key, key_value), ...] - same row-update, many keys,
    one call shape as data_access.py's own bulk_set_status()/
    bulk_set_electrical_status()."""
    for equip_key, key_value in keys:
        set_status(conn, domain, equip_key, key_value, **fields)


def rename_status_key(conn, domain, equip_key, old_key, new_key):
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id FROM [RowStatus] WHERE domain = ? AND equip_key = ? AND key_value = ?",
        [domain, equip_key, old_key],
    )
    row = cursor.fetchone()
    if row is not None:
        update_row(conn, "RowStatus", row[0], {"key_value": new_key, "updated_at": now_str()})
