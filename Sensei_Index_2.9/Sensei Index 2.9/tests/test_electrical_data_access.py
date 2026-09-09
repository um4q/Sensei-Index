# -*- coding: utf-8 -*-
"""Electrical domain - the independent EHT Removal & Reinstatement / EHT &
RTD Installation Inspection data layer. isolated_app_dir's fixture patches
electrical_data_access.py's paths into the same tmp_path as the
Instrumentation side, so `import electrical_data_access as eda` here always
resolves to the isolated instance."""
import openpyxl
import pytest
from pypdf import PdfReader

import electrical_data_access as eda


def test_registry_starts_empty_without_touching_the_workbook(isolated_app_dir):
    """list_zones() only reads electrical_registry.json - it has no reason
    to touch (let alone create) the workbook at all."""
    tmp_path, da = isolated_app_dir
    assert not eda.ELECTRICAL_WORKBOOK_PATH.exists()
    assert eda.list_zones() == []
    assert not eda.ELECTRICAL_WORKBOOK_PATH.exists()


def test_workbook_is_bootstrapped_lazily_on_first_real_use(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    assert not eda.ELECTRICAL_WORKBOOK_PATH.exists()
    eda.add_zone("K1B Well Pad")  # the first operation that actually needs the workbook
    assert eda.ELECTRICAL_WORKBOOK_PATH.exists()


def test_add_zone_creates_both_sheets(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    entry = eda.add_zone("K1B Well Pad")
    assert entry["name"] == "K1B Well Pad"
    assert eda.list_zones() == ["K1B Well Pad"]

    wb = openpyxl.load_workbook(eda.ELECTRICAL_WORKBOOK_PATH)
    assert entry["eht_removal_sheet"] in wb.sheetnames
    assert entry["eht_rtd_sheet"] in wb.sheetnames
    # bootstrap placeholder sheet is removed once a real zone exists
    assert "Zones go here" not in wb.sheetnames


def test_add_zone_header_row_matches_schema_labels(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    import eht_removal_schema
    entry = eda.add_zone("K1B Well Pad")
    wb = openpyxl.load_workbook(eda.ELECTRICAL_WORKBOOK_PATH)
    ws = wb[entry["eht_removal_sheet"]]
    header = [ws.cell(row=3, column=c).value for c in range(1, len(eht_removal_schema.LOG_COLUMNS) + 1)]
    assert header == [f["label"] for f in eht_removal_schema.LOG_COLUMNS]


def test_add_zone_rejects_duplicate_name(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    eda.add_zone("K1B Well Pad")
    with pytest.raises(ValueError):
        eda.add_zone("K1B Well Pad")


def test_add_zone_rejects_blank_name(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    with pytest.raises(ValueError):
        eda.add_zone("   ")


def test_sheet_name_truncates_long_zone_names_safely(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    long_name = "A Very Long Zone Name That Would Blow Past The Excel Sheet Name Limit"
    entry = eda.add_zone(long_name)
    assert len(entry["eht_removal_sheet"]) <= 31
    assert len(entry["eht_rtd_sheet"]) <= 31
    wb = openpyxl.load_workbook(eda.ELECTRICAL_WORKBOOK_PATH)
    assert entry["eht_removal_sheet"] in wb.sheetnames
    assert entry["eht_rtd_sheet"] in wb.sheetnames


def test_remove_zone_archives_sheets_and_unregisters(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    entry = eda.add_zone("K1B Well Pad")
    eda.remove_zone("K1B Well Pad")
    assert eda.list_zones() == []
    wb = openpyxl.load_workbook(eda.ELECTRICAL_WORKBOOK_PATH)
    assert entry["eht_removal_sheet"] not in wb.sheetnames  # renamed, not deleted
    assert any(s.startswith("DEL ") for s in wb.sheetnames)
    archived = next(s for s in wb.sheetnames if s.startswith("DEL "))
    assert wb[archived].sheet_state == "hidden"


def test_remove_zone_raises_for_unknown_zone(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    with pytest.raises(KeyError):
        eda.remove_zone("Nonexistent")


def test_remove_only_zone_does_not_crash_on_zero_visible_sheets(isolated_app_dir):
    """openpyxl refuses to save a workbook with zero visible sheets - if
    the zone being removed is the only one, archiving (hiding) both its
    sheets would leave none visible unless something takes their place."""
    tmp_path, da = isolated_app_dir
    eda.add_zone("Only Zone")
    eda.remove_zone("Only Zone")  # must not raise
    assert eda.list_zones() == []
    wb = openpyxl.load_workbook(eda.ELECTRICAL_WORKBOOK_PATH)
    assert any(ws.sheet_state == "visible" for ws in wb.worksheets)


def test_two_different_zone_names_that_truncate_the_same_do_not_collide(isolated_app_dir):
    """Two DIFFERENT zone names sharing the same first ~17/21 characters
    truncate to the identical sheet name - add_zone()'s own "does this
    exact zone name already exist" check doesn't catch that (it compares
    full names, not truncated ones), so _sheet_name_for_zone() itself must
    resolve the collision transparently rather than raise a confusing
    error naming a sheet the user never typed."""
    tmp_path, da = isolated_app_dir
    zone1 = "12345678901234567890AAAA"
    zone2 = "12345678901234567890BBBB"  # same first 21 chars as zone1
    entry1 = eda.add_zone(zone1)
    entry2 = eda.add_zone(zone2)  # must NOT raise
    assert entry1["eht_removal_sheet"] != entry2["eht_removal_sheet"]
    assert eda.list_zones() == sorted([zone1, zone2])

    wb = openpyxl.load_workbook(eda.ELECTRICAL_WORKBOOK_PATH)
    assert entry1["eht_removal_sheet"] in wb.sheetnames
    assert entry2["eht_removal_sheet"] in wb.sheetnames

    # each zone's rows land on ITS OWN sheet, not the other's
    row1 = eda.find_first_blank_row(zone1, "eht_removal")
    eda.save_row(zone1, "eht_removal", row1, {"trace_tag": "ZONE1-TAG"})
    assert eda.read_index_rows(zone2, "eht_removal") == []


def test_remove_and_readd_zone_cycle_keeps_workbook_valid(isolated_app_dir):
    """A full remove-then-add-again cycle (a common 'oops, undo that'
    workflow) must leave the workbook in a normal, loadable state, with
    the placeholder sheet cleaned back up once a real zone exists again."""
    tmp_path, da = isolated_app_dir
    eda.add_zone("Zone A")
    eda.remove_zone("Zone A")
    eda.add_zone("Zone B")
    wb = openpyxl.load_workbook(eda.ELECTRICAL_WORKBOOK_PATH)
    assert "Zones go here" not in wb.sheetnames
    row = eda.find_first_blank_row("Zone B", "eht_removal")
    eda.save_row("Zone B", "eht_removal", row, {"trace_tag": "X-1"})
    assert eda.read_index_rows("Zone B", "eht_removal")[0]["trace_tag"] == "X-1"


def test_save_and_read_row_round_trips(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    eda.add_zone("K1B Well Pad")
    row = eda.find_first_blank_row("K1B Well Pad", "eht_removal")
    eda.save_row("K1B Well Pad", "eht_removal", row, {
        "trace_tag": "29103-EHT-0001", "area": "29103", "alarm": "Yes",
        "full_removal_item_3_yes": "JD",
    })
    full = eda.read_full_row("K1B Well Pad", "eht_removal", row)
    assert full["trace_tag"] == "29103-EHT-0001"
    assert full["area"] == "29103"
    assert full["alarm"] == "Yes"
    assert full["full_removal_item_3_yes"] == "JD"
    assert full["full_removal_item_3_na"] == ""  # untouched field stays blank


def test_read_index_rows_only_shows_rows_with_key_filled(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    eda.add_zone("K1B Well Pad")
    row = eda.find_first_blank_row("K1B Well Pad", "eht_removal")
    eda.save_row("K1B Well Pad", "eht_removal", row, {"area": "29103"})  # no trace_tag
    assert eda.read_index_rows("K1B Well Pad", "eht_removal") == []

    eda.save_row("K1B Well Pad", "eht_removal", row, {"trace_tag": "29103-EHT-0001"})
    rows = eda.read_index_rows("K1B Well Pad", "eht_removal")
    assert len(rows) == 1
    assert rows[0]["trace_tag"] == "29103-EHT-0001"


def test_find_first_blank_row_advances_past_filled_rows(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    eda.add_zone("K1B Well Pad")
    r1 = eda.find_first_blank_row("K1B Well Pad", "eht_removal")
    eda.save_row("K1B Well Pad", "eht_removal", r1, {"trace_tag": "29103-EHT-0001"})
    r2 = eda.find_first_blank_row("K1B Well Pad", "eht_removal")
    assert r2 == r1 + 1


def test_find_duplicate_row_detects_case_insensitive_match(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    eda.add_zone("K1B Well Pad")
    r1 = eda.find_first_blank_row("K1B Well Pad", "eht_removal")
    eda.save_row("K1B Well Pad", "eht_removal", r1, {"trace_tag": "29103-EHT-0001"})
    dup = eda.find_duplicate_row("K1B Well Pad", "eht_removal", "29103-eht-0001")
    assert dup == r1
    assert eda.find_duplicate_row("K1B Well Pad", "eht_removal", "29103-eht-0001", exclude_row=r1) is None


def test_delete_rows_clears_in_place_never_shifts_rows(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    eda.add_zone("K1B Well Pad")
    r1 = eda.find_first_blank_row("K1B Well Pad", "eht_removal")
    eda.save_row("K1B Well Pad", "eht_removal", r1, {"trace_tag": "29103-EHT-0001"})
    r2 = eda.find_first_blank_row("K1B Well Pad", "eht_removal")
    eda.save_row("K1B Well Pad", "eht_removal", r2, {"trace_tag": "29103-EHT-0002"})

    eda.delete_rows("K1B Well Pad", "eht_removal", [r1])
    rows = eda.read_index_rows("K1B Well Pad", "eht_removal")
    assert [r["row"] for r in rows] == [r2]  # r1 gone, r2's row number unchanged
    assert eda.find_first_blank_row("K1B Well Pad", "eht_removal") == r1  # r1 is reusable again


def test_count_all_by_type_and_zone_summary(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    eda.add_zone("K1B Well Pad")
    row = eda.find_first_blank_row("K1B Well Pad", "eht_removal")
    eda.save_row("K1B Well Pad", "eht_removal", row, {"trace_tag": "29103-EHT-0001"})

    assert eda.count_all_by_type() == {"eht_removal": 1, "eht_rtd": 0, "eht_pre_insulation": 0}
    assert eda.zone_summary("K1B Well Pad") == {
        "eht_removal": {"total": 1}, "eht_rtd": {"total": 0}, "eht_pre_insulation": {"total": 0},
    }


def test_generate_preview_pdf_eht_removal_fills_real_fields(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    eda.add_zone("K1B Well Pad")
    row = eda.find_first_blank_row("K1B Well Pad", "eht_removal")
    eda.save_row("K1B Well Pad", "eht_removal", row, {
        "trace_tag": "29103-EHT-0001", "alarm": "Yes", "eht_type": "MI",
        "full_removal_item_1_yes": "AB", "test1_voltage": "500 VDC",
        "comments": "line1\nline2",
    })
    out_path = eda.generate_preview_pdf("K1B Well Pad", "eht_removal", row)
    assert out_path.exists()

    fields = PdfReader(str(out_path)).get_fields()
    assert fields["Text1"].get("/V") == "29103-EHT-0001"
    assert fields["Check Box3"].get("/V") == "/Yes"   # alarm=Yes
    assert fields["Check Box2"].get("/V") == "/Yes"   # eht_type=MI
    assert fields["Check Box1"].get("/V") in (None, "/Off")  # eht_type != SR
    assert fields["Text8"].get("/V") == "AB"
    assert fields["Check Box7"].get("/V") == "/Yes"   # test1_voltage=500 VDC


def test_generate_preview_pdf_eht_rtd_atc_uses_field_specific_on_state(isolated_app_dir):
    """The two ATC checkboxes use non-standard on-states (/ATC, /ATC (1)) -
    the one thing on this form that isn't a plain /Yes checkbox."""
    tmp_path, da = isolated_app_dir
    eda.add_zone("K1B Well Pad")
    row = eda.find_first_blank_row("K1B Well Pad", "eht_rtd")
    eda.save_row("K1B Well Pad", "eht_rtd", row, {
        "trace_number": "TR-001", "pre_ins_atc": "Y", "post_ins_atc": "Y",
    })
    out_path = eda.generate_preview_pdf("K1B Well Pad", "eht_rtd", row)
    fields = PdfReader(str(out_path)).get_fields()
    assert fields["ATC"].get("/V") == "/ATC"
    assert fields["ATC (1)"].get("/V") == "/ATC (1)"


def test_generate_preview_pdf_eht_rtd_comments_splits_across_three_lines(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    eda.add_zone("K1B Well Pad")
    row = eda.find_first_blank_row("K1B Well Pad", "eht_rtd")
    eda.save_row("K1B Well Pad", "eht_rtd", row, {
        "trace_number": "TR-001", "comments": "first\nsecond\nthird",
    })
    out_path = eda.generate_preview_pdf("K1B Well Pad", "eht_rtd", row)
    fields = PdfReader(str(out_path)).get_fields()
    assert fields["COMMENTS"].get("/V") == "first"
    assert fields["Text28"].get("/V") == "second"
    assert fields["Text29"].get("/V") == "third"


def test_generate_preview_pdf_eht_rtd_test_equip_log_writes_both_widgets(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    eda.add_zone("K1B Well Pad")
    row = eda.find_first_blank_row("K1B Well Pad", "eht_rtd")
    eda.save_row("K1B Well Pad", "eht_rtd", row, {
        "trace_number": "TR-001", "pre_ins_test_equip_log": "EQ-42",
    })
    out_path = eda.generate_preview_pdf("K1B Well Pad", "eht_rtd", row)
    fields = PdfReader(str(out_path)).get_fields()
    import eht_rtd_field_map as fm
    for pdf_field in fm.PRE_INS_TEST_EQUIP_LOG_FIELDS:
        assert fields[pdf_field].get("/V") == "EQ-42"


def test_generate_preview_pdf_never_touches_a_real_workbook(isolated_app_dir):
    """The live Electrical workbook is only ever read by generate_preview_pdf
    - each export copies the blank TEMPLATE, not the tracker itself."""
    tmp_path, da = isolated_app_dir
    eda.add_zone("K1B Well Pad")
    row = eda.find_first_blank_row("K1B Well Pad", "eht_removal")
    eda.save_row("K1B Well Pad", "eht_removal", row, {"trace_tag": "29103-EHT-0001"})
    before = eda.ELECTRICAL_WORKBOOK_PATH.read_bytes()
    eda.generate_preview_pdf("K1B Well Pad", "eht_removal", row)
    after = eda.ELECTRICAL_WORKBOOK_PATH.read_bytes()
    assert before == after


def test_unknown_zone_raises_keyerror(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    with pytest.raises(KeyError):
        eda.read_index_rows("Nonexistent", "eht_removal")


# --------------------------------------------------------------------------
# eht_pre_insulation - the third Electrical form (Sensei Index 2.9, Phase B).
# Unlike eht_removal/eht_rtd, its template was built from scratch (no
# original fillable PDF existed) - see build_eht_pre_insulation_template.py.
# --------------------------------------------------------------------------

def test_add_zone_creates_eht_pre_insulation_sheet(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    entry = eda.add_zone("K1B Well Pad")
    assert "eht_pre_insulation_sheet" in entry
    wb = openpyxl.load_workbook(eda.ELECTRICAL_WORKBOOK_PATH)
    assert entry["eht_pre_insulation_sheet"] in wb.sheetnames


def test_add_zone_eht_pre_insulation_header_row_matches_schema_labels(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    import eht_pre_insulation_schema
    entry = eda.add_zone("K1B Well Pad")
    wb = openpyxl.load_workbook(eda.ELECTRICAL_WORKBOOK_PATH)
    ws = wb[entry["eht_pre_insulation_sheet"]]
    header = [ws.cell(row=3, column=c).value for c in range(1, len(eht_pre_insulation_schema.LOG_COLUMNS) + 1)]
    assert header == [f["label"] for f in eht_pre_insulation_schema.LOG_COLUMNS]


def test_eht_pre_insulation_save_and_read_row_round_trips(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    eda.add_zone("K1B Well Pad")
    row = eda.find_first_blank_row("K1B Well Pad", "eht_pre_insulation")
    eda.save_row("K1B Well Pad", "eht_pre_insulation", row, {
        "trace_number": "TR-PI-001", "eht_controller_number": "EHTC-9",
        "panel_number": "P-12", "pre_ins_item_1_result": "JD",
    })
    full = eda.read_full_row("K1B Well Pad", "eht_pre_insulation", row)
    assert full["trace_number"] == "TR-PI-001"
    assert full["eht_controller_number"] == "EHTC-9"
    assert full["panel_number"] == "P-12"
    assert full["pre_ins_item_1_result"] == "JD"
    assert full["pre_ins_item_1_comments"] == ""  # untouched field stays blank


def test_eht_pre_insulation_read_index_rows_only_shows_rows_with_key_filled(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    eda.add_zone("K1B Well Pad")
    row = eda.find_first_blank_row("K1B Well Pad", "eht_pre_insulation")
    eda.save_row("K1B Well Pad", "eht_pre_insulation", row, {"panel_number": "P-12"})  # no trace_number
    assert eda.read_index_rows("K1B Well Pad", "eht_pre_insulation") == []

    eda.save_row("K1B Well Pad", "eht_pre_insulation", row, {"trace_number": "TR-PI-001"})
    rows = eda.read_index_rows("K1B Well Pad", "eht_pre_insulation")
    assert len(rows) == 1
    assert rows[0]["trace_number"] == "TR-PI-001"


def test_generate_preview_pdf_eht_pre_insulation_fills_real_fields(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    eda.add_zone("K1B Well Pad")
    row = eda.find_first_blank_row("K1B Well Pad", "eht_pre_insulation")
    eda.save_row("K1B Well Pad", "eht_pre_insulation", row, {
        "trace_number": "TR-PI-001", "eht_controller_number": "EHTC-9",
        "panel_number": "P-12", "pre_ins_item_1_result": "JD",
        "pre_ins_item_10_comments": "all clear",
        "megger_500_reading": "5000", "megger_500_result": "Passed",
        "comments": "line1\nline2",
        "yanda_rep_signature": "J. Doe",
    })
    out_path = eda.generate_preview_pdf("K1B Well Pad", "eht_pre_insulation", row)
    assert out_path.exists()

    fields = PdfReader(str(out_path)).get_fields()
    assert fields["trace_number"].get("/V") == "TR-PI-001"
    assert fields["eht_controller_number"].get("/V") == "EHTC-9"
    assert fields["panel_number"].get("/V") == "P-12"
    assert fields["pre_ins_item_1_result"].get("/V") == "JD"
    assert fields["pre_ins_item_10_comments"].get("/V") == "all clear"
    assert fields["megger_500_reading"].get("/V") == "5000"
    assert fields["megger_500_result"].get("/V") == "Passed"
    assert fields["comments"].get("/V") == "line1\nline2"
    assert fields["yanda_rep_signature"].get("/V") == "J. Doe"


def test_eht_pre_insulation_field_mapping_fidelity_against_its_own_template():
    """There's no 'original file's real widget names' cross-reference for
    a from-scratch template the way there is for eht_removal/eht_rtd - so
    this checks the template this form actually ships with directly:
    every schema field must have a FIELD_MAP entry, and every FIELD_MAP
    value must be a real field on the built template. This is the check
    that would catch a typo in a hand-chosen field name."""
    import eht_pre_insulation_schema as schema
    import eht_pre_insulation_field_map as fm
    from export_eht_pre_insulation_to_pdf import DEFAULT_TEMPLATE

    for field in schema.LOG_COLUMNS:
        assert field["id"] in fm.FIELD_MAP, f"{field['id']} has no FIELD_MAP entry"

    template_fields = set(PdfReader(str(DEFAULT_TEMPLATE)).get_fields().keys())
    for schema_id, pdf_field in fm.FIELD_MAP.items():
        assert pdf_field in template_fields, (
            f"FIELD_MAP['{schema_id}'] = '{pdf_field}' is not a real field on "
            f"{DEFAULT_TEMPLATE.name}"
        )
    # and the reverse: every real field on the template is actually used -
    # no dangling widget nothing ever writes to (the eht_removal/eht_rtd
    # precedent explicitly tolerates a couple of ARTIFACT_FIELDS, but this
    # template was purpose-built - it shouldn't have any).
    mapped = set(fm.FIELD_MAP.values())
    assert template_fields == mapped, (
        f"unused template fields: {template_fields - mapped}, "
        f"or FIELD_MAP entries with no matching template field: {mapped - template_fields}"
    )
