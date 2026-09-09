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

Unlike eht_removal/eht_rtd, there was no original fillable PDF for this
form - every source instance (reference_material/EHT-004_scanned_samples/)
is a hand-filled, scanned paper form. The template this schema is mapped
against (EHT_and_RTD_Pre-Insulation_Installation_Report_TEMPLATE.pdf) was
therefore built from scratch (see build_eht_pre_insulation_template.py),
so every field name below is one this project chose itself, not one
reverse-engineered from someone else's PDF authoring.

The "Results (Initial/N/A)" cells are plain text boxes (not checkboxes),
modeled here as ftype="choice" with a permissive Y/N/NA-style convention -
same treatment eht_rtd_schema.py gives its own equivalent "Results" cells
(see that module's docstring) - but since this form's own checklist is
initialed rather than Y/N/NA, the choices list is left as free-form text
(ftype="text") instead: whoever fills it in writes their initials or
"N/A", not a fixed set of codes.

The "1.8 Pre-Insulation Insulation Test Results" megger table's section
banner deliberately repeats "1.8" from item 9 in the checklist above (item
9 is itself numbered 9, not 1.8 - the "1.8" duplicate is the source
document's own table caption, not a checklist item number). This is a
genuine quirk in the client's own form, preserved as-is - not "fixed" here.
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
# Real fillable fields, same precedent as eht_removal/eht_rtd's own header
# block (static company/document chrome aside - the logos and the
# YCQE-EHT-004 Rev.0 title are printed directly on the template, not
# fields). Default values for a new zone are "COOEC Canada Ltd." /
# "K1B Well Pad Project" / "CA23007-SCM-AGC-004" / "Module Yard" per the
# source scans, but - like eht_removal/eht_rtd - nothing in this app's code
# auto-fills them; whoever fills in the row types them in, same as every
# other field.
_add("customer_name", "Customer Name", "header")
_add("project_name", "Project Name", "header")
_add("contract_no", "Contract #", "header")
_add("location", "Location", "header")

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
# Neither representative has a separate "Print Name" cell on this
# particular form (unlike eht_removal/eht_rtd's sign-off blocks, which do)
# - confirmed against every one of the 19 scanned instances, not invented
# here. Signature is a real fillable field on this template (a typed
# name/initials entry, not a hand-signed-only field) - a deliberate choice
# left open by the implementation plan; see
# eht_pre_insulation_field_map.py's docstring.
_add("yanda_rep_date", "Yanda Representative - Date (yy/mm/dd)", "signoff")
_add("yanda_rep_signature", "Yanda Representative - Signature", "signoff")
_add("client_rep_date", "Client Representative - Date (yy/mm/dd)", "signoff")
_add("client_rep_signature", "Client Representative - Signature", "signoff")


def by_section(section):
    return [f for f in FIELDS if f["section"] == section]


SECTION_TITLES = {
    "header": "Header",
    "trace_data": "Trace Data",
    "pre_insulation": "1.0 Pre-Insulation Inspection",
    "equipment": "Insulation Testing Equipment",
    "comments": "Comments",
    "signoff": "Sign-Off",
}

LOG_COLUMNS = FIELDS

if __name__ == "__main__":
    print(f"Total fields: {len(FIELDS)}")
