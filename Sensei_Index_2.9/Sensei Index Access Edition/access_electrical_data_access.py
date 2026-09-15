# -*- coding: utf-8 -*-
"""
Access Edition's Electrical data-access module - a drop-in replacement
for electrical_data_access.py's own call surface, backed by
SenseiIndex.accdb instead of Electrical_Inspection_Tracker.xlsx.

"Drop-in" is not an exaggeration here: every public function below
matches electrical_data_access.py's own signature exactly - including
taking NO explicit database connection argument, the same way
electrical_data_access.py's own functions take no explicit workbook
argument (both manage a single cached connection/workbook internally -
see access_db.py's own get_cached_connection()). That's what lets
gui_app.py's real UI code run against this module completely
unmodified - see access_gui_app.py's own docstring for the "why copy
gui_app.py almost verbatim" reasoning, and README_ACCESS_EDITION.txt
for the short version.

WHY THIS REUSES SO MUCH OF THE EXCEL EDITION'S OWN CODE DIRECTLY
------------------------------------------------------------------------
A lot of electrical_data_access.py's own logic was never actually
Excel-specific to begin with - it just lived there because that's where
the Excel-specific I/O also lived:
  - Every export_<kind>_to_pdf.py module: pure {field_id: value} -> PDF,
    zero openpyxl dependency in fill_pdf() itself.
  - tag_shape_warning, compute_progress, and its own small helpers
    (_progress_blank, _serial_captured, _inspection_complete) in
    data_access.py: pure functions over plain dicts, not Excel calls.
So those are imported directly, not re-implemented - they're the exact
Excel edition functions, imported and reused as-is. What's actually new
here is the DATA ACCESS underneath: reading/writing Access tables
instead of worksheet cells.
"""
import datetime
import os
import re
import sys
from pathlib import Path

HERE = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) \
    else Path(__file__).resolve().parent
EXCEL_EDITION_DIR = HERE.parent / "Sensei Index 2.9"
if str(EXCEL_EDITION_DIR) not in sys.path:
    sys.path.insert(0, str(EXCEL_EDITION_DIR))

import access_db as db
from access_schema import DOMAIN_TABLES

# Pure, backend-agnostic logic reused directly from the Excel edition -
# see this module's own docstring for why these are imports, not ports.
from data_access import compute_progress, tag_shape_warning  # noqa: F401
# ELECTRICAL_EQUIPMENT_TYPES itself is ALSO reused directly, not derived
# from access_schema.py's DOMAIN_TABLES - see access_data_access.py's
# own identical EQUIPMENT_TYPES import for the full reasoning (that
# registry's label/schema/export_module/summary_fields/date_fields/
# supports_signature_stamp metadata is pure UI metadata, never Excel-
# specific). access_schema.py's own DOMAIN_TABLES entries stay in play
# too, as _DB_TABLES below, purely for the Access table name and field
# list the real registry doesn't carry.
from electrical_data_access import ELECTRICAL_EQUIPMENT_TYPES  # noqa: F401

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

_DB_TABLES = DOMAIN_TABLES["electrical"]  # equip_key -> table_name/fields (DB layer only, see above)

ELECTRICAL_TEMP_DIR = HERE / "electrical_temp_previews"
ELECTRICAL_OUTPUT_DIR = HERE / "output_pdfs"
ELECTRICAL_BACKUPS_DIR = HERE / "electrical_backups"


class WorkbookLockedError(Exception):
    """Kept for gui_app.py's own `except eda.WorkbookLockedError:` blocks
    to keep working unmodified - Access's own locking (a .laccdb file
    next to the .accdb while it's open) is handled by the ACE engine
    itself at the row/table level, not by this app pre-checking a lock
    file the way the Excel edition's own is_workbook_locked() does, so
    this is never actually raised here today. Real concurrent-write
    conflicts surface as a pyodbc.Error from the failing INSERT/UPDATE
    itself instead."""


def _table_name(equip_key):
    return _DB_TABLES[equip_key]["table_name"]


def _key_field(equip_key):
    return _DB_TABLES[equip_key]["key_field"]


def _field_map(equip_key):
    """This edition's own table columns ARE the schema field ids - see
    access_schema.py's own docstring - so building the {field_id: value}
    dict fill_pdf() wants is a direct passthrough, not a translation."""
    return {f["id"]: f["id"] for f in _DB_TABLES[equip_key]["fields"]}


# ------------------------------------------------------------------- Zones

def list_zones():
    conn = db.get_cached_connection()
    return [p["zone_name"] for p in db.list_parents(conn, PARENT_TABLE, PARENT_NAME_COLUMN)]


def add_zone(zone_name):
    conn = db.get_cached_connection()
    zone_id, created = db.add_parent(conn, PARENT_TABLE, PARENT_NAME_COLUMN, zone_name)
    if created:
        db.log_activity(conn, "add_zone", domain=DOMAIN, parent_label=zone_name, row_id=zone_id)
    return zone_id


