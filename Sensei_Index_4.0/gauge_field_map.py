# -*- coding: utf-8 -*-
"""
Maps each gauge_schema.py field id to the ACTUAL field name inside the
original Gauge Inspection Record PDF (Form# YCQP-E&I-201, Rev. 1).

Verified directly against the PDF's AcroForm field dictionary (23 fields,
all plain text widgets, all on page 1 - extract_form_field_info.py) cross-
checked against the rendered page image so every field name is tied to
the label actually printed next to it, not guessed from field order.

A value of None means that item has no real, digitally-fillable field on
the original PDF - the Excel log still records it, but
export_gauge_to_pdf.py can't push it onto the PDF.
"""

# ------------------------------------------------------- simple 1-to-1 map
FIELD_MAP = {
    "project": "Text1",
    "location": "Text2",
    "job_no": None,  # no fillable field on the original for this

    "tag": "Text3",
    "service": "Text4",
    "system": "Text5",
    "line_number": "Text7",
    "pid_number": "Text9",
    "gauge_type": "Text6",
    "make": "Text10",
    "model": "Text14",
    "serial_number": "Text8",
    "range_low": "Text11",
    "range_high": "Text12",
    "units": "Text13",
    "installation_details": None,  # not on the PDF form at all - Excel-only

    # PART 3 - Visual Inspection: each item's "Initial / NA" cell is one
    # plain text widget (type in initials, or "N/A") - not a checkbox, same
    # convention as transmitter_field_map.py's own vi_ items.
    "vi_1": "Text15",
    "vi_2": "Text18",
    "vi_3": "Text19",
    "vi_4": "Text20",
    "vi_5": "Text21",
    "vi_6": "Text22",

    # PART 4 - Remarks is one real multiline box on this form (unlike
    # transmitter's 7-single-line-field split) - a single direct mapping.
    "remarks": "Text23",

    "yanda_qc_name": "Text24",
    "yanda_qc_date": "Text25",
    "yanda_qc_signature": None,   # hand-signed / stamped, see SIGNATURE_* below
    "client_name": None,          # no fillable field on the original for this
    "client_date": None,
    "client_signature": None,

    # Engineering-index fields (plate 6a) - Excel-only, never touch the PDF.
    "pid_rev": None,
    "cal_due_date": None,
    "datasheet_rev": None,
    "doc_status": None,
    "open_ecn": None,
}

# Fields on the original PDF with no real digital field behind them - shown
# to the user once as a heads-up, not a per-row warning. "Job No." and
# "Customer Ref#" are blank lines on the form itself with no AcroForm
# widget; the whole Client Representative block (Name/Date/Signature) and
# the Yanda QC Representative's own Signature line are the same - meant for
# hand/Bluebeam markup, matching transmitter_field_map.py's and
# valve_field_map.py's identical treatment of their own un-fillable fields.
UNMAPPED_FIELD_LABELS = [
    "Job No.",
    "Customer Ref#",
    "Yanda QC Representative - Signature",
    "Client Representative - Name",
    "Client Representative - Date",
    "Client Representative - Signature",
]
