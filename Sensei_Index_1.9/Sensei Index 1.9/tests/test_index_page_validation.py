# -*- coding: utf-8 -*-
"""Phase 13.5 - warn-don't-block validation, wired into EditDialog.save()
and IndexPage's grid rendering."""
import pytest

import gui_app


@pytest.fixture(autouse=True)
def _no_modal_boxes_except_warning(monkeypatch):
    """Everything except QMessageBox.warning is mocked to a no-op (these
    tests are specifically about when .warning() fires and with what
    text) - .warning is instead recorded, not blocked, so we can assert
    on it without it actually hanging the test."""
    monkeypatch.setattr(gui_app.QMessageBox, "information", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(gui_app.QMessageBox, "critical", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(gui_app.QMessageBox, "question",
                         staticmethod(lambda *a, **k: gui_app.QMessageBox.Yes))


def _make_edit_dialog(qtbot, da, series_number, equip_key, row_num, is_new=True):
    dlg = gui_app.EditDialog(None, series_number, equip_key, row_num, is_new=is_new)
    qtbot.addWidget(dlg)
    return dlg


def test_edit_dialog_warns_after_save_for_malformed_tag(qtbot, isolated_app_dir, monkeypatch):
    tmp_path, da = isolated_app_dir
    warnings = []
    monkeypatch.setattr(gui_app.QMessageBox, "warning",
                         staticmethod(lambda *a, **k: warnings.append(a) or gui_app.QMessageBox.Ok))

    row_num = da.find_first_blank_row(29103, "transmitter")
    dlg = _make_edit_dialog(qtbot, da, 29103, "transmitter", row_num)
    dlg.widgets["tag"].setText("not-a-valid-tag-shape!!")
    dlg.save()

    # the save happened regardless of the warning
    rows = da.read_index_rows(29103, "transmitter")
    assert any(r["tag"] == "not-a-valid-tag-shape!!" for r in rows)
    assert dlg.result() == gui_app.QDialog.Accepted
    assert len(warnings) == 1
    assert "doesn't look like AREA-TYPE-NUMBER" in warnings[0][2]


def test_edit_dialog_no_warning_for_well_formed_tag(qtbot, isolated_app_dir, monkeypatch):
    tmp_path, da = isolated_app_dir
    warnings = []
    monkeypatch.setattr(gui_app.QMessageBox, "warning",
                         staticmethod(lambda *a, **k: warnings.append(a) or gui_app.QMessageBox.Ok))

    row_num = da.find_first_blank_row(29103, "transmitter")
    dlg = _make_edit_dialog(qtbot, da, 29103, "transmitter", row_num)
    dlg.widgets["tag"].setText("29103-PIT-2171")
    dlg.save()

    assert dlg.result() == gui_app.QDialog.Accepted
    assert warnings == []


def test_edit_dialog_warns_for_duplicate_serial(qtbot, isolated_app_dir, monkeypatch):
    tmp_path, da = isolated_app_dir
    existing_row = da.find_first_blank_row(29103, "transmitter")
    da.save_row(29103, "transmitter", existing_row,
                {"tag": "29103-PIT-0001", "serial_number": "SN-100"})

    warnings = []
    monkeypatch.setattr(gui_app.QMessageBox, "warning",
                         staticmethod(lambda *a, **k: warnings.append(a) or gui_app.QMessageBox.Ok))

    new_row = da.find_first_blank_row(29103, "transmitter")
    dlg = _make_edit_dialog(qtbot, da, 29103, "transmitter", new_row)
    dlg.widgets["tag"].setText("29103-PIT-0002")
    dlg.widgets["serial_number"].setText("SN-100")
    dlg.save()

    assert dlg.result() == gui_app.QDialog.Accepted
    assert len(warnings) == 1
    assert "29103-PIT-0001" in warnings[0][2]
    assert "SN-100" in warnings[0][2]

    # the save still happened - this is advisory, never a block
    rows = da.read_index_rows(29103, "transmitter")
    assert any(r["tag"] == "29103-PIT-0002" for r in rows)


def test_edit_dialog_hard_block_still_wins_over_warn_dont_block(qtbot, isolated_app_dir, monkeypatch):
    """A duplicate TAG is still a hard block (find_duplicate_row) - never
    reaches the warn-don't-block path at all."""
    tmp_path, da = isolated_app_dir
    existing_row = da.find_first_blank_row(29103, "transmitter")
    da.save_row(29103, "transmitter", existing_row, {"tag": "29103-PIT-0001"})

    warned = []
    monkeypatch.setattr(gui_app.QMessageBox, "warning",
                         staticmethod(lambda *a, **k: warned.append(a) or gui_app.QMessageBox.Ok))

    new_row = da.find_first_blank_row(29103, "transmitter")
    dlg = _make_edit_dialog(qtbot, da, 29103, "transmitter", new_row)
    dlg.widgets["tag"].setText("29103-PIT-0001")  # duplicate of existing_row
    dlg.save()

    assert dlg.result() != gui_app.QDialog.Accepted  # save was blocked
    # the hard-block warning ("Duplicate ...") fired, not the soft one
    assert len(warned) == 1
    assert "already used" in warned[0][2]


def test_index_page_grid_flags_malformed_tag_cell(qtbot, isolated_app_dir, fake_main_window):
    tmp_path, da = isolated_app_dir
    row_num = da.find_first_blank_row(29103, "transmitter")
    da.save_row(29103, "transmitter", row_num, {"tag": "bad tag shape"})

    page = gui_app.IndexPage(fake_main_window, 29103, "transmitter")
    qtbot.addWidget(page)

    tag_col = page.columns.index("tag")
    r = page._table_row_for(row_num)
    item = page.table.item(r, tag_col)
    assert item.background().color() == gui_app._validation_warning_color()
    assert "AREA-TYPE-NUMBER" in item.toolTip()


def test_index_page_grid_does_not_flag_well_formed_tag(qtbot, isolated_app_dir, fake_main_window):
    tmp_path, da = isolated_app_dir
    row_num = da.find_first_blank_row(29103, "transmitter")
    da.save_row(29103, "transmitter", row_num, {"tag": "29103-PIT-2171"})

    page = gui_app.IndexPage(fake_main_window, 29103, "transmitter")
    qtbot.addWidget(page)

    tag_col = page.columns.index("tag")
    r = page._table_row_for(row_num)
    item = page.table.item(r, tag_col)
    assert item.toolTip() == ""
