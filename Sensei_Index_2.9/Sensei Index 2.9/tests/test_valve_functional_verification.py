# -*- coding: utf-8 -*-
"""Valve Check Record (YCQP-E&I-204) - the 8-item Functional Verification
section. Previously modeled as ONE combined Excel column per item
("initials, or N/A"), with an app-level guess ("is this text literally
'N/A'?") deciding which of the two real PDF widgets it landed on - a
locked-out valve marked "LO" would have silently landed in the Yes widget
instead of the N/A one, with no error. Now each item is TWO independent
columns (fv_N_yes / fv_N_na), matching the real PDF's own two independent
widgets directly - whatever's typed goes straight to its own widget, no
guessing. See valve_field_map.py's own FIELD_MAP comment for the full
rationale.

No prior test file covered this section at all (a real, pre-existing gap -
these tests are new, not migrated from anywhere)."""
import openpyxl
import pikepdf
import pytest
from pypdf import PdfReader

import data_access as da
import gui_app
import valve_schema
import valve_field_map as fm
from export_valve_to_pdf import DEFAULT_TEMPLATE


def test_functional_verification_items_are_split_into_yes_and_na_columns():
    ids = {f["id"] for f in valve_schema.LOG_COLUMNS}
    for n in range(1, 9):
        assert f"fv_{n}_yes" in ids, f"fv_{n}_yes is missing from the schema"
        assert f"fv_{n}_na" in ids, f"fv_{n}_na is missing from the schema"
        assert f"fv_{n}" not in ids, f"fv_{n}" + " (the old combined column) should no longer exist"
    for n in range(1, 9):
        assert valve_schema.by_id(f"fv_{n}_yes")["ftype"] == "text"
        assert valve_schema.by_id(f"fv_{n}_na")["ftype"] == "text"
    assert not hasattr(valve_schema, "INITIAL_OR_NA_TYPE")


def test_field_map_has_no_leftover_fv_yes_na_pairing_helper():
    assert not hasattr(fm, "FV_YES_NA_FIELDS")


def test_functional_verification_field_map_independently_verified_against_pdf_geometry():
    """Re-derives each fv_N_yes/fv_N_na -> real widget mapping from the
    template's own /Rect positions (not by reading FIELD_MAP) - catches a
    transposition (e.g. two items' Yes/N-A pairs swapped, or Yes/N-A
    swapped within one item) that a bijection-only check can't."""
    pdf = pikepdf.open(str(DEFAULT_TEMPLATE))
    acro = pdf.Root.AcroForm
    dropdown_rects = {}
    for f in acro.Fields:
        name = str(f.get("/T", ""))
        if name.startswith("Dropdown"):
            dropdown_rects[name] = [float(x) for x in f.get("/Rect")]
    assert len(dropdown_rects) == 16

    # Group into 8 rows by y-position (well separated - see the values
    # printed when this test was written, ~14-16pt apart). Within a row,
    # the widget with the SMALLER x is "Yes" (the left column on the real
    # form, confirmed against a 300 DPI render), the larger x is "N/A".
    rows = []
    remaining = dict(dropdown_rects)
    while remaining:
        _, rect = next(iter(remaining.items()))
        y = rect[1]
        row_names = [n for n, r in remaining.items() if abs(r[1] - y) < 1.0]
        assert len(row_names) == 2, f"expected exactly 2 widgets sharing a row, found {row_names}"
        row_names.sort(key=lambda n: remaining[n][0])
        rows.append((y, row_names[0], row_names[1]))
        for n in row_names:
            del remaining[n]
    rows.sort(key=lambda r: -r[0])  # top of page (largest y) = item 1
    assert len(rows) == 8

    for item_num, (_, yes_name, na_name) in enumerate(rows, start=1):
        assert fm.FIELD_MAP[f"fv_{item_num}_yes"] == yes_name, (
            f"fv_{item_num}_yes should map to {yes_name} (geometrically the Yes "
            f"widget in row {item_num}), but FIELD_MAP says "
            f"{fm.FIELD_MAP[f'fv_{item_num}_yes']!r}"
        )
        assert fm.FIELD_MAP[f"fv_{item_num}_na"] == na_name, (
            f"fv_{item_num}_na should map to {na_name} (geometrically the N/A "
            f"widget in row {item_num}), but FIELD_MAP says "
            f"{fm.FIELD_MAP[f'fv_{item_num}_na']!r}"
        )


