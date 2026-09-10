#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
One-time generator for EHT_and_RTD_Pre-Insulation_Installation_Report_TEMPLATE.pdf.

REVISION 2 - exact-fidelity rebuild. The user's own words: "I need the
exact template do not edit anything. keep the same design font border
thickness EVERYTHING NEEDS TO STAY THE SAME." Revision 1 (still in git
history) redrew the form from scratch with reportlab shapes/text -
visually similar, but not literally the same image, font, or border
weight as the real scanned form. This revision instead uses the actual
scanned page as the template's background image, with every handwritten
value whited out (see eht_pre_insulation_field_positions.py for exactly
which regions and why) and every printed element - the two company
logos, every label, every ruling line, the exact font the form was
typeset in - left completely untouched, pixel-for-pixel identical to the
real scan. 44 invisible, precisely-positioned AcroForm text fields sit on
top of the blanked writable regions.

Why 44, not 46: building this against the real scan (rather than
redrawing an approximation) surfaced two things Revision 1 got wrong:
  - customer_name/project_name/contract_no/location are PRINTED text on
    the real form (identical on every one of the 19 scanned instances,
    confirmed by inspection) - not hand-filled, so not fillable fields.
    Baked into the background image instead, same precedent as
    eht_removal/eht_rtd's own header rows.
  - The sign-off table's "Yanda Representative"/"Client Representative"
    columns are NOT signature-only - the real form has a handwritten NAME
    there too (e.g. "Dana Eshleyah"), which Revision 1's schema omitted.
    Added as yanda_rep_name/client_rep_name.
That's 46 - 4 header fields + 2 name fields = 44.

The background image (assets/eht_pre_insulation_background.jpg) was
produced from a clean 300 DPI render of page 3 of
Sharp_Scanner_20260908_123001_1.pdf (reference_material/EHT-004_scanned_samples/)
with every one of the 44 writable regions (plus a handful of small
supplementary patches for handwriting that bled slightly past a cell's
measured boundary) painted white - see
eht_pre_insulation_field_positions.py for the exact, individually
measured pixel rectangle for every field (found via horizontal/vertical
ruling-line detection, then visually cross-checked crop by crop), and
EXTRA_CLEANUP_PATCHES for the handwriting-overflow touch-ups. Regenerating
the background from the source scan is a deliberate manual/visual process
(see that module's own docstring) - this script does not redo it; it
just assembles the already-produced background image and the AcroForm
fields into the final template.

Run once:
    python3 build_eht_pre_insulation_template.py
Regenerates EHT_and_RTD_Pre-Insulation_Installation_Report_TEMPLATE.pdf
next to this script.
"""
from pathlib import Path

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from pypdf import PdfReader, PdfWriter

from eht_pre_insulation_field_positions import all_fields, PAGE_H_PX, DPI

HERE = Path(__file__).resolve().parent
OUT_PATH = HERE / "EHT_and_RTD_Pre-Insulation_Installation_Report_TEMPLATE.pdf"
BG_IMAGE = HERE / "assets" / "eht_pre_insulation_background.jpg"

PAGE_W, PAGE_H = letter  # 612 x 792 - US Letter, matching the real scan's proportions
SCALE = DPI / 72.0       # pixels per PDF point at the background image's 300 DPI

# Same inset used when whiting-out the background - keeps every field's
# typing box safely inside the blanked area, never overlapping the
# printed ruling line around it.
PAD_PT = 6 / SCALE

# comments is the only multi-line field; give it a touch more font size
# headroom since it's the only box tall enough to want it.
MULTILINE_FIELDS = {"comments"}


def px_rect_to_pt(x0, y0, x1, y1):
    """Pixel rect (top-left origin, y grows down) -> PDF point rect
    (bottom-left origin, y grows up), inset by PAD_PT on every side."""
    px = x0 / SCALE + PAD_PT
    py = (PAGE_H_PX - y1) / SCALE + PAD_PT
    pw = (x1 - x0) / SCALE - 2 * PAD_PT
    ph = (y1 - y0) / SCALE - 2 * PAD_PT
    return px, py, pw, ph


def build():
    c = canvas.Canvas(str(OUT_PATH), pagesize=letter)
    c.setTitle("EHT & RTD Pre-Insulation Installation Report - YCQE-EHT-004 Rev.0")
    c.drawImage(str(BG_IMAGE), 0, 0, width=PAGE_W, height=PAGE_H)
    # NOTE: `c.acroForm.needAppearances = True` (an earlier version of this
    # line) is a NO-OP - reportlab's AcroForm object has no such real
    # property; it silently sets an unused Python attribute and never
    # writes /NeedAppearances into the PDF at all. Set it for real below,
    # via pypdf, after reportlab has finished writing the file.

    count = 0
    for field_id, x0, y0, x1, y1 in all_fields():
        px, py, pw, ph = px_rect_to_pt(x0, y0, x1, y1)
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

    # Actually set /NeedAppearances true (see note above) - matters most
    # for whoever opens this blank template directly in a PDF viewer
    # (rather than through the app's own fill_pdf(), which already sets
    # this correctly via writer.set_need_appearances_writer()): without
    # it, a strict viewer may not (re)generate a field's on-screen
    # appearance reliably.
    reader = PdfReader(str(OUT_PATH))
    writer = PdfWriter()
    writer.append(reader)
    writer.set_need_appearances_writer(True)
    with open(OUT_PATH, "wb") as fh:
        writer.write(fh)

    print(f"Wrote {OUT_PATH} with {count} fields")


if __name__ == "__main__":
    build()
