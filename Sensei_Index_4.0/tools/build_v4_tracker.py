# -*- coding: utf-8 -*-
"""
Rebuilds Equipment_Inspection_Tracker.xlsx + series_registry.json for
Sensei Index 4.0: K1A excluded except Drain Tank 2, K1B heavily
cross-referenced against Instrumentation Master List.xlsx.

Run once from inside the Sensei_Index_4.0 folder:
    python tools/build_v4_tracker.py

Safe to re-run: it never overwrites a cell that already has a value (see
masterlist_etl.existing_tags - a tag already tracked anywhere in the kept
series is left completely untouched), it only appends genuinely new rows
and only runs the K1A archive step if series 29151 is still registered.
"""
import datetime
import json
import sys
from pathlib import Path

import openpyxl

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import transmitter_schema
import valve_schema
import masterlist_etl as etl

WORKBOOK_PATH = HERE / "Equipment_Inspection_Tracker.xlsx"
CONFIG_PATH = HERE / "series_registry.json"
MASTER_PATH = HERE / "Instrumentation Master List.xlsx"

TX_LABEL = {f["id"]: f["label"] for f in transmitter_schema.LOG_COLUMNS}
VLV_LABEL = {f["id"]: f["label"] for f in valve_schema.LOG_COLUMNS}

NOT_TRACKED_SHEET = "Not Tracked (Reference)"


def find_first_blank_row(ws, key_col):
    r = etl.FIRST_DATA_ROW
    while ws.cell(row=r, column=key_col).value not in (None, ""):
        r += 1
    return r


def write_transmitter_row(ws, row_num, cm, rec):
    values = {
        "tag": rec["tag"],
        "service": rec.get("service", ""),
        "pid_number": rec.get("pid", ""),
        "line_number": rec.get("line", ""),
        "make": rec.get("mfr", ""),
        "model": rec.get("model", ""),
        "transmitter_type": etl.TRANSMITTER_TYPE_LABEL.get(rec["func"], rec["type_desc"].title()),
    }
    for fid, val in values.items():
        col = cm.get(TX_LABEL[fid])
        if col and val:
            ws.cell(row=row_num, column=col).value = val


def write_valve_row(ws, row_num, cm, rec):
    values = {
        "equip_number": rec["tag"],
        "pid_number": rec.get("pid", ""),
        "line_number": rec.get("line", ""),
        "valve_type": etl.VALVE_TYPE_BY_PREFIX.get(rec["func"], "Other"),
        "valve_model": rec.get("model", ""),
    }
    pos = rec.get("positioner")
    if pos and pos.get("model"):
        values["positioner_model"] = pos["model"]
    for fid, val in values.items():
        col = cm.get(VLV_LABEL[fid])
        if col and val:
            ws.cell(row=row_num, column=col).value = val


def append_new_rows(wb, series_number, new_transmitters, new_valves):
    tx_name = f"Transmitter Log {series_number}"
    vlv_name = f"Valve Log {series_number}"
    added_tx = added_vlv = 0
    if new_transmitters and tx_name in wb.sheetnames:
        ws = wb[tx_name]
        cm = etl.load_column_map(ws)
        key_col = cm.get("Tag")
        r = find_first_blank_row(ws, key_col)
        for rec in new_transmitters:
            write_transmitter_row(ws, r, cm, rec)
            r += 1
            added_tx += 1
    if new_valves and vlv_name in wb.sheetnames:
        ws = wb[vlv_name]
        cm = etl.load_column_map(ws)
        key_col = cm.get("Equip #")
        r = find_first_blank_row(ws, key_col)
        for rec in new_valves:
            write_valve_row(ws, r, cm, rec)
            r += 1
            added_vlv += 1
    return added_tx, added_vlv


def _archived_name(original, wb):
    stamp = datetime.date.today().strftime("%y%m%d")
    prefix = "DEL "
    budget = 31 - len(prefix) - len(stamp) - 1
    candidate = f"{prefix}{original[:budget]} {stamp}"
    base, n = candidate, 2
    while candidate in wb.sheetnames:
        suffix = f"-{n}"
        candidate = base[: 31 - len(suffix)] + suffix
        n += 1
    return candidate


def archive_series(wb, cfg, series_number):
    entry = next((s for s in cfg["series"] if s["number"] == series_number), None)
    if entry is None:
        return False  # already archived on a previous run
    for key in ("transmitter_sheet", "valve_sheet"):
        name = entry.get(key)
        if name and name in wb.sheetnames:
            ws = wb[name]
            ws.title = _archived_name(name, wb)
            ws.sheet_state = "hidden"
    cfg["series"] = [s for s in cfg["series"] if s["number"] != series_number]
    return True


