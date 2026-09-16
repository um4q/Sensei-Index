# -*- coding: utf-8 -*-
"""
One-time migration: adds "Gauge Log <series>" sheets (matching the
existing Transmitter Log / Valve Log convention) to every series
currently in series_registry.json, then seeds Gauge Log 29103 with the
15 real gauges from the customer-supplied gauge serial list (Certificate #
read onto gauge_schema's serial_number field - see the module docstring
note below on that specific mapping choice).

Structure is borrowed from an existing Transmitter Log sheet (nav-row
hyperlink, freeze panes, row heights, header-row/group-row cell styling)
via copy_worksheet(), then every value/data-validation/conditional-format/
merge from that copy is stripped and rebuilt from gauge_schema.LOG_COLUMNS
- the same "copy structure, then strip and rebuild content" approach
data_access.add_series() already uses for a new SERIES of an existing
equipment type; this is the equivalent one-time move for an entirely new
EQUIPMENT TYPE across every existing series.

Purely additive: never touches an existing Transmitter/Valve sheet, an
existing row, or series_registry.json's existing keys - only appends new
sheets and a new "gauge_sheet" key per series entry. Safe to inspect with
--dry-run first; running it twice raises rather than silently duplicating
sheets (matches add_series()'s own guard).

Run once from inside the Sensei_Index_4.0 folder:
    python tools/add_gauge_equipment_type.py [--dry-run] [--workbook PATH]
"""
import argparse
import sys
from pathlib import Path

import openpyxl
from openpyxl.formatting.rule import CellIsRule
from openpyxl.styles import Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))

import gauge_schema

WORKBOOK_PATH = HERE / "Equipment_Inspection_Tracker.xlsx"
REGISTRY_PATH = HERE / "series_registry.json"
STYLE_SOURCE_SHEET = "Transmitter Log 100"
HEADER_ROW = 3
FIRST_DATA_ROW = 4
TEMPLATE_SHEET_NAME = "Gauge Log TEMPLATE"

