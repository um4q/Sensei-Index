# -*- coding: utf-8 -*-
"""Precisely measured field rects for the General Electrical Equipment
Installation & Test Report (YCQE-E&I-013 Rev.0).

REVISION 3 (built from the user's own real, official source document):
this form is no longer reconstructed from a hand-filled scan sample -
the user provided the real source as a Word document (.docx), converted
to PDF via LibreOffice (see build_general_equip_install_template.py's own
docstring for the conversion + build pipeline). All coordinates below
were read directly off that converted PDF's own text and vector-line
positions (pymupdf get_text("words") / get_drawings()) - not measured
from a raster image.

Two important facts about this specific source, both different from
transformer_test's/small_power_cable's own real sources:

1. The converted PDF is TWO PAGES, not one - the Word document's own
   content (Torqueing Log rows 3-5, Comments, and the Sign-Off block)
   spills onto a second page under LibreOffice's rendering (a
   pagination/margin difference from whatever produced the DOCX
   originally, not a content difference - confirmed no text/data is lost,
   only where the page break lands). Every field below is tagged with
   which page (0 or 1) it belongs on; build_general_equip_install_
   template.py merges each field's own overlay onto the matching page.
2. Unlike transformer_test/small_power_cable, this source is NOT
   perfectly blank - "Location" has real sample text ("Module Yard")
   printed directly into the page content (not a fillable field's
   default value - this document has no AcroForm fields of its own at
   all, unlike small_power_cable's real source). The cell is narrow
   enough that "Module Yard" wraps across 2 lines, and - critically -
   the printed "LOCATION:" LABEL shares that exact same cell, sitting on
   line 1 immediately to the left of "Module" (line 2, where "Yard"
   wraps to, is flush with the cell's own left edge - the same x
   position the label occupies one line up). A single bounding-box
   whiteout around the whole value therefore erases the real "LOCATION:"
   label too - confirmed by an earlier build attempt that did exactly
   that (caught by visual inspection: the label was simply gone).
   LOCATION_WHITEOUT_LINE1/LINE2 below are two separate, narrower
   rectangles read directly off this cell's own ruling-line borders
   (get_drawings()) and each line's own word boxes (get_text("words")) -
   LINE1 covers only "Module" (x to the right of "LOCATION:"'s own right
   edge), LINE2 covers only "Yard" (the full cell width, since line 2 has
   no label on it at all) - so the label itself is never touched. This is
   the only whiteout this build needs anywhere on the document - every
   other field's value zone was confirmed blank by direct text-extraction
   inspection.

All coordinates are in the coordinate space PyMuPDF's own
get_text()/get_drawings() report them in: origin TOP-LEFT, y grows
DOWNWARD - NOT the PDF's native bottom-left-origin space. all_fields()
converts each field's own y0/y1 to true PDF coordinates before yielding,
same fix (and same reasoning) as transformer_test_field_positions.py's
own all_fields() - see that module's docstring for the full story of how
this was found.
"""

PAGE_W_PT = 612.0
PAGE_H_PT = 792.0

# The one spot on the whole document with real pre-filled sample text
# instead of a blank cell - "LOCATION: Module Yard" wraps across 2 lines
# within its own narrow header cell, with the "LOCATION:" label itself
# sharing line 1 (see docstring above for why this is 2 rects, not 1).
# Real cell borders (get_drawings()): left x=481.9, right x~581.9,
# top y=82.3, bottom y=107.8. Real word boxes (get_text("words")):
# "LOCATION:" x487.3-536.4 y88.9-98.2; "Module" x539.2-572.2 y88.9-98.2;
# "Yard" x487.3-507.6 y98.2-107.5.
LOCATION_WHITEOUT_LINE1 = (537.0, 82.5, 581.0, 98.3)  # (x0,y0,x1,y1), top-down, page 0 - "Module" only
LOCATION_WHITEOUT_LINE2 = (483.0, 98.3, 581.0, 107.6)  # (x0,y0,x1,y1), top-down, page 0 - "Yard" only (no label on this line)
LOCATION_WHITEOUT_BOXES = (LOCATION_WHITEOUT_LINE1, LOCATION_WHITEOUT_LINE2)

# ---------------------------------------------------------------- Header block
LOCATION_X = (539.0, 576.0)
LOCATION_Y = (88.9, 107.5)

ROW_TAG_Y = (124.0, 134.5)
TAG_NUMBER_X = (92.0, 206.0)
MANUFACTURER_X = (293.0, 348.0)
MODEL_NUMBER_X = (406.0, 476.0)
SYSTEM_NUMBER_X = (539.0, 576.0)

