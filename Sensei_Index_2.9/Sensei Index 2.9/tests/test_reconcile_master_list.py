# -*- coding: utf-8 -*-
"""Phase 11.1 - data_access.reconcile_master_list()."""


def _seed_master_list(da, tmp_path, items, sheet_series_map=None):
    """Writes a master_list.json snapshot directly (bypassing the .xlsx
    parser, which Phase 10's own tests already cover) so these tests focus
    purely on the reconciliation logic."""
    da.save_master_list({
        "imported_at": "2026-08-30T00:00:00",
        "source_file": "Instrumentation_Master_List.xlsx",
        "source_mtime": 0,
        "sheet_series_map": sheet_series_map or {},
        "items": items,
    })


def _ml_item(tag, kind, **overrides):
    item = {
        "tag_raw": tag, "tag": tag, "area": tag.split("-")[0], "tag_type": tag.split("-")[1],
        "service": "", "type_desc": "", "kind": kind, "pid": "", "line_number": "",
        "module_id": "", "ewp": "", "model": "", "manufacturer": "", "install_details": "",
        "remarks": "", "ml_received": False, "ml_installed": False, "source_sheet": "Sheet1",
        "mapped_series": 29103,
    }
    item.update(overrides)
    return item


def test_none_when_nothing_imported(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    assert da.reconcile_master_list() is None


def test_matched_padded_tag_finds_unpadded_tracker_row(isolated_app_dir):
    """The exact Phase 11 acceptance criterion: a master-list padded tag
    matches the tracker's unpadded spelling."""
    tmp_path, da = isolated_app_dir
    row = da.find_first_blank_row(29103, "transmitter")
    da.save_row(29103, "transmitter", row, {"tag": "29103-FIT-0916", "model": "8800DF"})
    _seed_master_list(da, tmp_path, [
        _ml_item("29103-FIT-0916", "transmitter", tag_raw="29103-FIT -0916", model="8800DF"),
    ])

    result = da.reconcile_master_list()
    assert len(result["matched"]) == 1
    assert result["matched"][0]["master"]["tag"] == "29103-FIT-0916"
    assert result["matched"][0]["tracker"]["row"] == row
    assert result["matched"][0]["flags"] == []
    assert result["missing"] == []


def test_missing_when_no_tracker_row_anywhere(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    _seed_master_list(da, tmp_path, [_ml_item("29103-PIT-2171", "transmitter")])
    result = da.reconcile_master_list()
    assert len(result["missing"]) == 1
    assert result["missing"][0]["tag"] == "29103-PIT-2171"
    assert result["matched"] == []


def test_orphan_when_tracker_row_not_in_master_list(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    row = da.find_first_blank_row(29103, "transmitter")
    da.save_row(29103, "transmitter", row, {"tag": "29103-EXTRA-0001"})
    _seed_master_list(da, tmp_path, [_ml_item("29103-PIT-2171", "transmitter")])

    result = da.reconcile_master_list()
    assert len(result["orphans"]) == 1
    assert result["orphans"][0]["key_value"] == "29103-EXTRA-0001"
    assert len(result["missing"]) == 1  # the master item is still separately "missing"


def test_out_of_scope_counted_not_matched_or_missing(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    _seed_master_list(da, tmp_path, [
        _ml_item("29103-TW-0100", "out_of_scope"),
        _ml_item("29103-PSV-0905", "out_of_scope"),
        _ml_item("29103-PIT-2171", "transmitter"),
    ])
    result = da.reconcile_master_list()
    assert result["out_of_scope_count"] == 2
    assert len(result["out_of_scope_items"]) == 2
    assert len(result["missing"]) == 1  # only the in-scope item


def test_matched_plus_missing_equals_all_in_scope_items(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    row = da.find_first_blank_row(29103, "transmitter")
    da.save_row(29103, "transmitter", row, {"tag": "29103-PIT-2171"})
    _seed_master_list(da, tmp_path, [
        _ml_item("29103-PIT-2171", "transmitter"),   # matched
        _ml_item("29103-FIT-0916", "transmitter"),   # missing
        _ml_item("29103-XV-0100", "valve"),          # missing
        _ml_item("29103-TW-0100", "out_of_scope"),   # excluded entirely
    ])
    result = da.reconcile_master_list()
    in_scope_total = 3  # transmitter x2 + valve x1
    assert len(result["matched"]) + len(result["missing"]) == in_scope_total


def test_installed_mismatch_flag(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    row = da.find_first_blank_row(29103, "transmitter")
    da.save_row(29103, "transmitter", row, {"tag": "29103-PIT-2171"})
    da.set_status(29103, "transmitter", "29103-PIT-2171", installed=False)
    _seed_master_list(da, tmp_path, [_ml_item("29103-PIT-2171", "transmitter", ml_installed=True)])

    result = da.reconcile_master_list()
    assert result["matched"][0]["flags"] == ["installed_mismatch"]


def test_no_mismatch_flag_when_installed_agrees(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    row = da.find_first_blank_row(29103, "transmitter")
    da.save_row(29103, "transmitter", row, {"tag": "29103-PIT-2171"})
    da.set_status(29103, "transmitter", "29103-PIT-2171", installed=True)
    _seed_master_list(da, tmp_path, [_ml_item("29103-PIT-2171", "transmitter", ml_installed=True)])

    result = da.reconcile_master_list()
    assert "installed_mismatch" not in result["matched"][0]["flags"]


def test_model_mismatch_is_case_and_space_insensitive(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    row = da.find_first_blank_row(29103, "transmitter")
    da.save_row(29103, "transmitter", row, {"tag": "29103-PIT-2171", "model": "3051 TG3 A2B21"})
    _seed_master_list(da, tmp_path, [
        _ml_item("29103-PIT-2171", "transmitter", model="3051tg3a2b21"),  # same, different case/spacing
    ])
    result = da.reconcile_master_list()
    assert "model_mismatch" not in result["matched"][0]["flags"]


def test_model_mismatch_flagged_when_genuinely_different(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    row = da.find_first_blank_row(29103, "transmitter")
    da.save_row(29103, "transmitter", row, {"tag": "29103-PIT-2171", "model": "3051TG3A2B21"})
    _seed_master_list(da, tmp_path, [_ml_item("29103-PIT-2171", "transmitter", model="WIKA-233")])
    result = da.reconcile_master_list()
    assert "model_mismatch" in result["matched"][0]["flags"]


def test_model_mismatch_skipped_when_either_side_blank(isolated_app_dir):
    """A blank model on either side isn't a 'mismatch' - it's just unknown."""
    tmp_path, da = isolated_app_dir
    row = da.find_first_blank_row(29103, "transmitter")
    da.save_row(29103, "transmitter", row, {"tag": "29103-PIT-2171"})  # model left blank
    _seed_master_list(da, tmp_path, [_ml_item("29103-PIT-2171", "transmitter", model="WIKA-233")])
    result = da.reconcile_master_list()
    assert "model_mismatch" not in result["matched"][0]["flags"]


def test_valve_model_mismatch_uses_valve_model_field(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    row = da.find_first_blank_row(29103, "valve")
    da.save_row(29103, "valve", row, {"equip_number": "29103-XV-0100", "valve_model": "FISHER-9000"})
    _seed_master_list(da, tmp_path, [_ml_item("29103-XV-0100", "valve", model="MASONEILAN-1")])
    result = da.reconcile_master_list()
    assert "model_mismatch" in result["matched"][0]["flags"]


def test_matching_ignores_mapped_series_looks_across_all_series(isolated_app_dir):
    """11.1: match by canonical_tag across ALL registered series of that
    kind - a master item isn't required to be tracked under its sheet's
    mapped_series to count as matched."""
    tmp_path, da = isolated_app_dir
    row = da.find_first_blank_row(100, "transmitter")  # tracked under series 100
    da.save_row(100, "transmitter", row, {"tag": "29103-PIT-2171"})
    _seed_master_list(da, tmp_path, [
        _ml_item("29103-PIT-2171", "transmitter", mapped_series=29103),  # sheet mapped to 29103
    ])
    result = da.reconcile_master_list()
    assert len(result["matched"]) == 1
    assert result["matched"][0]["tracker"]["series"] == 100
