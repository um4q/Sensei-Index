# -*- coding: utf-8 -*-
"""
Data-access layer for the InstINDEX GUI.

Every place in this whole add-on that touches Equipment_Inspection_Tracker.xlsx
or series_registry.json lives in THIS file. gui_app.py never imports openpyxl
directly - it only calls functions defined here. That one rule is what makes
it possible to add a brand-new equipment type later (say, "Gauges") without
touching a single line of gui_app.py: you'd write gauge_schema.py +
gauge_field_map.py + export_gauge_to_pdf.py the same way the existing
Transmitter/Valve trio is built, then add ONE new entry to EQUIPMENT_TYPES
below. Everything else - the menu, the index table, the edit form, the
detail-view PDF - is generic and reads from that registry.

Reused, not duplicated: the column-header lookup, the row-to-PDF-field
translation, and the actual PDF filling all come from the *existing*
export_to_pdf.py / export_valve_to_pdf.py modules (imported below). This file
never re-implements that logic - it just calls it with a specific sheet name
and row number instead of running the whole command-line script.
"""
import contextlib
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path

import openpyxl
from pypdf import PdfReader, PdfWriter

import transmitter_schema
import valve_schema
import export_to_pdf
import export_valve_to_pdf

# When PyInstaller freezes this into a single .exe, __file__ points inside a
# temporary extraction folder (sys._MEIPASS) that's deleted when the app
# closes - using it here would silently lose every edit, setting, and
# signature the moment the exe exits. sys.executable's folder is the actual,
# persistent location of the .exe (or of python.exe when running as a plain
# script, which is why the frozen check comes first).
if getattr(sys, "frozen", False):
    HERE = Path(sys.executable).resolve().parent
else:
    HERE = Path(__file__).resolve().parent

WORKBOOK_PATH = HERE / "Equipment_Inspection_Tracker.xlsx"
CONFIG_PATH = HERE / "series_registry.json"
TEMP_DIR = HERE / "temp_previews"



_wb_cache = {False: None, True: None, "mtime": None}


def _workbook_mtime():
    try:
        return WORKBOOK_PATH.stat().st_mtime
    except OSError:
        return None


