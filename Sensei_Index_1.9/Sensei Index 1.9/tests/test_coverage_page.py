# -*- coding: utf-8 -*-
"""Phase 11.2/11.3 - CoveragePage, driven offscreen via pytest-qt."""
import pytest
from PySide6.QtCore import Qt

import gui_app


@pytest.fixture(autouse=True)
def _no_modal_message_boxes(monkeypatch):
    monkeypatch.setattr(gui_app.QMessageBox, "information", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(gui_app.QMessageBox, "critical", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(gui_app.QMessageBox, "warning", staticmethod(lambda *a, **k: None))
    # question() normally waits for a click - default every test to "Yes"
    # (proceeding with the confirm), individual tests can override.
    monkeypatch.setattr(gui_app.QMessageBox, "question",
                         staticmethod(lambda *a, **k: gui_app.QMessageBox.Yes))


def _seed_master_list(da, items):
    da.save_master_list({
        "imported_at": "2026-08-30T00:00:00", "source_file": "Instrumentation_Master_List.xlsx",
        "source_mtime": 0, "sheet_series_map": {}, "items": items,
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


def test_empty_state_shown_with_no_master_list(qtbot, isolated_app_dir):
    tmp_path, da = isolated_app_dir

    class FakeMainWindow:
        open_master_list_import_called = False

        def open_master_list_import(self):
            self.open_master_list_import_called = True

    mw = FakeMainWindow()
    page = gui_app.CoveragePage(mw)
    qtbot.addWidget(page)
    page.show()

    assert page.empty_state.isVisible()
    assert not page.content.isVisible()


def test_populated_tree_shows_matched_missing_orphans(qtbot, isolated_app_dir):
    tmp_path, da = isolated_app_dir
    row = da.find_first_blank_row(29103, "transmitter")
    da.save_row(29103, "transmitter", row, {"tag": "29103-PIT-2171"})
    extra_row = da.find_first_blank_row(29103, "transmitter")
    da.save_row(29103, "transmitter", extra_row, {"tag": "29103-ORPHAN-0001"})
    _seed_master_list(da, [
        _ml_item("29103-PIT-2171", "transmitter"),
        _ml_item("29103-FIT-0916", "transmitter"),
    ])

    class FakeMainWindow:
        def show_index(self, *a, **k):
            self.shown = (a, k)

        def statusBar(self):
            class SB:
                def showMessage(self, *a, **k):
                    pass
            return SB()

        def refresh_sidebar_and_dashboard(self):
            pass

    page = gui_app.CoveragePage(FakeMainWindow())
    qtbot.addWidget(page)
    page.show()

    assert page.content.isVisible()
    assert not page.empty_state.isVisible()
    assert page.result["matched"]
    assert page.result["missing"]
    assert page.result["orphans"]

    # "All" chip is active by default - the tree should have at least one
    # top-level area node.
    assert page.tree.topLevelItemCount() >= 1


def test_clicking_matched_item_navigates_to_index(qtbot, isolated_app_dir):
    tmp_path, da = isolated_app_dir
    row = da.find_first_blank_row(29103, "transmitter")
    da.save_row(29103, "transmitter", row, {"tag": "29103-PIT-2171"})
    _seed_master_list(da, [_ml_item("29103-PIT-2171", "transmitter")])

    calls = []

    class FakeMainWindow:
        def show_index(self, series_number, equip_key, filters):
            calls.append((series_number, equip_key, filters))

    page = gui_app.CoveragePage(FakeMainWindow())
    qtbot.addWidget(page)
    page.show()

    area_item = page.tree.topLevelItem(0)
    kind_item = area_item.child(0)
    leaf = kind_item.child(0)
    assert leaf.data(0, Qt.UserRole)[0] == "matched"
    page._on_item_clicked(leaf, 0)

    assert calls == [(29103, "transmitter", {"tag": "29103-PIT-2171"})]


def test_clicking_missing_item_opens_create_from_master(qtbot, isolated_app_dir):
    tmp_path, da = isolated_app_dir
    _seed_master_list(da, [_ml_item("29103-PIT-2171", "transmitter")])

    class FakeMainWindow:
        def __init__(self):
            self.undo_stack = gui_app.UndoManager()

        def refresh_sidebar_and_dashboard(self):
            pass

        def refresh_current_view(self):
            pass

        def statusBar(self):
            class SB:
                def showMessage(self, *a, **k):
                    pass
            return SB()

    page = gui_app.CoveragePage(FakeMainWindow())
    qtbot.addWidget(page)
    page.show()

    area_item = page.tree.topLevelItem(0)
    kind_item = area_item.child(0)
    leaf = kind_item.child(0)
    assert leaf.data(0, Qt.UserRole)[0] == "missing"
    page._on_item_clicked(leaf, 0)  # QMessageBox.question mocked to "Yes" above

    rows = da.read_index_rows(29103, "transmitter")
    assert any(r["tag"] == "29103-PIT-2171" for r in rows)


def test_add_selected_button_creates_all_selected_missing_items(qtbot, isolated_app_dir):
    tmp_path, da = isolated_app_dir
    _seed_master_list(da, [
        _ml_item("29103-PIT-2171", "transmitter"),
        _ml_item("29103-PIT-2172", "transmitter"),
    ])

    class FakeMainWindow:
        def __init__(self):
            self.undo_stack = gui_app.UndoManager()

        def refresh_sidebar_and_dashboard(self):
            pass

        def refresh_current_view(self):
            pass

        def statusBar(self):
            class SB:
                def showMessage(self, *a, **k):
                    pass
            return SB()

    page = gui_app.CoveragePage(FakeMainWindow())
    qtbot.addWidget(page)
    page.show()

    area_item = page.tree.topLevelItem(0)
    kind_item = area_item.child(0)
    for i in range(kind_item.childCount()):
        kind_item.child(i).setSelected(True)
    page._on_selection_changed()

    assert page.add_selected_btn.isEnabled()
    assert len(page._selected_missing) == 2

    page._create_from_master(list(page._selected_missing))

    tags = {r["tag"] for r in da.read_index_rows(29103, "transmitter")}
    assert {"29103-PIT-2171", "29103-PIT-2172"} <= tags


def test_out_of_scope_shown_collapsed_with_count(qtbot, isolated_app_dir):
    tmp_path, da = isolated_app_dir
    _seed_master_list(da, [
        _ml_item("29103-TW-0100", "out_of_scope"),
        _ml_item("29103-PSV-0905", "out_of_scope"),
    ])

    class FakeMainWindow:
        pass

    page = gui_app.CoveragePage(FakeMainWindow())
    qtbot.addWidget(page)
    page.show()

    oos_item = page.tree.topLevelItem(page.tree.topLevelItemCount() - 1)
    assert "Out of scope (2)" in oos_item.text(0)
    assert not oos_item.isExpanded()
    assert oos_item.childCount() == 2


def test_stale_banner_shown_when_master_list_needs_reimport(qtbot, isolated_app_dir, tmp_path=None):
    tmp_path, da = isolated_app_dir
    import time
    ml_path = tmp_path / "Instrumentation_Master_List.xlsx"
    ml_path.write_bytes(b"not a real xlsx but only mtime matters here")
    da.set_setting("master_list_path", str(ml_path))
    _seed_master_list(da, [])
    # force the snapshot's recorded mtime behind the file's real mtime
    snapshot = da.load_master_list()
    snapshot["source_mtime"] = ml_path.stat().st_mtime - 100
    da.save_master_list(snapshot)

    class FakeMainWindow:
        pass

    page = gui_app.CoveragePage(FakeMainWindow())
    qtbot.addWidget(page)
    page.show()
    assert page.banner.isVisible()


def test_reload_after_import_dialog_shows_new_data(qtbot, isolated_app_dir):
    """MainWindow.open_master_list_import() calls page.reload() on the
    active Coverage page after the dialog closes - verify reload() alone
    correctly flips from empty state to populated."""
    tmp_path, da = isolated_app_dir

    class FakeMainWindow:
        pass

    page = gui_app.CoveragePage(FakeMainWindow())
    qtbot.addWidget(page)
    page.show()
    assert page.empty_state.isVisible()

    _seed_master_list(da, [_ml_item("29103-PIT-2171", "transmitter")])
    page.reload()
    assert page.content.isVisible()
    assert not page.empty_state.isVisible()
