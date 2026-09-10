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
    assert zone_item.childCount() == 4  # eht_removal + eht_rtd + eht_pre_insulation + torqueing


def test_instrumentation_only_shortcuts_are_gated_while_electrical_is_active(
        qtbot, isolated_app_dir, monkeypatch):
    """Search (Ctrl+K), Populating Wizard (Ctrl+Shift+W), and Datasheet
    Import (Ctrl+Shift+I) are reachable via keyboard shortcut even though
    their sidebar buttons are hidden on the Electrical domain - each must
    refuse to open its (Instrumentation-only) dialog while active, not
    just hide its button. Search matters most: opening a result used to
    desync active_domain from the page actually on screen."""
    tmp_path, da = isolated_app_dir
    opened = []
    monkeypatch.setattr(gui_app, "GlobalSearchDialog",
                         lambda *a, **k: opened.append("search") or _StubExecDialog())
    monkeypatch.setattr(gui_app, "PopulatingWizardDialog",
                         lambda *a, **k: opened.append("wizard") or _StubExecDialog())
    monkeypatch.setattr(gui_app, "QFileDialog",
                         type("F", (), {"getOpenFileNames": staticmethod(lambda *a, **k: ([], ""))}))

    win = gui_app.MainWindow()
    qtbot.addWidget(win)
    win._switch_domain("electrical")

    win.open_global_search()
    win.open_populating_wizard()
    win.open_datasheet_import()  # would call QFileDialog.getOpenFileNames if not gated

    assert opened == []
    assert win.active_domain == "electrical"  # never desynced
    assert isinstance(win.current_dynamic_page, gui_app.ElectricalDashboardPage)


class _StubExecDialog:
    def exec(self):
        return gui_app.QDialog.Rejected


def test_switching_to_electrical_never_touches_instrumentation_workbook(qtbot, isolated_app_dir):
    tmp_path, da = isolated_app_dir
    before = da.WORKBOOK_PATH.read_bytes()
    win = gui_app.MainWindow()
    qtbot.addWidget(win)
    win._switch_domain("electrical")
    win._switch_domain("instrumentation")
    after = da.WORKBOOK_PATH.read_bytes()
    assert before == after


# --------------------------------------------------------------------------
# eht_pre_insulation - the third Electrical form. ElectricalDashboardPage/
# ElectricalIndexPage/ElectricalEditDialog are generic over
# ELECTRICAL_EQUIPMENT_TYPES, so these mirror the eht_removal GUI coverage
# above with no new GUI classes involved.
# --------------------------------------------------------------------------

def test_electrical_dashboard_shows_eht_pre_insulation_totals(qtbot, isolated_app_dir, fake_main_window):
    tmp_path, da = isolated_app_dir
    eda.add_zone("K1B Well Pad")
    row = eda.find_first_blank_row("K1B Well Pad", "eht_pre_insulation")
    eda.save_row("K1B Well Pad", "eht_pre_insulation", row, {"trace_number": "TR-PI-001"})

    page = gui_app.ElectricalDashboardPage(fake_main_window)
    qtbot.addWidget(page)
    labels = [w.text() for w in page.findChildren(gui_app.QLabel)]
    assert any(t == "K1B Well Pad" for t in labels)


def test_electrical_dashboard_top_stat_card_attributes_the_1_to_eht_pre_insulation_specifically(
        qtbot, isolated_app_dir, fake_main_window):
    """The sibling test above only asserts SOME label reads '1' somewhere
    on the page - a regression isolated to eht_pre_insulation's own count
    (while the other two types' cards still happen to show a correct
    number) would slip past that. Found by an adversarial review of Phase B.
    This attributes the '1' to the specific StatCard whose own title is
    eht_pre_insulation's label, not just anywhere on the page."""
    tmp_path, da = isolated_app_dir
    eda.add_zone("K1B Well Pad")
    row = eda.find_first_blank_row("K1B Well Pad", "eht_pre_insulation")
    eda.save_row("K1B Well Pad", "eht_pre_insulation", row, {"trace_number": "TR-PI-001"})

    page = gui_app.ElectricalDashboardPage(fake_main_window)
    qtbot.addWidget(page)

    totals_by_title = {}
    for card in page.findChildren(gui_app.StatCard):
        title_label = next(w for w in card.findChildren(gui_app.QLabel) if w.objectName() == "StatLabel")
        number_label = card.findChild(gui_app.QLabel, "StatNumber")
        totals_by_title[title_label.text()] = number_label.text()

    assert totals_by_title["EHT & RTD Pre-Insulation Installation"] == "1"
    assert totals_by_title["EHT Removal & Reinstatement"] == "0"
    assert totals_by_title["EHT & RTD Installation Inspection"] == "0"


