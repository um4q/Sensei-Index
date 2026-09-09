#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
One-time generator for EHT_and_RTD_Pre-Insulation_Installation_Report_TEMPLATE.pdf.

Unlike eht_removal/eht_rtd, there is no original fillable PDF for this form
(YCQE-EHT-004 Rev.0) - every source instance is a hand-filled, scanned paper
form (see reference_material/EHT-004_scanned_samples/). This script builds a
brand-new fillable AcroForm PDF from scratch with reportlab, reproducing the
scanned form's layout/section order/table structure/header logos/font
weights faithfully, with the field VALUES themselves left genuinely blank -
per the user's explicit instruction: "make sure its empty and polish up ...
make it look like the original document, BUT THE SAME FORMAT SAME IMAGE,
SAME FONT IS THE SAME JUST THE ALIGNMENT AND QUALITY LIKE AN ORIGINAL
TEMPLATE." The only intentional improvement over the scan is what a clean
digital original naturally gives you over a 10th-generation photocopy: crisp
straight lines, even row spacing, no skew, no scanner noise.

The two header logos (assets/eht004_yanda_logo.png, assets/eht004_cooec_logo.png)
were cropped directly from a clean instance of the scan itself (page 3 of
Sharp_Scanner_20260908_123001_1.pdf, rendered at 300 DPI) since no separate
clean asset exists for either mark - assets/oathplatehelm*.png are a
different, unrelated graphic already used elsewhere in the app (the
sidebar/splash logo) and are NOT the Yanda company logo. The crops had their
background scanner-grey washed to pure white and were autocropped to content
- no other editing.

Run once:
    python3 build_eht_pre_insulation_template.py
