# -*- coding: utf-8 -*-
"""
Single source of truth for every field on the Small Power and Control
Cable Inspection & Test Record (Form# YCQE-EI-113). Same contract
transmitter_schema.py/valve_schema.py/gauge_schema.py already follow - see
transmitter_schema.py's module docstring for what each field key means and
how LOG_COLUMNS/by_section/by_id/CONTROL_FIELD are used (by
data_access.py, export_small_power_cable_to_pdf.py, gui_app.py,
index_view.py).

Part of the Electrical equipment family added alongside Transmitter/
Valve/Gauge/Transformer Test - EQUIPMENT_TYPES in data_access.py carries
the per-type metadata that lets the rest of the app treat any number of
equipment types generically.

Unlike every other Electrical form, this one's real source PDF already
had its own correctly-positioned AcroForm fields (41 of them, authored by
whoever built the original document) - see small_power_cable_field_map.py
for how that changes the field_map/build story. "Project"/"Job No." exist
on the printed form but are NOT modeled here as schema fields (same
convention transmitter_schema.py/valve_schema.py use for their own
un-mapped header cells) - only Location is a real per-row field. There is
no signature field anywhere on the real source PDF for either
representative - hand-sign both after exporting.
"""
import re

FIELDS = []


def _add(id_, label, section, ftype="text", choices=None):
    FIELDS.append({
        "id": id_,
        "label": label,
        "section": section,
        "ftype": ftype,
        "choices": choices or [],
    })


# ------------------------------------------------ PART 1 - Project Description
_add("location", "Location", "part1")

# --------------------------------------------------- PART 2 - Cable Description
_add("cable_tag_number", "Cable Tag Number", "part2")
_add("cable_type", "Cable Type", "part2")
_add("system", "System", "part2")
_add("cable_size", "Cable Size", "part2")
_add("number_of_conductors", "Number of Conductors", "part2")
_add("cable_rated_voltage", "Cable Rated Voltage", "part2")

# ---------------------------------------------- PART 3 - Visual Inspection ---
VISUAL_INSPECTION_ITEMS = [
    "Cable size, type, location, installation, and routing are in accordance with the drawings."
    "(Check all connectors are tight)",
    "Bend radius is in accordance with project specifications and the cable jacket is free of kinks.",
    "Cable termination supports and support spacing is in accordance with drawings and project specifications.",
    "Installation is neat and evenly spaced.(Junction boxes are cleaned out & wires are dressed within panduit)",
    "Cable is free of surface damage.",
    "Correct cable tag is installed on both ends.",
    "Termination kit/materials are installed in accordance with the manufacturer's instructions.",
    "Conductors are properly identified.(Core markers are the same font, size & evenly spaced / alligned)",
    "Check phase location and marking (Left to Right, Top to Bottom, or Front to Rear) are in accordance "
    "with the drawings and project specifications.",
    "Insulation Test has been performed",
    "Enter all deficiencies and missing items on Form YCQE-PS-048 Rev.0",
]
for i, text in enumerate(VISUAL_INSPECTION_ITEMS, start=1):
    _add(f"vis_item_{i}_initial", f"{i}. {text} (Initial/NA)", "part3")

# --------------------------------------------------- PART 4 - Test Equipment -
for _row_n in (1, 2):
    _add(f"test_equip_{_row_n}_make", f"Test Equipment {_row_n} - Make", "part4")
    _add(f"test_equip_{_row_n}_model", f"Test Equipment {_row_n} - Model", "part4")
    _add(f"test_equip_{_row_n}_asset_serial", f"Test Equipment {_row_n} - Asset/Serial Number", "part4")
    _add(f"test_equip_{_row_n}_calibrated_on", f"Test Equipment {_row_n} - Calibrated On", "part4")

