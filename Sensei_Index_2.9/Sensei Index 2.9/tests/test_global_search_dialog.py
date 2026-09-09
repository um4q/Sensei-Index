# -*- coding: utf-8 -*-
"""Phase 14 - GlobalSearchDialog, driven offscreen via pytest-qt."""
import pytest

import gui_app


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


def test_typing_debounces_then_shows_results(qtbot, isolated_app_dir, fake_main_window):
    tmp_path, da = isolated_app_dir
    row = da.find_first_blank_row(29103, "transmitter")
    da.save_row(29103, "transmitter", row, {"tag": "29103-PIT-2171", "serial_number": "SN-UNIQUE-9"})

    dlg = gui_app.GlobalSearchDialog(None, fake_main_window)
    qtbot.addWidget(dlg)

    dlg.query_edit.setText("SN-UNIQUE-9")
    assert dlg.results_list.count() == 0  # debounce hasn't fired yet
    qtbot.wait(gui_app.GlobalSearchDialog.DEBOUNCE_MS + 100)
    assert dlg.results_list.count() == 1
    assert "29103-PIT-2171" in dlg.results_list.item(0).text()


def test_enter_navigates_to_tracker_hit(qtbot, isolated_app_dir, fake_main_window):
    tmp_path, da = isolated_app_dir
    row = da.find_first_blank_row(29103, "transmitter")
    da.save_row(29103, "transmitter", row, {"tag": "29103-PIT-2171"})

    calls = []
    fake_main_window.show_index = lambda *a, **k: calls.append(a)

    dlg = gui_app.GlobalSearchDialog(None, fake_main_window)
    qtbot.addWidget(dlg)
    dlg.query_edit.setText("PIT-2171")
    dlg._run_search()  # skip the debounce wait for a deterministic test
    dlg._activate_current()

    assert calls == [(29103, "transmitter", {"tag": "29103-PIT-2171"})]
    assert dlg.result() == gui_app.QDialog.Accepted


def test_enter_on_master_only_hit_opens_coverage_selected(qtbot, isolated_app_dir, fake_main_window):
    """14's own acceptance criterion: a master-list-only tag is findable
    and one click away from being added to the tracker."""
    tmp_path, da = isolated_app_dir
    da.save_master_list({
        "imported_at": "2026-08-30T00:00:00", "source_file": "x.xlsx", "source_mtime": 0,
        "sheet_series_map": {}, "items": [_ml_item("29103-FIT-0916", "transmitter")],
    })

    calls = []
    fake_main_window.show_coverage = lambda select_tag=None: calls.append(select_tag)

    dlg = gui_app.GlobalSearchDialog(None, fake_main_window)
    qtbot.addWidget(dlg)
    dlg.query_edit.setText("FIT-0916")
    dlg._run_search()
    dlg._activate_current()

    assert calls == ["29103-FIT-0916"]


def test_escape_closes_without_navigating(qtbot, isolated_app_dir, fake_main_window):
    tmp_path, da = isolated_app_dir
    dlg = gui_app.GlobalSearchDialog(None, fake_main_window)
    qtbot.addWidget(dlg)
    qtbot.keyClick(dlg, gui_app.Qt.Key_Escape)
    assert dlg.result() == gui_app.QDialog.Rejected


def test_results_capped_at_limit(qtbot, isolated_app_dir, fake_main_window):
    tmp_path, da = isolated_app_dir
    for i in range(gui_app.GlobalSearchDialog.RESULT_LIMIT + 10):
        row = da.find_first_blank_row(29103, "transmitter")
        da.save_row(29103, "transmitter", row, {"tag": f"29103-PIT-{i:04d}", "service": "COMMONSVC"})

    dlg = gui_app.GlobalSearchDialog(None, fake_main_window)
    qtbot.addWidget(dlg)
    dlg.query_edit.setText("COMMONSVC")
    dlg._run_search()
    assert dlg.results_list.count() == gui_app.GlobalSearchDialog.RESULT_LIMIT


# ------------------------------------------------------ Coverage integration
def test_select_and_scroll_to_tag_selects_the_missing_leaf(qtbot, isolated_app_dir, fake_main_window):
    tmp_path, da = isolated_app_dir
    da.save_master_list({
        "imported_at": "2026-08-30T00:00:00", "source_file": "x.xlsx", "source_mtime": 0,
        "sheet_series_map": {}, "items": [_ml_item("29103-FIT-0916", "transmitter")],
    })
    page = gui_app.CoveragePage(fake_main_window)
    qtbot.addWidget(page)

    found = page.select_and_scroll_to_tag("29103-FIT-0916")
    assert found is True
    current = page.tree.currentItem()
    assert current is not None
    assert page._leaf_tag(current) == "29103-FIT-0916"


def test_select_and_scroll_to_tag_forces_all_chip(qtbot, isolated_app_dir, fake_main_window):
    """Guarantees the target leaf is actually rendered, regardless of
    whatever chip was active before the search jumped here."""
    tmp_path, da = isolated_app_dir
    da.save_master_list({
        "imported_at": "2026-08-30T00:00:00", "source_file": "x.xlsx", "source_mtime": 0,
        "sheet_series_map": {}, "items": [_ml_item("29103-FIT-0916", "transmitter")],
    })
    page = gui_app.CoveragePage(fake_main_window)
    qtbot.addWidget(page)
    page.chips.set_active("orphans")  # a chip under which the missing leaf would be absent
    page._render_tree()

    found = page.select_and_scroll_to_tag("29103-FIT-0916")
    assert found is True
    assert page.chips.active_id == "all"


def test_select_and_scroll_to_tag_false_when_no_master_list(qtbot, isolated_app_dir, fake_main_window):
    tmp_path, da = isolated_app_dir
    page = gui_app.CoveragePage(fake_main_window)
    qtbot.addWidget(page)
    assert page.select_and_scroll_to_tag("29103-FIT-0916") is False
