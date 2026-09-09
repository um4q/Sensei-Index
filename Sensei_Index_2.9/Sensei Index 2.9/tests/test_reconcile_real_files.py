# -*- coding: utf-8 -*-
"""Phase 11 acceptance criteria, checked against the real, checked-in
Equipment_Inspection_Tracker.xlsx and the real uploaded
Instrumentation_Master_List.xlsx (not committed to the repo - the
client's ~3MB file, uploaded to this session only). Both are copied into
a tmp dir first - this test never writes to either real file. Skips
cleanly wherever the master list file isn't present (e.g. a fresh clone
outside this session)."""
import os
import shutil
import time
from pathlib import Path

import pytest

REAL_MASTER_LIST_PATH = (
    "/root/.claude/uploads/9a3620b2-457f-5e1e-9520-deffb56c387b/"
    "321c46e9-Instrumentation_Master_List.xlsx"
)

SHEET_SERIES_MAP = {
    "29103-K1B Pad": 29103, "29151 Drain 1": 29151, "29152 Drain 2": 29152,
    "KIB AREA 29203 FLOWLINE": 29203, "9050 SUS": None,
}


@pytest.mark.timeout(30)
def test_fit_0916_matches_across_real_files(tmp_path, monkeypatch):
    if not os.path.exists(REAL_MASTER_LIST_PATH):
        pytest.skip("real Instrumentation_Master_List.xlsx not present in this environment")

    import data_access as da

    real_workbook = da.HERE / "Equipment_Inspection_Tracker.xlsx"
    real_registry = da.CONFIG_PATH
    assert real_workbook.exists(), "checked-in Equipment_Inspection_Tracker.xlsx is missing"
    real_workbook_mtime_before = real_workbook.stat().st_mtime

    # Copy (never mutate) the real, checked-in files into an isolated tmp dir.
    workbook_copy = tmp_path / "Equipment_Inspection_Tracker.xlsx"
    registry_copy = tmp_path / "series_registry.json"
    shutil.copy(real_workbook, workbook_copy)
    shutil.copy(real_registry, registry_copy)

    monkeypatch.setattr(da, "HERE", tmp_path, raising=False)
    monkeypatch.setattr(da, "WORKBOOK_PATH", workbook_copy, raising=False)
    monkeypatch.setattr(da, "CONFIG_PATH", registry_copy, raising=False)
    monkeypatch.setattr(da, "MASTER_LIST_PATH", tmp_path / "master_list.json", raising=False)
    monkeypatch.setattr(da, "STATUS_PATH", tmp_path / "equipment_status.json", raising=False)
    monkeypatch.setattr(da, "SETTINGS_PATH", tmp_path / "app_settings.json", raising=False)
    da.invalidate_workbook_cache()

    snapshot, _summaries = da.import_master_list(REAL_MASTER_LIST_PATH, SHEET_SERIES_MAP)

    t0 = time.time()
    result = da.reconcile_master_list()
    elapsed = time.time() - t0

    assert elapsed < 20.0
    # Phase 11's own acceptance criterion, verbatim: "29103-FIT-0916 (exists
    # in both files today) lands in Matched despite the master list's
    # padded spelling."
    fit_0916 = [m for m in result["matched"] if m["master"]["tag"] == "29103-FIT-0916"]
    assert fit_0916, "29103-FIT-0916 should be in Matched"
    assert fit_0916[0]["tracker"]["key_value"] == "29103-FIT-0916"

    # Coverage counts must be internally consistent (11's acceptance criterion).
    in_scope_total = len(snapshot["items"]) - result["out_of_scope_count"]
    assert len(result["matched"]) + len(result["missing"]) == in_scope_total

    # The real, checked-in workbook was never modified by any of this -
    # everything above only ever touched workbook_copy in tmp_path.
    assert real_workbook.stat().st_mtime == real_workbook_mtime_before
