#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
One-time generator for
Small_Power_and_Control_Cable_Inspection_and_Test_Record_TEMPLATE.pdf
(YCQE-E&I-113 Rev.0) - the Electrical side's sixth form, and the second
of three new forms from the user's second uploaded scan bundle
(spcc_itrs.pdf - see transformer_test's own build script for the first).

Same "real scanned page as the background image" approach as
build_transformer_test_template.py (see that module's own docstring for
why - exact design/font/border fidelity, at the user's explicit request).
One real difference from transformer_test: this form's handwriting is
black/near-neutral ink (confirmed by direct RGB sampling - R≈G≈B on
every sample checked), not blue, so the ink-color whiteout technique
transformer_test uses doesn't apply here - every field's whiteout is a
directly-measured rectangle instead (see
small_power_cable_field_positions.py for the measurement notes,
including this scan's own ~1.4 degree rotation, which threw off an early
measurement pass and is worth reading before touching this template
again).

This script itself only assembles the already-produced background image
(assets/small_power_cable_background.jpg) and the AcroForm fields; it
does not repeat the whiteout step.

Run once:
    python3 build_small_power_cable_template.py
Regenerates Small_Power_and_Control_Cable_Inspection_and_Test_Record_TEMPLATE.pdf
next to this script.
"""
from pathlib import Path

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from pypdf import PdfReader, PdfWriter

from small_power_cable_field_positions import all_fields, PAGE_H_PX, DPI

HERE = Path(__file__).resolve().parent
OUT_PATH = HERE / "Small_Power_and_Control_Cable_Inspection_and_Test_Record_TEMPLATE.pdf"
BG_IMAGE = HERE / "assets" / "small_power_cable_background.jpg"

PAGE_W, PAGE_H = letter
SCALE = DPI / 72.0
PAD_PT = 5 / SCALE

MULTILINE_FIELDS = {"remarks"}


def px_rect_to_pt(x0, y0, x1, y1):
    px = x0 / SCALE + PAD_PT
    py = (PAGE_H_PX - y1) / SCALE + PAD_PT
    pw = (x1 - x0) / SCALE - 2 * PAD_PT
    ph = (y1 - y0) / SCALE - 2 * PAD_PT
    return px, py, pw, ph


def build():
    c = canvas.Canvas(str(OUT_PATH), pagesize=letter)
    c.setTitle("Small Power and Control Cable Inspection & Test Record - YCQE-E&I-113 Rev.0")
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
