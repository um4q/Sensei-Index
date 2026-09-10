#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Turns one row of the EHT & RTD Pre-Insulation Log into a filled,
ready-to-print PDF, using
EHT_and_RTD_Pre-Insulation_Installation_Report_TEMPLATE.pdf as the blank
form.

BASIC USE:
    python3 export_eht_pre_insulation_to_pdf.py Electrical_Inspection_Tracker.xlsx --sheet "EHT PreIns Log <zone>" --rows 4

Requires: pip install openpyxl pypdf
"""
import argparse
import datetime
import io
import re
import sys
from pathlib import Path

import openpyxl
from pypdf import PdfReader, PdfWriter
from pypdf.generic import DictionaryObject, NameObject, TextStringObject, ArrayObject
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.lib.pagesizes import letter

from eht_pre_insulation_schema import LOG_COLUMNS
from eht_pre_insulation_field_map import FIELD_MAP  # noqa: F401

HERE = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) \
    else Path(__file__).resolve().parent
DEFAULT_TEMPLATE = HERE / "EHT_and_RTD_Pre-Insulation_Installation_Report_TEMPLATE.pdf"
DEFAULT_OUTPUT_DIR = HERE / "output_pdfs"
HEADER_ROW = 3
FIRST_DATA_ROW = 4
SHEET_NAME = "EHT PreIns Log"

# Same Yanda QA Representative signature stamp export_to_pdf.py/
# export_valve_to_pdf.py/export_torqueing_to_pdf.py already use - reused
# directly (a shared static asset, not domain-specific data). Placed on
# this form's own "Yanda Representative - Signature" cell (the real,
# individually-measured sign-off rect from
# eht_pre_insulation_field_positions.py's SIGNOFF_SIG_X x SIGNOFF_YANDA_DATA_Y,
# converted to PDF points the same way build_eht_pre_insulation_template.py
# converts every other field's rect: px/SCALE, inset by PAD_PT). Unlike
# Torqueing's original PDF, this cell already had its own real fillable
# text field (yanda_rep_signature) - see fill_pdf() below for why that
# field's own typed value is skipped whenever the stamp is applied, so the
# two never render on top of each other.
SIGNATURE_IMAGE = HERE / "assets" / "yanda_qa_signature_transparent.png"
SIGNATURE_PAGE_INDEX = 0
SIGNATURE_X = 396
SIGNATURE_Y = 138
SIGNATURE_W = 87
SIGNATURE_H = 87 * (90 / 458)  # preserve the source image's aspect ratio


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
    """Returns a dict of REAL PDF field name -> value. Every field on this
    template is a plain text widget (see eht_pre_insulation_field_map.py's
    docstring) - no checkbox/ATC/multi-widget special cases needed, unlike
    eht_rtd's equivalent function."""
    values = {}

    for field in LOG_COLUMNS:
        fid = field["id"]
        col = field_to_col.get(fid)
        if col is None:
            continue
        raw = cell_to_str(ws.cell(row=row_num, column=col).value)
        if not raw:
            continue

        pdf_field = FIELD_MAP.get(fid)
        if pdf_field is None:
            continue
        values[pdf_field] = raw

    return values


def ensure_default_resources(writer):
    """See export_to_pdf.py's identical helper - a PDF built without an
    explicit /DR (default resources) entry on its /AcroForm crashes
    pypdf's field-update code. build_eht_pre_insulation_template.py's
    reportlab-generated AcroForm already carries its own /DR, but this
    guard is cheap insurance against ever regenerating the template with a
    tool that doesn't."""
    acro = writer._root_object["/AcroForm"]
    if "/DR" in acro and "/Font" in acro["/DR"] and "/Helv" in acro["/DR"]["/Font"]:
        return
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
    if "/DA" not in acro:
        acro[NameObject("/DA")] = TextStringObject("/Helv 0 Tf 0 g")


def stamp_signature(writer):
    """Overlays the Yanda QA Representative signature image onto this
    form's own Yanda Representative - Signature cell - the same mechanism
    export_to_pdf.py/export_torqueing_to_pdf.py already use for their own
    Yanda stamp."""
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
    """Unlike eht_removal/eht_rtd (hand-signed only, no field at all) and
    Torqueing (no field either), this form's Yanda Representative -
    Signature cell IS a real, independently fillable AcroForm text field
    (see eht_pre_insulation_field_map.py's docstring) - so when the
    automatic image stamp is applied, that field's own typed value (if
    any - e.g. leftover data from before this stamp existed) is skipped
    here rather than written underneath the stamp, so the two never
    render on top of each other. Turning add_signature off restores the
    old behavior (the typed value, if any, fills normally)."""
    values = dict(values)
    if add_signature:
        values.pop(FIELD_MAP["yanda_rep_signature"], None)

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
    trace_col = field_to_col.get("trace_number")

    print(f"Exporting {len(rows)} row(s): {rows}")
    used_names = set()
    for row_num in rows:
        values = build_values_for_row(ws, field_to_col, row_num)
        trace = cell_to_str(ws.cell(row=row_num, column=trace_col).value) if trace_col else ""
        base_name = sanitize(trace, f"Row{row_num}")
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
