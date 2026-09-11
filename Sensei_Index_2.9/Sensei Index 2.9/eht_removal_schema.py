# -*- coding: utf-8 -*-
"""
Single source of truth for every field on the EHT Removal and Reinstatement
Report (YCQE-EHT-019 Rev.0) - the Electrical side's equivalent of
transmitter_schema.py / valve_schema.py. Used by:
  - export_eht_removal_to_pdf.py  (fills the PDF template from a selected row)
  - electrical_data_access.py     (reads/writes the Excel log sheet)
  - gui_app.py                    (the Electrical edit form)

Each field:
  id       - internal key (must be unique)
  label    - Human readable label used as the Excel column header and the
             edit form's caption
  section  - Which part of the form it belongs to (for grouping/headers)
  ftype    - 'text' | 'multiline' | 'choice'
  choices  - list of allowed values, only for ftype == 'choice'

This form's 46 checklist items (Full EHT Removal, Partial EHT Removal,
Re-Installation, QA/QC Final Walk Down) are each modeled as TWO ordinary
text fields, "<item>_yes" and "<item>_na" - every one of the 92
Yes-Initial/N-A-Initial cells on the real PDF is a plain, independent
text box (verified against the PDF's own AcroForm - /Tx, never /Btn),
not a shared widget pair a single value gets routed between. Whoever's
filling it in writes their initials into whichever one applies and
leaves the other blank, exactly as the paper form works. valve_schema.py's
own fv_1..fv_8 items use this same "<item>_yes"/"<item>_na" split now too
(they didn't originally - see valve_field_map.py's own FIELD_MAP comment
for why that changed).

No CONTROL_FIELD ("Export to PDF Y/N") gate column, unlike transmitter/
valve - Electrical v1 only exports one row to PDF at a time (from the row's
own detail view), not a batch flagged in the sheet.
"""

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
_add("customer_name", "Customer Name", "header")
_add("project_name", "Project Name", "header")
_add("contract_no", "Contract #", "header")
_add("location", "Location", "header")
_add("trace_tag", "Trace Tag #", "header")
_add("area", "Area", "header")
_add("system_no", "System No.", "header")
_add("alarm", "Alarm", "header", "choice", YES_NO)
_add("eht_type", "EHT Type", "header", "choice", ["SR", "MI"])
_add("eht_length", "EHT Length", "header")
_add("ehtc_no", "EHTC #", "header")
_add("panel_no", "Panel #", "header")
_add("breaker_no", "Breaker #", "header")
_add("eht_iso_drawing_no", "EHT ISO Drawing No.", "header")

# ---------------------------------------------------- Full EHT Removal -----
_add("full_removal_na", "Full EHT Removal - N/A", "full_removal", "choice", ["Y", "N"])
FULL_REMOVAL_ITEMS = [
    "Lock out and testing for de-energization has been completed",
    "Pre-removal ohm reading and megger completed and documented",
    "Tracer has been removed safely and without damage",
    "Tracer has been removed from power kit / JB - penetration has been sealed",
    "Tracer has been properly wrapped and tagged to protect against damage",
    "Post removal ohm reading and megger reading completed and documented",
    "Power kit / JB has been put back to original state for re-energization if necessary",
    "All safeguards on terminal blocks / controllers / panels re-installed",
    "Trade lock has been removed",
    "Circuit is ready to be energized",
    "Trace is stored in sea can container for later re-installation",
]
for _n, _text in enumerate(FULL_REMOVAL_ITEMS, start=1):
    _add(f"full_removal_item_{_n}_yes", f"Full Removal {_n}. {_text} - Yes/Initial", "full_removal")
    _add(f"full_removal_item_{_n}_na", f"Full Removal {_n}. {_text} - N/A Initial", "full_removal")

# ------------------------------------------------- Partial EHT Removal -----
_add("partial_removal_na", "Partial EHT Removal - N/A", "partial_removal", "choice", ["Y", "N"])
PARTIAL_REMOVAL_ITEMS = [
    "Lock out and testing for de-energization has been completed",
    "Pre-removal ohm reading and megger completed and documented",
    "Trace is rolled back to the appropriate distance, out of the way of other craft",
    "Trace is completely wrapped in fire blanket and tagged with caution tags - extra care "
    "must be taken to separate MI lines to avoid touching metal to metal",
    "Post removal ohm reading and megger reading completed and documented",
    "Power kit / JB has been put back to original state for re-energization if necessary",
    "All safeguards on terminal blocks/controllers/panels re-installed",
    "Trade lock has been removed",
    "Circuit is ready to be energized",
]
for _n, _text in enumerate(PARTIAL_REMOVAL_ITEMS, start=1):
    _add(f"partial_removal_item_{_n}_yes", f"Partial Removal {_n}. {_text} - Yes/Initial", "partial_removal")
    _add(f"partial_removal_item_{_n}_na", f"Partial Removal {_n}. {_text} - N/A Initial", "partial_removal")

