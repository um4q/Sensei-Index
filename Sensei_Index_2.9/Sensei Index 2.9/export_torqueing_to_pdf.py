#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Turns one row of the Torqueing Report Log into a filled, ready-to-print
PDF, using YCQE-EI-014_Torqueing_Report_TEMPLATE.pdf as the blank form.

BASIC USE:
    python3 export_torqueing_to_pdf.py Electrical_Inspection_Tracker.xlsx --sheet "Torqueing Log <zone>" --rows 4

Requires: pip install openpyxl pypdf reportlab
"""
import argparse
import datetime
import io
import re
import sys
from pathlib import Path

import openpyxl
from pypdf import PdfReader, PdfWriter
from pypdf.generic import DictionaryObject, NameObject, TextStringObject
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.lib.pagesizes import letter

from torqueing_schema import LOG_COLUMNS
from torqueing_field_map import (
    FIELD_MAP, COMMENTS_NA_CHECKBOX, CHECKBOX_OFF,  # noqa: F401
)

HERE = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) \
    else Path(__file__).resolve().parent
DEFAULT_TEMPLATE = HERE / "YCQE-EI-014_Torqueing_Report_TEMPLATE.pdf"
DEFAULT_OUTPUT_DIR = HERE / "output_pdfs"
HEADER_ROW = 3
FIRST_DATA_ROW = 4
SHEET_NAME = "Torqueing Log"

# Same Yanda QA Representative signature stamp export_to_pdf.py/
# export_valve_to_pdf.py already use - reused directly (a shared static
# asset, not domain-specific data) rather than duplicated. Placed on the
# original PDF's own blank "SIGNATURE" cell in the Yanda Representative
# row (x=366.4-575.6, y=129.7-154.9 pt) - the original form has no field
# there at all (hand-signed only), so this is a pure visual overlay, same
# mechanism as Instrumentation's own stamp, not a fillable field.
SIGNATURE_IMAGE = HERE / "assets" / "yanda_qa_signature_transparent.png"
SIGNATURE_PAGE_INDEX = 0
SIGNATURE_X = 372
SIGNATURE_Y = 132
SIGNATURE_W = 115
SIGNATURE_H = 115 * (90 / 458)  # preserve the source image's aspect ratio


def sanitize(text, fallback):
    text = (text or "").strip()
    text = re.sub(r"[^A-Za-z0-9\-_. ]+", "", text).strip()
    return text or fallback


def cell_to_str(value):
    if value is None:
        return ""
    if isinstance(value, (datetime.datetime, datetime.date)):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def load_column_map(ws):
    label_to_col = {}
    dupe_labels = set()
    for col in range(1, ws.max_column + 1):
        label = ws.cell(row=HEADER_ROW, column=col).value
        if label:
            label = str(label).strip()
            if label in label_to_col:
                dupe_labels.add(label)
            label_to_col[label] = col
    if dupe_labels:
        print("WARNING: these column headers appear more than once in row "
              f"{HEADER_ROW} - only the last occurrence of each will be read:")
        for d in sorted(dupe_labels):
            print("   -", d)

    field_to_col = {}
    missing = []
    for field in LOG_COLUMNS:
        col = label_to_col.get(field["label"])
        if col is None:
            missing.append(field["label"])
        else:
            field_to_col[field["id"]] = col
    if missing:
        print("WARNING: these expected columns were not found in the Log sheet header "
              f"(row {HEADER_ROW}) and will be left blank on export:")
        for m in missing:
            print("   -", m)
    return field_to_col


def build_values_for_row(ws, field_to_col, row_num):
    """Returns a dict of REAL PDF field name -> value."""
    values = {}

    for field in LOG_COLUMNS:
        fid = field["id"]
        col = field_to_col.get(fid)
        if col is None:
            continue
        raw = cell_to_str(ws.cell(row=row_num, column=col).value)
        if not raw:
            continue

        if fid == "comments_na":
            if raw.upper() == "Y":
                values[COMMENTS_NA_CHECKBOX["field"]] = COMMENTS_NA_CHECKBOX["on"]
            continue

        pdf_field = FIELD_MAP.get(fid)
        if pdf_field is None:
            continue
        values[pdf_field] = raw

    return values


def ensure_default_resources(writer):
    """The ORIGINAL PDF (reference_material/.../..._ORIGINAL.pdf) has no
    /AcroForm /DR font dict at all, even though its fields' own /DA
    strings reference the standard short name '/Helv' - filling it
    directly reproduces pypdf's "Font dictionary for /Helv not found;
    defaulting to Helvetica" warning. The checked-in template
    (YCQE-EI-014_Torqueing_Report_TEMPLATE.pdf) already carries a correct
    /DR/Font/Helv entry from whatever process built it, so this function
    is currently a no-op against that real, shipped asset - it's kept
    as a defensive safety net (same helper export_to_pdf.py's own
    ensure_default_resources() uses) in case the template is ever
    regenerated without one: it only ever adds a '/Helv' entry alongside
    whatever /DR/Font already exists, never replaces it."""
    acro = writer._root_object["/AcroForm"]
    helv = DictionaryObject({
        NameObject("/Type"): NameObject("/Font"),
        NameObject("/Subtype"): NameObject("/Type1"),
        NameObject("/BaseFont"): NameObject("/Helvetica"),
        NameObject("/Encoding"): NameObject("/WinAnsiEncoding"),
    })
    helv_ref = writer._add_object(helv)
    dr = acro.get("/DR")
    if dr is None:
        dr = DictionaryObject()
        acro[NameObject("/DR")] = dr
    font_dict = dr.get("/Font")
    if font_dict is None:
        font_dict = DictionaryObject()
        dr[NameObject("/Font")] = font_dict
    font_dict[NameObject("/Helv")] = helv_ref
    if "/DA" not in acro:
        acro[NameObject("/DA")] = TextStringObject("/Helv 0 Tf 0 g")


def stamp_signature(writer):
    """Overlays the Yanda QA Representative signature image onto the
    original PDF's blank Signature cell in the Yanda Representative row -
    that cell has no fillable field at all on the original (hand-signed
    only there), so this is a pure page-content overlay, the same
    mechanism export_to_pdf.py's own stamp_signature() uses."""
    if not SIGNATURE_IMAGE.exists():
        print(f"   ! Signature image not found at {SIGNATURE_IMAGE} - skipping signature stamp. "
              f"Make sure the 'assets' folder is in the same directory as this script.")
        return
    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=letter)
    c.drawImage(str(SIGNATURE_IMAGE), SIGNATURE_X, SIGNATURE_Y,
                width=SIGNATURE_W, height=SIGNATURE_H,
                mask="auto", preserveAspectRatio=True)
    c.save()
    buf.seek(0)
    overlay_reader = PdfReader(buf)
    writer.pages[SIGNATURE_PAGE_INDEX].merge_page(overlay_reader.pages[0])


