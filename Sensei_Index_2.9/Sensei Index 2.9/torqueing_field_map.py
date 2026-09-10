# -*- coding: utf-8 -*-
"""
Maps each torqueing_schema.py field id to the ACTUAL field name inside the
original Torqueing Report PDF (YCQE-E&I-014 Rev.0).

This original PDF, like eht_removal/eht_rtd's own originals, was a
FILLED-IN example, not a blank form - the four header cells (Customer
Name, Project Name, Contract#, Location) had real sample values baked
into their /V entries ("COOEC Canada Ltd.", "K1B Well Pad",
"CA23007-SCM-AGC-004", "K1B Well Pad"). Every one of those sat on a
genuine fillable AcroForm widget (confirmed against the PDF's own field
dictionary), so overwriting them on export is completely safe - nothing
is baked into the page as flattened content. The sample values themselves
were cleared out of the checked-in template (see
build_torqueing_template.py) so a fresh export never starts from someone
else's sample data by accident - the exact same precaution eht_rtd_field_map.py's
own docstring describes for its original PDF.

Every field name below was reverse-engineered directly from the original
PDF's AcroForm field dictionary and each widget's on-page position
(grouped into rows by /Rect y-position, columns by x-position) -
NOT invented like eht_pre_insulation's clean identity map (that form had
no original PDF at all - see that module's own docstring for why it's
different).

The bolt/termination table's row 1 uses the original author's own
human-readable field names ("NO", "TAG #", "GRADE", "SIZE",
"VALUE (FT/LB", "BY INITIAL", "BY INITIAL (1)", "yyyy/mm/dd") - rows 2-15
use generic "Text##" names. The "date" column's own Text## numbering is
NOT sequential with the other seven columns (Text123-126, then
Text132, Text140-148) - a real quirk in how the original form's author
added that column in a separate editing pass, preserved as-is; verified
directly against each widget's /Rect, not assumed from naming.
"""

