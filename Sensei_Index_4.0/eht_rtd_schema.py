# -*- coding: utf-8 -*-
"""
Single source of truth for every field on the EHT & RTD Installation
Inspection Report (Form# YCQE-E&I-004). Same contract transmitter_schema.py/
valve_schema.py/gauge_schema.py already follow - see transmitter_schema.py's
module docstring for what each field key means and how LOG_COLUMNS/
by_section/CONTROL_FIELD are used (by data_access.py,
export_eht_rtd_to_pdf.py, gui_app.py, index_view.py).

Part of the Electrical equipment family added alongside Transmitter/Valve/
Gauge/Transformer Test/Small Power Cable/General Equip Install/EHT
Removal - EQUIPMENT_TYPES in data_access.py carries the per-type metadata
that lets the rest of the app treat any number of equipment types
generically.

Two real PDF fields on this template are unused authoring artifacts, not
real data - a checkbox sitting directly on top of the COOEC logo's "O",
and an empty spacer box in blank space above the Results/Comments column
headers. Both are confirmed decorative (no printed text overlaps either)
and are deliberately left OUT of this schema entirely - see
eht_rtd_field_map.py's ARTIFACT_FIELDS for the record of what they are
and why nothing ever writes to them.

The "Results (Y/N/NA)" cells are plain text boxes on the real PDF (not
checkboxes), but are modeled here as ftype="choice" with
choices=["Y","N","NA"] anyway, for a consistent dropdown edit experience -
the same treatment transmitter_schema.py already gives its own plain-text
"local_display" field.
"""

RESULT_CHOICES = ["Y", "N", "NA"]
YES_NO = ["Y", "N"]

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

# ------------------------------------------------------------ Trace Data ---
_add("trace_number", "Trace #", "trace_data")
_add("controller_number", "Controller #", "trace_data")
_add("trace_part_number", "Trace Part #", "trace_data")
_add("panel_number", "Panel #", "trace_data")
_add("rtds_number", "RTD(s) #", "trace_data")
_add("circuit_number", "Circuit #", "trace_data")
_add("zone_drawing_number", "Zone Drawing #", "trace_data")
_add("rev", "REV", "trace_data")

# ------------------------------------------------- Pre-Insulation Inspection
_add("pre_ins_item_1_1_result", "1.1 E.H.T/RTD Receiving Report Completed - Result",
     "pre_insulation", "choice", RESULT_CHOICES)
_add("pre_ins_item_1_1_comments", "1.1 E.H.T/RTD Receiving Report Completed - Comments", "pre_insulation")
_add("pre_ins_item_1_2_result", "1.2 E.H.T. Tag Matches Part # & Zone Drawing - Result",
     "pre_insulation", "choice", RESULT_CHOICES)
_add("pre_ins_item_1_2_comments", "1.2 E.H.T. Tag Matches Part # & Zone Drawing - Comments", "pre_insulation")
_add("pre_ins_item_1_3_result", "1.3 RTDs Installed per Drawing & Details - Result",
     "pre_insulation", "choice", RESULT_CHOICES)
_add("pre_ins_atc", "1.3 ATC", "pre_insulation", "choice", YES_NO)
_add("pre_ins_r1_ohms", "1.3 R1 (Ω)", "pre_insulation")
_add("pre_ins_r2_ohms", "1.3 R2 (Ω)", "pre_insulation")
_add("pre_ins_item_1_4_result", "1.4 RTD Tags Installed & Labeled Correctly - Result",
     "pre_insulation", "choice", RESULT_CHOICES)
_add("pre_ins_item_1_4_comments", "1.4 RTD Tags Installed & Labeled Correctly - Comments", "pre_insulation")
_add("pre_ins_item_1_5_result", "1.5 E.H.T. Routed & Installed per Standards - Result",
     "pre_insulation", "choice", RESULT_CHOICES)
_add("pre_ins_item_1_5_comments", "1.5 E.H.T. Routed & Installed per Standards - Comments", "pre_insulation")
_add("pre_ins_item_1_6_result", "1.6 As-Builts Completed & Splices Identified - Result",
     "pre_insulation", "choice", RESULT_CHOICES)
_add("pre_ins_item_1_6_comments", "1.6 As-Builts Completed & Splices Identified - Comments", "pre_insulation")
_add("pre_ins_item_1_7_result", "1.7 Power Connections & End Kits Properly Installed - Result",
     "pre_insulation", "choice", RESULT_CHOICES)