def set_zone_name(zone_name, new_name):
    zone_name = (zone_name or "").strip()
    new_name = (new_name or "").strip()
    if not new_name:
        raise ValueError("Zone name can't be blank.")
    conn = db.get_cached_connection()
    row = db.get_parent_by_name(conn, PARENT_TABLE, PARENT_NAME_COLUMN, zone_name)
    if row is None:
        raise KeyError(f"No zone named {zone_name!r}")
    if new_name != zone_name and db.get_parent_by_name(conn, PARENT_TABLE, PARENT_NAME_COLUMN, new_name):
        raise ValueError(f"Zone {new_name!r} already exists.")
    db.update_row(conn, PARENT_TABLE, row["id"], {PARENT_NAME_COLUMN: new_name})
    db.log_activity(conn, "rename_zone", domain=DOMAIN, parent_label=new_name, row_id=row["id"],
                     note=f"was {zone_name!r}")


def remove_zone(zone_name):
    """No archive-by-hiding concept for a real database row the way the
    Excel edition's own remove_zone() archives a sheet in place - this
    genuinely deletes the Zones row AND every equipment-kind row under
    it (matching relational delete semantics, not Excel's own "sheets
    can't really be un-created cleanly" workaround). A confirm dialog
    upstream (access_gui_app.py) is where "are you sure" belongs, same
    as it already is in gui_app.py."""
    conn = db.get_cached_connection()
    row = db.get_parent_by_name(conn, PARENT_TABLE, PARENT_NAME_COLUMN, zone_name)
    if row is None:
        raise KeyError(f"No zone named {zone_name!r}")
    zone_id = row["id"]
    for equip_key in ELECTRICAL_EQUIPMENT_TYPES:
        rows = db.list_rows(conn, _table_name(equip_key), parent_field="zone_id", parent_id=zone_id)
        if rows:
            db.delete_rows(conn, _table_name(equip_key), [r["id"] for r in rows])
    db.delete_rows(conn, PARENT_TABLE, [zone_id])
    db.log_activity(conn, "remove_zone", domain=DOMAIN, parent_label=zone_name)


def get_zone_id(zone_name):
    conn = db.get_cached_connection()
    row = db.get_parent_by_name(conn, PARENT_TABLE, PARENT_NAME_COLUMN, zone_name)
    if row is None:
        raise KeyError(f"No zone named {zone_name!r}")
    return row["id"]


def zone_summary(zone_name):
    result = {k: {"total": 0} for k in ELECTRICAL_EQUIPMENT_TYPES}
    for equip_key in ELECTRICAL_EQUIPMENT_TYPES:
        try:
            result[equip_key] = {"total": count_rows(zone_name, equip_key)}
        except KeyError:
            pass
    return result


# -------------------------------------------------------------------- Rows

def read_index_rows(zone_name, equip_key):
    conn = db.get_cached_connection()
    zone_id = get_zone_id(zone_name)
    rows = db.list_rows(conn, _table_name(equip_key), parent_field="zone_id", parent_id=zone_id)
    key_field = _key_field(equip_key)
    out = []
    for r in rows:
        if not (r.get(key_field) or "").strip():
            continue
        r["row"] = r["id"]  # gui_app.py reads the row id back as "row" - see read_index_rows_with_export_status
        out.append(r)
    return out


def read_index_rows_with_export_status(zone_name, equip_key):
    conn = db.get_cached_connection()
    key_field = _key_field(equip_key)
    rows = read_index_rows(zone_name, equip_key)
    for entry in rows:
        status = db.get_status(conn, DOMAIN, equip_key, entry.get(key_field, ""))
        entry["export"] = status["export"]
    return rows


def read_full_row(zone_name, equip_key, row_id):
    conn = db.get_cached_connection()
    row = db.get_row(conn, _table_name(equip_key), row_id)
    if row is None:
        raise KeyError(f"No row {row_id} in {equip_key}")
    return {k: (v if v is not None else "") for k, v in row.items()}


def find_first_blank_row(zone_name, equip_key):
    """Named to match electrical_data_access.py's own function for
    drop-in call compatibility, but there is no "blank row" concept in
    a real database - this creates a genuinely new, empty row and
    returns its real id. See access_schema.py's own docstring."""
    conn = db.get_cached_connection()
    zone_id = get_zone_id(zone_name)
    return db.insert_row(conn, _table_name(equip_key), {"zone_id": zone_id, "created_at": db.now_str()})


def save_row(zone_name, equip_key, row_id, values):
    conn = db.get_cached_connection()
    values = dict(values)
    values["updated_at"] = db.now_str()
    db.update_row(conn, _table_name(equip_key), row_id, values)
    key_field = _key_field(equip_key)
    db.log_activity(conn, "save_row", domain=DOMAIN, equip_key=equip_key, parent_label=zone_name,
                     row_id=row_id, key_value=values.get(key_field))


