# -*- coding: utf-8 -*-
"""
Single source of truth for every field on the EHT & RTD Pre-Insulation
Installation Report (YCQE-EHT-004 Rev.0) - the Electrical side's third
form. Used by:
  - export_eht_pre_insulation_to_pdf.py  (fills the PDF template from a selected row)
  - electrical_data_access.py            (reads/writes the Excel log sheet)
  - gui_app.py                           (the Electrical edit form)

Each field:
  id       - internal key (must be unique)
  label    - Human readable label used as the Excel column header and the
             edit form's caption
  section  - Which part of the form it belongs to (for grouping/headers)
  ftype    - 'text' | 'multiline' | 'choice'
  choices  - list of allowed values, only for ftype == 'choice'

Do not confuse this form with eht_rtd_schema.py's "EHT & RTD Installation
Inspection Report" (YCQE-E&I-004 Rev.0) - similar name, different form
number, and structurally much simpler: a single pre-insulation section
only, no post-insulation section, no per-voltage MI/SR checkbox grid. The
two are independent equipment types with independent sheets.

REVISION 2 (exact-fidelity template rebuild): the template this schema is
mapped against is now the real scanned form itself (background image),
not a reportlab redraw - see build_eht_pre_insulation_template.py's own
docstring. Rebuilding against the actual scan surfaced two corrections
versus the original 46-field version:

  - Customer Name / Project Name / Contract # / Location are PRINTED on
    every one of the 19 scanned instances (confirmed by inspection - not
    hand-filled anywhere), so they are NOT fillable fields here - they're
    part of the template's background image, the same precedent
    eht_removal_schema.py / eht_rtd_schema.py already set for their own
    header rows. (The original version made these real fields, which was
    a mistake corrected here.)
  - The sign-off table's "Yanda Representative" / "Client Representative"
    columns hold a handwritten NAME on the real form (e.g. "Dana
    Eshleyah"), not signature-only as originally assumed - added as
    yanda_rep_name / client_rep_name.

Total: 46 - 4 header fields + 2 name fields = 44.

The "Results (Initial/N/A)" cells are plain text boxes (not checkboxes),
modeled here as ftype="text" (free-form initials or "N/A" - see
eht_rtd_schema.py's docstring for why the sibling form's equivalent cells
are instead modeled as ftype="choice"; this form's checklist is initialed
rather than Y/N/NA, so a fixed choices list doesn't fit).

The "1.8 Pre-Insulation Insulation Test Results" megger table's section
label deliberately repeats "1.8" from item 9 in the checklist above (item
9 is itself numbered 9, not 1.8 - the "1.8" is the source document's own
table caption, printed directly above/left of the SR/MI @ 500/1000/2500
VDC rows, not a checklist item number). This is a genuine quirk in the
client's own form, preserved as-is - not "fixed" here.
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


# ------------------------------------------------------------ Trace Data ---
_add("trace_number", "Trace #", "trace_data")
_add("eht_controller_number", "EHT Controller #", "trace_data")
_add("trace_part_number", "Trace Part #", "trace_data")
_add("panel_number", "Panel #", "trace_data")
_add("rtds_number", "RTD(s) #", "trace_data")
_add("circuit_number", "Circuit #", "trace_data")
_add("trace_line_number", "Trace Line #", "trace_data")
_add("rev", "Rev #", "trace_data")

# ------------------------------------------------- Pre-Insulation Inspection
_CHECKLIST_LABELS = [
    "EHT Receiving Report has been Completed if required",
    "EHT Tag Matches Part # and drawings",
    "EHT is Routed and Installed as per specifications",
    "RTD's Receiving Report has been Completed if required",
    "RTD's are installed as per drawing and specification",
    "EHT/RTD's Tags are correctly labelled and installed",
    "As-built drawings completed and submitted",
    "Terminations are complete with correct wire tags",
    "SR/MI Trace Continuity test passed (Record Resistance)",
    "EHT/RTD's Released for Insulation",
]
for _n, _label in enumerate(_CHECKLIST_LABELS, start=1):
    _add(f"pre_ins_item_{_n}_result", f"{_n}. {_label} - Result", "pre_insulation")
    _add(f"pre_ins_item_{_n}_comments", f"{_n}. {_label} - Comments", "pre_insulation")

# ------------------------------------------------ Insulation Testing Equipment
_add("test_equip_model", "Test Equip. Model #", "equipment")
_add("test_equip_serial", "Test Equip. Serial #", "equipment")
_add("cal_due_date", "Cal. Due Date", "equipment")

# "1.8 Pre-Insulation Insulation Test Results" - see module docstring re:
# the duplicated "1.8" caption.
_add("megger_500_reading", "SR/MI @ 500 VDC - Reading", "equipment")
_add("megger_500_result", "SR/MI @ 500 VDC - Passed/Fail", "equipment")
_add("megger_1000_reading", "SR/MI @ 1000 VDC - Reading", "equipment")
_add("megger_1000_result", "SR/MI @ 1000 VDC - Passed/Fail", "equipment")
_add("megger_2500_reading", "SR/MI @ 2500 VDC - Reading", "equipment")
_add("megger_2500_result", "SR/MI @ 2500 VDC - Passed/Fail", "equipment")

# --------------------------------------------------------------- Comments --
_add("comments", "Comments", "comments", "multiline")

# ---------------------------------------------------------------- Sign-off -
# Both the name and the date/signature cells are real fillable fields on
# this template - the real form has a handwritten name under each
# "Yanda Representative"/"Client Representative" column header, not
# signature-only (see module docstring).
_add("yanda_rep_name", "Yanda Representative - Name", "signoff")
_add("yanda_rep_date", "Yanda Representative - Date (yy/mm/dd)", "signoff")
_add("yanda_rep_signature", "Yanda Representative - Signature", "signoff")
_add("client_rep_name", "Client Representative - Name", "signoff")
_add("client_rep_date", "Client Representative - Date (yy/mm/dd)", "signoff")
_add("client_rep_signature", "Client Representative - Signature", "signoff")


def by_section(section):
    return [f for f in FIELDS if f["section"] == section]


SECTION_TITLES = {
    "trace_data": "Trace Data",
    "pre_insulation": "1.0 Pre-Insulation Inspection",
    "equipment": "Insulation Testing Equipment",
    "comments": "Comments",
    "signoff": "Sign-Off",
}

LOG_COLUMNS = FIELDS

if __name__ == "__main__":
    print(f"Total fields: {len(FIELDS)}")
