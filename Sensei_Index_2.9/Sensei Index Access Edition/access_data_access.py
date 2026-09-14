# -*- coding: utf-8 -*-
"""
Access Edition's Instrumentation data-access module - the drop-in-shaped
replacement for data_access.py, backed by SenseiIndex.accdb instead of
Equipment_Inspection_Tracker.xlsx. Structurally identical to
access_electrical_data_access.py - "series" instead of "zones" - see
that module's own docstring for the shared reasoning (why the export
modules need zero changes, what's covered vs. not yet ported, and why
find_first_blank_row() keeps its old name despite there being no
"blank row" concept left to find).
"""
import sys
from pathlib import Path

HERE = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) \
    else Path(__file__).resolve().parent
EXCEL_EDITION_DIR = HERE.parent / "Sensei Index 2.9"
if str(EXCEL_EDITION_DIR) not in sys.path:
    sys.path.insert(0, str(EXCEL_EDITION_DIR))

import access_db as db
from access_schema import DOMAIN_TABLES

import export_to_pdf
import export_valve_to_pdf

_EXPORT_MODULES = {
    "transmitter": export_to_pdf,
    "valve": export_valve_to_pdf,
}

DOMAIN = "instrumentation"
PARENT_TABLE = "Series"
PARENT_NAME_COLUMN = "display_name"

EQUIPMENT_TYPES = DOMAIN_TABLES["instrumentation"]  # equip_key -> schema/table/key_field entry

TEMP_DIR = HERE / "temp_previews"


def _table_name(equip_key):
    return EQUIPMENT_TYPES[equip_key]["table_name"]


def _key_field(equip_key):
    return EQUIPMENT_TYPES[equip_key]["key_field"]


def _field_map(equip_key):
    return {f["id"]: f["id"] for f in EQUIPMENT_TYPES[equip_key]["fields"]}


# ------------------------------------------------------------------- Series

def list_series(conn):
    """Returns series NUMBERS (matching data_access.py's own list_series()
    return shape) - display_name doubles as the lookup key here since a
    series is really identified by its number, but Series.display_name
    is what actually gets shown/searched (data_access.py's own
    series_display_label() does similar number-vs-name juggling)."""
    rows = db.list_parents(conn, PARENT_TABLE, "series_number")
    return [r["series_number"] for r in rows]


def add_series(conn, new_number, display_name=None):
    display_name = display_name or str(new_number)
    existing = _get_series_row(conn, new_number)
    if existing is not None:
        return existing["id"]
    new_id = db.insert_row(conn, PARENT_TABLE, {
        "series_number": new_number, "display_name": display_name, "created_at": db.now_str(),
    })
    db.log_activity(conn, DOMAIN, None, str(new_number), new_id, None, "add_series")
    return new_id


def _get_series_row(conn, series_number):
    cursor = conn.cursor()
    cursor.execute(f"SELECT * FROM [{PARENT_TABLE}] WHERE series_number = ?", [series_number])
    row = cursor.fetchone()
    if row is None:
        return None
    return {desc[0]: value for desc, value in zip(cursor.description, row)}


def get_series_id(conn, series_number):
    row = _get_series_row(conn, series_number)
    if row is None:
        raise KeyError(f"No series numbered {series_number!r}")
    return row["id"]


def series_display_label(conn, series_number):
    row = _get_series_row(conn, series_number)
    if row is None:
        return str(series_number)
    return row.get("display_name") or str(series_number)


# -------------------------------------------------------------------- Rows

def read_index_rows(conn, series_number, equip_key):
    series_id = get_series_id(conn, series_number)
    rows = db.list_rows(conn, _table_name(equip_key), parent_field="series_id", parent_id=series_id)
    key_field = _key_field(equip_key)
    return [r for r in rows if (r.get(key_field) or "").strip()]


def read_full_row(conn, series_number, equip_key, row_id):
    row = db.get_row(conn, _table_name(equip_key), row_id)
    if row is None:
        raise KeyError(f"No row {row_id} in {equip_key}")
    return {k: (v if v is not None else "") for k, v in row.items()}


def find_first_blank_row(conn, series_number, equip_key):
    series_id = get_series_id(conn, series_number)
    return db.insert_row(conn, _table_name(equip_key), {"series_id": series_id, "created_at": db.now_str()})


def save_row(conn, series_number, equip_key, row_id, values, source="edit_dialog"):
    values = dict(values)
    values["updated_at"] = db.now_str()
    db.update_row(conn, _table_name(equip_key), row_id, values)
    key_field = _key_field(equip_key)
    db.log_activity(conn, DOMAIN, equip_key, str(series_number), row_id,
                     values.get(key_field), "save_row", source=source)


def delete_rows(conn, series_number, equip_key, row_ids, source="edit_dialog"):
    db.delete_rows(conn, _table_name(equip_key), row_ids)
    db.log_activity(conn, DOMAIN, equip_key, str(series_number), None, None,
                     "delete_rows", details=f"{len(row_ids)} row(s)", source=source)


def find_duplicate_row(conn, series_number, equip_key, key_value, exclude_row=None):
    if not (key_value or "").strip():
        return None
    series_id = get_series_id(conn, series_number)
    matches = db.find_by_field(conn, _table_name(equip_key), _key_field(equip_key), key_value,
                                parent_field="series_id", parent_id=series_id, exclude_id=exclude_row)
    return matches[0] if matches else None


def count_rows(conn, series_number, equip_key):
    series_id = get_series_id(conn, series_number)
    rows = db.list_rows(conn, _table_name(equip_key), parent_field="series_id", parent_id=series_id)
    key_field = _key_field(equip_key)
    return sum(1 for r in rows if (r.get(key_field) or "").strip())


def count_all_by_type(conn, series_number):
    return {equip_key: count_rows(conn, series_number, equip_key) for equip_key in EQUIPMENT_TYPES}


# ---------------------------------------------------------------- PDF export

def generate_preview_pdf(conn, series_number, equip_key, row_id):
    row = read_full_row(conn, series_number, equip_key, row_id)
    export_mod = _EXPORT_MODULES[equip_key]
    field_map = _field_map(equip_key)
    values = {field_map[fid]: v for fid, v in row.items() if fid in field_map and v}

    key_field = _key_field(equip_key)
    safe_name = export_mod.sanitize(row.get(key_field, ""), f"row{row_id}")

    TEMP_DIR.mkdir(exist_ok=True)
    for old in TEMP_DIR.glob("*.pdf"):
        try:
            old.unlink()
        except OSError:
            pass

    out_path = TEMP_DIR / f"{safe_name} PREVIEW.pdf"
    export_mod.fill_pdf(export_mod.DEFAULT_TEMPLATE, values, out_path, flatten=False)
    return out_path


# ------------------------------------------------------------------- Status

def get_status(conn, equip_key, key_value):
    return db.get_status(conn, DOMAIN, equip_key, key_value)


def set_status(conn, equip_key, key_value, **fields):
    db.set_status(conn, DOMAIN, equip_key, key_value, **fields)


# -------------------------------------------------------------- Activity log

def read_activity_log(conn, limit=None, series=None, equip_key=None, row=None):
    return db.read_activity_log(conn, limit=limit, domain=DOMAIN, equip_key=equip_key, row_id=row)


# ---------------------------------------------------------------- Settings

def get_setting(conn, key, default=None):
    return db.get_setting(conn, key, default)


def set_setting(conn, key, value):
    db.set_setting(conn, key, value)
