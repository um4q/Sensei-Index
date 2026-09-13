# -*- coding: utf-8 -*-
"""Precisely measured field rects for the Transformer Test Record
(YCQE-E&I-112 Rev. 0).

REVISION 5 (built from the user's own real, official source PDF): this
form is no longer reconstructed from a hand-filled scan sample at all -
see build_transformer_test_template.py's own docstring for why (in short:
the user provided the real, blank, digitally-authored source PDF, which
needs no whiteout of any kind since there is no handwriting on it to
remove). All coordinates below were read directly off that PDF's own text
and vector-line positions (pypdf/pymupdf get_text("words") /
get_drawings()) - not measured from a raster image, so there is no
DPI/pixel-to-point conversion anywhere in this module: every number here
already IS a PDF point, matching the real source PDF's own 612x792pt
(US Letter) page directly.

All X coordinates and the raw Y constants below (ROW_*_Y, *_ROWS_Y, etc.)
are in the coordinate space PyMuPDF's own get_text()/get_drawings() report
them in: origin TOP-LEFT, y grows DOWNWARD (image/device space - NOT the
PDF's own native bottom-left-origin space, a real gotcha this module's own
REVISION 5 rewrite got bitten by once already: every field landed roughly
one row too high, because reportlab's acroForm.textfield() - and PDF
annotation rects generally - expect true bottom-left-origin coordinates).
all_fields() below is the ONE place that converts each field's own y0/y1
(top-down) into real PDF y-coordinates (PAGE_H_PT - y, with the pair
swapped since the conversion also flips which one is numerically smaller)
before yielding - every constant above that point in this file stays in
PyMuPDF's own reporting convention, matching how it was actually measured.

Two cosmetic bits of leftover legacy text exist on the real source PDF,
both fully covered by newer text drawn on top of them in the same spot
(confirmed via direct inspection - not a rendering bug): "Job No.:" behind
the visible "Contract #:" label, and "Integral QA Representative:" behind
the visible "Yanda QA Representative:" label. Neither affects any field
rect below - both are pure label text, never a value zone.
"""

PAGE_W_PT = 612.0
PAGE_H_PT = 792.0

TABLE_LEFT = 41.6
TABLE_RIGHT = 570.6

# --------------------------------------------------------- PART 1 - Project
PROJECT_X = (80.0, 260.0)
LOCATION_X = (304.0, 470.0)
CONTRACT_NO_X = (514.0, 567.0)
PART1_ROW_Y = (119.9, 134.8)

# ------------------------------------------------- PART 2 - Nameplate Data
TAG_X = (67.0, 218.0)
TRANSFORMER_TYPE_DRY_X = (294.0, 306.0)
TRANSFORMER_TYPE_WET_X = (326.0, 338.0)
SYSTEM_X = (434.0, 567.0)
ROW_TAG_Y = (149.0, 163.2)
# Narrower than ROW_TAG_Y - the checkbox glyph's own real rect (measured
# off the page's vector drawing ops) is only ~7pt tall, centered a couple
# points above the row's text baseline.
TRANSFORMER_TYPE_CHECKBOX_Y = (151.0, 161.0)

MAKE_X = (73.0, 218.0)
MODEL_X = (252.0, 396.0)
SERIAL_NUMBER_X = (460.0, 567.0)
ROW_MAKE_Y = (163.2, 177.4)

PRIMARY_VOLTAGE_X = (114.0, 218.0)
SECONDARY_VOLTAGE_X = (301.0, 396.0)
PHASE_X = (430.0, 567.0)
ROW_VOLTAGE_Y = (177.4, 191.6)

PRIMARY_FLA_X = (101.0, 173.0)
SECONDARY_FLA_X = (243.0, 306.0)
RATING_KVA_X = (366.0, 439.0)
TEMPERATURE_RISE_X = (517.0, 567.0)
ROW_FLA_Y = (191.6, 205.8)

PRIMARY_CONNECTION_X = (129.0, 306.0)
SECONDARY_CONNECTION_X = (404.0, 567.0)
ROW_CONNECTION_Y = (205.8, 220.0)

# The real form packs "Primary Tap Setting: ____ % ____ Volts" with two
# blanks as literal underline runs of underscore characters - these rects
# match those underline runs exactly (read off their own word bboxes),
# not a label-inset guess.
PRIMARY_TAP_PERCENT_X = (127.7, 163.2)
PRIMARY_TAP_VOLTS_X = (174.7, 219.1)
AREA_CLASSIFICATION_X = (389.0, 567.0)
ROW_TAP_Y = (220.0, 234.2)

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
TEST_EQUIP_ROWS_Y = [(248.4, 270.5), (270.5, 292.6)]
TEST_EQUIP_COLS = [
    ("make", (73.0, 174.0)),
    ("model", (208.0, 307.0)),
    ("asset_serial", (396.0, 439.0)),
    ("calibrated_on", (502.0, 567.0)),
]
TEST_EQUIP_FIELDS = []
for _row_n, _row_y in enumerate(TEST_EQUIP_ROWS_Y, start=1):
    for _col_id, _col_x in TEST_EQUIP_COLS:
        TEST_EQUIP_FIELDS.append((f"test_equip_{_row_n}_{_col_id}", _col_x, _row_y))

