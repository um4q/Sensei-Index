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
import shutil
from contextlib import contextmanager
from pathlib import Path

import openpyxl
from pypdf import PdfReader, PdfWriter

from data_access import (  # noqa: F401
    HERE, write_json_atomic, read_json_with_recovery, open_file, get_setting,
)

import eht_removal_schema
import eht_rtd_schema
import eht_pre_insulation_schema
import torqueing_schema
import export_eht_removal_to_pdf
import export_eht_rtd_to_pdf
import export_eht_pre_insulation_to_pdf
import export_torqueing_to_pdf

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
# QOL prompt Phase A.1 - own backups dir, own constant (same "HERE is
# imported BY VALUE, so a bare HERE-derived path can't be retroactively
# test-isolated" reasoning as every path constant above).
ELECTRICAL_BACKUPS_DIR = HERE / "electrical_backups"

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
        # Same Yanda QA Representative signature stamp Torqueing has (see
        # export_eht_pre_insulation_to_pdf.py's own stamp_signature()) -
        # generate_preview_pdf()/run_export() check for this key
        # generically (hasattr would also work, but an explicit flag here
        # is easier to grep for and can't be fooled by an unrelated
        # same-named attribute on some future export module).
        "supports_signature_stamp": True,
    },
    "torqueing": {
        "label": "Torqueing Report",
        "schema": torqueing_schema,
        "export_module": export_torqueing_to_pdf,
        "key_field": "torque_record_number",
        "summary_fields": ["torque_record_number", "reference_tag_number", "system_number"],
        "summary_labels": ["Torque Record No.", "Reference Tag #", "System No."],
        "supports_signature_stamp": True,
    },
}

