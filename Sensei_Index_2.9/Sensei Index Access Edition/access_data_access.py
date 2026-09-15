# -*- coding: utf-8 -*-
"""
Access Edition's Instrumentation data-access module - a drop-in
replacement for data_access.py's own call surface, backed by
SenseiIndex.accdb instead of Equipment_Inspection_Tracker.xlsx.

Structurally identical to access_electrical_data_access.py - "series"
instead of "zones" - see that module's own docstring for the shared
reasoning (why every function takes no explicit connection argument,
why the export modules/compute_progress/tag_shape_warning/master_list_
reader are imported and reused rather than re-implemented, and why
find_first_blank_row() keeps its old name despite there being no
"blank row" concept left to find).
"""
import datetime
import os
import re
import subprocess
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
from data_access import (  # noqa: F401
    compute_progress, tag_shape_warning, write_json_atomic, read_json_with_recovery,
    write_progress_report_xlsx, PROGRESS_MILESTONES, FLAG_LABELS,
)
# EQUIPMENT_TYPES itself is ALSO reused directly, not derived from
# access_schema.py's DOMAIN_TABLES - that registry (label/schema/
# export_module/key_field/summary_fields/summary_labels/group_fields/
# group_labels/date_fields/date_labels) was never Excel-specific to
# begin with, it's pure metadata gui_app.py's own UI reads straight off
# (column headers, grouping, date formatting) - importing the real one
# guarantees this edition's index pages/grouping/date columns can never
# drift from the Excel edition's. access_schema.py's own DOMAIN_TABLES
# entries stay in play too, as _DB_TABLES below, purely for the two
# things they know that the real registry doesn't: the Access table
# name and the full field-id list (both come from the *_schema.py
# LOG_COLUMNS, same as ever).
from data_access import EQUIPMENT_TYPES  # noqa: F401
import master_list_reader
from master_list_reader import canonical_tag, parse_area_code  # noqa: F401

import export_to_pdf
import export_valve_to_pdf

_EXPORT_MODULES = {
    "transmitter": export_to_pdf,
    "valve": export_valve_to_pdf,
}

DOMAIN = "instrumentation"
PARENT_TABLE = "Series"
PARENT_NAME_COLUMN = "display_name"

_DB_TABLES = DOMAIN_TABLES["instrumentation"]  # equip_key -> table_name/fields (DB layer only, see above)

TEMP_DIR = HERE / "temp_previews"
OUTPUT_DIR = HERE / "output_pdfs"
BACKUPS_DIR = HERE / "backups"
ASSETS_DIR = HERE.parent / "Sensei Index 2.9" / "assets"  # shared with the Excel edition - see docstring below
WORKBOOK_PATH = db.DB_PATH  # "the workbook" -> "the database" for this edition - see open_workbook() below

MASTER_LIST_PATH = HERE / "master_list.json"
DRAFTS_PATH = HERE / "wizard_draft.json"
UI_STATE_PATH = HERE / "ui_state.json"

SERIAL_FIELD_BY_KIND = {"transmitter": "serial_number", "valve": "valve_serial"}

SIGNATURE_EXTENSIONS = {".png", ".jpg", ".jpeg"}


class WorkbookLockedError(Exception):
    """Kept for gui_app.py's own `except da.WorkbookLockedError:` blocks -
    see access_electrical_data_access.py's own identical class for why
    this is never actually raised here (Access's own file locking is
    handled by the ACE engine itself, not pre-checked by this app)."""


def _table_name(equip_key):
    return _DB_TABLES[equip_key]["table_name"]


def _key_field(equip_key):
    return _DB_TABLES[equip_key]["key_field"]


def _field_map(equip_key):
    return {f["id"]: f["id"] for f in _DB_TABLES[equip_key]["fields"]}


# ------------------------------------------------------------------- Series

def list_series():
    conn = db.get_cached_connection()
    rows = db.list_parents(conn, PARENT_TABLE, "series_number")
    return [r["series_number"] for r in rows]


def _get_series_row(series_number):
    conn = db.get_cached_connection()
    cursor = conn.cursor()
    cursor.execute(f"SELECT * FROM [{PARENT_TABLE}] WHERE series_number = ?", [series_number])
    row = cursor.fetchone()
    if row is None:
        return None
    return {desc[0]: value for desc, value in zip(cursor.description, row)}


def get_series_id(series_number):
    row = _get_series_row(series_number)
    if row is None:
        raise KeyError(f"No series numbered {series_number!r}")
    return row["id"]


def add_series(new_number, source_number=None):
    """source_number is accepted for call-signature compatibility with
    data_access.py's own add_series() (used there to copy a display name
    from an existing series when splitting one series into two) - copied
    here too when given."""
    conn = db.get_cached_connection()
    existing = _get_series_row(new_number)
    if existing is not None:
        return existing["id"]
    display_name = str(new_number)
    if source_number is not None:
        src = _get_series_row(source_number)
        if src is not None:
            display_name = src.get("display_name") or display_name
    new_id = db.insert_row(conn, PARENT_TABLE, {
        "series_number": new_number, "display_name": display_name, "created_at": db.now_str(),
    })
    db.log_activity(conn, "add_series", domain=DOMAIN, parent_label=str(new_number), row_id=new_id)
    return new_id


def get_series_name(series_number):
    row = _get_series_row(series_number)
    if row is None:
        return None
    name = row.get("display_name") or ""
    return name if name != str(series_number) else None


def set_series_name(series_number, name):
    conn = db.get_cached_connection()
    row = _get_series_row(series_number)
    if row is None:
        raise KeyError(f"No series numbered {series_number!r}")
    db.update_row(conn, PARENT_TABLE, row["id"], {"display_name": name or str(series_number)})


def series_display_label(series_number):
    row = _get_series_row(series_number)
    if row is None:
        return str(series_number)
    return row.get("display_name") or str(series_number)


