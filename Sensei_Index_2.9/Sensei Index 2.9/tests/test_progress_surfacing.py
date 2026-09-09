# -*- coding: utf-8 -*-
"""Phase 12.2 - compute_progress() surfaced in IndexPage-shaped row reads,
Dashboard series summaries, and Coverage's matched pairs. Same percent
everywhere for the same row (12's own acceptance criterion)."""


def test_read_index_rows_with_progress_matches_compute_progress(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    row = da.find_first_blank_row(29103, "transmitter")
    da.save_row(29103, "transmitter", row, {"tag": "29103-PIT-2171", "serial_number": "SN-1"})
    da.set_status(29103, "transmitter", "29103-PIT-2171", installed=True)

    rows = da.read_index_rows_with_progress(29103, "transmitter")
    assert len(rows) == 1
    entry = rows[0]
    assert entry["progress"]["percent"] == da.compute_progress(
        "transmitter", da.read_full_row(29103, "transmitter", row), entry)["percent"]
    assert entry["progress"]["percent"] > 0


def test_series_progress_summary_buckets_correctly(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    # row 1: nothing filled -> low %, bucket "partial" (created-only isn't 0%)
    row1 = da.find_first_blank_row(29103, "transmitter")
    da.save_row(29103, "transmitter", row1, {"tag": "29103-PIT-0001"})
    # row 2: fully done -> 100%
    row2 = da.find_first_blank_row(29103, "transmitter")
    values = {"tag": "29103-PIT-0002", "serial_number": "SN-2"}
    values.update({f"vi_{i}": "X" for i in range(1, 13)})
    values.update({f"proc_{i}": "Pass" for i in range(2, 15)})
    da.save_row(29103, "transmitter", row2, values)
    da.set_status(29103, "transmitter", "29103-PIT-0002", installed=True, submitted=True, accepted=True)

    summary = da.series_progress_summary(29103)
    assert summary["transmitter"]["at_100"] == 1
    assert summary["transmitter"]["partial"] == 1
    assert summary["transmitter"]["at_0"] == 0
    assert 0 < summary["transmitter"]["avg_percent"] < 100


def test_series_progress_summary_empty_series_is_zero_not_crash(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    summary = da.series_progress_summary(29103)
    assert summary["transmitter"] == {"avg_percent": 0, "at_0": 0, "partial": 0, "at_100": 0}


def test_reconcile_matched_pairs_carry_progress(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    row = da.find_first_blank_row(29103, "transmitter")
    da.save_row(29103, "transmitter", row, {"tag": "29103-PIT-2171", "serial_number": "SN-1"})
    da.save_master_list({
        "imported_at": "2026-08-30T00:00:00", "source_file": "x.xlsx", "source_mtime": 0,
        "sheet_series_map": {}, "items": [{
            "tag_raw": "29103-PIT-2171", "tag": "29103-PIT-2171", "area": "29103", "tag_type": "PIT",
            "service": "", "type_desc": "", "kind": "transmitter", "pid": "", "line_number": "",
            "module_id": "", "ewp": "", "model": "", "manufacturer": "", "install_details": "",
            "remarks": "", "ml_received": False, "ml_installed": False, "source_sheet": "Sheet1",
            "mapped_series": 29103,
        }],
    })
    result = da.reconcile_master_list()
    pair = result["matched"][0]
    assert "progress" in pair
    assert pair["progress"]["percent"] == da.compute_progress(
        "transmitter", da.read_full_row(29103, "transmitter", row),
        da.get_status(29103, "transmitter", "29103-PIT-2171"))["percent"]


def test_dashboard_and_index_and_coverage_agree_on_the_same_row(isolated_app_dir):
    """The literal 12 acceptance criterion: the same row shows the same
    percent in IndexPage(-shaped reads), Dashboard drill-down, and
    Coverage."""
    tmp_path, da = isolated_app_dir
    row = da.find_first_blank_row(29103, "transmitter")
    da.save_row(29103, "transmitter", row, {"tag": "29103-PIT-2171", "serial_number": "SN-1"})
    da.set_status(29103, "transmitter", "29103-PIT-2171", installed=True)
    da.save_master_list({
        "imported_at": "2026-08-30T00:00:00", "source_file": "x.xlsx", "source_mtime": 0,
        "sheet_series_map": {}, "items": [{
            "tag_raw": "29103-PIT-2171", "tag": "29103-PIT-2171", "area": "29103", "tag_type": "PIT",
            "service": "", "type_desc": "", "kind": "transmitter", "pid": "", "line_number": "",
            "module_id": "", "ewp": "", "model": "", "manufacturer": "", "install_details": "",
            "remarks": "", "ml_received": False, "ml_installed": False, "source_sheet": "Sheet1",
            "mapped_series": 29103,
        }],
    })

    index_pct = da.read_index_rows_with_progress(29103, "transmitter")[0]["progress"]["percent"]
    coverage_pct = da.reconcile_master_list()["matched"][0]["progress"]["percent"]
    dashboard_avg = da.series_progress_summary(29103)["transmitter"]["avg_percent"]

    assert index_pct == coverage_pct == dashboard_avg  # only one row exists, so avg == that row's %


def test_toggling_installed_changes_percent_everywhere_without_restart(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    row = da.find_first_blank_row(29103, "transmitter")
    da.save_row(29103, "transmitter", row, {"tag": "29103-PIT-2171"})

    before = da.read_index_rows_with_progress(29103, "transmitter")[0]["progress"]["percent"]
    da.set_status(29103, "transmitter", "29103-PIT-2171", installed=True)
    after = da.read_index_rows_with_progress(29103, "transmitter")[0]["progress"]["percent"]
    assert after > before
