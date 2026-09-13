# -*- coding: utf-8 -*-
"""
Maps each general_equip_install_schema.py field id to the ACTUAL AcroForm
field name inside
General_Electrical_Equipment_Installation_and_Test_Report_TEMPLATE.pdf.

REVISION 2: this form's template is now built directly from the user's
own real, official source document (a Word .docx converted to PDF via
LibreOffice) - see general_equip_install_field_positions.py's and
build_general_equip_install_template.py's own docstrings for the full
rebuild methodology. Field names on the built template are chosen to be
exactly the schema's own ids - so this is a clean identity mapping, not
a lookup table of legacy "Text##"-style widget names. Kept as a genuine
dict anyway (rather than reading schema ids directly as PDF field names)
so this form follows the same trio shape as every other Electrical form.

No checkbox fields on this template - every cell, including the section
N/A flags and the Torqueing Log's own "Torque Marked" column, is a plain
text field (same "plain text, not a real checkbox" choice every other
from-scratch form here makes).

yanda_rep_signature's own typed value is what
export_general_equip_install_to_pdf.py's fill_pdf() actually fills by
default though: the same automatic Yanda QA Representative signature-
image stamp Torqueing/eht_pre_insulation/transformer_test have is
overlaid on this exact cell (on page 1 of this form's real 2-page
source - see field_positions.py's own docstring), and that field's
typed value (if any) is skipped whenever the stamp is applied so the two
never render on top of each other. client_rep_signature is untouched by
any of this - still a plain typed field.
"""