def get_sheet_name(series_number, equip_key):
    """data_access.py's own get_sheet_name() answers "does series_number
    have a <equip_key> tab yet, and if so what's it called" - a real
    question in the Excel edition, where each series/equip_key pair gets
    its own worksheet lazily, only once something's actually entered for
    it. This edition's tables are shared (one Transmitter table for
    every series, with a series_id column), so there's no per-pair
    "hasn't been created yet" state to report - as long as the series
    itself is registered, every equipment kind is always available for
    it. Kept only for gui_app.py's own call sites (the Excel Sheets
    menu's "does this combo exist" filter, and the Settings page's
    workbook-name label) - raises KeyError under the same two
    conditions data_access.py's own version does (unknown series,
    unknown equip_key), so those call sites still filter/report
    correctly; when both are known it always succeeds, returning a
    sheet-name-shaped label rather than a real worksheet name."""
    if _get_series_row(series_number) is None:
        raise KeyError(f"Series {series_number} is not in the database.")
    if equip_key not in EQUIPMENT_TYPES:
        raise KeyError(f"Unknown equipment kind {equip_key!r}.")
    return f"{_table_name(equip_key)} (Series {series_number})"


def remove_series(series_number):
    """Genuinely deletes the Series row and every equipment row under it
    (real relational delete) - see access_electrical_data_access.py's
    own remove_zone() for why this differs from the Excel edition's own
    archive-by-hiding-a-sheet approach. The confirm-by-typing-the-number
    dialog stays a access_gui_app.py concern, same as gui_app.py."""
    conn = db.get_cached_connection()
    row = _get_series_row(series_number)
    if row is None:
        raise KeyError(f"No series numbered {series_number!r}")
    series_id = row["id"]
    for equip_key in EQUIPMENT_TYPES:
        rows = db.list_rows(conn, _table_name(equip_key), parent_field="series_id", parent_id=series_id)
        if rows:
            db.delete_rows(conn, _table_name(equip_key), [r["id"] for r in rows])
    db.delete_rows(conn, PARENT_TABLE, [series_id])
    db.log_activity(conn, "remove_series", domain=DOMAIN, parent_label=str(series_number))


def register_existing_series(new_number, transmitter_sheet, valve_sheet):
    """No "sheet name" concept for a real database - kept as a no-op
    compatibility shim only so gui_app.py's own call site (an advanced/
    rarely-used recovery path for a workbook whose sheets already exist
    under nonstandard names) doesn't crash outright; just registers the
    series the normal way."""
    return add_series(new_number)


# -------------------------------------------------------------------- Rows

def read_index_rows(series_number, equip_key):
    conn = db.get_cached_connection()
    series_id = get_series_id(series_number)
    rows = db.list_rows(conn, _table_name(equip_key), parent_field="series_id", parent_id=series_id)
    key_field = _key_field(equip_key)
    out = []
    for r in rows:
        if not (r.get(key_field) or "").strip():
            continue
        r["row"] = r["id"]
        out.append(r)
    return out


def read_index_rows_with_status(series_number, equip_key):
    conn = db.get_cached_connection()
    key_field = _key_field(equip_key)
    rows = read_index_rows(series_number, equip_key)
    for entry in rows:
        status = db.get_status(conn, DOMAIN, equip_key, entry.get(key_field, ""))
        entry["installed"] = status["installed"]
        entry["submitted"] = status["submitted"]
        entry["accepted"] = status["accepted"]
        entry["export"] = status["export"]
    return rows


def read_index_rows_filtered(series_number, equip_key, filters=None):
    rows = read_index_rows_with_status(series_number, equip_key)
    if filters:
        for fid, val in filters.items():
            rows = [r for r in rows if str(r.get(fid) or "") == str(val)]
    return rows


def read_index_rows_with_progress(series_number, equip_key, filters=None):
    rows = read_index_rows_with_status(series_number, equip_key)
    for entry in rows:
        entry["progress"] = compute_progress(equip_key, entry, entry)
    if filters:
        for fid, val in filters.items():
            rows = [r for r in rows if str(r.get(fid) or "") == str(val)]
    return rows


def read_full_row(series_number, equip_key, row_id):
    conn = db.get_cached_connection()
    row = db.get_row(conn, _table_name(equip_key), row_id)
    if row is None:
        raise KeyError(f"No row {row_id} in {equip_key}")
    return {k: (v if v is not None else "") for k, v in row.items()}


def find_first_blank_row(series_number, equip_key):
    conn = db.get_cached_connection()
    series_id = get_series_id(series_number)
    return db.insert_row(conn, _table_name(equip_key), {"series_id": series_id, "created_at": db.now_str()})


def save_row(series_number, equip_key, row_id, values, source="edit_dialog"):
    conn = db.get_cached_connection()
    values = dict(values)
    values["updated_at"] = db.now_str()
    db.update_row(conn, _table_name(equip_key), row_id, values)
    key_field = _key_field(equip_key)
    db.log_activity(conn, "save_row", domain=DOMAIN, equip_key=equip_key, parent_label=str(series_number),
                     row_id=row_id, key_value=values.get(key_field), source=source)


def save_fields_bulk(series_number, equip_key, updates, source="bulk"):
    """updates: {row_id: {field_id: value}} - one save_row() per row, one
    shared timestamp for the whole batch (matches data_access.py's own
    save_fields_bulk() intent: a single coherent activity-log moment for
    a bulk operation, not N separately-timestamped ones)."""
    ts = db.now_str()
    conn = db.get_cached_connection()
    for row_id, values in updates.items():
        values = dict(values)
        values["updated_at"] = ts
        db.update_row(conn, _table_name(equip_key), row_id, values)
    db.log_activity(conn, "save_fields_bulk", domain=DOMAIN, equip_key=equip_key,
                     parent_label=str(series_number), source=source, ts=ts,
                     note=f"{len(updates)} row(s)")


def delete_rows(series_number, equip_key, row_nums, source="edit_dialog"):
    conn = db.get_cached_connection()
    db.delete_rows(conn, _table_name(equip_key), row_nums)
    db.log_activity(conn, "delete_rows", domain=DOMAIN, equip_key=equip_key, parent_label=str(series_number),
                     source=source, note=f"{len(row_nums)} row(s)")