def delete_rows(zone_name, equip_key, row_nums):
    conn = db.get_cached_connection()
    db.delete_rows(conn, _table_name(equip_key), row_nums)
    db.log_activity(conn, "delete_rows", domain=DOMAIN, equip_key=equip_key, parent_label=zone_name,
                     note=f"{len(row_nums)} row(s)")


def find_duplicate_row(zone_name, equip_key, key_value, exclude_row=None):
    if not (key_value or "").strip():
        return None
    conn = db.get_cached_connection()
    zone_id = get_zone_id(zone_name)
    matches = db.find_by_field(conn, _table_name(equip_key), _key_field(equip_key), key_value,
                                parent_field="zone_id", parent_id=zone_id, exclude_id=exclude_row)
    return matches[0] if matches else None


def count_rows(zone_name, equip_key):
    return len(read_index_rows(zone_name, equip_key))


def count_all_by_type(zone_name):
    return {equip_key: count_rows(zone_name, equip_key) for equip_key in ELECTRICAL_EQUIPMENT_TYPES}


# ---------------------------------------------------------------- PDF export

def generate_preview_pdf(zone_name, equip_key, row_id):
    row = read_full_row(zone_name, equip_key, row_id)
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


def run_export(zone_name, equip_key, mode, suffix="", flatten=False,
                subfolder=None, merge=False, clear_after_selected=True,
                include_date_in_filename=False, include_signature=True):
    """Same mode/kwarg shape as electrical_data_access.py's own
    run_export() - see that function's own docstring for the exact
    semantics of each ('selected' vs 'all', clear_after_selected, etc.).
    Reads rows already fetched via this module's own read_index_rows*()
    instead of scanning worksheet cells - a real database needs no
    column-map/cell-by-cell reading at all."""
    from pypdf import PdfReader, PdfWriter

    conn = db.get_cached_connection()
    etype = ELECTRICAL_EQUIPMENT_TYPES[equip_key]
    export_mod = etype["export_module"] if "export_module" in etype else _EXPORT_MODULES[equip_key]
    field_map = _field_map(equip_key)
    key_field = _key_field(equip_key)

    out_dir = ELECTRICAL_OUTPUT_DIR
    if subfolder:
        safe_sub = re.sub(r'[<>:"/\\|?*]', "_", subfolder).strip()
        if safe_sub:
            out_dir = out_dir / safe_sub
    out_dir.mkdir(parents=True, exist_ok=True)

    if mode == "selected":
        rows = [r for r in read_index_rows_with_export_status(zone_name, equip_key) if r.get("export")]
    else:
        rows = read_index_rows(zone_name, equip_key)
    if not rows:
        return []

    filename_date = f" {datetime.date.today().isoformat()}" if include_date_in_filename else ""
    written = []
    used_names = set()
    for row in rows:
        values = {field_map[fid]: v for fid, v in row.items() if fid in field_map and v}
        key_val = row.get(key_field, "")
        base_name = export_mod.sanitize(key_val, f"Row{row['id']}")
        base_name = f"{base_name} {suffix}" if suffix else base_name
        base_name = f"{base_name}{filename_date}"
        name = base_name
        n = 2
        while name in used_names:
            name = f"{base_name} ({n})"
            n += 1
        used_names.add(name)
        out_path = out_dir / f"{name}.pdf"
        if etype.get("supports_signature_stamp"):
            export_mod.fill_pdf(export_mod.DEFAULT_TEMPLATE, values, out_path,
                                 flatten=flatten, add_signature=include_signature)
        else:
            export_mod.fill_pdf(export_mod.DEFAULT_TEMPLATE, values, out_path, flatten=flatten)
        written.append(out_path)

        if mode == "selected" and clear_after_selected:
            db.set_status(conn, DOMAIN, equip_key, key_val, export=False)

    if merge and written:
        merged_writer = PdfWriter()
        for p in written:
            merged_writer.append(PdfReader(str(p)))
        merged_writer.set_need_appearances_writer(True)
        stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        merged_path = out_dir / f"Combined_Export_{stamp}.pdf"
        with open(merged_path, "wb") as fh:
            merged_writer.write(fh)
        written.append(merged_path)

    db.log_activity(conn, "run_export", domain=DOMAIN, equip_key=equip_key, parent_label=zone_name,
                     note=f"{len(rows)} row(s), mode={mode}")
    return written


# ------------------------------------------------------------------- Status

def get_electrical_status(zone_name, equip_key, key_value):
    conn = db.get_cached_connection()
    return db.get_status(conn, DOMAIN, equip_key, key_value)


