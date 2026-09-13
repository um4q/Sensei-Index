# -*- coding: utf-8 -*-
"""Precisely measured field rects for the Small Power and Control Cable
Inspection & Test Record (YCQE-E&I-113 Rev.0), derived from a
gridline-overlaid crop of a clean 300 DPI render of page 3 of the user's
uploaded spcc_itrs.pdf (one of 10 filled instances of this same form in
that upload - all sharing an identical printed layout).

All coordinates are PIXEL space at 300 DPI, image origin TOP-LEFT
(y grows downward). Page is 2550 x 3300 px (= 612 x 792 pt, US Letter).

Each entry: (field_id, x0, y0, x1, y1) - the VALUE zone (already past any
printed label sharing the same cell), used both to place the invisible
AcroForm field AND (unlike transformer_test's mostly-blue pen) as the
actual WHITEOUT rect - see build_small_power_cable_template.py's own
docstring for why this form's handwriting doesn't qualify for the
ink-color approach (it's black/near-neutral, indistinguishable from
print by color, on every one of the 10 samples checked).

project / contract_no are NOT modeled as fields - cleanly typeset and
IDENTICAL across all 10 samples of this form in the upload ("K1B Well Pad
Project" / "CA23007"), confirmed by inspection - same precedent
eht_pre_insulation_schema.py set. location IS a real field: still
typeset (not hand-written) but genuinely varies between samples (e.g.
"Drain Tank 29152" vs "Drain Tank 29151").

REVISION 3 (this page's own skew): this scan is measurably rotated - the
SAME printed ruling line sits at a noticeably different y depending how
far across the page you measure it (confirmed directly: a horizontal-
line scan restricted to x~500 puts a row boundary near y=1000, the exact
same boundary restricted to x~2285 sits near y=850 - about 1.4 degrees of
rotation over the page width). REVISION 2's approach (read row heights
once on the left, reuse for every column including the far-right Initial
column) put Visual Inspection's own Initial/NA values off by as much as
90px by the bottom of the table. Every y-band below involving the
Initial/NA column (x~2250) or the Yanda/Client sign-off block was
re-measured directly in ITS OWN x-range, not carried over from a
different column's reading - see the scratchpad tooling this template
was built with for the horizontal-line scans this was based on.

REVISION 1's finding, still true here: "Project:"/"Location:"/
"Contract #:" are STACKED (label on one line, value on the line below,
within the same ruled cell) - unlike every other row on this form (and
unlike transformer_test's own PART 1, which is side-by-side).
"""

PAGE_W_PX = 2550
PAGE_H_PX = 3300
DPI = 300

# --------------------------------------------------------- PART 1 - Project
LOCATION_X = (815.0, 1945.0)
LOCATION_LABEL_Y = (500.0, 548.0)   # "Location:" itself - never touched
LOCATION_VALUE_Y = (550.0, 598.0)   # the line below it - typeset, but varies per sample

# ------------------------------------------------------- PART 2 - Cable Description
CABLE_TAG_NUMBER_X = (490.0, 1195.0)
CABLE_TYPE_X = (1300.0, 1750.0)
SYSTEM_X = (1880.0, 2430.0)
# A small gap (758 vs 766 below) between this row and the next - a first
# attempt with them touching at exactly 762 bled a sliver of this row's
# whiteout into "Number of Conductors:" own label on the row below.
ROW_TAG_Y = (700.0, 758.0)

CABLE_SIZE_X = (295.0, 1195.0)
NUMBER_OF_CONDUCTORS_X = (1480.0, 1955.0)
CABLE_RATED_VOLTAGE_X = (2345.0, 2430.0)
# y1=828 (a first estimate) overlapped the real "PART 3 - Visual
# Inspection" header bar, which starts at ~793, not ~845 as first assumed
# - found by directly locating that header's own text in the source
# image after a render showed it missing. 790 is a confirmed safe stop.
ROW_SIZE_Y = (766.0, 790.0)

# ------------------------------------------------------- PART 3 - Visual Inspection
# Measured directly in the Initial/NA column's OWN x-range (x~2150-2420) -
# see REVISION 3 above. The tall gap (item 9's row, whose printed text
# wraps to 2 lines) is the unambiguous anchor: exactly 8 normal-height
# rows precede it (items 1-8) and 2 follow it (items 10-11).
VISUAL_INITIAL_X = (2250.0, 2420.0)
VISUAL_ROWS_Y = [909.5, 968.0, 1027.5, 1087.5, 1146.5, 1205.5, 1264.5, 1324.5,
                 1383.5, 1479.5, 1538.5, 1598.0]  # item 9 (2-line label) gets extra height
VISUAL_FIELDS = []
for _n in range(11):
    y0, y1 = VISUAL_ROWS_Y[_n], VISUAL_ROWS_Y[_n + 1]
    VISUAL_FIELDS.append((f"vis_item_{_n + 1}_initial", VISUAL_INITIAL_X, (y0, y1)))