ROW_SERIAL_Y = (136.4, 146.9)
SERIAL_NUMBER_X = (107.0, 149.0)
VOLTAGE_X = (207.0, 225.0)
FREQ_X = (269.0, 292.0)
PHASE_X = (333.0, 338.0)
AMPS_X = (388.0, 420.0)
AREA_CLASS_OF_EQUIP_X = (540.0, 576.0)

ROW_REFDWG_Y = (148.6, 159.1)
REF_DWG_NUMBER_X = (123.0, 348.0)
KVA_X = (381.0, 420.0)
AREA_CLASS_X = (493.0, 576.0)

ROW_TESTEQUIP_Y = (160.4, 171.3)
TEST_EQUIP_MODEL_NUMBER_X = (174.0, 225.0)
TEST_EQUIP_SERIAL_NUMBER_X = (349.0, 420.0)
CAL_DUE_X = (478.0, 576.0)

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
# Column boundaries read directly off the table's own vertical ruling
# lines/segments. Row boundaries read directly off the table's own
# horizontal ruling lines - each item's own row is however tall its own
# (possibly multi-line-wrapped) description text needs.
YES_INITIAL_X = (515.0, 540.0)
NA_INITIAL_X = (547.0, 573.0)
TASK_ROWS_Y = [203.5, 224.5, 266.8, 287.9, 299.2, 320.2, 341.2, 362.2, 383.4,
               404.4, 415.6, 436.6, 457.8, 478.8, 521.2, 542.2, 563.2, 574.5, 585.8]
TASK_FIELDS = []
for _n in range(18):
    y0, y1 = TASK_ROWS_Y[_n], TASK_ROWS_Y[_n + 1]
    TASK_FIELDS.append((f"task_{_n + 1}_yes", YES_INITIAL_X, (y0, y1)))
    TASK_FIELDS.append((f"task_{_n + 1}_na", NA_INITIAL_X, (y0, y1)))

# --------------------------------------------------------- Section N/A flags
# Small checkbox glyphs, each positioned a few points left of its own
# printed "N/A" text (measured directly - none of these render as a
# vector rect PyMuPDF's get_drawings() can find, unlike every ruled-table
# border on this page, so there's no ruling-line boundary to read for
# these specifically).
ELECTRICAL_EQUIPMENT_TESTING_NA_X = (378.0, 393.0)
ELECTRICAL_EQUIPMENT_TESTING_NA_Y = (586.1, 596.6)
EQUIPMENT_RESISTANCE_TESTING_NA_X = (378.0, 393.0)
EQUIPMENT_RESISTANCE_TESTING_NA_Y = (617.0, 627.5)
EQUIPMENT_INSULATION_RESISTANCE_TESTING_NA_X = (419.0, 434.0)
EQUIPMENT_INSULATION_RESISTANCE_TESTING_NA_Y = (653.8, 664.3)
TORQUEING_LOG_NA_X = (345.0, 360.0)
TORQUEING_LOG_NA_Y = (700.2, 710.7)
# Comments N/A is on page 1 (see COMMENTS_NA_PAGE below).
COMMENTS_NA_X = (324.0, 339.0)
COMMENTS_NA_Y = (78.2, 87.5)

# ------------------------------------------------------ Unlabeled blank grids
# No printed column headers anywhere on the real source for either of
# these two sections (confirmed by inspection) - each modeled as one
# multiline field spanning the whole blank grid area, same as this app's
# other unlabeled-grid forms.
EQUIPMENT_RESISTANCE_TESTING_NOTES_X = (54.0, 572.0)
EQUIPMENT_RESISTANCE_TESTING_NOTES_Y = (616.8, 640.8)
EQUIPMENT_INSULATION_RESISTANCE_TESTING_NOTES_X = (54.0, 572.0)
EQUIPMENT_INSULATION_RESISTANCE_TESTING_NOTES_Y = (674.5, 700.0)

# ------------------------------------------------------------- Torqueing Log
# Column boundaries read off page 1's own vertical ruling lines (cleaner
# than page 0's - the header row's own checkbox glyphs there visually
# overlap a couple of header words, splitting them into extra line
# fragments PyMuPDF sees as more text lines, but none of that affects
# these column x-positions, all read from real ruling-line geometry, not
# text). Rows 1-2 are the last content on page 0; rows 3-5 continue at
# the top of page 1 - same table, split by the page break.
TORQUEING_COLS = [
    ("cond_id", (54.0, 166.0)), ("location", (173.0, 272.0)),
    ("bolt_grade", (278.0, 308.0)), ("bolt_size", (314.0, 351.0)),
    ("torque_value", (357.0, 408.0)), ("torque_marked", (414.0, 451.0)),
    ("torque_by", (457.0, 508.0)), ("date", (515.0, 573.0)),
]
TORQUEING_ROWS = [
    (1, (749.0, 761.7), 0), (2, (761.7, 774.5), 0),
    (3, (35.2, 48.0), 1), (4, (48.0, 60.7), 1), (5, (60.7, 74.0), 1),
]
TORQUEING_FIELDS = []  # (field_id, x, y, page)
for _row_n, _row_y, _page in TORQUEING_ROWS:
    for _col_id, _col_x in TORQUEING_COLS:
        TORQUEING_FIELDS.append((f"torqueing_row_{_row_n}_{_col_id}", _col_x, _row_y, _page))

