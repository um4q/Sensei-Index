# -*- coding: utf-8 -*-
"""Phase 18 - "Cleaned copy" export: auto-fix safe whitespace/casing
issues, flag (never touch) duplicate serials and malformed tag shapes,
never insert/delete/reorder a row, never open the live workbook for
writing."""
import openpyxl
import pytest

import export_to_pdf


def test_already_clean_row_produces_no_fixes_or_flags(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    row = da.find_first_blank_row(29103, "transmitter")
    da.save_row(29103, "transmitter", row, {"tag": "29103-PIT-2171", "serial_number": "SN-001"})

    plan = da.build_cleanup_plan()
    assert plan["fixes"] == []
    assert plan["flags"] == []


def test_trims_whitespace_and_reports_as_fix(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    row = da.find_first_blank_row(29103, "transmitter")
    da.save_row(29103, "transmitter", row, {"tag": "29103-PIT-2171", "serial_number": "  SN-001  "})

    plan = da.build_cleanup_plan()
    fix = next(f for f in plan["fixes"] if f["field"] == "serial_number")
    assert fix["old"] == "  SN-001  "
    assert fix["new"] == "SN-001"
    assert fix["row"] == row
    assert fix["series"] == 29103
    assert fix["key_value"] == "29103-PIT-2171"


def test_uppercases_key_field_and_reports_as_fix(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    row = da.find_first_blank_row(29103, "transmitter")
    da.save_row(29103, "transmitter", row, {"tag": "29103-pit-2171"})

    plan = da.build_cleanup_plan()
    fix = next(f for f in plan["fixes"] if f["field"] == "tag")
    assert fix["old"] == "29103-pit-2171"
    assert fix["new"] == "29103-PIT-2171"


def test_clean_cell_is_never_touched_even_if_field_map_present(isolated_app_dir):
    """A cell that's already exactly right (no whitespace, key already
    upper) must not show up as a 'fix' at all - only an actual change is
    reported."""
    tmp_path, da = isolated_app_dir
    row = da.find_first_blank_row(29103, "transmitter")
    da.save_row(29103, "transmitter", row, {"tag": "29103-PIT-2171", "system_number": "SYS-1"})

    plan = da.build_cleanup_plan()
    assert plan["fixes"] == []


def test_date_field_never_touched_even_with_stray_whitespace(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    row = da.find_first_blank_row(29103, "transmitter")
    da.save_row(29103, "transmitter", row, {"tag": "29103-PIT-2171", "te1_caldate": "  2024-01-01  "})

    plan = da.build_cleanup_plan()
    assert not any(f["field"] == "te1_caldate" for f in plan["fixes"])


def test_non_string_cell_type_never_touched(isolated_app_dir):
    """A cell holding a raw non-str value (e.g. a number typed straight
    into Excel) is never rewritten by the whitespace/case fixer - only
    plain str cells are eligible."""
    tmp_path, da = isolated_app_dir
    row = da.find_first_blank_row(29103, "transmitter")
    da.save_row(29103, "transmitter", row, {"tag": "29103-PIT-2171", "serial_number": "12345"})

    wb = openpyxl.load_workbook(da.WORKBOOK_PATH)
    ws = wb["Transmitter Log 29103"]
    col = export_to_pdf.load_column_map(ws)["serial_number"]
    ws.cell(row=row, column=col).value = 12345  # raw int, not str
    wb.save(da.WORKBOOK_PATH)
    da.invalidate_workbook_cache()

    plan = da.build_cleanup_plan()
    assert not any(f["row"] == row and f["field"] == "serial_number" for f in plan["fixes"])


def test_flags_tag_that_still_looks_wrong_after_normalizing(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    row = da.find_first_blank_row(29103, "transmitter")
    da.save_row(29103, "transmitter", row, {"tag": "not a valid shape"})

    plan = da.build_cleanup_plan()
    flag = next(f for f in plan["flags"] if f["row"] == row)
    assert flag["key_value"] == "NOT A VALID SHAPE"
    assert "doesn't look like AREA-TYPE-NUMBER" in flag["detail"]


def test_flags_duplicate_serials_without_touching_them(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    r1 = da.find_first_blank_row(29103, "transmitter")
    da.save_row(29103, "transmitter", r1, {"tag": "29103-PIT-0001", "serial_number": "SN-DUP"})
    r2 = da.find_first_blank_row(29103, "transmitter")
    da.save_row(29103, "transmitter", r2, {"tag": "29103-PIT-0002", "serial_number": "SN-DUP"})

    plan = da.build_cleanup_plan()
    dup_flags = [f for f in plan["flags"] if "Duplicate serial" in f["detail"]]
    assert {f["row"] for f in dup_flags} == {r1, r2}
    # never "fixed" - a duplicate serial isn't a whitespace/case problem
    assert not any(f["field"] == "serial_number" for f in plan["fixes"])


def test_blank_row_is_never_touched(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    row = da.find_first_blank_row(29103, "transmitter")
    da.save_row(29103, "transmitter", row, {"tag": "  29103-PIT-2171  "})
    blank_row = row + 1  # never written to - still empty

    plan = da.build_cleanup_plan()
    assert not any(f["row"] == blank_row for f in plan["fixes"])
    assert not any(f["row"] == blank_row for f in plan["flags"])


def test_export_writes_new_file_and_never_touches_the_live_workbook(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    row = da.find_first_blank_row(29103, "transmitter")
    da.save_row(29103, "transmitter", row, {"tag": "29103-pit-2171", "serial_number": "  SN-001  "})

    before_bytes = da.WORKBOOK_PATH.read_bytes()
    out_path = da.export_cleaned_workbook()
    after_bytes = da.WORKBOOK_PATH.read_bytes()

    assert before_bytes == after_bytes  # the live workbook was only ever read
    assert out_path.exists()
    assert out_path.parent == da.CLEANED_DIR
    assert out_path.name.startswith("Equipment_Inspection_Tracker_CLEANED_")


def test_export_applies_fixes_and_highlights_them(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    row = da.find_first_blank_row(29103, "transmitter")
    da.save_row(29103, "transmitter", row, {"tag": "29103-pit-2171", "serial_number": "  SN-001  "})

    out_path = da.export_cleaned_workbook()
    out_wb = openpyxl.load_workbook(out_path)
    ws = out_wb["Transmitter Log 29103"]
    col_map = export_to_pdf.load_column_map(ws)

    assert ws.cell(row=row, column=col_map["tag"]).value == "29103-PIT-2171"
    assert ws.cell(row=row, column=col_map["serial_number"]).value == "SN-001"
    assert "FFEB9C" in ws.cell(row=row, column=col_map["tag"]).fill.fgColor.rgb
    assert "FFEB9C" in ws.cell(row=row, column=col_map["serial_number"]).fill.fgColor.rgb


def test_export_highlights_flagged_rows_key_cell(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    row = da.find_first_blank_row(29103, "transmitter")
    da.save_row(29103, "transmitter", row, {"tag": "not a valid shape"})

    out_path = da.export_cleaned_workbook()
    out_wb = openpyxl.load_workbook(out_path)
    ws = out_wb["Transmitter Log 29103"]
    col_map = export_to_pdf.load_column_map(ws)
    assert "FFC7CE" in ws.cell(row=row, column=col_map["tag"]).fill.fgColor.rgb


def test_export_appends_cleanup_log_sheet_after_original_sheets(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    original_names = list(openpyxl.load_workbook(da.WORKBOOK_PATH).sheetnames)

    out_path = da.export_cleaned_workbook()
    out_wb = openpyxl.load_workbook(out_path)
    assert out_wb.sheetnames == original_names + ["Cleanup Log"]


def test_cleanup_log_notes_when_nothing_to_fix_or_flag(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    row = da.find_first_blank_row(29103, "transmitter")
    da.save_row(29103, "transmitter", row, {"tag": "29103-PIT-2171"})

    out_path = da.export_cleaned_workbook()
    ws = openpyxl.load_workbook(out_path)["Cleanup Log"]
    values = [c.value for r in ws.iter_rows() for c in r if c.value]
    assert any("already clean" in str(v) for v in values)


def test_cleanup_log_lists_fix_and_flag_details(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    row = da.find_first_blank_row(29103, "transmitter")
    da.save_row(29103, "transmitter", row, {"tag": "29103-pit-2171", "serial_number": "  SN-001  "})
    row2 = da.find_first_blank_row(29103, "transmitter")
    da.save_row(29103, "transmitter", row2, {"tag": "not a valid shape"})

    out_path = da.export_cleaned_workbook()
    ws = openpyxl.load_workbook(out_path)["Cleanup Log"]
    values = [c.value for r in ws.iter_rows() for c in r if c.value]
    assert any(v == "SN-001" for v in values)
    assert any("AREA-TYPE-NUMBER" in str(v) for v in values)


def test_export_never_inserts_or_deletes_rows(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    row = da.find_first_blank_row(29103, "transmitter")
    da.save_row(29103, "transmitter", row, {"tag": "29103-pit-2171"})

    before_max_row = openpyxl.load_workbook(da.WORKBOOK_PATH)["Transmitter Log 29103"].max_row
    out_path = da.export_cleaned_workbook()
    after_max_row = openpyxl.load_workbook(out_path)["Transmitter Log 29103"].max_row
    assert before_max_row == after_max_row


def test_export_does_not_clobber_same_day_export(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    row = da.find_first_blank_row(29103, "transmitter")
    da.save_row(29103, "transmitter", row, {"tag": "29103-PIT-2171"})

    first = da.export_cleaned_workbook()
    second = da.export_cleaned_workbook()
    assert first != second
    assert first.exists() and second.exists()


def test_export_raises_if_no_workbook_yet(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    da.WORKBOOK_PATH.unlink()
    with pytest.raises(FileNotFoundError):
        da.export_cleaned_workbook()


def test_export_works_with_zero_rows_anywhere(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    out_path = da.export_cleaned_workbook()
    assert out_path.exists()
    ws = openpyxl.load_workbook(out_path)["Cleanup Log"]
    values = [c.value for r in ws.iter_rows() for c in r if c.value]
    assert any("already clean" in str(v) for v in values)
