# -*- coding: utf-8 -*-
"""
Single source of truth for every field on the Gauge Inspection Record
(Form# YCQP-E&I-201, "GAUGE INSPECTION RECORD" - Yanda/Cooec Canada Co.
Ltd.). Same contract transmitter_schema.py and valve_schema.py already
follow - see transmitter_schema.py's module docstring for what each field
key means and how LOG_COLUMNS/by_section/by_id/CONTROL_FIELD are used
(by data_access.py, export_gauge_to_pdf.py, gui_app.py, index_view.py).

This is the third equipment type added to the app (after Transmitter and
Valve) - EQUIPMENT_TYPES in data_access.py carries the per-type metadata
(serial_field/qa_date_field/desc_field/etc.) that lets the rest of the
app treat any number of equipment types generically instead of assuming
exactly two.
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


# ------------------------------------------------ PART 1 - Project Description
_add("project", "Project", "part1")
_add("location", "Location", "part1")
_add("job_no", "Job No.", "part1")  # no fillable field on the original PDF

# ------------------------------------------------- PART 2 - Gauge Description
_add("tag", "Tag", "part2")
_add("service", "Service", "part2")
_add("system", "System", "part2")
_add("line_number", "Line Number", "part2")
_add("pid_number", "P&ID Number", "part2")
_add("gauge_type", "Gauge Type", "part2")
_add("make", "Make", "part2")
_add("model", "Model", "part2")
_add("serial_number", "Serial Number", "part2")
_add("range_low", "Gauge Range Low", "part2")
_add("range_high", "Gauge Range High", "part2")
_add("units", "Gauge Units", "part2")
# Not on the PDF form itself - present in the gauge serial list source data
# (its "Installation Details" column) and worth keeping alongside the rest
# of a gauge's identity, the same way transmitter_schema.py keeps
# customer_ref even though export_to_pdf.py has nowhere to put it either.
_add("installation_details", "Installation Details", "part2")

# ---------------------------------------------- PART 3 - Visual Inspection ---
VISUAL_INSPECTION_ITEMS = [
    "Stamped SS tag attached.",
    "Stamped SS cable tag attached.",
    "Gauge is installed as per P&ID drawings and installation details.",
    "Gauge is legible. Gauge faces the right direction.",
    "Confirm calibration tag is current.",
    "Confirm the gauge range/units and verify or record above.",
]
for i, text in enumerate(VISUAL_INSPECTION_ITEMS, start=1):
    _add(f"vi_{i}", f"{i}. {text} (Initial/NA)", "part3")

# ------------------------------------------------------- PART 4 - Remarks ----
_add("remarks", "Remarks", "part4", "multiline")

# ----------------------------------------------- PART 5 - Inspected/Approved -
_add("yanda_qc_name", "Yanda QC Representative - Name", "part5")
_add("yanda_qc_date", "Yanda QC Representative - Date", "part5")
_add("yanda_qc_signature", "Yanda QC Representative - Signature", "part5")
# Neither the Client Representative fields nor either signature line has a
# real fillable widget on the original PDF (confirmed against its AcroForm
# field dictionary - see gauge_field_map.py) - hand-sign/date those after
# exporting, same convention valve_field_map.py's UNMAPPED_NOTE documents
# for the valve form's equivalent blocks.
_add("client_name", "Client Representative - Name", "part5")
_add("client_date", "Client Representative - Date", "part5")
_add("client_signature", "Client Representative - Signature", "part5")

# --------------------------------------------------- INDEX - engineering -----
# Same purpose as transmitter_schema.py's / valve_schema.py's own "index"
# section (plate 6a) - not on the paper form, additive, invisible to PDF
# export. Only the subset that meaningfully applies to a passive gauge
# (no loop, no I/O, no home-run cable of its own the way a transmitter or
# valve's positioner has) - loop_id/hookup_dwg/loop_dwg/jb_number/
# cable_number/io_address/eng_units are deliberately left out rather than
# carried over just because transmitter/valve happen to have them; gauge's
# own "units" field above already covers what eng_units would have.
_add("pid_rev", "P&ID Rev", "index")
_add("cal_due_date", "Cal. Due Date", "index")
_add("datasheet_rev", "DS Rev", "index")
_add("doc_status", "Doc Status", "index", "choice", ["IFC", "IFR", "ECN", "SUP"])
_add("open_ecn", "Open ECN", "index")


# Extra column that only exists in the Excel log (not on the PDF form
# itself) - the checkbox-like flag that export_gauge_to_pdf.py looks at to
# decide which rows to turn into filled PDFs.
CONTROL_FIELD = {
    "id": "export_flag",
    "label": "Export to PDF (Y/N)",
    "section": "control",
    "ftype": "choice",
    "choices": ["Y", "N"],
}

# Full column plan for the Excel log: control column first, then every PDF
# form field in order. Both the workbook-migration tooling and
# export_gauge_to_pdf.py import this so the workbook's columns and the
# script that reads them can never drift apart.
LOG_COLUMNS = [CONTROL_FIELD] + FIELDS


def by_section(section):
    return [f for f in FIELDS if f["section"] == section]


def by_id(field_id):
    for f in FIELDS:
        if f["id"] == field_id:
            return f
    return None


SECTION_TITLES = {
    "control": "Status",
    "part1": "PART 1 – Project Description",
    "part2": "PART 2 – Gauge Description",
    "part3": "PART 3 – Visual Inspection",
    "part4": "PART 4 – Remarks",
    "part5": "PART 5 – Inspected/Approved By",
    "index": "Engineering Index",
}

if __name__ == "__main__":
    print(f"Total fields: {len(FIELDS)}")
    from collections import Counter
    c = Counter(f["section"] for f in FIELDS)
    for sec, n in c.items():
        print(f"  {sec}: {n}")
