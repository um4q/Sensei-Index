# -*- coding: utf-8 -*-
"""
Single source of truth for every field on the Transformer Test Record
(YCQE-E&I-112 Rev. 0) - the Electrical side's fifth form, and the first
of three new forms added from the user's second uploaded scan bundle
(spcc_itrs.pdf). Used by:
  - export_transformer_test_to_pdf.py  (fills the PDF template from a selected row)
  - electrical_data_access.py          (reads/writes the Excel log sheet)
  - gui_app.py                         (the Electrical edit form)

Each field:
  id       - internal key (must be unique)
  label    - Human readable label used as the Excel column header and the
             edit form's caption
  section  - Which part of the form it belongs to (for grouping/headers)
  ftype    - 'text' | 'multiline' | 'choice'
  choices  - list of allowed values, only for ftype == 'choice'

Like eht_pre_insulation, there was no original fillable PDF for this form
- only a hand-filled scan. The template is built by
build_transformer_test_template.py using the real scanned page as a
background image, field names chosen to be exactly this schema's own ids
(see transformer_test_field_map.py - an identity mapping).

project / location / contract_no ARE real fields here (unlike
eht_pre_insulation's own header, and unlike this SAME upload's other two
new forms - general_equip_install and small_power_cable - whose
Customer/Project/Contract# text is cleanly typeset/identical across every
sample seen, so THOSE bake it into the background instead). On this
specific form, "Project:"/"Location:"/"Contract #:" are hand-written on
the one sample seen, in the same technician's block-print handwriting as
every other field - confirmed by inspection, not typeset - so a genuinely
different project/site would need to type something different here, and
the template must let it.

"Transformer type: [ ] Dry [ ] Wet" is modeled as two independent fields
(transformer_type_dry / transformer_type_wet), one per checkbox - see
transformer_test_field_positions.py's docstring for why (matches this
same upload's General Electrical Equipment form's YES/N-A columns and the
valve ITR's fv_N_yes/fv_N_na split, rather than a real /Btn widget).
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
_add("project", "Project", "project")
_add("location", "Location", "project")
_add("contract_no", "Contract #", "project")

# ------------------------------------------------- PART 2 - Nameplate Data
_add("tag", "Tag", "nameplate")
_add("transformer_type_dry", "Transformer Type - Dry", "nameplate")
_add("transformer_type_wet", "Transformer Type - Wet", "nameplate")
_add("system", "System", "nameplate")
_add("make", "Make", "nameplate")
_add("model", "Model", "nameplate")
_add("serial_number", "Serial Number", "nameplate")
_add("primary_voltage", "Primary Voltage", "nameplate")
_add("secondary_voltage", "Secondary Voltage", "nameplate")
_add("phase", "Phase", "nameplate")
_add("primary_fla", "Primary FLA", "nameplate")
_add("secondary_fla", "Secondary FLA", "nameplate")
_add("rating_kva", "Rating (KVA)", "nameplate")
_add("temperature_rise", "Temperature Rise", "nameplate")
_add("primary_connection", "Primary Connection", "nameplate")
_add("secondary_connection", "Secondary Connection", "nameplate")
_add("primary_tap_setting_percent", "Primary Tap Setting - %", "nameplate")
_add("primary_tap_setting_volts", "Primary Tap Setting - Volts", "nameplate")
_add("area_classification", "Area Classification", "nameplate")

# ---------------------------------------------------- PART 3 - Test Equipment
for _row_n in (1, 2):
    _add(f"test_equip_{_row_n}_make", f"Test Equipment {_row_n} - Make", "test_equipment")
    _add(f"test_equip_{_row_n}_model", f"Test Equipment {_row_n} - Model", "test_equipment")
    _add(f"test_equip_{_row_n}_asset_serial", f"Test Equipment {_row_n} - Asset/Serial Number", "test_equipment")
    _add(f"test_equip_{_row_n}_calibrated_on", f"Test Equipment {_row_n} - Calibrated On", "test_equipment")

# ------------------------------------------------- PART 4 - Insulation Resistance
_INSUL_COLS = [
    ("primary_to_ground", "Primary to Ground"), ("secondary_to_ground", "Secondary to Ground"),
    ("primary_to_secondary", "Primary to Secondary"), ("test_voltage", "Test Voltage"),
    ("ambient", "Ambient Conditions"), ("initial", "Initial"),
]
for _row_n in (1, 2):
    for _col_id, _col_label in _INSUL_COLS:
        _add(f"insulation_row_{_row_n}_{_col_id}", f"Insulation Resistance Row {_row_n} - {_col_label}",
             "insulation_resistance")

# ---------------------------------------------------- Winding Resistance
for _col_id, _col_label in [("h1", "H1"), ("h2", "H2"), ("h3", "H3"), ("x1", "X1"), ("x2", "X2"), ("x3", "X3"),
                             ("ambient", "Ambient Conditions"), ("initial", "Initial")]:
    _add(f"winding_{_col_id}", f"Winding Resistance - {_col_label}", "winding_resistance")

# ------------------------------------------------------- PART 5 - Visual Inspection
_VISUAL_LABELS = [
    "Wall and floor clearance as per job specifications and codes.",
    "Primary feeder final insulation test complete.",
    "Secondary feeder final insulation test complete.",
    "Neutral ground connected to X-O correctly.",
    "Neutral ground connected to grid correctly.",
    "Ground bushing.",
    "Case/frame grounded.",
    "Primary tap setting.",
]
for _n, _label in enumerate(_VISUAL_LABELS, start=1):
    _add(f"vis_item_{_n}_initial", f"{_n}. {_label} - Initial/NA", "visual_inspection")

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
    "nameplate": "Transformer Nameplate Data",
    "test_equipment": "Test Equipment",
    "insulation_resistance": "Insulation Resistance",
    "winding_resistance": "Winding Resistance",
    "visual_inspection": "Visual Inspection",
    "remarks": "Remarks",
    "signoff": "Sign-Off",
}

LOG_COLUMNS = FIELDS

if __name__ == "__main__":
    print(f"Total fields: {len(FIELDS)}")