Regenerates EHT_and_RTD_Pre-Insulation_Installation_Report_TEMPLATE.pdf next
to this script. Safe to re-run any time the layout needs a tweak - it always
writes a fresh, fully blank template.
"""
import sys
from pathlib import Path

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.colors import HexColor, white, black

HERE = Path(__file__).resolve().parent
OUT_PATH = HERE / "EHT_and_RTD_Pre-Insulation_Installation_Report_TEMPLATE.pdf"
YANDA_LOGO = HERE / "assets" / "eht004_yanda_logo.png"
COOEC_LOGO = HERE / "assets" / "eht004_cooec_logo.png"

PAGE_W, PAGE_H = letter  # 612 x 792
MARGIN = 36
INK = HexColor("#111111")
RULE = HexColor("#444444")
BANNER_BG = HexColor("#DCE6F1")

CHECKLIST_ITEMS = [
    "EHT Receiving Report has been Completed if required",
    "EHT Tag Matches Part # and drawings",
    "EHT is Routed and Installed as per specifications",
    "RTD's Receiving Report has been Completed if required",
    "RTD's are installed as per drawing and specification",
    "EHT/RTD's Tags are correctly labelled and installed",
    "As-built drawings completed and submitted",
    "Terminations are complete with correct wire tags",
    "SR/MI Trace Continuity test passed (Record Resistance)",
    "EHT/RTD's Released for Insulation",
]

TRACE_FIELDS = [
    ("trace_number", "Trace #"),
    ("eht_controller_number", "EHT Controller #"),
    ("trace_part_number", "Trace Part #"),
    ("panel_number", "Panel #"),
    ("rtds_number", "RTD(s) #"),
    ("circuit_number", "Circuit #"),
    ("trace_line_number", "Trace Line #"),
    ("rev", "Rev #"),
]

MEGGER_ROWS = [
    ("500 VDC", "megger_500_reading", "megger_500_result"),
    ("1000 VDC", "megger_1000_reading", "megger_1000_result"),
    ("2500 VDC", "megger_2500_reading", "megger_2500_result"),
]


def draw_header(c):
    """Title + form number span the FULL width above the logos (not
    between them) - the title text alone is wider than the gap between the
    two logos would allow at a readable size, so it reads as a top banner
    with the two company marks anchored below it, left and right."""
    top = PAGE_H - MARGIN

    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 13)
    c.drawCentredString(PAGE_W / 2, top - 12, "EHT & RTD PRE-INSULATION INSTALLATION REPORT")
    c.setFont("Helvetica", 9)
    c.drawCentredString(PAGE_W / 2, top - 26, "YCQE-EHT-004 Rev.0")

    # Yanda logo, below the title, left
    try:
        c.drawImage(str(YANDA_LOGO), MARGIN, top - 66, width=110, height=26,
                     preserveAspectRatio=True, mask="auto")
    except Exception:
        pass
    # COOEC logo, below the title, right
    try:
        c.drawImage(str(COOEC_LOGO), PAGE_W - MARGIN - 100, top - 68, width=100, height=28,
                     preserveAspectRatio=True, mask="auto")
    except Exception:
        pass

    c.setStrokeColor(RULE)
    c.setLineWidth(1)
    c.line(MARGIN, top - 74, PAGE_W - MARGIN, top - 74)
    return top - 74


def section_banner(c, y, title, height=16):
    c.setFillColor(BANNER_BG)
    c.rect(MARGIN, y - height, PAGE_W - 2 * MARGIN, height, stroke=0, fill=1)
    c.setStrokeColor(RULE)
    c.rect(MARGIN, y - height, PAGE_W - 2 * MARGIN, height, stroke=1, fill=0)
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 9.5)
    c.drawString(MARGIN + 4, y - height + 4, title)
    return y - height


def text_field(c, name, x, y, w, h, font_size=8, tooltip=None, multiline=False):
    c.acroForm.textfield(
        name=name,
        tooltip=tooltip or name,
        x=x, y=y, width=w, height=h,
        borderStyle="underlined",
        borderColor=RULE, fillColor=white, textColor=black,
        forceBorder=True, fontSize=font_size,
        fieldFlags="multiline" if multiline else "",
    )


def labeled_field(c, field_id, label, x, y, w, h=14, label_size=6.5):
    """Small caption above an underlined fillable box - used for the header
    info row and the Trace Data grid."""
    c.setFillColor(RULE)
    c.setFont("Helvetica", label_size)
    c.drawString(x, y + h + 1, label)
    text_field(c, field_id, x, y, w, h)


def build():
    c = canvas.Canvas(str(OUT_PATH), pagesize=letter)
    c.setTitle("EHT & RTD Pre-Insulation Installation Report - YCQE-EHT-004 Rev.0")
    c.acroForm.needAppearances = True

    y = draw_header(c)
    y -= 10

    # ---------------------------------------------------------- Header info
    col_w = (PAGE_W - 2 * MARGIN - 16) / 2
    row_h = 16
    labeled_field(c, "customer_name", "Customer Name", MARGIN, y - row_h, col_w)
    labeled_field(c, "project_name", "Project Name", MARGIN + col_w + 16, y - row_h, col_w)
    y -= row_h + 20
    labeled_field(c, "contract_no", "Contract #", MARGIN, y - row_h, col_w)
    labeled_field(c, "location", "Location", MARGIN + col_w + 16, y - row_h, col_w)
    y -= row_h + 10

    # ------------------------------------------------------------- Trace Data
    y = section_banner(c, y, "TRACE DATA")
    y -= 18
    n_cols = 4
    cell_w = (PAGE_W - 2 * MARGIN) / n_cols
    for i, (fid, label) in enumerate(TRACE_FIELDS):
        col = i % n_cols
        row = i // n_cols
        fx = MARGIN + col * cell_w + 2
        fy = y - row * 26
        labeled_field(c, fid, label, fx, fy - 14, cell_w - 8, h=14, label_size=6.2)
    y -= 26 * ((len(TRACE_FIELDS) - 1) // n_cols + 1) + 6

    # ---------------------------------------------------- Pre-Insulation table
    y = section_banner(c, y, "1.0 PRE-INSULATION INSPECTION")
    header_h = 14
    item_col_x = MARGIN
    item_col_w = 22
    desc_col_x = item_col_x + item_col_w
    desc_col_w = 270
    result_col_x = desc_col_x + desc_col_w
    result_col_w = 60
    comments_col_x = result_col_x + result_col_w
    comments_col_w = (PAGE_W - MARGIN) - comments_col_x

    c.setFillColor(HexColor("#EEEEEE"))
    c.rect(MARGIN, y - header_h, PAGE_W - 2 * MARGIN, header_h, stroke=1, fill=1)
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 7.5)
    c.drawString(item_col_x + 2, y - header_h + 4, "#")
    c.drawString(desc_col_x + 2, y - header_h + 4, "Description")
    c.setFont("Helvetica-Bold", 6.3)
    c.drawCentredString(result_col_x + result_col_w / 2, y - header_h + 4, "Results (Init/NA)")
    c.setFont("Helvetica-Bold", 7.5)
    c.drawString(comments_col_x + 2, y - header_h + 4, "Comments")
    y -= header_h

    row_h = 18
    c.setStrokeColor(RULE)
    for i, desc in enumerate(CHECKLIST_ITEMS, start=1):
        row_top = y - (i - 1) * row_h
        row_bottom = row_top - row_h
        c.rect(MARGIN, row_bottom, PAGE_W - 2 * MARGIN, row_h, stroke=1, fill=0)
        c.line(desc_col_x, row_bottom, desc_col_x, row_top)
        c.line(result_col_x, row_bottom, result_col_x, row_top)
        c.line(comments_col_x, row_bottom, comments_col_x, row_top)

        c.setFillColor(INK)
        c.setFont("Helvetica", 7.5)
        c.drawString(item_col_x + 4, row_bottom + 5, str(i))
        c.drawString(desc_col_x + 3, row_bottom + 5, desc)

        text_field(c, f"pre_ins_item_{i}_result", result_col_x + 2, row_bottom + 2,
                    result_col_w - 4, row_h - 4, font_size=7.5)
        text_field(c, f"pre_ins_item_{i}_comments", comments_col_x + 2, row_bottom + 2,
                    comments_col_w - 4, row_h - 4, font_size=7.5)

    y -= len(CHECKLIST_ITEMS) * row_h + 10

    # ------------------------------------------------ Insulation Test Equipment
    y = section_banner(c, y, "INSULATION TESTING EQUIPMENT")
    y -= 18
    eq_col_w = (PAGE_W - 2 * MARGIN - 32) / 3
    labeled_field(c, "test_equip_model", "Test Equip. Model #", MARGIN, y - 14, eq_col_w)
    labeled_field(c, "test_equip_serial", "Test Equip. Serial #", MARGIN + eq_col_w + 16, y - 14, eq_col_w)
    labeled_field(c, "cal_due_date", "Cal. Due Date", MARGIN + 2 * (eq_col_w + 16), y - 14, eq_col_w)
    y -= 14 + 8

    # This banner intentionally repeats "1.8" from the checklist above - a
    # real quirk in the client's own source form, preserved as-is (see
    # eht_pre_insulation_schema.py's module docstring).
    y = section_banner(c, y, "1.8 PRE-INSULATION INSULATION TEST RESULTS")
    header_h = 14
    label_col_x = MARGIN
    label_col_w = 130
    reading_col_x = label_col_x + label_col_w
    reading_col_w = 220
    result_col_x2 = reading_col_x + reading_col_w
    result_col_w2 = (PAGE_W - MARGIN) - result_col_x2

    c.setFillColor(HexColor("#EEEEEE"))
    c.rect(MARGIN, y - header_h, PAGE_W - 2 * MARGIN, header_h, stroke=1, fill=1)
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 7.5)
    c.drawString(label_col_x + 2, y - header_h + 4, "SR/MI @")
    c.drawString(reading_col_x + 2, y - header_h + 4, "Reading")
    c.drawString(result_col_x2 + 2, y - header_h + 4, "Passed / Fail")
    y -= header_h

    row_h = 18
    for i, (label, reading_fid, result_fid) in enumerate(MEGGER_ROWS):
        row_top = y - i * row_h
        row_bottom = row_top - row_h
        c.setStrokeColor(RULE)
        c.rect(MARGIN, row_bottom, PAGE_W - 2 * MARGIN, row_h, stroke=1, fill=0)
        c.line(reading_col_x, row_bottom, reading_col_x, row_top)
        c.line(result_col_x2, row_bottom, result_col_x2, row_top)

        c.setFillColor(INK)
        c.setFont("Helvetica", 7.5)
        c.drawString(label_col_x + 3, row_bottom + 5, label)

        text_field(c, reading_fid, reading_col_x + 2, row_bottom + 2, reading_col_w - 4, row_h - 4, font_size=7.5)
        text_field(c, result_fid, result_col_x2 + 2, row_bottom + 2, result_col_w2 - 4, row_h - 4, font_size=7.5)

    y -= len(MEGGER_ROWS) * row_h + 10

    # ---------------------------------------------------------------- Comments
    c.setFillColor(RULE)
    c.setFont("Helvetica", 7)
    c.drawString(MARGIN, y, "Comments")
    comments_h = 40
    text_field(c, "comments", MARGIN, y - comments_h - 3, PAGE_W - 2 * MARGIN, comments_h,
               font_size=8, multiline=True)
    y -= comments_h + 3 + 10

    # ----------------------------------------------------------------- Sign-off
    y = section_banner(c, y, "SIGN-OFF")
    y -= 14
    half_w = (PAGE_W - 2 * MARGIN - 20) / 2
    x2 = MARGIN + half_w + 20

    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 7.5)
    c.drawString(MARGIN, y, "Yanda Representative")
    c.drawString(x2, y, "Client Representative")
    y -= 14

    labeled_field(c, "yanda_rep_date", "Date (yy/mm/dd)", MARGIN, y - 14, half_w * 0.35)
    labeled_field(c, "yanda_rep_signature", "Signature",
                  MARGIN + half_w * 0.35 + 8, y - 14, half_w * 0.65 - 8)
    labeled_field(c, "client_rep_date", "Date (yy/mm/dd)", x2, y - 14, half_w * 0.35)
    labeled_field(c, "client_rep_signature", "Signature",
                  x2 + half_w * 0.35 + 8, y - 14, half_w * 0.65 - 8)
    y -= 14 + 10

    # ------------------------------------------------------------------ Footer
    # Reproduces a real inconsistency in the client's own form: the header
    # names this form "YCQE-EHT-004 Rev.0" but the footer stamp on every
    # scanned instance actually reads "YCQE-EHT-003 Rev.0". Preserved
    # exactly as printed on the original - not ours to "fix".
    c.setFillColor(RULE)
    c.setFont("Helvetica", 6.5)
    c.drawRightString(PAGE_W - MARGIN, MARGIN - 6, "YCQE-EHT-003 Rev.0")
    c.drawRightString(PAGE_W - MARGIN, MARGIN - 14, "04/06/2026")

    c.showPage()
    c.save()
    print(f"Wrote {OUT_PATH}")


if __name__ == "__main__":
    build()