def test_electrical_index_page_lists_saved_eht_pre_insulation_rows(qtbot, isolated_app_dir, fake_main_window):
    tmp_path, da = isolated_app_dir
    eda.add_zone("K1B Well Pad")
    row = eda.find_first_blank_row("K1B Well Pad", "eht_pre_insulation")
    eda.save_row("K1B Well Pad", "eht_pre_insulation", row, {"trace_number": "TR-PI-001", "panel_number": "P-12"})

    page = gui_app.ElectricalIndexPage(fake_main_window, "K1B Well Pad", "eht_pre_insulation")
    qtbot.addWidget(page)
    assert page.table.rowCount() == 1
    assert page.table.item(0, 0).text() == "TR-PI-001"
    assert page.table.item(0, 0).data(gui_app.Qt.UserRole) == row


def test_electrical_index_page_add_new_eht_pre_insulation_via_real_dialog(qtbot, isolated_app_dir, fake_main_window):
    tmp_path, da = isolated_app_dir
    eda.add_zone("K1B Well Pad")
    page = gui_app.ElectricalIndexPage(fake_main_window, "K1B Well Pad", "eht_pre_insulation")
    qtbot.addWidget(page)

    row_num = eda.find_first_blank_row("K1B Well Pad", "eht_pre_insulation")
    dlg = gui_app.ElectricalEditDialog(page, "K1B Well Pad", "eht_pre_insulation", row_num, is_new=True)
    qtbot.addWidget(dlg)
    dlg.widgets["trace_number"].setText("TR-PI-099")
    dlg.save()
    assert dlg.result() == gui_app.QDialog.Accepted

    page.reload()
    assert page.table.rowCount() == 1
    assert page.table.item(0, 0).text() == "TR-PI-099"


def test_export_electrical_pdf_flow_eht_pre_insulation_writes_and_opens_file(
        qtbot, isolated_app_dir, fake_main_window, monkeypatch):
    tmp_path, da = isolated_app_dir
    opened = []
    monkeypatch.setattr(gui_app.da, "open_file", lambda p: opened.append(p))
    eda.add_zone("K1B Well Pad")
    row = eda.find_first_blank_row("K1B Well Pad", "eht_pre_insulation")
    eda.save_row("K1B Well Pad", "eht_pre_insulation", row, {"trace_number": "TR-PI-001"})

    widget = gui_app.QWidget()
    qtbot.addWidget(widget)
    gui_app.export_electrical_pdf_flow(widget, "K1B Well Pad", "eht_pre_insulation", row)
    assert len(opened) == 1
    assert PdfReader(str(opened[0])).get_fields()["trace_number"].get("/V") == "TR-PI-001"


# --------------------------------------------------------------------------
# Mass/batch export GUI - the per-row Export checkbox column,
# "Queue All Shown"/"Clear Queue" buttons, and ElectricalExportDialog.
# --------------------------------------------------------------------------

def _three_rows(zone_name="K1B Well Pad"):
    eda.add_zone(zone_name)
    tags = ["TR-001", "TR-002", "TR-003"]
    for tag in tags:
        row = eda.find_first_blank_row(zone_name, "eht_pre_insulation")
        eda.save_row(zone_name, "eht_pre_insulation", row, {"trace_number": tag})
    return tags


def test_electrical_index_page_shows_export_column_with_checkboxes(qtbot, isolated_app_dir, fake_main_window):
    tmp_path, da = isolated_app_dir
    _three_rows()
    page = gui_app.ElectricalIndexPage(fake_main_window, "K1B Well Pad", "eht_pre_insulation")
    qtbot.addWidget(page)
    export_col = page.table.columnCount() - 1
    assert page.table.horizontalHeaderItem(export_col).text() == "Export"
    assert page.table.rowCount() == 3
    for r in range(3):
        checkbox = page.table.cellWidget(r, export_col).findChild(gui_app.QCheckBox)
        assert checkbox is not None
        assert checkbox.isChecked() is False