# -------------------------------------------------------- Re-Installation --
# No section-level N/A checkbox exists for this section on the real form.
REINSTALL_ITEMS = [
    "Lock out and testing for de-energization has been completed",
    "Pre-installation ohm reading and megger completed and documented",
    "MI tracers shall not cross and run/wraps shall be a minimum of 1\" apart and secured a "
    "maximum of 18\" apart. Tracer bends shall be a minimum of 6 times the O.D. of the tracer",
    "S.R / P.L. tracers shall be secured at a maximum interval of 12\", only use tape supplied "
    "by the manufacturer",
    "Confirm that correct tagging has been installed at all EHT power points, temperature "
    "sensing devices and temperature controllers as per IFC drawings and specifications",
    "Cold leads / end bullets or thermostat capillary and RTD leads egress from the lower half "
    "of the pipe insulation on piping above 300 degrees, per drawings",
    "Tracer, power kit, end kit, temperature device and cable support is installed so as not "
    "to interfere with plant maintenance & installed as per detail & manufacturer's instructions",
    "Tracing shall not be installed over pipe plugs or interfere with a sensing device (i.e. "
    "diaphragms, temperature gauges, etc.)",
    "Adequate support is installed at bends, fittings, JBs and enclosures",
    "Tracers are installed into the power boxes and end kits are complete",
    "Inspect all instruments, weather protection boxes and tubing bundles to ensure they are "
    "installed & terminated as per IFC drawings and specifications",
    "Post installation ohm reading and megger completed and documented",
    "Tug test wiring to ensure terminations are secure",
    "Trade lock has been removed",
    "All work is complete and circuit is ready for final QA/QC walkdown",
]
for _n, _text in enumerate(REINSTALL_ITEMS, start=1):
    _add(f"reinstall_item_{_n}_yes", f"Re-Installation {_n}. {_text} - Yes/Initial", "reinstallation")
    _add(f"reinstall_item_{_n}_na", f"Re-Installation {_n}. {_text} - N/A Initial", "reinstallation")

# ---------------------------------------------------- QA/QC Final Walkdown -
WALKDOWN_ITEMS = [
    "Tracer is fully secured to pipe following client standards",
    "All splices (if any) have been completed and tested",
    "Junction boxes and end kits are secured, clean and operational",
    "All locks have been removed",
    "Area is clean and free of waste and debris",
    "Pre-insulation point to point and megger values recorded - walk down / spot check with "
    "EHT leads, for all high value tracers/critical path",
    "IDR to insulation released",
    "Insulation complete - IDR to electrical released",
    "Post insulation point to point and megger recorded",
    "Red line drawings submitted to client",
    "Close out steps in P6",
]
for _n, _text in enumerate(WALKDOWN_ITEMS, start=1):
    _add(f"walkdown_item_{_n}_yes", f"Walkdown {_n}. {_text} - Yes/Initial", "walkdown")
    _add(f"walkdown_item_{_n}_na", f"Walkdown {_n}. {_text} - N/A Initial", "walkdown")

# ------------------------------------------------------- Testing Activities
TEST_VOLTAGE = ["500 VDC", "1000 VDC"]
TEST_BLOCKS = [
    ("test1", "Test 1 (Before Rollback, by Crew)"),
    ("test2", "Test 2 (After Rollback, by Crew)"),
    ("test3", "Test 3 (Before Re-Install, by Crew)"),
    ("test4", "Test 4 (After Installation, by QC)"),
    ("test5", "Test 5 (After Insulation, by QC)"),
]
for _prefix, _block_label in TEST_BLOCKS:
    _add(f"{_prefix}_voltage", f"{_block_label} - Test Voltage", "testing", "choice", TEST_VOLTAGE)
    _add(f"{_prefix}_date", f"{_block_label} - Date", "testing")
    _add(f"{_prefix}_amb_temp", f"{_block_label} - Amb. Temp (°C)", "testing")
    _add(f"{_prefix}_tested_by", f"{_block_label} - Tested By", "testing")
    _add(f"{_prefix}_test_equip", f"{_block_label} - Test Equip.#", "testing")
    _add(f"{_prefix}_ir_value", f"{_block_label} - IR Value", "testing")
    _add(f"{_prefix}_continuity", f"{_block_label} - Continuity", "testing")

# --------------------------------------------------------------- Comments --
_add("comments_na", "Comments/Delays - N/A", "comments", "choice", ["Y", "N"])
_add("comments", "Comments / Delays", "comments", "multiline")

# --------------------------------------------------------------- Sign-Off --
_add("yanda_rep_name", "Yanda Representative - Name", "signoff")
_add("yanda_rep_date", "Yanda Representative - Date", "signoff")
_add("yanda_rep_signature", "Yanda Representative - Signature", "signoff")
_add("client_rep_name", "Client Representative - Name", "signoff")
_add("client_rep_date", "Client Representative - Date", "signoff")
_add("client_rep_signature", "Client Representative - Signature", "signoff")


def by_section(section):
    return [f for f in FIELDS if f["section"] == section]


SECTION_TITLES = {
    "header": "Header",
    "full_removal": "Full EHT Removal",
    "partial_removal": "Partial EHT Removal",
    "reinstallation": "Re-Installation",
    "walkdown": "QA/QC Final Walk Down",
    "testing": "Testing Activities",
    "comments": "Comments / Delays",
    "signoff": "Sign-Off",
}

LOG_COLUMNS = FIELDS

if __name__ == "__main__":
    print(f"Total fields: {len(FIELDS)}")
