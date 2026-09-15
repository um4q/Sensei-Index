# -*- coding: utf-8 -*-
"""
Single source of truth for every field on the Pneumatically Actuated Valve
Check Record (Form# YCQP-E&I-204). Mirrors schema.py from the transmitter
inspection kit. Used by:
  - build_valve_excel_log.py  (creates the Excel data-entry log)
  - export_valve_to_pdf.py    (fills the PDF template from selected Excel rows)
"""

CHOICE_TYPE = "choice"
TEXT_TYPE = "text"
INITIAL_OR_NA_TYPE = "initial_or_na"   # special: goes into a Yes-initials
                                        # widget, or an NA-initials widget

YES_NO = ["Y", "N"]

FIELDS = []


def _add(id_, label, section, ftype=TEXT_TYPE, choices=None):
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

_add("system", "System", "header")
_add("pid_number", "P&ID #", "header")
_add("line_number", "Line #", "header")
_add("equip_number", "Equip #", "header")
_add("unit_number", "Unit #", "header")
_add("valve_type", "Valve Type", "header", CHOICE_TYPE, ["ESDV", "FCV", "LCV", "PCV", "Other"])
_add("valve_type_other", "Valve Type - Other (specify)", "header")

# ------------------------------------------------ General Description ------
_add("actuator_serial", "Actuator - Serial #", "general")
_add("actuator_model", "Actuator - Model #", "general")
_add("trim_plug", "Trim - Plug", "general")
_add("trim_seat", "Trim - Seat", "general")

_add("valve_serial", "Valve - Serial #", "general")
_add("valve_model", "Valve - Model #", "general")
_add("travel_unit", "Travel - Unit", "general", CHOICE_TYPE, ["Inch", "Metric"])
_add("travel_value", "Travel - Value", "general")

_add("positioner_serial", "Positioner - Serial #", "general")
_add("positioner_model", "Positioner - Model #", "general")
_add("valve_class", "Class (ANSI Leakage Class)", "general", CHOICE_TYPE,
     ["I", "II", "III", "IV", "V", "VI"])
_add("ansi_rating", "ANSI Rating", "general", CHOICE_TYPE,
     ["150", "300", "600", "900", "1200", "1500", "2500"])

_add("position_limit_serial", "Position Limit - Serial #", "general")
_add("position_limit_model", "Position Limit - Model #", "general")
_add("ansi_size", "ANSI Rating - Size", "general")
_add("body_style", "Body Style", "general", CHOICE_TYPE, ["Flanged", "Threaded"])

_add("solenoid_serial", "Solenoid - Serial #", "general")
_add("solenoid_model", "Solenoid - Model #", "general")
_add("crn_number", "CRN#", "general")

# ------------------------------------------------ Commissioning Inspection -
_add("signal_type", "Signal Type", "commissioning", CHOICE_TYPE,
     ["4-20 mA / HART", "Fieldbus", "Wireless", "Modbus", "Pneumatic"])
_add("commissioning_tag", "Commissioning Tag #", "commissioning")
_add("voltage", "Voltage", "commissioning")
_add("fuse_rating", "Fuse Rating", "commissioning")
_add("inst_air_pressure", "Inst. Air Pressure", "commissioning")

_add("bad_io", "Bad I/O", "commissioning", CHOICE_TYPE, YES_NO)
_add("verify_device_screen_match", "Verify Device & Screen Match", "commissioning", CHOICE_TYPE, YES_NO)
_add("ss_device_tag", "SS Device Tag", "commissioning", CHOICE_TYPE, YES_NO)
_add("ss_cable_tag", "SS Cable Tag", "commissioning", CHOICE_TYPE, YES_NO)

_add("calibration_tag", "Calibration Tag", "commissioning", CHOICE_TYPE, YES_NO)
_add("wire_tagged", "Wire Tagged", "commissioning", CHOICE_TYPE, YES_NO)
_add("cable_fittings_inspected", "Cable & Fittings Inspected", "commissioning", CHOICE_TYPE, YES_NO)
_add("adequate_service_loop", "Adequate Service Loop", "commissioning", CHOICE_TYPE, YES_NO)

_add("polarity_correct_wire_tug", "Polarity Correct & Wire Tug", "commissioning", CHOICE_TYPE, YES_NO)
_add("heat_traced", "Heat Traced", "commissioning", CHOICE_TYPE, YES_NO)
_add("insulated", "Insulated", "commissioning", CHOICE_TYPE, YES_NO)
_add("tubing_fittings_inspected", "Tubing & Fittings Inspected", "commissioning", CHOICE_TYPE, YES_NO)
_add("conforms_to_install", "Conforms to Install", "commissioning", CHOICE_TYPE, YES_NO)

