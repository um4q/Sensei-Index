# -*- coding: utf-8 -*-
"""
Data-access layer for the Electrical side of the app - EHT Removal &
Reinstatement and EHT & RTD Installation Inspection tracking.

Deliberately independent of data_access.py's Equipment_Inspection_Tracker.
xlsx and series_registry.json: its own workbook
(Electrical_Inspection_Tracker.xlsx) and its own registry
(electrical_registry.json), organized by "Zone" (a free-named area/module,
e.g. "K1B Well Pad") instead of Instrumentation's numbered series -
Electrical's forms don't share Instrumentation's series numbering, and this
was deliberately built to track fully independently of it. gui_app.py never
imports openpyxl directly here either - same rule as data_access.py.

Only the genuinely generic, workbook-agnostic helpers are reused from
data_access.py (HERE, write_json_atomic, read_json_with_recovery,
open_file) - everything that actually touches THIS workbook (the cache,
the mutating choke point, every read/save function) is its own, so nothing
here can ever put Equipment_Inspection_Tracker.xlsx or its sidecars at
risk, and vice versa.

v1 scope, deliberately: core CRUD (add/edit/view rows, add/remove zones),
single-row and mass/batch PDF export (an Export checkbox queue per row,
mirroring data_access.py's own "selected"/"all" batch export - see
run_export() below), mirroring the ORIGINAL Transmitter/Valve system
(pre-Phase-10) rather than every v2.1 refinement Instrumentation has since
grown (master-list reconciliation, global search integration, activity
log, Installed/Submitted/Accepted status tracking, automatic backups,
cleaned-copy export). Those can be added later the same way they were
added for Instrumentation, if wanted.
"""
import datetime
import os
import re
from contextlib import contextmanager
from pathlib import Path

import openpyxl
from pypdf import PdfReader, PdfWriter

from data_access import HERE, write_json_atomic, read_json_with_recovery, open_file  # noqa: F401

import eht_removal_schema
import eht_rtd_schema
import eht_pre_insulation_schema
import export_eht_removal_to_pdf
import export_eht_rtd_to_pdf
import export_eht_pre_insulation_to_pdf

ELECTRICAL_WORKBOOK_PATH = HERE / "Electrical_Inspection_Tracker.xlsx"
ELECTRICAL_CONFIG_PATH = HERE / "electrical_registry.json"
ELECTRICAL_TEMP_DIR = HERE / "electrical_temp_previews"
ELECTRICAL_STATUS_PATH = HERE / "electrical_status.json"
# A dedicated constant, NOT computed inline as `HERE / "output_pdfs"` inside
# run_export() - `HERE` itself is imported BY VALUE from data_access.py, so
# isolated_app_dir's `monkeypatch.setattr(da, "HERE", tmp_path)` does not
# (and cannot) change what this module sees for a bare `HERE` reference.
# Every path that tests need to isolate has to be its own patchable
# module-level name here, same reasoning as ELECTRICAL_WORKBOOK_PATH/
# ELECTRICAL_CONFIG_PATH/ELECTRICAL_TEMP_DIR/ELECTRICAL_STATUS_PATH above.
ELECTRICAL_OUTPUT_DIR = HERE / "output_pdfs"

# ---------------------------------------------------------------------------
# Equipment type registry - the Electrical equivalent of data_access.py's
# EQUIPMENT_TYPES. Every lookup below is generic over this dict, exactly
# like the Instrumentation side, so a third Electrical form later would
# only need one new entry here (plus its own schema/field-map/export
# module trio) - no other code in this file would need to change.
# ---------------------------------------------------------------------------
ELECTRICAL_EQUIPMENT_TYPES = {
    "eht_removal": {
        "label": "EHT Removal & Reinstatement",
        "schema": eht_removal_schema,
        "export_module": export_eht_removal_to_pdf,
        "key_field": "trace_tag",
        "summary_fields": ["trace_tag", "area", "system_no"],
        "summary_labels": ["Trace Tag #", "Area", "System No."],
    },
    "eht_rtd": {
        "label": "EHT & RTD Installation Inspection",
        "schema": eht_rtd_schema,
        "export_module": export_eht_rtd_to_pdf,
        "key_field": "trace_number",
        "summary_fields": ["trace_number", "controller_number", "panel_number"],
        "summary_labels": ["Trace #", "Controller #", "Panel #"],
    },
    "eht_pre_insulation": {
        "label": "EHT & RTD Pre-Insulation Installation",
        "schema": eht_pre_insulation_schema,
        "export_module": export_eht_pre_insulation_to_pdf,
        "key_field": "trace_number",
        "summary_fields": ["trace_number", "eht_controller_number", "panel_number"],
        "summary_labels": ["Trace #", "EHT Controller #", "Panel #"],
    },
}

