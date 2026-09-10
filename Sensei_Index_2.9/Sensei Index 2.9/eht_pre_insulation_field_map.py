# -*- coding: utf-8 -*-
"""
Maps each eht_pre_insulation_schema.py field id to the ACTUAL AcroForm field
name inside EHT_and_RTD_Pre-Insulation_Installation_Report_TEMPLATE.pdf.

Unlike eht_removal_field_map.py/eht_rtd_field_map.py, this is not a
reverse-engineered map against someone else's original PDF - there was no
original fillable PDF for this form (YCQE-EHT-004 Rev.0), only hand-filled
scans. The template itself is built by build_eht_pre_insulation_template.py
using the real scanned page as a background image (see that module's
docstring for why - exact design/font/border fidelity), with field names
chosen to be exactly the schema's own ids - so this map is a clean identity
mapping, not a lookup table of legacy "Text##"-style widget names.

Kept as a genuine dict (rather than deleting the module and reading
schema ids directly as PDF field names in the export script) so this form
follows the same trio shape as eht_removal/eht_rtd - export_*_to_pdf.py can
import FIELD_MAP the same way regardless of which of the three forms it's
filling.

No checkbox fields on this template (unlike eht_rtd, whose megger/ATC
cells are real /Btn widgets) - every field here, including the Results
and megger Passed/Fail cells, is a plain text field. There's no
CHECKBOX_ON/CHECKBOX_OFF convention to apply to any of them.

Signature fields (yanda_rep_signature, client_rep_signature) are real
fillable text fields on this template, not hand-signed-only - a
deliberate choice (see eht_pre_insulation_schema.py's docstring) made
because a real digital field keeps the export fully self-contained,
consistent with how every other field on this form works.

yanda_rep_signature's own typed value is what export_eht_pre_insulation_to_pdf.py's
fill_pdf() actually fills by default now though: the same automatic
Yanda QA Representative signature-image stamp Torqueing has is overlaid
on this exact cell, and that field's typed value (if any) is skipped
whenever the stamp is applied so the two never render on top of each
other - see that module's stamp_signature()/fill_pdf() for the details.
client_rep_signature is untouched by any of this - still a plain typed
field, same as every other field on this form.
"""

FIELD_MAP = {
    "trace_number": "trace_number",
    "eht_controller_number": "eht_controller_number",
    "trace_part_number": "trace_part_number",
    "panel_number": "panel_number",
    "rtds_number": "rtds_number",
    "circuit_number": "circuit_number",
    "trace_line_number": "trace_line_number",
    "rev": "rev",

    "test_equip_model": "test_equip_model",
    "test_equip_serial": "test_equip_serial",
    "cal_due_date": "cal_due_date",

    "megger_500_reading": "megger_500_reading",
    "megger_500_result": "megger_500_result",
    "megger_1000_reading": "megger_1000_reading",
    "megger_1000_result": "megger_1000_result",
    "megger_2500_reading": "megger_2500_reading",
    "megger_2500_result": "megger_2500_result",

    "comments": "comments",

    "yanda_rep_name": "yanda_rep_name",
    "yanda_rep_date": "yanda_rep_date",
    "yanda_rep_signature": "yanda_rep_signature",
    "client_rep_name": "client_rep_name",
    "client_rep_date": "client_rep_date",
    "client_rep_signature": "client_rep_signature",
}

# The 10 checklist rows follow one predictable naming pattern - generated
# rather than hand-typed twice, so it can never drift out of step with
# build_eht_pre_insulation_template.py / eht_pre_insulation_field_positions.py's
# own field names.
for _n in range(1, 11):
    FIELD_MAP[f"pre_ins_item_{_n}_result"] = f"pre_ins_item_{_n}_result"
    FIELD_MAP[f"pre_ins_item_{_n}_comments"] = f"pre_ins_item_{_n}_comments"

# No checkbox groups, no ATC-style field-specific on-states, no multi-widget
# fields, and no artifact/decorative widgets on this template - it was
# built for this form only, with exactly the 44 fields the schema declares.
YES_NO_CHECKBOXES = {}
CHECKBOX_ON = "/Yes"
CHECKBOX_OFF = "/Off"

# Nothing on this form is hand-signed-only - every sign-off cell is a real
# fillable field (see module docstring).
UNMAPPED_NOTE = None
