#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
One-time generator for
General_Electrical_Equipment_Installation_and_Test_Report_TEMPLATE.pdf
(YCQE-E&I-013 Rev.0).

REVISION 4: built directly from the user's own real, official source
document (a Word .docx converted to PDF via LibreOffice - see
assets/general_equip_install_source.pdf) instead of a hand-filled scan
sample. Same merge-overlay approach as transformer_test's own REVISION 5
rebuild (see build_transformer_test_template.py's docstring for the full
reasoning) - reportlab draws a transparent overlay of invisible AcroForm
text field widgets on its own blank page, then pypdf merges that overlay
onto the real source page, keeping every pixel of the real page's own
content/fonts/logos intact underneath. Every field rect comes from
general_equip_install_field_positions.py, itself read directly off the
source PDF's own text and ruling-line positions - see that module's own
docstring.

Two differences from transformer_test's build script, both explained in
general_equip_install_field_positions.py's own docstring:
  1. This source PDF is TWO PAGES - every field is merged onto whichever
     page it belongs to (all_fields() yields a `page` index per field),
     and the /AcroForm catalog is built by collecting Widget annotations
     from BOTH pages, not just page 0.
  2. This source is not perfectly blank - "Location"'s own value zone has
     real pre-filled sample text ("Module Yard") baked into page 0's own
     content stream (not a fillable field's own default value - this
     document has no AcroForm fields of its own at all). LOCATION_WHITEOUT_BOX
     is whited out (a plain white filled rect, drawn into the page-0
     overlay before it's merged) before the location field is placed on
     top of it - the only whiteout this build needs anywhere on the
     document (every other field's value zone was confirmed blank by
     direct text-extraction inspection).

Run once:
    python3 build_general_equip_install_template.py
Regenerates General_Electrical_Equipment_Installation_and_Test_Report_TEMPLATE.pdf
next to this script.
"""
import io
from pathlib import Path

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.colors import white
from pypdf import PdfReader, PdfWriter
from pypdf.generic import ArrayObject, BooleanObject, DictionaryObject, NameObject, TextStringObject

from general_equip_install_field_positions import (
    all_fields, PAGE_W_PT, PAGE_H_PT, LOCATION_WHITEOUT_BOXES,
)

HERE = Path(__file__).resolve().parent
OUT_PATH = HERE / "General_Electrical_Equipment_Installation_and_Test_Report_TEMPLATE.pdf"
SRC_PATH = HERE / "assets" / "general_equip_install_source.pdf"

MULTILINE_FIELDS = {"comments", "equipment_resistance_testing_notes",
                     "equipment_insulation_resistance_testing_notes"}

NUM_PAGES = 2


def build_fields_overlays():
    """A 2-page overlay document - one page per real source page - each
    with nothing but invisible AcroForm text field widgets on it, at the
    exact same coordinates the real source PDF's own pages use (both are
    612x792pt US Letter) - reportlab's own pages, completely separate
    from the real source pages, merged onto them afterward so none of the
    real pages' own content is ever redrawn. Page 0's overlay also
    carries plain white filled rects over LOCATION_WHITEOUT_BOXES, drawn
    before any field widget, so the real page's own "Module Yard" sample
    text is covered before the location field is placed on top of it - as
    2 separate rects, not 1, so the real "LOCATION:" label (sharing the
    same cell) is never touched. See LOCATION_WHITEOUT_BOXES's own
    docstring for why."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    counts = [0, 0]

    fields_by_page = {0: [], 1: []}
    for field_id, x0, y0, x1, y1, page in all_fields():
        fields_by_page[page].append((field_id, x0, y0, x1, y1))

    for page_num in range(NUM_PAGES):
        if page_num == 0:
            c.setFillColor(white)
            for wx0, wy0_td, wx1, wy1_td in LOCATION_WHITEOUT_BOXES:
                wy0 = PAGE_H_PT - wy1_td
                wy1 = PAGE_H_PT - wy0_td
                c.rect(wx0, wy0, wx1 - wx0, wy1 - wy0, fill=1, stroke=0)

        for field_id, x0, y0, x1, y1 in fields_by_page[page_num]:
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
            counts[page_num] += 1
        c.showPage()

    c.save()
    buf.seek(0)
    return buf, counts


def build_acroform_catalog(writer):
    """Same reasoning as build_transformer_test_template.py's own
    identical helper, extended to collect Widget annotations from BOTH
    pages (this source has 2), not just page 0 - merge_page() brings
    each overlay page's own Widget annotations onto that page's own
    /Annots array, but never touches the document CATALOG's own
    /AcroForm entry, so nothing here creates one automatically."""
    fields = ArrayObject()
    for page in writer.pages:
        if "/Annots" not in page:
            continue
        for annot in page["/Annots"]:
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
    assert len(src_reader.pages) == NUM_PAGES, \
        f"Source PDF has {len(src_reader.pages)} pages, expected {NUM_PAGES}"
    for p in src_reader.pages:
        assert (round(float(p.mediabox.width)) == round(PAGE_W_PT)
                and round(float(p.mediabox.height)) == round(PAGE_H_PT)), \
            "Source PDF page size doesn't match general_equip_install_field_positions.py's own assumption"

    overlay_buf, counts = build_fields_overlays()
    overlay_reader = PdfReader(overlay_buf)

    writer = PdfWriter()
    writer.append(src_reader)
    # merge_page draws each overlay page's own content (the invisible
    # field widgets' own annotations come along too, via pypdf's merge)
    # ON TOP of that page's existing real content, leaving that content
    # itself untouched.
    for page_num in range(NUM_PAGES):
        writer.pages[page_num].merge_page(overlay_reader.pages[page_num])

    build_acroform_catalog(writer)
    ensure_default_resources(writer)
    writer.set_need_appearances_writer(True)
    with open(OUT_PATH, "wb") as fh:
        writer.write(fh)

    total = sum(counts)
    print(f"Wrote {OUT_PATH} with {total} fields ({counts[0]} on page 0, {counts[1]} on page 1)")


if __name__ == "__main__":
    build()
