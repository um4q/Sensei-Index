# -*- coding: utf-8 -*-
"""Precisely measured field rects for the General Electrical Equipment
Installation & Test Report (YCQE-E&I-013 Rev.0) - the third and most
complex of the new forms from the user's second uploaded scan bundle
(spcc_itrs.pdf). Derived from gridline-overlaid crops of a clean 300 DPI
render of page 2 of that upload, one sample only (no repeats of this
form in the bundle) - see the module docstring in
build_general_equip_install_template.py for the overall build approach.

All coordinates are PIXEL space at 300 DPI, image origin TOP-LEFT
(y grows downward). Page is 2550 x 3300 px (= 612 x 792 pt, US Letter).

Unlike transformer_test (blue pen, ink-color whiteout) this form's
handwriting is a MIX of blue (e.g. the header's own "Tag #" and the
Torqueing Log's "Location" cell) and black/near-neutral (everything
else, confirmed by direct inspection of a page-wide ink-color pass that
left almost every field untouched) - not worth splitting into two
techniques for one form, so every field here uses the same rectangle
whiteout small_power_cable does.

CUSTOMER NAME / PROJECT NAME / CONTRACT# are NOT modeled as fields -
cleanly typeset, matching this whole engagement's constant values (same
precedent every other Electrical form here already set). LOCATION IS a
field - also typeset (not hand-written) on this form, matching
small_power_cable's own treatment of its Location field, not
transformer_test's (whose own Location is hand-written).

Two sections have NO printed column structure at all - "EQUIPMENT
RESISTANCE TESTING" and "EQUIPMENT INSULATION RESISTANCE TESTING (1
MINUTE PER)" are each a blank 2-row grid with unlabeled cells (no column
headers anywhere on the form, on the one sample seen - a genuine gap in
the source form's own design, not something this app invented). Rather
than guess at column meanings that don't exist, each is modeled as ONE
multiline field spanning the whole blank area - the printed grid lines
stay exactly as scanned (nothing about the design changes), it's just
fillable as free text instead of column-by-column.

"TORQUE MARKED" (one column in the 5-row Torqueing Log sub-table) is a
printed checkbox + "YES" per row, modeled as a single narrow text field
per row (same "plain text, not a real checkbox" choice every other form
here makes) - matches this same upload's General Electrical form's own
"YES INITIAL"/"N/A INITIAL" verification columns and the valve ITR's
fv_N_yes/fv_N_na split.
"""

PAGE_W_PX = 2550
PAGE_H_PX = 3300
DPI = 300

# ---------------------------------------------------------------- Header block
LOCATION_X = (2005.0, 2430.0)
LOCATION_Y = (432.0, 495.0)

ROW_TAG_Y = (505.0, 560.0)
# REVISION 2 (rectangle-whiteout width fix): tag_number/serial_number were
# both measured far too narrow - a direct pixel/gridline check against the
# clean source showed the real sample's handwritten values ("29152-
# DCSFFJB-001", "5478101") both run right up to their column's own
# vertical divider, not stopping ~300px short of it the way the original
# rects did. Rectangle whiteout (unlike the old page-wide ink-color pass)
# only ever clears what its own rect covers, so a too-narrow rect here
# left the value's own tail end fully visible on the built template -
# found by direct visual audit, not by the original halo-check pass
# (which evidently never caught this one). Widened to each column's real
# divider position (~995 / ~610), measured off a gridline crop.
TAG_NUMBER_X = (355.0, 850.0)
MANUFACTURER_X = (1130.0, 1400.0)
MODEL_NUMBER_X = (1610.0, 1900.0)
SYSTEM_NUMBER_X = (2160.0, 2500.0)

ROW_SERIAL_Y = (562.0, 618.0)
SERIAL_NUMBER_X = (270.0, 610.0)
VOLTAGE_X = (595.0, 745.0)
FREQ_X = (810.0, 995.0)
PHASE_X = (1090.0, 1195.0)
AMPS_X = (1320.0, 1495.0)
AREA_CLASS_OF_EQUIP_X = (2280.0, 2525.0)

