#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
One-time generator for
Small_Power_and_Control_Cable_Inspection_and_Test_Record_TEMPLATE.pdf
(YCQE-EI-113 Rev.0) - the Electrical side's sixth form.

REVISION 2: this form is now built from the user's own real, official
source PDF (assets/small_power_cable_source.pdf) instead of a hand-filled
scan sample. The earlier scan-based build (whiteout + reportlab-drawn
AcroForm fields over a background image) is retired entirely - it never
reliably matched the source's actual ink extent (see this repo's own
commit history for the "white spots" investigation that found it), and
there is no whiteout to get wrong here in the first place: the real
source PDF is a genuinely BLANK, digitally-authored form, not a scan.

The real source PDF is not just blank - it already has its own 41 real
AcroForm fields, correctly positioned by whoever authored the original
document (three of them - Project/Location/Job No - already carry this
engagement's constant pre-filled values: "K1B Well Pad Project"/
"K1B Kinosis"/"CA23007"). So this script does the simplest, most
faithful thing possible: take that PDF byte-for-byte and rename each
field's own internal /T name to this schema's own id - no redrawing, no
repositioning, no whiteout. See RENAME below for the exact old-name ->
new-id table (verified directly against the source PDF's own AcroForm
field dictionary, same as every other from-a-real-PDF Electrical form's
own field_map.py already documents doing).

REVISION 3: the real source has no signature field at all (see RENAME's
own history/small_power_cable_schema.py's docstring) - only a printed
"Signature:" label and blank underline, for both representatives. Two
BRAND NEW fields (yanda_rep_signature, client_rep_signature) are merged
on top of those two blank lines - same merge-overlay technique
transformer_test's/general_equip_install's own build scripts use for
forms whose real source has NO existing fields at all, just applied here
to 2 specific cells on a source that otherwise already has its own 41
real fields. build_signature_fields_overlay() below reads the exact
blank-line extent directly off the source PDF's own text
(get_text("words")) - see that function's own docstring for the
coordinates. Unlike a pure-rename field, merge_page() only adds the new
widgets to the page's own /Annots - the document catalog's existing
/AcroForm/Fields array (already populated by the 41 renamed fields) needs
the 2 new widgets appended to it by hand, or a viewer would never find
them despite them being visibly present on the page.

Run once:
    python3 build_small_power_cable_template.py
Regenerates Small_Power_and_Control_Cable_Inspection_and_Test_Record_TEMPLATE.pdf
next to this script.
"""
import io
from pathlib import Path

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from pypdf import PdfReader, PdfWriter
from pypdf.generic import DictionaryObject, NameObject, TextStringObject

HERE = Path(__file__).resolve().parent
SRC = HERE / "assets" / "small_power_cable_source.pdf"
OUT = HERE / "Small_Power_and_Control_Cable_Inspection_and_Test_Record_TEMPLATE.pdf"

PAGE_W_PT, PAGE_H_PT = letter

# Real "Signature:" blank-line extent for each representative, read
# directly off the source PDF's own text (get_text("words"), top-down
# space - PyMuPDF's own convention, NOT the PDF's native bottom-left
# origin - see transformer_test_field_positions.py's own docstring for
# the full story of why this matters). "Signature:" itself ends at
# x=86.7 (Yanda)/x=342.4 (Client); each blank underscore run - the real
# value zone - spans the coordinates below, y638.6-650.1 for both
# (same row, two columns).
SIGNATURE_FIELDS_TOPDOWN = {
    "yanda_rep_signature": ((89.0, 271.0), (638.6, 650.1)),
    "client_rep_signature": ((344.6, 526.9), (638.6, 650.1)),
}


def _to_pdf_y(y0_topdown, y1_topdown):
    return PAGE_H_PT - y1_topdown, PAGE_H_PT - y0_topdown

RENAME = {
    "Text37": "cable_tag_number",
    "Text39": "cable_type",
    "Text41": "system",
    "Text38": "cable_size",
    "Text40": "number_of_conductors",
    "Text42": "cable_rated_voltage",
    "Initial /NA": "vis_item_1_initial",
    "Initial /NA (1)": "vis_item_2_initial",
    "Text7": "vis_item_3_initial",
    "Text8": "vis_item_4_initial",
    "Text9": "vis_item_5_initial",
    "Text10": "vis_item_6_initial",
    "Text11": "vis_item_7_initial",
    "Text12": "vis_item_8_initial",
    "9. Check phase location and marking (Left to Right, Top to Bottom, or Front to Rear) are in accordance with the drawings": "vis_item_9_initial",
    "Text14": "vis_item_10_initial",
    "Text15": "vis_item_11_initial",
    "Make": "test_equip_1_make",
    "Model": "test_equip_1_model",
    "Asset/Serial Number": "test_equip_1_asset_serial",
    "Calibrated On": "test_equip_1_calibrated_on",
    "Make (1)": "test_equip_2_make",
    "Model (1)": "test_equip_2_model",
    "Asset/Serial Number (1)": "test_equip_2_asset_serial",
    "Calibrated On (1)": "test_equip_2_calibrated_on",
    "Conductor to Conductor": "insulation_cond_to_cond",
    "Conductor to Conductor (1)": "continuity_cond_to_cond",
    "Result": "insulation_cond_to_ground",
    "Result (1)": "continuity_cond_to_ground",
    "Text28": "insulation_cond_to_armour",
    "Text29": "continuity_cond_to_armour",
    "PART 6 – Remarks": "remarks_line1",
    "PART 6 – Remarks (1)": "remarks_line2",
    "Text32": "remarks_line3",
    "Name": "yanda_rep_name",
    "Name (1)": "client_rep_name",
    "Date": "yanda_rep_date",
    "Date (1)": "client_rep_date",
    # left as-is (already meaningful, already correctly pre-filled
    # constants baked in by the source PDF itself): Project, Location, Job No
}


def build_signature_fields_overlay():
    """A single blank page with nothing but 2 invisible AcroForm text
    field widgets on it (yanda_rep_signature, client_rep_signature),
    positioned exactly on top of the real source PDF's own printed
    "Signature:" blank lines - reportlab's own page, completely separate
    from the real source page, merged onto it afterward so none of that
    page's own content (including the other 41 real fields, already
    renamed in place) is ever redrawn."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    for field_id, (x_range, y_range_td) in SIGNATURE_FIELDS_TOPDOWN.items():
        x0, x1 = x_range
        y0, y1 = _to_pdf_y(*y_range_td)
        c.acroForm.textfield(
            name=field_id, tooltip=field_id, x=x0, y=y0, width=x1 - x0, height=y1 - y0,
            borderStyle=None, borderWidth=0, fillColor=None,
            forceBorder=False, fontSize=8,
        )
    c.showPage()
    c.save()
    buf.seek(0)
    return buf