def find_duplicate_row(series_number, equip_key, key_value, exclude_row=None):
    if not (key_value or "").strip():
        return None
    conn = db.get_cached_connection()
    series_id = get_series_id(series_number)
    matches = db.find_by_field(conn, _table_name(equip_key), _key_field(equip_key), key_value,
                                parent_field="series_id", parent_id=series_id, exclude_id=exclude_row)
    return matches[0] if matches else None


def find_rows_with_duplicate_serial(equip_key, serial_value, exclude_series_row=None):
    field = SERIAL_FIELD_BY_KIND.get(equip_key)
    if not field:
        return []
    target = re.sub(r"\s+", "", str(serial_value or "")).casefold()
    if not target:
        return []
    key_field = _key_field(equip_key)
    matches = []
    for series_number in list_series():
        for row in read_index_rows(series_number, equip_key):
            if exclude_series_row == (series_number, row["id"]):
                continue
            if re.sub(r"\s+", "", str(row.get(field) or "")).casefold() != target:
                continue
            key_val = row.get(key_field, "")
            if key_val:
                matches.append({"series": series_number, "row": row["id"], "key_value": key_val})
    return matches


def count_rows(series_number, equip_key):
    return len(read_index_rows(series_number, equip_key))


def count_all_by_type(series_number=None):
    """data_access.py's own count_all_by_type() takes NO arguments at
    all - it's a global count across every series, unlike
    electrical_data_access.py's own zone-scoped equivalent. series_number
    is accepted (and ignored) only so a caller that passes one by
    mistake doesn't crash; the real per-series version is
    series_full_summary()."""
    totals = {k: 0 for k in EQUIPMENT_TYPES}
    for series_number in list_series():
        for equip_key in EQUIPMENT_TYPES:
            totals[equip_key] += count_rows(series_number, equip_key)
    return totals


def count_by_system_all_series(equip_key):
    etype = EQUIPMENT_TYPES[equip_key]
    system_field = (etype.get("group_fields") or [None])[0]
    if not system_field:
        return {}
    combined = {}
    unset = 0
    for series_number in list_series():
        for entry in read_index_rows(series_number, equip_key):
            value = str(entry.get(system_field) or "").strip()
            if value:
                combined[value] = combined.get(value, 0) + 1
            else:
                unset += 1
    result = dict(sorted(combined.items(), key=lambda kv: -kv[1]))
    if unset:
        result["(No System Set)"] = unset
    return result


def series_type_summary(series_number, equip_key, group_field):
    """(count, {group_value: count}) - same shape data_access.py's own
    series_type_summary() returns (the sidebar tree unpacks both, so
    this can't just return the counts dict on its own - caught the hard
    way, via a real MainWindow smoke test, since no automated test
    exercises the sidebar-building code directly)."""
    rows = read_index_rows(series_number, equip_key)
    counts = {}
    for entry in rows:
        value = str(entry.get(group_field) or "").strip()
        if value:
            counts[value] = counts.get(value, 0) + 1
    return len(rows), dict(sorted(counts.items()))


def series_full_summary(series_number):
    result = {}
    for equip_key in EQUIPMENT_TYPES:
        try:
            rows = read_index_rows_with_status(series_number, equip_key)
        except KeyError:
            continue
        result[equip_key] = {
            "total": len(rows),
            "installed": sum(1 for r in rows if r.get("installed")),
            "submitted": sum(1 for r in rows if r.get("submitted")),
            "accepted": sum(1 for r in rows if r.get("accepted")),
        }
    return result


def series_progress_summary(series_number):
    """{'transmitter': {'avg_percent', 'at_0', 'partial', 'at_100'}, ...} -
    same shape data_access.py's own series_progress_summary() returns
    (the Dashboard's SeriesStatCard unpacks all four keys to draw its
    segmented progress bar - caught via a real MainWindow smoke test,
    same as series_type_summary()'s own fix above)."""
    result = {}
    for equip_key in EQUIPMENT_TYPES:
        rows = read_index_rows_with_progress(series_number, equip_key)
        if not rows:
            result[equip_key] = {"avg_percent": 0, "at_0": 0, "partial": 0, "at_100": 0}
            continue
        percents = [r["progress"]["percent"] for r in rows]
        result[equip_key] = {
            "avg_percent": round(sum(percents) / len(percents)),
            "at_0": sum(1 for p in percents if p == 0),
            "partial": sum(1 for p in percents if 0 < p < 100),
            "at_100": sum(1 for p in percents if p == 100),
        }
    return result


# ---------------------------------------------------------------- PDF export

def generate_preview_pdf(series_number, equip_key, row_id):
    row = read_full_row(series_number, equip_key, row_id)
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


def run_export(series_number, equip_key, mode, suffix, flatten, include_signature,
                subfolder=None, merge=False, filters=None, clear_after_selected=True,
                include_date_in_filename=False):
    """Same mode/kwarg shape as data_access.py's own run_export()."""
    from pypdf import PdfReader, PdfWriter

    conn = db.get_cached_connection()
    export_mod = _EXPORT_MODULES[equip_key]
    field_map = _field_map(equip_key)
    key_field = _key_field(equip_key)

    out_dir = OUTPUT_DIR
    if subfolder:
        safe_sub = re.sub(r'[<>:"/\\|?*]', "_", subfolder).strip()
        if safe_sub:
            out_dir = out_dir / safe_sub
    out_dir.mkdir(parents=True, exist_ok=True)

    if mode == "flagged":
        rows = [r for r in read_index_rows(series_number, equip_key) if r.get("export_flag") == "Y"]
    elif mode == "selected":
        rows = [r for r in read_index_rows_with_status(series_number, equip_key) if r.get("export")]
    else:
        rows = read_index_rows(series_number, equip_key)
    if filters:
        for fid, val in filters.items():
            rows = [r for r in rows if str(r.get(fid) or "") == str(val)]
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
        try:
            export_mod.fill_pdf(export_mod.DEFAULT_TEMPLATE, values, out_path,
                                 flatten=flatten, add_signature=include_signature)
        except TypeError:
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

    db.log_activity(conn, "run_export", domain=DOMAIN, equip_key=equip_key, parent_label=str(series_number),
                     note=f"{len(rows)} row(s), mode={mode}")
    return written


