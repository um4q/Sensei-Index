# -*- coding: utf-8 -*-
"""
Access Edition's Electrical data-access module - the drop-in-shaped
replacement for electrical_data_access.py, backed by SenseiIndex.accdb
(via access_db.py's generic engine) instead of Electrical_Inspection_
Tracker.xlsx. Covers the CORE workflow the app's own GUI actually
exercises minute to minute: pick a zone, list/read/save/delete rows per
equipment kind, check for duplicate tags, track installed/submitted/
accepted status, generate/export the filled PDF.

NOT PORTED YET (see README_ACCESS_EDITION.txt's own "what's not here
yet" section for the full list and why each one is a separate,
deliberately deferred effort rather than an oversight): the Master List
import/reconciliation engine, the datasheet-PDF-import feature, the
progress-report/cleaned-workbook exporters, and the Excel-file-specific
mechanics that don't mean anything for a real database at all (workbook
locking, backup-by-copying-the-file - Access itself/SharePoint's own
version history covers durability differently, see that same README).

WHY THIS REUSES THE EXCEL EDITION'S OWN export_*.py MODULES UNCHANGED
------------------------------------------------------------------------
Every export_<kind>_to_pdf.py's own fill_pdf() takes a template path and
a plain {field_id: value} dict - it has never once touched openpyxl or
known anything about where its values dict came from. That means the
exact same export modules the Excel edition uses work here completely
unmodified - this module's own job is just producing that same shape of
dict from Access instead of from a worksheet row, then handing it to the
SAME fill_pdf() the Excel edition already has. Nothing about PDF
generation, signature stamping, or field mapping needed porting at all.
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

import export_eht_removal_to_pdf
import export_eht_rtd_to_pdf
import export_eht_pre_insulation_to_pdf
import export_torqueing_to_pdf
import export_transformer_test_to_pdf
import export_small_power_cable_to_pdf
import export_general_equip_install_to_pdf

_EXPORT_MODULES = {
    "eht_removal": export_eht_removal_to_pdf,
    "eht_rtd": export_eht_rtd_to_pdf,
    "eht_pre_insulation": export_eht_pre_insulation_to_pdf,
    "torqueing": export_torqueing_to_pdf,
    "transformer_test": export_transformer_test_to_pdf,
    "small_power_cable": export_small_power_cable_to_pdf,
    "general_equip_install": export_general_equip_install_to_pdf,
}

DOMAIN = "electrical"
PARENT_TABLE = "Zones"
PARENT_NAME_COLUMN = "zone_name"

ELECTRICAL_EQUIPMENT_TYPES = DOMAIN_TABLES["electrical"]  # equip_key -> schema/table/key_field entry

ELECTRICAL_TEMP_DIR = HERE / "electrical_temp_previews"


def _table_name(equip_key):
    return ELECTRICAL_EQUIPMENT_TYPES[equip_key]["table_name"]


def _key_field(equip_key):
    return ELECTRICAL_EQUIPMENT_TYPES[equip_key]["key_field"]


def _field_map(equip_key):
    """This edition's own table columns ARE the schema field ids
    (access_schema.py names every column after its own field id, no
    FIELD_MAP-style rename table needed the way a real fillable PDF's
    own AcroForm field names sometimes require) - so building the
    {field_id: value} dict fill_pdf() wants is a direct passthrough,
    not a translation."""
    return {f["id"]: f["id"] for f in ELECTRICAL_EQUIPMENT_TYPES[equip_key]["fields"]}


# ------------------------------------------------------------------- Zones

def list_zones(conn):
    return [p["zone_name"] for p in db.list_parents(conn, PARENT_TABLE, PARENT_NAME_COLUMN)]


def add_zone(conn, zone_name):
    zone_id, created = db.add_parent(conn, PARENT_TABLE, PARENT_NAME_COLUMN, zone_name)
    if created:
        db.log_activity(conn, DOMAIN, None, zone_name, zone_id, None, "add_zone")
    return zone_id


def get_zone_id(conn, zone_name):
    row = db.get_parent_by_name(conn, PARENT_TABLE, PARENT_NAME_COLUMN, zone_name)
    if row is None:
        raise KeyError(f"No zone named {zone_name!r}")
    return row["id"]


# -------------------------------------------------------------------- Rows

def read_index_rows(conn, zone_name, equip_key):
    """Only rows whose own key field is filled in count as "real" -
    same "blank rows don't show up in the index view" rule
    electrical_data_access.py's own read_index_rows() already applies."""
    zone_id = get_zone_id(conn, zone_name)
    rows = db.list_rows(conn, _table_name(equip_key), parent_field="zone_id", parent_id=zone_id)
    key_field = _key_field(equip_key)
    return [r for r in rows if (r.get(key_field) or "").strip()]


