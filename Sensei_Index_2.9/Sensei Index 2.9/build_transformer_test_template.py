#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
One-time generator for Transformer_Test_Record_TEMPLATE.pdf (YCQE-E&I-112
Rev. 0) - the Electrical side's fifth form, and the first of three new
forms from the user's second uploaded scan bundle (spcc_itrs.pdf, a
14-page mix of hand-filled Yanda ITR forms - see this module's own
history for the other two, general_equip_install and small_power_cable).

Same "real scanned page as the background image" approach as
build_eht_pre_insulation_template.py (see that module's own docstring for
why - exact design/font/border fidelity, at the user's explicit request:
"DO NOT CHANGE THE DESIGN AND TEMPLATE WHATS SO EVER"), with one
methodology change worth calling out:

REVISION HISTORY (this form specifically):
  - Attempt 1 whited out each field's full ruled CELL - wrong the moment
    a cell packs "Label: value" into one box (nearly every cell on this
    form): the label got erased along with the handwriting.
  - Attempt 2 hand-measured a "value zone" rect per field, inset past
    each printed label (see transformer_test_field_positions.py's own
    revision notes). Better, but pixel-hunting ~24 label-end positions by
    eye against a gridline overlay is slow AND still either clipped a
    label or left a handwriting fragment depending which way the
    estimate erred - the two failure modes pull in opposite directions,
    so there's no single "safe" rect.
  - Attempt 3 (this one) whites out ACTUAL INK PIXELS by color instead of
    an estimated rectangle (see ink_whiteout.py) - this sample's pen is
    blue, cleanly separable from the form's black print by color alone,
    so the whiteout is now driven by where the handwriting actually is,
    not by a guess at where the label ends. 4 fields (project, location,
    contract_no, serial_number) happen to be filled in near-black ink
    indistinguishable from print by color - those get a small,
    empirically-measured manual patch instead (see
    MANUAL_BLACK_INK_PATCHES in the field-positions module).
  This script itself only assembles the already-produced background
  image (assets/transformer_test_background.jpg - see
  build_transformer_test_background.py) and the AcroForm fields; it does
  not repeat the ink-whiteout step.

Run once:
    python3 build_transformer_test_template.py
Regenerates Transformer_Test_Record_TEMPLATE.pdf next to this script.
"""
from pathlib import Path

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from pypdf import PdfReader, PdfWriter

from transformer_test_field_positions import all_fields, PAGE_H_PX, DPI

HERE = Path(__file__).resolve().parent
OUT_PATH = HERE / "Transformer_Test_Record_TEMPLATE.pdf"
BG_IMAGE = HERE / "assets" / "transformer_test_background.jpg"

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
    c.setTitle("Transformer Test Record - YCQE-E&I-112 Rev. 0")
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
