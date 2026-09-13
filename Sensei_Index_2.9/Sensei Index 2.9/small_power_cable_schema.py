# -*- coding: utf-8 -*-
"""
Single source of truth for every field on the Small Power and Control
Cable Inspection & Test Record (YCQE-E&I-113 Rev.0) - the Electrical
side's sixth form, and the second of three new forms added from the
user's second uploaded scan bundle (spcc_itrs.pdf). Used by:
  - export_small_power_cable_to_pdf.py  (fills the PDF template from a selected row)
  - electrical_data_access.py           (reads/writes the Excel log sheet)
  - gui_app.py                          (the Electrical edit form)

Each field:
  id       - internal key (must be unique)
  label    - Human readable label used as the Excel column header and the
             edit form's caption
  section  - Which part of the form it belongs to (for grouping/headers)
  ftype    - 'text' | 'multiline' | 'choice'
  choices  - list of allowed values, only for ftype == 'choice'

Like eht_pre_insulation/transformer_test, there was no original fillable
PDF for this form - only 10 hand-filled scans of the same blank template
in the user's upload. The template is built by
build_small_power_cable_template.py using the real scanned page as a
background image, field names chosen to be exactly this schema's own
ids (see small_power_cable_field_map.py - an identity mapping).

project / contract_no are NOT modeled as fields - cleanly typeset and
IDENTICAL across all 10 samples of this form ("K1B Well Pad Project" /
"CA23007"), confirmed by inspection - same precedent
eht_pre_insulation_schema.py set. location IS a real field: still
typeset (not hand-written) but genuinely varies between samples (e.g.
"Drain Tank 29152" vs "Drain Tank 29151").
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


# ------------------------------------------------------------ PART 1 - Project
_add("location", "Location", "project")

# ------------------------------------------------------- PART 2 - Cable Description
_add("cable_tag_number", "Cable Tag Number", "cable_description")
_add("cable_type", "Cable Type", "cable_description")
_add("system", "System", "cable_description")
_add("cable_size", "Cable Size", "cable_description")
_add("number_of_conductors", "Number of Conductors", "cable_description")
_add("cable_rated_voltage", "Cable Rated Voltage", "cable_description")

# ------------------------------------------------------- PART 3 - Visual Inspection
_VISUAL_LABELS = [
    "Cable size, type, location, installation, and routing are in accordance with the "
    "drawings.(Check all connectors are tight)",
    "Bend radius is in accordance with project specifications and the cable jacket is "
    "free of kinks.",
    "Cable termination supports and support spacing is in accordance with drawings and "
    "project specifications.",
    "Installation is neat and evenly spaced.(Junction boxes are cleaned out & wires are "
    "dressed within panduit)",
    "Cable is free of surface damage.",
    "Correct cable tag is installed on both ends.",
    "Termination kit/materials are installed in accordance with the manufacturer's "
    "instructions.",
    "Conductors are properly identified.(Core markers are the same font, size & evenly "
    "spaced / alligned)",
    "Check phase location and marking (Left to Right, Top to Bottom, or Front to Rear) "
    "are in accordance with the drawings and project specifications.",
    "Insulation Test has been performed",
    "Enter all deficiencies and missing items on Form YCQE-PS-048 Rev.0",
]
for _n, _label in enumerate(_VISUAL_LABELS, start=1):
    _add(f"vis_item_{_n}_initial", f"{_n}. {_label} - Initial/NA", "visual_inspection")

# ------------------------------------------------------- PART 4 - Test Equipment
_add("test_equip_make", "Test Equipment - Make", "test_equipment")
_add("test_equip_model", "Test Equipment - Model", "test_equipment")
_add("test_equip_asset_serial", "Test Equipment - Asset/Serial Number", "test_equipment")
_add("test_equip_calibrated_on", "Test Equipment - Calibrated On", "test_equipment")

# ------------------------------------------------------- PART 5 - Test Results
_RESULT_ROWS = [("conductor_to_conductor", "Conductor to Conductor"),
                 ("conductor_to_ground", "Conductor to Ground"),
                 ("conductor_to_armour", "Conductor to Armour")]
for _id, _label in _RESULT_ROWS:
    _add(f"insulation_{_id}", f"Insulation Resistance - {_label}", "test_results")
for _id, _label in _RESULT_ROWS:
    _add(f"continuity_{_id}", f"Continuity - {_label}", "test_results")

# --------------------------------------------------------------- PART 6 - Remarks
_add("remarks", "Remarks", "remarks", "multiline")

# ------------------------------------------------------------------- PART 7 Sign-off
_add("yanda_rep_name", "Yanda QA Representative - Name", "signoff")
_add("yanda_rep_date", "Yanda QA Representative - Date", "signoff")
_add("yanda_rep_signature", "Yanda QA Representative - Signature", "signoff")
_add("client_rep_name", "Client Representative - Name", "signoff")
_add("client_rep_date", "Client Representative - Date", "signoff")
_add("client_rep_signature", "Client Representative - Signature", "signoff")


def by_section(section):
    return [f for f in FIELDS if f["section"] == section]


SECTION_TITLES = {
    "project": "Project Description",
    "cable_description": "Cable Description",
    "visual_inspection": "Visual Inspection",
    "test_equipment": "Test Equipment",
    "test_results": "Test Results",
    "remarks": "Remarks",
    "signoff": "Sign-Off",
}

LOG_COLUMNS = FIELDS

if __name__ == "__main__":
    print(f"Total fields: {len(FIELDS)}")