FIELD_MAP = {
    "customer_name": "Text127",
    "project_name": "Text128",
    "contract_no": "Text129",
    "location": "Text130",

    "torque_record_number": "Text131",
    "system_number": "Dropdown1",
    "reference_tag_number": "Text134",
    "torque_wrench_manufacturer": "Text138",
    "torque_wrench_serial_number": "Text135",
    "calibration_date": "Text137",
    "drawing_reference_number": "Text136",

    "torque_spec_document_reference": "TORQUE SPECIFICATION DOCUMENT REFERENCE",
    "comments": "COMMENTS",

    "yanda_rep_name": "YANDA REPRESENTATIVE",
    "yanda_rep_date": "Text139",
    "client_rep_name": "CLIENT REPRESENTATIVE",
    "client_rep_date": "Text133",

    "bolt_row_1_no": "NO",
    "bolt_row_1_tag": "TAG #",
    "bolt_row_1_grade": "GRADE",
    "bolt_row_1_size": "SIZE",
    "bolt_row_1_torque_value": "VALUE (FT/LB",
    "bolt_row_1_torqued_by": "BY INITIAL",
    "bolt_row_1_witnessed_by": "BY INITIAL (1)",
    "bolt_row_1_date": "yyyy/mm/dd",
    "bolt_row_2_no": "Text10",
    "bolt_row_2_tag": "Text11",
    "bolt_row_2_grade": "Text12",
    "bolt_row_2_size": "Text13",
    "bolt_row_2_torque_value": "Text14",
    "bolt_row_2_torqued_by": "Text15",
    "bolt_row_2_witnessed_by": "Text16",
    "bolt_row_2_date": "Text123",
    "bolt_row_3_no": "Text18",
    "bolt_row_3_tag": "Text19",
    "bolt_row_3_grade": "Text20",
    "bolt_row_3_size": "Text21",
    "bolt_row_3_torque_value": "Text22",
    "bolt_row_3_torqued_by": "Text23",
    "bolt_row_3_witnessed_by": "Text24",
    "bolt_row_3_date": "Text124",
    "bolt_row_4_no": "Text26",
    "bolt_row_4_tag": "Text27",
    "bolt_row_4_grade": "Text28",
    "bolt_row_4_size": "Text29",
    "bolt_row_4_torque_value": "Text30",
    "bolt_row_4_torqued_by": "Text31",
    "bolt_row_4_witnessed_by": "Text32",
    "bolt_row_4_date": "Text125",
    "bolt_row_5_no": "Text34",
    "bolt_row_5_tag": "Text35",
    "bolt_row_5_grade": "Text36",
    "bolt_row_5_size": "Text37",
    "bolt_row_5_torque_value": "Text38",
    "bolt_row_5_torqued_by": "Text39",
    "bolt_row_5_witnessed_by": "Text40",
    "bolt_row_5_date": "Text126",
    "bolt_row_6_no": "Text42",
    "bolt_row_6_tag": "Text43",
    "bolt_row_6_grade": "Text44",
    "bolt_row_6_size": "Text45",
    "bolt_row_6_torque_value": "Text46",
    "bolt_row_6_torqued_by": "Text47",
    "bolt_row_6_witnessed_by": "Text48",
    "bolt_row_6_date": "Text132",
    "bolt_row_7_no": "Text50",
    "bolt_row_7_tag": "Text51",
    "bolt_row_7_grade": "Text52",
    "bolt_row_7_size": "Text53",
    "bolt_row_7_torque_value": "Text54",
    "bolt_row_7_torqued_by": "Text55",
    "bolt_row_7_witnessed_by": "Text56",
    "bolt_row_7_date": "Text140",
    "bolt_row_8_no": "Text58",
    "bolt_row_8_tag": "Text59",
    "bolt_row_8_grade": "Text60",
    "bolt_row_8_size": "Text61",
    "bolt_row_8_torque_value": "Text62",
    "bolt_row_8_torqued_by": "Text63",
    "bolt_row_8_witnessed_by": "Text64",
    "bolt_row_8_date": "Text141",
    "bolt_row_9_no": "Text66",
    "bolt_row_9_tag": "Text67",
    "bolt_row_9_grade": "Text68",
    "bolt_row_9_size": "Text69",
    "bolt_row_9_torque_value": "Text70",
    "bolt_row_9_torqued_by": "Text71",
    "bolt_row_9_witnessed_by": "Text72",
    "bolt_row_9_date": "Text142",
    "bolt_row_10_no": "Text74",
    "bolt_row_10_tag": "Text75",
    "bolt_row_10_grade": "Text76",
    "bolt_row_10_size": "Text77",
    "bolt_row_10_torque_value": "Text78",
    "bolt_row_10_torqued_by": "Text79",
    "bolt_row_10_witnessed_by": "Text80",
    "bolt_row_10_date": "Text143",
    "bolt_row_11_no": "Text82",
    "bolt_row_11_tag": "Text83",
    "bolt_row_11_grade": "Text84",
    "bolt_row_11_size": "Text85",
    "bolt_row_11_torque_value": "Text86",
    "bolt_row_11_torqued_by": "Text87",
    "bolt_row_11_witnessed_by": "Text88",
    "bolt_row_11_date": "Text144",
    "bolt_row_12_no": "Text90",
    "bolt_row_12_tag": "Text91",
    "bolt_row_12_grade": "Text92",
    "bolt_row_12_size": "Text93",
    "bolt_row_12_torque_value": "Text94",
    "bolt_row_12_torqued_by": "Text95",
    "bolt_row_12_witnessed_by": "Text96",
    "bolt_row_12_date": "Text145",
    "bolt_row_13_no": "Text98",
    "bolt_row_13_tag": "Text99",
    "bolt_row_13_grade": "Text100",
    "bolt_row_13_size": "Text101",
    "bolt_row_13_torque_value": "Text102",
    "bolt_row_13_torqued_by": "Text103",
    "bolt_row_13_witnessed_by": "Text104",
    "bolt_row_13_date": "Text146",
    "bolt_row_14_no": "Text106",
    "bolt_row_14_tag": "Text107",
    "bolt_row_14_grade": "Text108",
    "bolt_row_14_size": "Text109",
    "bolt_row_14_torque_value": "Text110",
    "bolt_row_14_torqued_by": "Text111",
    "bolt_row_14_witnessed_by": "Text112",
    "bolt_row_14_date": "Text147",
    "bolt_row_15_no": "Text114",
    "bolt_row_15_tag": "Text115",
    "bolt_row_15_grade": "Text116",
    "bolt_row_15_size": "Text117",
    "bolt_row_15_torque_value": "Text118",
    "bolt_row_15_torqued_by": "Text119",
    "bolt_row_15_witnessed_by": "Text120",
    "bolt_row_15_date": "Text148",
}

# The "N/A" checkbox next to the Comments banner - a real /Btn widget with
# a field-specific on-state (confirmed against the PDF's own /_States_:
# ["/N/A", "/Off"] - "/Yes" is not a valid appearance state for it).
COMMENTS_NA_CHECKBOX = {"field": "N/A", "on": "/N/A"}
CHECKBOX_OFF = "/Off"

# Nothing else on this form is a checkbox/choice widget besides the System
# No. dropdown (a real /Ch field, handled like any other text-ish value -
# Dropdown1's own /Opt list is reproduced as SYSTEM_NUMBER_CHOICES in
# torqueing_schema.py) and the N/A button above.
YES_NO_CHECKBOXES = {}
CHECKBOX_ON = "/Yes"

# Neither representative has a real Signature field on the original PDF
# (hand-signed only there). The user asked for a Yanda signature stamp
# "as the instrumentation dashboard has it" - export_torqueing_to_pdf.py
# adds that separately, as a reportlab image overlay merged onto the page
# at export time (see that module's stamp_signature()), same mechanism
# export_to_pdf.py/export_valve_to_pdf.py already use for their own Yanda
# QA Representative stamp - it is NOT a FIELD_MAP entry because it isn't
# a fillable field at all.
UNMAPPED_NOTE = (
    "Neither representative's Signature cell has a digital field on the "
    "original PDF. Yanda's own signature is stamped automatically at "
    "export time (see export_torqueing_to_pdf.py's stamp_signature()); "
    "Client Representative's signature is hand-signed only."
)