def ensure_default_resources(writer):
    """The source PDF's /AcroForm has no /DR (default resources) entry,
    which crashes pypdf's field-update code later and leaves no /Helv font
    for a viewer to render typed text with. Same fix every other Electrical
    form's own build/export script already applies."""
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
    acro[NameObject("/DA")] = TextStringObject("/Helv 9 Tf 0 g")


def build():
    reader = PdfReader(str(SRC))
    writer = PdfWriter()
    writer.append(reader)

    page = writer.pages[0]
    present_old_names = {
        str(a.get_object().get("/T"))
        for a in PdfReader(str(SRC)).pages[0]["/Annots"]
        if a.get_object().get("/T")
    }
    missing = set(RENAME) - present_old_names
    if missing:
        raise ValueError(f"Expected field name(s) not found in source PDF: {missing}")

    renamed = 0
    seen = set()
    for annot in page["/Annots"]:
        obj = annot.get_object()
        old_name = obj.get("/T")
        if old_name is None:
            continue
        old_name = str(old_name)
        if old_name in RENAME:
            new_name = RENAME[old_name]
            if new_name in seen:
                raise ValueError(f"Duplicate target field id: {new_name}")
            seen.add(new_name)
            obj[NameObject("/T")] = TextStringObject(new_name)
            renamed += 1

    # "Location" is a real per-row field (unlike Project/Job No, which are
    # constants for this one client engagement and correctly stay
    # pre-filled forever) - the source PDF's own sample happened to have
    # "K1B Kinosis" typed into it, which would otherwise silently show up
    # on every export whose own row leaves location blank. Clear it.
    for annot in page["/Annots"]:
        obj = annot.get_object()
        if obj.get("/T") == "Location":
            if "/V" in obj:
                del obj[NameObject("/V")]
            if "/AP" in obj:
                del obj[NameObject("/AP")]

    # 2 brand new fields (yanda_rep_signature/client_rep_signature) - see
    # this script's own docstring (REVISION 3) for why these aren't just
    # more RENAME entries: the real source has no signature field at all.
    before = {id(a) for a in page["/Annots"]}
    overlay_reader = PdfReader(build_signature_fields_overlay())
    page.merge_page(overlay_reader.pages[0])
    new_widgets = [a for a in page["/Annots"] if id(a) not in before]
    if len(new_widgets) != len(SIGNATURE_FIELDS_TOPDOWN):
        raise ValueError(
            f"Expected {len(SIGNATURE_FIELDS_TOPDOWN)} new signature widgets after merge, "
            f"got {len(new_widgets)}"
        )
    # merge_page() only adds the new widgets to the PAGE's own /Annots -
    # the document catalog's existing /AcroForm/Fields array (already
    # populated by the 41 renamed fields) needs them appended by hand, or
    # a viewer would never find them despite them being visibly present.
    writer._root_object["/AcroForm"]["/Fields"].extend(new_widgets)

    ensure_default_resources(writer)
    writer.set_need_appearances_writer(True)
    with open(OUT, "wb") as fh:
        writer.write(fh)

    print(f"Wrote {OUT} - renamed {renamed} of {len(RENAME)} fields "
          "(3 more - Project/Location/Job No - kept their original real names), "
          f"added {len(new_widgets)} new signature fields")


if __name__ == "__main__":
    build()
