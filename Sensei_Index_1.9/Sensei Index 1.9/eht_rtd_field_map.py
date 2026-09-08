# -*- coding: utf-8 -*-
"""
Maps each eht_rtd_schema.py field id to the ACTUAL field name(s) inside the
original EHT & RTD Installation Inspection Report PDF (YCQE-E&I-004 Rev.0).
Verified directly against the PDF's AcroForm field dictionary and positions.

This particular original PDF (the one used to build this map and the
template PDF next to it) happened to be a FILLED-IN example, not a blank
form - every value referenced below (a customer name, a signer's name, a
date, a megger reading, ...) sat on a genuine fillable AcroForm widget, so
overwriting it on export is completely safe; nothing is baked into the page
as flattened content. The sample values themselves were cleared out of the
checked-in template (see build_eht_rtd_template.py) so a fresh export
never starts from someone else's old inspection data by accident.
"""

# ------------------------------------------------------- simple 1-to-1 map
FIELD_MAP = {
    "customer_name": "Text30",
    "project_name": "Text31",
    "contract_no": "Text32",
    "location": "Text33",

    "trace_number": "Text1",
    "controller_number": "Controller #",
    "trace_part_number": "Text3",
    "panel_number": "Panel #",
    "rtds_number": "Text5",
    "circuit_number": "Circuit #",
    "zone_drawing_number": "Text7",
    "rev": "REV",

    "pre_ins_item_1_1_result": "Y/N/NA",
    "pre_ins_item_1_1_comments": "Comments",
    "pre_ins_item_1_2_result": "Y/N/NA (1)",
    "pre_ins_item_1_2_comments": "Text13",
    "pre_ins_item_1_3_result": "ATC (2)",
    "pre_ins_r1_ohms": "Text34",
    "pre_ins_r2_ohms": "Text35",
    "pre_ins_item_1_4_result": "Text15",
    "pre_ins_item_1_4_comments": "Ω",
    "pre_ins_item_1_5_result": "E.H.T. is routed and installed as per standards and details",
    "pre_ins_item_1_5_comments": "Text18",
    "pre_ins_item_1_6_result": "Text19",
    "pre_ins_item_1_6_comments": "Text20",
    "pre_ins_item_1_7_result": "Text21",
    "pre_ins_item_1_7_comments": "Text22",
    "pre_ins_item_1_8_result": "MI",
    "pre_ins_mi_ohms": "Text36",
    "pre_ins_megger_reading_500": "Text38",
    "pre_ins_megger_reading_1000": "Text39",
    "pre_ins_megger_reading_2500": "Text40",

    "yanda_rep_pre_ins_print": "Text41",
    "yanda_rep_pre_ins_date": "Text42",
    "client_rep_pre_ins_print": "Text45",
    "client_rep_pre_ins_date": "Text46",

    "post_ins_item_2_1_result": "Text53",
    "post_ins_item_2_1_comments": "Text54",
    "post_ins_item_2_2_result": "Text52",
    "post_ins_item_2_2_comments": "Text56",
    "post_ins_item_2_3_result": "Text51",
    "post_ins_item_2_3_comments": "Text55",
    "post_ins_item_2_4_result": "Text50",
    "post_ins_r1_ohms": "Text57",
    "post_ins_r2_ohms": "Text58",
    "post_ins_mi_ohms": "Text59",
    "post_ins_megger_reading_500": "Text47",
    "post_ins_test_equip_log": "Test Equipment Log # (1)",
    "post_ins_megger_reading_1000": "Text48",
    "post_ins_calibration_due_date": "Text26",
    "post_ins_megger_reading_2500": "Text49",

    "comments": "COMMENTS",  # first of 3 stacked lines - see COMMENTS_LINE_FIELDS

    "final_signoff_performer_name": "Text60",
    "final_signoff_performer_date": "Text62",
    "final_signoff_yanda_name": "Text63",
    "final_signoff_yanda_date": "Text65",
    "final_signoff_client_name": "Text66",
    "final_signoff_client_date": "Text68",
}

# ------------------------------------------ simple Yes/No confirm checkboxes
# Every checkbox on this form uses the standard /Yes on-state EXCEPT the two
# ATC ones (see ATC_CHECKBOXES below, which have their own field-specific
# on-states).
YES_NO_CHECKBOXES = {
    "pre_ins_megger_mi_500": "Check Box4",
    "pre_ins_megger_sr_500": "Check Box5",
    "pre_ins_megger_mi_1000": "Check Box6",
    "pre_ins_megger_sr_1000": "Check Box7",
    "pre_ins_megger_mi_2500": "Check Box8",
    "pre_ins_megger_sr_2500": "Check Box9",

    "post_ins_megger_mi_500": "Check Box10",
    "post_ins_megger_sr_500": "Check Box13",
    "post_ins_megger_mi_1000": "Check Box11",
    "post_ins_megger_sr_1000": "Check Box14",
    "post_ins_megger_mi_2500": "Check Box12",
    "post_ins_megger_sr_2500": "Check Box15",
}
CHECKBOX_ON = "/Yes"
CHECKBOX_OFF = "/Off"

# The two ATC checkboxes are the only ones on this PDF that don't use the
# standard /Yes on-state - each has its own field-specific on-state
# (confirmed against the PDF's own /AP /N dictionary: "ATC" only has states
# ["/ATC","/Off"], "ATC (1)" only has ["/ATC (1)","/Off"] - "/Yes" is not a
# valid appearance state for either, so writing it would leave the box
# looking unchecked in most viewers even though /V was technically set).
ATC_CHECKBOXES = {
    "pre_ins_atc": {"field": "ATC", "on": "/ATC"},
    "post_ins_atc": {"field": "ATC (1)", "on": "/ATC (1)"},
}

# pre_ins_test_equip_log has TWO widgets on the real PDF for the one value
# (a narrow icon-adjacent box plus a wider underline beneath it, both
# independently turned into fields by the original form's own authoring -
# post-insulation's mirror field has only the one) - write the same value
# to both so it's never ambiguous which one actually shows it.
PRE_INS_TEST_EQUIP_LOG_FIELDS = ["", "Text37"]

# ------------------------------------------------------------- Comments ----
COMMENTS_LINE_FIELDS = ["COMMENTS", "Text28", "Text29"]

# Two widgets on the real PDF are unused authoring artifacts, not real data
# - deliberately never written to by build_values_for_row(), and excluded
# from eht_rtd_schema.py entirely:
#   "Check Box1"                       - sits exactly on top of the small
#                                         square inside the "O" of the COOEC
#                                         logo; purely decorative overlap.
#   "1.0 PRE-INSULATION INSPECTION"    - an empty, unlabeled box in blank
#                                         space between the section's gray
#                                         header bar and the Results/
#                                         Comments column-header row.
ARTIFACT_FIELDS = ["Check Box1", "1.0 PRE-INSULATION INSPECTION"]

# Both pre-insulation reps' "Sign:" line, and all three rows of the final
# sign-off table's SIGNATURE column, are hand-signed only - no digital
# field exists for any of them.
UNMAPPED_NOTE = (
    "Both pre-insulation representatives' Sign: line, and every row of the "
    "final sign-off table's SIGNATURE column, have no digital field on the "
    "original PDF - hand-sign those after exporting."
)