# ------------------------------------------------- PART 4 - Insulation Resistance
# Column boundaries read directly off the table's own vertical ruling
# lines (get_drawings()), inset a few points from each - blank data cells,
# no packed label, so no risk of clipping anything.
INSUL_ROWS_Y = [(336.6, 351.5), (351.5, 366.4)]
INSUL_COLS = [
    ("primary_to_ground", (45.0, 134.0)),
    ("secondary_to_ground", (141.0, 230.0)),
    ("primary_to_secondary", (237.0, 327.0)),
    ("test_voltage", (334.0, 423.0)),
    ("ambient", (430.0, 519.0)),
    ("initial", (526.0, 567.0)),
]
INSULATION_FIELDS = []
for _row_n, _row_y in enumerate(INSUL_ROWS_Y, start=1):
    for _col_id, _col_x in INSUL_COLS:
        INSULATION_FIELDS.append((f"insulation_row_{_row_n}_{_col_id}", _col_x, _row_y))

# ---------------------------------------------------- Winding Resistance
WINDING_ROW_Y = (396.2, 411.1)
WINDING_COLS = [
    ("h1", (45.0, 104.0)), ("h2", (111.0, 169.0)), ("h3", (176.0, 234.0)),
    ("x1", (241.0, 300.0)), ("x2", (307.0, 365.0)), ("x3", (372.0, 431.0)),
    ("ambient", (438.0, 519.0)), ("initial", (526.0, 567.0)),
]
WINDING_FIELDS = [(f"winding_{_id}", _x, WINDING_ROW_Y) for _id, _x in WINDING_COLS]

# ------------------------------------------------------- PART 5 - Visual Inspection
# "Initial/NA" is a column header (own row, above item 1) - each item
# row's value cell is one wide blank column on the right, no label-inset
# needed. Row boundaries read directly off the table's own horizontal
# ruling lines.
VISUAL_ROWS_Y = [444.2, 459.1, 474.0, 488.9, 503.8, 518.6, 533.6, 548.5, 563.4]
VISUAL_INITIAL_X = (527.0, 567.0)
VISUAL_FIELDS = []
for _n in range(8):
    y0, y1 = VISUAL_ROWS_Y[_n], VISUAL_ROWS_Y[_n + 1]
    VISUAL_FIELDS.append((f"vis_item_{_n + 1}_initial", VISUAL_INITIAL_X, (y0, y1)))

# --------------------------------------------------------------- PART 6 - Remarks
# Two blank ruled lines on the real form - modeled as one multiline field
# spanning both, same convention every other Electrical form's own
# unlabeled blank grid uses.
REMARKS_BOX = ("remarks", (45.0, 567.0), (577.6, 607.4))

# ------------------------------------------------------------------- PART 7 Sign-off
# Underline-based (no ruled cell box) - value zones are each underline
# run's own exact word bbox, not a label-inset estimate.
SIGNOFF_YANDA_NAME_X = (89.0, 271.5)
SIGNOFF_YANDA_DATE_X = (89.0, 271.5)
SIGNOFF_YANDA_SIGNATURE_X = (89.0, 271.2)
SIGNOFF_CLIENT_NAME_X = (357.5, 539.7)
SIGNOFF_CLIENT_DATE_X = (357.5, 539.7)
SIGNOFF_CLIENT_SIGNATURE_X = (357.0, 539.4)
SIGNOFF_NAME_Y = (642.2, 653.7)
SIGNOFF_DATE_Y = (657.3, 668.8)
SIGNOFF_SIGNATURE_Y = (672.5, 684.0)

SIGNOFF_FIELDS = [
    ("yanda_rep_name", SIGNOFF_YANDA_NAME_X, SIGNOFF_NAME_Y),
    ("yanda_rep_date", SIGNOFF_YANDA_DATE_X, SIGNOFF_DATE_Y),
    ("yanda_rep_signature", SIGNOFF_YANDA_SIGNATURE_X, SIGNOFF_SIGNATURE_Y),
    ("client_rep_name", SIGNOFF_CLIENT_NAME_X, SIGNOFF_NAME_Y),
    ("client_rep_date", SIGNOFF_CLIENT_DATE_X, SIGNOFF_DATE_Y),
    ("client_rep_signature", SIGNOFF_CLIENT_SIGNATURE_X, SIGNOFF_SIGNATURE_Y),
]


def _to_pdf_y(y0_topdown, y1_topdown):
    """Converts a (top,bottom) pair in PyMuPDF's top-down reporting
    convention into a real (y0,y1) PDF-space rect, bottom-left origin -
    see this module's own docstring for why this conversion has to exist
    at all. The pair swaps: PyMuPDF's smaller "top" value becomes the
    PDF's LARGER y (further from the bottom-left origin)."""
    return PAGE_H_PT - y1_topdown, PAGE_H_PT - y0_topdown


def all_fields():
    raw = [
        ("project", PROJECT_X, PART1_ROW_Y),
        ("location", LOCATION_X, PART1_ROW_Y),
        ("contract_no", CONTRACT_NO_X, PART1_ROW_Y),
        *NAMEPLATE_FIELDS,
        *TEST_EQUIP_FIELDS,
        *INSULATION_FIELDS,
        *WINDING_FIELDS,
        *VISUAL_FIELDS,
        REMARKS_BOX,
        *SIGNOFF_FIELDS,
    ]
    for fid, (x0, x1), (y0, y1) in raw:
        py0, py1 = _to_pdf_y(y0, y1)
        yield fid, x0, py0, x1, py1


if __name__ == "__main__":
    fields = list(all_fields())
    print(f"Total fields: {len(fields)}")
    for f in fields:
        print(f)