# ------------------------------------------------------------------- Status

def get_status(series_number, equip_key, key_value):
    conn = db.get_cached_connection()
    return db.get_status(conn, DOMAIN, equip_key, key_value)


def set_status(series_number, equip_key, key_value, source="app", **fields):
    conn = db.get_cached_connection()
    db.set_status(conn, DOMAIN, equip_key, key_value, **fields)


def bulk_set_status(keys, source="bulk", **fields):
    conn = db.get_cached_connection()
    db.bulk_set_status(conn, DOMAIN, keys, **fields)


def rename_status_key(series_number, equip_key, old_key, new_key):
    conn = db.get_cached_connection()
    db.rename_status_key(conn, DOMAIN, equip_key, old_key, new_key)


# -------------------------------------------------------------- Activity log

def log_activity(action, series=None, equip_key=None, row=None, key_value=None,
                  fields=None, source="app", note=None, ts=None):
    conn = db.get_cached_connection()
    db.log_activity(conn, action, domain=DOMAIN, equip_key=equip_key,
                     parent_label=str(series) if series is not None else None,
                     row_id=row, key_value=key_value, fields=fields, source=source, note=note, ts=ts)


def read_activity_log(limit=None, series=None, equip_key=None, row=None):
    conn = db.get_cached_connection()
    return db.read_activity_log(conn, limit=limit, domain=DOMAIN, equip_key=equip_key, row_id=row)


def read_row_history(series_number, equip_key, row_num, key_value=None, limit=None):
    """Every activity-log entry for this exact row - a thin filter over
    read_activity_log(), same relationship as data_access.py's own
    read_row_history()."""
    entries = read_activity_log(limit=None, series=series_number, equip_key=equip_key, row=row_num)
    if limit:
        entries = entries[:limit]
    return entries


# ---------------------------------------------------------------- Settings

def load_settings():
    conn = db.get_cached_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT setting_key, setting_value FROM [Settings]")
    return {row[0]: row[1] for row in cursor.fetchall()}


def get_setting(key):
    conn = db.get_cached_connection()
    return db.get_setting(conn, key)


def set_setting(key, value):
    conn = db.get_cached_connection()
    db.set_setting(conn, key, value)


# --------------------------------------------------------------- Signatures
# The actual image FILES live in the Excel edition's own assets/ folder,
# shared on purpose - export_to_pdf.py/export_valve_to_pdf.py and every
# Electrical export module all resolve their own SIGNATURE_IMAGE relative
# to THEIR OWN file's location (the Excel edition folder), regardless of
# which edition imported them - see access_electrical_data_access.py's
# own docstring for why those modules are reused unmodified. A signature
# added from either edition is instantly usable from both.

def list_signatures():
    ASSETS_DIR.mkdir(exist_ok=True)
    return sorted(p.name for p in ASSETS_DIR.iterdir() if p.suffix.lower() in SIGNATURE_EXTENSIONS)


def add_signature(source_path, display_name):
    import shutil
    source_path = Path(source_path)
    if not source_path.exists():
        raise FileNotFoundError(f"Can't find {source_path}")
    ext = source_path.suffix.lower()
    if ext not in SIGNATURE_EXTENSIONS:
        raise ValueError("Signature file must be a .png, .jpg, or .jpeg image.")
    try:
        from reportlab.lib.utils import ImageReader
        ImageReader(str(source_path))
    except Exception as exc:
        raise ValueError(f"That file doesn't look like a valid image ({exc}).") from exc

    safe_name = re.sub(r"[^A-Za-z0-9_\- ]+", "", display_name).strip() or "signature"
    ASSETS_DIR.mkdir(exist_ok=True)
    filename = f"{safe_name}{ext}"
    dest = ASSETS_DIR / filename
    n = 2
    while dest.exists():
        filename = f"{safe_name} ({n}){ext}"
        dest = ASSETS_DIR / filename
        n += 1
    shutil.copy(str(source_path), str(dest))
    if not get_setting("active_signature") or get_active_signature_path() is None:
        set_setting("active_signature", filename)
    return filename


def delete_signature(filename):
    path = ASSETS_DIR / filename
    if path.exists():
        path.unlink()
    if get_setting("active_signature") == filename:
        remaining = list_signatures()
        set_setting("active_signature", remaining[0] if remaining else "")


def get_active_signature_path():
    active = get_setting("active_signature")
    if not active:
        return None
    path = ASSETS_DIR / active
    return path if path.exists() else None


def set_active_signature(filename):
    set_setting("active_signature", filename)


def _apply_active_signature(export_mod):
    active_path = get_active_signature_path()
    if active_path is not None:
        export_mod.SIGNATURE_IMAGE = active_path


# ------------------------------------------------------- Populating Wizard

def load_wizard_draft():
    return read_json_with_recovery(DRAFTS_PATH, None)


def save_wizard_draft(data):
    write_json_atomic(DRAFTS_PATH, data)


def clear_wizard_draft():
    try:
        DRAFTS_PATH.unlink()
    except FileNotFoundError:
        pass


# --------------------------------------------------------- Master List import
# master_list.json is a normalized snapshot of the last-imported external
# Instrumentation Master List spreadsheet - read-only reference data,
# same file shape/meaning as the Excel edition's own (just its own
# separate copy, next to THIS edition's own app). Parsing that external
# file is handled entirely by master_list_reader.py, imported directly -
# it never depended on OUR OWN storage being Excel in the first place.

def load_master_list():
    return read_json_with_recovery(MASTER_LIST_PATH, None)


def save_master_list(data):
    write_json_atomic(MASTER_LIST_PATH, data)


