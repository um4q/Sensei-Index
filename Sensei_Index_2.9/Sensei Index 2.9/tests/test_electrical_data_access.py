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

    assert eda.count_all_by_type() == {
        "eht_removal": 1, "eht_rtd": 0, "eht_pre_insulation": 0, "torqueing": 0,
    }
    assert eda.zone_summary("K1B Well Pad") == {
        "eht_removal": {"total": 1}, "eht_rtd": {"total": 0},
        "eht_pre_insulation": {"total": 0}, "torqueing": {"total": 0},
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


def test_eht_pre_insulation_sheet_name_also_respects_the_31_char_limit(isolated_app_dir):
    """test_sheet_name_truncates_long_zone_names_safely (above) only checked
    eht_removal/eht_rtd's own truncation budgets - eht_pre_insulation has
    ITS OWN budget (SHEET_NAME_PREFIXES['eht_pre_insulation'] = 'EHT PreIns'
    is a different length than the other two prefixes), so it needs its own
    assertion rather than assuming the other two passing proves this one
    does too (found by an adversarial review of Phase B)."""
    tmp_path, da = isolated_app_dir
    long_name = "A Very Long Zone Name That Would Blow Past The Excel Sheet Name Limit"
    entry = eda.add_zone(long_name)
    assert len(entry["eht_pre_insulation_sheet"]) <= 31
    wb = openpyxl.load_workbook(eda.ELECTRICAL_WORKBOOK_PATH)
    assert entry["eht_pre_insulation_sheet"] in wb.sheetnames


def test_get_sheet_name_backfills_a_zone_registered_before_this_type_existed(isolated_app_dir):
    """A zone created on a build that only had eht_removal/eht_rtd (i.e.
    before eht_pre_insulation was registered) has no 'eht_pre_insulation_sheet'
    key in its registry entry and no corresponding workbook sheet. Every
    caller of get_sheet_name used to propagate an uncaught KeyError for
    this - found by an adversarial review of Phase B. get_sheet_name must
    now self-heal: create the missing sheet and persist the key, rather
    than fail forever for every zone that predates this equipment type."""
    tmp_path, da = isolated_app_dir
    entry = eda.add_zone("K1B Well Pad")

    # Simulate a legacy zone: strip the key AND remove the sheet, exactly
    # as if eht_pre_insulation had never existed when this zone was made.
    cfg = eda.load_config()
    legacy_entry = next(z for z in cfg["zones"] if z["name"] == "K1B Well Pad")
    old_sheet_name = legacy_entry.pop("eht_pre_insulation_sheet")
    eda.save_config(cfg)
    with eda._mutating_workbook() as wb:
        del wb[old_sheet_name]

    # Must not raise, and must actually work end-to-end.
    row = eda.find_first_blank_row("K1B Well Pad", "eht_pre_insulation")
    eda.save_row("K1B Well Pad", "eht_pre_insulation", row, {"trace_number": "TR-BACKFILL"})
    assert eda.read_full_row("K1B Well Pad", "eht_pre_insulation", row)["trace_number"] == "TR-BACKFILL"

    # The backfill must be PERSISTED, not just made to work once in memory.
    cfg2 = eda.load_config()
    healed_entry = next(z for z in cfg2["zones"] if z["name"] == "K1B Well Pad")
    assert "eht_pre_insulation_sheet" in healed_entry
    wb2 = openpyxl.load_workbook(eda.ELECTRICAL_WORKBOOK_PATH)
    assert healed_entry["eht_pre_insulation_sheet"] in wb2.sheetnames


def test_get_sheet_name_backfill_header_row_matches_schema_labels(isolated_app_dir):
    """The self-healed sheet must be a real, correctly-built Log sheet
    (header row included) - not just any sheet with the right name."""
    tmp_path, da = isolated_app_dir
    import eht_pre_insulation_schema
    entry = eda.add_zone("K1B Well Pad")
    cfg = eda.load_config()
    legacy_entry = next(z for z in cfg["zones"] if z["name"] == "K1B Well Pad")
    old_sheet_name = legacy_entry.pop("eht_pre_insulation_sheet")
    eda.save_config(cfg)
    with eda._mutating_workbook() as wb:
        del wb[old_sheet_name]

    eda.get_sheet_name("K1B Well Pad", "eht_pre_insulation")  # triggers the backfill
    cfg2 = eda.load_config()
    healed_sheet = next(z for z in cfg2["zones"] if z["name"] == "K1B Well Pad")["eht_pre_insulation_sheet"]
    wb2 = openpyxl.load_workbook(eda.ELECTRICAL_WORKBOOK_PATH)
    ws = wb2[healed_sheet]
    header = [ws.cell(row=3, column=c).value for c in range(1, len(eht_pre_insulation_schema.LOG_COLUMNS) + 1)]
    assert header == [f["label"] for f in eht_pre_insulation_schema.LOG_COLUMNS]


def test_zone_summary_zero_fills_every_registry_key_same_as_count_all_by_type(isolated_app_dir):
    """Both functions must share the same 'always has every registry key'
    contract (found by an adversarial review of Phase B: zone_summary()
    used to omit a key entirely instead of zero-filling it)."""
    tmp_path, da = isolated_app_dir
    eda.add_zone("K1B Well Pad")
    assert set(eda.zone_summary("K1B Well Pad").keys()) == set(eda.count_all_by_type().keys())
    assert eda.zone_summary("K1B Well Pad") == {
        "eht_removal": {"total": 0}, "eht_rtd": {"total": 0},
        "eht_pre_insulation": {"total": 0}, "torqueing": {"total": 0},
    }


def test_count_all_by_type_and_zone_summary_actually_count_an_eht_pre_insulation_row(isolated_app_dir):
    """The pre-existing count_all_by_type/zone_summary test only ever
    asserts a zero eht_pre_insulation count, which would pass even if the
    real counting logic for this type were broken - found by an adversarial
    review of Phase B. This saves a REAL row and checks a nonzero count
    comes back from both functions, for this type specifically."""
    tmp_path, da = isolated_app_dir
    eda.add_zone("K1B Well Pad")
    row = eda.find_first_blank_row("K1B Well Pad", "eht_pre_insulation")
    eda.save_row("K1B Well Pad", "eht_pre_insulation", row, {"trace_number": "TR-PI-001"})

    assert eda.count_all_by_type()["eht_pre_insulation"] == 1
    assert eda.zone_summary("K1B Well Pad")["eht_pre_insulation"] == {"total": 1}


def test_eht_pre_insulation_export_fills_every_hand_typed_field_with_a_distinct_value(isolated_app_dir):
    """test_generate_preview_pdf_eht_pre_insulation_fills_real_fields (above)
    only value-checks a handful of the 24 hand-typed FIELD_MAP entries - a
    transposition between two same-shaped fields (e.g. client_rep_date <->
    client_rep_signature) would pass every existing test, including the
    bijection-only field-mapping fidelity check, since both are still valid
    template field names either way. Found by an adversarial review of
    Phase B.

    Deliberately does NOT look up the expected PDF field name via
    eht_pre_insulation_field_map.FIELD_MAP - doing so would make this test
    exactly as blind as the bug it's meant to catch, since build_values_for_row
    ALSO reads its target field name from that same dict: if FIELD_MAP itself
    had a transposition, both the production code and a FIELD_MAP-driven
    test would agree with each other and the swap would still pass. Instead,
    every hand-typed schema id is listed here literally, independent of the
    map, and checked directly against the PDF field of THE SAME NAME - true
    by construction because this template's field names were chosen to be a
    clean identity mapping onto the schema's own ids (see FIELD_MAP's own
    docstring)."""
    tmp_path, da = isolated_app_dir
    eda.add_zone("K1B Well Pad")
    row = eda.find_first_blank_row("K1B Well Pad", "eht_pre_insulation")

    hand_typed_ids = [
        "trace_number", "eht_controller_number", "trace_part_number", "panel_number",
        "rtds_number", "circuit_number", "trace_line_number", "rev",
        "test_equip_model", "test_equip_serial", "cal_due_date",
        "megger_500_reading", "megger_500_result", "megger_1000_reading", "megger_1000_result",
        "megger_2500_reading", "megger_2500_result", "comments",
        "yanda_rep_name", "yanda_rep_date", "yanda_rep_signature",
        "client_rep_name", "client_rep_date", "client_rep_signature",
    ]
    # Every hand-typed (non-checklist-loop) schema id gets a value that
    # encodes its own id, so a swap between any two fields is unmistakable.
    values = {fid: f"VAL::{fid}" for fid in hand_typed_ids}
    eda.save_row("K1B Well Pad", "eht_pre_insulation", row, values)

    out_path = eda.generate_preview_pdf("K1B Well Pad", "eht_pre_insulation", row)
    fields = PdfReader(str(out_path)).get_fields()
    for fid in hand_typed_ids:
        assert fields[fid].get("/V") == f"VAL::{fid}", (
            f"'{fid}' did not land on the PDF's own '{fid}' field with its own value - "
            f"possible FIELD_MAP transposition"
        )


def test_export_eht_pre_insulation_cli_main_writes_a_pdf(isolated_app_dir, tmp_path, capsys):
    """No test invoked export_eht_pre_insulation_to_pdf.py's CLI main() at
    all (found by an adversarial review of Phase B) - only its DEFAULT_TEMPLATE
    was ever imported. Exercises --rows parsing and the actual file-write
    path end-to-end via the real workbook this fixture builds."""
    tmp_path_app, da = isolated_app_dir
    import sys
    import export_eht_pre_insulation_to_pdf as export_mod

    eda.add_zone("K1B Well Pad")
    row = eda.find_first_blank_row("K1B Well Pad", "eht_pre_insulation")
    sheet_name = eda.get_sheet_name("K1B Well Pad", "eht_pre_insulation")
    eda.save_row("K1B Well Pad", "eht_pre_insulation", row, {"trace_number": "TR-CLI-001"})

    output_dir = tmp_path / "cli_out"
    old_argv = sys.argv
    sys.argv = [
        "export_eht_pre_insulation_to_pdf.py", str(eda.ELECTRICAL_WORKBOOK_PATH),
        "--sheet", sheet_name, "--rows", str(row), "--output-dir", str(output_dir),
    ]
    try:
        export_mod.main()
    finally:
        sys.argv = old_argv

    out_files = list(output_dir.glob("*.pdf"))
    assert len(out_files) == 1
    assert PdfReader(str(out_files[0])).get_fields()["trace_number"].get("/V") == "TR-CLI-001"


# --------------------------------------------------------------------------
# Mass/batch export - the user's own request: "I WANT IT LIKE THE
# INSTRUMENTATION DASH BOARD SAME FEATURES AND EVERYTHING ESPECIALLY MASS
# EXPORT." Electrical's run_export()/electrical_status.json mirror
# data_access.py's own run_export()/equipment_status.json, scoped to what
# actually applies (no 'flagged' mode, no signature option - see
# run_export()'s own docstring).
# --------------------------------------------------------------------------

def _three_rows(zone_name="K1B Well Pad"):
    eda.add_zone(zone_name)
    tags = ["TR-001", "TR-002", "TR-003"]
    for tag in tags:
        row = eda.find_first_blank_row(zone_name, "eht_pre_insulation")
        eda.save_row(zone_name, "eht_pre_insulation", row, {"trace_number": tag})
    return tags


def test_get_and_set_electrical_status_round_trip(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    _three_rows()
    assert eda.get_electrical_status("K1B Well Pad", "eht_pre_insulation", "TR-001") == {"export": False}
    eda.set_electrical_status("K1B Well Pad", "eht_pre_insulation", "TR-001", export=True)
    assert eda.get_electrical_status("K1B Well Pad", "eht_pre_insulation", "TR-001") == {"export": True}
    # untouched rows stay at the default
    assert eda.get_electrical_status("K1B Well Pad", "eht_pre_insulation", "TR-002") == {"export": False}


def test_bulk_set_electrical_status_writes_the_file_once_for_many_keys(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    tags = _three_rows()
    keys = [("K1B Well Pad", "eht_pre_insulation", t) for t in tags]
    eda.bulk_set_electrical_status(keys, export=True)
    for t in tags:
        assert eda.get_electrical_status("K1B Well Pad", "eht_pre_insulation", t) == {"export": True}


def test_read_index_rows_with_export_status_merges_the_flag_per_row(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    _three_rows()
    eda.set_electrical_status("K1B Well Pad", "eht_pre_insulation", "TR-002", export=True)
    rows = eda.read_index_rows_with_export_status("K1B Well Pad", "eht_pre_insulation")
    by_tag = {r["trace_number"]: r["export"] for r in rows}
    assert by_tag == {"TR-001": False, "TR-002": True, "TR-003": False}


def test_run_export_all_mode_writes_every_row_regardless_of_export_flag(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    _three_rows()
    written = eda.run_export("K1B Well Pad", "eht_pre_insulation", mode="all")
    names = {p.stem for p in written}
    assert names == {"TR-001", "TR-002", "TR-003"}
    for p in written:
        assert p.exists()


def test_run_export_selected_mode_only_writes_checked_rows(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    _three_rows()
    eda.set_electrical_status("K1B Well Pad", "eht_pre_insulation", "TR-001", export=True)
    eda.set_electrical_status("K1B Well Pad", "eht_pre_insulation", "TR-003", export=True)
    written = eda.run_export("K1B Well Pad", "eht_pre_insulation", mode="selected")
    assert {p.stem for p in written} == {"TR-001", "TR-003"}


def test_run_export_selected_mode_clears_the_export_flag_afterward_by_default(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    _three_rows()
    eda.set_electrical_status("K1B Well Pad", "eht_pre_insulation", "TR-001", export=True)
    eda.run_export("K1B Well Pad", "eht_pre_insulation", mode="selected")
    assert eda.get_electrical_status("K1B Well Pad", "eht_pre_insulation", "TR-001") == {"export": False}


def test_run_export_selected_mode_can_keep_the_export_flag_when_asked(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    _three_rows()
    eda.set_electrical_status("K1B Well Pad", "eht_pre_insulation", "TR-001", export=True)
    eda.run_export("K1B Well Pad", "eht_pre_insulation", mode="selected", clear_after_selected=False)
    assert eda.get_electrical_status("K1B Well Pad", "eht_pre_insulation", "TR-001") == {"export": True}


def test_run_export_returns_empty_list_when_nothing_matches(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    _three_rows()  # none flagged for export
    assert eda.run_export("K1B Well Pad", "eht_pre_insulation", mode="selected") == []


def test_run_export_merge_produces_one_combined_pdf_covering_every_written_row(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    _three_rows()
    written = eda.run_export("K1B Well Pad", "eht_pre_insulation", mode="all", merge=True)
    assert written[-1].name.startswith("Combined_Export_")
    merged = PdfReader(str(written[-1]))
    assert len(merged.pages) == 3  # one page per exported row


def test_run_export_respects_suffix_subfolder_and_date_options(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    _three_rows()
    written = eda.run_export("K1B Well Pad", "eht_pre_insulation", mode="all",
                              suffix="DEV", subfolder="myrun", include_date_in_filename=True)
    import datetime
    today = datetime.date.today().isoformat()
    for p in written:
        assert p.parent.name == "myrun"
        assert "DEV" in p.name
        assert today in p.name


def test_run_export_never_touches_a_real_workbook(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    _three_rows()
    before = eda.ELECTRICAL_WORKBOOK_PATH.read_bytes()
    eda.run_export("K1B Well Pad", "eht_pre_insulation", mode="all")
    after = eda.ELECTRICAL_WORKBOOK_PATH.read_bytes()
    assert before == after


# --------------------------------------------------------------------------
# torqueing - the fourth Electrical form (YCQE-E&I-014 Rev.0). Unlike
# eht_pre_insulation, the original PDF IS a real fillable form (not a
# scan) - see torqueing_field_map.py's own docstring for how its 138
# fields were reverse-engineered by row/column position. It's also the
# only Electrical form with a Yanda signature stamp (the user's own
# request: "can add signature too as the instrumentation dashboard has
# it") - export_torqueing_to_pdf.py's stamp_signature() mirrors
# export_to_pdf.py's mechanism exactly.
# --------------------------------------------------------------------------

def test_add_zone_creates_torqueing_sheet(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    entry = eda.add_zone("K1B Well Pad")
    assert "torqueing_sheet" in entry
    wb = openpyxl.load_workbook(eda.ELECTRICAL_WORKBOOK_PATH)
    assert entry["torqueing_sheet"] in wb.sheetnames


def test_add_zone_torqueing_header_row_matches_schema_labels(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    import torqueing_schema
    entry = eda.add_zone("K1B Well Pad")
    wb = openpyxl.load_workbook(eda.ELECTRICAL_WORKBOOK_PATH)
    ws = wb[entry["torqueing_sheet"]]
    header = [ws.cell(row=3, column=c).value for c in range(1, len(torqueing_schema.LOG_COLUMNS) + 1)]
    assert header == [f["label"] for f in torqueing_schema.LOG_COLUMNS]


def test_torqueing_sheet_name_respects_the_31_char_limit(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    long_name = "A Very Long Zone Name That Would Blow Past The Excel Sheet Name Limit"
    entry = eda.add_zone(long_name)
    assert len(entry["torqueing_sheet"]) <= 31
    wb = openpyxl.load_workbook(eda.ELECTRICAL_WORKBOOK_PATH)
    assert entry["torqueing_sheet"] in wb.sheetnames


def test_torqueing_save_and_read_row_round_trips(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    eda.add_zone("K1B Well Pad")
    row = eda.find_first_blank_row("K1B Well Pad", "torqueing")
    eda.save_row("K1B Well Pad", "torqueing", row, {
        "torque_record_number": "TR-100", "reference_tag_number": "TAG-001",
        "system_number": "K1B- EHouse", "bolt_row_1_no": "1", "bolt_row_1_tag": "BOLT-1",
        "bolt_row_2_no": "2",
    })
    full = eda.read_full_row("K1B Well Pad", "torqueing", row)
    assert full["torque_record_number"] == "TR-100"
    assert full["reference_tag_number"] == "TAG-001"
    assert full["system_number"] == "K1B- EHouse"
    assert full["bolt_row_1_no"] == "1"
    assert full["bolt_row_1_tag"] == "BOLT-1"
    assert full["bolt_row_2_no"] == "2"
    assert full["bolt_row_1_grade"] == ""  # untouched field stays blank
    assert full["bolt_row_15_date"] == ""  # last row, untouched, stays blank


def test_torqueing_read_index_rows_only_shows_rows_with_key_filled(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    eda.add_zone("K1B Well Pad")
    row = eda.find_first_blank_row("K1B Well Pad", "torqueing")
    eda.save_row("K1B Well Pad", "torqueing", row, {"reference_tag_number": "TAG-001"})  # no torque_record_number
    assert eda.read_index_rows("K1B Well Pad", "torqueing") == []

    eda.save_row("K1B Well Pad", "torqueing", row, {"torque_record_number": "TR-100"})
    rows = eda.read_index_rows("K1B Well Pad", "torqueing")
    assert len(rows) == 1
    assert rows[0]["torque_record_number"] == "TR-100"


def test_generate_preview_pdf_torqueing_fills_real_fields_across_the_whole_form(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    eda.add_zone("K1B Well Pad")
    row = eda.find_first_blank_row("K1B Well Pad", "torqueing")
    eda.save_row("K1B Well Pad", "torqueing", row, {
        "torque_record_number": "TR-100", "system_number": "K1B- EHouse",
        "reference_tag_number": "TAG-001", "torque_wrench_manufacturer": "Snap-On",
        "bolt_row_1_no": "1", "bolt_row_1_tag": "BOLT-1", "bolt_row_1_grade": "8",
        "bolt_row_2_no": "2", "bolt_row_2_tag": "BOLT-2",
        # Row 8: a MIDDLE row (3-14 were previously never touched by any
        # PDF-fill test), and the size/torque_value/torqued_by/witnessed_by
        # columns (previously never touched by ANY row) - see
        # test_torqueing_bolt_table_maps_every_row_and_column_to_the_correct_field
        # for the exhaustive, formula-derived version of this same check.
        "bolt_row_8_size": "1/2 in", "bolt_row_8_torque_value": "75",
        "bolt_row_8_torqued_by": "AB", "bolt_row_8_witnessed_by": "CD",
        "bolt_row_15_no": "15", "bolt_row_15_date": "2026/09/10",
        "torque_spec_document_reference": "SPEC-1", "comments_na": "Y",
        "comments": "all good", "yanda_rep_name": "Dana Eshleyah",
        "client_rep_name": "John Smith",
    })
    out_path = eda.generate_preview_pdf("K1B Well Pad", "torqueing", row)
    assert out_path.exists()

    fields = PdfReader(str(out_path)).get_fields()
    assert fields["Text131"].get("/V") == "TR-100"
    assert fields["Dropdown1"].get("/V") == "K1B- EHouse"
    assert fields["Text134"].get("/V") == "TAG-001"
    assert fields["Text138"].get("/V") == "Snap-On"
    assert fields["NO"].get("/V") == "1"
    assert fields["TAG #"].get("/V") == "BOLT-1"
    assert fields["GRADE"].get("/V") == "8"
    assert fields["Text10"].get("/V") == "2"
    assert fields["Text11"].get("/V") == "BOLT-2"
    assert fields["Text61"].get("/V") == "1/2 in"   # bolt_row_8_size
    assert fields["Text62"].get("/V") == "75"        # bolt_row_8_torque_value
    assert fields["Text63"].get("/V") == "AB"        # bolt_row_8_torqued_by
    assert fields["Text64"].get("/V") == "CD"        # bolt_row_8_witnessed_by
    assert fields["Text114"].get("/V") == "15"      # bolt_row_15_no
    assert fields["Text148"].get("/V") == "2026/09/10"  # bolt_row_15_date
    assert fields["TORQUE SPECIFICATION DOCUMENT REFERENCE"].get("/V") == "SPEC-1"
    assert fields["N/A"].get("/V") == "/N/A"
    assert fields["COMMENTS"].get("/V") == "all good"
    assert fields["YANDA REPRESENTATIVE"].get("/V") == "Dana Eshleyah"
    assert fields["CLIENT REPRESENTATIVE"].get("/V") == "John Smith"


def test_generate_preview_pdf_torqueing_comments_na_off_by_default(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    eda.add_zone("K1B Well Pad")
    row = eda.find_first_blank_row("K1B Well Pad", "torqueing")
    eda.save_row("K1B Well Pad", "torqueing", row, {"torque_record_number": "TR-100"})
    out_path = eda.generate_preview_pdf("K1B Well Pad", "torqueing", row)
    fields = PdfReader(str(out_path)).get_fields()
    assert fields["N/A"].get("/V") in (None, "/Off")


def test_generate_preview_pdf_torqueing_stamps_yanda_signature_by_default(isolated_app_dir):
    """The signature stamp is a page-content overlay, not a fillable field
    (the original PDF has no signature field for either representative) -
    detected here via the extra merged-in XObject stamp_signature() adds,
    the same signal a real PDF viewer would show as visible ink."""
    tmp_path, da = isolated_app_dir
    eda.add_zone("K1B Well Pad")
    row = eda.find_first_blank_row("K1B Well Pad", "torqueing")
    eda.save_row("K1B Well Pad", "torqueing", row, {"torque_record_number": "TR-100"})
    out_path = eda.generate_preview_pdf("K1B Well Pad", "torqueing", row)
    page = PdfReader(str(out_path)).pages[0]
    xobjects = page.get("/Resources", {}).get("/XObject", {})
    assert any(str(k).startswith("/FormXob") for k in xobjects.keys())


def test_run_export_torqueing_respects_include_signature_toggle(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    eda.add_zone("K1B Well Pad")
    row = eda.find_first_blank_row("K1B Well Pad", "torqueing")
    eda.save_row("K1B Well Pad", "torqueing", row, {"torque_record_number": "TR-100"})

    written_with = eda.run_export("K1B Well Pad", "torqueing", mode="all", include_signature=True)
    page_with = PdfReader(str(written_with[0])).pages[0]
    has_stamp = any(str(k).startswith("/FormXob")
                    for k in page_with.get("/Resources", {}).get("/XObject", {}).keys())
    assert has_stamp

    written_without = eda.run_export("K1B Well Pad", "torqueing", mode="all",
                                       include_signature=False, suffix="nosig")
    page_without = PdfReader(str(written_without[0])).pages[0]
    has_stamp2 = any(str(k).startswith("/FormXob")
                      for k in page_without.get("/Resources", {}).get("/XObject", {}).keys())
    assert not has_stamp2


def test_run_export_include_signature_is_harmless_for_forms_without_a_stamp(isolated_app_dir):
    """include_signature only means something for a type that declares
    supports_signature_stamp - passing it for eht_removal (whose fill_pdf
    doesn't even accept the kwarg) must not raise."""
    tmp_path, da = isolated_app_dir
    eda.add_zone("K1B Well Pad")
    row = eda.find_first_blank_row("K1B Well Pad", "eht_removal")
    eda.save_row("K1B Well Pad", "eht_removal", row, {"trace_tag": "29103-EHT-0001"})
    written = eda.run_export("K1B Well Pad", "eht_removal", mode="all", include_signature=False)
    assert len(written) == 1


def test_torqueing_field_mapping_fidelity_against_its_own_template():
    """Every schema field (except comments_na, special-cased through
    COMMENTS_NA_CHECKBOX) must have a FIELD_MAP entry pointing at a real
    field on the template, every FIELD_MAP value must be a real field,
    and together with the N/A checkbox they must account for EVERY field
    on the template - a from-scratch bijection check, the reverse-
    engineered-map equivalent of eht_pre_insulation's identity-map check."""
    import torqueing_schema as schema
    import torqueing_field_map as fm
    from export_torqueing_to_pdf import DEFAULT_TEMPLATE

    for field in schema.LOG_COLUMNS:
        if field["id"] == "comments_na":
            continue
        assert field["id"] in fm.FIELD_MAP, f"{field['id']} has no FIELD_MAP entry"

    template_fields = set(PdfReader(str(DEFAULT_TEMPLATE)).get_fields().keys())
    for schema_id, pdf_field in fm.FIELD_MAP.items():
        assert pdf_field in template_fields, (
            f"FIELD_MAP['{schema_id}'] = '{pdf_field}' is not a real field on {DEFAULT_TEMPLATE.name}"
        )
    accounted_for = set(fm.FIELD_MAP.values()) | {fm.COMMENTS_NA_CHECKBOX["field"]}
    assert template_fields == accounted_for, (
        f"unaccounted template fields: {template_fields - accounted_for}, "
        f"or map entries with no matching template field: {accounted_for - template_fields}"
    )


def test_torqueing_bolt_table_maps_every_row_and_column_to_the_correct_field():
    """The bijection test above only checks FIELD_MAP's *value set* against
    the template's field set - two entries with the same shape (e.g. two
    rows' "tag" columns, or "torqued_by" swapped with "witnessed_by"
    within one row) can be transposed and it still passes, because the
    set of values is unchanged. This test instead re-derives each bolt-
    table cell's expected PDF field name independently, from the original
    form's own numbering pattern (not by reading FIELD_MAP), and checks
    every one of the 120 cells against it individually - so a transposition
    like that is actually caught.

    The pattern (confirmed both by clustering every widget's own /Rect
    from reference_material/YCQE-EI-014_Torqueing_Report/
    torqueing_field_positions_raw.json into rows/columns, and by manual
    review against the template's real field dictionary when
    torqueing_field_map.py was first built):
      - Row 1 uses the original author's own human-readable names.
      - Rows 2-15, across the 7 columns no/tag/grade/size/torque_value/
        torqued_by/witnessed_by, are "Text##" and perfectly sequential
        PER ROW: row r's "no" column is Text{8*r - 6}, and the next 6
        columns are the next 6 consecutive numbers.
      - The "date" column is NOT sequential with the rest - the original
        author added it in a separate editing pass (a real quirk of the
        source PDF, not a mapping error) - its values are listed
        explicitly below rather than derived from a formula.
    """
    import torqueing_field_map as fm

    row_1_names = ["NO", "TAG #", "GRADE", "SIZE", "VALUE (FT/LB", "BY INITIAL", "BY INITIAL (1)"]
    columns = ["no", "tag", "grade", "size", "torque_value", "torqued_by", "witnessed_by"]
    date_by_row = {
        1: "yyyy/mm/dd", 2: "Text123", 3: "Text124", 4: "Text125", 5: "Text126",
        6: "Text132", 7: "Text140", 8: "Text141", 9: "Text142", 10: "Text143",
        11: "Text144", 12: "Text145", 13: "Text146", 14: "Text147", 15: "Text148",
    }

    checked = 0
    for row in range(1, 16):
        for col_index, col_id in enumerate(columns):
            expected = row_1_names[col_index] if row == 1 else f"Text{8 * row - 6 + col_index}"
            fid = f"bolt_row_{row}_{col_id}"
            assert fm.FIELD_MAP[fid] == expected, (
                f"FIELD_MAP['{fid}'] = {fm.FIELD_MAP[fid]!r}, expected {expected!r} "
                f"(row {row}, column '{col_id}')"
            )
            checked += 1
        date_fid = f"bolt_row_{row}_date"
        assert fm.FIELD_MAP[date_fid] == date_by_row[row], (
            f"FIELD_MAP['{date_fid}'] = {fm.FIELD_MAP[date_fid]!r}, expected {date_by_row[row]!r} (row {row})"
        )
        checked += 1
    assert checked == 120  # all 15 rows x 8 columns, no silent gaps


def test_torqueing_template_has_no_baked_in_sample_data(isolated_app_dir):
    """The original PDF this template came from had real sample values in
    its 4 header fields (Customer Name/Project Name/Contract#/Location) -
    confirmed cleared when the checked-in template was built (see
    torqueing_field_map.py's own docstring re: this exact precaution)."""
    from export_torqueing_to_pdf import DEFAULT_TEMPLATE
    fields = PdfReader(str(DEFAULT_TEMPLATE)).get_fields()
    non_blank = {k: v.get("/V") for k, v in fields.items()
                 if v.get("/V") and str(v.get("/V")).strip() not in ("", " ", "  ")}
    # The N/A checkbox's own /Off default state is not "sample data".
    non_blank.pop("N/A", None)
    assert non_blank == {}