# The serial list PDF's own column is labeled "Certificate #", not "Serial
# Number" - there's no separate serial-number column in that source at
# all, and the app has nowhere else to put a calibration-certificate
# reference for a gauge. Mapped onto serial_number (the field that
# actually reaches "Serial Number:" on the exported PDF) as the closest
# real fit, disclosed here and in the session's own summary to the user
# rather than done silently - correct it per-row in the app if
# "Certificate #" turns out to mean something else in practice.
GAUGE_29103_ROWS = [
    {"tag": "29103-PG -0903", "service": "29103-V-004 MAINLINE SEPARATOR",
     "gauge_type": "PRESSURE GAUGE", "pid_number": "29103-25J-002-01", "line_number": "",
     "model": "233.34", "make": "WIKA", "installation_details": "9000-70F-010-01",
     "serial_number": "109865"},
    {"tag": "29103-PG -0905", "service": "29103-V-004 MAINLINE SEPARATOR PSE RELIEF PRESSURE",
     "gauge_type": "PRESSURE GAUGE", "pid_number": "29103-25J-002-01",
     "line_number": '29103-6"-PG-1901-BAPD0-64H-ET',
     "model": "233.34", "make": "WIKA", "installation_details": "9000-70F-010-01",
     "serial_number": "109860"},
    {"tag": "29103-TG -0905", "service": "29103-V-004 MAINLINE SEPARATOR",
     "gauge_type": "TEMPERATURE GAUGE", "pid_number": "29103-25J-002-01", "line_number": "",
     "model": "TG53.5Z", "make": "WIKA", "installation_details": "9000-70F-014-01",
     "serial_number": "S003427365-2-1"},
    {"tag": "29103-PG -0906", "service": "29103-P-001A DISCHARGE PRESSURE",
     "gauge_type": "PRESSURE GAUGE", "pid_number": "29103-25J-003-01",
     "line_number": '29103-6"-HC-1904-BAPC0-64H-ET',
     "model": "233.34", "make": "WIKA", "installation_details": "9000-70F-010-01",
     "serial_number": "109850"},
    {"tag": "29103-PG -0907", "service": "29103-P-001B DISCHARGE PRESSURE",
     "gauge_type": "PRESSURE GAUGE", "pid_number": "29103-25J-003-01",
     "line_number": '29103-6"-HC-1907-BAPC0-64H-ET',
     "model": "233.34", "make": "WIKA", "installation_details": "9000-70F-010-01",
     "serial_number": "109843"},
    {"tag": "29103-PG -0908", "service": "29103-P-001A SUCTION PRESSURE",
     "gauge_type": "PRESSURE GAUGE", "pid_number": "29103-25J-003-01",
     "line_number": '29103-8"-HC-1903-BAPC0-64H-ET',
     "model": "233.34", "make": "WIKA", "installation_details": "9000-70F-010-01",
     "serial_number": "109868"},
    {"tag": "29103-PG -0909", "service": "29103-P-001B SUCTION PRESSURE",
     "gauge_type": "PRESSURE GAUGE", "pid_number": "29103-25J-003-01",
     "line_number": '29103-8"-HC-1906-BAPC0-64H-ET',
     "model": "233.34", "make": "WIKA", "installation_details": "9000-70F-010-01",
     "serial_number": "109863"},
    {"tag": "29103-PG -0911", "service": "29103-P-001A SUCTION PRESSURE",
     "gauge_type": "PRESSURE GAUGE", "pid_number": "29103-25J-003-01",
     "line_number": '29103-8"-HC-1903-BAPC0-64H-ET',
     "model": "233.34", "make": "WIKA", "installation_details": "9000-70F-010-01",
     "serial_number": "109866"},
    {"tag": "29103-PG -0912", "service": "29103-P-001B SUCTION PRESSURE",
     "gauge_type": "PRESSURE GAUGE", "pid_number": "29103-25J-003-01",
     "line_number": '29103-8"-HC-1906-BAPC0-64H-ET',
     "model": "233.34", "make": "WIKA", "installation_details": "9000-70F-010-01",
     "serial_number": "109864"},
    {"tag": "29103-TG -0910", "service": "29103-P-001A/B DISCHARGE FLOWLINE TEMPTERATURE",
     "gauge_type": "TEMPERATURE GAUGE", "pid_number": "29103-25J-003-01",
     "line_number": '29103-6"-HC-1910-BAPC0-64H-ET',
     "model": "TG53.5Z", "make": "WIKA", "installation_details": "9000-70F-014-01",
     "serial_number": "S003427365-3-1"},
    {"tag": "29103-PG -1102", "service": "PAD A SPARGE STEAM TO PRODUCED VAPOR LINE",
     "gauge_type": "PRESSURE GAUGE", "pid_number": "29103-25J-102-01",
     "line_number": '29103-2"-ST-1001-DASB0-64H',
     "model": "233.34", "make": "WIKA", "installation_details": "9000-70F-010-01",
     "serial_number": ""},
    {"tag": "29103-PG -1105", "service": "PAD A BLANKET GAS TO PRODUCED VAPOR LINE",
     "gauge_type": "PRESSURE GAUGE", "pid_number": "29103-25J-103-01",
     "line_number": '29103-2"-FG-1112-DLHB0-38H-ET',
     "model": "233.34", "make": "WIKA", "installation_details": "9000-70F-010-01",
     "serial_number": "109779"},
    {"tag": "29103-TG -1401", "service": "PAD A TEST FLUIDS FROM PRODUCTION WELL",
     "gauge_type": "TEMPERATURE GAUGE", "pid_number": "29103-25J-106-01",
     "line_number": '29103-4"-PE-1803-DAPC0-64H-ET',
     "model": "TG53.5Z", "make": "WIKA", "installation_details": "9000-70F-014-01",
     "serial_number": ""},
    {"tag": "29103-PG -2102", "service": "PAD R SPARGE STEAM TO PRODUCED VAPOR LINE",
     "gauge_type": "PRESSURE GAUGE", "pid_number": "29103-25J-202-01",
     "line_number": '29103-2"-ST-2001-DASB0-64H',
     "model": "233.34", "make": "WIKA", "installation_details": "9000-70F-010-01",
     "serial_number": "109742"},
    {"tag": "29103-PG -2105", "service": "PAD R BLANKET GAS TO PRODUCED VAPOR LINE",
     "gauge_type": "PRESSURE GAUGE", "pid_number": "29103-25J-203-01",
     "line_number": '29103-2"-FG-2112-DLHB0-38H-ET',
     "model": "233.34", "make": "WIKA", "installation_details": "9000-70F-010-01",
     "serial_number": "109778"},
]
# Every row above came from a single-page, single-P&ID-area (29103)
# source list, so "system" (this app's usual group-by field for the Index
# table) is filled in uniformly rather than guessed per row.
for _row in GAUGE_29103_ROWS:
    _row.setdefault("system", "PRODUCED GAS")