def preview_master_list(path):
    return master_list_reader.read_master_list_file(path)


def guess_master_list_series_mapping(sheet_names):
    return master_list_reader.guess_series_mapping(sheet_names, list_series())


def import_master_list(path, sheet_series_map):
    items_by_sheet, summaries = master_list_reader.read_master_list_file(path)
    items = []
    for sheet_name, sheet_items in items_by_sheet.items():
        mapped_series = sheet_series_map.get(sheet_name)
        for item in sheet_items:
            item = dict(item)
            item["mapped_series"] = mapped_series
            items.append(item)

    source_path = Path(path)
    snapshot = {
        "imported_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "source_file": source_path.name,
        "source_mtime": source_path.stat().st_mtime,
        "sheet_series_map": dict(sheet_series_map),
        "items": items,
    }
    save_master_list(snapshot)
    set_setting("master_list_path", str(source_path))
    log_activity("master_list_import", source="master_list",
                 note=f"Imported {len(items)} row(s) from {source_path.name}")
    return snapshot, summaries


def master_list_items(kind=None, area=None, series=None):
    snapshot = load_master_list()
    if not snapshot:
        return []
    items = snapshot.get("items", [])
    if kind is not None:
        items = [it for it in items if it.get("kind") == kind]
    if area is not None:
        items = [it for it in items if it.get("area") == area]
    if series is not None:
        items = [it for it in items if it.get("mapped_series") == series]
    return items


def master_list_needs_reimport():
    remembered_path = get_setting("master_list_path")
    if not remembered_path:
        return False
    source_path = Path(remembered_path)
    if not source_path.exists():
        return False
    snapshot = load_master_list()
    if not snapshot:
        return False
    try:
        return source_path.stat().st_mtime > snapshot.get("source_mtime", 0)
    except OSError:
        return False


def _normalize_for_compare(value):
    return re.sub(r"\s+", "", str(value or "")).casefold()


def _tracker_refs_by_tag(equip_key):
    key_field = _key_field(equip_key)
    refs = {}
    for series_number in list_series():
        for entry in read_index_rows_with_status(series_number, equip_key):
            tag = canonical_tag(entry.get(key_field, ""))
            if not tag or tag in refs:
                continue
            refs[tag] = {
                "series": series_number, "equip_key": equip_key, "row": entry["row"],
                "key_value": entry.get(key_field, ""), "installed": bool(entry.get("installed")),
                "submitted": bool(entry.get("submitted")), "accepted": bool(entry.get("accepted")),
            }
    return refs


def reconcile_master_list():
    snapshot = load_master_list()
    if not snapshot:
        return None

    tracker_refs = {equip_key: _tracker_refs_by_tag(equip_key) for equip_key in EQUIPMENT_TYPES}
    matched_tags = {equip_key: set() for equip_key in EQUIPMENT_TYPES}
    matched, missing, out_of_scope_items = [], [], []

    for item in snapshot.get("items", []):
        kind = item.get("kind")
        if kind not in EQUIPMENT_TYPES:
            out_of_scope_items.append(item)
            continue
        ref = tracker_refs[kind].get(item["tag"])
        if ref is None:
            missing.append(item)
            continue
        matched_tags[kind].add(item["tag"])
        flags = []
        if bool(item.get("ml_installed")) != ref["installed"]:
            flags.append("installed_mismatch")
        tracker_values = read_full_row(ref["series"], kind, ref["row"])
        model_field = "model" if kind == "transmitter" else "valve_model"
        tracker_model = tracker_values.get(model_field, "")
        master_model = item.get("model", "")
        if (master_model and tracker_model
                and _normalize_for_compare(master_model) != _normalize_for_compare(tracker_model)):
            flags.append("model_mismatch")
        progress = compute_progress(kind, tracker_values, ref)
        matched.append({"master": item, "tracker": ref, "flags": flags, "progress": progress})

    orphans = [
        ref for equip_key, refs_by_tag in tracker_refs.items()
        for tag, ref in refs_by_tag.items() if tag not in matched_tags[equip_key]
    ]

    return {
        "matched": matched, "missing": missing, "orphans": orphans,
        "out_of_scope_count": len(out_of_scope_items), "out_of_scope_items": out_of_scope_items,
    }


def master_item_to_row_values(item, equip_key):
    qa_name = get_setting("default_qa_rep_name")
    if equip_key == "valve":
        values = {
            "equip_number": item.get("tag", ""), "pid_number": item.get("pid", ""),
            "line_number": item.get("line_number", ""), "valve_model": item.get("model", ""),
        }
        if qa_name:
            values["qc_rep_name"] = qa_name
    else:
        values = {
            "tag": item.get("tag", ""), "service": item.get("service", ""),
            "pid_number": item.get("pid", ""), "line_number": item.get("line_number", ""),
            "make": item.get("manufacturer", ""), "model": item.get("model", ""),
        }
        if qa_name:
            values["yanda_qa_name"] = qa_name
    return {k: v for k, v in values.items() if v}


def create_rows_from_master_items(items_with_kind):
    """items_with_kind: [(equip_key, master_item), ...]. Creates one new
    row per entry, grouped by which series each item's own mapped_series
    targets - unmapped items (mapped_series is None) are skipped, same
    as data_access.py's own convention (a caller maps every sheet before
    offering Create-from-master)."""
    created = 0
    for equip_key, item in items_with_kind:
        series_number = item.get("mapped_series")
        if series_number is None:
            continue
        row_id = find_first_blank_row(series_number, equip_key)
        values = master_item_to_row_values(item, equip_key)
        save_row(series_number, equip_key, row_id, values, source="master_list_create")
        created += 1
    return created


# ------------------------------------------------------- Page view state

def _page_key(series_number, equip_key):
    return f"{series_number}:{equip_key}"


def get_page_view_state(series_number, equip_key):
    state = read_json_with_recovery(UI_STATE_PATH, dict)
    return state.get(_page_key(series_number, equip_key), {})


