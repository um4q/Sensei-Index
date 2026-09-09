# -*- coding: utf-8 -*-
"""Phase 14 - the global search index."""
import time


def _seed_master_list(da, items):
    da.save_master_list({
        "imported_at": "2026-08-30T00:00:00", "source_file": "x.xlsx", "source_mtime": 0,
        "sheet_series_map": {}, "items": items,
    })


def _ml_item(tag, kind, **overrides):
    item = {
        "tag_raw": tag, "tag": tag, "area": tag.split("-")[0], "tag_type": tag.split("-")[1],
        "service": "SVC", "type_desc": "", "kind": kind, "pid": "", "line_number": "",
        "module_id": "", "ewp": "", "model": "", "manufacturer": "", "install_details": "",
        "remarks": "", "ml_received": False, "ml_installed": False, "source_sheet": "Sheet1",
        "mapped_series": 29103,
    }
    item.update(overrides)
    return item


def test_search_blank_query_returns_nothing(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    assert da.search_index("") == []
    assert da.search_index("   ") == []


def test_search_finds_by_tag(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    row = da.find_first_blank_row(29103, "transmitter")
    da.save_row(29103, "transmitter", row, {"tag": "29103-PIT-2171"})

    results = da.search_index("PIT-2171")
    assert len(results) == 1
    assert results[0]["source"] == "tracker"
    assert results[0]["key_value"] == "29103-PIT-2171"
    assert results[0]["series"] == 29103
    assert results[0]["kind"] == "transmitter"


def test_search_finds_by_serial_number_from_anywhere_in_the_app(isolated_app_dir):
    """The exact Phase 14 acceptance criterion: a serial number that
    exists on exactly one valve is findable from anywhere, in under a
    second, and lands on the row."""
    tmp_path, da = isolated_app_dir
    row = da.find_first_blank_row(29103, "valve")
    da.save_row(29103, "valve", row, {"equip_number": "29103-XV-0100", "valve_serial": "VS-UNIQUE-42"})

    t0 = time.time()
    results = da.search_index("VS-UNIQUE-42")
    elapsed = time.time() - t0

    assert elapsed < 1.0
    assert len(results) == 1
    assert results[0]["key_value"] == "29103-XV-0100"
    assert results[0]["row"] == row


def test_search_is_case_insensitive_and_substring(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    row = da.find_first_blank_row(29103, "transmitter")
    da.save_row(29103, "transmitter", row, {"tag": "29103-PIT-2171", "model": "ROSEMOUNT-3051"})
    assert da.search_index("rosemount") != []
    assert da.search_index("3051") != []


def test_search_finds_master_list_only_items(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    _seed_master_list(da, [_ml_item("29103-FIT-0916", "transmitter", service="VAPOUR OUTLET")])
    results = da.search_index("FIT-0916")
    assert len(results) == 1
    assert results[0]["source"] == "master"
    assert results[0]["key_value"] == "29103-FIT-0916"
    assert "Master list" in results[0]["label"]


def test_search_excludes_out_of_scope_master_items(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    _seed_master_list(da, [_ml_item("29103-TW-0100", "out_of_scope", service="THERMOWELL SVC")])
    assert da.search_index("TW-0100") == []


def test_search_respects_limit(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    for i in range(10):
        row = da.find_first_blank_row(29103, "transmitter")
        da.save_row(29103, "transmitter", row, {"tag": f"29103-PIT-{i:04d}", "service": "COMMON SVC"})
    results = da.search_index("COMMON SVC", limit=3)
    assert len(results) == 3


def test_cache_invalidates_on_workbook_mutation(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    assert da.search_index("NEWLY-ADDED") == []
    row = da.find_first_blank_row(29103, "transmitter")
    da.save_row(29103, "transmitter", row, {"tag": "29103-PIT-NEWLY-ADDED"})
    # no explicit invalidate_search_index() call needed - the workbook's
    # mtime changed, which get_search_index() checks on every call.
    assert da.search_index("NEWLY-ADDED") != []


def test_cache_invalidates_on_master_list_reimport(tmp_path, isolated_app_dir):
    tmp_path, da = isolated_app_dir
    assert da.search_index("FRESH-IMPORT") == []

    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    ws.append(["Tag Number", "Service", "Instrument Type Description"])
    ws.append(["29103-PIT-FRESH-IMPORT", "SVC", "PRESSURE INDICATING TRANSMITTER"])
    ml_path = tmp_path / "ml.xlsx"
    wb.save(ml_path)

    da.import_master_list(ml_path, {"Sheet1": 29103})
    # import_master_list() doesn't touch the workbook at all, so this only
    # works if it explicitly calls invalidate_search_index().
    assert da.search_index("FRESH-IMPORT") != []


def test_search_index_entries_are_flat_and_serializable(isolated_app_dir):
    """No live openpyxl objects leaking into the index - the GUI layer
    needs to hold onto these across a debounce timer."""
    tmp_path, da = isolated_app_dir
    row = da.find_first_blank_row(29103, "transmitter")
    da.save_row(29103, "transmitter", row, {"tag": "29103-PIT-2171"})
    import json
    json.dumps(da.search_index("PIT"))  # raises if anything isn't JSON-safe