def set_electrical_status(zone_name, equip_key, key_value, **fields):
    conn = db.get_cached_connection()
    db.set_status(conn, DOMAIN, equip_key, key_value, **fields)


def bulk_set_electrical_status(keys, **fields):
    """keys: [(equip_key, key_value), ...] - matches
    electrical_data_access.py's own bulk_set_electrical_status()."""
    conn = db.get_cached_connection()
    db.bulk_set_status(conn, DOMAIN, keys, **fields)


# -------------------------------------------------------------- Activity log

def read_electrical_activity_log(limit=None, zone=None, equip_key=None, row=None):
    conn = db.get_cached_connection()
    return db.read_activity_log(conn, limit=limit, domain=DOMAIN, equip_key=equip_key, row_id=row)


# --------------------------------------------------------------- Duplicate serials

SERIAL_FIELD_BY_KIND = {
    "transformer_test": "serial_number",
    "general_equip_install": "serial_number",
}


def find_rows_with_duplicate_serial(equip_key, serial_value, exclude_zone_row=None):
    """Every {'zone', 'row', 'key_value'} across ALL zones of this
    equipment kind whose primary serial field matches serial_value -
    same intent as data_access.py's own find_rows_with_duplicate_serial(),
    reimplemented against Access reads instead of worksheet cell scans."""
    field = SERIAL_FIELD_BY_KIND.get(equip_key)
    if not field:
        return []
    target = (serial_value or "").strip().lower()
    if not target:
        return []
    key_field = _key_field(equip_key)
    matches = []
    for zone_name in list_zones():
        for row in read_index_rows(zone_name, equip_key):
            if exclude_zone_row == (zone_name, row["id"]):
                continue
            if (row.get(field) or "").strip().lower() != target:
                continue
            key_val = row.get(key_field, "")
            if key_val:
                matches.append({"zone": zone_name, "row": row["id"], "key_value": key_val})
    return matches


# ---------------------------------------------------------------- Backups

def list_backups():
    """[{'path', 'name', 'mtime', 'size'}, ...], NEWEST first - same
    shape electrical_data_access.py's own list_backups() returns. See
    access_data_access.py's own identical fix for why this can't just
    return raw Path objects (BackupsDialog is shared between both
    domains via its own backend= param, and indexes every entry by
    these 4 dict keys - caught via a real BackupsDialog smoke test,
    opened as the Electrical sidebar's own Backups... button does)."""
    if not ELECTRICAL_BACKUPS_DIR.exists():
        return []
    result = []
    for p in sorted(ELECTRICAL_BACKUPS_DIR.glob("SenseiIndex.*.accdb"), reverse=True):
        try:
            stat = p.stat()
        except OSError:
            continue
        result.append({"path": p, "name": p.name, "mtime": stat.st_mtime, "size": stat.st_size})
    return result


def restore_backup(backup_path):
    """Copies the chosen snapshot over the live .accdb - same "one more
    safety snapshot first" guarantee as access_data_access.py's own
    restore_backup(). Only the backups FOLDER differs between the two
    domains (ELECTRICAL_BACKUPS_DIR vs. BACKUPS_DIR) - the .accdb being
    restored is the same single shared database either way."""
    import shutil

    backup_path = Path(backup_path)
    if not backup_path.exists():
        raise FileNotFoundError(f"Backup not found: {backup_path}")
    safety_snapshot = None
    if db.DB_PATH.exists():
        db.invalidate_connection_cache()
        safety_snapshot = backup_now()
    else:
        db.invalidate_connection_cache()
    ELECTRICAL_BACKUPS_DIR.mkdir(exist_ok=True)
    shutil.copy(str(backup_path), str(db.DB_PATH))
    return safety_snapshot


def backup_now():
    """Copies SenseiIndex.accdb into ELECTRICAL_BACKUPS_DIR, timestamped -
    same idea as the Excel edition's own backup-the-workbook-file
    mechanism, just backing up the one shared .accdb (there's no
    separate Electrical-only file to back up here the way there's a
    separate Electrical_Inspection_Tracker.xlsx on the Excel edition -
    Instrumentation and Electrical share one database). Collision-safe
    (a '-2', '-3', ... suffix on a same-second repeat) - see
    access_data_access.py's own identical backup_now() docstring for why
    this matters here specifically (restore_backup() below calls this a
    second time, often within the same second, for its own safety
    snapshot)."""
    import shutil
    ELECTRICAL_BACKUPS_DIR.mkdir(exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = ELECTRICAL_BACKUPS_DIR / f"SenseiIndex.{stamp}.accdb"
    n = 2
    while dest.exists():
        dest = ELECTRICAL_BACKUPS_DIR / f"SenseiIndex.{stamp}-{n}.accdb"
        n += 1
    shutil.copy(str(db.DB_PATH), str(dest))
    return dest