def test_electrical_index_page_export_checkbox_toggle_persists(qtbot, isolated_app_dir, fake_main_window):
    tmp_path, da = isolated_app_dir
    _three_rows()
    page = gui_app.ElectricalIndexPage(fake_main_window, "K1B Well Pad", "eht_pre_insulation")
    qtbot.addWidget(page)
    export_col = page.table.columnCount() - 1
    checkbox = page.table.cellWidget(0, export_col).findChild(gui_app.QCheckBox)
    checkbox.setChecked(True)
    assert eda.get_electrical_status("K1B Well Pad", "eht_pre_insulation", "TR-001") == {"export": True}

    # reload() must reflect the toggle back into the table
    page.reload()
    checkbox2 = page.table.cellWidget(0, export_col).findChild(gui_app.QCheckBox)
    assert checkbox2.isChecked() is True


def test_electrical_index_page_queue_all_shown_and_clear_queue(qtbot, isolated_app_dir, fake_main_window):
    tmp_path, da = isolated_app_dir
    _three_rows()
    page = gui_app.ElectricalIndexPage(fake_main_window, "K1B Well Pad", "eht_pre_insulation")
    qtbot.addWidget(page)

    page.queue_all_shown_for_export()
    for tag in ("TR-001", "TR-002", "TR-003"):
        assert eda.get_electrical_status("K1B Well Pad", "eht_pre_insulation", tag) == {"export": True}

    page.clear_export_queue_shown()
    for tag in ("TR-001", "TR-002", "TR-003"):
        assert eda.get_electrical_status("K1B Well Pad", "eht_pre_insulation", tag) == {"export": False}


def test_electrical_export_dialog_selected_mode_writes_files_and_clears_checkboxes(
        qtbot, isolated_app_dir, fake_main_window):
    tmp_path, da = isolated_app_dir
    _three_rows()
    eda.set_electrical_status("K1B Well Pad", "eht_pre_insulation", "TR-001", export=True)

    dlg = gui_app.ElectricalExportDialog(None, "K1B Well Pad", "eht_pre_insulation")
    qtbot.addWidget(dlg)
    dlg._run()
    assert dlg.result() == gui_app.QDialog.Accepted

    out_dir = eda.ELECTRICAL_OUTPUT_DIR
    assert (out_dir / "TR-001.pdf").exists()
    assert not (out_dir / "TR-002.pdf").exists()
    assert eda.get_electrical_status("K1B Well Pad", "eht_pre_insulation", "TR-001") == {"export": False}


def test_electrical_export_dialog_all_mode_writes_every_row(qtbot, isolated_app_dir, fake_main_window):
    tmp_path, da = isolated_app_dir
    _three_rows()

    dlg = gui_app.ElectricalExportDialog(None, "K1B Well Pad", "eht_pre_insulation")
    qtbot.addWidget(dlg)
    dlg.mode_group.button(1).setChecked(True)  # "all" mode
    dlg._run()
    assert dlg.result() == gui_app.QDialog.Accepted

    out_dir = eda.ELECTRICAL_OUTPUT_DIR
    for tag in ("TR-001", "TR-002", "TR-003"):
        assert (out_dir / f"{tag}.pdf").exists()


def test_electrical_export_dialog_nothing_selected_does_not_close(qtbot, isolated_app_dir, fake_main_window):
    """mode defaults to 'selected' with nothing checked - Run Export should
    report nothing exported and leave the dialog open, not silently accept."""
    tmp_path, da = isolated_app_dir
    _three_rows()
    dlg = gui_app.ElectricalExportDialog(None, "K1B Well Pad", "eht_pre_insulation")
    qtbot.addWidget(dlg)
    dlg._run()
    assert dlg.result() != gui_app.QDialog.Accepted