_add("pre_ins_item_1_7_comments", "1.7 Power Connections & End Kits Properly Installed - Comments", "pre_insulation")
_add("pre_ins_item_1_8_result", "1.8 MI Trace Continuity Test - Result", "pre_insulation", "choice", RESULT_CHOICES)
_add("pre_ins_mi_ohms", "1.8 MI Trace Continuity - MI (Ω)", "pre_insulation")
_add("pre_ins_megger_mi_500", "Pre-Ins Megger @500 Vdc - MI", "pre_insulation", "choice", YES_NO)
_add("pre_ins_megger_sr_500", "Pre-Ins Megger @500 Vdc - SR", "pre_insulation", "choice", YES_NO)
_add("pre_ins_megger_reading_500", "Pre-Ins Megger @500 Vdc - Reading (mΩ)", "pre_insulation")
_add("pre_ins_megger_mi_1000", "Pre-Ins Megger @1000 Vdc - MI", "pre_insulation", "choice", YES_NO)
_add("pre_ins_megger_sr_1000", "Pre-Ins Megger @1000 Vdc - SR", "pre_insulation", "choice", YES_NO)
_add("pre_ins_megger_reading_1000", "Pre-Ins Megger @1000 Vdc - Reading (mΩ)", "pre_insulation")
_add("pre_ins_megger_mi_2500", "Pre-Ins Megger @2500 Vdc - MI", "pre_insulation", "choice", YES_NO)
_add("pre_ins_megger_sr_2500", "Pre-Ins Megger @2500 Vdc - SR", "pre_insulation", "choice", YES_NO)
_add("pre_ins_megger_reading_2500", "Pre-Ins Megger @2500 Vdc - Reading (mΩ)", "pre_insulation")
_add("pre_ins_test_equip_log", "Pre-Ins Test Equipment Log #", "pre_insulation")

# --------------------------------------------- Pre-Insulation Sign-Off -----
_add("yanda_rep_pre_ins_print", "Pre-Ins Inspected By (YANDA Rep) - Print Name", "pre_insulation_signoff")
_add("yanda_rep_pre_ins_date", "Pre-Ins Inspected By (YANDA Rep) - Date", "pre_insulation_signoff")
_add("client_rep_pre_ins_print", "Pre-Ins Inspected By (Client Rep) - Print Name", "pre_insulation_signoff")
_add("client_rep_pre_ins_date", "Pre-Ins Inspected By (Client Rep) - Date", "pre_insulation_signoff")
# Both reps' "Sign:" line is hand-signed only - no digital field exists for
# either on the real PDF (confirmed: nothing overlaps that spot).

# ------------------------------------------------ Post-Insulation Inspection
_add("post_ins_item_2_1_result", "2.1 Power Boxes & Terminations per Details - Result",
     "post_insulation", "choice", RESULT_CHOICES)
_add("post_ins_item_2_1_comments", "2.1 Power Boxes & Terminations per Details - Comments", "post_insulation")
_add("post_ins_item_2_2_result", "2.2 Power Boxes & Terminations Properly Tagged - Result",
     "post_insulation", "choice", RESULT_CHOICES)
_add("post_ins_item_2_2_comments", "2.2 Power Boxes & Terminations Properly Tagged - Comments", "post_insulation")
_add("post_ins_item_2_3_result", '2.3 "Electric Traced" Stickers Applied - Result',
     "post_insulation", "choice", RESULT_CHOICES)
_add("post_ins_item_2_3_comments", '2.3 "Electric Traced" Stickers Applied - Comments', "post_insulation")
_add("post_ins_item_2_4_result", "2.4 RTDs Installed & Wired per Drawings - Result",
     "post_insulation", "choice", RESULT_CHOICES)