def write_json_atomic(path, data):
    """Every JSON file this app writes (series_registry.json,
    app_settings.json, equipment_status.json, and every new sidecar added
    since) goes through this. Two things it guarantees:

    1. Atomicity: the new content is written to a temp file in the SAME
       directory (so it's on the same filesystem - os.replace() is only
       atomic within one filesystem) and only swapped into place with
       os.replace() once the write fully succeeds. A crash, power loss, or
       killed process mid-save leaves either the old file untouched or the
       complete new one - never a truncated/half-written file that bricks
       the next startup.
    2. A permissions problem always gives the same clear explanation
       instead of a raw traceback. In practice this only ever fires one
       way: the app's own folder needs administrator rights to write to -
       almost always because it's sitting inside Program Files or another
       protected location, which normal saves inside the app hit
       constantly.
    """
    path = Path(path)
    tmp_path = path.with_name(f".{path.name}.tmp{os.getpid()}")
    try:
        with open(tmp_path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
        os.replace(tmp_path, path)
    except PermissionError:
        with contextlib.suppress(OSError):
            tmp_path.unlink()
        raise PermissionError(
            f"Can't write to '{path.name}'. This app's folder needs administrator "
            "rights to write to - almost always because it's inside Program Files "
            "or another protected location. Move the whole InstINDEX folder "
            "somewhere any account can write to without admin, like "
            "C:\\Users\\Public\\InstINDEX, your Desktop, or Documents."
        ) from None
    except Exception:
        with contextlib.suppress(OSError):
            tmp_path.unlink()
        raise


# Populated by read_json_with_recovery() whenever it has to reset a
# corrupted sidecar to defaults. gui_app checks this once at startup and
# shows each entry as a toast - so "the file got reset" is never silent,
# but it also never blocks the app from opening the way a crash would.
STARTUP_WARNINGS = []


def read_json_with_recovery(path, default):
    """Loads JSON from path, tolerating both a missing file (returns
    default, no warning - normal for a sidecar that hasn't been created
    yet) and a corrupted one (renames the bad file to
    '<name>.corrupt.<timestamp>' - preserved for hand recovery, never
    silently deleted - queues a STARTUP_WARNINGS entry, and returns
    default). default may be a plain value or a zero-arg callable (use a
    callable when the default is a mutable container, so every caller
    doesn't share one dict/list instance)."""
    path = Path(path)

    def _default():
        return default() if callable(default) else default

    if not path.exists():
        return _default()
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        corrupt_path = path.with_name(f"{path.name}.corrupt.{stamp}")
        try:
            path.rename(corrupt_path)
            STARTUP_WARNINGS.append(
                f"'{path.name}' was corrupted and has been reset to defaults. "
                f"The unreadable file was saved as '{corrupt_path.name}' next to it."
            )
        except OSError:
            STARTUP_WARNINGS.append(
                f"'{path.name}' was corrupted and could not be read - using defaults."
            )
        return _default()


def _get_cached_workbook(data_only=False):
    """Returns a shared, live openpyxl Workbook - reloaded from disk only
    when the file's mtime has changed since the last load. Callers must NOT
    call .close() on what this returns; the cache owns its lifecycle.
    Mutating callers (save_row, add_series, delete_rows, remove_series,
    ...) must call _save_workbook_and_refresh_cache(wb) afterward instead
    of saving directly, so the cache and the on-disk file never disagree."""
    current_mtime = _workbook_mtime()
    if current_mtime != _wb_cache["mtime"]:
        # File is new to us, or changed since we last looked (our own save,
        # or someone editing it directly in Excel) - drop both cached views
        # so they're reloaded fresh, lazily, below.
        _wb_cache[False] = None
        _wb_cache[True] = None
        _wb_cache["mtime"] = current_mtime
    if _wb_cache[data_only] is None:
        _wb_cache[data_only] = openpyxl.load_workbook(WORKBOOK_PATH, data_only=data_only)
    return _wb_cache[data_only]


def _save_workbook_and_refresh_cache(wb):
    """Saves a workbook obtained from _get_cached_workbook(data_only=False)
    and updates the cache to match, so the very next read (e.g. the reload
    that follows almost every save in the GUI) doesn't pay for a disk
    round-trip it doesn't need. The data_only=True view is dropped rather
    than refreshed - openpyxl can't recompute formulas itself, so the only
    honest thing to do with a 'last calculated value' cache after an edit is
    to let it reload fresh the next time something actually needs it."""
    _save_workbook(wb)
    _wb_cache[False] = wb
    _wb_cache[True] = None
    _wb_cache["mtime"] = _workbook_mtime()


def invalidate_workbook_cache():
    """Forces the next read to reload from disk. Not needed in normal use
    (saves already refresh the cache themselves) - exposed mainly so 'Open
    Excel File' + manual edits followed by a Refresh in the app can't ever
    show stale data if mtime granularity ever lies on some filesystem."""
    _wb_cache[False] = None
    _wb_cache[True] = None
    _wb_cache["mtime"] = None


@contextmanager
def _mutating_workbook():
    """Yields the shared cached workbook for a block of in-place edits,
    saving it and refreshing the cache on success. If anything inside the
    block raises, the in-memory workbook is thrown away (never saved) and
    the cache is invalidated - otherwise a half-finished edit (say, the
    Transmitter sheet got copied for a new series but the Valve sheet copy
    then failed) would sit in memory looking like valid, current data on
    every subsequent read, when what's actually on disk never changed."""
    wb = _get_cached_workbook(data_only=False)
    try:
        yield wb
    except Exception:
        invalidate_workbook_cache()
        raise
    else:
        _save_workbook_and_refresh_cache(wb)


# ---------------------------------------------------------------------------
# Equipment type registry - the single place that defines what a
# "Transmitter" or a "Valve" IS, as far as the GUI is concerned.
# ---------------------------------------------------------------------------
EQUIPMENT_TYPES = {
    "transmitter": {
        "label": "Transmitter",
        "schema": transmitter_schema,
        "export_module": export_to_pdf,
        "key_field": "tag",
        "summary_fields": ["tag", "system_number", "transmitter_type"],
        "summary_labels": ["Tag", "System #", "Type"],
        "group_fields": ["system_number"],
        "group_labels": ["System"],
        "date_fields": ["te1_caldate", "te2_caldate", "te3_caldate", "yanda_qa_date", "client_date"],
        "date_labels": ["TE1 Cal. Date", "TE2 Cal. Date", "TE3 Cal. Date", "QA Rep Date", "Client Rep Date"],
    },
    "valve": {
        "label": "Valve",
        "schema": valve_schema,
        "export_module": export_valve_to_pdf,
        "key_field": "equip_number",
        "summary_fields": ["equip_number", "system", "valve_type"],
        "summary_labels": ["Equip #", "System", "Type"],
        "group_fields": ["system"],
        "group_labels": ["System"],
        "date_fields": ["equip_caldate", "qc_date"],
        "date_labels": ["TE Cal. Date", "QC Rep Date"],
    },
}

ASSETS_DIR = HERE / "assets"
SETTINGS_PATH = HERE / "app_settings.json"
STATUS_PATH = HERE / "equipment_status.json"


# ---------------------------------------------------------------------------
# series_registry.json
# ---------------------------------------------------------------------------
def load_config():
    return read_json_with_recovery(CONFIG_PATH, lambda: {"series": []})


def save_config(cfg):
    write_json_atomic(CONFIG_PATH, cfg)


def list_series():
    """e.g. [100, 200]"""
    return sorted(s["number"] for s in load_config()["series"])


def get_sheet_name(series_number, equip_key):
    for s in load_config()["series"]:
        if s["number"] == series_number:
            key = f"{equip_key}_sheet"
            if key not in s:
                raise KeyError(f"Series {series_number} has no '{equip_key}' sheet registered.")
            return s[key]
    raise KeyError(f"Series {series_number} is not in {CONFIG_PATH.name}")


# ---------------------------------------------------------------------------
# Series display names
#
# Series have only ever had a number. This adds an optional friendly label
# next to it (stored as "name" on the series' entry in series_registry.json)
# without touching the workbook at all - so it's instant, and there's no
# sheet-renaming risk to anything Excel-side (named ranges, formulas
# referencing the sheet by name, etc).
# ---------------------------------------------------------------------------
def get_series_name(series_number):
    for s in load_config()["series"]:
        if s["number"] == series_number:
            return s.get("name", "")
    return ""


def set_series_name(series_number, name):
    cfg = load_config()
    for s in cfg["series"]:
        if s["number"] == series_number:
            name = (name or "").strip()
            if name:
                s["name"] = name
            else:
                s.pop("name", None)
            save_config(cfg)
            return
    raise KeyError(f"Series {series_number} is not in {CONFIG_PATH.name}")


def series_display_label(series_number):
    """The custom name if one's been set, or just the bare series number
    as a fallback. Deliberately never says the word 'Series' here - this
    is what actually shows up throughout the sidebar, dashboard, and index
    page titles day-to-day, so a name (or, failing that, just the number)
    reads a lot cleaner than 'Series 100' everywhere."""
    name = get_series_name(series_number)
    return name if name else str(series_number)


# ---------------------------------------------------------------------------
# Removing a whole series
#
# Un-registers it from the app and archives (renames + hides) its
# Transmitter/Valve Log sheets rather than deleting them outright. These are
# equipment inspection/QA records - a single misclick permanently destroying
# a series' entire history is a much worse failure mode than a hidden,
# oddly-named leftover sheet sitting in the workbook that a human can find
# and restore by hand in Excel (Home tab, right-click a sheet tab, Unhide).
# ---------------------------------------------------------------------------
def _archived_sheet_name(original_name, wb):
    """A sheet name under Excel's hard 31-character limit that still says
    what it is and when it was removed, however long the original name."""
    stamp = datetime.date.today().strftime("%y%m%d")
    prefix = "DEL "
    budget = 31 - len(prefix) - len(stamp) - 1  # -1 for the space before the stamp
    candidate = f"{prefix}{original_name[:budget]} {stamp}"
    base, n = candidate, 2
    while candidate in wb.sheetnames:
        suffix = f"-{n}"
        candidate = base[:31 - len(suffix)] + suffix
        n += 1
    return candidate


def remove_series(series_number):
    """Raises KeyError if the series isn't registered. Returns nothing on
    success - callers should refresh whatever series list they're showing."""
    cfg = load_config()
    entry = next((s for s in cfg["series"] if s["number"] == series_number), None)
    if entry is None:
        raise KeyError(f"Series {series_number} is not in {CONFIG_PATH.name}")

    with _mutating_workbook() as wb:
        for equip_key in EQUIPMENT_TYPES:
            sheet_name = entry.get(f"{equip_key}_sheet")
            if sheet_name and sheet_name in wb.sheetnames:
                ws = wb[sheet_name]
                ws.title = _archived_sheet_name(sheet_name, wb)
                ws.sheet_state = "hidden"

    cfg["series"] = [s for s in cfg["series"] if s["number"] != series_number]
    save_config(cfg)

    prefix = f"{series_number}|"
    store = _load_status_store()
    filtered = {k: v for k, v in store.items() if not k.startswith(prefix)}
    if len(filtered) != len(store):
        _save_status_store(filtered)


# ---------------------------------------------------------------------------
# Reading rows for the Index view
# ---------------------------------------------------------------------------
def _looks_like_excel_serial(text):
    """True for a bare integer roughly in the range Excel's date serials
    cover for realistic years (~1954-2064). Used only to decide whether a
    date field's raw text is worth trying to reformat for display - never
    to guess at non-date fields."""
    t = text.strip()
    if not t or not t.lstrip("-").isdigit():
        return False
    n = int(t)
    return 19000 <= n <= 60000


def format_date_for_display(raw_text):
    """Best-effort cosmetic fix for date fields whose cell was never given
    a proper Excel date format - some rows in this workbook have calibration
    / sign-off dates stored as a bare serial number (e.g. "46234") that
    Excel itself would also show as "46234" until the cell's format is
    fixed. Converts anything that looks like one of those into a plain
    "YYYY-MM-DD" string for display. Purely cosmetic: the underlying cell
    is untouched unless that field is actually edited afterward, at which
    point whatever gets typed (or Mass Edit Dates sets) is saved as clean
    text and the formatting problem is gone for that cell for good."""
    if not raw_text:
        return raw_text
    if _looks_like_excel_serial(raw_text):
        try:
            from openpyxl.utils.datetime import from_excel
            return from_excel(int(raw_text)).strftime("%Y-%m-%d")
        except Exception:
            return raw_text
    return raw_text


def read_index_rows(series_number, equip_key):
    """[{'row': 5, 'tag': '...', 'system_number': '...', ...}, ...] - one
    dict per row that has its key field (Tag / Equip #) filled in. Includes
    both the equipment type's summary_fields AND date_fields - the Index
    table's grid shows and mass-edits both."""
    etype = EQUIPMENT_TYPES[equip_key]
    export_mod = etype["export_module"]
    sheet_name = get_sheet_name(series_number, equip_key)

    wb = _get_cached_workbook(data_only=False)
    if sheet_name not in wb.sheetnames:
        raise KeyError(f"Workbook has no sheet named '{sheet_name}'")
    ws = wb[sheet_name]
    field_to_col = export_mod.load_column_map(ws)
    key_col = field_to_col.get(etype["key_field"])
    date_fields = set(etype.get("date_fields", []))
    display_fields = list(etype["summary_fields"]) + list(date_fields)

    rows = []
    for r in range(export_mod.FIRST_DATA_ROW, ws.max_row + 1):
        key_val = ws.cell(row=r, column=key_col).value if key_col else None
        if key_val in (None, ""):
            continue
        entry = {"row": r}
        for fid in display_fields:
            col = field_to_col.get(fid)
            raw = ws.cell(row=r, column=col).value if col else ""
            text = export_mod.cell_to_str(raw)
            entry[fid] = format_date_for_display(text) if fid in date_fields else text
        rows.append(entry)
    return rows


def read_full_row(series_number, equip_key, row_num):
    """{field_id: value_as_string} for every schema field on one row - used
    to pre-fill the Edit form."""
    etype = EQUIPMENT_TYPES[equip_key]
    export_mod = etype["export_module"]
    schema = etype["schema"]
    sheet_name = get_sheet_name(series_number, equip_key)
    date_fields = set(etype.get("date_fields", []))

    values = {f["id"]: "" for f in schema.LOG_COLUMNS}

    wb = _get_cached_workbook(data_only=False)
    ws = wb[sheet_name]
    field_to_col = export_mod.load_column_map(ws)
    for fid, col in field_to_col.items():
        text = export_mod.cell_to_str(ws.cell(row=row_num, column=col).value)
        values[fid] = format_date_for_display(text) if fid in date_fields else text
    return values


def find_first_blank_row(series_number, equip_key):
    """First data row whose key field (Tag / Equip #) is empty - used for
    'Add New'."""
    etype = EQUIPMENT_TYPES[equip_key]
    export_mod = etype["export_module"]
    sheet_name = get_sheet_name(series_number, equip_key)

    wb = _get_cached_workbook(data_only=False)
    ws = wb[sheet_name]
    field_to_col = export_mod.load_column_map(ws)
    key_col = field_to_col.get(etype["key_field"])
    r = export_mod.FIRST_DATA_ROW
    while key_col and ws.cell(row=r, column=key_col).value not in (None, ""):
        r += 1
    return r


def save_row(series_number, equip_key, row_num, values):
    """Writes values (field_id -> string) into one row of the matching Log
    sheet and saves the workbook. Only touches columns the schema knows
    about - every other cell (styling, the yellow example-row formatting,
    other columns) is left exactly as it was."""
    etype = EQUIPMENT_TYPES[equip_key]
    export_mod = etype["export_module"]
    sheet_name = get_sheet_name(series_number, equip_key)

    with _mutating_workbook() as wb:
        ws = wb[sheet_name]
        field_to_col = export_mod.load_column_map(ws)
        for fid, val in values.items():
            col = field_to_col.get(fid)
            if col is None:
                continue
            ws.cell(row=row_num, column=col).value = (val if val != "" else None)


def save_fields_bulk(series_number, equip_key, updates):
    """updates: an iterable of (row_num, field_id, value) triples - writes
    all of them within a SINGLE workbook load/save cycle, regardless of how
    many rows or fields are touched. This is the efficient path behind
    every "mass edit" action in the Index grid (paste across a column,
    fill-down, mass-clear, Mass Edit Dates) - the alternative, calling
    save_row() once per cell, would mean one full disk write per cell,
    which gets slow fast once a paste spans dozens of rows."""
    etype = EQUIPMENT_TYPES[equip_key]
    export_mod = etype["export_module"]
    sheet_name = get_sheet_name(series_number, equip_key)

    with _mutating_workbook() as wb:
        ws = wb[sheet_name]
        field_to_col = export_mod.load_column_map(ws)
        for row_num, fid, val in updates:
            col = field_to_col.get(fid)
            if col is None:
                continue
            ws.cell(row=row_num, column=col).value = (val if val != "" else None)


# ---------------------------------------------------------------------------
# Removing rows
#
# This clears every schema-mapped cell on each given row rather than
# physically deleting the worksheet row (ws.delete_rows). A real delete
# would shift every row below it up by one - which sounds fine until you
# remember data-validation dropdown ranges and conditional-formatting rules
# (like the Export-flag green highlight) are anchored to specific row
# numbers, and openpyxl's support for re-anchoring those on a shift is
# known to be incomplete. Clearing in place touches only the cells the
# schema already owns, can't disturb anything else on the sheet, and the
# row becomes indistinguishable from an unused one - find_first_blank_row()
# will naturally hand it back out the next time something is added, so
# nothing is wasted.
# ---------------------------------------------------------------------------
def delete_rows(series_number, equip_key, row_nums):
    """Clears the given row number(s) in one series+type's Log sheet.
    Returns the list of key-field values (Tag / Equip #) that were cleared,
    so their Installed/Submitted status entries can be dropped too."""
    etype = EQUIPMENT_TYPES[equip_key]
    export_mod = etype["export_module"]
    sheet_name = get_sheet_name(series_number, equip_key)
    key_field = etype["key_field"]

    cleared_keys = []
    with _mutating_workbook() as wb:
        ws = wb[sheet_name]
        field_to_col = export_mod.load_column_map(ws)
        key_col = field_to_col.get(key_field)

        for row_num in row_nums:
            if key_col:
                key_val = ws.cell(row=row_num, column=key_col).value
                if key_val not in (None, ""):
                    cleared_keys.append(str(key_val))
            for col in field_to_col.values():
                ws.cell(row=row_num, column=col).value = None

    if cleared_keys:
        store = _load_status_store()
        changed = False
        for key_val in cleared_keys:
            if store.pop(_status_key(series_number, equip_key, key_val), None) is not None:
                changed = True
        if changed:
            _save_status_store(store)

    return cleared_keys


def _save_workbook(wb):
    try:
        wb.save(WORKBOOK_PATH)
    except PermissionError:
        raise PermissionError(
            f"Can't save '{WORKBOOK_PATH.name}'. One of two things is almost "
            "always the cause: it's open in Excel (or another program) right "
            "now - close it there and try again - or this app's folder needs "
            "administrator rights to write to, which usually means it's "
            "sitting inside Program Files or another protected location. If "
            "it's the second one, move the whole InstINDEX folder somewhere "
            "any account can write to without admin, like "
            "C:\\Users\\Public\\InstINDEX, your Desktop, or Documents."
        ) from None


# ---------------------------------------------------------------------------
# "View Details" - fill one row into a PDF in a temp folder, then open it
# ---------------------------------------------------------------------------
def generate_preview_pdf(series_number, equip_key, row_num):
    etype = EQUIPMENT_TYPES[equip_key]
    export_mod = etype["export_module"]
    sheet_name = get_sheet_name(series_number, equip_key)

    TEMP_DIR.mkdir(exist_ok=True)
    for old in TEMP_DIR.glob("*.pdf"):          # keep the temp folder from growing forever
        try:
            old.unlink()
        except OSError:
            pass  # a previous preview is probably still open in a PDF viewer - fine, skip it

    wb = _get_cached_workbook(data_only=True)
    ws = wb[sheet_name]
    field_to_col = export_mod.load_column_map(ws)
    values = export_mod.build_values_for_row(ws, field_to_col, row_num)
    key_col = field_to_col.get(etype["key_field"])
    key_val = export_mod.cell_to_str(ws.cell(row=row_num, column=key_col).value) if key_col else ""

    safe_name = export_mod.sanitize(key_val, f"row{row_num}")
    out_path = TEMP_DIR / f"{safe_name} PREVIEW.pdf"

    if equip_key == "valve":
        export_mod.fill_pdf(export_mod.DEFAULT_TEMPLATE, values, out_path,
                             flatten=False, add_signature=True)
    else:
        export_mod.fill_pdf(export_mod.DEFAULT_TEMPLATE, values, out_path, flatten=False)

    return out_path


def open_file(path):
    """Opens a file with whatever the OS considers its default app for it."""
    path = str(path)
    if sys.platform.startswith("win"):
        os.startfile(path)  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.run(["open", path])
    else:
        subprocess.run(["xdg-open", path])


# ---------------------------------------------------------------------------
# Settings -> Add a new series
# ---------------------------------------------------------------------------
def add_series(new_number, source_number=None):
    """Duplicates an existing series' Transmitter + Valve Log sheets into a
    brand-new, empty series, and registers it in series_registry.json.

    Best-effort: openpyxl's copy_worksheet() copies cell values, styles,
    column widths, and merged cells - but it silently DROPS data-validation
    dropdowns and conditional formatting. This function re-attaches both by
    hand afterward, then wipes the data rows so the new sheet starts empty.

    If this ever produces a sheet where a dropdown doesn't work, the
    reliable fallback is to duplicate the sheet manually in Excel (right-click
    the tab -> Move or Copy -> check "Create a copy") and then call
    register_existing_series() instead.
    """
    cfg = load_config()
    existing_numbers = [s["number"] for s in cfg["series"]]
    if new_number in existing_numbers:
        raise ValueError(f"Series {new_number} already exists.")
    if source_number is None:
        source_number = existing_numbers[0]

    new_entry = {"number": new_number}
    with _mutating_workbook() as wb:
        for equip_key, etype in EQUIPMENT_TYPES.items():
            src_name = get_sheet_name(source_number, equip_key)
            new_name = f"{etype['label']} Log {new_number}"
            if new_name in wb.sheetnames:
                raise ValueError(f"Sheet '{new_name}' already exists in the workbook.")

            src_ws = wb[src_name]
            new_ws = wb.copy_worksheet(src_ws)
            new_ws.title = new_name

            for dv in src_ws.data_validations.dataValidation:
                new_ws.add_data_validation(dv)
            for cf in src_ws.conditional_formatting:
                for rule in cf.rules:
                    new_ws.conditional_formatting.add(str(cf.sqref), rule)

            export_mod = etype["export_module"]
            for r in range(export_mod.FIRST_DATA_ROW, new_ws.max_row + 1):
                for c in range(1, new_ws.max_column + 1):
                    new_ws.cell(row=r, column=c).value = None

            new_entry[f"{equip_key}_sheet"] = new_name

    cfg["series"].append(new_entry)
    save_config(cfg)
    return new_entry


def register_existing_series(new_number, transmitter_sheet, valve_sheet):
    """For the manual fallback: you already created 'Transmitter Log 300' /
    'Valve Log 300' yourself in Excel - this just teaches the app about
    them, with no sheet copying at all."""
    wb = _get_cached_workbook(data_only=False)
    for name in (transmitter_sheet, valve_sheet):
        if name not in wb.sheetnames:
            raise KeyError(f"Workbook has no sheet named '{name}'")

    cfg = load_config()
    if any(s["number"] == new_number for s in cfg["series"]):
        raise ValueError(f"Series {new_number} already exists.")
    cfg["series"].append({
        "number": new_number,
        "transmitter_sheet": transmitter_sheet,
        "valve_sheet": valve_sheet,
    })
    save_config(cfg)


# ---------------------------------------------------------------------------
# Instructions + live counts (for the Instructions dialog and the Main Menu /
# Series Menu summary numbers)
# ---------------------------------------------------------------------------
def read_instructions():
    """Column B of the workbook's 'Instructions' sheet, one string per
    non-empty row, in order. Returns [] if the sheet doesn't exist."""
    wb = _get_cached_workbook(data_only=False)
    if "Instructions" not in wb.sheetnames:
        return []
    ws = wb["Instructions"]
    lines = []
    for r in range(1, ws.max_row + 1):
        val = ws.cell(row=r, column=2).value
        if val:
            lines.append(str(val))
    return lines


def count_rows(series_number, equip_key):
    """How many rows in this series+type have their key field filled in."""
    return len(read_index_rows(series_number, equip_key))


def series_type_summary(series_number, equip_key, group_field):
    """(count, {group_value: count}) in one pass over read_index_rows() -
    used by the sidebar, which used to call count_rows() and
    distinct_group_values() back to back (two separate scans of the same
    rows) for every series x equipment-type combo it draws."""
    rows = read_index_rows(series_number, equip_key)
    counts = {}
    for r in rows:
        val = str(r.get(group_field) or "").strip()
        if val:
            counts[val] = counts.get(val, 0) + 1
    return len(rows), dict(sorted(counts.items()))


def count_all_by_type():
    """{'transmitter': <total across every series>, 'valve': <...>}"""
    totals = {k: 0 for k in EQUIPMENT_TYPES}
    for series_number in list_series():
        for equip_key in EQUIPMENT_TYPES:
            try:
                totals[equip_key] += count_rows(series_number, equip_key)
            except KeyError:
                pass  # this series doesn't register that equipment type
    return totals


# ---------------------------------------------------------------------------
# Per-series Installed/Submitted/Accepted breakdown - powers the Dashboard's
# "BY SERIES" cards (one card per series, each showing how many Transmitters
# and Valves are logged AND how many of each are Installed/Submitted/
# Accepted - the plain totals in count_all_by_type() above only ever showed
# a single grand total per equipment type, with no per-series or
# per-status view at all).
# ---------------------------------------------------------------------------
def series_full_summary(series_number):
    """{'transmitter': {'total': N, 'installed': n, 'submitted': n, 'accepted': n},
         'valve': {...}} for ONE series. An equipment type is simply absent
    from the result if this series has no sheet registered for it."""
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


# ---------------------------------------------------------------------------
# Populating Wizard - a single resumable draft.
#
# Deliberately just ONE slot (not a named/multi-draft library): the wizard
# is meant for "I'm about to bulk-enter a batch of similar equipment, got
# interrupted, and want to pick the batch back up later" - not for
# maintaining a permanent library of in-progress templates. Saving a new
# draft overwrites whatever was there before, and the wizard tells you
# that plainly before it lets you do so.
# ---------------------------------------------------------------------------
DRAFTS_PATH = HERE / "wizard_draft.json"


def load_wizard_draft():
    return read_json_with_recovery(DRAFTS_PATH, None)


def save_wizard_draft(data):
    write_json_atomic(DRAFTS_PATH, data)


def clear_wizard_draft():
    try:
        DRAFTS_PATH.unlink()
    except FileNotFoundError:
        pass


# ---------------------------------------------------------------------------
# App-wide settings: theme, default export preferences, which signature
# image is "active". Lives in its own small JSON file - nothing to do with
# the workbook at all.
# ---------------------------------------------------------------------------
DEFAULT_SETTINGS = {
    "theme": "bootstrap-light",
    "active_signature": "yanda_qa_signature_transparent.png",
    "default_flatten": False,
    "default_include_signature": True,
    # Sensei Index 2.1 additions:
    "default_qa_rep_name": "",           # pre-fills the QA rep name on create-from-master (Coverage)
    "master_list_path": "",              # remembered path for Master List re-import (Coverage)
    "backup_interval_minutes": 30,       # automatic workbook backup cadence
    "backup_keep": 20,                   # how many workbook snapshots to retain
}


def load_settings():
    data = read_json_with_recovery(SETTINGS_PATH, dict)
    merged = dict(DEFAULT_SETTINGS)
    merged.update(data)
    return merged


def save_settings(settings):
    write_json_atomic(SETTINGS_PATH, settings)


def get_setting(key):
    return load_settings().get(key, DEFAULT_SETTINGS.get(key))


def set_setting(key, value):
    settings = load_settings()
    settings[key] = value
    save_settings(settings)


# ---------------------------------------------------------------------------
# Signature image management (the assets/ folder)
# ---------------------------------------------------------------------------
SIGNATURE_EXTENSIONS = {".png", ".jpg", ".jpeg"}


def list_signatures():
    ASSETS_DIR.mkdir(exist_ok=True)
    return sorted(p.name for p in ASSETS_DIR.iterdir()
                  if p.suffix.lower() in SIGNATURE_EXTENSIONS)


def add_signature(source_path, display_name):
    """Copies an existing PNG/JPG from anywhere on disk into assets/, named
    after display_name. Returns the new filename."""
    source_path = Path(source_path)
    if not source_path.exists():
        raise FileNotFoundError(f"Can't find {source_path}")
    ext = source_path.suffix.lower()
    if ext not in SIGNATURE_EXTENSIONS:
        raise ValueError("Signature file must be a .png, .jpg, or .jpeg image.")

    # Validate with the exact same reader stamp_signature() uses later, so
    # passing validation here is a real guarantee it'll work at export time
    # too - not just a superficial extension check.
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
        set_setting("active_signature", filename)  # first one added becomes active automatically
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
    """Points the export module's SIGNATURE_IMAGE constant at whichever file
    is currently active in Settings. export_to_pdf.py / export_valve_to_pdf.py
    both read SIGNATURE_IMAGE as a plain module-level global at call time
    (not a baked-in default argument), so reassigning it here from outside
    genuinely changes what the next fill_pdf() call stamps - no need to
    touch either export script for this part."""
    active_path = get_active_signature_path()
    if active_path is not None:
        export_mod.SIGNATURE_IMAGE = active_path


# ---------------------------------------------------------------------------
# Installed / Submitted / Accepted status tracking.
#
# Deliberately kept OUTSIDE the Excel file, in its own JSON store keyed by
# series + equipment type + the row's key-field value (Tag / Equip #), so
# this never requires inserting new columns into your real, in-production
# Log sheets (which would also mean widening every data-validation and
# conditional-formatting range on every existing and future series sheet -
# a much bigger, riskier change for what's meant to be a lightweight
# tracking flag). The trade-off: this status lives in equipment_status.json
# next to the workbook, not as a column you'd see opening the raw .xlsx.
#
# "accepted" was added after installed/submitted, and "export" after that -
# which means real stored entries from earlier updates only have whichever
# keys existed when they were written. Every read of a status dict below
# goes through a DEFAULT_STATUS merge rather than trusting the stored dict
# to already have every key - a plain `[...]` lookup on an old entry would
# KeyError the very first time a pre-existing row's status was read after
# one of these changes.
#
# "export" is the row-level Export checkbox in the Index table: ticking it
# queues that row for the NEXT export run regardless of the Excel sheet's
# own "Export to PDF (Y/N)" column. It's intentionally stored here (next to
# installed/submitted/accepted) rather than written into the workbook, for
# the same reason those are: no new column, no widened data-validation /
# conditional-formatting ranges on every Log sheet.
# ---------------------------------------------------------------------------
DEFAULT_STATUS = {"installed": False, "submitted": False, "accepted": False, "export": False}


def _load_status_store():
    return read_json_with_recovery(STATUS_PATH, dict)


def _save_status_store(store):
    write_json_atomic(STATUS_PATH, store)


def _status_key(series_number, equip_key, key_value):
    return f"{series_number}|{equip_key}|{key_value}"


def _normalized_status(raw):
    """DEFAULT_STATUS, overlaid with whatever fields a stored entry
    actually has - so an entry saved before 'accepted' existed still comes
    back with accepted=False instead of a missing key."""
    merged = dict(DEFAULT_STATUS)
    if raw:
        merged.update(raw)
    return merged


def get_status(series_number, equip_key, key_value):
    store = _load_status_store()
    return _normalized_status(store.get(_status_key(series_number, equip_key, key_value)))


def set_status(series_number, equip_key, key_value, **fields):
    store = _load_status_store()
    k = _status_key(series_number, equip_key, key_value)
    current = _normalized_status(store.get(k))
    current.update(fields)
    store[k] = current
    _save_status_store(store)


def bulk_set_status(keys, **fields):
    """keys: an iterable of (series_number, equip_key, key_value) tuples -
    e.g. every row currently selected or visible in a filtered Index
    window. Loads and saves the status file exactly once regardless of how
    many keys are passed, so selecting a hundred rows and toggling a status
    on all of them is still a single read + single write."""
    store = _load_status_store()
    for series_number, equip_key, key_value in keys:
        k = _status_key(series_number, equip_key, key_value)
        current = _normalized_status(store.get(k))
        current.update(fields)
        store[k] = current
    _save_status_store(store)


def rename_status_key(series_number, equip_key, old_key, new_key):
    """Migrates an Installed/Submitted/Accepted/Export status entry from
    old_key to new_key. Called whenever the Tag/Equip # itself is edited
    in place (inline in the Index grid) - without this, the row's status
    would appear to silently reset to unchecked the moment its identifying
    text changed, since the status store is keyed by that exact text."""
    if not old_key or not new_key or old_key == new_key:
        return
    store = _load_status_store()
    old_full = _status_key(series_number, equip_key, old_key)
    new_full = _status_key(series_number, equip_key, new_key)
    if old_full in store:
        store[new_full] = store.pop(old_full)
        _save_status_store(store)


# ---------------------------------------------------------------------------
# Phase 12 - Unified progress model.
#
# One definition of "how done is this instrument," used identically by
# IndexPage, DashboardPage, and Coverage - so the app has a single number
# instead of four disconnected checkboxes (Installed / Submitted / Accepted
# / "did anyone fill out the inspection"). Pure function, no workbook or
# sidecar I/O: callers pass in a read_full_row()-shaped values dict and a
# get_status()-shaped status dict, both of which they already have.
#
# Milestones are equal-weighted by default. PROGRESS_WEIGHTS is a plain
# dict (not baked into the function) specifically so a future "Accepted
# should count for more than Serial captured" ask from the client is a
# one-dict change, not a rewrite (see spec assumption 12.4).
# ---------------------------------------------------------------------------
PROGRESS_MILESTONES = [
    ("created", "Created"),
    ("serial_captured", "Serial captured"),
    ("installed", "Installed"),
    ("inspection_complete", "Inspection complete"),
    ("submitted", "Submitted"),
    ("accepted", "Accepted"),
]

PROGRESS_WEIGHTS = {
    "transmitter": {mid: 1 for mid, _label in PROGRESS_MILESTONES},
    "valve": {mid: 1 for mid, _label in PROGRESS_MILESTONES},
}

# Every valve "component" the check record has a Model/Serial pair for.
# "valve" itself is always required (it's what the row IS); the rest only
# count toward "serial captured" if that component's model was actually
# specified - a row with no positioner shouldn't be penalized for a blank
# positioner serial.
_VALVE_COMPONENTS = ["valve", "actuator", "positioner", "solenoid", "position_limit"]
_TRANSMITTER_VI_FIELDS = [f"vi_{i}" for i in range(1, 13)]         # PART 3, transmitter_schema.py
_TRANSMITTER_PROC_FIELDS = [f"proc_{i}" for i in range(2, 15)]     # PART 4 items 2-14 (excludes proc_1_vdc)
_VALVE_FV_FIELDS = [f"fv_{i}" for i in range(1, 9)]                # Functional Verification, valve_schema.py


def _progress_blank(value):
    return not str(value or "").strip()


def _serial_captured(equip_key, values):
    if equip_key != "valve":
        return not _progress_blank(values.get("serial_number"))
    for component in _VALVE_COMPONENTS:
        model_blank = component != "valve" and _progress_blank(values.get(f"{component}_model"))
        if model_blank:
            continue  # this component isn't present on this valve at all
        if _progress_blank(values.get(f"{component}_serial")):
            return False
    return True


def _inspection_complete(equip_key, values):
    fields = _VALVE_FV_FIELDS if equip_key == "valve" else (_TRANSMITTER_VI_FIELDS + _TRANSMITTER_PROC_FIELDS)
    return all(not _progress_blank(values.get(f)) for f in fields)


def compute_progress(equip_key, values, status):
    """values: {field_id: str}, shaped like read_full_row()'s return.
    status: {'installed': bool, 'submitted': bool, 'accepted': bool, ...},
    shaped like get_status()'s return (missing keys are treated as False,
    so a plain {} also works).

    Returns {'percent': int 0-100,
             'milestones': [{'id', 'label', 'done'}, ...] in fixed order,
             'next': id of the first not-done milestone, or None if every
                     milestone is done}."""
    values = values or {}
    status = status or {}

    done_by_id = {
        "created": True,  # this function is only ever called for a row that exists
        "serial_captured": _serial_captured(equip_key, values),
        "installed": bool(status.get("installed")),
        "inspection_complete": _inspection_complete(equip_key, values),
        "submitted": bool(status.get("submitted")),
        "accepted": bool(status.get("accepted")),
    }

    weights = PROGRESS_WEIGHTS.get(equip_key, PROGRESS_WEIGHTS["transmitter"])
    total_weight = sum(weights.values()) or 1
    earned_weight = sum(weights[mid] for mid, _label in PROGRESS_MILESTONES if done_by_id[mid])
    percent = round(100 * earned_weight / total_weight)

    milestones = [{"id": mid, "label": label, "done": done_by_id[mid]}
                  for mid, label in PROGRESS_MILESTONES]
    next_id = next((mid for mid, _label in PROGRESS_MILESTONES if not done_by_id[mid]), None)

    return {"percent": percent, "milestones": milestones, "next": next_id}


# ---------------------------------------------------------------------------
# Status-enriched + filterable row reading, for the Index window and the
# System/Type drill-down browser. Both build on read_index_rows() - neither
# re-reads the workbook independently.
# ---------------------------------------------------------------------------
def read_index_rows_with_status(series_number, equip_key):
    etype = EQUIPMENT_TYPES[equip_key]
    rows = read_index_rows(series_number, equip_key)
    store = _load_status_store()
    for entry in rows:
        key_val = entry.get(etype["key_field"], "")
        status = _normalized_status(store.get(_status_key(series_number, equip_key, key_val)))
        entry["installed"] = status["installed"]
        entry["submitted"] = status["submitted"]
        entry["accepted"] = status["accepted"]
        entry["export"] = status["export"]
    return rows


def read_index_rows_filtered(series_number, equip_key, filters=None):
    """filters: {field_id: value} - e.g. {'system_number': 'STEAM'}. Applied
    as an exact (string) match, on top of the status-enriched row list."""
    rows = read_index_rows_with_status(series_number, equip_key)
    if filters:
        for fid, val in filters.items():
            rows = [r for r in rows if str(r.get(fid) or "") == str(val)]
    return rows


def distinct_group_values(series_number, equip_key, group_field, filters=None):
    """{value: count} for every distinct non-blank value of group_field,
    among rows matching any filters already chosen at a shallower level of
    the drill-down browser."""
    rows = read_index_rows(series_number, equip_key)
    if filters:
        for fid, val in filters.items():
            rows = [r for r in rows if str(r.get(fid) or "") == str(val)]
    counts = {}
    for r in rows:
        val = str(r.get(group_field) or "").strip()
        if val:
            counts[val] = counts.get(val, 0) + 1
    return dict(sorted(counts.items()))


# ---------------------------------------------------------------------------
# Batch export (the new Export menu) - mirrors what export_to_pdf.py /
# export_valve_to_pdf.py's own main() does, but driven by explicit GUI
# parameters instead of argv, and able to target a subfolder of output_pdfs/.
# ---------------------------------------------------------------------------
def run_export(series_number, equip_key, mode, suffix, flatten, include_signature,
                subfolder=None, merge=False, filters=None, clear_after_selected=True,
                include_date_in_filename=False):
    """mode:
        'selected' - only rows whose Export checkbox is checked in the app
                     (the DEFAULT mode - see ExportDialog). Nothing to do
                     with the Excel sheet at all; this is purely the
                     app-side checkbox state from equipment_status.json.
        'flagged'  - only rows with the Excel "Export to PDF (Y/N)" column
                     set to Y (the sheet's own status, unchanged from the
                     original workbook-driven behavior).
        'all'      - every row with the key field filled in.
    filters, if given (e.g. {'system_number': 'STEAM'}), narrows any of
    these down further to rows matching it - the same filter dict the
    Index page's System drill-down already uses, so "export everything
    currently shown while filtered by system" reuses the exact same
    matching logic as what's on screen.

    clear_after_selected: when mode == 'selected' and this is True (the
    default), every row actually written un-checks its own Export box
    afterward - the queue empties as it's used, like a real "ready to
    send" tray rather than a sticky flag someone has to remember to clear.

    Sign-off dates (both equipment types) come from real schema fields now
    - qc_date for valves, yanda_qa_date/client_date for transmitters - so
    they're just ordinary values from the row like anything else, edited
    ahead of time in the Index grid or with Mass Edit Dates. Valve exports
    used to also silently stamp today's date next to the signature image
    as a separate canvas overlay; that's gone now that qc_date is a real,
    visible field occupying that exact spot on the form - stamping a
    second date there would just draw over the first.

    include_date_in_filename: appends today's date to every output
    filename, e.g. "29103-PIT-1021 DEV. 2026-08-27.pdf".

    Returns the list of Paths written (the merged PDF, if any, is last)."""
    etype = EQUIPMENT_TYPES[equip_key]
    export_mod = etype["export_module"]
    sheet_name = get_sheet_name(series_number, equip_key)
    _apply_active_signature(export_mod)

    out_dir = HERE / "output_pdfs"
    if subfolder:
        safe_sub = re.sub(r'[<>:"/\\|?*]', "_", subfolder).strip()
        if safe_sub:
            out_dir = out_dir / safe_sub
    out_dir.mkdir(parents=True, exist_ok=True)

    wb = _get_cached_workbook(data_only=True)
    ws = wb[sheet_name]
    field_to_col = export_mod.load_column_map(ws)

    if mode == "selected":
        checked_rows = [r["row"] for r in read_index_rows_filtered(series_number, equip_key, filters)
                         if r.get("export")]
        rows = export_mod.rows_to_export(ws, field_to_col, checked_rows, False)
    else:
        rows = export_mod.rows_to_export(ws, field_to_col, [], mode == "all")
        if filters:
            allowed_rows = {r["row"] for r in read_index_rows_filtered(series_number, equip_key, filters)}
            rows = [r for r in rows if r in allowed_rows]

    if not rows:
        return []

    key_col = field_to_col.get(etype["key_field"])
    filename_date = f" {datetime.date.today().isoformat()}" if include_date_in_filename else ""
    written = []
    used_names = set()
    for row_num in rows:
        values = export_mod.build_values_for_row(ws, field_to_col, row_num)
        key_val = export_mod.cell_to_str(ws.cell(row=row_num, column=key_col).value) if key_col else ""
        tag_part = export_mod.sanitize(key_val, f"Row{row_num}")
        base_name = f"{tag_part} {suffix}" if suffix else tag_part
        base_name = f"{base_name}{filename_date}"
        name = base_name
        n = 2
        while name in used_names:
            name = f"{base_name} ({n})"
            n += 1
        used_names.add(name)
        out_path = out_dir / f"{name}.pdf"

        if equip_key == "valve":
            export_mod.fill_pdf(export_mod.DEFAULT_TEMPLATE, values, out_path, flatten=flatten,
                                 add_signature=include_signature)
        else:
            export_mod.fill_pdf(export_mod.DEFAULT_TEMPLATE, values, out_path, flatten=flatten,
                                 add_signature=include_signature)
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
        key_col = field_to_col.get(etype["key_field"])
        keys = []
        for row_num in rows:
            key_val = export_mod.cell_to_str(ws.cell(row=row_num, column=key_col).value) if key_col else ""
            if key_val:
                keys.append((series_number, equip_key, key_val))
        if keys:
            bulk_set_status(keys, export=False)

    return written


# ---------------------------------------------------------------------------
# Duplicate-tag prevention
#
# The Tag / Equip # is the identifier everything else keys off: the Index
# list, the PDF filename, and - critically - the Installed/Submitted status
# store (equipment_status.json is keyed by this value). Two rows sharing a
# Tag wouldn't just be a display annoyance; the status tracker would
# silently conflate two different physical pieces of equipment as one.
# ---------------------------------------------------------------------------
def find_duplicate_row(series_number, equip_key, key_value, exclude_row=None):
    """Returns the row number of another row already using this exact Tag /
    Equip # (case-insensitive), or None if it's free to use."""
    etype = EQUIPMENT_TYPES[equip_key]
    target = str(key_value).strip().casefold()
    if not target:
        return None
    for entry in read_index_rows(series_number, equip_key):
        if entry["row"] == exclude_row:
            continue
        existing = str(entry.get(etype["key_field"]) or "").strip().casefold()
        if existing == target:
            return entry["row"]
    return None


# ---------------------------------------------------------------------------
# By-system breakdown, aggregated across every series - powers the Main
# Menu's dashboard (which otherwise only had one grand total per type).
# ---------------------------------------------------------------------------
def count_by_system_all_series(equip_key):
    """{'STEAM': 47, 'NATURAL GAS': 24, ..., '(No System Set)': 2} - the
    equipment type's System field, counted across every registered series
    combined. Rows with the key field filled in but no System value yet
    are bucketed under '(No System Set)' rather than silently dropped, so
    this always sums to exactly count_all_by_type()[equip_key] - the two
    numbers should never visibly disagree on screen."""
    etype = EQUIPMENT_TYPES[equip_key]
    system_field = etype["group_fields"][0]
    combined = {}
    unset = 0
    for series_number in list_series():
        try:
            rows = read_index_rows(series_number, equip_key)
        except KeyError:
            continue
        for entry in rows:
            value = str(entry.get(system_field) or "").strip()
            if value:
                combined[value] = combined.get(value, 0) + 1
            else:
                unset += 1
    result = dict(sorted(combined.items(), key=lambda kv: -kv[1]))  # busiest system first
    if unset:
        result["(No System Set)"] = unset
    return result


# ---------------------------------------------------------------------------
# Open the workbook itself directly (Settings -> "Open Excel File")
# ---------------------------------------------------------------------------
def open_workbook():
    open_file(WORKBOOK_PATH)


def open_sheet(series_number, equip_key):
    """Marks the given series+type's sheet as the workbook's active tab,
    saves that (a tiny metadata change - no data is touched), then opens
    the file with the OS's default app for .xlsx. Excel opens showing
    whichever sheet was active when the file was last saved, so this is
    a real jump-to-that-tab, not just 'open the workbook and hope'.

    Caveat worth knowing: if the workbook is ALREADY open in Excel, most
    Excel versions just bring the existing window to the front rather than
    re-reading the file from disk - so this can only land on a specific
    tab when nothing already has the file open."""
    sheet_name = get_sheet_name(series_number, equip_key)
    with _mutating_workbook() as wb:
        if sheet_name not in wb.sheetnames:
            raise KeyError(f"Workbook has no sheet named '{sheet_name}'")
        wb.active = wb.sheetnames.index(sheet_name)
    open_file(WORKBOOK_PATH)


# ---------------------------------------------------------------------------
# Desktop shortcut creation. Windows-only (uses the WScript.Shell COM object
# via a one-line PowerShell call, which ships with every modern Windows -
# no extra Python dependency like pywin32 needed, which also keeps the
# PyInstaller build simpler).
# ---------------------------------------------------------------------------
def _shortcut_target_and_args():
    """(target_exe, arguments) the shortcut should launch."""
    if getattr(sys, "frozen", False):
        return sys.executable, ""
    # Running as a plain script: point at pythonw.exe (no console window)
    # with this script as its argument, falling back to python.exe if
    # pythonw isn't found next to the interpreter for some reason.
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    target = str(pythonw) if pythonw.exists() else sys.executable
    script = str(HERE / "gui_app.py")
    return target, f'"{script}"'


def create_desktop_shortcut(shortcut_name="InstINDEX"):
    """Creates a .lnk on the Windows Desktop pointing at this app. Returns
    the shortcut path on success. Raises on any failure (no Desktop folder,
    not on Windows, PowerShell unavailable, etc.) - callers decide whether
    that's worth showing the user or failing silently."""
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
