# -*- coding: utf-8 -*-
"""
1. Gap-fills the current workbook from a user-supplied copy: for every
   Transmitter/Valve Log sheet, any cell that's blank in the current
   workbook but has a value in the supplied copy gets that value copied
   in. Never overwrites a cell that already has a value in the current
   workbook, even if the supplied copy disagrees - those are reported as
   conflicts and left alone.
2. Upgrades every equipment-log sheet's "export flag" conditional
   formatting so the WHOLE ROW highlights green when the flag is "Y",
   not just that one cell - a formula rule ($A<row>="Y") rather than a
   static fill, so it keeps working as rows are edited later, in the app
   or directly in Excel. Leaves every other existing conditional-format
   rule (N/A highlighting, etc.) untouched. Valve sheets get this rule
   added fresh; Transmitter/Gauge sheets have a same-purpose single-cell
   rule that gets replaced.

Usage: python3 merge_field_data.py <source_workbook> <target_workbook> [--apply]
Without --apply, reports what it WOULD do and writes nothing.
"""
import copy
import json
import sys
from pathlib import Path

import openpyxl
from openpyxl.formatting.rule import FormulaRule
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

HEADER_ROW = 3
FIRST_DATA_ROW = 4
EXPORT_FLAG_LABEL = "Export to PDF (Y/N)"


def header_map(ws, header_row=HEADER_ROW):
    m = {}
    for c in range(1, ws.max_column + 1):
        label = ws.cell(row=header_row, column=c).value
        if label:
            m[str(label).strip()] = c
    return m


def cell_blank(v):
    return v is None or (isinstance(v, str) and v.strip() == "")


def merge_sheet(src_ws, dst_ws, sheet_name):
    src_map = header_map(src_ws)
    dst_map = header_map(dst_ws)
    common_labels = set(src_map) & set(dst_map)
    filled = []
    conflicts = []
    max_r = min(src_ws.max_row, dst_ws.max_row)
    for r in range(FIRST_DATA_ROW, max_r + 1):
        for label in common_labels:
            dc, sc = dst_map[label], src_map[label]
            dv = dst_ws.cell(row=r, column=dc).value
            sv = src_ws.cell(row=r, column=sc).value
            if cell_blank(dv) and not cell_blank(sv):
                filled.append((sheet_name, r, label, sv))
            elif not cell_blank(dv) and not cell_blank(sv) and str(dv).strip() != str(sv).strip():
                conflicts.append((sheet_name, r, label, dv, sv))
    return filled, conflicts


GREEN_FILL = PatternFill(start_color="FFC6EFCE", end_color="FFC6EFCE", fill_type="solid")
GREEN_FONT = Font(color="FF006100")


def upgrade_row_highlight(ws):
    """Removes any existing single-cell 'export flag = Y' rule scoped to
    just column A, then adds a fresh formula rule spanning the whole row.
    Any other conditional-formatting rule on the sheet (N/A highlighting,
    etc.) is left exactly as-is. Idempotent: a sheet that already has the
    full-row formula rule (a previous run of this script) is left alone
    rather than growing a duplicate rule."""
    expected_formula = [f'$A{FIRST_DATA_ROW}="Y"']
    for cf in ws.conditional_formatting:
        for rule in cf.rules:
            if rule.type == "expression" and rule.formula == expected_formula:
                return 0, None  # already upgraded, nothing to do

    # _cf_rules is keyed by the ConditionalFormatting object itself (not
    # by its sqref as a string - str(that object) prints as
    # "<ConditionalFormatting A5:A304>", which never matches a bare
    # "A5:A304" string, so a string-keyed lookup here silently deletes
    # nothing). Collect the actual matching objects instead.
    to_remove = []
    for cf in ws.conditional_formatting:
        sqref_str = str(cf.sqref)
        if sqref_str.split(":")[0].rstrip("0123456789") != "A":
            continue
        for rule in cf.rules:
            if rule.type == "cellIs" and rule.operator == "equal" and rule.formula == ['"Y"']:
                to_remove.append(cf)
                break

    for cf in to_remove:
        del ws.conditional_formatting._cf_rules[cf]

    last_col_letter = get_column_letter(ws.max_column)
    full_row_range = f"A{FIRST_DATA_ROW}:{last_col_letter}{ws.max_row}"
    rule = FormulaRule(formula=expected_formula, font=copy.copy(GREEN_FONT), fill=copy.copy(GREEN_FILL))
    ws.conditional_formatting.add(full_row_range, rule)
    return len(to_remove), full_row_range


def main():
    if len(sys.argv) < 3:
        sys.exit("usage: merge_field_data.py <source_workbook> <target_workbook> [--apply]")
    source_path = Path(sys.argv[1])
    target_path = Path(sys.argv[2])
    apply = "--apply" in sys.argv[3:]

    src_wb = openpyxl.load_workbook(source_path, data_only=False)
    dst_wb = openpyxl.load_workbook(target_path, data_only=False)

    registry_path = target_path.parent / "series_registry.json"
    series_numbers = [s["number"] for s in json.loads(registry_path.read_text())["series"]]

    all_filled = []
    all_conflicts = []
    for sn in series_numbers:
        for prefix in ("Transmitter Log", "Valve Log"):
            sheet = f"{prefix} {sn}"
            if sheet not in src_wb.sheetnames or sheet not in dst_wb.sheetnames:
                continue
            filled, conflicts = merge_sheet(src_wb[sheet], dst_wb[sheet], sheet)
            all_filled.extend(filled)
            all_conflicts.extend(conflicts)

    print(f"Data merge: {len(all_filled)} cells would be filled, {len(all_conflicts)} conflicts left untouched.")
    for sheet_name, r, label, dv, sv in all_conflicts:
        print(f"  CONFLICT {sheet_name} row {r} [{label}]: current={dv!r} vs supplied={sv!r} - left as current")

    if apply:
        for sheet_name, r, label, sv in all_filled:
            dst_map = header_map(dst_wb[sheet_name])
            dst_wb[sheet_name].cell(row=r, column=dst_map[label]).value = sv
        print(f"Applied {len(all_filled)} cell fills.")

    print()
    print("Row-highlight upgrade:")
    for sn in series_numbers:
        for prefix in ("Transmitter Log", "Valve Log", "Gauge Log"):
            sheet = f"{prefix} {sn}"
            if sheet not in dst_wb.sheetnames:
                continue
            if apply:
                removed, new_range = upgrade_row_highlight(dst_wb[sheet])
                if new_range is None:
                    print(f"  {sheet}: already upgraded, skipped")
                else:
                    print(f"  {sheet}: removed {removed} old cell-only rule(s), added row rule over {new_range}")
            else:
                print(f"  {sheet}: (dry run - would upgrade)")

    if apply:
        dst_wb.save(target_path)
        print(f"\nSaved {target_path}.")
    else:
        print("\nDry run only - nothing written. Re-run with --apply to write changes.")


if __name__ == "__main__":
    main()
