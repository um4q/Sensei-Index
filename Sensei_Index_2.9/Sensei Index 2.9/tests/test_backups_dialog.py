# -*- coding: utf-8 -*-
"""Phase 16.1 - BackupsDialog, driven offscreen via pytest-qt."""
import pytest

import gui_app
import electrical_data_access as eda


@pytest.fixture(autouse=True)
def _no_modal_message_boxes(monkeypatch):
    monkeypatch.setattr(gui_app.QMessageBox, "information", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(gui_app.QMessageBox, "critical", staticmethod(lambda *a, **k: None))


def test_empty_state_when_no_backups_yet(qtbot, isolated_app_dir):
    tmp_path, da = isolated_app_dir
    dlg = gui_app.BackupsDialog(None)
    qtbot.addWidget(dlg)
    assert dlg.table.rowCount() == 1
    assert "No backups yet" in dlg.table.item(0, 0).text()
    assert not dlg.restore_btn.isEnabled()


def test_lists_existing_backups(qtbot, isolated_app_dir):
    tmp_path, da = isolated_app_dir
    row = da.find_first_blank_row(29103, "transmitter")
    da.save_row(29103, "transmitter", row, {"tag": "29103-PIT-2171"})  # triggers the first backup

    dlg = gui_app.BackupsDialog(None)
    qtbot.addWidget(dlg)
    assert dlg.table.rowCount() == 1
    assert "Equipment_Inspection_Tracker." in dlg.table.item(0, 0).text()


def test_back_up_now_button_adds_a_snapshot(qtbot, isolated_app_dir):
    tmp_path, da = isolated_app_dir
    row = da.find_first_blank_row(29103, "transmitter")
    da.save_row(29103, "transmitter", row, {"tag": "29103-PIT-2171"})

    dlg = gui_app.BackupsDialog(None)
    qtbot.addWidget(dlg)
    before = dlg.table.rowCount()
    dlg._backup_now()
    assert dlg.table.rowCount() == before + 1


def test_restore_requires_typing_restore(qtbot, isolated_app_dir, monkeypatch):
    tmp_path, da = isolated_app_dir
    row = da.find_first_blank_row(29103, "transmitter")
    da.save_row(29103, "transmitter", row, {"tag": "ORIGINAL"})
    da.set_setting("backup_interval_minutes", 0)
    row2 = da.find_first_blank_row(29103, "transmitter")
    da.save_row(29103, "transmitter", row2, {"tag": "NEWER"})

    monkeypatch.setattr(gui_app.QInputDialog, "getText",
                         staticmethod(lambda *a, **k: ("not restore", True)))

    dlg = gui_app.BackupsDialog(None)
    qtbot.addWidget(dlg)
    dlg.table.selectRow(dlg.table.rowCount() - 1)  # oldest backup
    dlg._restore_selected()

    tags = {r["tag"] for r in da.read_index_rows(29103, "transmitter")}
    assert "NEWER" in tags  # restore did NOT happen - confirmation text didn't match


def test_restore_with_correct_confirmation_restores_and_takes_safety_snapshot(qtbot, isolated_app_dir, monkeypatch):
    tmp_path, da = isolated_app_dir
    row = da.find_first_blank_row(29103, "transmitter")
    da.save_row(29103, "transmitter", row, {"tag": "ORIGINAL"})
    oldest_backup_name = da.list_backups()[0]["name"]

    da.set_setting("backup_interval_minutes", 0)
    row2 = da.find_first_blank_row(29103, "transmitter")
    da.save_row(29103, "transmitter", row2, {"tag": "NEWER"})
    backups_before = len(da.list_backups())

    monkeypatch.setattr(gui_app.QInputDialog, "getText",
                         staticmethod(lambda *a, **k: ("RESTORE", True)))

    dlg = gui_app.BackupsDialog(None)
    qtbot.addWidget(dlg)
    # select the row matching the oldest backup (list is newest-first)
    target_row = next(r for r in range(dlg.table.rowCount())
                       if oldest_backup_name in dlg.table.item(r, 0).text())
    dlg.table.selectRow(target_row)
    dlg._restore_selected()

    tags = {r["tag"] for r in da.read_index_rows(29103, "transmitter")}
    assert "NEWER" not in tags  # the restore actually took effect
    assert len(da.list_backups()) == backups_before + 1  # + the safety snapshot


# ------------------------------------------------------ QOL prompt Phase A.1
# BackupsDialog(backend=eda, ...) - the same dialog, generalized to also
# drive Electrical's own, separately-scoped backups.

def test_electrical_backend_shows_electrical_backups_only(qtbot, isolated_app_dir):
    tmp_path, da = isolated_app_dir
    eda.add_zone("K1B Well Pad")
    row = eda.find_first_blank_row("K1B Well Pad", "eht_removal")
    eda.save_row("K1B Well Pad", "eht_removal", row, {"trace_tag": "29103-EHT-0001"})

    dlg = gui_app.BackupsDialog(None, backend=eda, backups_dir=eda.ELECTRICAL_BACKUPS_DIR,
                                 workbook_label="Electrical")
    qtbot.addWidget(dlg)
    assert "Electrical" in dlg.windowTitle()
    assert dlg.table.rowCount() == 1
    assert "Electrical_Inspection_Tracker." in dlg.table.item(0, 0).text()


def test_electrical_backend_back_up_now_and_restore(qtbot, isolated_app_dir, monkeypatch):
    tmp_path, da = isolated_app_dir
    eda.add_zone("K1B Well Pad")
    row = eda.find_first_blank_row("K1B Well Pad", "eht_removal")
    eda.save_row("K1B Well Pad", "eht_removal", row, {"trace_tag": "ORIGINAL"})
    oldest_backup_name = eda.list_backups()[0]["name"]

    da.set_setting("backup_interval_minutes", 0)
    row2 = eda.find_first_blank_row("K1B Well Pad", "eht_removal")
    eda.save_row("K1B Well Pad", "eht_removal", row2, {"trace_tag": "NEWER"})
    backups_before = len(eda.list_backups())

    monkeypatch.setattr(gui_app.QInputDialog, "getText",
                         staticmethod(lambda *a, **k: ("RESTORE", True)))

    dlg = gui_app.BackupsDialog(None, backend=eda, backups_dir=eda.ELECTRICAL_BACKUPS_DIR,
                                 workbook_label="Electrical")
    qtbot.addWidget(dlg)
    target_row = next(r for r in range(dlg.table.rowCount())
                       if oldest_backup_name in dlg.table.item(r, 0).text())
    dlg.table.selectRow(target_row)
    dlg._restore_selected()

    tags = {r["trace_tag"] for r in eda.read_index_rows("K1B Well Pad", "eht_removal")}
    assert "NEWER" not in tags
    assert len(eda.list_backups()) == backups_before + 1

    # and Instrumentation's own backups were never touched by any of this
    assert da.list_backups() == []


def test_open_backups_dialog_dispatches_by_active_domain(qtbot, isolated_app_dir, monkeypatch, fake_main_window):
    """MainWindow.open_backups_dialog() - not just the dialog class
    itself - must route to the Electrical backend while that domain is
    active, and back to Instrumentation otherwise."""
    tmp_path, da = isolated_app_dir
    seen = {}

    class _FakeDialog:
        def __init__(self, parent, backend=None, backups_dir=None, workbook_label="Instrumentation"):
            seen["backend"] = backend or gui_app.da
            seen["label"] = workbook_label

        def exec(self):
            pass

    monkeypatch.setattr(gui_app, "BackupsDialog", _FakeDialog)
    mw = fake_main_window
    mw.active_domain = "electrical"
    gui_app.MainWindow.open_backups_dialog(mw)
    assert seen["backend"] is eda
    assert seen["label"] == "Electrical"

    mw.active_domain = "instrumentation"
    gui_app.MainWindow.open_backups_dialog(mw)
    assert seen["backend"] is gui_app.da
