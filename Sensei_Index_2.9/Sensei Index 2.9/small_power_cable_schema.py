# -*- coding: utf-8 -*-
"""
Single source of truth for every field on the Small Power and Control
Cable Inspection & Test Record (YCQE-EI-113 Rev.0) - the Electrical
side's sixth form. Used by:
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

REVISION 2: rebuilt from the user's own real, official source PDF
(YCQE-EI-113 Rev.0) instead of a hand-filled scan sample - see
small_power_cable_field_map.py's own docstring for why this replaces the
earlier scan-based reconstruction. The real PDF already had its own
correctly-positioned AcroForm fields (41 of them, one per fillable cell) -
this schema's own field shape now matches that real structure exactly
(test equipment is 2 rows, not 1; remarks is 3 separate lines, not one
multiline box).

REVISION 3: yanda_rep_signature/client_rep_signature added back. The
real PDF has no signature AcroForm field of its own for either
representative - only the printed "Signature:" label and blank line
(confirmed directly against the source's own field list) - so REVISION 2
treated this form as hand-signed only, same as eht_removal/eht_rtd's own
real, signature-field-less source PDFs. That's still literally true of
the real PDF, but nothing stops this app from adding its OWN new field
on top of that blank line, the same way transformer_test/
general_equip_install add fields onto real source PDFs that had none at
all - see build_small_power_cable_template.py's own docstring for the
merge-overlay mechanics. yanda_rep_signature gets the same automatic
Yanda QA Representative signature-image stamp every other signature-
bearing Electrical form has (see small_power_cable_field_map.py);
client_rep_signature is a plain typed field, same as every other form's
own client-side signature cell.

project / contract_no are NOT modeled as fields - the real PDF has them
as already-filled, non-fillable print text ("K1B Well Pad Project" /
"CA23007"). location IS a real fillable field on the real PDF (labeled
"Location:" under PART 1), pre-filled with "K1B Kinosis" on the sample
seen but still a genuine field, not baked-in print.
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
# Two rows on the real form, same "flatten a repeating table into numbered
# columns" approach every other multi-row section in this app already uses.
for _row in (1, 2):
    _add(f"test_equip_{_row}_make", f"Test Equipment {_row} - Make", "test_equipment")
    _add(f"test_equip_{_row}_model", f"Test Equipment {_row} - Model", "test_equipment")
    _add(f"test_equip_{_row}_asset_serial", f"Test Equipment {_row} - Asset/Serial Number",
         "test_equipment")
    _add(f"test_equip_{_row}_calibrated_on", f"Test Equipment {_row} - Calibrated On",
         "test_equipment")

# ------------------------------------------------------- PART 5 - Test Results
_RESULT_ROWS = [("cond_to_cond", "Conductor to Conductor"),
                 ("cond_to_ground", "Conductor to Ground"),
                 ("cond_to_armour", "Conductor to Armour")]
for _id, _label in _RESULT_ROWS:
    _add(f"insulation_{_id}", f"Insulation Resistance - {_label}", "test_results")
for _id, _label in _RESULT_ROWS:
    _add(f"continuity_{_id}", f"Continuity - {_label}", "test_results")

# --------------------------------------------------------------- PART 6 - Remarks
# 3 separate ruled lines on the real form (not one multiline box).
_add("remarks_line1", "Remarks - Line 1", "remarks")
_add("remarks_line2", "Remarks - Line 2", "remarks")
_add("remarks_line3", "Remarks - Line 3", "remarks")

# ------------------------------------------------------------------- PART 7 Sign-off
# yanda_rep_signature/client_rep_signature are new fields merged onto the
# real PDF's own blank "Signature:" line - see this file's own docstring
# (REVISION 3) and build_small_power_cable_template.py's for why/how.
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
