# -*- coding: utf-8 -*-
"""Phase 13.4 - QDateEdit calendar picker for date_fields grid columns."""
from PySide6.QtCore import QDate

import gui_app


def test_delegate_wired_onto_every_date_column(qtbot, isolated_app_dir, fake_main_window):
    tmp_path, da = isolated_app_dir
    row_num = da.find_first_blank_row(29103, "transmitter")
    da.save_row(29103, "transmitter", row_num, {"tag": "29103-PIT-2171"})

    page = gui_app.IndexPage(fake_main_window, 29103, "transmitter")
    qtbot.addWidget(page)

    date_fields = page.etype["date_fields"]
    assert date_fields  # transmitter has some
    for fid in date_fields:
        col = page.columns.index(fid)
        assert page.table.itemDelegateForColumn(col) is page._date_delegate


def test_create_editor_has_calendar_popup_and_today_button(qtbot):
    delegate = gui_app.DateEditDelegate()
    container = delegate.createEditor(None, None, None)
    qtbot.addWidget(container)
    assert container.date_edit.calendarPopup() is True
    assert container.date_edit.displayFormat() == "yyyy-MM-dd"

    today_btns = [w for w in container.findChildren(gui_app.QPushButton) if w.text() == "Today"]
    assert len(today_btns) == 1
    container.date_edit.setDate(QDate(2020, 1, 1))
    today_btns[0].click()
    assert container.date_edit.date() == QDate.currentDate()


def test_set_editor_data_parses_existing_iso_date(qtbot, isolated_app_dir, fake_main_window):
    tmp_path, da = isolated_app_dir
    row_num = da.find_first_blank_row(29103, "transmitter")
    field = list(da.EQUIPMENT_TYPES["transmitter"]["date_fields"])[0]
    da.save_row(29103, "transmitter", row_num, {"tag": "29103-PIT-2171", field: "2026-03-14"})

    page = gui_app.IndexPage(fake_main_window, 29103, "transmitter")
    qtbot.addWidget(page)

    col = page.columns.index(field)
    r = page._table_row_for(row_num)
    index = page.table.model().index(r, col)

    editor = page._date_delegate.createEditor(None, None, index)
    qtbot.addWidget(editor)
    page._date_delegate.setEditorData(editor, index)
    assert editor.date_edit.date() == QDate(2026, 3, 14)


def test_set_editor_data_defaults_to_today_for_blank_or_unparseable(qtbot, isolated_app_dir, fake_main_window):
    tmp_path, da = isolated_app_dir
    row_num = da.find_first_blank_row(29103, "transmitter")
    da.save_row(29103, "transmitter", row_num, {"tag": "29103-PIT-2171"})  # date left blank

    page = gui_app.IndexPage(fake_main_window, 29103, "transmitter")
    qtbot.addWidget(page)

    field = list(da.EQUIPMENT_TYPES["transmitter"]["date_fields"])[0]
    col = page.columns.index(field)
    r = page._table_row_for(row_num)
    index = page.table.model().index(r, col)

    editor = page._date_delegate.createEditor(None, None, index)
    qtbot.addWidget(editor)
    page._date_delegate.setEditorData(editor, index)
    assert editor.date_edit.date() == QDate.currentDate()


def test_editing_a_date_cell_through_the_delegate_saves_and_round_trips(qtbot, isolated_app_dir, fake_main_window):
    """The literal Phase 13 acceptance criterion: a date entered via the
    calendar re-opens in Excel formatted exactly like pre-existing dates
    (yyyy-MM-dd, matching Mass Edit Dates' own write format)."""
    tmp_path, da = isolated_app_dir
    row_num = da.find_first_blank_row(29103, "transmitter")
    da.save_row(29103, "transmitter", row_num, {"tag": "29103-PIT-2171"})

    page = gui_app.IndexPage(fake_main_window, 29103, "transmitter")
    qtbot.addWidget(page)

    field = list(da.EQUIPMENT_TYPES["transmitter"]["date_fields"])[0]
    col = page.columns.index(field)
    r = page._table_row_for(row_num)
    model = page.table.model()
    index = model.index(r, col)

    editor = page._date_delegate.createEditor(page.table, None, index)
    qtbot.addWidget(editor)
    editor.date_edit.setDate(QDate(2026, 12, 25))
    page._date_delegate.setModelData(editor, model, index)

    # itemChanged -> _on_item_changed -> _commit_single_cell_edit already
    # fired synchronously from setModelData's model.setData() call.
    saved = da.read_full_row(29103, "transmitter", row_num)
    assert saved[field] == "2026-12-25"

    # Re-opening the editor on what was just saved round-trips exactly.
    index2 = model.index(r, col)
    editor2 = page._date_delegate.createEditor(page.table, None, index2)
    qtbot.addWidget(editor2)
    page._date_delegate.setEditorData(editor2, index2)
    assert editor2.date_edit.date() == QDate(2026, 12, 25)