# Short, distinct prefixes for sheet names - the equipment types' own
# "label" above is too long to combine with a zone name and stay under
# Excel's 31-character sheet-name limit.
SHEET_NAME_PREFIXES = {
    "eht_removal": "EHT Removal",
    "eht_rtd": "EHT RTD",
    "eht_pre_insulation": "EHT PreIns",
}


# ---------------------------------------------------------------------------
# Workbook cache + the one mutating choke point - same shape as
# data_access.py's _get_cached_workbook/_mutating_workbook, scoped to
# ELECTRICAL_WORKBOOK_PATH instead.
# ---------------------------------------------------------------------------
_wb_cache = {False: None, True: None, "mtime": None}


def _workbook_mtime():
    try:
        return ELECTRICAL_WORKBOOK_PATH.stat().st_mtime
    except OSError:
        return None


def _get_cached_workbook(data_only=False):
    current_mtime = _workbook_mtime()
    if current_mtime != _wb_cache["mtime"]:
        _wb_cache[False] = None
        _wb_cache[True] = None
        _wb_cache["mtime"] = current_mtime
    if _wb_cache[data_only] is None:
        if not ELECTRICAL_WORKBOOK_PATH.exists():
            _bootstrap_empty_workbook()
        _wb_cache[data_only] = openpyxl.load_workbook(ELECTRICAL_WORKBOOK_PATH, data_only=data_only)
    return _wb_cache[data_only]


def _bootstrap_empty_workbook():
    """Creates a brand-new, empty Electrical_Inspection_Tracker.xlsx the
    first time anything needs one - no zones yet, just an otherwise-empty
    workbook openpyxl can open. Zones (and their sheets) are added one at
    a time afterward via add_zone()."""
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    wb.create_sheet("Zones go here")  # a workbook needs at least one sheet
    wb.save(ELECTRICAL_WORKBOOK_PATH)


class WorkbookLockedError(Exception):
    """Raised in place of the raw PermissionError when the Electrical
    workbook appears to be open in Excel (or another program holding an
    exclusive lock) at save time - mirrors data_access.py's identical
    class for the Instrumentation workbook."""


def _excel_lock_file_path():
    return ELECTRICAL_WORKBOOK_PATH.with_name(f"~${ELECTRICAL_WORKBOOK_PATH.name}")


def is_workbook_locked():
    try:
        if _excel_lock_file_path().exists():
            return True
    except OSError:
        pass
    if os.name == "nt" and ELECTRICAL_WORKBOOK_PATH.exists():
        try:
            os.rename(ELECTRICAL_WORKBOOK_PATH, ELECTRICAL_WORKBOOK_PATH)
        except OSError:
            return True
    return False


def _save_workbook(wb):
    try:
        wb.save(ELECTRICAL_WORKBOOK_PATH)
    except PermissionError:
        if is_workbook_locked():
            raise WorkbookLockedError(
                "The Electrical workbook is open in Excel. Close it there, then click Retry."
            ) from None
        raise PermissionError(
            f"Can't save '{ELECTRICAL_WORKBOOK_PATH.name}'. Either it's open in Excel "
            "(or another program) right now - close it there and try again - or this "
            "app's folder needs administrator rights to write to."
        ) from None


def _save_workbook_and_refresh_cache(wb):
    _save_workbook(wb)
    _wb_cache[False] = wb
    _wb_cache[True] = None
    _wb_cache["mtime"] = _workbook_mtime()


def invalidate_workbook_cache():
    _wb_cache[False] = None
    _wb_cache[True] = None
    _wb_cache["mtime"] = None


@contextmanager
def _mutating_workbook():
    wb = _get_cached_workbook(data_only=False)
    try:
        yield wb
    except Exception:
        invalidate_workbook_cache()
        raise
    else:
        _save_workbook_and_refresh_cache(wb)