def build_template_sheet(wb):
    if STYLE_SOURCE_SHEET not in wb.sheetnames:
        raise KeyError(f"Style source sheet '{STYLE_SOURCE_SHEET}' not found in workbook.")
    if TEMPLATE_SHEET_NAME in wb.sheetnames:
        raise ValueError(f"'{TEMPLATE_SHEET_NAME}' already exists - a previous run wasn't cleaned up.")

    src_ws = wb[STYLE_SOURCE_SHEET]
    ws = wb.copy_worksheet(src_ws)
    ws.title = TEMPLATE_SHEET_NAME

    # Strip everything the source sheet had that's specific to ITS
    # (completely different) column layout: data validations, conditional
    # formatting, merged group-header cells, and every value from row 2
    # down (row 1's "<< Dashboard" nav hyperlink is left alone).
    ws.data_validations.dataValidation = []
    for rng in list(ws.conditional_formatting._cf_rules.keys()):
        del ws.conditional_formatting._cf_rules[rng]
    for rng in list(ws.merged_cells.ranges):
        ws.unmerge_cells(str(rng))
    for r in range(2, ws.max_row + 1):
        for c in range(1, ws.max_column + 1):
            ws.cell(row=r, column=c).value = None

    # Rebuild row 2 (section group labels, merged across each section's
    # own column span) and row 3 (field labels) from gauge_schema, reusing
    # whichever row-2/row-3 cell styling the copy already carries (font,
    # fill, borders, alignment) rather than hand-copying style objects -
    # simpler and exactly matches how the source sheet's own header looks.
    sections = list(dict.fromkeys(f["section"] for f in gauge_schema.LOG_COLUMNS))
    col = 1
    for section in sections:
        fields = [f for f in gauge_schema.LOG_COLUMNS if f["section"] == section]
        section_start = col
        for field in fields:
            ws.cell(row=HEADER_ROW, column=col).value = field["label"]
            col += 1
        section_end = col - 1
        ws.cell(row=2, column=section_start).value = gauge_schema.SECTION_TITLES.get(section, section.title())
        if section_end > section_start:
            ws.merge_cells(start_row=2, start_column=section_start, end_row=2, end_column=section_end)
    last_col = col - 1
    return ws, last_col


