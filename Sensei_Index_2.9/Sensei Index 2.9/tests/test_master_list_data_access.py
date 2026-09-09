# -*- coding: utf-8 -*-
"""Phase 10.4 - data_access.py's master-list orchestration layer:
import_master_list / load_master_list / master_list_items /
master_list_needs_reimport."""
import time

import openpyxl
import pytest


def _make_master_list_xlsx(path):
    wb = openpyxl.Workbook()
    ws1 = wb.active
    ws1.title = "29103-K1B Pad"
    ws1.append(["Tag Number", "Service", "Instrument Type Description", "Model", "Manufacturer"])
    ws1.append(["29103-PIT -2171", "SVC A", "PRESSURE INDICATING TRANSMITTER", "233.34", "WIKA"])
    ws1.append(["29103-XV  -0100", "SVC B", "SHUTDOWN VALVE", "", ""])
    ws1.append(["29103-TW  -0100", "SVC C", "THERMOWELL", "", ""])
    ws2 = wb.create_sheet("9050 SUS")
    ws2.append(["Tag_Number", "Service", "Instrument_Type_Desc"])
    ws2.append(["9050-FI-922", "SVC D", "FIELD FLOW INDICATOR"])
    wb.save(path)
    return path


def test_import_master_list_writes_snapshot_and_stamps_mapped_series(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    path = _make_master_list_xlsx(tmp_path / "Instrumentation_Master_List.xlsx")

    snapshot, summaries = da.import_master_list(
        path, sheet_series_map={"29103-K1B Pad": 29103, "9050 SUS": None})

    assert da.MASTER_LIST_PATH.exists()
    assert snapshot["source_file"] == path.name
    assert snapshot["sheet_series_map"] == {"29103-K1B Pad": 29103, "9050 SUS": None}
    assert len(snapshot["items"]) == 4  # 3 from 29103 + 1 from 9050 SUS

    by_tag = {it["tag"]: it for it in snapshot["items"]}
    assert by_tag["29103-PIT-2171"]["mapped_series"] == 29103
    assert by_tag["29103-PIT-2171"]["model"] == "233.34"
    assert by_tag["9050-FI-922"]["mapped_series"] is None

    sheet_names = {s["sheet_name"] for s in summaries}
    assert sheet_names == {"29103-K1B Pad", "9050 SUS"}

    # Also remembered for one-click re-import (10.4)
    assert da.get_setting("master_list_path") == str(path)


def test_reimport_fully_replaces_not_accumulates(isolated_app_dir):
    """10's acceptance criterion: 'Re-running the import fully replaces
    the previous snapshot (idempotent)'."""
    tmp_path, da = isolated_app_dir
    path = _make_master_list_xlsx(tmp_path / "Instrumentation_Master_List.xlsx")

    da.import_master_list(path, {"29103-K1B Pad": 29103, "9050 SUS": None})
    first_count = len(da.load_master_list()["items"])

    da.import_master_list(path, {"29103-K1B Pad": 29103, "9050 SUS": None})
    second_count = len(da.load_master_list()["items"])

    assert first_count == second_count == 4  # not doubled


def test_master_list_items_filters(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    path = _make_master_list_xlsx(tmp_path / "Instrumentation_Master_List.xlsx")
    da.import_master_list(path, {"29103-K1B Pad": 29103, "9050 SUS": None})

    assert len(da.master_list_items(kind="transmitter")) == 1
    assert len(da.master_list_items(kind="valve")) == 1
    assert len(da.master_list_items(kind="out_of_scope")) == 2
    assert len(da.master_list_items(series=29103)) == 3
    assert len(da.master_list_items(series=None, area="29103")) == 3


def test_master_list_items_empty_when_nothing_imported(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    assert da.load_master_list() is None
    assert da.master_list_items() == []


def test_app_works_with_no_master_list_json_at_all(isolated_app_dir):
    """10's acceptance criterion: 'the app works normally when
    master_list.json doesn't exist at all'."""
    tmp_path, da = isolated_app_dir
    assert not da.MASTER_LIST_PATH.exists()
    assert da.load_master_list() is None
    assert da.master_list_items(kind="transmitter") == []
    assert da.master_list_needs_reimport() is False


def test_needs_reimport_false_until_source_file_changes(isolated_app_dir, monkeypatch):
    tmp_path, da = isolated_app_dir
    path = _make_master_list_xlsx(tmp_path / "Instrumentation_Master_List.xlsx")
    da.import_master_list(path, {"29103-K1B Pad": 29103, "9050 SUS": None})

    assert da.master_list_needs_reimport() is False

    time.sleep(0.05)
    path.write_bytes(path.read_bytes())  # touch: rewrite same bytes, bumps mtime
    import os
    os.utime(path, None)

    assert da.master_list_needs_reimport() is True


def test_needs_reimport_false_when_remembered_path_is_gone(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    path = _make_master_list_xlsx(tmp_path / "Instrumentation_Master_List.xlsx")
    da.import_master_list(path, {"29103-K1B Pad": 29103})
    path.unlink()
    assert da.master_list_needs_reimport() is False


def test_canonical_tag_and_parse_area_code_reexported(da_module=None):
    import data_access as da
    assert da.canonical_tag("29103-FIT -0916") == "29103-FIT-0916"
    assert da.parse_area_code("29103-FIT-0916") == "29103"
    assert da.classify_kind("PIT", "PRESSURE INDICATING TRANSMITTER") == "transmitter"


# ------------------------------------------------- real-file integration (opt-in)
REAL_MASTER_LIST_PATH = (
    "/root/.claude/uploads/9a3620b2-457f-5e1e-9520-deffb56c387b/"
    "321c46e9-Instrumentation_Master_List.xlsx"
)


def test_against_real_uploaded_master_list_if_present(isolated_app_dir):
    """Not a fixture checked into the repo (it's the client's ~3MB file,
    uploaded to this session only) - skips cleanly anywhere else, but runs
    for real here and is the actual acceptance-criteria check for Phase 10."""
    import os
    if not os.path.exists(REAL_MASTER_LIST_PATH):
        pytest.skip("real Instrumentation_Master_List.xlsx not present in this environment")

    tmp_path, da = isolated_app_dir
    sheet_series_map = {
        "29103-K1B Pad": 29103, "29151 Drain 1": 29151, "29152 Drain 2": 29152,
        "KIB AREA 29203 FLOWLINE": 29203, "9050 SUS": None,
    }
    t0 = time.time()
    snapshot, summaries = da.import_master_list(REAL_MASTER_LIST_PATH, sheet_series_map)
    elapsed = time.time() - t0

    assert elapsed < 10.0  # no hang on the 29203 sheet's inflated dimension
    by_sheet = {s["sheet_name"]: s for s in summaries}
    assert by_sheet["29103-K1B Pad"]["rows_found"] == 1120
    assert by_sheet["29151 Drain 1"]["rows_found"] == 28
    assert by_sheet["29152 Drain 2"]["rows_found"] == 21
    assert by_sheet["KIB AREA 29203 FLOWLINE"]["rows_found"] == 20
    # NOTE: the spec's own acceptance criteria estimate ~1,380 rows for
    # 9050 SUS - verified against the real file, that figure conflates the
    # sheet's inflated claimed dimension (1,383) with its real row count.
    # The real count, confirmed by direct inspection, is 134.
    assert by_sheet["9050 SUS"]["rows_found"] == 134

    by_tag = {it["tag"]: it for it in snapshot["items"]}
    assert by_tag["29103-AT-2720A"]["tag_raw"] == "29103-AT  -2720A"
    assert by_tag["29103-FIT-0916"]["mapped_series"] == 29103
    assert not any("000000" in it["model"] for it in snapshot["items"])
