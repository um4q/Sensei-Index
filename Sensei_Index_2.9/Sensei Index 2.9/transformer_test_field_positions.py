# -*- coding: utf-8 -*-
"""Precisely measured field rects for the Transformer Test Record
(YCQE-E&I-112 Rev. 0), derived from horizontal/vertical ruling-line
detection against a clean 300 DPI render of page 1 of the user's uploaded
spcc_itrs.pdf, then visually cross-checked against gridline-overlaid
crops of every section - same methodology as
eht_pre_insulation_field_positions.py (see that module's own docstring
for the general approach).

All coordinates are PIXEL space at 300 DPI, image origin TOP-LEFT
(y grows downward). Page is 2550 x 3300 px (= 612 x 792 pt, US Letter).

Each entry: (field_id, x0, y0, x1, y1) - x0,y0 = top-left, x1,y1 =
bottom-right of the VALUE zone only (already past any printed label
sharing the same ruled cell - see "label-inset" note below), not yet
inset for padding (the consumer insets further before both whiting-out
and placing the AcroForm field).

REVISION 2 (label-inset fix): revision 1 used each field's full RULED
CELL as its rect - correct for cells with no printed label (the
Insulation/Winding Resistance and Visual Inspection data cells, whose
label lives in a separate header row above), but WRONG for every cell
that packs "Label: value" into one ruled box (e.g. "Tag: ____"), which
this form uses throughout PART 1-3 and PART 7's sign-off block. Whiting
out the full cell there erased the printed label too - caught by
rendering the background and visually comparing against the source scan
(see build_transformer_test_template.py). Every such field below is
inset to start just past where the printed label ends (measured off a
gridline-overlaid crop, one ruler-pixel at a time), not at the cell's
own left edge.

REVISION 3 (ink-color whiteout, not rectangle whiteout): rectangle-based
whiteout turned out to be fundamentally too imprecise for a hand-filled
source scan - the same measurement error that risks clipping a label
also risks leaving handwriting fragments visible past the rectangle's
edge, and the two failure modes pull in opposite directions (see
build_transformer_test_template.py's own docstring for the full story).
The actual background image is instead produced by whiting out
HANDWRITTEN INK PIXELS directly, detected by color (this sample's pen is
blue; see ink_whiteout.py) across the WHOLE page, independent of any
rect below. The rects in this module now serve ONE job: placing each
invisible AcroForm text field in a sane spot within its cell so newly
typed text doesn't render on top of the printed label - they no longer
need to be whiteout-precise, and a few pixels off is harmless. The 4
fields whose handwriting is black, not blue (project, location,
contract_no, serial_number - see build_transformer_test_template.py) are
the one place color-detection can't distinguish ink from print; those
four get an additional small manual whiteout patch (still just a rect,
but now only needing to beat 4 fields, not all 65 - see
MANUAL_BLACK_INK_PATCHES).

Unlike eht_pre_insulation's own header, "Project:" / "Location:" /
"Contract #:" on THIS form are hand-written on every field (all-caps
technician print, not typeset) - confirmed by inspection of this exact
page - so, unlike eht_pre_insulation's precedent, they are real fillable
fields here, not baked into the background. (Contrast with the OTHER two
new forms from this same upload, general_equip_install and
small_power_cable, whose own Customer/Project/Contract# header text IS
cleanly typeset/identical across every sample seen - those bake it in,
matching the eht_pre_insulation precedent properly.)

"Transformer type: [ ] Dry [ ] Wet" is modeled as two independent small
text fields (transformer_type_dry / transformer_type_wet, one per
checkbox glyph) rather than one field or a real /Btn checkbox widget -
same "plain text field, not a real checkbox" choice eht_pre_insulation's
REVISION 2 build made for every cell on that form (see its
field_map.py docstring), and the same "one field per checkbox" shape the
valve ITR's fv_N_yes/fv_N_na split and this same upload's own General
Electrical Equipment form's YES/N-A columns use. Both checkbox zones are
deliberately narrow (just the glyph) so they can never bleed into the
printed "Dry"/"Wet" word beside them.

"Primary Tap Setting: ___ % ___ Volts" packs two handwritten blanks plus
two PRINTED words ("%", "Volts") into one cell with no internal ruling
line - the split below is measured off the gridline crop, not
ruling-line-detected (there's no rule to detect).
"""

PAGE_W_PX = 2550
PAGE_H_PX = 3300
DPI = 300