# ---------------------------------------------------------------------------
# electrical_registry.json - the Zone equivalent of series_registry.json.
# A zone's identity IS its name (no separate number+optional-label split
# like series has - there's no pre-existing numbering convention for
# Electrical to preserve).
# ---------------------------------------------------------------------------
def load_config():
    return read_json_with_recovery(ELECTRICAL_CONFIG_PATH, lambda: {"zones": []})


def save_config(cfg):
    write_json_atomic(ELECTRICAL_CONFIG_PATH, cfg)


def list_zones():
    """Zone names, alphabetically."""
    return sorted(z["name"] for z in load_config()["zones"])


def get_sheet_name(zone_name, equip_key):
    """Self-healing lookup: a zone registered before `equip_key` existed in
    ELECTRICAL_EQUIPMENT_TYPES (e.g. any real zone created before
    eht_pre_insulation was added) has no `<equip_key>_sheet` key yet.
    Rather than permanently raise for every such zone forever, create the
    missing sheet and persist the key now, exactly as add_zone() would have
    done if this equipment type had existed at zone-creation time - the
    same "create what's missing on first real use" philosophy
    _bootstrap_empty_workbook() already uses for the whole workbook.
    Found by an adversarial review of Phase B: every one of get_sheet_name's
    callers (read_index_rows, read_full_row, find_first_blank_row, save_row,
    delete_rows, generate_preview_pdf, open_sheet) propagated an uncaught
    KeyError for this exact case, and remove_zone() already had to code
    around it defensively (entry.get(...) instead of a hard lookup) -
    confirming the missing-key case is a real, reachable possibility that
    now heals instead of failing."""
    cfg = load_config()
    for z in cfg["zones"]:
        if z["name"] == zone_name:
            key = f"{equip_key}_sheet"
            if key not in z:
                etype = ELECTRICAL_EQUIPMENT_TYPES[equip_key]
                with _mutating_workbook() as wb:
                    sheet_name = _sheet_name_for_zone(equip_key, zone_name, wb)
                    _build_new_sheet(wb, sheet_name, etype["schema"].LOG_COLUMNS)
                z[key] = sheet_name
                save_config(cfg)
                return sheet_name
            return z[key]
    raise KeyError(f"Zone '{zone_name}' is not in {ELECTRICAL_CONFIG_PATH.name}")


def _sheet_name_for_zone(equip_key, zone_name, wb):
    """A sheet name under Excel's hard 31-character limit, distinct per
    equipment type - collision-suffixed like _archived_sheet_name() in
    data_access.py whenever two DIFFERENT zone names truncate to the same
    thing (the caller's own "does this exact zone name already exist"
    check doesn't catch that - it compares full zone names, not truncated
    sheet names)."""
    prefix = SHEET_NAME_PREFIXES[equip_key]
    budget = 31 - len(prefix) - 3  # " - "
    candidate = f"{prefix} - {zone_name[:budget]}"
    base, n = candidate, 2
    while candidate in wb.sheetnames:
        suffix = f" ({n})"
        candidate = base[:31 - len(suffix)] + suffix
        n += 1
    return candidate


def _build_new_sheet(wb, sheet_name, log_columns):
    """Creates a brand-new, empty Log sheet from scratch: a title row, then
    the header row (HEADER_ROW=3, matching both export modules'
    convention) with every schema field's label. No data-validation
    dropdowns or conditional formatting are set up (unlike Instrumentation's
    hand-built Transmitter/Valve sheets) - a known v1 limitation; add them
    by hand in Excel afterward if wanted, the same manual fallback
    add_series()'s own docstring already points to for a copy gone wrong."""
    ws = wb.create_sheet(sheet_name)
    ws.cell(row=1, column=1, value=sheet_name)
    for col, field in enumerate(log_columns, start=1):
        ws.cell(row=3, column=col, value=field["label"])
    return ws


