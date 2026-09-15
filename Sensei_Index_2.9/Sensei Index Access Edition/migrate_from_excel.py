# -*- coding: utf-8 -*-
"""
One-time migration: copies every real row - Instrumentation (Transmitter/
Valve) AND Electrical (EHT Removal, EHT & RTD, EHT & RTD Pre-Insulation,
Torqueing, Transformer Test, Small Power Cable, General Equip Install) -
out of the Excel edition's own Equipment_Inspection_Tracker.xlsx /
Electrical_Inspection_Tracker.xlsx and into this edition's SenseiIndex.
accdb: every series/zone (with its friendly display name), every field on
every row, and each row's own Installed/Submitted/Accepted/Export status.
Read-only against the Excel side - never writes to either .xlsx file.

WHY THIS IS A SEPARATE SCRIPT, NOT SOMETHING access_gui_app.py DOES ITSELF
----------------------------------------------------------------------------
This only ever needs to run ONCE, right after getting a fresh SenseiIndex.
accdb and before using the Access Edition for anything else - it has
nothing to do with this app's own day-to-day workflow, so it doesn't
belong behind a button in the UI (as opposed to, say, Master List import,
which is a recurring, ongoing part of using the app). It reuses data_
access.py/electrical_data_access.py's own read functions on the Excel
side (list_series/read_index_rows/read_full_row/get_status, etc. - the
exact same functions gui_app.py itself calls) and access_data_access.py/
access_electrical_data_access.py's own write functions on the Access
side, so there's no separate "how do I read an xlsx row" or "how do I
write an Access row" logic to get wrong here - just wiring the two
together, field-id dict in, field-id dict out (read_full_row() on the
Excel side already returns {field_id: value}, keyed exactly the way
save_row() on the Access side expects it - both sides derive their own
field lists from the SAME *_schema.py files, so there's no translation
step at all).

SAFETY
----------
Refuses to run against a SenseiIndex.accdb that already has ANY series or
zones registered, unless --force is passed - this edition's own
find_first_blank_row() always INSERTs a new row (there's no "blank row to
reuse" concept for a real database - see access_schema.py's own
docstring), so running this twice against the same Access db would
duplicate every row, not overwrite it. If you need to re-run it, first
replace SenseiIndex.accdb with a fresh one (python build_access_database.
py) - that wipes and rebuilds the schema from scratch, so never run that
against an Access db that already has real migrated data you want to
keep.

USAGE
    python migrate_from_excel.py             # migrate everything
    python migrate_from_excel.py --dry-run   # show what WOULD move, write nothing
    python migrate_from_excel.py --force     # migrate even if the Access db already has data (WILL duplicate rows)
"""
import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXCEL_EDITION_DIR = HERE.parent / "Sensei Index 2.9"
if str(EXCEL_EDITION_DIR) not in sys.path:
    sys.path.insert(0, str(EXCEL_EDITION_DIR))

import access_data_access as da
import access_electrical_data_access as eda
import data_access as excel_da
import electrical_data_access as excel_eda


def migrate_instrumentation(dry_run):
    total_rows = 0
    series_numbers = excel_da.list_series()
    print(f"Instrumentation: {len(series_numbers)} series in Equipment_Inspection_Tracker.xlsx")
    for series_number in series_numbers:
        name = excel_da.get_series_name(series_number)
        label = f"{series_number} ({name})" if name else str(series_number)
        if not dry_run:
            da.add_series(series_number)
            if name:
                da.set_series_name(series_number, name)
        series_row_count = 0
        for equip_key, etype in excel_da.EQUIPMENT_TYPES.items():
            rows = excel_da.read_index_rows(series_number, equip_key)
            if not rows:
                continue
            key_field = etype["key_field"]
            for entry in rows:
                row_num = entry["row"]
                values = excel_da.read_full_row(series_number, equip_key, row_num)
                key_value = values.get(key_field)
                status = excel_da.get_status(series_number, equip_key, key_value) if key_value else None
                if not dry_run:
                    new_row_id = da.find_first_blank_row(series_number, equip_key)
                    da.save_row(series_number, equip_key, new_row_id, values, source="migration")
                    if key_value and status:
                        da.set_status(series_number, equip_key, key_value, **status)
                series_row_count += 1
            print(f"    series {label}: {len(rows)} {etype['label']} row(s)")
        total_rows += series_row_count
    return total_rows


def migrate_electrical(dry_run):
    total_rows = 0
    zone_names = excel_eda.list_zones()
    print(f"Electrical: {len(zone_names)} zone(s) in Electrical_Inspection_Tracker.xlsx")
    for zone_name in zone_names:
        if not dry_run:
            eda.add_zone(zone_name)
        zone_row_count = 0
        for equip_key, etype in excel_eda.ELECTRICAL_EQUIPMENT_TYPES.items():
            rows = excel_eda.read_index_rows(zone_name, equip_key)
            if not rows:
                continue
            key_field = etype["key_field"]
            for entry in rows:
                row_num = entry["row"]
                values = excel_eda.read_full_row(zone_name, equip_key, row_num)
                key_value = values.get(key_field)
                status = excel_eda.get_electrical_status(zone_name, equip_key, key_value) if key_value else None
                if not dry_run:
                    new_row_id = eda.find_first_blank_row(zone_name, equip_key)
                    eda.save_row(zone_name, equip_key, new_row_id, values)
                    if key_value and status:
                        eda.set_electrical_status(zone_name, equip_key, key_value, **status)
                zone_row_count += 1
            print(f"    zone {zone_name!r}: {len(rows)} {etype['label']} row(s)")
        total_rows += zone_row_count
    return total_rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                         help="Show what would be migrated - writes nothing to SenseiIndex.accdb.")
    parser.add_argument("--force", action="store_true",
                         help="Migrate even if SenseiIndex.accdb already has series/zones registered "
                              "(will duplicate any rows already there - see this script's own docstring).")
    args = parser.parse_args()

    if not args.dry_run and not args.force:
        existing_series = da.list_series()
        existing_zones = eda.list_zones()
        if existing_series or existing_zones:
            print(
                f"SenseiIndex.accdb already has {len(existing_series)} series and "
                f"{len(existing_zones)} zone(s) registered - refusing to migrate on top of "
                f"that (it would duplicate every row already there). Re-run with --force to "
                f"do it anyway, or replace SenseiIndex.accdb with a fresh one first "
                f"(python build_access_database.py) if you meant to start over."
            )
            sys.exit(1)

    if args.dry_run:
        print("DRY RUN - nothing will be written to SenseiIndex.accdb.\n")

    instrumentation_rows = migrate_instrumentation(args.dry_run)
    print()
    electrical_rows = migrate_electrical(args.dry_run)

    print()
    verb = "would move" if args.dry_run else "moved"
    print(f"Done - {verb} {instrumentation_rows} Instrumentation row(s) and "
          f"{electrical_rows} Electrical row(s) into SenseiIndex.accdb.")
    if not args.dry_run:
        print("Open access_gui_app.py (or the .exe) to see them.")


if __name__ == "__main__":
    main()
