# -*- coding: utf-8 -*-
"""Precisely measured field rects for the EHT-004 Pre-Insulation form,
derived from horizontal/vertical ruling-line detection against a clean
300 DPI render of page 3 of Sharp_Scanner_20260908_123001_1.pdf, then
visually cross-checked against crops of every section.

All coordinates are PIXEL space at 300 DPI, image origin TOP-LEFT
(y grows downward), matching PIL's coordinate convention.
Page is 2550 x 3300 px (= 612 x 792 pt, US Letter, at 300 DPI).

Each entry: (field_id, x0, y0, x1, y1) - x0,y0 = top-left, x1,y1 = bottom-right
of the FULL cell the value lives in (not yet inset for padding - the
consumer insets before both whiting-out and placing the AcroForm field).
"""

PAGE_W_PX = 2550
PAGE_H_PX = 3300
DPI = 300

# ---------------------------------------------------------------- Trace Data
# columns: label1[137,519] value1[519,1425] label2[1425,1833] value2[1833,2421]
# rows:    515.5, 599.0, 681.5, 764.5, 847.0
TRACE_DATA_ROWS_Y = [515.5, 599.0, 681.5, 764.5, 847.0]
TRACE_VALUE1_X = (519, 1425)
TRACE_VALUE2_X = (1833, 2421)
TRACE_DATA_FIELDS = [
    ("trace_number", TRACE_VALUE1_X, (TRACE_DATA_ROWS_Y[0], TRACE_DATA_ROWS_Y[1])),
    ("eht_controller_number", TRACE_VALUE2_X, (TRACE_DATA_ROWS_Y[0], TRACE_DATA_ROWS_Y[1])),
    ("trace_part_number", TRACE_VALUE1_X, (TRACE_DATA_ROWS_Y[1], TRACE_DATA_ROWS_Y[2])),
    ("panel_number", TRACE_VALUE2_X, (TRACE_DATA_ROWS_Y[1], TRACE_DATA_ROWS_Y[2])),
    ("rtds_number", TRACE_VALUE1_X, (TRACE_DATA_ROWS_Y[2], TRACE_DATA_ROWS_Y[3])),
    ("circuit_number", TRACE_VALUE2_X, (TRACE_DATA_ROWS_Y[2], TRACE_DATA_ROWS_Y[3])),
    ("trace_line_number", TRACE_VALUE1_X, (TRACE_DATA_ROWS_Y[3], TRACE_DATA_ROWS_Y[4])),
    ("rev", TRACE_VALUE2_X, (TRACE_DATA_ROWS_Y[3], TRACE_DATA_ROWS_Y[4])),
]

# ------------------------------------------------------------ Checklist (1.0)
# columns: description[141.5,1428.5] results[1428.5,1836.5] comments[1836.5,2425.5]
CHECKLIST_ROWS_Y = [1049.0, 1125.0, 1200.0, 1274.5, 1350.5, 1425.5, 1501.0,
                    1575.5, 1650.5, 1725.5, 1800.5]
RESULTS_X = (1428.5, 1836.5)
COMMENTS_COL_X = (1836.5, 2425.5)
CHECKLIST_FIELDS = []
for _n in range(10):
    y0, y1 = CHECKLIST_ROWS_Y[_n], CHECKLIST_ROWS_Y[_n + 1]
    CHECKLIST_FIELDS.append((f"pre_ins_item_{_n+1}_result", RESULTS_X, (y0, y1)))
    CHECKLIST_FIELDS.append((f"pre_ins_item_{_n+1}_comments", COMMENTS_COL_X, (y0, y1)))

# ------------------------------------------------- Equipment + Megger table
EQUIP_ROW_Y = (1873.0, 1948.5)
EQUIP_FIELDS = [
    # (id, x0,x1 of the VALUE zone - after the printed label, within the cell)
    ("test_equip_model", (545, 955)),
    ("test_equip_serial", (1370, 1718)),
    ("cal_due_date", (2030, 2422)),
]

MEGGER_ROWS_Y = [1948.5, 2035.5, 2122.5, 2212.5]  # 3 rows: 500/1000/2500 VDC
MEGGER_READING_X = (1431.0, 1840.5)
MEGGER_RESULT_X = (2115, 2422)  # value zone after "(Passed/Fail):" label
MEGGER_FIELDS = []
for _i, _v in enumerate(["500", "1000", "2500"]):
    y0, y1 = MEGGER_ROWS_Y[_i], MEGGER_ROWS_Y[_i + 1]
    MEGGER_FIELDS.append((f"megger_{_v}_reading", MEGGER_READING_X, (y0, y1)))
    MEGGER_FIELDS.append((f"megger_{_v}_result", MEGGER_RESULT_X, (y0, y1)))

# --------------------------------------------------------------- Comments
COMMENTS_BOX = ("comments", (137, 2421), (2299.0, 2555.5))

# ---------------------------------------------------------------- Sign-off
SIGNOFF_NAME_X = (148, 878.5)
SIGNOFF_DATE_X = (878.5, 1644.5)
SIGNOFF_SIG_X = (1644.5, 2430.5)
SIGNOFF_YANDA_DATA_Y = (2643.5, 2734.5)
SIGNOFF_CLIENT_DATA_Y = (2825.0, 2915.0)
SIGNOFF_FIELDS = [
    ("yanda_rep_name", SIGNOFF_NAME_X, SIGNOFF_YANDA_DATA_Y),
    ("yanda_rep_date", SIGNOFF_DATE_X, SIGNOFF_YANDA_DATA_Y),
    ("yanda_rep_signature", SIGNOFF_SIG_X, SIGNOFF_YANDA_DATA_Y),
    ("client_rep_name", SIGNOFF_NAME_X, SIGNOFF_CLIENT_DATA_Y),
    ("client_rep_date", SIGNOFF_DATE_X, SIGNOFF_CLIENT_DATA_Y),
    ("client_rep_signature", SIGNOFF_SIG_X, SIGNOFF_CLIENT_DATA_Y),
]


# Small supplementary whiteout-only patches (NOT AcroForm fields) for stray
# handwriting observed bleeding slightly past a value column's boundary
# into label-adjacent blank space, found on a first visual pass of the
# composite. (x0, y0, x1, y1) in pixel space.
EXTRA_CLEANUP_PATCHES = [
    (1660, 660, 1833, 764.5),    # "CB" written in Circuit #: row's label tail
    (519, 512, 1050, 599),       # stray mark, top/bottom of Trace # value cell
    (519, 700, 1425, 764.5),     # stray marks, RTD'(s) # value cell
    (137, 2825, 900, 2915),      # stray mark, Client Representative name row
]


def all_fields():
    """Yields (field_id, x0, y0, x1, y1) in pixel space for every one of the
    44 fillable fields on this form."""
    for fid, (x0, x1), (y0, y1) in TRACE_DATA_FIELDS:
        yield fid, x0, y0, x1, y1
    for fid, (x0, x1), (y0, y1) in CHECKLIST_FIELDS:
        yield fid, x0, y0, x1, y1
    for fid, (x0, x1) in EQUIP_FIELDS:
        yield fid, x0, EQUIP_ROW_Y[0], x1, EQUIP_ROW_Y[1]
    for fid, (x0, x1), (y0, y1) in MEGGER_FIELDS:
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
