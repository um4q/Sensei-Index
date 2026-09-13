# -*- coding: utf-8 -*-
"""
Maps each transformer_test_schema.py field id to the ACTUAL AcroForm field
name inside Transformer_Test_Record_TEMPLATE.pdf.

Same situation as eht_pre_insulation_field_map.py: there was no original
fillable PDF for this form, only a hand-filled scan. The template is
built by build_transformer_test_template.py using the real scanned page
as a background image, with field names chosen to be exactly the
schema's own ids - so this is a clean identity mapping, not a lookup
table of legacy "Text##"-style widget names. Kept as a genuine dict
anyway (rather than reading schema ids directly as PDF field names) so
this form follows the same trio shape as every other Electrical form -
export_*_to_pdf.py can import FIELD_MAP the same way regardless of which
form it's filling.

No checkbox fields on this template - "Transformer type: [ ] Dry
[ ] Wet" is two independent plain text fields (transformer_type_dry /
transformer_type_wet), same "plain text, not a real checkbox" choice
eht_pre_insulation made for every cell on its own template (see that
module's docstring).

yanda_rep_signature's own typed value is what
export_transformer_test_to_pdf.py's fill_pdf() actually fills by default
though: the same automatic Yanda QA Representative signature-image stamp
Torqueing/eht_pre_insulation have is overlaid on this exact cell, and
that field's typed value (if any) is skipped whenever the stamp is
applied - see that module's stamp_signature()/fill_pdf() for the details.
client_rep_signature is untouched by any of this - still a plain typed
field.
"""

FIELD_MAP = {
    "project": "project",
    "location": "location",
    "contract_no": "contract_no",

    "tag": "tag",
    "transformer_type_dry": "transformer_type_dry",
    "transformer_type_wet": "transformer_type_wet",
    "system": "system",
    "make": "make",
    "model": "model",
    "serial_number": "serial_number",
    "primary_voltage": "primary_voltage",
    "secondary_voltage": "secondary_voltage",
    "phase": "phase",
    "primary_fla": "primary_fla",
    "secondary_fla": "secondary_fla",
    "rating_kva": "rating_kva",
    "temperature_rise": "temperature_rise",
    "primary_connection": "primary_connection",
    "secondary_connection": "secondary_connection",
    "primary_tap_setting_percent": "primary_tap_setting_percent",
    "primary_tap_setting_volts": "primary_tap_setting_volts",
    "area_classification": "area_classification",

    "remarks": "remarks",

    "yanda_rep_name": "yanda_rep_name",
    "yanda_rep_date": "yanda_rep_date",
    "yanda_rep_signature": "yanda_rep_signature",
    "client_rep_name": "client_rep_name",
    "client_rep_date": "client_rep_date",
    "client_rep_signature": "client_rep_signature",
}

for _row_n in (1, 2):
    for _col_id in ("make", "model", "asset_serial", "calibrated_on"):
        _fid = f"test_equip_{_row_n}_{_col_id}"
        FIELD_MAP[_fid] = _fid

for _row_n in (1, 2):
    for _col_id in ("primary_to_ground", "secondary_to_ground", "primary_to_secondary",
                     "test_voltage", "ambient", "initial"):
        _fid = f"insulation_row_{_row_n}_{_col_id}"
        FIELD_MAP[_fid] = _fid

for _col_id in ("h1", "h2", "h3", "x1", "x2", "x3", "ambient", "initial"):
    _fid = f"winding_{_col_id}"
    FIELD_MAP[_fid] = _fid

for _n in range(1, 9):
    _fid = f"vis_item_{_n}_initial"
    FIELD_MAP[_fid] = _fid

# No checkbox groups, no ATC-style field-specific on-states, no multi-widget
# fields on this template.
YES_NO_CHECKBOXES = {}
CHECKBOX_ON = "/Yes"
CHECKBOX_OFF = "/Off"

# Nothing on this form is hand-signed-only - every sign-off cell is a real
# fillable field (see module docstring).
UNMAPPED_NOTE = None
