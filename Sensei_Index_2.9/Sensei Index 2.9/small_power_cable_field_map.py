# -*- coding: utf-8 -*-
"""
Maps each small_power_cable_schema.py field id to the ACTUAL AcroForm
field name inside
Small_Power_and_Control_Cable_Inspection_and_Test_Record_TEMPLATE.pdf.

Same situation as eht_pre_insulation_field_map.py / transformer_test_field_map.py:
there was no original fillable PDF for this form, only hand-filled scans.
The template is built by build_small_power_cable_template.py using a real
scanned page as a background image, with field names chosen to be
exactly the schema's own ids - so this is a clean identity mapping, not a
lookup table of legacy "Text##"-style widget names. Kept as a genuine
dict anyway (rather than reading schema ids directly as PDF field names)
so this form follows the same trio shape as every other Electrical form.

No checkbox fields on this template - every cell, including the
Initial/NA and Insulation/Continuity Result cells, is a plain text field
(same "plain text, not a real checkbox" choice eht_pre_insulation's
REVISION 2 build made for every cell on that form).

yanda_rep_signature's own typed value is what
export_small_power_cable_to_pdf.py's fill_pdf() actually fills by default
though: the same automatic Yanda QA Representative signature-image stamp
Torqueing/eht_pre_insulation/transformer_test have is overlaid on this
exact cell, and that field's typed value (if any) is skipped whenever the
stamp is applied so the two never render on top of each other.
client_rep_signature is untouched by any of this - still a plain typed
field.
"""

FIELD_MAP = {
    "location": "location",

    "cable_tag_number": "cable_tag_number",
    "cable_type": "cable_type",
    "system": "system",
    "cable_size": "cable_size",
    "number_of_conductors": "number_of_conductors",
    "cable_rated_voltage": "cable_rated_voltage",

    "test_equip_make": "test_equip_make",
    "test_equip_model": "test_equip_model",
    "test_equip_asset_serial": "test_equip_asset_serial",
    "test_equip_calibrated_on": "test_equip_calibrated_on",

    "remarks": "remarks",

    "yanda_rep_name": "yanda_rep_name",
    "yanda_rep_date": "yanda_rep_date",
    "yanda_rep_signature": "yanda_rep_signature",
    "client_rep_name": "client_rep_name",
    "client_rep_date": "client_rep_date",
    "client_rep_signature": "client_rep_signature",
}

for _n in range(1, 12):
    _fid = f"vis_item_{_n}_initial"
    FIELD_MAP[_fid] = _fid

for _id in ("conductor_to_conductor", "conductor_to_ground", "conductor_to_armour"):
    FIELD_MAP[f"insulation_{_id}"] = f"insulation_{_id}"
    FIELD_MAP[f"continuity_{_id}"] = f"continuity_{_id}"

# No checkbox groups, no ATC-style field-specific on-states, no multi-widget
# fields on this template - it was built for this form only, with exactly
# the 35 fields the schema declares.
YES_NO_CHECKBOXES = {}
CHECKBOX_ON = "/Yes"
CHECKBOX_OFF = "/Off"

# Nothing on this form is hand-signed-only - every sign-off cell is a real
# fillable field (see module docstring).
UNMAPPED_NOTE = None
