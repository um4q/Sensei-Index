#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
One-time generator for Transformer_Test_Record_TEMPLATE.pdf
(YCQE-E&I-112 Rev. 0).

REVISION 5: built directly from the user's own real, official source PDF
(assets/transformer_test_source.pdf) instead of a hand-filled scan sample.
That source PDF is genuinely blank - a digitally-authored form, not a
scan - so there is no handwriting to whiteout at all: this script takes
the real page's own content untouched and merges a transparent overlay of
invisible AcroForm text fields on top of it (reportlab draws the overlay
on its own blank page - no background image is drawn anywhere - then
pypdf merges that single page onto the real source page, keeping every
pixel of the real form's own vector content/fonts/logos intact
underneath). Every field rect comes from
transformer_test_field_positions.py, itself read directly off the source
PDF's own text and ruling-line positions - see that module's own
docstring.

Run once:
    python3 build_transformer_test_template.py
Regenerates Transformer_Test_Record_TEMPLATE.pdf next to this script.
"""
import io
from pathlib import Path

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from pypdf import PdfReader, PdfWriter
from pypdf.generic import ArrayObject, BooleanObject, DictionaryObject, NameObject, TextStringObject

from transformer_test_field_positions import all_fields, PAGE_W_PT, PAGE_H_PT

HERE = Path(__file__).resolve().parent
OUT_PATH = HERE / "Transformer_Test_Record_TEMPLATE.pdf"
SRC_PATH = HERE / "assets" / "transformer_test_source.pdf"

MULTILINE_FIELDS = {"remarks"}


def build_fields_overlay():
    """A single blank page with nothing but invisible AcroForm text field
    widgets on it, at the exact same coordinates the real source PDF's own
    page uses (both are 612x792pt US Letter) - reportlab's own page,
    completely separate from the real source page, merged onto it
    afterward so none of the real page's own content is ever redrawn."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    count = 0
    for field_id, x0, y0, x1, y1 in all_fields():
        w, h = x1 - x0, y1 - y0
        if w <= 0 or h <= 0:
            raise ValueError(f"Degenerate rect for {field_id}: {(x0, y0, x1, y1)}")
        multiline = field_id in MULTILINE_FIELDS
        c.acroForm.textfield(
            name=field_id, tooltip=field_id, x=x0, y=y0, width=w, height=h,
            borderStyle=None, borderWidth=0, fillColor=None,
            forceBorder=False, fontSize=8 if multiline else 7,
            fieldFlags="multiline" if multiline else "",
        )
        count += 1
    c.showPage()
    c.save()
    buf.seek(0)
    return buf, count


def build_acroform_catalog(writer):
    """merge_page() brings the overlay's Widget annotations onto page 0's
    own /Annots array, but it never touches the document CATALOG's own
    /AcroForm entry - the source PDF had none to begin with (it has no
    fields of its own), so nothing here creates one automatically. Without
    it, a real PDF viewer has no top-level index of "these are this
    document's form fields", even though the widgets themselves are
    present on the page. Build it by collecting every Widget annotation
    now on page 0."""
    fields = ArrayObject()
    for annot in writer.pages[0]["/Annots"]:
        obj = annot.get_object()
        if obj.get("/Subtype") == "/Widget":
            fields.append(annot)
    acro = DictionaryObject({
        NameObject("/Fields"): fields,
        NameObject("/NeedAppearances"): BooleanObject(True),
    })
    writer._root_object[NameObject("/AcroForm")] = acro
    return acro


def ensure_default_resources(writer):
    acro = writer._root_object["/AcroForm"]
    helv = DictionaryObject({
        NameObject("/Type"): NameObject("/Font"),
        NameObject("/Subtype"): NameObject("/Type1"),
        NameObject("/BaseFont"): NameObject("/Helvetica"),
        NameObject("/Encoding"): NameObject("/WinAnsiEncoding"),
    })
    helv_ref = writer._add_object(helv)
    font_dict = DictionaryObject({NameObject("/Helv"): helv_ref})
    dr = DictionaryObject({NameObject("/Font"): font_dict})
    acro[NameObject("/DR")] = dr
    acro[NameObject("/DA")] = TextStringObject("/Helv 7 Tf 0 g")


def build():
    src_reader = PdfReader(str(SRC_PATH))
    assert (round(float(src_reader.pages[0].mediabox.width)) == round(PAGE_W_PT)
            and round(float(src_reader.pages[0].mediabox.height)) == round(PAGE_H_PT)), \
        "Source PDF page size doesn't match transformer_test_field_positions.py's own assumption"

    overlay_buf, count = build_fields_overlay()
    overlay_reader = PdfReader(overlay_buf)

    writer = PdfWriter()
    writer.append(src_reader)
    # merge_page draws the overlay's content (the invisible field widgets'
    # own annotations come along too, via pypdf's merge) ON TOP of page 0's
    # existing real content, leaving that content itself untouched.
    writer.pages[0].merge_page(overlay_reader.pages[0])

    build_acroform_catalog(writer)
    ensure_default_resources(writer)
    writer.set_need_appearances_writer(True)
    with open(OUT_PATH, "wb") as fh:
        writer.write(fh)

    print(f"Wrote {OUT_PATH} with {count} fields")


if __name__ == "__main__":
    build()