def apply_validation_and_formatting(ws):
    """Adds the doc_status dropdown and the export-flag "Y" highlight
    directly to ws, building fresh DataValidation/Rule objects every call -
    reusing the SAME object across multiple worksheets risks openpyxl
    quietly mis-serializing which sheet a validation/rule actually belongs
    to, so this is called once per final per-series sheet rather than once
    on a template that then gets copied."""
    from openpyxl.utils import get_column_letter

    # Data validation: doc_status is the one choice-type field in gauge's
    # own schema (besides the control column, handled separately below) -
    # same inline-list approach tools/migrate_engineering_index_columns.py
    # uses for this exact field on the Transmitter/Valve sheets.
    doc_status_field = gauge_schema.by_id("doc_status")
    doc_status_col = next(i + 1 for i, f in enumerate(gauge_schema.LOG_COLUMNS) if f["id"] == "doc_status")
    dv = DataValidation(type="list", formula1=f'"{",".join(doc_status_field["choices"])}"', allow_blank=True)
    ws.add_data_validation(dv)
    dv_col_letter = get_column_letter(doc_status_col)
    dv.add(f"{dv_col_letter}{FIRST_DATA_ROW}:{dv_col_letter}{ws.max_row}")

    # Conditional formatting: highlight "Y" in the export-flag column
    # (always column A) - Excel's built-in "Green Fill with Dark Green
    # Text" preset, matching the same rule already on every Transmitter/
    # Valve sheet's own column A.
    green_fill = PatternFill(start_color="FFC6EFCE", end_color="FFC6EFCE", fill_type="solid")
    green_font = Font(color="FF006100")
    rule = CellIsRule(operator="equal", formula=['"Y"'], font=green_font, fill=green_fill)
    ws.conditional_formatting.add(f"A{FIRST_DATA_ROW}:A{ws.max_row}", rule)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--workbook", default=str(WORKBOOK_PATH), help="Path to the workbook to migrate")
    ap.add_argument("--registry", default=str(REGISTRY_PATH),
                     help="Path to series_registry.json to read/update (default: the real one) - "
                          "override together with --workbook when testing against scratch copies "
                          "of both, so a test run can never touch the real registry.")
    ap.add_argument("--dry-run", action="store_true",
                     help="Build and report everything, but don't save - inspect before committing.")
    args = ap.parse_args()

    workbook_path = Path(args.workbook)
    registry_path = Path(args.registry)
    wb = openpyxl.load_workbook(workbook_path, data_only=False)

    import json
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    series_numbers = [s["number"] for s in registry["series"]]

    already_registered = [s["number"] for s in registry["series"] if "gauge_sheet" in s]
    if already_registered:
        sys.exit(f"ERROR: these series already have a gauge_sheet registered: {already_registered}. "
                  f"This migration has already run - nothing to do.")

    print(f"Building '{TEMPLATE_SHEET_NAME}' from '{STYLE_SOURCE_SHEET}'...")
    template_ws, last_col = build_template_sheet(wb)
    print(f"  {len(gauge_schema.LOG_COLUMNS)} columns written (through column {last_col}).")

    print(f"\nCreating a Gauge Log sheet for {len(series_numbers)} series: {series_numbers}")
    new_sheet_names = {}
    for series_number in series_numbers:
        new_name = f"Gauge Log {series_number}"
        if new_name in wb.sheetnames:
            sys.exit(f"ERROR: sheet '{new_name}' already exists in the workbook.")
        new_ws = wb.copy_worksheet(template_ws)
        new_ws.title = new_name
        # copy_worksheet() silently drops data validations and conditional
        # formatting (same limitation data_access.add_series() already
        # documents and works around) - add both fresh on the real sheet
        # rather than trying to carry over the template's own.
        apply_validation_and_formatting(new_ws)
        new_sheet_names[series_number] = new_name
        print(f"  {new_name}")

    del wb[TEMPLATE_SHEET_NAME]

    print(f"\nSeeding {len(GAUGE_29103_ROWS)} real gauge rows into 'Gauge Log 29103'...")
    field_ids = [f["id"] for f in gauge_schema.LOG_COLUMNS]
    ws29103 = wb[new_sheet_names[29103]]
    for i, row_data in enumerate(GAUGE_29103_ROWS):
        excel_row = FIRST_DATA_ROW + i
        ws29103.cell(row=excel_row, column=1).value = "N"  # export_flag, control column
        for fid, value in row_data.items():
            col = field_ids.index(fid) + 1
            ws29103.cell(row=excel_row, column=col).value = value
    print(f"  Rows {FIRST_DATA_ROW}-{FIRST_DATA_ROW + len(GAUGE_29103_ROWS) - 1} written.")

    if args.dry_run:
        print("\n--dry-run: not saving, and not updating series_registry.json.")
        return

    wb.save(workbook_path)
    print(f"\nSaved {workbook_path.name}.")

    for s in registry["series"]:
        s["gauge_sheet"] = new_sheet_names[s["number"]]
    registry_path.write_text(json.dumps(registry, indent=2) + "\n", encoding="utf-8")
    print(f"Updated {registry_path.name} with a gauge_sheet entry for every series.")


if __name__ == "__main__":
    main()