def set_page_view_state(series_number, equip_key, **fields):
    state = read_json_with_recovery(UI_STATE_PATH, dict)
    key = _page_key(series_number, equip_key)
    state[key] = {**state.get(key, {}), **fields}
    write_json_atomic(UI_STATE_PATH, state)


# --------------------------------------------------------------- Search

def search_index(query, limit=50):
    """A straightforward in-memory scan across every series/kind/row's
    own key field + summary_fields - good enough at this dataset's real
    scale (hundreds to low thousands of rows, not millions). Unlike
    data_access.py's own search_index(), there's no separate persisted
    index to build/invalidate - a real database has no "re-parse the
    whole workbook" cost to amortize away in the first place."""
    query = (query or "").strip().casefold()
    if not query:
        return []
    results = []
    for series_number in list_series():
        for equip_key, etype in EQUIPMENT_TYPES.items():
            fields_to_check = [etype["key_field"]] + list(etype.get("summary_fields", []))
            for row in read_index_rows(series_number, equip_key):
                haystack = " ".join(str(row.get(f, "")) for f in fields_to_check).casefold()
                if query in haystack:
                    results.append({
                        "series": series_number, "equip_key": equip_key, "row": row["id"],
                        "key_value": row.get(etype["key_field"], ""),
                    })
                    if len(results) >= limit:
                        return results
    return results


# --------------------------------------------------------------- Reports

def find_all_duplicate_serials(equip_key):
    """Every group of 2+ rows (across ALL registered series) sharing the
    same primary serial value for this kind - the whole-tracker version
    of find_rows_with_duplicate_serial()'s single-value check, used by
    the progress report and cleanup plan's own Flags output below.
    Mirrors data_access.py's own find_all_duplicate_serials() one-for-
    one, just reading rows through this module's own read_index_rows()
    (already plain dicts) instead of a worksheet's column map."""
    field = SERIAL_FIELD_BY_KIND.get(equip_key)
    if not field:
        return []
    key_field = _key_field(equip_key)
    by_serial = {}
    for series_number in list_series():
        for row in read_index_rows(series_number, equip_key):
            serial = re.sub(r"\s+", "", str(row.get(field) or "")).casefold()
            if not serial:
                continue
            key_val = row.get(key_field, "")
            if not key_val:
                continue
            by_serial.setdefault(serial, []).append(
                {"series": series_number, "row": row["id"], "key_value": key_val})
    return [{"serial": serial, "rows": rows} for serial, rows in by_serial.items() if len(rows) >= 2]


def build_progress_report_data():
    """Same {'has_master_list', 'summary', 'missing', 'flags'} shape as
    data_access.py's own build_progress_report_data() - see that
    function's own docstring for the exact summary-row semantics
    (master-list-reconciled vs. tracker-only degrade). Not imported
    directly because it's not actually pure - it calls list_series()/
    EQUIPMENT_TYPES/read_index_rows_with_progress()/etc. as free
    functions off data_access.py's own Excel-backed module, not as
    parameters, so it always reads the Excel tracker no matter which
    edition calls it. Re-implemented here calling this module's OWN
    same-named functions instead - the two can never disagree about
    what a milestone or a flag means, since PROGRESS_MILESTONES/
    FLAG_LABELS/tag_shape_warning are the same imported constants/
    functions either way."""
    snapshot = load_master_list()
    reconciliation = reconcile_master_list() if snapshot else None

    summary = []
    missing = []
    flags = []

    if reconciliation:
        groups = {}
        for pair in reconciliation["matched"]:
            item = pair["master"]
            groups.setdefault((item["area"], item["kind"]), {"matched": [], "missing": []})
            groups[(item["area"], item["kind"])]["matched"].append(pair)
        for item in reconciliation["missing"]:
            groups.setdefault((item["area"], item["kind"]), {"matched": [], "missing": []})
            groups[(item["area"], item["kind"])]["missing"].append(item)

        for (area, kind), bucket in sorted(groups.items()):
            matched, miss = bucket["matched"], bucket["missing"]
            total = len(matched) + len(miss)
            milestone_counts = {mid: 0 for mid, _label in PROGRESS_MILESTONES}
            percents = []
            for pair in matched:
                percents.append(pair["progress"]["percent"])
                for m in pair["progress"]["milestones"]:
                    if m["done"]:
                        milestone_counts[m["id"]] += 1
            summary.append({
                "area": area, "kind": kind, "total_in_scope": total,
                "created": milestone_counts["created"],
                "serials_captured": milestone_counts["serial_captured"],
                "installed": milestone_counts["installed"],
                "inspection_complete": milestone_counts["inspection_complete"],
                "submitted": milestone_counts["submitted"],
                "accepted": milestone_counts["accepted"],
                "avg_percent": round(sum(percents) / len(percents)) if percents else 0,
            })

        for item in reconciliation["missing"]:
            missing.append({
                "tag": item["tag"], "service": item.get("service", ""),
                "type_desc": item.get("type_desc", ""), "sheet": item.get("source_sheet", ""),
            })

        for pair in reconciliation["matched"]:
            if pair["flags"]:
                flags.append({
                    "tag": pair["master"]["tag"], "kind": pair["master"]["kind"],
                    "detail": "; ".join(FLAG_LABELS.get(f, f) for f in pair["flags"]),
                })
    else:
        for series_number in list_series():
            for equip_key, etype in EQUIPMENT_TYPES.items():
                rows = read_index_rows_with_progress(series_number, equip_key)
                if not rows:
                    continue
                milestone_counts = {mid: 0 for mid, _label in PROGRESS_MILESTONES}
                percents = []
                for entry in rows:
                    percents.append(entry["progress"]["percent"])
                    for m in entry["progress"]["milestones"]:
                        if m["done"]:
                            milestone_counts[m["id"]] += 1
                summary.append({
                    "area": f"{series_display_label(series_number)} (tracker only)", "kind": equip_key,
                    "total_in_scope": len(rows),
                    "created": milestone_counts["created"],
                    "serials_captured": milestone_counts["serial_captured"],
                    "installed": milestone_counts["installed"],
                    "inspection_complete": milestone_counts["inspection_complete"],
                    "submitted": milestone_counts["submitted"],
                    "accepted": milestone_counts["accepted"],
                    "avg_percent": round(sum(percents) / len(percents)) if percents else 0,
                })

    for equip_key, etype in EQUIPMENT_TYPES.items():
        key_field = etype["key_field"]
        for series_number in list_series():
            for r in read_index_rows(series_number, equip_key):
                key_val = r.get(key_field, "")
                warning = tag_shape_warning(key_val)
                if warning:
                    flags.append({"tag": key_val, "kind": equip_key, "detail": warning})
        for group in find_all_duplicate_serials(equip_key):
            tags = ", ".join(f"{row['key_value']} (series {row['series']})" for row in group["rows"])
            flags.append({
                "tag": tags, "kind": equip_key,
                "detail": f"Duplicate serial \"{group['serial']}\"",
            })

    return {"has_master_list": bool(snapshot), "summary": summary, "missing": missing, "flags": flags}


