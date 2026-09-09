# -*- coding: utf-8 -*-
"""Sanity checks for the isolated_app_dir test fixture itself, and a couple
of existing data_access behaviors this whole test suite leans on."""


def test_isolated_app_dir_round_trip(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    assert da.list_series() == [100, 29103]

    row = da.find_first_blank_row(29103, "transmitter")
    da.save_row(29103, "transmitter", row, {"tag": "29103-FIT-0916", "service": "TEST SERVICE"})

    rows = da.read_index_rows(29103, "transmitter")
    assert len(rows) == 1
    assert rows[0]["tag"] == "29103-FIT-0916"


def test_isolated_app_dir_does_not_touch_real_workbook(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    assert da.WORKBOOK_PATH == tmp_path / "Equipment_Inspection_Tracker.xlsx"
    assert da.WORKBOOK_PATH.exists()
