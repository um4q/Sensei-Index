# -*- coding: utf-8 -*-
"""
Maps each schema.py field id to the ACTUAL field name(s) inside the user's
original PDF (29103-PIT-1014_-_ITR.pdf / Transmitter_Inspection_Test_Record_TEMPLATE.pdf).

Verified directly against the original file's AcroForm field dictionary and
its sample values - not guessed from the visual layout.

A value of None means that item has no real, digitally-fillable field on the
original PDF (the paper/PDF form only has a printed checkbox glyph or blank
line there, meant to be marked by hand or with a Bluebeam markup tool) - the
Excel log still records it, but export_to_pdf.py can't push it onto the PDF.
"""

# ------------------------------------------------------- simple 1-to-1 map
FIELD_MAP = {
    "customer_ref": None,  # no fillable field on the original for this
    "project": "Text1",
    "location": "Text2",
    "contract_no": "Text3",
    "tag": "Text4",
    "transmitter_type": "Text5",
    "system_number": "Text6",
    "service": "Text7",
    "pid_number": "Text8",
    "line_number": "Text9",
    "make": "Text10",
    "model": "Text11",
    "serial_number": "Text12",
    "calibration_range": "Text13",
    "instrument_range": "Text14",
    "repeatability": "Text15",
    "local_display": "Text16",
    "signal_type": "Text17",
    "k_factor": "Text18",
    "scale_factor": "Text19",

    "vi_1": "Dropdown1", "vi_2": "Dropdown2", "vi_3": "Dropdown3", "vi_4": "Dropdown4",
    "vi_5": "Dropdown5", "vi_6": "Dropdown6", "vi_7": "Dropdown7", "vi_8": "Dropdown8",
    "vi_9": "Dropdown9", "vi_10": "Dropdown10", "vi_11": "Dropdown11", "vi_12": "Dropdown12",

    "proc_1_vdc": "Text20",
    # proc_2 .. proc_14 are each three independent checkboxes (Pass/Fail/N/A) -
    # handled specially via PROC_CHECKBOXES below, verified directly against
    # a fully-checked sample (test123.pdf) field-by-field.

    "te1_make": "Make", "te1_model": "Model", "te1_serial": "Serial", "te1_caldate": "Calibration Date",
    "te2_make": "Make (1)", "te2_model": "Model (1)", "te2_serial": "Serial (1)",
    "te2_caldate": "Calibration Date (1)",
    "te3_make": "Text66", "te3_model": "Text67", "te3_serial": "Text68", "te3_caldate": "Text69",

    "tr_0_input_up": "Upscale", "tr_0_input_down": "Downscale",
    "tr_0_output_up": "Upscale (1)", "tr_0_output_down": "Downscale (1)",
    "tr_0_localdisplay_up": "Upscale (2)", "tr_0_localdisplay_down": "Downscale (2)",
    "tr_0_dcs_up": "Upscale (3)", "tr_0_dcs_down": "Downscale (3)",

    "tr_25_input_up": "Upscale (4)", "tr_25_input_down": "Downscale (4)",
    "tr_25_output_up": "Upscale (5)", "tr_25_output_down": "Downscale (5)",
    "tr_25_localdisplay_up": "Upscale (6)", "tr_25_localdisplay_down": "Downscale (6)",
    "tr_25_dcs_up": "Upscale (7)", "tr_25_dcs_down": "Downscale (7)",

    "tr_50_input_up": "Text87", "tr_50_input_down": "Text88",
    "tr_50_output_up": "Text89", "tr_50_output_down": "Text90",
    "tr_50_localdisplay_up": "Text91", "tr_50_localdisplay_down": "Text92",
    "tr_50_dcs_up": "Text93", "tr_50_dcs_down": "Text94",

    "tr_75_input_up": "Text95", "tr_75_input_down": "Text96",
    "tr_75_output_up": "Text97", "tr_75_output_down": "Text98",
    "tr_75_localdisplay_up": "Text99", "tr_75_localdisplay_down": "Text100",
    "tr_75_dcs_up": "Text101", "tr_75_dcs_down": "Text102",

    "tr_100_input_up": "Text103", "tr_100_input_down": "Text104",
    "tr_100_output_up": "Text105", "tr_100_output_down": "Text106",
    "tr_100_localdisplay_up": "Text107", "tr_100_localdisplay_down": "Text108",
    "tr_100_dcs_up": "Text109", "tr_100_dcs_down": "Text110",

    "system_results": None,  # no fillable field on the original for this

    # remarks is handled specially - split across 7 single-line fields, see REMARKS_LINE_FIELDS.

    "yanda_qa_name": "Name",
    "yanda_qa_date": "Date",
    "yanda_qa_signature": None,   # hand-signed / Bluebeam signature on the original
    "client_name": "Name (1)",
    "client_date": "Date (1)",
    "client_signature": None,     # hand-signed / Bluebeam signature on the original
}

# Every Part 4 procedure item (2 through 14) is three independent checkboxes
# on the PDF, left-to-right = Pass, Fail, N/A. Verified field-by-field against
# a fully-filled sample (test123.pdf) - every row below was cross-checked
# against that file's actual /V values.
PROC_CHECKBOXES = {
    "proc_2": {"Pass": "Check Box1", "Fail": "Check Box4", "N/A": "Check Box5"},
    "proc_3": {"Pass": "Check Box6", "Fail": "Check Box18", "N/A": "Check Box19"},
    "proc_4": {"Pass": "Check Box7", "Fail": "Check Box20", "N/A": "Check Box21"},
    "proc_5": {"Pass": "Check Box8", "Fail": "Check Box22", "N/A": "Check Box23"},
    "proc_6": {"Pass": "Check Box9", "Fail": "Check Box25", "N/A": "Check Box24"},
    "proc_7": {"Pass": "Check Box10", "Fail": "Check Box26", "N/A": "Check Box27"},
    "proc_8": {"Pass": "Check Box11", "Fail": "Check Box28", "N/A": "Check Box29"},
    "proc_9": {"Pass": "Check Box12", "Fail": "Check Box31", "N/A": "Check Box30"},
    "proc_10": {"Pass": "Check Box13", "Fail": "Check Box32", "N/A": "Check Box33"},
    "proc_11": {"Pass": "Check Box14", "Fail": "Check Box34", "N/A": "Check Box35"},
    "proc_12": {"Pass": "Check Box15", "Fail": "Check Box36", "N/A": "Check Box37"},
    "proc_13": {"Pass": "Check Box16", "Fail": "Check Box38", "N/A": "Check Box39"},
    "proc_14": {"Pass": "Check Box17", "Fail": "Check Box40", "N/A": "Check Box41"},
}
CHECKBOX_ON = "/Yes"
CHECKBOX_OFF = "/Off"

# PART 7 - Remarks is 7 separate single-line fields on the original PDF, not
# one multiline box. A log entry's remarks text is split on newlines (or
# wrapped) across these, top to bottom.
REMARKS_LINE_FIELDS = [
    "PART 7 \u2013 Remarks",
    "PART 7 \u2013 Remarks (1)",
    "Text113",
    "Text114",
    "Text115",
    "Text116",
    "Text117",
]

# Fields on the original PDF with no real digital field behind them - shown
# to the user once as a heads-up, not a per-row warning.
UNMAPPED_FIELD_LABELS = [
    "Customer Ref#",
    "System Results",
    "Yanda QA Representative - Signature",
    "Client Representative - Signature",
]