def add_zone(zone_name):
    """Registers a brand-new zone and creates both its Log sheets from
    scratch (there's no existing zone's sheet to copy from the way
    add_series() copies an existing series - see _build_new_sheet). Raises
    ValueError only if the zone NAME itself already exists - a truncated
    SHEET name colliding with a different zone's is resolved transparently
    by _sheet_name_for_zone()'s own suffix loop, never surfaced as an
    error the user can't act on (they didn't type the sheet name, and a
    different zone name could just as easily truncate to the same thing)."""
    zone_name = (zone_name or "").strip()
    if not zone_name:
        raise ValueError("Zone name can't be blank.")
    cfg = load_config()
    if any(z["name"] == zone_name for z in cfg["zones"]):
        raise ValueError(f"Zone '{zone_name}' already exists.")

    new_entry = {"name": zone_name}
    with _mutating_workbook() as wb:
        for equip_key, etype in ELECTRICAL_EQUIPMENT_TYPES.items():
            sheet_name = _sheet_name_for_zone(equip_key, zone_name, wb)
            _build_new_sheet(wb, sheet_name, etype["schema"].LOG_COLUMNS)
            new_entry[f"{equip_key}_sheet"] = sheet_name
        # the bootstrap placeholder is only ever needed when NO real zone
        # sheet exists yet - once this loop has created one sheet per
        # registered equipment type, it's always safe to drop.
        if "Zones go here" in wb.sheetnames and len(wb.sheetnames) > len(ELECTRICAL_EQUIPMENT_TYPES):
            del wb["Zones go here"]

    cfg["zones"].append(new_entry)
    save_config(cfg)
    return new_entry


def _archived_sheet_name(original_name, wb):
    stamp = datetime.date.today().strftime("%y%m%d")
    prefix = "DEL "
    budget = 31 - len(prefix) - len(stamp) - 1
    candidate = f"{prefix}{original_name[:budget]} {stamp}"
    base, n = candidate, 2
    while candidate in wb.sheetnames:
        suffix = f"-{n}"
        candidate = base[:31 - len(suffix)] + suffix
        n += 1
    return candidate


def remove_zone(zone_name):
    """Same philosophy as data_access.py's remove_series(): archives
    (renames + hides) the zone's sheets rather than deleting them outright,
    so a misclick can't destroy inspection records permanently."""
    cfg = load_config()
    entry = next((z for z in cfg["zones"] if z["name"] == zone_name), None)
    if entry is None:
        raise KeyError(f"Zone '{zone_name}' is not in {ELECTRICAL_CONFIG_PATH.name}")

    with _mutating_workbook() as wb:
        for equip_key in ELECTRICAL_EQUIPMENT_TYPES:
            sheet_name = entry.get(f"{equip_key}_sheet")
            if sheet_name and sheet_name in wb.sheetnames:
                ws = wb[sheet_name]
                ws.title = _archived_sheet_name(sheet_name, wb)
                ws.sheet_state = "hidden"
        # openpyxl refuses to save a workbook with zero VISIBLE sheets -
        # if this was the last zone, every sheet just got hidden above, so
        # bring back the bootstrap placeholder (removed by add_zone() the
        # first time a real zone was created) rather than let the save
        # crash. It's re-hidden/removed automatically the next time
        # add_zone() succeeds, same as it was originally.
        if not any(ws.sheet_state == "visible" for ws in wb.worksheets):
            if "Zones go here" in wb.sheetnames:
                wb["Zones go here"].sheet_state = "visible"
            else:
                wb.create_sheet("Zones go here")

    cfg["zones"] = [z for z in cfg["zones"] if z["name"] != zone_name]
    save_config(cfg)


# ---------------------------------------------------------------------------
# Reading/writing rows - same shape as data_access.py's equivalents,
# generic over ELECTRICAL_EQUIPMENT_TYPES.
# ---------------------------------------------------------------------------
def read_index_rows(zone_name, equip_key):
    """[{'row': 4, <summary_field>: '...', ...}, ...] - one dict per row
    that has its key field filled in."""
    etype = ELECTRICAL_EQUIPMENT_TYPES[equip_key]
    export_mod = etype["export_module"]
    sheet_name = get_sheet_name(zone_name, equip_key)

    wb = _get_cached_workbook(data_only=False)
    if sheet_name not in wb.sheetnames:
        raise KeyError(f"Workbook has no sheet named '{sheet_name}'")
    ws = wb[sheet_name]
    field_to_col = export_mod.load_column_map(ws)
    key_col = field_to_col.get(etype["key_field"])

    rows = []
    for r in range(export_mod.FIRST_DATA_ROW, ws.max_row + 1):
        key_val = ws.cell(row=r, column=key_col).value if key_col else None
        if key_val in (None, ""):
            continue
        entry = {"row": r}
        for fid in etype["summary_fields"]:
            col = field_to_col.get(fid)
            entry[fid] = export_mod.cell_to_str(ws.cell(row=r, column=col).value) if col else ""
        rows.append(entry)
    return rows


