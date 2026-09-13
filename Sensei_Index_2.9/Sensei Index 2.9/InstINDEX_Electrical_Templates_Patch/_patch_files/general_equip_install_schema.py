# -*- coding: utf-8 -*-
"""
Single source of truth for every field on the General Electrical
Equipment Installation & Test Report (YCQE-E&I-013 Rev.0) - the
Electrical side's seventh form. Used by:
  - export_general_equip_install_to_pdf.py  (fills the PDF template from a selected row)
  - electrical_data_access.py                (reads/writes the Excel log sheet)
  - gui_app.py                                (the Electrical edit form)

Each field:
  id       - internal key (must be unique)
  label    - Human readable label used as the Excel column header and the
             edit form's caption
  section  - Which part of the form it belongs to (for grouping/headers)
  ftype    - 'text' | 'multiline' | 'choice'
  choices  - list of allowed values, only for ftype == 'choice'

REVISION 2: this form's template is now built from the user's own real,
official source document (a Word .docx converted to PDF via LibreOffice)
instead of a hand-filled scan sample - see
general_equip_install_field_positions.py's and
build_general_equip_install_template.py's own docstrings for the full
rebuild methodology. Field names are still chosen to be exactly this
schema's own ids (see general_equip_install_field_map.py - an identity
mapping).

customer_name / project_name / contract_no are NOT modeled as fields -
cleanly typeset, matching this whole engagement's constant values (same
precedent every other Electrical form here sets). location IS a field -
also typeset (not hand-written), matching small_power_cable's own
Location field.

"MANFACTURER" is a typo on the real, printed source document (confirmed
- not a transcription error here) - kept as-is on the template (never
edited, per the "do not change the design" instruction), but this
schema's own label spells it correctly ("Manufacturer") since that's
only used internally (Excel column header, edit-form caption), not
printed anywhere.

Two sections - "EQUIPMENT RESISTANCE TESTING" and "EQUIPMENT INSULATION
RESISTANCE TESTING (1 MINUTE PER)" - have no printed column headers on
the real form (a genuine gap in the source document, confirmed by
inspection), so each is modeled as a single multiline field rather than
invented columns - see general_equip_install_field_positions.py's own
docstring.

The Torqueing Log's 5 rows are flattened into numbered columns, the same
"flatten a repeating table into numbered columns" approach
eht_pre_insulation's checklist and torqueing's own bolt table already
use. "TORQUE MARKED" (a checkbox + printed "YES" per row) is modeled as
a single small text field per row, same "plain text, not a real
checkbox" choice every other form here makes.
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


# ---------------------------------------------------------------- Project
_add("location", "Location", "project")

# ------------------------------------------------------------- Nameplate
_add("tag_number", "Tag #", "nameplate")
_add("manufacturer", "Manufacturer", "nameplate")
_add("model_number", "Model #", "nameplate")
_add("system_number", "System #", "nameplate")
_add("serial_number", "Serial #", "nameplate")
_add("voltage", "Voltage", "nameplate")
_add("freq", "Freq.", "nameplate")
_add("phase", "Phase", "nameplate")
_add("amps", "Amps", "nameplate")
_add("area_class_of_equip", "Area Class of Equip", "nameplate")
_add("ref_dwg_number", "Ref. Dwg #", "nameplate")
_add("kva", "KVA", "nameplate")
_add("area_class", "Area Class", "nameplate")
_add("test_equip_model_number", "Test Equip. Model #", "nameplate")
_add("test_equip_serial_number", "Test Equip. Serial #", "nameplate")
_add("cal_due", "Cal. Due", "nameplate")

# ------------------------------------------------------------ Verifications
_TASK_LABELS = [
    "Inspect for any damage to all components associated. Ensure removal of shipping blocks.",
    "Equipment is securely mounted, anchored & plumb. Correct fastener assemblies are "
    "installed & complete. Clearances and installation are as per CEC & manufacturer "
    "specifications.",
    "Verify CSA certification marking (or equivalent), warning labels installed as per "
    "CEC & specifications.",
    "Verify equipment nameplate data matches IFC drawings & specifications.",
    "Verify area classification rating & connectors are rated for the location of "
    "installation.",
    "Verify over current protection is as per CEC & IFC drawings. MCC cubicle has been "
    "inspected.",
    "Verify grounding & bonding requirements are as per CEC, owner specifications & IFC "
    "drawings.",
    "All cables, conductors & equipment are labeled and identified as per CEC & IFC "
    "drawings.",
    "Verify that continuity and megger testing has been conducted on all cables/conductors.",
    "Insulation resistance testing and winding resistance testing has been completed.",
    "Re-terminate all wiring as per IFC drawings & manufacturer specs after testing is "
    "completed.",
    "Push-pull-tug method completed after termination. Torqueing as per manufacturer "
    "specifications.",
    "Ensure there are no metal filings inside or on top of equipment before energization.",
    "Check for overall cleanliness and acceptable constructability of equipment "
    "installation. Remove all tools, debris, oil, dirt, safety grounds and isolation. "
    "Inspect for moisture & leaks.",
    "Gland plates & all other entrances have been sealed as per owner specifications.",
    "All covers and/or doors have been installed as per manufacturer specifications.",
    "Picture(s) of equipment installation are attached with this report.",
    "Red line mark-ups to be submitted with as-built drawings for turnover.",
]
for _n, _label in enumerate(_TASK_LABELS, start=1):
    _add(f"task_{_n}_yes", f"Task {_n} - Yes Initial", "verifications")
    _add(f"task_{_n}_na", f"Task {_n} - N/A Initial", "verifications")

# --------------------------------------------------------- Section N/A flags
_add("electrical_equipment_testing_na", "Electrical Equipment Testing - N/A", "section_flags")
_add("equipment_resistance_testing_na", "Equipment Resistance Testing - N/A", "section_flags")
_add("equipment_insulation_resistance_testing_na",
     "Equipment Insulation Resistance Testing (1 Minute Per) - N/A", "section_flags")
_add("torqueing_log_na", "Torqueing Log - N/A", "section_flags")
_add("comments_na", "Comments - N/A", "section_flags")

# ------------------------------------------------------ Unlabeled blank grids
_add("equipment_resistance_testing_notes", "Equipment Resistance Testing - Notes",
     "resistance_testing", "multiline")
_add("equipment_insulation_resistance_testing_notes",
     "Equipment Insulation Resistance Testing (1 Minute Per) - Notes",
     "resistance_testing", "multiline")

# ------------------------------------------------------------- Torqueing Log
_TORQUEING_COLUMNS = [
    ("cond_id", "Cond I.D."), ("location", "Location"), ("bolt_grade", "Bolt Grade"),
    ("bolt_size", "Bolt Size"), ("torque_value", "Torque Value"),
    ("torque_marked", "Torque Marked - Yes"), ("torque_by", "Torque By (Initial)"),
    ("date", "Date"),
]
for _row in range(1, 6):
    for _col_id, _col_label in _TORQUEING_COLUMNS:
        _add(f"torqueing_row_{_row}_{_col_id}", f"Torqueing Row {_row} - {_col_label}", "torqueing_log")

# ------------------------------------------------------------------ Comments
_add("comments", "Comments", "comments", "multiline")

# ------------------------------------------------------------------ Sign-off
_add("yanda_rep_name", "Yanda Representative - Name", "signoff")
_add("yanda_rep_date", "Yanda Representative - Date", "signoff")
_add("yanda_rep_signature", "Yanda Representative - Signature", "signoff")
_add("client_rep_name", "Client Representative - Name", "signoff")
_add("client_rep_date", "Client Representative - Date", "signoff")
_add("client_rep_signature", "Client Representative - Signature", "signoff")


def by_section(section):
    return [f for f in FIELDS if f["section"] == section]


SECTION_TITLES = {
    "project": "Project Description",
    "nameplate": "Equipment Nameplate Data",
    "verifications": "Verifications",
    "section_flags": "Section N/A Flags",
    "resistance_testing": "Resistance Testing",
    "torqueing_log": "Torqueing Log",
    "comments": "Comments",
    "signoff": "Sign-Off",
}

LOG_COLUMNS = FIELDS

if __name__ == "__main__":
    print(f"Total fields: {len(FIELDS)}")
