#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
One-time generator for
General_Electrical_Equipment_Installation_and_Test_Report_TEMPLATE.pdf
(YCQE-E&I-013 Rev.0) - the Electrical side's seventh form, and the third
and most complex of the new forms from the user's second uploaded scan
bundle (spcc_itrs.pdf - see transformer_test's and small_power_cable's
own build scripts for the other two).

Same "real scanned page as the background image" approach as every other
form built this way (see build_eht_pre_insulation_template.py's own
docstring for why - exact design/font/border fidelity, at the user's
explicit request). This form's handwriting is a MIX of blue and black
ink (confirmed by a page-wide ink-color pass that left almost every
field untouched, unlike transformer_test's own fully-blue pen) - not
worth splitting into two techniques for one form, so every field uses
rectangle whiteout, same as small_power_cable.

This form was also the hardest of the three to measure - a wide (250px
grid) first pass got several sections badly wrong (an entire header row
of field labels erased, the 18-item Verifications table's row heights
off by a full row from a misjudged header boundary, the Torqueing Log's
own column x-positions off by 100-200px) - every one of those was only
caught by combining a quantitative "is this field's own interior fully
white" check (which stayed green throughout - a reminder that a clean
value zone alone does NOT mean a label survived) with a second
"halo" check comparing dark-pixel density just OUTSIDE each field's
rect, before vs after whiteout, and finally fine (25px-or-tighter)
gridline crops read from actual pixel coordinates for anything the halo
check flagged. See general_equip_install_field_positions.py's own
docstring for the field-by-field specifics.

This script itself only assembles the already-produced background image
(assets/general_equip_install_background.jpg) and the AcroForm fields;
it does not repeat the whiteout step.

Run once:
    python3 build_general_equip_install_template.py
Regenerates General_Electrical_Equipment_Installation_and_Test_Report_TEMPLATE.pdf
next to this script.
"""
from pathlib import Path

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from pypdf import PdfReader, PdfWriter

from general_equip_install_field_positions import all_fields, PAGE_H_PX, DPI

HERE = Path(__file__).resolve().parent
OUT_PATH = HERE / "General_Electrical_Equipment_Installation_and_Test_Report_TEMPLATE.pdf"
BG_IMAGE = HERE / "assets" / "general_equip_install_background.jpg"

PAGE_W, PAGE_H = letter
SCALE = DPI / 72.0
PAD_PT = 5 / SCALE

MULTILINE_FIELDS = {"comments", "equipment_resistance_testing_notes",
                     "equipment_insulation_resistance_testing_notes"}


def px_rect_to_pt(x0, y0, x1, y1):
    px = x0 / SCALE + PAD_PT
    py = (PAGE_H_PX - y1) / SCALE + PAD_PT
    pw = (x1 - x0) / SCALE - 2 * PAD_PT
    ph = (y1 - y0) / SCALE - 2 * PAD_PT
    return px, py, pw, ph


def build():
    c = canvas.Canvas(str(OUT_PATH), pagesize=letter)
    c.setTitle("General Electrical Equipment Installation & Test Report - YCQE-E&I-013 Rev.0")
    c.drawImage(str(BG_IMAGE), 0, 0, width=PAGE_W, height=PAGE_H)

    count = 0
    for field_id, x0, y0, x1, y1 in all_fields():
        px, py, pw, ph = px_rect_to_pt(x0, y0, x1, y1)
        if pw <= 0 or ph <= 0:
            raise ValueError(f"Degenerate rect for {field_id}: {(x0, y0, x1, y1)}")
        multiline = field_id in MULTILINE_FIELDS
        c.acroForm.textfield(
            name=field_id, tooltip=field_id, x=px, y=py, width=pw, height=ph,
            borderStyle=None, borderWidth=0, fillColor=None,
            forceBorder=False, fontSize=8 if multiline else 7,
            fieldFlags="multiline" if multiline else "",
        )
        count += 1

    c.showPage()
    c.save()

    reader = PdfReader(str(OUT_PATH))
    writer = PdfWriter()
    writer.append(reader)
    writer.set_need_appearances_writer(True)
    with open(OUT_PATH, "wb") as fh:
        writer.write(fh)

    print(f"Wrote {OUT_PATH} with {count} fields")


if __name__ == "__main__":
    build()