def read_full_row(zone_name, equip_key, row_num):
    """{field_id: value_as_string} for every schema field on one row."""
    etype = ELECTRICAL_EQUIPMENT_TYPES[equip_key]
    export_mod = etype["export_module"]
    schema = etype["schema"]
    sheet_name = get_sheet_name(zone_name, equip_key)

    values = {f["id"]: "" for f in schema.LOG_COLUMNS}

    wb = _get_cached_workbook(data_only=False)
    ws = wb[sheet_name]
    field_to_col = export_mod.load_column_map(ws)
    for fid, col in field_to_col.items():
        values[fid] = export_mod.cell_to_str(ws.cell(row=row_num, column=col).value)
    return values


def find_first_blank_row(zone_name, equip_key):
    etype = ELECTRICAL_EQUIPMENT_TYPES[equip_key]
    export_mod = etype["export_module"]
    sheet_name = get_sheet_name(zone_name, equip_key)

    wb = _get_cached_workbook(data_only=False)
    ws = wb[sheet_name]
    field_to_col = export_mod.load_column_map(ws)
    key_col = field_to_col.get(etype["key_field"])
    r = export_mod.FIRST_DATA_ROW
    while key_col and ws.cell(row=r, column=key_col).value not in (None, ""):
        r += 1
    return r


def save_row(zone_name, equip_key, row_num, values):
    """Writes values (field_id -> string) into one row - only touches
    columns the schema knows about, same as data_access.py's save_row."""
    etype = ELECTRICAL_EQUIPMENT_TYPES[equip_key]
    export_mod = etype["export_module"]
    sheet_name = get_sheet_name(zone_name, equip_key)

    with _mutating_workbook() as wb:
        ws = wb[sheet_name]
        field_to_col = export_mod.load_column_map(ws)
        for fid, val in values.items():
            col = field_to_col.get(fid)
            if col is None:
                continue
            ws.cell(row=row_num, column=col).value = (val if val != "" else None)


def delete_rows(zone_name, equip_key, row_nums):
    """Clears the given row(s) in place - never ws.delete_rows(), same
    reasoning as data_access.py's delete_rows()."""
    etype = ELECTRICAL_EQUIPMENT_TYPES[equip_key]
    export_mod = etype["export_module"]
    sheet_name = get_sheet_name(zone_name, equip_key)

    with _mutating_workbook() as wb:
        ws = wb[sheet_name]
        field_to_col = export_mod.load_column_map(ws)
        for row_num in row_nums:
            for col in field_to_col.values():
                ws.cell(row=row_num, column=col).value = None


def find_duplicate_row(zone_name, equip_key, key_value, exclude_row=None):
    """Returns the row number of another row already using this exact key
    value (case-insensitive), or None if it's free to use."""
    etype = ELECTRICAL_EQUIPMENT_TYPES[equip_key]
    target = str(key_value).strip().casefold()
    if not target:
        return None
    for entry in read_index_rows(zone_name, equip_key):
        if entry["row"] == exclude_row:
            continue
        existing = str(entry.get(etype["key_field"]) or "").strip().casefold()
        if existing == target:
            return entry["row"]
    return None


def count_rows(zone_name, equip_key):
    return len(read_index_rows(zone_name, equip_key))


def count_all_by_type():
    """{'eht_removal': <total across every zone>, 'eht_rtd': <...>}"""
    totals = {k: 0 for k in ELECTRICAL_EQUIPMENT_TYPES}
    for zone_name in list_zones():
        for equip_key in ELECTRICAL_EQUIPMENT_TYPES:
            try:
                totals[equip_key] += count_rows(zone_name, equip_key)
            except KeyError:
                pass
    return totals