REPORTS_DIR = HERE / "reports"


def export_progress_report():
    """Builds the report and saves it to reports/Progress_Report_<date>.
    xlsx next to the database - same filename pattern and same
    write_progress_report_xlsx() renderer data_access.py's own version
    uses (that renderer is pure - {data, out_path} in, workbook out -
    so it's imported and reused directly, not re-implemented)."""
    data = build_progress_report_data()
    stamp = datetime.date.today().isoformat()
    out_path = REPORTS_DIR / f"Progress_Report_{stamp}.xlsx"
    n = 2
    while out_path.exists():
        out_path = REPORTS_DIR / f"Progress_Report_{stamp}-{n}.xlsx"
        n += 1
    return write_progress_report_xlsx(data, out_path)


# ---------------------------------------------------------- Cleaned copy
#
# data_access.py's own version copies the live .xlsx (shutil.copy2) and
# fixes cell values in place on that copy, preserving every data-
# validation/conditional-formatting rule a re-saved openpyxl workbook
# can't reliably reproduce. The Access equivalent of "never touch the
# live file, only a copy" is the same shutil.copy2() trick applied to
# SenseiIndex.accdb itself, then opening THAT COPY through its own
# separate pyodbc connection (never the cached live one - see
# access_db.py's own get_cached_connection()) to apply fixes and append
# a CleanupLog table. Same two-bucket split as the Excel edition: fixed
# automatically (whitespace trim + key-field upper-case) vs. flagged,
# never touched (duplicate serial / tag shape warning).
# ---------------------------------------------------------------------------
CLEANED_DIR = HERE / "cleaned"


def build_cleanup_plan():
    """Dry-run over the live database (read-only) - {'fixes': [...],
    'flags': [...]}. Safe to call any time, including just to preview
    what a cleanup would find. Fixes only ever touch a field that's
    already a plain str (same reasoning data_access.py's own version
    gives for not touching a numeric/bool/date-typed cell - Access
    columns are typed TEXT(255)/MEMO for exactly the fields that could
    ever hold one, so this is mostly moot here, but the same str-only
    guard is kept for parity and because a truly empty cell reads back
    as None, not ''"""
    fixes = []
    flags = []
    for equip_key, etype in EQUIPMENT_TYPES.items():
        key_field = etype["key_field"]
        date_fields = set(etype.get("date_fields", []))
        field_ids = [f["id"] for f in _DB_TABLES[equip_key]["fields"]]
        for series_number in list_series():
            for row in read_index_rows(series_number, equip_key):
                key_val = row.get(key_field) or ""
                if not str(key_val).strip():
                    continue
                for fid in field_ids:
                    if fid in date_fields:
                        continue
                    raw = row.get(fid)
                    if not isinstance(raw, str):
                        continue
                    old_text = raw
                    new_text = raw.strip()
                    if fid == key_field:
                        new_text = new_text.upper()
                    if new_text != old_text:
                        fixes.append({
                            "equip_key": equip_key, "series": series_number, "row_id": row["id"],
                            "key_value": key_val, "field": fid,
                            "old_text": old_text, "new_text": new_text,
                        })
                warning = tag_shape_warning(key_val)
                if warning:
                    flags.append({
                        "equip_key": equip_key, "tag": key_val, "kind": equip_key, "detail": warning,
                    })
        for group in find_all_duplicate_serials(equip_key):
            tags = ", ".join(f"{row['key_value']} (series {row['series']})" for row in group["rows"])
            flags.append({
                "equip_key": equip_key, "tag": tags, "kind": equip_key,
                "detail": f"Duplicate serial \"{group['serial']}\"",
            })
    return {"fixes": fixes, "flags": flags}


def export_cleaned_workbook():
    """Makes a byte-identical copy of SenseiIndex.accdb, applies the
    cleanup plan's fixes to THAT COPY through a fresh, separate
    connection, and appends a CleanupLog table listing every fix/flag -
    the live database is never opened for writing here at all. Returns
    the path to the copy."""
    import shutil

    plan = build_cleanup_plan()
    CLEANED_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.date.today().isoformat()
    out_path = CLEANED_DIR / f"SenseiIndex_Cleaned_{stamp}.accdb"
    n = 2
    while out_path.exists():
        out_path = CLEANED_DIR / f"SenseiIndex_Cleaned_{stamp}-{n}.accdb"
        n += 1
    shutil.copy2(db.DB_PATH, out_path)

    copy_conn = db.get_connection(out_path)
    try:
        cursor = copy_conn.cursor()
        cursor.execute(
            "CREATE TABLE [CleanupLog] ("
            "[id] COUNTER PRIMARY KEY, [kind] TEXT(20), [equip_key] TEXT(50), "
            "[tag] TEXT(255), [field] TEXT(255), [detail] MEMO)"
        )
        copy_conn.commit()
        for fix in plan["fixes"]:
            db.update_row(copy_conn, _table_name(fix["equip_key"]), fix["row_id"],
                           {fix["field"]: fix["new_text"]})
            cursor.execute(
                "INSERT INTO [CleanupLog] ([kind],[equip_key],[tag],[field],[detail]) "
                "VALUES (?,?,?,?,?)",
                ["fix", fix["equip_key"], fix["key_value"], fix["field"],
                 f"{fix['old_text']!r} -> {fix['new_text']!r}"])
        for flag in plan["flags"]:
            cursor.execute(
                "INSERT INTO [CleanupLog] ([kind],[equip_key],[tag],[field],[detail]) "
                "VALUES (?,?,?,?,?)",
                ["flag", flag["equip_key"], flag["tag"], "", flag["detail"]])
        copy_conn.commit()
    finally:
        copy_conn.close()
    return out_path