ROW_REFDWG_Y = (625.0, 680.0)
REF_DWG_NUMBER_X = (430.0, 1495.0)
KVA_X = (1590.0, 1745.0)
AREA_CLASS_X = (2070.0, 2525.0)

ROW_TESTEQUIP_Y = (685.0, 745.0)
TEST_EQUIP_MODEL_NUMBER_X = (625.0, 700.0)
TEST_EQUIP_SERIAL_NUMBER_X = (1375.0, 1690.0)
CAL_DUE_X = (1875.0, 2500.0)

HEADER_FIELDS = [
    ("tag_number", TAG_NUMBER_X, ROW_TAG_Y),
    ("manufacturer", MANUFACTURER_X, ROW_TAG_Y),
    ("model_number", MODEL_NUMBER_X, ROW_TAG_Y),
    ("system_number", SYSTEM_NUMBER_X, ROW_TAG_Y),
    ("serial_number", SERIAL_NUMBER_X, ROW_SERIAL_Y),
    ("voltage", VOLTAGE_X, ROW_SERIAL_Y),
    ("freq", FREQ_X, ROW_SERIAL_Y),
    ("phase", PHASE_X, ROW_SERIAL_Y),
    ("amps", AMPS_X, ROW_SERIAL_Y),
    ("area_class_of_equip", AREA_CLASS_OF_EQUIP_X, ROW_SERIAL_Y),
    ("ref_dwg_number", REF_DWG_NUMBER_X, ROW_REFDWG_Y),
    ("kva", KVA_X, ROW_REFDWG_Y),
    ("area_class", AREA_CLASS_X, ROW_REFDWG_Y),
    ("test_equip_model_number", TEST_EQUIP_MODEL_NUMBER_X, ROW_TESTEQUIP_Y),
    ("test_equip_serial_number", TEST_EQUIP_SERIAL_NUMBER_X, ROW_TESTEQUIP_Y),
    ("cal_due", CAL_DUE_X, ROW_TESTEQUIP_Y),
]

# ------------------------------------------------------------ Verifications (18)
YES_INITIAL_X = (1910.0, 2075.0)
NA_INITIAL_X = (2080.0, 2330.0)
# 19 boundaries -> 18 rows. Item 2 (2-line) and item 14 (2-line) are
# taller than the rest - measured directly off a gridline crop, not
# interpolated (see module docstring in build_general_equip_install_template.py
# re: why an earlier interpolation approach on a sibling form's Visual
# Inspection table broke badly and isn't repeated here).
TASK_ROWS_Y = [838.0, 883.0, 955.0, 1000.0, 1062.5, 1125.0, 1187.5, 1250.0,
               1300.0, 1350.0, 1400.0, 1450.0, 1500.0, 1544.6, 1616.0,
               1660.6, 1705.2, 1750.0, 1810.0]
TASK_FIELDS = []
for _n in range(18):
    y0, y1 = TASK_ROWS_Y[_n], TASK_ROWS_Y[_n + 1]
    TASK_FIELDS.append((f"task_{_n + 1}_yes", YES_INITIAL_X, (y0, y1)))
    TASK_FIELDS.append((f"task_{_n + 1}_na", NA_INITIAL_X, (y0, y1)))

# ------------------------------------------------------- Section N/A checkboxes
# Each of these 5 section headers has its own small "[ ] N/A" checkbox -
# narrow fields, just the checkbox glyph (same "one field per checkbox"
# convention as everywhere else on this form).
SECTION_NA_FIELDS = [
    ("electrical_equipment_testing_na", (1225.0, 1270.0), (1815.0, 1855.0)),
    ("equipment_resistance_testing_na", (1225.0, 1270.0), (1955.0, 1995.0)),
    ("equipment_insulation_resistance_testing_na", (1395.0, 1440.0), (2130.0, 2170.0)),
    ("torqueing_log_na", (1130.0, 1175.0), (2250.0, 2290.0)),
    ("comments_na", (1095.0, 1140.0), (2700.0, 2745.0)),
]