# --------------------------------------------------------- PART 1 - Project
# All hand-written on this form (see module docstring) - all three are
# real fields, not baked.
PROJECT_X = (350.0, 1081.0)
LOCATION_X = (1260.0, 1960.0)
# x0 measured directly off a 4x zoomed gridline crop: "Contract #:"'s own
# colon ends at x=2100, the handwritten value's "C" begins at x=2103 - a
# genuinely tight 3px gap on this sample, not a wide label-inset margin
# like every other field on this form gets (an earlier attempt at x0=2133,
# reasoned from a coarser per-row scan that mistook parts of the
# overlapping value for label, missed the value's own left edge entirely).
# y1 widened past PART1_ROW_Y's own row line (589.5) because this field's
# handwritten value has a descender that dips to y=600 - well short of
# where "PART 2 - Transformer Nameplate Data" header text starts (y=648),
# so this is still safe.
CONTRACT_NO_X = (2101.0, 2367.5)
CONTRACT_NO_Y = (527.0, 610.0)
PART1_ROW_Y = (527.0, 589.5)

# ------------------------------------------------- PART 2 - Nameplate Data
# REVISION 4 (rectangle-whiteout label-safety fix): switching the actual
# background image from ink-color whiteout back to clean rectangle
# whiteout (see build_transformer_test_template.py's own REVISION 4 note)
# exposed that several of these rects, though fine as mere AcroForm-field
# placements, actually overlapped their own printed label once used to
# draw a real white rectangle - confirmed by direct pixel measurement
# against the clean source render, not visual guessing. tag/
# transformer_type_dry/transformer_type_wet/rating_kva/temperature_rise
# below are corrected; everything else in this file was verified clean at
# rectangle-whiteout precision and left as-is.
TAG_X = (285.0, 907.0)  # was 260.0 - overlapped "Tag:"
# transformer_type_dry/wet: previously sat ON the "Dry"/"Wet" WORDS
# themselves, not the checkbox glyph before each word - harmless for an
# invisible AcroForm field, but fatal once whited as a rectangle (it erased
# "Dry"/"Wet" outright). The checkbox glyph's own printed border is also too
# thin/small to reliably survive whiteout-then-ink-cleanup at this box's
# ~40x43px size (the checkmark ink inside touches the border on a hand-
# filled sample), so build_transformer_test_template.py's own background
# rebuild step whites out the FULL glyph (TRANSFORMER_TYPE_*_GLYPH_BOX
# below) and draws a fresh, clean border back in - see that script's own
# docstring. These two X-tuples are the field's own INTERIOR only (inside
# the fresh border), so typed input never renders on top of it.
TRANSFORMER_TYPE_DRY_X = (1231.0, 1264.0)
TRANSFORMER_TYPE_WET_X = (1361.0, 1394.0)
TRANSFORMER_TYPE_CHECKBOX_Y = (655.0, 690.0)  # narrower than ROW_TAG_Y - just the glyph's own interior
# Full outer glyph bounds (border included), measured by pixel-scanning the
# clean source render for each box's own horizontal top/bottom border runs -
# used only by the background-rebuild script to whiteout+redraw the glyph,
# never for AcroForm field placement (see TRANSFORMER_TYPE_*_X above for that).
TRANSFORMER_TYPE_DRY_GLYPH_BOX = (1227.0, 651.0, 1268.0, 694.0)
TRANSFORMER_TYPE_WET_GLYPH_BOX = (1357.0, 651.0, 1398.0, 694.0)
SYSTEM_X = (2130.0, 2368.0)
ROW_TAG_Y = (649.5, 708.5)

MAKE_X = (300.0, 907.0)
MODEL_X = (1100.0, 1639.0)
SERIAL_NUMBER_X = (1900.0, 2368.5)
ROW_MAKE_Y = (708.5, 767.5)

PRIMARY_VOLTAGE_X = (620.0, 907.0)
SECONDARY_VOLTAGE_X = (1350.0, 1639.5)
PHASE_X = (1780.0, 2369.0)
ROW_VOLTAGE_Y = (767.5, 827.0)

PRIMARY_FLA_X = (450.0, 721.0)
SECONDARY_FLA_X = (1010.0, 1271.5)
RATING_KVA_X = (1568.0, 1819.0)  # was 1560.0 - clipped "(KVA):"
TEMPERATURE_RISE_X = (2142.0, 2369.0)  # was 2130.0 - clipped "Rise:"
ROW_FLA_Y = (827.0, 886.5)

PRIMARY_CONNECTION_X = (610.0, 1272.0)
SECONDARY_CONNECTION_X = (1730.0, 2370.0)
ROW_CONNECTION_Y = (886.5, 945.5)

PRIMARY_TAP_PERCENT_X = (610.0, 695.0)
PRIMARY_TAP_VOLTS_X = (735.0, 895.0)
AREA_CLASSIFICATION_X = (1700.0, 2370.0)
ROW_TAP_Y = (945.5, 1005.5)