_add("conforms_to_pid", "Conforms to P&ID", "commissioning", CHOICE_TYPE, YES_NO)
_add("installed_by", "Installed By", "commissioning", CHOICE_TYPE, ["IESL", "Other"])
_add("verified_by", "Verified By", "commissioning", CHOICE_TYPE, ["IESL", "Other"])
_add("asme_code", "ASME Code", "commissioning", CHOICE_TYPE, YES_NO)

# ------------------------------------------- Functional Verification Acts --
FUNCTIONAL_VERIFICATION_ITEMS = [
    (1, "Blow Down Air Supply at Header, Open and Drain Instrument Regulator"),
    (2, "Valve is Sliding Stem: Rotary: Quarter Turn: Throttle: Snap Acting"),
    (3, "Verify Fail Position: Valve Fails Open / Valve Fails Closed / Valve Fails Last"),
    (4, "Verify Positioner Command Signals: mA / %"),
    (5, "Valve and Actuator Strokes Smoothly on Command From DCS/PLC"),
    (6, "Verify Open and Close Limit Switches Function and are Displayed Correctly on DCS/PLC"),
    (7, "Verify Solenoid Trip and Valve Strokes to Fail Position"),
    (8, "Verify Positioner is Returned to IN SERVICE"),
]
for num, text in FUNCTIONAL_VERIFICATION_ITEMS:
    _add(f"fv_{num}", f"{num}. {text} (initials, or N/A)", "functional", INITIAL_OR_NA_TYPE)

_add("valve_stem_type", "Valve is Sliding Stem / Type", "functional", CHOICE_TYPE,
     ["Sliding Stem", "Rotary", "Quarter Turn", "Throttle", "Snap Acting"])
_add("fail_position", "Verify Fail Position", "functional", CHOICE_TYPE,
     ["Valve Fails Open", "Valve Fails Closed", "Valve Fails Last"])
_add("command_signal_type", "Verify Positioner Command Signals", "functional", CHOICE_TYPE, ["mA", "%"])

# --------------------------------- Positioner / Valve Travel Indication ----
# NOTE: labels must be unique (the export script looks columns up by label
# text), so the ascending and descending legs of the ramp (which share the
# same percentage) are disambiguated with (up)/(down).
TRAVEL_COLUMNS = [
    ("0_up", "0% (up)"), ("25_up", "25% (up)"), ("50_up", "50% (up)"),
    ("75_up", "75% (up)"), ("100", "100%"),
    ("75_down", "75% (down)"), ("50_down", "50% (down)"),
    ("25_down", "25% (down)"), ("0_down", "0% (down)"),
]
for key, label in TRAVEL_COLUMNS:
    _add(f"valve_position_{key}", f"Valve Position @ {label}", "travel")
for key, label in TRAVEL_COLUMNS:
    _add(f"ma_input_{key}", f"mA Input @ {label}", "travel")

# ------------------------------ Calibration & Configuration Test Equipment -
_add("equip_make", "Test Equipment - Make", "equipment")
_add("equip_model", "Test Equipment - Model", "equipment")
_add("equip_serial", "Test Equipment - Serial#", "equipment")
_add("equip_caldate", "Test Equipment - Calibration Date", "equipment")

# ---------------------------------------------------------------- Comments -
_add("comments", "Comments", "comments", "multiline")

# ------------------------------------------------------------- Sign-Off ----
_add("qc_rep_name", "YANDA QC Representative - Name", "signoff")
_add("qc_date", "YANDA QC Representative - Date", "signoff")
_add("commissioning_rep_name", "YANDA Commissioning Representative - Name", "signoff")


def by_id(field_id):
    for f in FIELDS:
        if f["id"] == field_id:
            return f
    return None


def by_section(section):
    return [f for f in FIELDS if f["section"] == section]


SECTION_TITLES = {
    "header": "Header",
    "general": "General Description",
    "commissioning": "Commissioning Inspection",
    "functional": "Functional Verification Activities",
    "travel": "Positioner / Valve Travel Indication",
    "equipment": "Calibration & Configuration Test Equipment Used",
    "comments": "Comments",
    "signoff": "Sign-Off",
}

# Extra column that only exists in the Excel log (not on the PDF form).
CONTROL_FIELD = {
    "id": "export_flag",
    "label": "Export to PDF (Y/N)",
    "section": "control",
    "ftype": CHOICE_TYPE,
    "choices": ["Y", "N"],
}
LOG_COLUMNS = [CONTROL_FIELD] + FIELDS

if __name__ == "__main__":
    print(f"Total PDF fields: {len(FIELDS)}")
    from collections import Counter
    c = Counter(f["section"] for f in FIELDS)
    for sec, n in c.items():
        print(f"  {sec}: {n}")