# ------------------------------------------------------------- Misc/utility

def read_instructions():
    """No "Instructions" worksheet concept for a real database - returns
    a short static pointer instead of an empty list, since gui_app.py
    shows whatever this returns directly (an empty list there just
    means "no instructions panel shown", which is a worse experience
    than a one-line pointer to the real docs)."""
    return ["See README_ACCESS_EDITION.txt, next to this app, for setup "
            "and usage notes."]


def open_file(path):
    """Opens any file with the OS's own default app - identical to
    data_access.py's own open_file()."""
    path = str(path)
    if os.name == "nt":
        os.startfile(path)  # noqa: S606 - matches data_access.py's own Windows-only behavior
    elif sys.platform == "darwin":
        subprocess.run(["open", path], check=False)
    else:
        subprocess.run(["xdg-open", path], check=False)


def open_workbook():
    """"Open the workbook" -> "open the database" for this edition -
    launches SenseiIndex.accdb in whatever's registered for .accdb
    (normally Access itself, if installed)."""
    open_file(db.DB_PATH)


def open_sheet(series_number, equip_key):
    """No "active tab" concept to jump to in a database the way Excel's
    own sheet-tab metadata works - opens the database itself. See
    access_electrical_data_access.py's own docstring pattern for the
    same adaptation on the Electrical side."""
    open_workbook()


def _shortcut_target_and_args():
    if getattr(sys, "frozen", False):
        return sys.executable, ""
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    target = str(pythonw) if pythonw.exists() else sys.executable
    script = str(HERE / "access_gui_app.py")
    return target, f'"{script}"'


def create_desktop_shortcut(shortcut_name="Sensei Index - Access Edition"):
    if os.name != "nt":
        raise OSError("Desktop shortcuts are only supported on Windows.")
    desktop = Path(os.environ["USERPROFILE"]) / "Desktop"
    if not desktop.exists():
        raise FileNotFoundError(f"Couldn't find your Desktop folder at {desktop}")
    target, arguments = _shortcut_target_and_args()
    shortcut_path = desktop / f"{shortcut_name}.lnk"
    ps_script = (
        "$WshShell = New-Object -ComObject WScript.Shell;"
        f'$Shortcut = $WshShell.CreateShortcut("{shortcut_path}");'
        f'$Shortcut.TargetPath = "{target}";'
        f'$Shortcut.Arguments = \'{arguments}\';'
        f'$Shortcut.WorkingDirectory = "{HERE}";'
        f'$Shortcut.IconLocation = "{target}";'
        "$Shortcut.Save()"
    )
    subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_script],
                    check=True, capture_output=True, text=True)
    return shortcut_path


def _backup_workbook_if_due():
    """No "is a backup overdue" scheduling here yet (the Excel edition's
    own version checks a last-backup timestamp against a due interval) -
    always a no-op; backup_now() below does the real work, callable
    directly from access_gui_app.py's own Settings page the same way
    gui_app.py's own manual "Back Up Now" button already calls
    da.backup_now()."""
    return None


def backup_now():
    """Collision-safe (two backups in the same second get a '-2', '-3',
    ... suffix) - same guarantee data_access.py's own _write_backup_
    snapshot() gives, and needed here for the exact same reason:
    restore_backup() below calls this a second time (for its own safety
    snapshot) within the same second as a caller's first backup_now()
    often enough in practice - a bare timestamp collision would silently
    overwrite the earlier backup instead of writing a new one (caught by
    a regression test that does exactly this, back to back)."""
    import shutil
    BACKUPS_DIR.mkdir(exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = BACKUPS_DIR / f"SenseiIndex.{stamp}.accdb"
    n = 2
    while dest.exists():
        dest = BACKUPS_DIR / f"SenseiIndex.{stamp}-{n}.accdb"
        n += 1
    shutil.copy(str(db.DB_PATH), str(dest))
    return dest


def list_backups():
    """[{'path', 'name', 'mtime', 'size'}, ...], NEWEST first - same
    shape data_access.py's own list_backups() returns (BackupsDialog's
    own _reload() indexes every entry by these 4 keys, not as a Path -
    caught via a real BackupsDialog smoke test, since no automated test
    exercises Settings/Backups UI code directly)."""
    if not BACKUPS_DIR.exists():
        return []
    result = []
    for p in sorted(BACKUPS_DIR.glob("SenseiIndex.*.accdb"), reverse=True):
        try:
            stat = p.stat()
        except OSError:
            continue
        result.append({"path": p, "name": p.name, "mtime": stat.st_mtime, "size": stat.st_size})
    return result


def restore_backup(backup_path):
    """Copies the chosen snapshot over the live .accdb - AFTER taking ONE
    MORE safety snapshot of whatever's currently live (same "restoring
    is itself undoable" guarantee data_access.py's own restore_backup()
    gives), then invalidates the cached connection so the next access
    re-opens the restored file instead of holding a handle to whatever
    was live before this call. Returns the safety snapshot's path (None
    if there was no live database to protect - a restore onto a fresh
    install)."""
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
    BACKUPS_DIR.mkdir(exist_ok=True)
    shutil.copy(str(backup_path), str(db.DB_PATH))
    return safety_snapshot