# ------------------------------------------------------- PART 4 - Test Equipment
# Column labels live in their own header row (not repeated per data row,
# unlike transformer_test's own Test Equipment table) - only 1 data row,
# generously tall (the ruled row itself is ~110px, not just line height).
TEST_EQUIP_ROW_Y = (1690.0, 1800.0)
TEST_EQUIP_COLS = [
    ("make", (150.0, 615.0)), ("model", (615.0, 1000.0)),
    ("asset_serial", (1000.0, 1480.0)), ("calibrated_on", (1480.0, 2380.0)),
]
TEST_EQUIP_FIELDS = [(f"test_equip_{_id}", _x, TEST_EQUIP_ROW_Y) for _id, _x in TEST_EQUIP_COLS]

# ------------------------------------------------------- PART 5 - Test Results
_RESULT_ROWS_Y = [2000.0, 2053.0, 2107.0, 2165.0]
_RESULT_ROW_IDS = ["conductor_to_conductor", "conductor_to_ground", "conductor_to_armour"]
INSULATION_RESULT_X = (630.0, 995.0)
CONTINUITY_RESULT_X = (1660.0, 1955.0)
RESULT_FIELDS = []
for _n, _id in enumerate(_RESULT_ROW_IDS):
    y0, y1 = _RESULT_ROWS_Y[_n], _RESULT_ROWS_Y[_n + 1]
    RESULT_FIELDS.append((f"insulation_{_id}", INSULATION_RESULT_X, (y0, y1)))
    RESULT_FIELDS.append((f"continuity_{_id}", CONTINUITY_RESULT_X, (y0, y1)))

# --------------------------------------------------------------- PART 6 - Remarks
REMARKS_BOX = ("remarks", (150.0, 2380.0), (2225.0, 2345.0))

# ------------------------------------------------------------------- PART 7 Sign-off
SIGNOFF_YANDA_X = (145.0, 965.0)
SIGNOFF_CLIENT_X = (965.0, 2380.0)
_SIGNOFF_LABEL_INSET = 0.34
_SIGNOFF_RIGHT_MARGIN = 0.06


def _signoff_value_x(col_x0, col_x1):
    w = col_x1 - col_x0
    return (col_x0 + _SIGNOFF_LABEL_INSET * w, col_x1 - _SIGNOFF_RIGHT_MARGIN * w)


SIGNOFF_NAME_Y = (2535.0, 2600.0)
SIGNOFF_DATE_Y = (2600.0, 2660.0)
SIGNOFF_SIGNATURE_Y = (2660.0, 2720.0)

SIGNOFF_FIELDS = [
    ("yanda_rep_name", _signoff_value_x(*SIGNOFF_YANDA_X), SIGNOFF_NAME_Y),
    ("yanda_rep_date", _signoff_value_x(*SIGNOFF_YANDA_X), SIGNOFF_DATE_Y),
    ("yanda_rep_signature", _signoff_value_x(*SIGNOFF_YANDA_X), SIGNOFF_SIGNATURE_Y),
    ("client_rep_name", _signoff_value_x(*SIGNOFF_CLIENT_X), SIGNOFF_NAME_Y),
    ("client_rep_date", _signoff_value_x(*SIGNOFF_CLIENT_X), SIGNOFF_DATE_Y),
    ("client_rep_signature", _signoff_value_x(*SIGNOFF_CLIENT_X), SIGNOFF_SIGNATURE_Y),
]


def all_fields():
    yield ("location", LOCATION_X[0], LOCATION_VALUE_Y[0], LOCATION_X[1], LOCATION_VALUE_Y[1])
    yield ("cable_tag_number", CABLE_TAG_NUMBER_X[0], ROW_TAG_Y[0], CABLE_TAG_NUMBER_X[1], ROW_TAG_Y[1])
    yield ("cable_type", CABLE_TYPE_X[0], ROW_TAG_Y[0], CABLE_TYPE_X[1], ROW_TAG_Y[1])
    yield ("system", SYSTEM_X[0], ROW_TAG_Y[0], SYSTEM_X[1], ROW_TAG_Y[1])
    yield ("cable_size", CABLE_SIZE_X[0], ROW_SIZE_Y[0], CABLE_SIZE_X[1], ROW_SIZE_Y[1])
    yield ("number_of_conductors", NUMBER_OF_CONDUCTORS_X[0], ROW_SIZE_Y[0],
           NUMBER_OF_CONDUCTORS_X[1], ROW_SIZE_Y[1])
    yield ("cable_rated_voltage", CABLE_RATED_VOLTAGE_X[0], ROW_SIZE_Y[0],
           CABLE_RATED_VOLTAGE_X[1], ROW_SIZE_Y[1])
    for fid, (x0, x1), (y0, y1) in VISUAL_FIELDS:
        yield fid, x0, y0, x1, y1
    for fid, (x0, x1), (y0, y1) in TEST_EQUIP_FIELDS:
        yield fid, x0, y0, x1, y1
    for fid, (x0, x1), (y0, y1) in RESULT_FIELDS:
        yield fid, x0, y0, x1, y1
    fid, (x0, x1), (y0, y1) = REMARKS_BOX
    yield fid, x0, y0, x1, y1
    for fid, (x0, x1), (y0, y1) in SIGNOFF_FIELDS:
        yield fid, x0, y0, x1, y1


if __name__ == "__main__":
    fields = list(all_fields())
    print(f"Total fields: {len(fields)}")
    for f in fields:
        print(f)
