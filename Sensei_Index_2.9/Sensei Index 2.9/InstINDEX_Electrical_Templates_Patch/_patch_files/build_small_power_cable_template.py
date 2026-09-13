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

Run once:
    python3 build_small_power_cable_template.py
Regenerates Small_Power_and_Control_Cable_Inspection_and_Test_Record_TEMPLATE.pdf
next to this script.
"""
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from pypdf.generic import DictionaryObject, NameObject, TextStringObject

HERE = Path(__file__).resolve().parent
SRC = HERE / "assets" / "small_power_cable_source.pdf"
OUT = HERE / "Small_Power_and_Control_Cable_Inspection_and_Test_Record_TEMPLATE.pdf"

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

    ensure_default_resources(writer)
    writer.set_need_appearances_writer(True)
    with open(OUT, "wb") as fh:
        writer.write(fh)

    print(f"Wrote {OUT} - renamed {renamed} of {len(RENAME)} fields "
          "(3 more - Project/Location/Job No - kept their original real names)")


if __name__ == "__main__":
    build()