def zone_summary(zone_name):
    """{'eht_removal': {'total': N}, 'eht_rtd': {'total': N}} for ONE zone.
    Pre-seeds every registry key at 0 first, same shape as
    count_all_by_type() - a caller can rely on both functions always
    returning every ELECTRICAL_EQUIPMENT_TYPES key (found by an
    adversarial review of Phase B: this used to `continue` before ever
    assigning the key, so it silently omitted it instead of zero-filling
    it, an inconsistency with count_all_by_type()'s contract for the
    identical underlying condition)."""
    result = {k: {"total": 0} for k in ELECTRICAL_EQUIPMENT_TYPES}
    for equip_key in ELECTRICAL_EQUIPMENT_TYPES:
        try:
            result[equip_key] = {"total": count_rows(zone_name, equip_key)}
        except KeyError:
            pass
    return result


# ---------------------------------------------------------------------------
# PDF export - single row at a time (v1 has no batch/export-flag column).
# ---------------------------------------------------------------------------
def generate_preview_pdf(zone_name, equip_key, row_num):
    etype = ELECTRICAL_EQUIPMENT_TYPES[equip_key]
    export_mod = etype["export_module"]
    sheet_name = get_sheet_name(zone_name, equip_key)

    ELECTRICAL_TEMP_DIR.mkdir(exist_ok=True)
    for old in ELECTRICAL_TEMP_DIR.glob("*.pdf"):
        try:
            old.unlink()
        except OSError:
            pass

    wb = _get_cached_workbook(data_only=True)
    ws = wb[sheet_name]
    field_to_col = export_mod.load_column_map(ws)
    values = export_mod.build_values_for_row(ws, field_to_col, row_num)
    key_col = field_to_col.get(etype["key_field"])
    key_val = export_mod.cell_to_str(ws.cell(row=row_num, column=key_col).value) if key_col else ""

    safe_name = export_mod.sanitize(key_val, f"row{row_num}")
    out_path = ELECTRICAL_TEMP_DIR / f"{safe_name} PREVIEW.pdf"
    export_mod.fill_pdf(export_mod.DEFAULT_TEMPLATE, values, out_path, flatten=False)
    return out_path


def open_sheet(zone_name, equip_key):
    """Marks the given zone+type's sheet as the workbook's active tab,
    saves that, then opens the file - same as data_access.py's open_sheet."""
    sheet_name = get_sheet_name(zone_name, equip_key)
    with _mutating_workbook() as wb:
        if sheet_name not in wb.sheetnames:
            raise KeyError(f"Workbook has no sheet named '{sheet_name}'")
        wb.active = wb.sheetnames.index(sheet_name)
    open_file(ELECTRICAL_WORKBOOK_PATH)


# ---------------------------------------------------------------------------
# Export status (the row-level Export checkbox) + mass/batch export.
#
# Same philosophy as data_access.py's equipment_status.json: kept OUTSIDE
# the Excel file, in its own JSON store keyed by zone + equipment type +
# the row's key-field value, so ticking a row's Export box never requires
# touching the Log sheet itself. Electrical only tracks "export" here (no
# Installed/Submitted/Accepted - that's an Instrumentation-specific
# workflow with no established Electrical equivalent yet - see this
# module's own top docstring).
# ---------------------------------------------------------------------------
DEFAULT_ELECTRICAL_STATUS = {"export": False}


def _load_electrical_status_store():
    return read_json_with_recovery(ELECTRICAL_STATUS_PATH, dict)


def _save_electrical_status_store(store):
    write_json_atomic(ELECTRICAL_STATUS_PATH, store)


def _electrical_status_key(zone_name, equip_key, key_value):
    return f"{zone_name}|{equip_key}|{key_value}"


def _normalized_electrical_status(raw):
    merged = dict(DEFAULT_ELECTRICAL_STATUS)
    if raw:
        merged.update(raw)
    return merged


def get_electrical_status(zone_name, equip_key, key_value):
    store = _load_electrical_status_store()
    return _normalized_electrical_status(store.get(_electrical_status_key(zone_name, equip_key, key_value)))


def set_electrical_status(zone_name, equip_key, key_value, **fields):
    store = _load_electrical_status_store()
    k = _electrical_status_key(zone_name, equip_key, key_value)
    current = _normalized_electrical_status(store.get(k))
    current.update(fields)
    store[k] = current
    _save_electrical_status_store(store)