def read_full_row(conn, zone_name, equip_key, row_id):
    row = db.get_row(conn, _table_name(equip_key), row_id)
    if row is None:
        raise KeyError(f"No row {row_id} in {equip_key}")
    return {k: (v if v is not None else "") for k, v in row.items()}


def find_first_blank_row(conn, zone_name, equip_key):
    """Named to match electrical_data_access.py's own function for
    drop-in call compatibility, but there is no "blank row" concept in
    a real database - this just creates a genuinely new, empty row and
    returns its real id. See access_schema.py's own docstring for why
    that's a strict improvement, not a shortcut."""
    zone_id = get_zone_id(conn, zone_name)
    return db.insert_row(conn, _table_name(equip_key), {"zone_id": zone_id, "created_at": db.now_str()})


def save_row(conn, zone_name, equip_key, row_id, values):
    values = dict(values)
    values["updated_at"] = db.now_str()
    db.update_row(conn, _table_name(equip_key), row_id, values)
    key_field = _key_field(equip_key)
    db.log_activity(conn, DOMAIN, equip_key, zone_name, row_id, values.get(key_field), "save_row")


def delete_rows(conn, zone_name, equip_key, row_ids):
    db.delete_rows(conn, _table_name(equip_key), row_ids)
    db.log_activity(conn, DOMAIN, equip_key, zone_name, None, None,
                     "delete_rows", details=f"{len(row_ids)} row(s)")


def find_duplicate_row(conn, zone_name, equip_key, key_value, exclude_row=None):
    if not (key_value or "").strip():
        return None
    zone_id = get_zone_id(conn, zone_name)
    matches = db.find_by_field(conn, _table_name(equip_key), _key_field(equip_key), key_value,
                                parent_field="zone_id", parent_id=zone_id, exclude_id=exclude_row)
    return matches[0] if matches else None


def count_rows(conn, zone_name, equip_key):
    zone_id = get_zone_id(conn, zone_name)
    rows = db.list_rows(conn, _table_name(equip_key), parent_field="zone_id", parent_id=zone_id)
    key_field = _key_field(equip_key)
    return sum(1 for r in rows if (r.get(key_field) or "").strip())


def count_all_by_type(conn, zone_name):
    return {equip_key: count_rows(conn, zone_name, equip_key) for equip_key in ELECTRICAL_EQUIPMENT_TYPES}


# ---------------------------------------------------------------- PDF export

def generate_preview_pdf(conn, zone_name, equip_key, row_id):
    row = read_full_row(conn, zone_name, equip_key, row_id)
    export_mod = _EXPORT_MODULES[equip_key]
    field_map = _field_map(equip_key)
    values = {field_map[fid]: v for fid, v in row.items() if fid in field_map and v}

    key_field = _key_field(equip_key)
    safe_name = export_mod.sanitize(row.get(key_field, ""), f"row{row_id}")

    ELECTRICAL_TEMP_DIR.mkdir(exist_ok=True)
    for old in ELECTRICAL_TEMP_DIR.glob("*.pdf"):
        try:
            old.unlink()
        except OSError:
            pass

    out_path = ELECTRICAL_TEMP_DIR / f"{safe_name} PREVIEW.pdf"
    export_mod.fill_pdf(export_mod.DEFAULT_TEMPLATE, values, out_path, flatten=False)
    return out_path


# ------------------------------------------------------------------- Status

def get_electrical_status(conn, equip_key, key_value):
    return db.get_status(conn, DOMAIN, equip_key, key_value)


def set_electrical_status(conn, equip_key, key_value, **fields):
    db.set_status(conn, DOMAIN, equip_key, key_value, **fields)


# -------------------------------------------------------------- Activity log

def read_electrical_activity_log(conn, limit=None, zone=None, equip_key=None, row=None):
    return db.read_activity_log(conn, limit=limit, domain=DOMAIN, equip_key=equip_key, row_id=row)