FIELD_MAP = {
    "location": "location",
    "tag_number": "tag_number",
    "manufacturer": "manufacturer",
    "model_number": "model_number",
    "system_number": "system_number",
    "serial_number": "serial_number",
    "voltage": "voltage",
    "freq": "freq",
    "phase": "phase",
    "amps": "amps",
    "area_class_of_equip": "area_class_of_equip",
    "ref_dwg_number": "ref_dwg_number",
    "kva": "kva",
    "area_class": "area_class",
    "test_equip_model_number": "test_equip_model_number",
    "test_equip_serial_number": "test_equip_serial_number",
    "cal_due": "cal_due",
    "task_1_yes": "task_1_yes",
    "task_1_na": "task_1_na",
    "task_2_yes": "task_2_yes",
    "task_2_na": "task_2_na",
    "task_3_yes": "task_3_yes",
    "task_3_na": "task_3_na",
    "task_4_yes": "task_4_yes",
    "task_4_na": "task_4_na",
    "task_5_yes": "task_5_yes",
    "task_5_na": "task_5_na",
    "task_6_yes": "task_6_yes",
    "task_6_na": "task_6_na",
    "task_7_yes": "task_7_yes",
    "task_7_na": "task_7_na",
    "task_8_yes": "task_8_yes",
    "task_8_na": "task_8_na",
    "task_9_yes": "task_9_yes",
    "task_9_na": "task_9_na",
    "task_10_yes": "task_10_yes",
    "task_10_na": "task_10_na",
    "task_11_yes": "task_11_yes",
    "task_11_na": "task_11_na",
    "task_12_yes": "task_12_yes",
    "task_12_na": "task_12_na",
    "task_13_yes": "task_13_yes",
    "task_13_na": "task_13_na",
    "task_14_yes": "task_14_yes",
    "task_14_na": "task_14_na",
    "task_15_yes": "task_15_yes",
    "task_15_na": "task_15_na",
    "task_16_yes": "task_16_yes",
    "task_16_na": "task_16_na",
    "task_17_yes": "task_17_yes",
    "task_17_na": "task_17_na",
    "task_18_yes": "task_18_yes",
    "task_18_na": "task_18_na",
    "electrical_equipment_testing_na": "electrical_equipment_testing_na",
    "equipment_resistance_testing_na": "equipment_resistance_testing_na",
    "equipment_insulation_resistance_testing_na": "equipment_insulation_resistance_testing_na",
    "torqueing_log_na": "torqueing_log_na",
    "comments_na": "comments_na",
    "equipment_resistance_testing_notes": "equipment_resistance_testing_notes",
    "equipment_insulation_resistance_testing_notes": "equipment_insulation_resistance_testing_notes",
    "torqueing_row_1_cond_id": "torqueing_row_1_cond_id",
    "torqueing_row_1_location": "torqueing_row_1_location",
    "torqueing_row_1_bolt_grade": "torqueing_row_1_bolt_grade",
    "torqueing_row_1_bolt_size": "torqueing_row_1_bolt_size",
    "torqueing_row_1_torque_value": "torqueing_row_1_torque_value",
    "torqueing_row_1_torque_marked": "torqueing_row_1_torque_marked",
    "torqueing_row_1_torque_by": "torqueing_row_1_torque_by",
    "torqueing_row_1_date": "torqueing_row_1_date",
    "torqueing_row_2_cond_id": "torqueing_row_2_cond_id",
    "torqueing_row_2_location": "torqueing_row_2_location",
    "torqueing_row_2_bolt_grade": "torqueing_row_2_bolt_grade",
    "torqueing_row_2_bolt_size": "torqueing_row_2_bolt_size",
    "torqueing_row_2_torque_value": "torqueing_row_2_torque_value",
    "torqueing_row_2_torque_marked": "torqueing_row_2_torque_marked",
    "torqueing_row_2_torque_by": "torqueing_row_2_torque_by",
    "torqueing_row_2_date": "torqueing_row_2_date",
    "torqueing_row_3_cond_id": "torqueing_row_3_cond_id",
    "torqueing_row_3_location": "torqueing_row_3_location",
    "torqueing_row_3_bolt_grade": "torqueing_row_3_bolt_grade",
    "torqueing_row_3_bolt_size": "torqueing_row_3_bolt_size",
    "torqueing_row_3_torque_value": "torqueing_row_3_torque_value",
    "torqueing_row_3_torque_marked": "torqueing_row_3_torque_marked",
    "torqueing_row_3_torque_by": "torqueing_row_3_torque_by",
    "torqueing_row_3_date": "torqueing_row_3_date",
    "torqueing_row_4_cond_id": "torqueing_row_4_cond_id",
    "torqueing_row_4_location": "torqueing_row_4_location",
    "torqueing_row_4_bolt_grade": "torqueing_row_4_bolt_grade",
    "torqueing_row_4_bolt_size": "torqueing_row_4_bolt_size",
    "torqueing_row_4_torque_value": "torqueing_row_4_torque_value",
    "torqueing_row_4_torque_marked": "torqueing_row_4_torque_marked",
    "torqueing_row_4_torque_by": "torqueing_row_4_torque_by",
    "torqueing_row_4_date": "torqueing_row_4_date",
    "torqueing_row_5_cond_id": "torqueing_row_5_cond_id",
    "torqueing_row_5_location": "torqueing_row_5_location",
    "torqueing_row_5_bolt_grade": "torqueing_row_5_bolt_grade",
    "torqueing_row_5_bolt_size": "torqueing_row_5_bolt_size",
    "torqueing_row_5_torque_value": "torqueing_row_5_torque_value",
    "torqueing_row_5_torque_marked": "torqueing_row_5_torque_marked",
    "torqueing_row_5_torque_by": "torqueing_row_5_torque_by",
    "torqueing_row_5_date": "torqueing_row_5_date",
    "comments": "comments",
    "yanda_rep_name": "yanda_rep_name",
    "yanda_rep_date": "yanda_rep_date",
    "yanda_rep_signature": "yanda_rep_signature",
    "client_rep_name": "client_rep_name",
    "client_rep_date": "client_rep_date",
    "client_rep_signature": "client_rep_signature",
}

# No checkbox groups, no ATC-style field-specific on-states, no multi-widget
# fields on this template - it was built for this form only, with exactly
# the 107 fields the schema declares.
YES_NO_CHECKBOXES = {}
CHECKBOX_ON = "/Yes"
CHECKBOX_OFF = "/Off"

# Nothing on this form is hand-signed-only - every sign-off cell is a real
# fillable field (see module docstring).
UNMAPPED_NOTE = None