def create_series_from_template(wb, template_number, new_number, new_label,
                                  n_transmitters, n_valves):
    """Mirrors data_access.add_series(): copy a template series' two sheets,
    reattach data validations + conditional formatting (copy_worksheet
    silently drops both), wipe the copied data rows, rename."""
    created = {}
    for equip_key, sheet_prefix, count in (
        ("transmitter", "Transmitter Log", n_transmitters),
        ("valve", "Valve Log", n_valves),
    ):
        if not count:
            continue
        src_name = f"{sheet_prefix} {template_number}"
        new_name = f"{sheet_prefix} {new_number}"
        if new_name in wb.sheetnames:
            created[f"{equip_key}_sheet"] = new_name
            continue  # already created on a previous run
        src_ws = wb[src_name]
        new_ws = wb.copy_worksheet(src_ws)
        new_ws.title = new_name

        for dv in src_ws.data_validations.dataValidation:
            new_ws.add_data_validation(dv)
        for cf in src_ws.conditional_formatting:
            for rule in cf.rules:
                new_ws.conditional_formatting.add(str(cf.sqref), rule)

        for r in range(etl.FIRST_DATA_ROW, new_ws.max_row + 1):
            for c in range(1, new_ws.max_column + 1):
                new_ws.cell(row=r, column=c).value = None

        created[f"{equip_key}_sheet"] = new_name
    return created


def write_not_tracked_sheet(wb, other_type_counts, unmatched_accessories):
    if NOT_TRACKED_SHEET in wb.sheetnames:
        del wb[NOT_TRACKED_SHEET]
    ws = wb.create_sheet(NOT_TRACKED_SHEET)
    ws["A1"] = "Instrument types from the Master List that this tool doesn't track"
    ws["A2"] = ("These have no Transmitter Inspection & Test Record or Valve Check Record in "
                "this system (gauges, switches, thermowells, downhole fiber, motor/VFD signals, "
                "relief/manual valves, analyzer elements, etc.) - listed here, not silently "
                "dropped, so nothing from the master list disappears without a trace.")
    ws["A4"] = "Type Description"
    ws["B4"] = "Count in K1B + Drain Tank 2 scope"
    r = 5
    for t, n in other_type_counts.most_common():
        ws.cell(row=r, column=1).value = t
        ws.cell(row=r, column=2).value = n
        r += 1
    r += 1
    if unmatched_accessories:
        ws.cell(row=r, column=1).value = "Positioner/accessory rows with no matching valve tag:"
        r += 1
        for acc in unmatched_accessories:
            ws.cell(row=r, column=1).value = acc["tag"]
            ws.cell(row=r, column=2).value = acc["type_desc"]
            r += 1
    ws.column_dimensions["A"].width = 46
    ws.column_dimensions["B"].width = 30


def main():
    report = etl.build_report(str(MASTER_PATH), str(WORKBOOK_PATH), str(CONFIG_PATH))
    wb = openpyxl.load_workbook(WORKBOOK_PATH, data_only=False)
    cfg = json.load(open(CONFIG_PATH, encoding="utf-8"))

    print("Archiving K1A-excluded series...")
    for num in etl.EXCLUDED_SERIES:
        changed = archive_series(wb, cfg, num)
        print(f"  series {num}: {'archived' if changed else 'already archived'}")

    summary = []
    for sheet_name, info in report["per_sheet"].items():
        route = info["route"]
        if route["route"] == "append_existing":
            series_number = route["series_number"]
            added_tx, added_vlv = append_new_rows(
                wb, series_number, info["new_transmitters"], info["new_valves"])
            summary.append((sheet_name, series_number, added_tx, added_vlv))
        elif route["route"] == "new_series":
            series_number = route["series_number"]
            existing_entry = next((s for s in cfg["series"] if s["number"] == series_number), None)
            sheets = create_series_from_template(
                wb, template_number=100, new_number=series_number,
                new_label=route["series_name"],
                n_transmitters=len(info["new_transmitters"]),
                n_valves=len(info["new_valves"]))
            if sheets and existing_entry is None:
                entry = {"number": series_number, "name": route["series_name"]}
                entry.update(sheets)
                cfg["series"].append(entry)
            added_tx, added_vlv = append_new_rows(
                wb, series_number, info["new_transmitters"], info["new_valves"])
            summary.append((sheet_name, series_number, added_tx, added_vlv))

    write_not_tracked_sheet(wb, report["other_type_counts"], report["unmatched_accessories"])

    wb.save(WORKBOOK_PATH)
    with open(CONFIG_PATH, "w", encoding="utf-8") as fh:
        json.dump(cfg, fh, indent=2)

    print("\nRows added:")
    for sheet_name, series_number, added_tx, added_vlv in summary:
        print(f"  {sheet_name} -> series {series_number}: +{added_tx} transmitters, +{added_vlv} valves")
    print(f"\nSaved {WORKBOOK_PATH}")
    print(f"Saved {CONFIG_PATH}")


if __name__ == "__main__":
    main()
