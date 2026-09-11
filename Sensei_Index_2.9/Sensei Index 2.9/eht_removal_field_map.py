# -*- coding: utf-8 -*-
"""
Maps each eht_removal_schema.py field id to the ACTUAL field name(s) inside
the original EHT Removal and Reinstatement Report PDF (YCQE-EHT-019 Rev.0).
Verified directly against the PDF's AcroForm field dictionary and positions -
not guessed from the visual layout.
"""

# ------------------------------------------------------- simple 1-to-1 map
FIELD_MAP = {
    "customer_name": None,  # static print text on this template, no fillable field
    "project_name": None,   # static print text on this template, no fillable field
    "contract_no": None,    # static print text on this template, no fillable field
    "location": "Text148",

    "trace_tag": "Text1",
    "area": "Text2",
    "system_no": "Text3",
    "eht_length": "Text136",
    "ehtc_no": "Text4",
    "panel_no": "Text5",
    "breaker_no": "Text6",
    "eht_iso_drawing_no": "Text7",

    "comments": "Text131",

    "yanda_rep_name": "Text132",
    "yanda_rep_date": "Text134",
    "yanda_rep_signature": None,   # hand-signed, no digital field
    "client_rep_name": "Text133",
    "client_rep_date": "Text135",
    "client_rep_signature": None,  # hand-signed, no digital field
}

# ---------------------------------------------------------- checkbox groups
# Each of these schema fields is a single-choice value that maps to ONE of
# several independent checkboxes (set that one /Yes, leave the rest /Off).
CHECKBOX_GROUPS = {
    "alarm": {"Yes": "Check Box3", "No": "Check Box4"},
    "eht_type": {"SR": "Check Box1", "MI": "Check Box2"},
    "test1_voltage": {"500 VDC": "Check Box7", "1000 VDC": "Check Box8"},
    "test2_voltage": {"500 VDC": "Check Box9", "1000 VDC": "Check Box10"},
    "test3_voltage": {"500 VDC": "Check Box11", "1000 VDC": "Check Box12"},
    "test4_voltage": {"500 VDC": "Check Box13", "1000 VDC": "Check Box14"},
    "test5_voltage": {"500 VDC": "Check Box15", "1000 VDC": "Check Box16"},
}

# ------------------------------------------ simple Yes/No confirm checkboxes
# The 3 section-level "N/A" flags and the Comments/Delays "N/A" flag - each
# is a single lone checkbox (checked = Y, left /Off for N or blank).
YES_NO_CHECKBOXES = {
    "full_removal_na": "Check Box5",
    "partial_removal_na": "Check Box6",
    "comments_na": "Check Box17",
}

CHECKBOX_ON = "/Yes"
CHECKBOX_OFF = "/Off"

