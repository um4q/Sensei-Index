# -*- coding: utf-8 -*-
"""
Single source of truth for every field on the Transformer Test Record.
Same contract transmitter_schema.py/valve_schema.py/gauge_schema.py already
follow - see transmitter_schema.py's module docstring for what each field
key means and how LOG_COLUMNS/by_section/by_id/CONTROL_FIELD are used (by
data_access.py, export_transformer_test_to_pdf.py, gui_app.py, index_view.py).

Part of the Electrical equipment family added alongside Transmitter/Valve/
Gauge - EQUIPMENT_TYPES in data_access.py carries the per-type metadata
that lets the rest of the app treat any number of equipment types
generically instead of assuming exactly three.

"Transformer type: [ ] Dry [ ] Wet" is modeled as two independent plain
text fields (transformer_type_dry/transformer_type_wet, "X" or initials
to mark the one that applies), not a real checkbox - the source PDF's own
AcroForm has no checkbox widget there, just two blank text cells.
"""

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
_add("project", "Project", "part1")
_add("location", "Location", "part1")
_add("contract_no", "Contract #", "part1")

# ------------------------------------------- PART 2 - Transformer Nameplate --
_add("tag", "Tag", "part2")
_add("transformer_type_dry", "Transformer Type - Dry", "part2")
_add("transformer_type_wet", "Transformer Type - Wet", "part2")
_add("system", "System", "part2")
_add("make", "Make", "part2")
_add("model", "Model", "part2")
_add("serial_number", "Serial Number", "part2")
_add("primary_voltage", "Primary Voltage", "part2")
_add("secondary_voltage", "Secondary Voltage", "part2")
_add("phase", "Phase", "part2")
_add("primary_fla", "Primary FLA", "part2")
_add("secondary_fla", "Secondary FLA", "part2")
_add("rating_kva", "Rating (KVA)", "part2")
_add("temperature_rise", "Temperature Rise", "part2")
_add("primary_connection", "Primary Connection", "part2")
_add("secondary_connection", "Secondary Connection", "part2")
_add("primary_tap_setting_percent", "Primary Tap Setting - %", "part2")
_add("primary_tap_setting_volts", "Primary Tap Setting - Volts", "part2")
_add("area_classification", "Area Classification", "part2")

# --------------------------------------------------- PART 3 - Test Equipment -
for _row_n in (1, 2):
    _add(f"test_equip_{_row_n}_make", f"Test Equipment {_row_n} - Make", "part3")
    _add(f"test_equip_{_row_n}_model", f"Test Equipment {_row_n} - Model", "part3")
    _add(f"test_equip_{_row_n}_asset_serial", f"Test Equipment {_row_n} - Asset/Serial Number", "part3")
    _add(f"test_equip_{_row_n}_calibrated_on", f"Test Equipment {_row_n} - Calibrated On", "part3")

# ------------------------------------------- PART 4 - Insulation Resistance --
for _row_n in (1, 2):
    _add(f"insulation_row_{_row_n}_primary_to_ground", f"Insulation Resistance Row {_row_n} - Primary to Ground", "part4")
    _add(f"insulation_row_{_row_n}_secondary_to_ground", f"Insulation Resistance Row {_row_n} - Secondary to Ground", "part4")
    _add(f"insulation_row_{_row_n}_primary_to_secondary", f"Insulation Resistance Row {_row_n} - Primary to Secondary", "part4")
    _add(f"insulation_row_{_row_n}_test_voltage", f"Insulation Resistance Row {_row_n} - Test Voltage", "part4")
    _add(f"insulation_row_{_row_n}_ambient", f"Insulation Resistance Row {_row_n} - Ambient Conditions", "part4")
    _add(f"insulation_row_{_row_n}_initial", f"Insulation Resistance Row {_row_n} - Initial", "part4")

# ---------------------------------------------- PART 5 - Winding Resistance --
for _col_id in ("h1", "h2", "h3", "x1", "x2", "x3"):
    _add(f"winding_{_col_id}", f"Winding Resistance - {_col_id.upper()}", "part5")
_add("winding_ambient", "Winding Resistance - Ambient Conditions", "part5")
_add("winding_initial", "Winding Resistance - Initial", "part5")

# ---------------------------------------------- PART 6 - Visual Inspection ---
VISUAL_INSPECTION_ITEMS = [
    "Wall and floor clearance as per job specifications and codes.",
    "Primary feeder final insulation test complete.",
    "Secondary feeder final insulation test complete.",
    "Neutral ground connected to X-O correctly.",
    "Neutral ground connected to grid correctly.",
    "Ground bushing.",
    "Case/frame grounded.",
    "Primary tap setting.",
]
for i, text in enumerate(VISUAL_INSPECTION_ITEMS, start=1):
    _add(f"vis_item_{i}_initial", f"{i}. {text} (Initial/NA)", "part6")

# ------------------------------------------------------- PART 7 - Remarks ----
_add("remarks", "Remarks", "part7", "multiline")

# ----------------------------------------------- PART 8 - Inspected/Approved -
_add("yanda_rep_name", "Yanda Representative - Name", "part8")
_add("yanda_rep_date", "Yanda Representative - Date", "part8")
_add("yanda_rep_signature", "Yanda Representative - Signature", "part8")
_add("client_rep_name", "Client Representative - Name", "part8")
_add("client_rep_date", "Client Representative - Date", "part8")
_add("client_rep_signature", "Client Representative - Signature", "part8")


# Extra column that only exists in the Excel log (not on the PDF form
# itself) - the checkbox-like flag that export_transformer_test_to_pdf.py
# looks at to decide which rows to turn into filled PDFs.
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
    "part2": "PART 2 – Transformer Nameplate",
    "part3": "PART 3 – Test Equipment",
    "part4": "PART 4 – Insulation Resistance",
    "part5": "PART 5 – Winding Resistance",
    "part6": "PART 6 – Visual Inspection",
    "part7": "PART 7 – Remarks",
    "part8": "PART 8 – Inspected/Approved By",
}

if __name__ == "__main__":
    print(f"Total fields: {len(FIELDS)}")
    from collections import Counter
    c = Counter(f["section"] for f in FIELDS)
    for sec, n in c.items():
        print(f"  {sec}: {n}")
