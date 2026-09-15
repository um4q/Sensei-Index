# -*- coding: utf-8 -*-
"""
Single source of truth for every field on the Transmitter Inspection & Test
Record. Used by:
  - build_pdf_template.py  (creates the blank fillable PDF)
  - build_excel_log.py     (creates the Excel data-entry log)
  - export_to_pdf.py       (fills the PDF template from selected Excel rows)

Each field:
  id       - PDF form field name / internal key (must be unique)
  label    - Human readable label used as the Excel column header and the
             PDF field's on-page caption
  section  - Which PART of the form it belongs to (for grouping/headers)
  ftype    - 'text' | 'multiline' | 'choice'
  choices  - list of allowed values, only for ftype == 'choice'
"""

PASS_FAIL_NA = ["Pass", "Fail", "N/A"]
YES_NO = ["Yes", "No"]

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
_add("customer_ref", "Customer Ref#", "header")

# ------------------------------------------------------ PART 1 - Project ---
_add("project", "Project", "part1")
_add("location", "Location", "part1")
_add("contract_no", "Contract #", "part1")

# ------------------------------------------------ PART 2 - Transmitter -----
_add("tag", "Tag", "part2")
_add("transmitter_type", "Transmitter Type", "part2")
_add("system_number", "System Number", "part2")
_add("service", "Service", "part2")
_add("pid_number", "P&ID Number", "part2")
_add("line_number", "Line Number", "part2")
_add("make", "Make", "part2")
_add("model", "Model", "part2")
_add("serial_number", "Serial Number", "part2")
_add("calibration_range", "Calibration Range", "part2")
_add("instrument_range", "Instrument Range", "part2")
_add("repeatability", "Repeatability", "part2")
_add("local_display", "Local Display", "part2", "choice", YES_NO)
_add("signal_type", "Signal Type", "part2")
_add("k_factor", "K-Factor", "part2")
_add("scale_factor", "Scale Factor", "part2")

# ------------------------------------------- PART 3 - Visual Inspection ----
VISUAL_INSPECTION_ITEMS = [
    "Stamped SS instrument tag attached.",
    "Stamped SS cable tag attached.",
    "Device installed as per P&ID drawings and installation details.",
    "Equipment accessible and easy to maintain.",
    "Verify impulse line(s) are correctly installed.",
    "Manifold/isolation valve(s) conform to data sheets.",
    "Wiring polarity correct and properly labeled.",
    "Tug test terminations.",
    "Perform insulation check on wiring.",
    "Check enclosure labeling.",
    "Check enclosure mounting/orientation.",
    "Check boot and seal(s). (All openings sealed)",
]
for i, text in enumerate(VISUAL_INSPECTION_ITEMS, start=1):
    _add(f"vi_{i}", f"{i}. {text} (Initial/NA)", "part3")

# ------------------------------------------------- PART 4 - Procedure ------
_add("proc_1_vdc", "1. Power the transmitter and measure the voltage (VDC)", "part4")

PROCEDURE_ITEMS = [
    (2, "Perform leak check procedure."),
    (3, "Power enclosure heater and verify operations."),
    (4, "Power traced tubing bundle(s) and verify operation."),
    (5, "Disconnect wire (open loop) and verify fault."),
    (6, "Verify local display(s) operational."),
    (7, "Ensure process sensing/impulse lines are open."),
    (8, "Verify signal configuration."),
    (9, "Ensure manifolds are placed back into service position."),
    (10, "Confirm controller action as per loop narrative."),
    (11, "Graphic display matches with function."),
    (12, "Construction QA/QC Documents Verified."),
    (13, "Is loop left energized and ready for service."),
    (14, "Place \"pre-commissioned\" tag on instrument."),
]
for num, text in PROCEDURE_ITEMS:
    _add(f"proc_{num}", f"{num}. {text}", "part4", "choice", PASS_FAIL_NA)

# --------------------------------------------- PART 5 - Test Equipment -----
for row in (1, 2, 3):
    _add(f"te{row}_make", f"Test Equip {row} - Make", "part5")
    _add(f"te{row}_model", f"Test Equip {row} - Model", "part5")
    _add(f"te{row}_serial", f"Test Equip {row} - Serial", "part5")
    _add(f"te{row}_caldate", f"Test Equip {row} - Calibration Date", "part5")

# ----------------------------------------------- PART 6 - Test Results -----
TEST_RESULT_PCTS = [0, 25, 50, 75, 100]
TEST_RESULT_MEASURES = [
    ("input", "Input"),
    ("output", "Output"),
    ("localdisplay", "Local Display"),
    ("dcs", "DCS Display/Units"),
]
for pct in TEST_RESULT_PCTS:
    for mkey, mlabel in TEST_RESULT_MEASURES:
        _add(f"tr_{pct}_{mkey}_up", f"{pct}% {mlabel} Upscale", "part6")
        _add(f"tr_{pct}_{mkey}_down", f"{pct}% {mlabel} Downscale", "part6")
_add("system_results", "System Results", "part6", "choice", PASS_FAIL_NA)

# ---------------------------------------------------- PART 7 - Remarks -----
_add("remarks", "Remarks", "part7", "multiline")

# ------------------------------------------- PART 8 - Inspected/Approved ---
_add("yanda_qa_name", "Yanda QA Representative - Name", "part8")
_add("yanda_qa_date", "Yanda QA Representative - Date", "part8")
_add("yanda_qa_signature", "Yanda QA Representative - Signature", "part8")
_add("client_name", "Client Representative - Name", "part8")
_add("client_date", "Client Representative - Date", "part8")
_add("client_signature", "Client Representative - Signature", "part8")


# Extra column that only exists in the Excel log (not on the PDF form
# itself) - the checkbox-like flag that export_to_pdf.py looks at to decide
# which rows to turn into filled PDFs.
CONTROL_FIELD = {
    "id": "export_flag",
    "label": "Export to PDF (Y/N)",
    "section": "control",
    "ftype": "choice",
    "choices": ["Y", "N"],
}

# Full column plan for the Excel log: control column first, then every PDF
# form field in order. Both build_excel_log.py and export_to_pdf.py import
# this so the workbook's columns and the script that reads them can never
# drift apart.
LOG_COLUMNS = [CONTROL_FIELD] + FIELDS


def by_section(section):
    return [f for f in FIELDS if f["section"] == section]


def by_id(field_id):
    for f in FIELDS:
        if f["id"] == field_id:
            return f
    return None


SECTION_TITLES = {
    "header": "Header Info",
    "part1": "PART 1 \u2013 Project Description",
    "part2": "PART 2 \u2013 Transmitter Description",
    "part3": "PART 3 \u2013 Visual Inspection",
    "part4": "PART 4 \u2013 Procedure",
    "part5": "PART 5 \u2013 Test Equipment",
    "part6": "PART 6 \u2013 Test Results",
    "part7": "PART 7 \u2013 Remarks",
    "part8": "PART 8 \u2013 Inspected/Approved By",
}

if __name__ == "__main__":
    print(f"Total fields: {len(FIELDS)}")
    from collections import Counter
    c = Counter(f["section"] for f in FIELDS)
    for sec, n in c.items():
        print(f"  {sec}: {n}")