NAMEPLATE_FIELDS = [
    ("tag", TAG_X, ROW_TAG_Y),
    ("transformer_type_dry", TRANSFORMER_TYPE_DRY_X, TRANSFORMER_TYPE_CHECKBOX_Y),
    ("transformer_type_wet", TRANSFORMER_TYPE_WET_X, TRANSFORMER_TYPE_CHECKBOX_Y),
    ("system", SYSTEM_X, ROW_TAG_Y),
    ("make", MAKE_X, ROW_MAKE_Y),
    ("model", MODEL_X, ROW_MAKE_Y),
    ("serial_number", SERIAL_NUMBER_X, ROW_MAKE_Y),
    ("primary_voltage", PRIMARY_VOLTAGE_X, ROW_VOLTAGE_Y),
    ("secondary_voltage", SECONDARY_VOLTAGE_X, ROW_VOLTAGE_Y),
    ("phase", PHASE_X, ROW_VOLTAGE_Y),
    ("primary_fla", PRIMARY_FLA_X, ROW_FLA_Y),
    ("secondary_fla", SECONDARY_FLA_X, ROW_FLA_Y),
    ("rating_kva", RATING_KVA_X, ROW_FLA_Y),
    ("temperature_rise", TEMPERATURE_RISE_X, ROW_FLA_Y),
    ("primary_connection", PRIMARY_CONNECTION_X, ROW_CONNECTION_Y),
    ("secondary_connection", SECONDARY_CONNECTION_X, ROW_CONNECTION_Y),
    ("primary_tap_setting_percent", PRIMARY_TAP_PERCENT_X, ROW_TAP_Y),
    ("primary_tap_setting_volts", PRIMARY_TAP_VOLTS_X, ROW_TAP_Y),
    ("area_classification", AREA_CLASSIFICATION_X, ROW_TAP_Y),
]

# ---------------------------------------------------- PART 3 - Test Equipment
# Unlike Insulation/Winding Resistance below, EACH of these 2 rows repeats
# its own "Make:"/"Model:"/"Asset/Serial Number:"/"Calibrated On:" labels
# in-cell (confirmed via gridline crop - there is no separate header row
# + blank data rows here, both rows are independently labelled) - every
# column here needs the same label-inset treatment as PART 2 above.
TEST_EQUIP_ROWS_Y = [(1064.0, 1157.0), (1157.0, 1249.0)]
TEST_EQUIP_COLS = [
    ("make", (400.0, 725.0)),
    ("model", (945.0, 1275.0)),
    ("asset_serial", (1670.0, 1821.0)),
    ("calibrated_on", (2100.0, 2370.5)),
]
TEST_EQUIP_FIELDS = []
for _row_n, _row_y in enumerate(TEST_EQUIP_ROWS_Y, start=1):
    for _col_id, _col_x in TEST_EQUIP_COLS:
        TEST_EQUIP_FIELDS.append((f"test_equip_{_row_n}_{_col_id}", _col_x, _row_y))

# ------------------------------------------------- PART 4 - Insulation Resistance
# Column labels live in their OWN header row (not repeated per data row) -
# confirmed via gridline crop - so these data cells are blank edge-to-edge
# and need no label-inset.
INSUL_ROWS_Y = [(1433.0, 1495.0), (1495.0, 1557.5)]
INSUL_COLS = [
    ("primary_to_ground", (181.0, 578.0)),
    ("secondary_to_ground", (578.0, 978.0)),
    ("primary_to_secondary", (978.0, 1376.0)),
    ("test_voltage", (1376.0, 1772.0)),
    ("ambient", (1772.0, 2171.0)),
    ("initial", (2171.0, 2372.0)),
]
INSULATION_FIELDS = []
for _row_n, _row_y in enumerate(INSUL_ROWS_Y, start=1):
    for _col_id, _col_x in INSUL_COLS:
        INSULATION_FIELDS.append((f"insulation_row_{_row_n}_{_col_id}", _col_x, _row_y))

# ---------------------------------------------------- Winding Resistance
# Same "separate header row" shape as Insulation Resistance above.
WINDING_ROW_Y = (1682.0, 1744.5)
WINDING_COLS = [
    ("h1", (182.0, 454.5)), ("h2", (454.5, 724.0)), ("h3", (724.0, 996.0)),
    ("x1", (996.0, 1266.0)), ("x2", (1266.0, 1536.0)), ("x3", (1536.0, 1806.0)),
    ("ambient", (1806.0, 2173.0)), ("initial", (2173.0, 2373.5)),
]
WINDING_FIELDS = [(f"winding_{_id}", _x, WINDING_ROW_Y) for _id, _x in WINDING_COLS]

