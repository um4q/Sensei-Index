# -*- coding: utf-8 -*-
"""Electrical domain GUI - the Instrumentation/Electrical sidebar switcher,
ElectricalDashboardPage, ElectricalIndexPage, and ElectricalEditDialog,
driven offscreen via pytest-qt."""
import pytest
from pypdf import PdfReader

import gui_app
import electrical_data_access as eda


@pytest.fixture(autouse=True)
def _no_modal_message_boxes(monkeypatch):
    monkeypatch.setattr(gui_app.QMessageBox, "information", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(gui_app.QMessageBox, "critical", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(gui_app.QMessageBox, "warning", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(gui_app.QMessageBox, "question",
                         staticmethod(lambda *a, **k: gui_app.QMessageBox.Yes))
    monkeypatch.setattr(gui_app.da, "open_file", lambda *a, **k: None)


def test_electrical_dashboard_renders_with_no_zones(qtbot, isolated_app_dir, fake_main_window):
    tmp_path, da = isolated_app_dir
    page = gui_app.ElectricalDashboardPage(fake_main_window)
    qtbot.addWidget(page)
    labels = [w.text() for w in page.findChildren(gui_app.QLabel)]
    assert any("No zones yet" in t for t in labels)


def test_electrical_dashboard_shows_zone_cards_and_totals(qtbot, isolated_app_dir, fake_main_window):
    tmp_path, da = isolated_app_dir
    eda.add_zone("K1B Well Pad")
    row = eda.find_first_blank_row("K1B Well Pad", "eht_removal")
    eda.save_row("K1B Well Pad", "eht_removal", row, {"trace_tag": "29103-EHT-0001"})

    page = gui_app.ElectricalDashboardPage(fake_main_window)
    qtbot.addWidget(page)
    labels = [w.text() for w in page.findChildren(gui_app.QLabel)]
    assert any(t == "K1B Well Pad" for t in labels)
    assert any(t == "1" for t in labels)  # the StatCard total


def test_electrical_index_page_lists_saved_rows(qtbot, isolated_app_dir, fake_main_window):
    tmp_path, da = isolated_app_dir
    eda.add_zone("K1B Well Pad")
    row = eda.find_first_blank_row("K1B Well Pad", "eht_removal")
    eda.save_row("K1B Well Pad", "eht_removal", row, {"trace_tag": "29103-EHT-0001", "area": "29103"})

    page = gui_app.ElectricalIndexPage(fake_main_window, "K1B Well Pad", "eht_removal")
    qtbot.addWidget(page)
    assert page.table.rowCount() == 1
    assert page.table.item(0, 0).text() == "29103-EHT-0001"
    assert page.table.item(0, 0).data(gui_app.Qt.UserRole) == row


def test_electrical_index_page_add_new_via_real_dialog(qtbot, isolated_app_dir, fake_main_window):
    tmp_path, da = isolated_app_dir
    eda.add_zone("K1B Well Pad")
    page = gui_app.ElectricalIndexPage(fake_main_window, "K1B Well Pad", "eht_removal")
    qtbot.addWidget(page)

    row_num = eda.find_first_blank_row("K1B Well Pad", "eht_removal")
    dlg = gui_app.ElectricalEditDialog(page, "K1B Well Pad", "eht_removal", row_num, is_new=True)
    qtbot.addWidget(dlg)
    dlg.widgets["trace_tag"].setText("29103-EHT-0099")
    dlg.save()
    assert dlg.result() == gui_app.QDialog.Accepted

    page.reload()
    assert page.table.rowCount() == 1
    assert page.table.item(0, 0).text() == "29103-EHT-0099"


def test_electrical_edit_dialog_blocks_blank_key_field(qtbot, isolated_app_dir, fake_main_window):
    tmp_path, da = isolated_app_dir
    eda.add_zone("K1B Well Pad")
    row_num = eda.find_first_blank_row("K1B Well Pad", "eht_removal")
    dlg = gui_app.ElectricalEditDialog(None, "K1B Well Pad", "eht_removal", row_num, is_new=True)
    qtbot.addWidget(dlg)
    dlg.widgets["area"].setText("29103")  # trace_tag (the key field) left blank
    dlg.save()
    assert dlg.result() != gui_app.QDialog.Accepted  # save refused, dialog still open
    assert eda.read_index_rows("K1B Well Pad", "eht_removal") == []


def test_electrical_edit_dialog_blocks_duplicate_key_value(qtbot, isolated_app_dir, fake_main_window):
    tmp_path, da = isolated_app_dir
    eda.add_zone("K1B Well Pad")
    r1 = eda.find_first_blank_row("K1B Well Pad", "eht_removal")
    eda.save_row("K1B Well Pad", "eht_removal", r1, {"trace_tag": "29103-EHT-0001"})

    r2 = eda.find_first_blank_row("K1B Well Pad", "eht_removal")
    dlg = gui_app.ElectricalEditDialog(None, "K1B Well Pad", "eht_removal", r2, is_new=True)
    qtbot.addWidget(dlg)
    dlg.widgets["trace_tag"].setText("29103-eht-0001")  # same tag, different case
    dlg.save()
    assert dlg.result() != gui_app.QDialog.Accepted
    assert len(eda.read_index_rows("K1B Well Pad", "eht_removal")) == 1


def test_electrical_index_page_edit_existing_row(qtbot, isolated_app_dir, fake_main_window):
    tmp_path, da = isolated_app_dir
    eda.add_zone("K1B Well Pad")
    row = eda.find_first_blank_row("K1B Well Pad", "eht_removal")
    eda.save_row("K1B Well Pad", "eht_removal", row, {"trace_tag": "29103-EHT-0001"})

    dlg = gui_app.ElectricalEditDialog(None, "K1B Well Pad", "eht_removal", row, is_new=False)
    qtbot.addWidget(dlg)
    assert dlg.widgets["trace_tag"].text() == "29103-EHT-0001"
    dlg.widgets["area"].setText("29103")
    dlg.save()
    assert dlg.result() == gui_app.QDialog.Accepted
    assert eda.read_full_row("K1B Well Pad", "eht_removal", row)["area"] == "29103"


def test_electrical_index_page_remove_selected(qtbot, isolated_app_dir, fake_main_window):
    tmp_path, da = isolated_app_dir
    eda.add_zone("K1B Well Pad")
    row = eda.find_first_blank_row("K1B Well Pad", "eht_removal")
    eda.save_row("K1B Well Pad", "eht_removal", row, {"trace_tag": "29103-EHT-0001"})

    page = gui_app.ElectricalIndexPage(fake_main_window, "K1B Well Pad", "eht_removal")
    qtbot.addWidget(page)
    page.table.selectRow(0)
    page.remove_selected()
    assert eda.read_index_rows("K1B Well Pad", "eht_removal") == []


def test_export_electrical_pdf_flow_writes_and_opens_file(qtbot, isolated_app_dir, fake_main_window, monkeypatch):
    tmp_path, da = isolated_app_dir
    opened = []
    monkeypatch.setattr(gui_app.da, "open_file", lambda p: opened.append(p))
    eda.add_zone("K1B Well Pad")
    row = eda.find_first_blank_row("K1B Well Pad", "eht_removal")
    eda.save_row("K1B Well Pad", "eht_removal", row, {"trace_tag": "29103-EHT-0001"})

    widget = gui_app.QWidget()
    qtbot.addWidget(widget)
    gui_app.export_electrical_pdf_flow(widget, "K1B Well Pad", "eht_removal", row)
    assert len(opened) == 1
    assert PdfReader(str(opened[0])).get_fields()["Text1"].get("/V") == "29103-EHT-0001"


def test_main_window_domain_switch_shows_correct_pages(qtbot, isolated_app_dir, monkeypatch):
    """End-to-end through the real MainWindow, not a stand-in - the
    Instrumentation side must keep working exactly as before, and
    switching to Electrical (with zero zones registered) must not crash."""
    tmp_path, da = isolated_app_dir
    win = gui_app.MainWindow()
    qtbot.addWidget(win)
    win.show()  # isVisible() below reflects the real ancestor chain, not just the widget's own flag
    assert win.active_domain == "instrumentation"
    assert isinstance(win.current_dynamic_page, gui_app.DashboardPage)

    win._switch_domain("electrical")
    assert win.active_domain == "electrical"
    assert isinstance(win.current_dynamic_page, gui_app.ElectricalDashboardPage)
    assert win.add_zone_btn.isVisible()

    win._switch_domain("instrumentation")
    assert isinstance(win.current_dynamic_page, gui_app.DashboardPage)
    assert not win.add_zone_btn.isVisible()


def test_main_window_add_zone_flow_and_sidebar_tree(qtbot, isolated_app_dir, monkeypatch):
    tmp_path, da = isolated_app_dir
    monkeypatch.setattr(gui_app.QInputDialog, "getText",
                         staticmethod(lambda *a, **k: ("K1B Well Pad", True)))
    win = gui_app.MainWindow()
    qtbot.addWidget(win)
    win._switch_domain("electrical")
    win.add_zone()

    assert eda.list_zones() == ["K1B Well Pad"]
    # sidebar tree now has a Dashboard node + one Zone node
    assert win.tree.topLevelItemCount() == 2
    zone_item = win.tree.topLevelItem(1)
    assert zone_item.text(0) == "K1B Well Pad"
    assert zone_item.childCount() == 2  # eht_removal + eht_rtd


def test_switching_to_electrical_never_touches_instrumentation_workbook(qtbot, isolated_app_dir):
    tmp_path, da = isolated_app_dir
    before = da.WORKBOOK_PATH.read_bytes()
    win = gui_app.MainWindow()
    qtbot.addWidget(win)
    win._switch_domain("electrical")
    win._switch_domain("instrumentation")
    after = da.WORKBOOK_PATH.read_bytes()
    assert before == after
