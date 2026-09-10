# -*- coding: utf-8 -*-
"""
Single source of truth for every field on the Torqueing Report
(YCQE-E&I-014 Rev.0) - the Electrical side's fourth form. Used by:
  - export_torqueing_to_pdf.py    (fills the PDF template from a selected row)
  - electrical_data_access.py     (reads/writes the Excel log sheet)
  - gui_app.py                    (the Electrical edit form)

Each field:
  id       - internal key (must be unique)
  label    - Human readable label used as the Excel column header and the
             edit form's caption
  section  - Which part of the form it belongs to (for grouping/headers)
  ftype    - 'text' | 'multiline' | 'choice'
  choices  - list of allowed values, only for ftype == 'choice'

Unlike eht_pre_insulation, the original YCQE-E&I-014_TORQUEING_REPORT.pdf
IS a real, born-digital fillable PDF (not a hand-filled scan) - same
situation as eht_removal/eht_rtd, so the template here is the ORIGINAL
PDF itself (with its own baked-in sample values cleared - see
torqueing_field_map.py's docstring), not a from-scratch rebuild. Every
field name below was reverse-engineered directly from that PDF's own
AcroForm field dictionary and on-page position (grouped by row/column via
each widget's /Rect) - see torqueing_field_map.py for the id -> real
field name mapping.

The bolt/termination table holds up to 15 rows on the real form (row 1
uses the original author's own human-readable field names - "NO",
"TAG #", "GRADE", ... ; rows 2-15 use generic "Text##" names, not
sequential in the "date" column - the original PDF's own authoring
quirk, not a mapping error). Modeled here as 15 independent numbered
rows (bolt_row_1_* .. bolt_row_15_*), the same "flatten a repeating table
into numbered columns" approach eht_pre_insulation's checklist and
eht_rtd's post/pre-insulation sections already use.

The original PDF has NO signature field for either representative (name
+ date only) - "SIGNATURE" is printed as a column header with a blank
cell under it, hand-signed on the original. The user explicitly asked for
a Yanda signature stamp "as the instrumentation dashboard has it" - so
export_torqueing_to_pdf.py overlays the same Yanda QA signature image
transmitter/valve already use, the same way (a reportlab overlay merged
onto the page at export time, NOT a fillable field - see that module's
stamp_signature()). Client Representative's signature stays hand-signed
only, matching transmitter/valve's own asymmetry (only YANDA's own rep
gets the automatic stamp).
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


# ---------------------------------------------------------------- Header ---
_add("customer_name", "Customer Name", "header")
_add("project_name", "Project Name", "header")
_add("contract_no", "Contract #", "header")
_add("location", "Location", "header")

# ------------------------------------------------------------- Torque Info -
_add("torque_record_number", "Torque Record No.", "torque_info")
# The real Dropdown1 field's /Opt array (dumped directly from the original
# PDF) has 14 entries, not 12 - "MULTIPLE" (for a record spanning more
# than one system) and a blank "  " default (the widget's own /V/DV are
# both set to this blank entry) bracket the 12 named "K1B-..." systems.
# Both belong here - dropping them meant a real, selectable option
# ("MULTIPLE") was unreachable from this app's own combo, and there was
# no way to explicitly keep/select the form's true unset default.
SYSTEM_NUMBER_CHOICES = [
    "MULTIPLE",
    "K1B- EHouse", "K1B- EGEN", "K1B- PT", "K1B- 600V", "K1B- UPS",
    "K1B- 600V SUS", "K1B-DCS", "K1B-IA", "K1B-WP-INJECTION-A",
    "K1B-WP-INJECTION-R", "K1B-WP-PRODUCER-A", "K1B-WP-PRODUCER-R",
    "  ",
]
_add("system_number", "System No.", "torque_info", "choice", SYSTEM_NUMBER_CHOICES)
_add("reference_tag_number", "Reference Tag #", "torque_info")
_add("torque_wrench_manufacturer", "Torque Wrench Manufacturer", "torque_info")
_add("torque_wrench_serial_number", "Torque Wrench Serial #", "torque_info")
_add("calibration_date", "Calibration Date (yyyy/mm/dd)", "torque_info")
_add("drawing_reference_number", "Drawing Reference #", "torque_info")

# ------------------------------------------------------- Bolt/Termination --
_BOLT_COLUMNS = [
    ("no", "No."),
    ("tag", "Location (Tag #)"),
    ("grade", "Bolt Grade"),
    ("size", "Bolt Size"),
    ("torque_value", "Torque Value (FT/LB)"),
    ("torqued_by", "Torqued By - Initial"),
    ("witnessed_by", "Witnessed By - Initial"),
    ("date", "Date (yyyy/mm/dd)"),
]
for _row in range(1, 16):
    for _col_id, _col_label in _BOLT_COLUMNS:
        _add(f"bolt_row_{_row}_{_col_id}", f"Row {_row} - {_col_label}", "bolt_table")

# --------------------------------------------------------------- Comments --
_add("torque_spec_document_reference", "Torque Specification Document Reference", "comments")
_add("comments_na", "Comments - N/A", "comments", "choice", ["Y", "N"])
_add("comments", "Comments", "comments", "multiline")

# ---------------------------------------------------------------- Sign-off -
# Neither representative has a real Signature FIELD on the original PDF
# (hand-signed only there) - see module docstring re: the Yanda stamp
# being applied separately at export time, outside this field list.
_add("yanda_rep_name", "Yanda Representative - Name", "signoff")
_add("yanda_rep_date", "Yanda Representative - Date (yyyy/mm/dd)", "signoff")
_add("client_rep_name", "Client Representative - Name", "signoff")
_add("client_rep_date", "Client Representative - Date (yyyy/mm/dd)", "signoff")


def by_section(section):
    return [f for f in FIELDS if f["section"] == section]


SECTION_TITLES = {
    "header": "Header",
    "torque_info": "Torque Info",
    "bolt_table": "Bolt / Termination Table",
    "comments": "Comments",
    "signoff": "Sign-Off",
}

LOG_COLUMNS = FIELDS

if __name__ == "__main__":
    print(f"Total fields: {len(FIELDS)}")
