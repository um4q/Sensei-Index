# -*- coding: utf-8 -*-
"""
Maps each valve_schema.py field id to the ACTUAL field name(s) inside the
original Pneumatically Actuated Valve Check Record PDF (Form# YCQP-E&I-204).
Verified directly against the PDF's AcroForm field dictionary and positions.
"""

# ------------------------------------------------------- simple 1-to-1 map
FIELD_MAP = {
    "customer_name": "Text53",
    "project_name": "Text54",
    "contract_no": "Text55",
    "location": "Text56",

    "system": "Text4",
    "pid_number": "Text7",
    "line_number": "Text5",
    "equip_number": "Text8",
    "unit_number": "Text6",
    "valve_type_other": "Text60",

    "actuator_serial": "Text9",
    "actuator_model": "Text10",
    "trim_plug": "Text19",
    "trim_seat": "Text20",

    "valve_serial": "Text11",
    "valve_model": "Text12",
    "travel_value": None,  # handled specially - goes into Text59 or Text58 depending on travel_unit

    "positioner_serial": "Text13",
    "positioner_model": "Text14",

    "position_limit_serial": "Text15",
    "position_limit_model": "Text16",
    "ansi_size": "Text57",

    "solenoid_serial": "Text17",
    "solenoid_model": "Text18",
    "crn_number": "Text21",

    "commissioning_tag": "Text25",
    "voltage": "Text24",
    "fuse_rating": "Text23",
    "inst_air_pressure": "Text22",

    "equip_make": "Text44",
    "equip_model": "Text45",
    "equip_serial": "Text46",
    "equip_caldate": "Text47",

    "qc_rep_name": "Text51",
    "qc_date": "QCRepDate",
    "commissioning_rep_name": "Text52",
}

# ---------------------------------------------------------- checkbox groups
# Each of these schema fields is a single-choice value that maps to ONE of
# several independent checkboxes (set that one /Yes, leave the rest /Off).
CHECKBOX_GROUPS = {
    "valve_type": {"ESDV": "Check Box1", "FCV": "Check Box2", "LCV": "Check Box3", "PCV": "Check Box4"},
    "valve_class": {
        "I": "Check Box11", "II": "Check Box12", "III": "Check Box13",
        "IV": "Check Box14", "V": "Check Box15", "VI": "Check Box16",
    },
    "ansi_rating": {
        "150": "Check Box8", "300": "Check Box10", "600": "Check Box9", "900": "Check Box7",
        "1200": "Check Box53", "1500": "Check Box54", "2500": "Check Box55",
    },
    "body_style": {"Flanged": "Check Box17", "Threaded": "Check Box18"},
    "signal_type": {
        "4-20 mA / HART": "Check Box23", "Fieldbus": "Check Box22", "Wireless": "Check Box21",
        "Modbus": "Check Box20", "Pneumatic": "Check Box19",
    },
    "installed_by": {"IESL": "Check Box32", "Other": "Check Box33"},
    "verified_by": {"IESL": "Check Box37", "Other": "Check Box38"},
    "valve_stem_type": {
        "Sliding Stem": "Check Box52", "Rotary": "Check Box48", "Quarter Turn": "Check Box47",
        "Throttle": "Check Box45", "Snap Acting": "Check Box43",
    },
    "fail_position": {
        "Valve Fails Open": "Check Box49", "Valve Fails Closed": "Check Box46", "Valve Fails Last": "Check Box44",
    },
    "command_signal_type": {"mA": "Check Box50", "%": "Check Box51"},
}

# Travel unit (Inch/Metric) is a checkbox choice PLUS its own value goes into
# a matching text field.
TRAVEL_UNIT_CHECKBOXES = {"Inch": "Check Box5", "Metric": "Check Box6"}
TRAVEL_UNIT_VALUE_FIELDS = {"Inch": "Text59", "Metric": "Text58"}

# ------------------------------------------ simple Yes/No confirm checkboxes
# Each of these schema fields is Y/N and maps straight to one checkbox
# (checked for Y, left /Off for N or blank).
YES_NO_CHECKBOXES = {
    "bad_io": "Check Box26",
    "verify_device_screen_match": "Check Box24",
    "ss_device_tag": "Check Box34",
    "ss_cable_tag": "Check Box39",
    "calibration_tag": "Check Box27",
    "wire_tagged": "Check Box25",
    "cable_fittings_inspected": "Check Box35",
    "adequate_service_loop": "Check Box40",
    "polarity_correct_wire_tug": "Check Box28",
    "heat_traced": "Check Box30",
    "insulated": "Check Box31",
    "tubing_fittings_inspected": "Check Box36",
    "conforms_to_install": "Check Box41",
    "conforms_to_pid": "Check Box29",
    "asme_code": "Check Box42",
}

CHECKBOX_ON = "/Yes"
CHECKBOX_OFF = "/Off"

# ------------------------------------- Functional Verification Yes/NA pairs
# Each item has a Yes-initials widget and a separate NA-initials widget.
# If the log value is "N/A" (any case), it goes in the NA widget; any other
# non-empty text (initials) goes in the Yes widget.
FV_YES_NA_FIELDS = {
    "fv_1": {"yes": "Dropdown1", "na": "Dropdown3"},
    "fv_2": {"yes": "Dropdown2", "na": "Dropdown4"},
    "fv_3": {"yes": "Dropdown5", "na": "Dropdown6"},
    "fv_4": {"yes": "Dropdown10", "na": "Dropdown7"},
    "fv_5": {"yes": "Dropdown11", "na": "Dropdown8"},
    "fv_6": {"yes": "Dropdown12", "na": "Dropdown9"},
    "fv_7": {"yes": "Dropdown15", "na": "Dropdown13"},
    "fv_8": {"yes": "Dropdown16", "na": "Dropdown14"},
}

# ------------------------------------------------- Travel Indication table
TRAVEL_FIELD_MAP = {
    "valve_position_0_up": "Text26", "valve_position_25_up": "Text28", "valve_position_50_up": "Text30",
    "valve_position_75_up": "Text31", "valve_position_100": "Text34",
    "valve_position_75_down": "Text36", "valve_position_50_down": "Text38",
    "valve_position_25_down": "Text40", "valve_position_0_down": "Text42",

    "ma_input_0_up": "Text27", "ma_input_25_up": "Text29", "ma_input_50_up": "Text33",
    "ma_input_75_up": "Text32", "ma_input_100": "Text35",
    "ma_input_75_down": "Text37", "ma_input_50_down": "Text39",
    "ma_input_25_down": "Text41", "ma_input_0_down": "Text43",
}
FIELD_MAP.update(TRAVEL_FIELD_MAP)

# ------------------------------------------------------------- Comments ----
COMMENTS_LINE_FIELDS = ["Text48", "Text49", "Text50"]

# Fields on the PDF with no real digital field behind them - hand-written /
# hand-signed only: Pre-Commissioning Signature/Date, Commissioning
# Signature/Date, and the Signature lines under both Sign-Off blocks. The
# YANDA QC Representative Sign-Off block's own Date line USED to be in this
# category too - a "QCRepDate" text field was added to the PDF template
# (see /assets or the template file itself) specifically so qc_date could
# be a real, trackable field the same way transmitters' sign-off dates
# always have been, instead of a canvas-drawn stamp.
UNMAPPED_NOTE = (
    "Pre-Commissioning Signature/Date, Commissioning Signature/Date, and the "
    "Signature lines under both Sign-Off blocks have no digital fields on "
    "the original PDF - hand-sign/date those after exporting. The YANDA QC "
    "Representative Sign-Off block's Date line is the one exception - it's "
    "a real field (qc_date) now."
)