# ---------------------------------------- 46-item checklist Yes/N-A columns
# Every checklist item on this form is TWO independent text boxes (someone's
# initials go in one or the other) - same "<item>_yes"/"<item>_na" split
# valve_field_map.py's own fv_1..fv_8 entries now use too. Kept as a plain
# id -> pdf field name map, same shape as FIELD_MAP, just kept separate for
# clarity since there are 92 of them.
CHECKLIST_FIELD_MAP = {
    # Full EHT Removal (11 items)
    "full_removal_item_1_yes": "Text8", "full_removal_item_1_na": "Text9",
    "full_removal_item_2_yes": "Text10", "full_removal_item_2_na": "Text11",
    "full_removal_item_3_yes": "Text12", "full_removal_item_3_na": "Text13",
    "full_removal_item_4_yes": "Text14", "full_removal_item_4_na": "Text15",
    "full_removal_item_5_yes": "Text16", "full_removal_item_5_na": "Text17",
    "full_removal_item_6_yes": "Text18", "full_removal_item_6_na": "Text19",
    "full_removal_item_7_yes": "Text20", "full_removal_item_7_na": "Text21",
    "full_removal_item_8_yes": "Text22", "full_removal_item_8_na": "Text23",
    "full_removal_item_9_yes": "Text24", "full_removal_item_9_na": "Text25",
    "full_removal_item_10_yes": "Text26", "full_removal_item_10_na": "Text27",
    "full_removal_item_11_yes": "Text28", "full_removal_item_11_na": "Text29",

    # Partial EHT Removal (9 items)
    "partial_removal_item_1_yes": "Text30", "partial_removal_item_1_na": "Text31",
    "partial_removal_item_2_yes": "Text32", "partial_removal_item_2_na": "Text33",
    "partial_removal_item_3_yes": "Text34", "partial_removal_item_3_na": "Text35",
    "partial_removal_item_4_yes": "Text36", "partial_removal_item_4_na": "Text37",
    "partial_removal_item_5_yes": "Text38", "partial_removal_item_5_na": "Text39",
    "partial_removal_item_6_yes": "Text40", "partial_removal_item_6_na": "Text41",
    "partial_removal_item_7_yes": "Text42", "partial_removal_item_7_na": "Text43",
    "partial_removal_item_8_yes": "Text44", "partial_removal_item_8_na": "Text45",
    "partial_removal_item_9_yes": "Text46", "partial_removal_item_9_na": "Text47",

    # Re-Installation (15 items)
    "reinstall_item_1_yes": "Text48", "reinstall_item_1_na": "Text49",
    "reinstall_item_2_yes": "Text50", "reinstall_item_2_na": "Text51",
    "reinstall_item_3_yes": "Text52", "reinstall_item_3_na": "Text53",
    "reinstall_item_4_yes": "Text54", "reinstall_item_4_na": "Text55",
    "reinstall_item_5_yes": "Text56", "reinstall_item_5_na": "Text57",
    "reinstall_item_6_yes": "Text58", "reinstall_item_6_na": "Text59",
    "reinstall_item_7_yes": "Text61", "reinstall_item_7_na": "Text62",
    "reinstall_item_8_yes": "Text63", "reinstall_item_8_na": "Text64",
    "reinstall_item_9_yes": "Text65", "reinstall_item_9_na": "Text66",
    "reinstall_item_10_yes": "Text67", "reinstall_item_10_na": "Text68",
    "reinstall_item_11_yes": "Text69", "reinstall_item_11_na": "Text70",
    "reinstall_item_12_yes": "Text71", "reinstall_item_12_na": "Text72",
    "reinstall_item_13_yes": "Text73", "reinstall_item_13_na": "Text74",
    "reinstall_item_14_yes": "Text75", "reinstall_item_14_na": "Text76",
    "reinstall_item_15_yes": "Text77", "reinstall_item_15_na": "Text78",

    # QA/QC Final Walk Down (11 items)
    "walkdown_item_1_yes": "Text79", "walkdown_item_1_na": "Text80",
    "walkdown_item_2_yes": "Text81", "walkdown_item_2_na": "Text82",
    "walkdown_item_3_yes": "Text83", "walkdown_item_3_na": "Text84",
    "walkdown_item_4_yes": "Text85", "walkdown_item_4_na": "Text86",
    "walkdown_item_5_yes": "Text87", "walkdown_item_5_na": "Text88",
    "walkdown_item_6_yes": "Text89", "walkdown_item_6_na": "Text90",
    "walkdown_item_7_yes": "Text91", "walkdown_item_7_na": "Text92",
    "walkdown_item_8_yes": "Text93", "walkdown_item_8_na": "Text94",
    "walkdown_item_9_yes": "Text95", "walkdown_item_9_na": "Text96",
    "walkdown_item_10_yes": "Text97", "walkdown_item_10_na": "Text98",
    "walkdown_item_11_yes": "Text99", "walkdown_item_11_na": "Text100",
}
FIELD_MAP.update(CHECKLIST_FIELD_MAP)

# ------------------------------------------------------ Testing Activities
TESTING_FIELD_MAP = {
    "test1_date": "Text101", "test2_date": "Text102", "test3_date": "Text103",
    "test4_date": "Text104", "test5_date": "Text105",

    "test1_ir_value": "Text106", "test2_ir_value": "Text107", "test3_ir_value": "Text108",
    "test4_ir_value": "Text109", "test5_ir_value": "Text110",

    "test1_test_equip": "Text111", "test2_test_equip": "Text112", "test3_test_equip": "Text113",
    "test4_test_equip": "Text114", "test5_test_equip": "Text115",

    "test1_amb_temp": "Text116", "test2_amb_temp": "Text117", "test3_amb_temp": "Text118",
    "test4_amb_temp": "Text119", "test5_amb_temp": "Text120",

    "test1_continuity": "Text121", "test2_continuity": "Text122", "test3_continuity": "Text123",
    "test4_continuity": "Text124", "test5_continuity": "Text125",

    "test1_tested_by": "Text126", "test2_tested_by": "Text127", "test3_tested_by": "Text128",
    "test4_tested_by": "Text129", "test5_tested_by": "Text130",
}
FIELD_MAP.update(TESTING_FIELD_MAP)

# Fields on the PDF with no real digital field behind them: the Customer
# Name / Project Name / Contract # header (static print text, pre-branded
# to this one client engagement, same as the boilerplate on this form's
# other pages), and both representatives' Signature lines (hand-signed
# only) - see the None entries in FIELD_MAP above.
UNMAPPED_NOTE = (
    "Customer Name, Project Name, and Contract # are static print text on "
    "this template (no digital field exists for them). Both Yanda and "
    "Client Representative Signature lines have no digital field either - "
    "hand-sign those after exporting."
)