# Short, distinct prefixes for sheet names - the equipment types' own
# "label" above is too long to combine with a zone name and stay under
# Excel's 31-character sheet-name limit.
SHEET_NAME_PREFIXES = {
    "eht_removal": "EHT Removal",
    "eht_rtd": "EHT RTD",
    "eht_pre_insulation": "EHT PreIns",
    "torqueing": "Torqueing",
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
    """QOL prompt Phase A.1: also the choke point for automatic backups,
    same shape/reasoning as data_access.py's identical docstring - a
    snapshot of the CURRENT on-disk Electrical workbook is taken here,
    before this block's write, whenever the last one is older than the
    shared backup_interval_minutes setting (or there isn't one yet).
    Never blocks the actual mutation: a backup failure is warned to
    console and swallowed."""
    _backup_workbook_if_due()
    wb = _get_cached_workbook(data_only=False)
    try:
        yield wb
    except Exception:
        invalidate_workbook_cache()
        raise
    else:
        _save_workbook_and_refresh_cache(wb)


# ---------------------------------------------------------------------------
# QOL prompt Phase A.1 - automatic Electrical workbook backups. Direct
# mirror of data_access.py's identically-named functions (same collision-
# safe timestamped naming, same prune-to-backup_keep behavior), scoped to
# ELECTRICAL_WORKBOOK_PATH/ELECTRICAL_BACKUPS_DIR instead. Deliberately
# SHARES the same backup_interval_minutes/backup_keep settings keys with
# Instrumentation (one cadence for both workbooks) rather than inventing
# electrical_backup_interval_minutes/electrical_backup_keep - simpler for
# a user to reason about ("how often does the app back things up") and
# nothing about those two keys' names or Settings-dialog wording is
# Instrumentation-specific.
# ---------------------------------------------------------------------------
ELECTRICAL_BACKUP_NAME_PREFIX = "Electrical_Inspection_Tracker."
ELECTRICAL_BACKUP_NAME_SUFFIX = ".xlsx"


def _list_backup_paths():
    """Oldest first (by mtime) - [] if the folder doesn't exist yet."""
    if not ELECTRICAL_BACKUPS_DIR.exists():
        return []
    paths = [p for p in ELECTRICAL_BACKUPS_DIR.glob(
        f"{ELECTRICAL_BACKUP_NAME_PREFIX}*{ELECTRICAL_BACKUP_NAME_SUFFIX}") if p.is_file()]
    return sorted(paths, key=lambda p: p.stat().st_mtime)


def _write_backup_snapshot():
    """Copies the CURRENT on-disk workbook into electrical_backups/,
    timestamped to the second. Collision-safe (two backups in the same
    second get a '-2', '-3', ... suffix) so nothing is ever silently
    overwritten."""
    ELECTRICAL_BACKUPS_DIR.mkdir(exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = ELECTRICAL_BACKUPS_DIR / f"{ELECTRICAL_BACKUP_NAME_PREFIX}{stamp}{ELECTRICAL_BACKUP_NAME_SUFFIX}"
    n = 2
    while dest.exists():
        dest = ELECTRICAL_BACKUPS_DIR / f"{ELECTRICAL_BACKUP_NAME_PREFIX}{stamp}-{n}{ELECTRICAL_BACKUP_NAME_SUFFIX}"
        n += 1
    shutil.copy2(ELECTRICAL_WORKBOOK_PATH, dest)
    return dest


def _prune_backups():
    keep = get_setting("backup_keep")
    if not keep or keep <= 0:
        return
    existing = _list_backup_paths()  # oldest first
    for old in existing[:-keep]:
        try:
            old.unlink()
        except OSError:
            pass


def _backup_workbook_if_due():
    if not ELECTRICAL_WORKBOOK_PATH.exists():
        return  # nothing to back up yet (a brand-new install)
    try:
        interval_minutes = get_setting("backup_interval_minutes")
        if interval_minutes is None:
            interval_minutes = 30  # `or 30` would also override an explicit 0 ("always back up")
        existing = _list_backup_paths()
        if existing:
            newest = existing[-1]
            age_minutes = (datetime.datetime.now().timestamp() - newest.stat().st_mtime) / 60
            if age_minutes < interval_minutes:
                return
        _write_backup_snapshot()
        _prune_backups()
    except OSError as exc:
        print(f"WARNING: automatic Electrical workbook backup failed (continuing without backing up): {exc}")


def list_backups():
    """[{'path', 'name', 'mtime', 'size'}, ...], NEWEST first - the
    Backups dialog's list."""
    result = []
    for p in reversed(_list_backup_paths()):
        try:
            stat = p.stat()
        except OSError:
            continue
        result.append({"path": p, "name": p.name, "mtime": stat.st_mtime, "size": stat.st_size})
    return result


def backup_now():
    """The Backups dialog's 'Back up now' button - always writes a fresh
    snapshot regardless of backup_interval_minutes, then prunes to
    backup_keep same as the automatic path."""
    if not ELECTRICAL_WORKBOOK_PATH.exists():
        raise FileNotFoundError("No workbook to back up yet.")
    dest = _write_backup_snapshot()
    _prune_backups()
    return dest


def restore_backup(backup_path):
    """Copies the chosen snapshot over the live workbook - AFTER taking
    ONE MORE safety snapshot of whatever's currently live, so restoring
    is itself undoable (by restoring that safety snapshot by hand).
    Returns the safety snapshot's path (None if there was no live
    workbook to protect - a restore onto a fresh install)."""
    backup_path = Path(backup_path)
    if not backup_path.exists():
        raise FileNotFoundError(f"Backup not found: {backup_path}")
    safety_snapshot = None
    if ELECTRICAL_WORKBOOK_PATH.exists():
        safety_snapshot = _write_backup_snapshot()
    shutil.copy2(backup_path, ELECTRICAL_WORKBOOK_PATH)
    invalidate_workbook_cache()
    return safety_snapshot


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
    now heals instead of failing.

    Also self-heals the column-level version of the same problem: a sheet
    that already exists but was built BEFORE some field was added to its
    schema (e.g. yanda_rep_name added to a form after some zone's sheet
    already existed) has no column for it in its header row at all - every
    caller above resolves columns via load_column_map(), which can only
    find a column that's actually there, so a field missing from the
    header can never be saved or read back no matter how many times it's
    retyped. See _ensure_sheet_has_every_schema_column() below."""
    cfg = load_config()
    for z in cfg["zones"]:
        if z["name"] == zone_name:
            key = f"{equip_key}_sheet"
            etype = ELECTRICAL_EQUIPMENT_TYPES[equip_key]
            if key not in z:
                with _mutating_workbook() as wb:
                    sheet_name = _sheet_name_for_zone(equip_key, zone_name, wb)
                    _build_new_sheet(wb, sheet_name, etype["schema"].LOG_COLUMNS)
                z[key] = sheet_name
                save_config(cfg)
                return sheet_name
            sheet_name = z[key]
            _ensure_sheet_has_every_schema_column(sheet_name, etype)
            return sheet_name
    raise KeyError(f"Zone '{zone_name}' is not in {ELECTRICAL_CONFIG_PATH.name}")


def _ensure_sheet_has_every_schema_column(sheet_name, etype):
    """The column-level equivalent of get_sheet_name()'s own missing-SHEET
    healing above. Backfills any schema field whose label isn't already
    somewhere in the header row onto the END of that row (new columns
    only - existing columns/positions/data are never touched), so
    load_column_map() can find it from here on. A cheap read-only check
    (cached workbook, no save) in the common case where nothing's
    missing; only opens _mutating_workbook() - and so only writes to
    disk - when there's an actual gap to backfill."""
    header_row = etype["export_module"].HEADER_ROW
    wb = _get_cached_workbook(data_only=False)
    if sheet_name not in wb.sheetnames:
        return  # get_sheet_name just resolved this name - shouldn't happen
    ws = wb[sheet_name]
    existing_labels = {ws.cell(row=header_row, column=c).value for c in range(1, ws.max_column + 1)}
    missing = [f for f in etype["schema"].LOG_COLUMNS if f["label"] not in existing_labels]
    if not missing:
        return
    with _mutating_workbook() as wb:
        ws = wb[sheet_name]
        col = ws.max_column + 1
        for field in missing:
            ws.cell(row=header_row, column=col, value=field["label"])
            col += 1


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


def set_zone_name(zone_name, new_name):
    """QOL prompt Phase A.10 - renames a zone (previously a typo'd zone name
    was a dead end short of destructive remove/re-add). Genuinely different
    from data_access.py's set_series_name(): a series has a stable numeric
    identity with a separate, optional display-name overlay, so renaming it
    never touches anything that identity is used as a key for. A zone has
    no such separate id - its `name` field IS the key every other function
    in this module looks it up by (read_index_rows(zone_name, ...),
    save_row(zone_name, ...), etc.) - so this really does change the zone's
    identity going forward. That's still safe: the zone's sheets were
    already created and their names fixed at zone-creation time, stored
    independently under `<equip_key>_sheet` (see get_sheet_name) and never
    derived from the zone name again after that, so this only ever touches
    the JSON registry, never the workbook. Callers that hold onto the old
    name (e.g. a currently-open ElectricalIndexPage) are the caller's
    responsibility to refresh - see rename_zone_flow in gui_app.py."""
    zone_name = (zone_name or "").strip()
    new_name = (new_name or "").strip()
    if not new_name:
        raise ValueError("Zone name can't be blank.")
    cfg = load_config()
    entry = next((z for z in cfg["zones"] if z["name"] == zone_name), None)
    if entry is None:
        raise KeyError(f"Zone '{zone_name}' is not in {ELECTRICAL_CONFIG_PATH.name}")
    if new_name != zone_name and any(z["name"] == new_name for z in cfg["zones"]):
        raise ValueError(f"Zone '{new_name}' already exists.")
    entry["name"] = new_name
    save_config(cfg)


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
                include_date_in_filename=False, include_signature=True):
    """Batch export - the Electrical equivalent of data_access.py's
    run_export(), scoped to what actually applies here:
        'selected' - only rows whose Export checkbox is checked in the app
                     (the DEFAULT mode - see ElectricalExportDialog).
        'all'      - every row with the key field filled in.
    There is no 'flagged' mode (Electrical's schemas have no Excel
    "Export to PDF Y/N" gate column - see eht_removal_schema.py's own
    docstring for why).

    include_signature: only meaningful for an equipment type whose
    ELECTRICAL_EQUIPMENT_TYPES entry sets supports_signature_stamp=True
    (currently eht_pre_insulation and torqueing - see each one's own
    export module's stamp_signature()); harmless to pass for eht_removal/
    eht_rtd too, whose export modules' fill_pdf() simply don't accept the
    kwarg at all - both are hand-signed only, with no signature field or
    stamp of any kind.

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
        if etype.get("supports_signature_stamp"):
            # Only the export modules that actually declare this even
            # accept the kwarg - eht_removal/eht_rtd/eht_pre_insulation's
            # own fill_pdf() signatures have no add_signature parameter at
            # all, so this is passed conditionally, never blindly.
            export_mod.fill_pdf(export_mod.DEFAULT_TEMPLATE, values, out_path,
                                 flatten=flatten, add_signature=include_signature)
        else:
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