# ------------------------------------------------------- PART 5 - Visual Inspection
# "Initial/NA" is a column header (own row, band 21 above item 1), each
# item row's value cell is blank - no label-inset needed.
VISUAL_ROWS_Y = [1882.5, 1944.5, 2007.0, 2069.0, 2132.0, 2194.0, 2256.5, 2319.5, 2381.5]
VISUAL_INITIAL_X = (2178.0, 2374.0)
VISUAL_FIELDS = []
for _n in range(8):
    y0, y1 = VISUAL_ROWS_Y[_n], VISUAL_ROWS_Y[_n + 1]
    VISUAL_FIELDS.append((f"vis_item_{_n + 1}_initial", VISUAL_INITIAL_X, (y0, y1)))

# --------------------------------------------------------------- PART 6 - Remarks
# Below the "PART 6 - Remarks" header bar, blank edge-to-edge - no label.
REMARKS_BOX = ("remarks", (185.0, 2377.0), (2441.0, 2566.5))
# No supplementary whiteout-only patches needed on this form beyond the
# ink-color pass (REVISION 3) and the 4 black-ink fields below - kept as
# an empty list, not deleted outright, so this still matches the same
# "EXTRA_CLEANUP_PATCHES" shape eht_pre_insulation_field_positions.py
# uses (an initial attempt at one, targeting a supposed handwriting-bleed
# spot above the Remarks box, turned out to instead be clipping "PART 6
# - Remarks" itself - the ink-color pass already handles the real
# handwriting there with no help needed).
EXTRA_CLEANUP_PATCHES = []

# This form's pen for Project/Location/Contract#/Serial Number happens to
# be near-black (not the blue ink used everywhere else on this page). Under
# REVISION 3 (page-wide ink-COLOR whiteout) this mattered a lot - color
# detection can't tell black ink from black print, so these four needed a
# hand-measured rectangle patch applied on top. REVISION 4 (back to
# rectangle whiteout for every field, see build_transformer_test_template.py)
# whites out every field's own rect uniformly regardless of ink color, so
# these four are no longer special-cased - MANUAL_BLACK_INK_PATCHES is
# retired (removed, not left as dead code) and all_fields() below is the
# only source of truth for what gets whited.

# ------------------------------------------------------------------- PART 7 Sign-off
# "Name:"/"Date:"/"Signature:" labels are printed on each line, to the
# left of a handwritten-on underline - value zones measured off a
# gridline crop, not ruling-line-detected (there's no full cell border
# between the three lines, just underline strokes).
SIGNOFF_YANDA_VALUE_X = (380.0, 1150.0)
SIGNOFF_CLIENT_VALUE_X = (1520.0, 2375.0)
SIGNOFF_NAME_Y = (2696.0, 2766.5)
SIGNOFF_DATE_Y = (2766.5, 2837.0)
SIGNOFF_SIGNATURE_Y = (2837.0, 2908.0)

SIGNOFF_FIELDS = [
    ("yanda_rep_name", SIGNOFF_YANDA_VALUE_X, SIGNOFF_NAME_Y),
    ("yanda_rep_date", SIGNOFF_YANDA_VALUE_X, SIGNOFF_DATE_Y),
    ("yanda_rep_signature", SIGNOFF_YANDA_VALUE_X, SIGNOFF_SIGNATURE_Y),
    ("client_rep_name", SIGNOFF_CLIENT_VALUE_X, SIGNOFF_NAME_Y),
    ("client_rep_date", SIGNOFF_CLIENT_VALUE_X, SIGNOFF_DATE_Y),
    ("client_rep_signature", SIGNOFF_CLIENT_VALUE_X, SIGNOFF_SIGNATURE_Y),
]


def all_fields():
    yield ("project", PROJECT_X[0], PART1_ROW_Y[0], PROJECT_X[1], PART1_ROW_Y[1])
    yield ("location", LOCATION_X[0], PART1_ROW_Y[0], LOCATION_X[1], PART1_ROW_Y[1])
    yield ("contract_no", CONTRACT_NO_X[0], CONTRACT_NO_Y[0], CONTRACT_NO_X[1], CONTRACT_NO_Y[1])
    for fid, (x0, x1), (y0, y1) in NAMEPLATE_FIELDS:
        yield fid, x0, y0, x1, y1
    for fid, (x0, x1), (y0, y1) in TEST_EQUIP_FIELDS:
        yield fid, x0, y0, x1, y1
    for fid, (x0, x1), (y0, y1) in INSULATION_FIELDS:
        yield fid, x0, y0, x1, y1
    for fid, (x0, x1), (y0, y1) in WINDING_FIELDS:
        yield fid, x0, y0, x1, y1
    for fid, (x0, x1), (y0, y1) in VISUAL_FIELDS:
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