# ------------------------------------------------------------------ Comments
# Page 1 - the blank row directly below the "COMMENTS" header bar.
COMMENTS_X = (54.0, 572.0)
COMMENTS_Y = (88.3, 105.7)

# ------------------------------------------------------------------ Sign-off
# Page 1 - column boundaries off that page's own vertical ruling lines,
# row boundaries off its own horizontal ruling lines.
SIGNOFF_NAME_X = (54.0, 220.0)
SIGNOFF_DATE_X = (228.0, 386.0)
SIGNOFF_SIGNATURE_X = (393.0, 572.0)
SIGNOFF_YANDA_ROW_Y = (120.0, 135.5)
SIGNOFF_CLIENT_ROW_Y = (150.0, 165.5)

SIGNOFF_FIELDS = [
    ("yanda_rep_name", SIGNOFF_NAME_X, SIGNOFF_YANDA_ROW_Y),
    ("yanda_rep_date", SIGNOFF_DATE_X, SIGNOFF_YANDA_ROW_Y),
    ("yanda_rep_signature", SIGNOFF_SIGNATURE_X, SIGNOFF_YANDA_ROW_Y),
    ("client_rep_name", SIGNOFF_NAME_X, SIGNOFF_CLIENT_ROW_Y),
    ("client_rep_date", SIGNOFF_DATE_X, SIGNOFF_CLIENT_ROW_Y),
    ("client_rep_signature", SIGNOFF_SIGNATURE_X, SIGNOFF_CLIENT_ROW_Y),
]


def _to_pdf_y(y0_topdown, y1_topdown):
    return PAGE_H_PT - y1_topdown, PAGE_H_PT - y0_topdown


def all_fields():
    """Yields (field_id, x0, y0, x1, y1, page) - note the extra `page`
    element (0 or 1) this module's own all_fields() has that
    transformer_test/small_power_cable's don't need, since this is the
    one Electrical form whose real source spans 2 pages."""
    page0_raw = [
        ("location", LOCATION_X, LOCATION_Y),
        *HEADER_FIELDS,
        *TASK_FIELDS,
        ("electrical_equipment_testing_na", ELECTRICAL_EQUIPMENT_TESTING_NA_X,
         ELECTRICAL_EQUIPMENT_TESTING_NA_Y),
        ("equipment_resistance_testing_na", EQUIPMENT_RESISTANCE_TESTING_NA_X,
         EQUIPMENT_RESISTANCE_TESTING_NA_Y),
        ("equipment_insulation_resistance_testing_na",
         EQUIPMENT_INSULATION_RESISTANCE_TESTING_NA_X,
         EQUIPMENT_INSULATION_RESISTANCE_TESTING_NA_Y),
        ("torqueing_log_na", TORQUEING_LOG_NA_X, TORQUEING_LOG_NA_Y),
        ("equipment_resistance_testing_notes", EQUIPMENT_RESISTANCE_TESTING_NOTES_X,
         EQUIPMENT_RESISTANCE_TESTING_NOTES_Y),
        ("equipment_insulation_resistance_testing_notes",
         EQUIPMENT_INSULATION_RESISTANCE_TESTING_NOTES_X,
         EQUIPMENT_INSULATION_RESISTANCE_TESTING_NOTES_Y),
    ]
    for fid, (x0, x1), (y0, y1) in page0_raw:
        py0, py1 = _to_pdf_y(y0, y1)
        yield fid, x0, py0, x1, py1, 0
    for fid, (x0, x1), (y0, y1), page in TORQUEING_FIELDS:
        py0, py1 = _to_pdf_y(y0, y1)
        yield fid, x0, py0, x1, py1, page

    page1_raw = [
        ("comments_na", COMMENTS_NA_X, COMMENTS_NA_Y),
        ("comments", COMMENTS_X, COMMENTS_Y),
        *SIGNOFF_FIELDS,
    ]
    for fid, (x0, x1), (y0, y1) in page1_raw:
        py0, py1 = _to_pdf_y(y0, y1)
        yield fid, x0, py0, x1, py1, 1


if __name__ == "__main__":
    fields = list(all_fields())
    print(f"Total fields: {len(fields)}")
    for f in fields:
        print(f)
