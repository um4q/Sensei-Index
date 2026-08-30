# -*- coding: utf-8 -*-
"""Phase 10.4 - MasterListImportDialog, driven end-to-end offscreen via
pytest-qt (no real display needed - see conftest.py)."""
import openpyxl
import pytest

import gui_app


@pytest.fixture(autouse=True)
def _no_modal_message_boxes(monkeypatch):
    """QMessageBox.information/.critical/.warning are modal - .exec()ing
    one with no display and no human to click it hangs the test suite
    forever. Every test in this file drives the dialog headlessly, so
    replace them with no-ops (return value doesn't matter - none of the
    code under test branches on it)."""
    monkeypatch.setattr(gui_app.QMessageBox, "information", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(gui_app.QMessageBox, "critical", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(gui_app.QMessageBox, "warning", staticmethod(lambda *a, **k: None))


def _make_master_list_xlsx(path):
    wb = openpyxl.Workbook()
    ws1 = wb.active
    ws1.title = "29103-K1B Pad"
    ws1.append(["Tag Number", "Service", "Instrument Type Description", "Model", "Manufacturer"])
    ws1.append(["29103-PIT -2171", "SVC A", "PRESSURE INDICATING TRANSMITTER", "233.34", "WIKA"])
    ws1.append(["29103-XV  -0100", "SVC B", "SHUTDOWN VALVE", "", ""])
    ws2 = wb.create_sheet("9050 SUS")
    ws2.append(["Tag_Number", "Service", "Instrument_Type_Desc"])
    ws2.append(["9050-FI-922", "SVC D", "FIELD FLOW INDICATOR"])
    wb.save(path)
    return path


def test_full_import_flow_writes_master_list_json(qtbot, isolated_app_dir):
    tmp_path, da = isolated_app_dir
    ml_path = _make_master_list_xlsx(tmp_path / "Instrumentation_Master_List.xlsx")

    dlg = gui_app.MasterListImportDialog(None, main_window=None)
    qtbot.addWidget(dlg)

    # Step 1: simulate the file picker choosing ml_path (browse itself is
    # a blocking native dialog - test the effect, not QFileDialog itself).
    items_by_sheet, summaries = da.preview_master_list(ml_path)
    dlg.file_path = str(ml_path)
    dlg.items_by_sheet = items_by_sheet
    dlg.summaries = summaries
    dlg.path_edit.setText(str(ml_path))
    dlg._populate_summary_table()
    dlg._rebuild_step2()
    dlg._refresh_step()

    assert dlg.summary_table.rowCount() == 2
    assert dlg.next_btn.isEnabled()

    # Step 1 -> Step 2
    dlg._go_next()
    assert dlg.stack.currentIndex() == 1
    assert set(dlg.series_combos.keys()) == {"29103-K1B Pad", "9050 SUS"}
    # 29103 sheet should auto-guess series 29103 (it's registered in isolated_app_dir)
    assert dlg.series_combos["29103-K1B Pad"].currentData() == 29103
    # 9050 SUS has no registered series numbered 9050 - left unmapped
    assert dlg.series_combos["9050 SUS"].currentData() is None

    # Step 2 -> Step 3
    dlg._go_next()
    assert dlg.stack.currentIndex() == 2
    assert "29103-K1B Pad" in dlg.step3_summary.text()
    assert dlg.next_btn.text() == "Import"

    # Step 3: Import
    dlg._go_next()

    snapshot = da.load_master_list()
    assert snapshot is not None
    assert len(snapshot["items"]) == 3
    by_tag = {it["tag"]: it for it in snapshot["items"]}
    assert by_tag["29103-PIT-2171"]["mapped_series"] == 29103
    assert by_tag["9050-FI-922"]["mapped_series"] is None


def test_next_disabled_until_a_file_is_parsed(qtbot, isolated_app_dir):
    tmp_path, da = isolated_app_dir
    dlg = gui_app.MasterListImportDialog(None, main_window=None)
    qtbot.addWidget(dlg)
    assert dlg.stack.currentIndex() == 0
    assert not dlg.next_btn.isEnabled()


def test_dialog_prefills_remembered_master_list_path(qtbot, isolated_app_dir):
    tmp_path, da = isolated_app_dir
    da.set_setting("master_list_path", str(tmp_path / "somewhere.xlsx"))
    dlg = gui_app.MasterListImportDialog(None, main_window=None)
    qtbot.addWidget(dlg)
    assert dlg.path_edit.text() == str(tmp_path / "somewhere.xlsx")