def test_electrical_index_page_open_export_reloads_after_dialog_closes(
        qtbot, isolated_app_dir, fake_main_window, monkeypatch):
    tmp_path, da = isolated_app_dir
    _three_rows()
    eda.set_electrical_status("K1B Well Pad", "eht_pre_insulation", "TR-001", export=True)
    page = gui_app.ElectricalIndexPage(fake_main_window, "K1B Well Pad", "eht_pre_insulation")
    qtbot.addWidget(page)

    # Stub exec() to run the export immediately rather than blocking on a
    # real modal event loop, mirroring how other dialog-opening flows in
    # this suite are tested offscreen.
    def fake_exec(self):
        self._run()
        return gui_app.QDialog.Accepted

    monkeypatch.setattr(gui_app.ElectricalExportDialog, "exec", fake_exec)
    page.open_export()

    out_dir = eda.ELECTRICAL_OUTPUT_DIR
    assert (out_dir / "TR-001.pdf").exists()
    # reload() picked up the cleared checkbox
    export_col = page.table.columnCount() - 1
    row_of_tr001 = next(r for r in range(page.table.rowCount()) if page.table.item(r, 0).text() == "TR-001")
    checkbox = page.table.cellWidget(row_of_tr001, export_col).findChild(gui_app.QCheckBox)
    assert checkbox.isChecked() is False


# --------------------------------------------------------------------------
# torqueing - the fourth Electrical form. Also the only one whose
# ElectricalExportDialog shows an "Include signature" checkbox.
# --------------------------------------------------------------------------

def test_electrical_dashboard_shows_torqueing_totals(qtbot, isolated_app_dir, fake_main_window):
    tmp_path, da = isolated_app_dir
    eda.add_zone("K1B Well Pad")
    row = eda.find_first_blank_row("K1B Well Pad", "torqueing")
    eda.save_row("K1B Well Pad", "torqueing", row, {"torque_record_number": "TR-100"})

    page = gui_app.ElectricalDashboardPage(fake_main_window)
    qtbot.addWidget(page)
    totals_by_title = {}
    for card in page.findChildren(gui_app.StatCard):
        title_label = next(w for w in card.findChildren(gui_app.QLabel) if w.objectName() == "StatLabel")
        number_label = card.findChild(gui_app.QLabel, "StatNumber")
        totals_by_title[title_label.text()] = number_label.text()
    assert totals_by_title["Torqueing Report"] == "1"


def test_electrical_index_page_lists_saved_torqueing_rows(qtbot, isolated_app_dir, fake_main_window):
    tmp_path, da = isolated_app_dir
    eda.add_zone("K1B Well Pad")
    row = eda.find_first_blank_row("K1B Well Pad", "torqueing")
    eda.save_row("K1B Well Pad", "torqueing", row, {"torque_record_number": "TR-100", "reference_tag_number": "TAG-1"})

    page = gui_app.ElectricalIndexPage(fake_main_window, "K1B Well Pad", "torqueing")
    qtbot.addWidget(page)
    assert page.table.rowCount() == 1
    assert page.table.item(0, 0).text() == "TR-100"
    assert page.table.item(0, 0).data(gui_app.Qt.UserRole) == row


def test_electrical_edit_dialog_has_a_widget_for_every_torqueing_field(qtbot, isolated_app_dir, fake_main_window):
    tmp_path, da = isolated_app_dir
    import torqueing_schema
    eda.add_zone("K1B Well Pad")
    row = eda.find_first_blank_row("K1B Well Pad", "torqueing")
    dlg = gui_app.ElectricalEditDialog(None, "K1B Well Pad", "torqueing", row, is_new=True)
    qtbot.addWidget(dlg)
    assert set(dlg.widgets.keys()) == {f["id"] for f in torqueing_schema.LOG_COLUMNS}
    # the System No. dropdown is a real choice field, not a plain line edit
    assert isinstance(dlg.widgets["system_number"], gui_app.QComboBox)