def bulk_set_electrical_status(keys, **fields):
    """keys: an iterable of (zone_name, equip_key, key_value) tuples - one
    read + one write of the status file regardless of how many keys."""
    store = _load_electrical_status_store()
    for zone_name, equip_key, key_value in keys:
        k = _electrical_status_key(zone_name, equip_key, key_value)
        current = _normalized_electrical_status(store.get(k))
        current.update(fields)
        store[k] = current
    _save_electrical_status_store(store)


def read_index_rows_with_export_status(zone_name, equip_key):
    """read_index_rows()'s rows, each with an 'export' key added - the
    Index page's per-row Export checkbox column reads this."""
    etype = ELECTRICAL_EQUIPMENT_TYPES[equip_key]
    rows = read_index_rows(zone_name, equip_key)
    store = _load_electrical_status_store()
    for entry in rows:
        key_val = entry.get(etype["key_field"], "")
        status = _normalized_electrical_status(store.get(_electrical_status_key(zone_name, equip_key, key_val)))
        entry["export"] = status["export"]
    return rows


def run_export(zone_name, equip_key, mode, suffix="", flatten=False,
                subfolder=None, merge=False, clear_after_selected=True,
                include_date_in_filename=False):
    """Batch export - the Electrical equivalent of data_access.py's
    run_export(), scoped to what actually applies here:
        'selected' - only rows whose Export checkbox is checked in the app
                     (the DEFAULT mode - see ElectricalExportDialog).
        'all'      - every row with the key field filled in.
    There is no 'flagged' mode (Electrical's schemas have no Excel
    "Export to PDF Y/N" gate column - see eht_removal_schema.py's own
    docstring for why) and no include_signature option (none of the three
    Electrical forms stamp a signature image - eht_removal/eht_rtd are
    hand-signed only, eht_pre_insulation's signature is a real typed
    field like any other).

    clear_after_selected: when mode == 'selected' and this is True (the
    default), every row actually written un-checks its own Export box
    afterward - same "empties as it's used" convention as Instrumentation's
    export queue.

    include_date_in_filename: appends today's date to every output
    filename, e.g. "TR-001 2026-09-10.pdf".

    Returns the list of Paths written (the merged PDF, if any, is last)."""
    etype = ELECTRICAL_EQUIPMENT_TYPES[equip_key]
    export_mod = etype["export_module"]
    sheet_name = get_sheet_name(zone_name, equip_key)

    out_dir = ELECTRICAL_OUTPUT_DIR
    if subfolder:
        safe_sub = re.sub(r'[<>:"/\\|?*]', "_", subfolder).strip()
        if safe_sub:
            out_dir = out_dir / safe_sub
    out_dir.mkdir(parents=True, exist_ok=True)

    wb = _get_cached_workbook(data_only=True)
    ws = wb[sheet_name]
    field_to_col = export_mod.load_column_map(ws)
    key_col = field_to_col.get(etype["key_field"])

    if mode == "selected":
        rows = [r["row"] for r in read_index_rows_with_export_status(zone_name, equip_key) if r.get("export")]
    else:
        rows = [r["row"] for r in read_index_rows(zone_name, equip_key)]
    if not rows:
        return []

    filename_date = f" {datetime.date.today().isoformat()}" if include_date_in_filename else ""
    written = []
    used_names = set()
    for row_num in rows:
        values = export_mod.build_values_for_row(ws, field_to_col, row_num)
        key_val = export_mod.cell_to_str(ws.cell(row=row_num, column=key_col).value) if key_col else ""
        base_name = export_mod.sanitize(key_val, f"Row{row_num}")
        base_name = f"{base_name} {suffix}" if suffix else base_name
        base_name = f"{base_name}{filename_date}"
        name = base_name
        n = 2
        while name in used_names:
            name = f"{base_name} ({n})"
            n += 1
        used_names.add(name)
        out_path = out_dir / f"{name}.pdf"
        export_mod.fill_pdf(export_mod.DEFAULT_TEMPLATE, values, out_path, flatten=flatten)
        written.append(out_path)

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

    if mode == "selected" and clear_after_selected:
        keys = []
        for row_num in rows:
            key_val = export_mod.cell_to_str(ws.cell(row=row_num, column=key_col).value) if key_col else ""
            if key_val:
                keys.append((zone_name, equip_key, key_val))
        if keys:
            bulk_set_electrical_status(keys, export=False)

    return written
