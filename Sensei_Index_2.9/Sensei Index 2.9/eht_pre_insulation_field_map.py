# -*- coding: utf-8 -*-
"""
Maps each eht_pre_insulation_schema.py field id to the ACTUAL AcroForm field
name inside EHT_and_RTD_Pre-Insulation_Installation_Report_TEMPLATE.pdf.

Unlike eht_removal_field_map.py/eht_rtd_field_map.py, this is not a
reverse-engineered map against someone else's original PDF - there was no
original fillable PDF for this form (YCQE-EHT-004 Rev.0), only hand-filled
scans. The template itself was built from scratch by
build_eht_pre_insulation_template.py, and the field names chosen there are
exactly the schema's own ids - so this map is a clean identity mapping,
not a lookup table of legacy "Text##"-style widget names.

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
because the implementation plan left it open ("decide when building the
template") and a real digital field keeps the export fully self-contained,
consistent with how every other field on this form works. If a wet/typed
signature convention is wanted instead, this is the field to repoint.
"""

FIELD_MAP = {
    "customer_name": "customer_name",
    "project_name": "project_name",
    "contract_no": "contract_no",
    "location": "location",

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

    "yanda_rep_date": "yanda_rep_date",
    "yanda_rep_signature": "yanda_rep_signature",
    "client_rep_date": "client_rep_date",
    "client_rep_signature": "client_rep_signature",
}

# The 10 checklist rows follow one predictable naming pattern - generated
# rather than hand-typed twice, so it can never drift out of step with
# build_eht_pre_insulation_template.py's own field names.
for _n in range(1, 11):
    FIELD_MAP[f"pre_ins_item_{_n}_result"] = f"pre_ins_item_{_n}_result"
    FIELD_MAP[f"pre_ins_item_{_n}_comments"] = f"pre_ins_item_{_n}_comments"

# No checkbox groups, no ATC-style field-specific on-states, no multi-widget
# fields, and no artifact/decorative widgets on this template - it was
# built for this form only, with exactly the 46 fields the schema declares.
YES_NO_CHECKBOXES = {}
CHECKBOX_ON = "/Yes"
CHECKBOX_OFF = "/Off"

# Nothing on this form is hand-signed-only - every sign-off cell is a real
# fillable field (see module docstring).
UNMAPPED_NOTE = None