def fill_pdf(template_path, values, out_path, flatten=False, add_signature=True):
    reader = PdfReader(str(template_path))
    writer = PdfWriter()
    writer.append(reader)
    ensure_default_resources(writer)

    for page in writer.pages:
        writer.update_page_form_field_values(page, values, flatten=flatten)
    writer.set_need_appearances_writer(not flatten)

    if add_signature:
        stamp_signature(writer)

    if flatten:
        writer.remove_annotations(subtypes="/Widget")
        if "/AcroForm" in writer._root_object:
            from pypdf.generic import ArrayObject
            acro = writer._root_object["/AcroForm"]
            acro[NameObject("/Fields")] = ArrayObject()

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "wb") as fh:
        writer.write(fh)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("excel_path", nargs="?", default=str(HERE / "Electrical_Inspection_Tracker.xlsx"))
    ap.add_argument("--template", default=str(DEFAULT_TEMPLATE), help="Path to the blank fillable PDF template")
    ap.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Folder to write filled PDFs into")
    ap.add_argument("--rows", default="", required=False,
                     help="Comma-separated Excel row numbers to export, e.g. --rows 4,7,12")
    ap.add_argument("--flatten", action="store_true", help="Flatten the filled fields into static page content "
                                                              "(no longer editable/fillable afterward)")
    ap.add_argument("--no-signature", action="store_true", help="Skip the Yanda Representative signature stamp")
    ap.add_argument("--sheet", default=SHEET_NAME, help=f"Which sheet to read from (default: '{SHEET_NAME}')")
    args = ap.parse_args()

    excel_path = Path(args.excel_path)
    template_path = Path(args.template)
    output_dir = Path(args.output_dir)

    if not excel_path.exists():
        sys.exit(f"ERROR: can't find workbook: {excel_path}")
    if not template_path.exists():
        sys.exit(f"ERROR: can't find PDF template: {template_path}")
    if not args.rows:
        sys.exit("ERROR: pass --rows 4,7,... (this form has no batch export-flag column)")

    rows = sorted({int(x) for x in args.rows.split(",") if x.strip()})

    wb = openpyxl.load_workbook(excel_path, data_only=True)
    if args.sheet not in wb.sheetnames:
        sys.exit(f"ERROR: workbook has no '{args.sheet}' sheet. Available sheets: {', '.join(wb.sheetnames)}")
    ws = wb[args.sheet]

    field_to_col = load_column_map(ws)
    key_col = field_to_col.get("torque_record_number")

    print(f"Exporting {len(rows)} row(s): {rows}")
    used_names = set()
    for row_num in rows:
        values = build_values_for_row(ws, field_to_col, row_num)
        key_val = cell_to_str(ws.cell(row=row_num, column=key_col).value) if key_col else ""
        base_name = sanitize(key_val, f"Row{row_num}")
        name = base_name
        n = 2
        while name in used_names:
            name = f"{base_name} ({n})"
            n += 1
        used_names.add(name)
        out_path = output_dir / f"{name}.pdf"
        fill_pdf(template_path, values, out_path, flatten=args.flatten, add_signature=not args.no_signature)
        print(f"   -> {out_path}")

    print(f"Done. {len(rows)} PDF(s) written to {output_dir}/")


if __name__ == "__main__":
    main()
