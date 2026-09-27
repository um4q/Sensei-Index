# -*- coding: utf-8 -*-
"""
Single source of truth for every field on the General Electrical Equipment
Installation & Test Report (Form# YCQE-E&I-013). Same contract
transmitter_schema.py/valve_schema.py/gauge_schema.py already follow - see
transmitter_schema.py's module docstring for what each field key means and
how LOG_COLUMNS/by_section/by_id/CONTROL_FIELD are used (by
data_access.py, export_general_equip_install_to_pdf.py, gui_app.py,
index_view.py).

Part of the Electrical equipment family added alongside Transmitter/Valve/
Gauge/Transformer Test/Small Power Cable - EQUIPMENT_TYPES in
data_access.py carries the per-type metadata that lets the rest of the
app treat any number of equipment types generically.

Unlike the other two rebuilt Electrical forms, this one's real source
document was a Word .docx converted to PDF, which naturally splits onto
2 pages (the Torqueing Log's last 3 rows, Comments, and the Sign-Off
block land on page 2) - a pagination/margin difference from the
conversion, not a content change. customer_name/project_name/contract_no
are cleanly typeset on the form and not modeled as schema fields (same
convention every other Electrical form uses for its own un-mapped header
cells).

"MANFACTURER" is a genuine typo on the real printed form (confirmed
against the source document, not something introduced here) - kept as
the printed label the PDF field itself carries; this schema's own label
below spells it correctly since that's only ever shown in the Excel
column header / edit-form caption, never printed.
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
_add("location", "Location", "part1")

# ------------------------------------------------- PART 2 - Equipment Nameplate
_add("tag_number", "Tag #", "part2")
_add("manufacturer", "Manufacturer", "part2")
_add("model_number", "Model #", "part2")
_add("system_number", "System #", "part2")
_add("serial_number", "Serial #", "part2")
_add("voltage", "Voltage", "part2")
_add("freq", "Freq.", "part2")
_add("phase", "Phase", "part2")
_add("amps", "Amps", "part2")
_add("area_class_of_equip", "Area Class of Equip", "part2")
_add("ref_dwg_number", "Ref. Dwg #", "part2")
_add("kva", "KVA", "part2")
_add("area_class", "Area Class", "part2")
_add("test_equip_model_number", "Test Equip. Model #", "part2")
_add("test_equip_serial_number", "Test Equip. Serial #", "part2")
_add("cal_due", "Cal. Due", "part2")

# --------------------------------------------------------- PART 3 - Verifications
for _n in range(1, 19):
    _add(f"task_{_n}_yes", f"Task {_n} - Yes Initial", "part3")
    _add(f"task_{_n}_na", f"Task {_n} - N/A Initial", "part3")

# -------------------------------------------------------- PART 4 - Section Flags
_add("electrical_equipment_testing_na", "Electrical Equipment Testing - N/A", "part4")
_add("equipment_resistance_testing_na", "Equipment Resistance Testing - N/A", "part4")
_add("equipment_insulation_resistance_testing_na",
     "Equipment Insulation Resistance Testing (1 Minute Per) - N/A", "part4")
_add("torqueing_log_na", "Torqueing Log - N/A", "part4")
_add("comments_na", "Comments - N/A", "part4")

# ---------------------------------------------------- PART 5 - Resistance Testing
_add("equipment_resistance_testing_notes", "Equipment Resistance Testing - Notes", "part5", "multiline")
_add("equipment_insulation_resistance_testing_notes",
     "Equipment Insulation Resistance Testing (1 Minute Per) - Notes", "part5", "multiline")

# ------------------------------------------------------- PART 6 - Torqueing Log
for _row_n in range(1, 6):
    _add(f"torqueing_row_{_row_n}_cond_id", f"Torqueing Row {_row_n} - Cond I.D.", "part6")
    _add(f"torqueing_row_{_row_n}_location", f"Torqueing Row {_row_n} - Location", "part6")
    _add(f"torqueing_row_{_row_n}_bolt_grade", f"Torqueing Row {_row_n} - Bolt Grade", "part6")
    _add(f"torqueing_row_{_row_n}_bolt_size", f"Torqueing Row {_row_n} - Bolt Size", "part6")
    _add(f"torqueing_row_{_row_n}_torque_value", f"Torqueing Row {_row_n} - Torque Value", "part6")
    _add(f"torqueing_row_{_row_n}_torque_marked", f"Torqueing Row {_row_n} - Torque Marked - Yes", "part6")
    _add(f"torqueing_row_{_row_n}_torque_by", f"Torqueing Row {_row_n} - Torque By (Initial)", "part6")
    _add(f"torqueing_row_{_row_n}_date", f"Torqueing Row {_row_n} - Date", "part6")

# --------------------------------------------------------------- PART 7 - Comments
_add("comments", "Comments", "part7", "multiline")

# ------------------------------------------------------ PART 8 - Inspected/Approved
_add("yanda_rep_name", "Yanda Representative - Name", "part8")
_add("yanda_rep_date", "Yanda Representative - Date", "part8")
_add("yanda_rep_signature", "Yanda Representative - Signature", "part8")
_add("client_rep_name", "Client Representative - Name", "part8")
_add("client_rep_date", "Client Representative - Date", "part8")
_add("client_rep_signature", "Client Representative - Signature", "part8")


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
    "part2": "PART 2 – Equipment Nameplate",
    "part3": "PART 3 – Verifications",
    "part4": "PART 4 – Section Flags",
    "part5": "PART 5 – Resistance Testing",
    "part6": "PART 6 – Torqueing Log",
    "part7": "PART 7 – Comments",
    "part8": "PART 8 – Inspected/Approved By",
}

# The 18 verification task descriptions, from the printed form itself
# (YCQE-E&I-013 Rev.0) - the log only stores the Yes/N-A initials per task.
_TASKS = [
    "Inspect for any damage to all components associated. Ensure removal of shipping blocks.",
    "Equipment is securely mounted, anchored & plumb. Correct fastener assemblies are installed & "
    "complete. Clearances and installation are as per CEC & manufacturer specifications.",
    "Verify CSA certification marking (or equivalent), warning labels installed as per CEC & "
    "specifications.",
    "Verify equipment nameplate data matches IFC drawings & specifications.",
    "Verify area classification rating & connectors are rated for the location of installation.",
    "Verify over current protection is as per CEC & IFC drawings. MCC cubicle has been inspected.",
    "Verify grounding & bonding requirements are as per CEC, owner specifications & IFC drawings.",
    "All cables, conductors & equipment are labeled and identified as per CEC & IFC drawings.",
    "Verify that continuity and megger testing has been conducted on all cables/conductors.",
    "Insulation resistance testing and winding resistance testing has been completed.",
    "Re-terminate all wiring as per IFC drawings & manufacturer specs after testing is completed.",
    "Push-pull-tug method completed after termination. Torqueing as per manufacturer specifications.",
    "Ensure there are no metal filings inside or on top of equipment before energization.",
    "Check for overall cleanliness and acceptable constructability of equipment installation. Remove "
    "all tools, debris, oil, dirt, safety grounds and isolation. Inspect for moisture & leaks.",
    "Gland plates & all other entrances have been sealed as per owner specifications.",
    "All covers and/or doors have been installed as per manufacturer specifications.",
    "Picture(s) of equipment installation are attached with this report.",
    "Red line mark-ups to be submitted with as-built drawings for turnover.",
]

# Edit-form table layouts for gui_app.EditDialog - presentation only. Each
# row is (row label, [field id per column]); a column width of 0 stretches.
GRIDS = [
    {
        "row_header": "Task",
        "row_header_width": 0,
        "columns": [("Yes Initial", 88), ("N/A Initial", 88)],
        "rows": [(f"{n}. {text}", [f"task_{n}_yes", f"task_{n}_na"])
                 for n, text in enumerate(_TASKS, start=1)],
    },
    {
        "row_header": "Row",
        "row_header_width": 36,
        "columns": [("Cond. I.D.", 90), ("Location", 0), ("Bolt Grade", 76), ("Bolt Size", 66),
                    ("Torque Value", 86), ("Marked (Yes)", 88), ("By (Initial)", 80), ("Date", 96)],
        "rows": [(str(n), [f"torqueing_row_{n}_{part}" for part in
                           ("cond_id", "location", "bolt_grade", "bolt_size", "torque_value",
                            "torque_marked", "torque_by", "date")])
                 for n in range(1, 6)],
    },
]

if __name__ == "__main__":
    print(f"Total fields: {len(FIELDS)}")
    from collections import Counter
    c = Counter(f["section"] for f in FIELDS)
    for sec, n in c.items():
        print(f"  {sec}: {n}")