def test_functional_verification_dropdowns_all_accept_lo_as_a_real_choice():
    """LO is not an app invention - it's a real /Opt entry on every one of
    these 16 widgets on the original PDF (alongside N/A, blank, and FS)."""
    pdf = pikepdf.open(str(DEFAULT_TEMPLATE))
    acro = pdf.Root.AcroForm
    checked = 0
    for f in acro.Fields:
        name = str(f.get("/T", ""))
        if name.startswith("Dropdown"):
            opt = [str(o) for o in f.get("/Opt")]
            assert "LO" in opt, f"{name}'s /Opt {opt} has no 'LO' entry"
            checked += 1
    assert checked == 16


def test_exporting_lo_and_initials_lands_each_functional_verification_item_correctly(isolated_app_dir):
    """Fills all 8 items with DISTINCT values (some 'LO', some initials) and
    checks each lands on its own real widget with its own exact value - a
    swap between any two items, or between an item's own Yes/N-A pair,
    would be caught here."""
    tmp_path, _ = isolated_app_dir
    row = da.find_first_blank_row(100, "valve")

    values = {"equip_number": "V-100"}
    expected = {}
    for n in range(1, 9):
        if n % 2 == 0:
            values[f"fv_{n}_na"] = "LO"
            expected[fm.FIELD_MAP[f"fv_{n}_na"]] = "LO"
        else:
            initials = f"JD{n}"
            values[f"fv_{n}_yes"] = initials
            expected[fm.FIELD_MAP[f"fv_{n}_yes"]] = initials
    da.save_row(100, "valve", row, values)

    out_path = da.generate_preview_pdf(100, "valve", row)
    fields = PdfReader(str(out_path)).get_fields()
    for pdf_field, expected_value in expected.items():
        assert fields[pdf_field].get("/V") == expected_value, (
            f"{pdf_field} should hold {expected_value!r}"
        )
    # every widget NOT explicitly set above must be untouched (still the
    # template's own idle default - "  ", the blank /Opt entry, for these
    # particular widgets - never one of the OTHER items' values, which is
    # what an actual transposition bug would produce).
    all_fv_pdf_fields = {fm.FIELD_MAP[f"fv_{n}_yes"] for n in range(1, 9)} | \
        {fm.FIELD_MAP[f"fv_{n}_na"] for n in range(1, 9)}
    placed_values = set(expected.values())
    for pdf_field in all_fv_pdf_fields - set(expected):
        untouched_value = fields[pdf_field].get("/V")
        assert untouched_value not in placed_values, (
            f"{pdf_field} should be untouched, but holds {untouched_value!r} - "
            f"a value meant for a different item"
        )


def test_valve_edit_dialog_has_independent_widgets_for_every_functional_verification_column(
        qtbot, isolated_app_dir):
    dlg = gui_app.EditDialog(None, 100, "valve", da.find_first_blank_row(100, "valve"), is_new=True)
    qtbot.addWidget(dlg)
    for n in range(1, 9):
        assert f"fv_{n}_yes" in dlg.widgets
        assert f"fv_{n}_na" in dlg.widgets
        assert dlg.widgets[f"fv_{n}_yes"] is not dlg.widgets[f"fv_{n}_na"]
        assert isinstance(dlg.widgets[f"fv_{n}_yes"], gui_app.QLineEdit)
        assert isinstance(dlg.widgets[f"fv_{n}_na"], gui_app.QLineEdit)


def test_yanda_qc_representative_name_font_matches_the_signed_date_field():
    """Regression test: Text51 (qc_rep_name, "YANDA QC Representative -
    Name") used to render at 7pt while QCRepDate (qc_date, right below it)
    rendered at 9pt - a visible size mismatch between a name and its own
    signed date. Both must now share the same font size."""
    pdf = pikepdf.open(str(DEFAULT_TEMPLATE))
    acro = pdf.Root.AcroForm
    da_strings = {}
    for f in acro.Fields:
        name = str(f.get("/T", ""))
        if name in ("Text51", "QCRepDate"):
            da_strings[name] = str(f.get("/DA"))

    def font_size(da_string):
        # e.g. "0 0 0 rg /Helv 9 Tf" -> 9.0
        tokens = da_string.split()
        tf_index = tokens.index("Tf")
        return float(tokens[tf_index - 1])

    assert font_size(da_strings["Text51"]) == font_size(da_strings["QCRepDate"]), (
        f"qc_rep_name ({da_strings['Text51']!r}) and qc_date ({da_strings['QCRepDate']!r}) "
        f"should render at the same font size"
    )