_add("post_ins_atc", "2.4 ATC", "post_insulation", "choice", YES_NO)
_add("post_ins_r1_ohms", "2.4 R1 (Ω)", "post_insulation")
_add("post_ins_r2_ohms", "2.4 R2 (Ω)", "post_insulation")
# 2.5 "MI trace continuity test" has no separate Results field on the real
# PDF (a real asymmetry vs. its pre-insulation mirror, item 1.8 - confirmed,
# not a mapping error) - just the ohms value.
_add("post_ins_mi_ohms", "2.5 MI Trace Continuity - MI (Ω)", "post_insulation")
_add("post_ins_megger_mi_500", "Post-Ins Megger @500 Vdc - MI", "post_insulation", "choice", YES_NO)
_add("post_ins_megger_sr_500", "Post-Ins Megger @500 Vdc - SR", "post_insulation", "choice", YES_NO)
_add("post_ins_megger_reading_500", "Post-Ins Megger @500 Vdc - Reading (mΩ)", "post_insulation")
_add("post_ins_test_equip_log", "Post-Ins Test Equipment Log #", "post_insulation")
_add("post_ins_megger_mi_1000", "Post-Ins Megger @1000 Vdc - MI", "post_insulation", "choice", YES_NO)
_add("post_ins_megger_sr_1000", "Post-Ins Megger @1000 Vdc - SR", "post_insulation", "choice", YES_NO)
_add("post_ins_megger_reading_1000", "Post-Ins Megger @1000 Vdc - Reading (mΩ)", "post_insulation")
_add("post_ins_calibration_due_date", "Post-Ins Megger - Calibration Due Date", "post_insulation")
_add("post_ins_megger_mi_2500", "Post-Ins Megger @2500 Vdc - MI", "post_insulation", "choice", YES_NO)
_add("post_ins_megger_sr_2500", "Post-Ins Megger @2500 Vdc - SR", "post_insulation", "choice", YES_NO)
_add("post_ins_megger_reading_2500", "Post-Ins Megger @2500 Vdc - Reading (mΩ)", "post_insulation")

# --------------------------------------------------------------- Comments --
_add("comments", "Comments", "comments", "multiline")

# ---------------------------------------------------------- Final Sign-Off -
# The table's own header row literally reads "Post Insulation Inspected and
# Tested by" over its first column, with "YANDA" and "CLIENT" as the other
# two - three separate name/date pairs total. SIGNATURE is hand-signed only
# on all three (no digital field for any of them).
_add("final_signoff_performer_name", "Post-Insulation Tested By - Name", "final_signoff")
_add("final_signoff_performer_date", "Post-Insulation Tested By - Date", "final_signoff")
_add("final_signoff_yanda_name", "Post-Insulation Sign-Off (YANDA) - Name", "final_signoff")
_add("final_signoff_yanda_date", "Post-Insulation Sign-Off (YANDA) - Date", "final_signoff")
_add("final_signoff_client_name", "Post-Insulation Sign-Off (Client) - Name", "final_signoff")
_add("final_signoff_client_date", "Post-Insulation Sign-Off (Client) - Date", "final_signoff")


def by_section(section):
    return [f for f in FIELDS if f["section"] == section]


def by_id(field_id):
    for f in FIELDS:
        if f["id"] == field_id:
            return f
    return None


SECTION_TITLES = {
    "header": "Header",
    "trace_data": "Trace Data",
    "pre_insulation": "1.0 Pre-Insulation Inspection",
    "pre_insulation_signoff": "Pre-Insulation Sign-Off",
    "post_insulation": "2.0 Post-Insulation Inspection",
    "comments": "Comments",
    "final_signoff": "Final Sign-Off",
}

LOG_COLUMNS = FIELDS


def _result_rows(prefix, numbers):
    rows = []
    for num in numbers:
        result_id, comments_id = f"{prefix}_{num}_result", f"{prefix}_{num}_comments"
        label = by_id(result_id)["label"].rsplit(" - ", 1)[0]
        rows.append((label, [result_id, comments_id if by_id(comments_id) else None]))
    return rows


def _megger(prefix):
    return {
        "row_header": "Megger",
        "row_header_width": 90,
        "columns": [("MI", 76), ("SR", 76), ("Reading (mΩ)", 0)],
        "rows": [(f"@ {v} Vdc", [f"{prefix}_megger_mi_{v}", f"{prefix}_megger_sr_{v}",
                                 f"{prefix}_megger_reading_{v}"]) for v in (500, 1000, 2500)],
    }


# Edit-form table layouts for gui_app.EditDialog - presentation only. Each
# row is (row label, [field id per column]); a column width of 0 stretches.
# Items 1.3/1.8/2.4 have no Comments cell on the real form (their ATC/ohms
# readings stay ordinary fields right under the table).
GRIDS = [
    {
        "row_header": "Item",
        "row_header_width": 300,
        "columns": [("Result", 84), ("Comments", 0)],
        "rows": _result_rows("pre_ins_item", ["1_1", "1_2", "1_3", "1_4", "1_5", "1_6", "1_7", "1_8"]),
    },
    _megger("pre_ins"),
    {
        "row_header": "Item",
        "row_header_width": 300,
        "columns": [("Result", 84), ("Comments", 0)],
        "rows": _result_rows("post_ins_item", ["2_1", "2_2", "2_3", "2_4"]),
    },
    _megger("post_ins"),
]

if __name__ == "__main__":
    print(f"Total fields: {len(FIELDS)}")
