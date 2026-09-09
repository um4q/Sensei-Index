# -*- coding: utf-8 -*-
"""Phase 16.1 - BackupsDialog, driven offscreen via pytest-qt."""
import pytest

import gui_app


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