# ----------------------------------------------------- Unlabeled blank grids
# See module docstring - no column headers exist on the form for either
# of these, so each is one multiline field spanning its whole blank area.
EQUIPMENT_RESISTANCE_TESTING_NOTES = ("equipment_resistance_testing_notes", (170.0, 2530.0), (2000.0, 2100.0))
EQUIPMENT_INSULATION_RESISTANCE_TESTING_NOTES = (
    "equipment_insulation_resistance_testing_notes", (170.0, 2530.0), (2150.0, 2250.0))

# --------------------------------------------------------------- Torqueing Log
TORQUEING_COLS = [
    ("cond_id", (170.0, 680.0)),
    ("location", (680.0, 1105.0)),
    ("bolt_grade", (1105.0, 1290.0)),
    ("bolt_size", (1290.0, 1410.0)),
    ("torque_value", (1410.0, 1680.0)),
    ("torque_marked", (1685.0, 1740.0)),   # just the checkbox glyph
    ("torque_by", (1875.0, 2085.0)),
    ("date", (2085.0, 2350.0)),
]
TORQUEING_ROWS_Y = [(2400.0, 2500.0), (2500.0, 2550.0), (2550.0, 2600.0),
                     (2600.0, 2650.0), (2650.0, 2700.0)]
TORQUEING_FIELDS = []
for _row_n, _row_y in enumerate(TORQUEING_ROWS_Y, start=1):
    for _col_id, _col_x in TORQUEING_COLS:
        TORQUEING_FIELDS.append((f"torqueing_row_{_row_n}_{_col_id}", _col_x, _row_y))

# ------------------------------------------------------------------- Comments
COMMENTS_BOX = ("comments", (170.0, 2530.0), (2750.0, 2850.0))

# ------------------------------------------------------------------- Sign-off
SIGNOFF_YANDA_X = (170.0, 960.0)
SIGNOFF_DATE_X = (960.0, 1495.0)
SIGNOFF_SIGNATURE_X = (1495.0, 2530.0)
SIGNOFF_YANDA_ROW_Y = (2900.0, 2950.0)
SIGNOFF_CLIENT_ROW_Y = (3000.0, 3050.0)

SIGNOFF_FIELDS = [
    ("yanda_rep_name", SIGNOFF_YANDA_X, SIGNOFF_YANDA_ROW_Y),
    ("yanda_rep_date", SIGNOFF_DATE_X, SIGNOFF_YANDA_ROW_Y),
    ("yanda_rep_signature", SIGNOFF_SIGNATURE_X, SIGNOFF_YANDA_ROW_Y),
    ("client_rep_name", SIGNOFF_YANDA_X, SIGNOFF_CLIENT_ROW_Y),
    ("client_rep_date", SIGNOFF_DATE_X, SIGNOFF_CLIENT_ROW_Y),
    ("client_rep_signature", SIGNOFF_SIGNATURE_X, SIGNOFF_CLIENT_ROW_Y),
]


def all_fields():
    yield ("location", LOCATION_X[0], LOCATION_Y[0], LOCATION_X[1], LOCATION_Y[1])
    for fid, (x0, x1), (y0, y1) in HEADER_FIELDS:
        yield fid, x0, y0, x1, y1
    for fid, (x0, x1), (y0, y1) in TASK_FIELDS:
        yield fid, x0, y0, x1, y1
    for fid, (x0, x1), (y0, y1) in SECTION_NA_FIELDS:
        yield fid, x0, y0, x1, y1
    fid, (x0, x1), (y0, y1) = EQUIPMENT_RESISTANCE_TESTING_NOTES
    yield fid, x0, y0, x1, y1
    fid, (x0, x1), (y0, y1) = EQUIPMENT_INSULATION_RESISTANCE_TESTING_NOTES
    yield fid, x0, y0, x1, y1
    for fid, (x0, x1), (y0, y1) in TORQUEING_FIELDS:
        yield fid, x0, y0, x1, y1
    fid, (x0, x1), (y0, y1) = COMMENTS_BOX
    yield fid, x0, y0, x1, y1
    for fid, (x0, x1), (y0, y1) in SIGNOFF_FIELDS:
        yield fid, x0, y0, x1, y1


if __name__ == "__main__":
    fields = list(all_fields())
    print(f"Total fields: {len(fields)}")
    for f in fields:
        print(f)
