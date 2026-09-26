# -*- coding: utf-8 -*-
"""
Maps each general_equip_install_schema.py field id to the ACTUAL AcroForm
field name inside
General_Electrical_Equipment_Installation_and_Test_Report_TEMPLATE.pdf.

The template was built from the user's own real, official source document
(a Word .docx converted to PDF) with every fillable widget named after
this schema's own field id - so this is a clean identity mapping, not a
lookup table of legacy "Text##"-style widget names. Kept as a real dict
anyway so this form follows the same shape every other Electrical form's
field_map.py uses.

No checkbox fields on this template - every "Yes Initial"/"N/A Initial"
cell is a plain text widget, same "plain text, not a real checkbox"
choice this whole Electrical family makes for every cell on its own
template.

yanda_rep_signature's own typed value is skipped whenever the automatic
Yanda Representative signature-image stamp (same mechanism
export_gauge_to_pdf.py/export_transformer_test_to_pdf.py already use) is
applied on top of this exact cell (page 2 of this form) - see
export_general_equip_install_to_pdf.py's stamp_signature()/fill_pdf() for
the details. client_rep_signature is untouched by any of this - still a
plain typed field, hand-signed only.
"""

FIELD_MAP = {f["id"]: f["id"] for f in __import__("general_equip_install_schema").FIELDS}

YES_NO_CHECKBOXES = {}
CHECKBOX_ON = "/Yes"
CHECKBOX_OFF = "/Off"

# Nothing on this form is hand-signed-only except client_rep_signature -
# every other sign-off cell is a real fillable field (see module docstring).
UNMAPPED_NOTE = None