# ----------------------------------------------------- PART 5 - Test Results -
_add("insulation_cond_to_cond", "Insulation Resistance - Conductor to Conductor", "part5")
_add("insulation_cond_to_ground", "Insulation Resistance - Conductor to Ground", "part5")
_add("insulation_cond_to_armour", "Insulation Resistance - Conductor to Armour", "part5")
_add("continuity_cond_to_cond", "Continuity - Conductor to Conductor", "part5")
_add("continuity_cond_to_ground", "Continuity - Conductor to Ground", "part5")
_add("continuity_cond_to_armour", "Continuity - Conductor to Armour", "part5")

# ------------------------------------------------------- PART 6 - Remarks ----
# Three separate ruled lines on the real source PDF, not one multiline box.
_add("remarks_line1", "Remarks - Line 1", "part6")
_add("remarks_line2", "Remarks - Line 2", "part6")
_add("remarks_line3", "Remarks - Line 3", "part6")

# ----------------------------------------------- PART 7 - Inspected/Approved -
_add("yanda_rep_name", "Yanda Representative - Name", "part7")
_add("yanda_rep_date", "Yanda Representative - Date", "part7")
_add("client_rep_name", "Client Representative - Name", "part7")
_add("client_rep_date", "Client Representative - Date", "part7")


CONTROL_FIELD = {
    "id": "export_flag",
    "label": "Export to PDF (Y/N)",
    "section": "control",
    "ftype": "choice",
    "choices": ["Y", "N"],
}

LOG_COLUMNS = [CONTROL_FIELD] + FIELDS


def by_section(section):
    return [f for f in FIELDS if f["section"] == section]


def by_id(field_id):
    for f in FIELDS:
        if f["id"] == field_id:
            return f
    return None


SECTION_TITLES = {
    "control": "Status",
    "part1": "PART 1 – Project Description",
    "part2": "PART 2 – Cable Description",
    "part3": "PART 3 – Visual Inspection",
    "part4": "PART 4 – Test Equipment",
    "part5": "PART 5 – Test Results",
    "part6": "PART 6 – Remarks",
    "part7": "PART 7 – Inspected/Approved By",
}

# Edit-form table layouts for gui_app.EditDialog - presentation only. Each
# row is (row label, [field id per column]); a column width of 0 stretches.
GRIDS = [
    {
        "row_header": "Check",
        "row_header_width": 0,
        "columns": [("Initial / NA", 100)],
        "rows": [(re.sub(r"\s*\(Initial/NA\)\s*$", "", by_id(f"vis_item_{n}_initial")["label"]),
                  [f"vis_item_{n}_initial"]) for n in range(1, 12)],
    },
    {
        "row_header": "",
        "row_header_width": 120,
        "columns": [("Make", 0), ("Model", 0), ("Asset/Serial #", 0), ("Calibrated On", 110)],
        "rows": [(f"Test Equipment {n}", [f"test_equip_{n}_{part}" for part in
                                          ("make", "model", "asset_serial", "calibrated_on")])
                 for n in (1, 2)],
    },
    {
        "row_header": "",
        "row_header_width": 150,
        "columns": [("Conductor–Conductor", 0), ("Conductor–Ground", 0), ("Conductor–Armour", 0)],
        "rows": [("Insulation Resistance", ["insulation_cond_to_cond", "insulation_cond_to_ground",
                                            "insulation_cond_to_armour"]),
                 ("Continuity", ["continuity_cond_to_cond", "continuity_cond_to_ground",
                                 "continuity_cond_to_armour"])],
    },
    {
        "row_header": "",
        "row_header_width": 50,
        "columns": [("Remarks", 0)],
        "rows": [(f"Line {n}", [f"remarks_line{n}"]) for n in (1, 2, 3)],
    },
]

if __name__ == "__main__":
    print(f"Total fields: {len(FIELDS)}")
    from collections import Counter
    c = Counter(f["section"] for f in FIELDS)
    for sec, n in c.items():
        print(f"  {sec}: {n}")