def test_electrical_edit_dialog_preserves_a_system_number_not_in_the_choice_list(
        qtbot, isolated_app_dir, fake_main_window):
    """Regression test: a stored system_number that isn't byte-for-byte one
    of the fixed SYSTEM_NUMBER_CHOICES (a legacy value, an import, or just
    a stored value predating a choice-list change) must survive opening
    and saving the row unchanged - not get silently blanked because the
    combo couldn't find it and fell back to an unselected state."""
    tmp_path, da = isolated_app_dir
    eda.add_zone("K1B Well Pad")
    row = eda.find_first_blank_row("K1B Well Pad", "torqueing")
    eda.save_row("K1B Well Pad", "torqueing", row, {
        "torque_record_number": "TR-100", "system_number": "K1B-EHouse-LEGACY-VALUE",
    })

    dlg = gui_app.ElectricalEditDialog(None, "K1B Well Pad", "torqueing", row, is_new=False)
    qtbot.addWidget(dlg)
    combo = dlg.widgets["system_number"]
    assert combo.currentText() == "K1B-EHouse-LEGACY-VALUE"
    assert dlg.is_dirty() is False  # opening the dialog alone must not read as a change

    dlg.save()
    full = eda.read_full_row("K1B Well Pad", "torqueing", row)
    assert full["system_number"] == "K1B-EHouse-LEGACY-VALUE"


def test_electrical_index_page_add_new_torqueing_via_real_dialog(qtbot, isolated_app_dir, fake_main_window):
    tmp_path, da = isolated_app_dir
    eda.add_zone("K1B Well Pad")
    page = gui_app.ElectricalIndexPage(fake_main_window, "K1B Well Pad", "torqueing")
    qtbot.addWidget(page)

    row_num = eda.find_first_blank_row("K1B Well Pad", "torqueing")
    dlg = gui_app.ElectricalEditDialog(page, "K1B Well Pad", "torqueing", row_num, is_new=True)
    qtbot.addWidget(dlg)
    dlg.widgets["torque_record_number"].setText("TR-999")
    dlg.save()
    assert dlg.result() == gui_app.QDialog.Accepted

    page.reload()
    assert page.table.rowCount() == 1
    assert page.table.item(0, 0).text() == "TR-999"


def test_export_electrical_pdf_flow_torqueing_writes_and_opens_file(
        qtbot, isolated_app_dir, fake_main_window, monkeypatch):
    tmp_path, da = isolated_app_dir
    opened = []
    monkeypatch.setattr(gui_app.da, "open_file", lambda p: opened.append(p))
    eda.add_zone("K1B Well Pad")
    row = eda.find_first_blank_row("K1B Well Pad", "torqueing")
    eda.save_row("K1B Well Pad", "torqueing", row, {"torque_record_number": "TR-100"})

    widget = gui_app.QWidget()
    qtbot.addWidget(widget)
    gui_app.export_electrical_pdf_flow(widget, "K1B Well Pad", "torqueing", row)
    assert len(opened) == 1
    assert PdfReader(str(opened[0])).get_fields()["Text131"].get("/V") == "TR-100"


def test_electrical_export_dialog_shows_signature_checkbox_only_for_torqueing(
        qtbot, isolated_app_dir, fake_main_window):
    tmp_path, da = isolated_app_dir
    eda.add_zone("K1B Well Pad")

    dlg_torqueing = gui_app.ElectricalExportDialog(None, "K1B Well Pad", "torqueing")
    qtbot.addWidget(dlg_torqueing)
    assert dlg_torqueing.signature_check is not None
    assert dlg_torqueing.signature_check.isChecked() is True

    dlg_removal = gui_app.ElectricalExportDialog(None, "K1B Well Pad", "eht_removal")
    qtbot.addWidget(dlg_removal)
    assert dlg_removal.signature_check is None


def test_electrical_export_dialog_torqueing_signature_checkbox_controls_the_stamp(
        qtbot, isolated_app_dir, fake_main_window):
    tmp_path, da = isolated_app_dir
    eda.add_zone("K1B Well Pad")
    row = eda.find_first_blank_row("K1B Well Pad", "torqueing")
    eda.save_row("K1B Well Pad", "torqueing", row, {"torque_record_number": "TR-100"})

    dlg = gui_app.ElectricalExportDialog(None, "K1B Well Pad", "torqueing")
    qtbot.addWidget(dlg)
    dlg.mode_group.button(1).setChecked(True)  # "all" mode
    dlg.signature_check.setChecked(False)
    dlg._run()
    assert dlg.result() == gui_app.QDialog.Accepted

    out_path = eda.ELECTRICAL_OUTPUT_DIR / "TR-100.pdf"
    page = PdfReader(str(out_path)).pages[0]
    has_stamp = any(str(k).startswith("/FormXob")
                     for k in page.get("/Resources", {}).get("/XObject", {}).keys())
    assert not has_stamp
